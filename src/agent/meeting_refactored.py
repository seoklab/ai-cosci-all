"""Subtask-centric Virtual Lab with sequential collaboration and red flag enforcement."""

import os
import re
from typing import Optional, List, Dict, Any
from src.agent.agent_refactored import ScientificAgent, AgentPersona
from src.agent.team_manager_refactored import (
    create_research_team_with_plan,
    create_pi_persona,
    create_critic_persona,
)
from src.utils.logger import get_logger


class VirtualLabMeeting:
    """Subtask-centric Virtual Lab with sequential specialist collaboration.

    Key differences from parallel model:
    1. PI decomposes question into sequential subtasks
    2. Specialists execute subtasks in order (not in parallel)
    3. Each specialist receives full context from previous specialists
    4. Critic outputs structured Red Flag Checklist
    5. PI must address all red flags in final synthesis
    6. Complex subtasks can trigger sub-meetings (mini-dialogues)
    """

    def __init__(
        self,
        user_question: str,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
        max_team_size: int = 3,
        verbose: bool = False,
        data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data",
        input_dir: Optional[str] = None
    ):
        self.user_question = user_question
        self.verbose = verbose
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.data_dir = data_dir
        self.input_dir = input_dir if input_dir is not None else data_dir
        self.logger = get_logger()

        self.logger.subsection("INITIALIZING SUBTASK-CENTRIC VIRTUAL LAB")

        # Initialize PI
        self.logger.progress("Creating Principal Investigator agent...")
        self.pi = ScientificAgent(
            persona=create_pi_persona(),
            api_key=api_key,
            model=model,
            provider=provider,
            data_dir=data_dir,
            input_dir=self.input_dir
        )

        # PI designs team AND research plan
        self.logger.progress("PI is designing team and research plan...")

        team_specs, self.research_plan = create_research_team_with_plan(
            user_question,
            self.pi.client,
            max_team_size=max_team_size
        )

        self.logger.success(f"Team designed: {len(team_specs)} specialists")
        for spec in team_specs:
            self.logger.info(f"  • {spec['title']}", indent=2)

        self.logger.success(f"Research plan: {len(self.research_plan)} subtasks")
        for subtask in self.research_plan:
            assigned_str = ', '.join(subtask['assigned_specialists'])
            self.logger.info(f"  {subtask['subtask_id']}. {subtask['description']}", indent=2)
            self.logger.verbose(f"     → Assigned: {assigned_str}", indent=2)

        # Create specialist agents (indexed by title for lookup)
        self.specialists = {
            spec['title']: ScientificAgent(
                persona=AgentPersona(**spec),
                api_key=api_key,
                model=model,
                provider=provider,
                data_dir=data_dir,
                input_dir=self.input_dir
            )
            for spec in team_specs
        }

        # Add the Scientific Critic
        self.critic = ScientificAgent(
            persona=create_critic_persona(),
            api_key=api_key,
            model=model,
            provider=provider,
            data_dir=data_dir,
            input_dir=self.input_dir
        )

        self.meeting_transcript = []
        self.subtask_outputs = {}  # Track outputs from each subtask

    def _execute_subtask_sequential(self, subtask: Dict[str, Any]) -> str:
        """Execute a single subtask with assigned specialists in sequence.

        Args:
            subtask: Subtask specification from research_plan

        Returns:
            Combined output from all assigned specialists
        """
        subtask_id = subtask['subtask_id']
        description = subtask['description']
        assigned = subtask['assigned_specialists']
        expected_outputs = subtask['expected_outputs']
        dependencies = subtask.get('dependencies', [])

        self.logger.subtask(subtask_id, description, assigned)
        self.logger.verbose(f"Expected outputs: {', '.join(expected_outputs)}", indent=2)
        if dependencies:
            self.logger.verbose(f"Dependencies: {', '.join(dependencies)}", indent=2)

        # Build context from dependent subtasks
        dependency_context = self._build_dependency_context(dependencies)

        # If 2+ specialists assigned, run a sub-meeting
        if len(assigned) >= 2:
            self.logger.progress(f"Sub-meeting: {' & '.join(assigned)} collaborating...", indent=2)
            result = self._run_submeeting(subtask, dependency_context, assigned)
        else:
            # Single specialist execution
            specialist_title = assigned[0]
            if specialist_title not in self.specialists:
                self.logger.warning(f"Specialist '{specialist_title}' not found, skipping", indent=2)
                return ""

            specialist = self.specialists[specialist_title]

            # Construct subtask prompt with full context
            subtask_prompt = f"""**SUBTASK {subtask_id}:** {description}

**Expected Outputs:** {', '.join(expected_outputs)}

**Context from Previous Subtasks:**
{dependency_context if dependency_context else "This is the first subtask - no previous context."}

**Your Task:**
Execute this subtask using your expertise. Remember to:
1. If previous specialists generated files/data, READ them using tools (read_file, execute_python)
2. EXPLICITLY reference and build upon their findings
3. Generate the expected outputs
4. Create artifacts (files, plots, results) for downstream specialists
5. Be specific and cite exact data/results

Use tools as needed. Be concise but thorough."""

            self.logger.agent_action(specialist_title, f"Working on subtask {subtask_id}", indent=2)

            result = specialist.run(subtask_prompt, verbose=self.verbose)

            self.logger.verbose(f"{specialist_title} completed subtask", indent=2)
            if self.verbose:
                self.logger.result_summary(f"{specialist_title} output", result, max_lines=5)

            # Add to transcript
            self.meeting_transcript.append({
                "speaker": specialist_title,
                "subtask_id": subtask_id,
                "role": f"Subtask {subtask_id}",
                "content": result
            })

        # Store outputs for this subtask
        self.subtask_outputs[subtask_id] = result
        return result

    def _run_submeeting(
        self,
        subtask: Dict[str, Any],
        dependency_context: str,
        assigned: List[str]
    ) -> str:
        """Run a mini-dialogue between 2 specialists for complex subtask.

        Args:
            subtask: The subtask specification
            dependency_context: Context from previous subtasks
            assigned: List of specialist titles

        Returns:
            Combined output from the sub-meeting
        """
        subtask_id = subtask['subtask_id']
        description = subtask['description']
        expected_outputs = subtask['expected_outputs']

        # Get the specialist agents
        specialists_in_meeting = [
            self.specialists[title] for title in assigned if title in self.specialists
        ]

        if len(specialists_in_meeting) < 2:
            # Fallback to single specialist if one is missing
            if len(specialists_in_meeting) == 1:
                return specialists_in_meeting[0].run(
                    f"Subtask: {description}\nContext: {dependency_context}",
                    verbose=self.verbose
                )
            return ""

        sub_meeting_transcript = []
        num_turns = 2  # Each specialist gets 2 turns

        initial_prompt = f"""**COLLABORATIVE SUBTASK {subtask_id}:** {description}

**Expected Outputs:** {', '.join(expected_outputs)}

**Context from Previous Subtasks:**
{dependency_context if dependency_context else "This is the first subtask."}

**Sub-meeting Participants:** {', '.join(assigned)}

You are working TOGETHER on this subtask. This is a mini-dialogue where you'll each contribute your expertise.

**Your first contribution:**
- Review the subtask and context
- Outline your approach
- Use tools if needed
- Prepare findings for discussion

Be concise (3-5 sentences or one analysis). You'll have another turn to refine."""

        # Turn 1: Both specialists contribute initial thoughts
        for i, specialist in enumerate(specialists_in_meeting):
            if self.verbose:
                print(f"\n--- Sub-meeting Turn 1: {specialist.persona.title} ---")

            # Add context from previous sub-meeting turn
            if i > 0:
                context_from_peer = f"\n\n**{specialists_in_meeting[i-1].persona.title}'s contribution:**\n{sub_meeting_transcript[-1]['content']}"
                turn_prompt = initial_prompt + context_from_peer
            else:
                turn_prompt = initial_prompt

            response = specialist.run(turn_prompt, verbose=self.verbose)

            sub_meeting_transcript.append({
                "speaker": specialist.persona.title,
                "turn": 1,
                "content": response
            })

            self.meeting_transcript.append({
                "speaker": specialist.persona.title,
                "subtask_id": subtask_id,
                "role": f"Subtask {subtask_id} - Turn 1",
                "content": response
            })

        # Turn 2: Refinement and consensus
        for i, specialist in enumerate(specialists_in_meeting):
            if self.verbose:
                print(f"\n--- Sub-meeting Turn 2: {specialist.persona.title} ---")

            # Build context from both Turn 1 contributions
            turn1_context = "\n\n".join([
                f"**{entry['speaker']} (Turn 1):**\n{entry['content']}"
                for entry in sub_meeting_transcript if entry['turn'] == 1
            ])

            refinement_prompt = f"""**COLLABORATIVE SUBTASK {subtask_id} - FINAL TURN**

**Subtask:** {description}
**Expected Outputs:** {', '.join(expected_outputs)}

**Turn 1 Discussion:**
{turn1_context}

**Your final contribution:**
- Build on/validate your colleague's findings
- Add your unique expertise
- Synthesize toward consensus if possible
- Generate concrete outputs
- Reference specific data/files

This is your last turn - make it count!"""

            response = specialist.run(refinement_prompt, verbose=self.verbose)

            sub_meeting_transcript.append({
                "speaker": specialist.persona.title,
                "turn": 2,
                "content": response
            })

            self.meeting_transcript.append({
                "speaker": specialist.persona.title,
                "subtask_id": subtask_id,
                "role": f"Subtask {subtask_id} - Turn 2",
                "content": response
            })

        # Synthesize sub-meeting results
        combined_output = "\n\n".join([
            f"[{entry['speaker']} - Turn {entry['turn']}]: {entry['content']}"
            for entry in sub_meeting_transcript
        ])

        if self.verbose:
            print(f"\n[Sub-meeting completed: {len(sub_meeting_transcript)} contributions]")

        return combined_output

    def _build_dependency_context(self, dependencies: List[int]) -> str:
        """Build context string from dependent subtasks.

        Args:
            dependencies: List of subtask IDs this subtask depends on

        Returns:
            Formatted context string with previous subtask outputs
        """
        if not dependencies:
            return ""

        context_parts = []
        for dep_id in dependencies:
            if dep_id in self.subtask_outputs:
                # Find the subtask description
                dep_subtask = next(
                    (st for st in self.research_plan if st['subtask_id'] == dep_id),
                    None
                )
                if dep_subtask:
                    desc = dep_subtask['description']
                    context_parts.append(
                        f"**Subtask {dep_id} ({desc}):**\n{self.subtask_outputs[dep_id]}"
                    )

        return "\n\n" + "-" * 60 + "\n\n".join(context_parts) if context_parts else ""

    def _extract_red_flags(self, critique_text: str) -> List[Dict[str, str]]:
        """Extract structured red flags from critic's output.

        Args:
            critique_text: The critic's feedback text

        Returns:
            List of red flag dictionaries with id, severity, issue, and required_fix
        """
        red_flags = []

        # Parse red flags from the critique
        # Expected format:
        # [CRITICAL - Category]
        # - Flag ID: XX-N
        # - Issue: ...
        # - Required Fix: ...

        flag_pattern = r'\[(CRITICAL|MODERATE|MINOR).*?\].*?Flag ID:\s*([^\n]+).*?Issue:\s*([^\n]+).*?Required Fix:\s*([^\n]+)'
        matches = re.findall(flag_pattern, critique_text, re.DOTALL | re.IGNORECASE)

        for match in matches:
            severity, flag_id, issue, fix = match
            red_flags.append({
                "severity": severity.strip(),
                "flag_id": flag_id.strip(),
                "issue": issue.strip(),
                "required_fix": fix.strip()
            })

        # If no structured flags found, but text contains "CRITICAL" or "red flag", create generic flags
        if not red_flags and any(keyword in critique_text.lower() for keyword in ['critical', 'red flag', 'must fix']):
            # Try to extract issues from text
            lines = critique_text.split('\n')
            for i, line in enumerate(lines):
                if any(k in line.lower() for k in ['critical', 'error', 'missing', 'incorrect']):
                    red_flags.append({
                        "severity": "CRITICAL",
                        "flag_id": f"GEN-{i+1}",
                        "issue": line.strip(),
                        "required_fix": "Address this issue"
                    })

        return red_flags

    def run_meeting(self, num_rounds: int = 1) -> str:
        """Run the subtask-centric Virtual Lab meeting.

        Args:
            num_rounds: Number of full research plan iterations (default: 1)
                       Note: With sequential subtasks, 1 round is often sufficient

        Returns:
            Final synthesized answer from PI with red flags addressed
        """
        self.logger.subsection("STARTING SUBTASK-CENTRIC MEETING")

        # Phase 1: PI opens with research plan overview
        self.logger.subsection("PHASE 1: PI Research Plan Overview")

        plan_summary = "\n".join([
            f"{st['subtask_id']}. {st['description']} (Assigned: {', '.join(st['assigned_specialists'])})"
            for st in self.research_plan
        ])

        pi_intro_prompt = f"""Open the research meeting and present the research plan.

**Research Question:** "{self.user_question}"

**Your team:**
{self._format_team_list()}

**Research Plan:**
{plan_summary}

Provide a brief opening (2-3 sentences) that:
1. Frames the research question
2. Outlines the subtask-based approach
3. Sets expectations for sequential collaboration"""

        pi_intro = self.pi.run(pi_intro_prompt, verbose=self.verbose)
        self.meeting_transcript.append({
            "speaker": "PI",
            "role": "Opening - Research Plan",
            "content": pi_intro
        })

        # Phase 2: Execute research plan (sequential subtasks)
        self.logger.subsection("PHASE 2: SEQUENTIAL SUBTASK EXECUTION")
        self.logger.info(f"Executing {len(self.research_plan)} subtasks in sequence...")

        for subtask in self.research_plan:
            self._execute_subtask_sequential(subtask)

        self.logger.success(f"All {len(self.research_plan)} subtasks completed")

        # Phase 3: Critic review with Red Flag Checklist
        self.logger.subsection("PHASE 3: CRITIC RED FLAG REVIEW")

        all_subtask_outputs = "\n\n".join([
            f"=== SUBTASK {st_id} ===\n{output}"
            for st_id, output in self.subtask_outputs.items()
        ])

        critique_prompt = f"""Review all subtask outputs and generate a Red Flag Checklist.

**Original Question:** {self.user_question}

**All Subtask Outputs:**
{all_subtask_outputs}

**Your Task:**
Generate a structured Red Flag Checklist identifying CRITICAL flaws that MUST be fixed.

Use this format for each flag:

[CRITICAL/MODERATE/MINOR - Category]
- Flag ID: XX-N
- Issue: [Specific problem]
- Location: [Which subtask/analysis]
- Required Fix: [Exact action needed]

Focus on:
- Incorrect analyses
- Missing critical steps
- Unsupported claims
- Data not properly examined
- Files mentioned but not analyzed

If work is sound, output: "No critical red flags detected."""

        self.logger.agent_action("Scientific Critic", "Reviewing all subtask outputs for red flags", indent=2)

        critique = self.critic.run(critique_prompt, verbose=False)

        self.meeting_transcript.append({
            "speaker": "Critic",
            "role": "Red Flag Checklist",
            "content": critique
        })

        if self.verbose:
            print(f"\nCritic Red Flags:\n{critique[:500]}...")

        # Extract red flags
        red_flags = self._extract_red_flags(critique)

        if self.verbose:
            print(f"\n[Extracted {len(red_flags)} red flags]")
            for flag in red_flags:
                print(f"  - [{flag['severity']}] {flag['flag_id']}: {flag['issue'][:60]}...")

        # Phase 4: PI Final Synthesis WITH Red Flag Resolution
        if self.verbose:
            print("\n" + "=" * 60)
            print("[PHASE 4: FINAL SYNTHESIS WITH RED FLAG RESOLUTION]")
            print("=" * 60)

        # Build full transcript
        full_transcript = self._build_full_transcript()

        # Build red flag requirements
        red_flag_section = ""
        if red_flags:
            critical_flags = [f for f in red_flags if f['severity'] == 'CRITICAL']
            if critical_flags:
                red_flag_section = "\n\n**CRITICAL RED FLAGS TO ADDRESS:**\n"
                for flag in critical_flags:
                    red_flag_section += f"\n- [{flag['flag_id']}] {flag['issue']}\n  Required Fix: {flag['required_fix']}\n"
                red_flag_section += "\n**YOU MUST** include a 'Red Flag Resolution' section addressing EVERY critical flag."

        final_prompt = f"""Synthesize the team's findings into a final answer with Red Flag Resolution.

**Original Question:** "{self.user_question}"

**Research Plan Execution:**
{full_transcript}

**Critic's Red Flag Checklist:**
{critique}
{red_flag_section}

**Your Task:**
Provide a comprehensive final answer with these sections:

1. **Executive Summary** - Direct answer to the research question
2. **Key Findings** - Integrate insights from all subtasks
3. **Red Flag Resolution** - Address EVERY critical red flag:
   - For each flag: state what was done to resolve it
   - If a fix requires additional analysis, acknowledge and propose next steps
   - If a flag is invalid, explain why
4. **Evidence & Citations** - Preserve all citations, PMIDs, files, databases mentioned
5. **Limitations & Uncertainties** - Acknowledge gaps
6. **Recommended Next Steps** - If appropriate

**CRITICAL REQUIREMENT:**
The "Red Flag Resolution" section is MANDATORY if there are critical flags.
If you do not address ALL critical flags, your synthesis is INCOMPLETE."""

        self.logger.agent_action("PI", "Synthesizing final answer with red flag resolution", indent=2)

        final_answer = self.pi.run(final_prompt, verbose=self.verbose)

        self.meeting_transcript.append({
            "speaker": "PI",
            "role": "Final Synthesis",
            "content": final_answer
        })

        # Verify red flags were addressed
        if red_flags:
            critical_flags = [f for f in red_flags if f['severity'] == 'CRITICAL']
            if critical_flags:
                addressed_count = sum(
                    1 for flag in critical_flags
                    if flag['flag_id'] in final_answer or flag['issue'][:30] in final_answer
                )

                if addressed_count == len(critical_flags):
                    self.logger.success(f"Red Flag Resolution: All {len(critical_flags)} critical flags addressed", indent=2)
                elif addressed_count > 0:
                    self.logger.warning(f"Red Flag Resolution: {addressed_count}/{len(critical_flags)} critical flags addressed", indent=2)
                else:
                    self.logger.error(f"Red Flag Resolution: No critical flags addressed ({len(critical_flags)} pending)", indent=2)

                if addressed_count < len(critical_flags):
                    # Add warning to final answer
                    final_answer += f"\n\n⚠️ **WARNING:** Not all critical red flags were fully addressed ({addressed_count}/{len(critical_flags)}). Further iteration may be needed."

        # Append references
        self.logger.progress("Appending references section...", indent=2)
        final_answer_with_refs = self._append_references_section(final_answer)

        self.logger.success("Virtual Lab meeting completed")

        return final_answer_with_refs

    def _format_team_list(self) -> str:
        """Format the team member list for prompts."""
        team_list = []
        for title, agent in self.specialists.items():
            team_list.append(f"- {title}: {agent.persona.expertise}")
        return "\n".join(team_list)

    def _build_full_transcript(self) -> str:
        """Build the full meeting transcript grouped by subtask."""
        transcript_parts = []

        # Group by subtask
        for subtask in self.research_plan:
            subtask_id = subtask['subtask_id']
            subtask_entries = [
                entry for entry in self.meeting_transcript
                if entry.get('subtask_id') == subtask_id
            ]

            if subtask_entries:
                transcript_parts.append(
                    f"=== SUBTASK {subtask_id}: {subtask['description']} ==="
                )
                for entry in subtask_entries:
                    transcript_parts.append(
                        f"[{entry['speaker']}]: {entry['content']}"
                    )
                transcript_parts.append("")  # Blank line

        # Add non-subtask entries (PI intro, critic, etc.)
        other_entries = [
            entry for entry in self.meeting_transcript
            if 'subtask_id' not in entry
        ]
        for entry in other_entries:
            if entry['speaker'] != 'PI' or 'Opening' in entry['role']:
                transcript_parts.append(
                    f"=== {entry['speaker']} ({entry['role']}) ===\n{entry['content']}\n"
                )

        return "\n".join(transcript_parts)

    def get_transcript(self) -> List[Dict]:
        """Get the full meeting transcript."""
        return self.meeting_transcript

    def _append_references_section(self, final_answer: str) -> str:
        """Extract and append references section to final answer."""
        pmids = set()
        data_sources = set()

        for entry in self.meeting_transcript:
            content = entry['content']

            # Extract PMIDs
            pmid_matches = re.findall(r'PMID:\s*(\d+)', content, re.IGNORECASE)
            pmids.update(pmid_matches)

            # Extract file references
            file_matches = re.findall(
                r'([A-Za-z0-9_\-]+\.(?:csv|txt|bam|pod5|pdf|png|jpg))',
                content
            )
            data_sources.update(file_matches)

            # Extract database mentions
            db_keywords = [
                'DrugBank', 'BindingDB', 'PubMed', 'PPI database',
                'GWAS', 'StringDB', 'UniProt', 'Semantic Scholar'
            ]
            for keyword in db_keywords:
                if keyword.lower() in content.lower():
                    data_sources.add(keyword)

        # Build references section
        references_parts = []

        if pmids:
            references_parts.append("\n## References\n")
            references_parts.append("**Literature Cited:**")
            for pmid in sorted(pmids):
                references_parts.append(
                    f"- PMID: {pmid} (https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"
                )

        if data_sources:
            if not pmids:
                references_parts.append("\n## References\n")
            references_parts.append("\n**Data Sources:**")
            for source in sorted(data_sources):
                references_parts.append(f"- {source}")

        if references_parts:
            return final_answer + "\n" + "\n".join(references_parts)
        else:
            return final_answer


def run_virtual_lab(
    question: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    num_rounds: int = 1,  # Changed default to 1 for sequential workflow
    max_team_size: int = 3,
    verbose: bool = False,
    data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data",
    input_dir: Optional[str] = None
) -> str:
    """Run a subtask-centric Virtual Lab meeting.

    Args:
        question: Research question to solve
        api_key: API key (defaults to env var)
        model: Model to use (defaults based on provider)
        provider: 'anthropic' or 'openrouter' (defaults to env var)
        num_rounds: Number of research plan iterations (default: 1)
        max_team_size: Maximum number of specialists (default: 3)
        verbose: Print detailed transcript
        data_dir: Path to database directory
        input_dir: Path to question-specific input data

    Returns:
        Final synthesized answer with red flags addressed
    """
    if provider is None:
        provider = os.getenv("API_PROVIDER", "anthropic")

    if model is None:
        if provider == "anthropic":
            model = "claude-sonnet-4-20250514"
        else:
            model = "anthropic/claude-sonnet-4"

    meeting = VirtualLabMeeting(
        user_question=question,
        api_key=api_key,
        model=model,
        provider=provider,
        max_team_size=max_team_size,
        verbose=verbose,
        data_dir=data_dir,
        input_dir=input_dir
    )

    final_answer = meeting.run_meeting(num_rounds=num_rounds)
    return final_answer
