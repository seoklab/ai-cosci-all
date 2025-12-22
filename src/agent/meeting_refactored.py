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
from src.utils.output_manager import get_current_run_dir


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
        input_dir: Optional[str] = None,
        max_iterations: int = 30,
        save_intermediate: bool = False
    ):
        self.user_question = user_question
        self.verbose = verbose
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.data_dir = data_dir
        self.input_dir = input_dir if input_dir is not None else data_dir
        self.max_iterations = max_iterations
        self.save_intermediate = save_intermediate
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
            input_dir=self.input_dir,
            max_iterations=max_iterations
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
                input_dir=self.input_dir,
                max_iterations=max_iterations
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
            input_dir=self.input_dir,
            max_iterations=max_iterations
        )

        self.meeting_transcript = []
        self.subtask_outputs = {}  # Track outputs from each subtask

        # Multi-round tracking
        self.round_outputs = {}  # {round_num: {subtask_id: output}}
        self.round_syntheses = []  # PI synthesis after each round
        self.round_critiques = []  # Critic reviews after each round
        self.current_round = 0

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
            self.logger.verbose(f"Dependencies: {', '.join(map(str, dependencies))}", indent=2)

        # Build cumulative context from all previous work (multi-round aware)
        if self.current_round > 0:
            # Multi-round mode: use cumulative context
            dependency_context = self._build_cumulative_context(subtask_id, self.current_round)
        else:
            # Legacy single-round mode: use dependency-based context
            dependency_context = self._build_dependency_context(dependencies)

        # If 2+ specialists assigned, run a sub-meeting
        if len(assigned) >= 2:
            self.logger.progress(f"Sub-meeting: {' & '.join(assigned)} collaborating...", indent=2)
            result = self._run_submeeting(subtask, dependency_context, assigned)
            self.logger.verbose(f"Sub-meeting returned {len(result) if result else 0} chars", indent=2)
        else:
            # Single specialist execution
            specialist_title = assigned[0]
            if specialist_title not in self.specialists:
                self.logger.warning(f"Specialist '{specialist_title}' not found, skipping", indent=2)
                return ""

            specialist = self.specialists[specialist_title]

            # Get OUTPUT_DIR for context
            run_dir = get_current_run_dir()
            output_dir_info = ""
            if run_dir:
                output_dir_info = f"""
**FILE LOCATIONS (CRITICAL):**
- All files from this run are in: `{run_dir}`
- When reading files from previous subtasks, use: `{run_dir}/filename.csv` in execute_python
- When mentioning files in your text responses, ALWAYS include the full path or {run_dir} prefix
- Example: Say "Results saved to {run_dir}/analysis.csv" NOT just "analysis.csv"
"""

            # Create overview context for this subtask
            overview_context = self._create_overview_context(subtask_id)

            # Construct subtask prompt with full context
            subtask_prompt = f"""{overview_context}

**SUBTASK {subtask_id}:** {description}

**Expected Outputs:** {', '.join(expected_outputs)}
{output_dir_info}
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

            self.logger.verbose(f"{specialist_title} completed subtask ({len(result) if result else 0} chars)", indent=2)
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
        
        # Debug log
        self.logger.verbose(f"Stored subtask {subtask_id} output: {len(result) if result else 0} chars", indent=2)

        # If in multi-round mode, also store in round_outputs
        if self.current_round > 0:
            if self.current_round not in self.round_outputs:
                self.round_outputs[self.current_round] = {}
            self.round_outputs[self.current_round][subtask_id] = result

        # Save subtask result to file
        self._save_subtask_result(subtask_id, result, self.current_round)

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

        # Get OUTPUT_DIR for context
        run_dir = get_current_run_dir()
        output_dir_info = ""
        if run_dir:
            output_dir_info = f"""
**FILE LOCATIONS (CRITICAL):**
- All files from this run are in: `{run_dir}`
- When reading files from previous subtasks, use: `{{OUTPUT_DIR}}/filename.csv` in execute_python
- When mentioning files in your text responses, ALWAYS include the full path or {{OUTPUT_DIR}} prefix
"""

        # Create overview context for this subtask
        overview_context = self._create_overview_context(subtask_id)

        initial_prompt = f"""{overview_context}

**COLLABORATIVE SUBTASK {subtask_id}:** {description}

**Expected Outputs:** {', '.join(expected_outputs)}
{output_dir_info}
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
        """Build context string from dependent subtasks (legacy - single round).

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

    def _build_cumulative_context(self, current_subtask_id: int, current_round: int) -> str:
        """Build cumulative context from all previous work.

        For multi-round workflow, each subtask sees:
        1. ALL outputs from all subtasks in previous rounds
        2. ALL completed subtasks in the current round (before this one)
        3. PI syntheses from previous rounds

        Args:
            current_subtask_id: The subtask currently being executed
            current_round: The current round number (1-indexed)

        Returns:
            Formatted context string with all previous work
        """
        context_parts = []

        # Part 1: Previous rounds' work (if any)
        if current_round > 1:
            context_parts.append("=" * 70)
            context_parts.append("PREVIOUS ROUNDS SUMMARY")
            context_parts.append("=" * 70)

            for round_num in range(1, current_round):
                context_parts.append(f"\n### ROUND {round_num} ###")

                # Include all subtask outputs from this previous round
                if round_num in self.round_outputs:
                    for subtask_id, output in sorted(self.round_outputs[round_num].items()):
                        subtask = next(
                            (st for st in self.research_plan if st['subtask_id'] == subtask_id),
                            None
                        )
                        if subtask:
                            desc = subtask['description']
                            assigned = ', '.join(subtask['assigned_specialists'])
                            context_parts.append(
                                f"\n**Subtask {subtask_id}: {desc}**\n"
                                f"(Team: {assigned})\n\n{output}"
                            )

                # Include PI synthesis from this round
                if round_num - 1 < len(self.round_syntheses):
                    synthesis = self.round_syntheses[round_num - 1]
                    context_parts.append(
                        f"\n**PI Synthesis (Round {round_num}):**\n{synthesis}"
                    )

                # Include critic review from this round
                if round_num - 1 < len(self.round_critiques):
                    critique = self.round_critiques[round_num - 1]
                    context_parts.append(
                        f"\n**Critic Review (Round {round_num}):**\n{critique}"
                    )

        # Part 2: Current round's completed subtasks (before this one)
        current_round_has_context = False
        if current_round in self.round_outputs:
            completed_in_round = [
                (sid, out) for sid, out in self.round_outputs[current_round].items()
                if sid < current_subtask_id
            ]
            if completed_in_round:
                current_round_has_context = True
                if current_round > 1:
                    context_parts.append("\n" + "=" * 70)
                context_parts.append(f"CURRENT ROUND {current_round} (Completed Subtasks)")
                context_parts.append("=" * 70)

                for subtask_id, output in sorted(completed_in_round):
                    subtask = next(
                        (st for st in self.research_plan if st['subtask_id'] == subtask_id),
                        None
                    )
                    if subtask:
                        desc = subtask['description']
                        assigned = ', '.join(subtask['assigned_specialists'])
                        context_parts.append(
                            f"\n**Subtask {subtask_id}: {desc}**\n"
                            f"(Team: {assigned})\n\n{output}"
                        )

        # If no context at all
        if not context_parts:
            if current_round == 1 and current_subtask_id == 1:
                return "This is the first subtask in the first round - no previous context available."
            else:
                return "No previous work available yet for this subtask."

        return "\n\n".join(context_parts)

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

    def _execute_single_round(self, round_num: int) -> tuple[str, List[Dict[str, str]]]:
        """Execute a single round of the research plan.

        Args:
            round_num: The current round number (1-indexed)

        Returns:
            Tuple of (round_synthesis, red_flags)
        """
        self.current_round = round_num

        # Clear subtask_outputs for this round (will be populated during execution)
        self.subtask_outputs = {}

        # Log round start
        if round_num == 1:
            self.logger.subsection(f"ROUND {round_num}: INITIAL RESEARCH EXECUTION")
        else:
            self.logger.subsection(f"ROUND {round_num}: REFINEMENT & ITERATION")
            self.logger.info(f"Teams will see ALL work from {round_num-1} previous round(s)", indent=2)

        # Execute all subtasks sequentially with cumulative context
        self.logger.info(f"Executing {len(self.research_plan)} subtasks in sequence...", indent=2)

        for subtask in self.research_plan:
            self._execute_subtask_sequential(subtask)

        self.logger.success(f"All {len(self.research_plan)} subtasks completed in Round {round_num}", indent=2)

        # Critic review for this round
        self.logger.subsection(f"ROUND {round_num}: CRITIC REVIEW")

        all_subtask_outputs = "\n\n".join([
            f"=== SUBTASK {st_id} ===\n{output}"
            for st_id, output in sorted(self.subtask_outputs.items())
        ])

        critique_prompt = f"""Review Round {round_num} subtask outputs and generate a Red Flag Checklist.

**Original Question:** {self.user_question}

**Round {round_num} Subtask Outputs:**
{all_subtask_outputs}

**Your Task:**
Generate a structured Red Flag Checklist identifying CRITICAL flaws that MUST be fixed.

Use this format for each flag:

[CRITICAL/MODERATE/MINOR - Category]
- Flag ID: R{round_num}-XX-N
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

        self.logger.agent_action("Scientific Critic", f"Reviewing Round {round_num} outputs", indent=2)

        critique = self.critic.run(critique_prompt, verbose=False)
        self.round_critiques.append(critique)

        self.meeting_transcript.append({
            "speaker": "Critic",
            "role": f"Round {round_num} Red Flag Checklist",
            "content": critique
        })

        # Extract red flags
        red_flags = self._extract_red_flags(critique)

        critical_count = sum(1 for f in red_flags if f['severity'] == 'CRITICAL')
        if critical_count > 0:
            self.logger.warning(f"Extracted {len(red_flags)} red flags ({critical_count} CRITICAL)", indent=2)
        else:
            self.logger.success(f"Extracted {len(red_flags)} red flags (no critical issues)", indent=2)

        if self.verbose:
            for flag in red_flags[:5]:  # Show first 5
                self.logger.verbose(f"  - [{flag['severity']}] {flag['flag_id']}: {flag['issue'][:60]}...", indent=2)

        # PI Round Synthesis
        self.logger.subsection(f"ROUND {round_num}: PI SYNTHESIS")

        round_summary_prompt = f"""Synthesize the findings from Round {round_num}.

**Original Question:** {self.user_question}

**Round {round_num} Work:**
{all_subtask_outputs}

**Critic's Red Flags:**
{critique}

**Your Task:**
Provide a brief synthesis (3-5 paragraphs) that:
1. Summarizes key findings from this round
2. Highlights any critical issues identified by the critic
3. Notes what has been accomplished
4. Identifies what still needs clarification (if anything)

Be concise but comprehensive."""

        self.logger.agent_action("PI", f"Synthesizing Round {round_num} findings", indent=2)

        round_synthesis = self.pi.run(round_summary_prompt, verbose=self.verbose)
        self.round_syntheses.append(round_synthesis)

        self.meeting_transcript.append({
            "speaker": "PI",
            "role": f"Round {round_num} Synthesis",
            "content": round_synthesis
        })

        if self.verbose:
            self.logger.result_summary(f"Round {round_num} PI Synthesis", round_synthesis, max_lines=8)

        # Save round summary to file
        self._save_round_summary(round_num, round_synthesis, critique)

        return round_synthesis, red_flags

    def run_meeting(self, num_rounds: int = 1) -> str:
        """Run the subtask-centric Virtual Lab meeting with multi-round support.

        Args:
            num_rounds: Number of full research plan iterations (default: 1)
                       Each round allows teams to refine their work based on
                       previous findings and PI/Critic feedback

        Returns:
            Final synthesized answer from PI with red flags addressed
        """
        self.logger.subsection("STARTING SUBTASK-CENTRIC VIRTUAL LAB")

        # Phase 1: PI opens with research plan overview (only once at start)
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

**Number of Rounds:** {num_rounds}

Provide a brief opening (2-3 sentences) that:
1. Frames the research question
2. Outlines the subtask-based approach
3. Explains that the team will iterate over {num_rounds} round(s) for thoroughness"""

        pi_intro = self.pi.run(pi_intro_prompt, verbose=self.verbose)
        self.meeting_transcript.append({
            "speaker": "PI",
            "role": "Opening - Research Plan",
            "content": pi_intro
        })

        # Phase 2: Multi-Round Execution
        self.logger.subsection(f"PHASE 2: MULTI-ROUND RESEARCH EXECUTION ({num_rounds} rounds)")

        all_round_red_flags = []

        for round_num in range(1, num_rounds + 1):
            round_synthesis, red_flags = self._execute_single_round(round_num)
            all_round_red_flags.extend(red_flags)

            # Between rounds: check if continuation makes sense
            if round_num < num_rounds:
                critical_count = sum(1 for f in red_flags if f['severity'] == 'CRITICAL')
                if critical_count == 0:
                    self.logger.info(f"Round {round_num} completed with no critical issues", indent=2)
                    self.logger.info(f"Proceeding to Round {round_num + 1} for refinement...", indent=2)
                else:
                    self.logger.warning(f"Round {round_num} has {critical_count} critical flags - teams will address in Round {round_num + 1}", indent=2)

        # Phase 3: Final Synthesis Across All Rounds
        self.logger.subsection("PHASE 3: FINAL SYNTHESIS ACROSS ALL ROUNDS")

        # Build comprehensive context from all rounds
        all_rounds_summary = []
        for round_num in range(1, num_rounds + 1):
            all_rounds_summary.append(f"\n### ROUND {round_num} ###")

            if round_num in self.round_outputs:
                for subtask_id, output in sorted(self.round_outputs[round_num].items()):
                    subtask = next((st for st in self.research_plan if st['subtask_id'] == subtask_id), None)
                    if subtask:
                        all_rounds_summary.append(
                            f"\n**Subtask {subtask_id}: {subtask['description']}**\n{output}"
                        )

            if round_num - 1 < len(self.round_syntheses):
                all_rounds_summary.append(f"\n**PI Synthesis:**\n{self.round_syntheses[round_num - 1]}")

            if round_num - 1 < len(self.round_critiques):
                all_rounds_summary.append(f"\n**Critic Review:**\n{self.round_critiques[round_num - 1]}")

        all_rounds_text = "\n\n".join(all_rounds_summary)

        # Consolidate red flags
        critical_flags = [f for f in all_round_red_flags if f['severity'] == 'CRITICAL']
        red_flag_section = ""
        if critical_flags:
            red_flag_section = "\n\n**REMAINING CRITICAL RED FLAGS TO ADDRESS:**\n"
            for flag in critical_flags:
                red_flag_section += f"\n- [{flag['flag_id']}] {flag['issue']}\n  Required Fix: {flag['required_fix']}\n"
            red_flag_section += "\n**YOU MUST** address these in your final synthesis."

        final_prompt = f"""Synthesize the team's findings across all {num_rounds} round(s) into a comprehensive final answer.

**Original Question:** "{self.user_question}"

**All Rounds Summary:**
{all_rounds_text}

{red_flag_section}

**Your Task:**
Provide a DETAILED, COMPREHENSIVE final answer. DO NOT summarize or condense the findings.

**CRITICAL INSTRUCTIONS:**
1. If the original question contains multiple sub-questions or parts (e.g., "What is X? How does Y work? What are the implications?"), you MUST address EACH sub-question separately and thoroughly.
2. For EACH sub-question or aspect of the question:
   - Provide a complete, detailed answer
   - Include all relevant data, findings, and evidence from the subtask outputs
   - Cite specific results, numbers, files, and analyses
   - Do NOT skip or condense information
3. Preserve the depth and detail from specialist analyses - do not over-summarize
4. Include all relevant context, methodologies, and reasoning

**Structure your answer with these sections:**

1. **Answer to Each Question Component**
   - If the question has multiple parts, create a subsection for EACH part
   - For each part, provide the full, detailed answer drawing from all relevant subtask outputs
   - Include all evidence, data, and citations for that specific question component
   - Be thorough and comprehensive - aim for completeness, not brevity

2. **Integrated Key Findings**
   - Synthesize insights that span multiple question components
   - Highlight connections and patterns across subtasks
   - Preserve specific details, numbers, and evidence

3. **Red Flag Resolution** (if critical flags exist)
   - For each flag: state what was done to resolve it across the rounds
   - If a fix requires additional analysis, acknowledge and propose next steps
   - If a flag is invalid, explain why

4. **Evidence & Citations**
   - List all PMIDs, databases, files, and tools used
   - Preserve all specific references from specialist work

5. **Limitations & Uncertainties**
   - Acknowledge gaps in data or analysis
   - Note areas requiring further investigation

6. **Recommended Next Steps** (if appropriate)
   - Suggest concrete follow-up analyses or experiments

**REMEMBER:**
- DO NOT over-summarize or condense specialist findings
- Each question component deserves a FULL, DETAILED answer
- Include ALL relevant evidence, data points, and citations
- Aim for thoroughness and completeness
- The goal is to provide a comprehensive response that fully addresses every aspect of the original question

Synthesize across all {num_rounds} rounds to provide the most complete and detailed answer possible."""

        self.logger.agent_action("PI", "Synthesizing final answer across all rounds", indent=2)

        final_answer = self.pi.run(final_prompt, verbose=self.verbose)

        self.meeting_transcript.append({
            "speaker": "PI",
            "role": "Final Synthesis",
            "content": final_answer
        })

        # Verify red flags were addressed
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
                final_answer += f"\n\n⚠️ **WARNING:** Not all critical red flags were fully addressed ({addressed_count}/{len(critical_flags)}). Further iteration may be needed."

        # Append references
        self.logger.progress("Appending references section...", indent=2)
        final_answer_with_refs = self._append_references_section(final_answer)

        self.logger.success(f"Virtual Lab meeting completed ({num_rounds} rounds)")

        # Save complete transcript to file
        self.logger.progress("Saving complete transcript...", indent=2)
        self.save_complete_transcript()

        return final_answer_with_refs


    def _format_team_list(self) -> str:
        """Format the team member list for prompts."""
        team_list = []
        for title, agent in self.specialists.items():
            team_list.append(f"- {title}: {agent.persona.expertise}")
        return "\n".join(team_list)

    def _save_subtask_result(self, subtask_id: int, result: str, round_num: int = 0):
        """Save individual subtask result to markdown file.
        
        Args:
            subtask_id: The subtask ID
            result: The output from the subtask
            round_num: Current round number (0 for single round)
        """
        if not self.save_intermediate:
            return
            
        run_dir = get_current_run_dir()
        if not run_dir:
            return
            
        # Find subtask details
        subtask = next(
            (st for st in self.research_plan if st['subtask_id'] == subtask_id),
            None
        )
        if not subtask:
            return
            
        # Create filename
        if round_num > 0:
            filename = f"subtask_{subtask_id}_round_{round_num}.md"
        else:
            filename = f"subtask_{subtask_id}.md"
            
        filepath = run_dir / filename
        
        # Format content
        content = f"""# Subtask {subtask_id} Results

**Description:** {subtask['description']}

**Assigned Specialists:** {', '.join(subtask['assigned_specialists'])}

**Expected Outputs:** {', '.join(subtask['expected_outputs'])}

{'**Round:** ' + str(round_num) if round_num > 0 else ''}

---

## Output

{result}

---

*Generated by CoScientist Subtask-Centric Virtual Lab*
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        self.logger.verbose(f"Saved subtask result to: {filepath.name}", indent=2)

    def _save_round_summary(self, round_num: int, synthesis: str, critique: str):
        """Save round summary with synthesis and critique.
        
        Args:
            round_num: Current round number
            synthesis: PI's synthesis for this round
            critique: Critic's review for this round
        """
        if not self.save_intermediate:
            return
            
        run_dir = get_current_run_dir()
        if not run_dir:
            return
            
        filename = f"round_{round_num}_summary.md"
        filepath = run_dir / filename
        
        # Format content
        content = f"""# Round {round_num} Summary

**Question:** {self.user_question}

**Team Size:** {len(self.specialists)} specialists

**Subtasks Completed:** {len(self.research_plan)}

---

## PI Synthesis

{synthesis}

---

## Critic Review (Red Flag Checklist)

{critique}

---

*Generated by CoScientist Subtask-Centric Virtual Lab*
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        self.logger.verbose(f"Saved round summary to: {filepath.name}", indent=2)

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

    def save_complete_transcript(self):
        """Save the complete meeting transcript to a markdown file."""
        if not self.save_intermediate:
            return
            
        run_dir = get_current_run_dir()
        if not run_dir:
            return
            
        filename = "complete_transcript.md"
        filepath = run_dir / filename
        
        # Build comprehensive transcript
        content_parts = []
        content_parts.append("# Complete Virtual Lab Transcript\n")
        content_parts.append(f"**Research Question:** {self.user_question}\n")
        content_parts.append(f"**Team Size:** {len(self.specialists)} specialists\n")
        content_parts.append(f"**Rounds:** {len(self.round_syntheses) if self.round_syntheses else 1}\n")
        content_parts.append("\n---\n\n")
        
        # Research Plan
        content_parts.append("## Research Plan\n\n")
        for subtask in self.research_plan:
            content_parts.append(f"**Subtask {subtask['subtask_id']}:** {subtask['description']}\n")
            content_parts.append(f"- Assigned: {', '.join(subtask['assigned_specialists'])}\n")
            content_parts.append(f"- Expected: {', '.join(subtask['expected_outputs'])}\n\n")
        
        content_parts.append("\n---\n\n")
        
        # Full transcript
        content_parts.append("## Complete Transcript\n\n")
        content_parts.append(self._build_full_transcript())
        
        content_parts.append("\n---\n\n")
        content_parts.append("*Generated by CoScientist Subtask-Centric Virtual Lab*\n")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(''.join(content_parts))
            
        self.logger.success(f"Complete transcript saved to: {filepath.name}")

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

    def _create_overview_context(self, current_subtask_id: int) -> str:
        """Create overview context explaining the research question, goals, and subtask position.
        
        Args:
            current_subtask_id: The current subtask being executed
            
        Returns:
            Formatted overview context string
        """
        # Create subtasks overview
        all_subtasks = []
        for subtask in self.research_plan:
            status = "CURRENT" if subtask['subtask_id'] == current_subtask_id else ""
            if subtask['subtask_id'] < current_subtask_id:
                status = "COMPLETED"
            elif subtask['subtask_id'] > current_subtask_id:
                status = "PENDING"
                
            all_subtasks.append(
                f"  {subtask['subtask_id']}. {subtask['description']} "
                f"(Team: {', '.join(subtask['assigned_specialists'])}) [{status}]"
            )
        
        joined_subtasks = "\n".join(all_subtasks)
        overview = f"""**RESEARCH OVERVIEW:**
- Original Question: "{self.user_question}"
- Final Goal: Provide a comprehensive, evidence-based answer to the research question
- Research Strategy: Sequential subtask execution with specialist collaboration

**ALL SUBTASKS IN THIS RESEARCH PLAN:**
{joined_subtasks}

**YOUR CURRENT POSITION:**
You are executing Subtask {current_subtask_id}, which is part of a larger research effort.
Each subtask builds on previous work to collectively answer the original question."""

        return overview

    # ...existing code...


def run_virtual_lab(
    question: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    num_rounds: int = 1,  # Changed default to 1 for sequential workflow
    max_team_size: int = 3,
    verbose: bool = False,
    data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data",
    input_dir: Optional[str] = None,
    max_iterations: int = 30,
    save_intermediate: bool = False
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
        max_iterations: Maximum iterations per agent (default: 30)
        save_intermediate: Save intermediate subtask and round results (default: False)

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
        input_dir=input_dir,
        max_iterations=max_iterations,
        save_intermediate=save_intermediate
    )

    final_answer = meeting.run_meeting(num_rounds=num_rounds)
    return final_answer
