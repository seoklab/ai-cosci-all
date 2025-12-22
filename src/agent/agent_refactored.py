"""Core agent with data-driven reasoning prompts for subtask-centric collaboration."""

import json
import os
import asyncio
from typing import Any, Optional
from dataclasses import dataclass
from src.agent.openrouter_client import OpenRouterClient
from src.agent.anthropic_client import AnthropicClient
from src.tools.implementations import (
    execute_python,
    search_pubmed,
    search_literature,
    query_database,
    read_file,
    find_files,
    get_tool_definitions,
)


def get_max_tokens_for_model(model_name: str) -> int:
    """Determine appropriate max_tokens based on model name."""
    if ":free" in model_name.lower():
        return 500
    return 4096


@dataclass
class AgentPersona:
    """Represents a scientific agent's persona for role-playing in Virtual Lab."""
    title: str
    expertise: str
    goal: str
    role: str


class BioinformaticsAgent:
    """Agent for answering complex bioinformatics questions."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514", provider: str = "anthropic", data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data", input_dir: Optional[str] = None, max_iterations: int = 30):
        if provider == "anthropic":
            self.client = AnthropicClient(api_key=api_key, model=model)
        else:
            self.client = OpenRouterClient(api_key=api_key, model=model)
        self.data_dir = data_dir
        self.input_dir = input_dir if input_dir is not None else data_dir
        self.tools = {
            "execute_python": execute_python,
            "search_pubmed": search_pubmed,
            "search_literature": search_literature,
            "query_database": query_database,
            "read_file": read_file,
            "find_files": find_files,
        }
        self.conversation_history = []
        self.max_iterations = max_iterations

    def get_system_prompt(self) -> str:
        """Get the system prompt for scientific reasoning."""
        return """You are CoScientist, an expert AI research assistant for biomedical research. Your role is to help scientists answer complex, multi-step research questions through rigorous analysis, data exploration, and literature review.

## Core Capabilities
- Analyze complex biological datasets and databases
- Search peer-reviewed literature to ground answers in evidence
- Execute Python code for data analysis and visualization
- Reason through multi-step research problems systematically
- Propose novel experimental strategies and validate their feasibility

## Response Guidelines

1. **Scientific Rigor**: Always distinguish between established facts, well-supported hypotheses, and speculative ideas. Use phrases like "evidence suggests", "it is plausible that", "needs validation", etc.

2. **Multi-step Problem Solving**: For complex questions:
   - Break the problem into logical steps
   - Explain your reasoning for each step
   - Use tools strategically to gather data
   - Synthesize findings into coherent conclusions

3. **Data Exploration**: When analyzing data:
   - ALWAYS use find_files() FIRST to discover available data files
   - When reading INPUT files: the input directory is pre-configured, so use ONLY the filename (e.g., 'file.csv', NOT 'data/Q5/file.csv')
   - When SAVING OUTPUT files (CSV, plots, etc.): ALWAYS prefix paths with OUTPUT_DIR (e.g., f'{{OUTPUT_DIR}}/results.csv')
     - OUTPUT_DIR is automatically available in execute_python code
     - This organizes all outputs into a run-specific directory
     - To read files you saved earlier: use f'{{OUTPUT_DIR}}/filename.csv'
   - **CRITICAL FOR COLLABORATION**: When mentioning files in your TEXT responses to other agents:
     - ALWAYS include the {{OUTPUT_DIR}} prefix or full path
     - Say "Results saved to {{OUTPUT_DIR}}/analysis.csv" NOT just "analysis.csv"
     - Say "See {{OUTPUT_DIR}}/plot.png for visualization" NOT just "plot.png"
     - This ensures other agents can find your files
   - Query relevant databases to get context
   - Examine distributions, patterns, and outliers
   - Document assumptions clearly
   - Consider alternative explanations

4. **Literature Integration** (CRITICAL):
   - **STRATEGIC SEARCH APPROACH**:
     * Limit to 1-2 BROAD literature searches per subtask - make each one count
     * Use GENERAL, comprehensive queries for background domain knowledge
     * GOOD: "What are epigenetic mechanisms in T cell exhaustion?"
     * BAD: "Does Hist1h2ao methylation affect CD8+ T cell PD-1 expression?"
     * If search doesn't find papers, your query is likely TOO SPECIFIC - broaden it
     * Extract ALL relevant information from search results before considering another search
     * It's up to YOU to decide if papers are useful - the tool provides background knowledge
   - **VERIFY BEFORE CITING**: If you reference a paper (e.g., "Philip et al., Nature 2017"), you MUST use `search_literature` to fetch and read it BEFORE making claims about its content
   - **Don't guess**: Never say "likely X paper says Y" - actually fetch and read the paper to confirm
   - Use `search_literature(mode='online')` to fetch papers from PubMed/arXiv if not in local library
   - Use `search_pubmed` ONLY for quick abstract-level searches when full-text isn't needed
   - ALWAYS cite papers in this format: "Title" (PMID: 12345678)
   - Include the full paper title and PMID for every claim backed by literature
   - Example: "According to 'Chromatin states define tumour-specific T cell dysfunction and reprogramming' (PMID: 28193889), ..."
   - Note consensus vs. contrasting findings
   - Acknowledge knowledge gaps where relevant

5. **Practical Feasibility**:
   - When proposing strategies, consider experimental resources needed
   - Discuss timeline expectations
   - Identify potential technical challenges
   - Suggest validation approaches

## Communication Style
- Be precise and avoid vague statements
- Use appropriate scientific terminology
- Structure complex answers with clear sections
- Highlight key findings and limitations
- Propose next steps when appropriate

Remember: Your goal is to help scientists make informed decisions, not to provide definitive answers. Surface uncertainty honestly and help them understand where more research is needed."""

    def add_message(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation_history.append({"role": role, "content": content})

    def call_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return the result."""
        if tool_name not in self.tools:
            return {
                "success": False,
                "output": None,
                "error": f"Unknown tool: {tool_name}",
            }

        try:
            tool_func = self.tools[tool_name]
            if tool_name == "query_database":
                tool_input["data_dir"] = self.data_dir
            elif tool_name == "read_file":
                tool_input["input_dir"] = self.input_dir
            elif tool_name == "find_files":
                tool_input["data_dir"] = self.data_dir
            result = tool_func(**tool_input)
            return result.to_dict()
        except TypeError as e:
            return {
                "success": False,
                "output": None,
                "error": f"Invalid arguments for {tool_name}: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "error": f"Tool execution error: {str(e)}",
            }

    def process_response(self, response: dict[str, Any]) -> tuple[Optional[str], list[dict[str, Any]]]:
        """Process API response and extract text and tool calls."""
        text = self.client.get_response_text(response)
        tool_calls = self.client.extract_tool_calls(response)
        return text, tool_calls

    def run(self, user_question: str, verbose: bool = False) -> str:
        """Run the agent loop for a user question."""
        self.conversation_history = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        self.add_message("user", user_question)

        if verbose:
            print(f"\n{'='*60}")
            print(f"Question: {user_question}")
            print(f"{'='*60}\n")

        for iteration in range(self.max_iterations):
            if verbose:
                print(f"[Iteration {iteration + 1}/{self.max_iterations}]")

            call_params = {
                "messages": self.conversation_history,
                "tools": get_tool_definitions(),
                "temperature": 0.7,
                "max_tokens": get_max_tokens_for_model(self.client.model),
            }

            if isinstance(self.client, AnthropicClient):
                call_params["system"] = self.get_system_prompt()

            response = self.client.create_message(**call_params)
            text, tool_calls = self.process_response(response)

            finish_reason = None
            if response.get("choices") and len(response["choices"]) > 0:
                finish_reason = response["choices"][0].get("finish_reason")

            if text:
                if verbose:
                    print(f"Assistant: {text[:200]}..." if len(text) > 200 else f"Assistant: {text}")
                    if finish_reason:
                        print(f"[Finish reason: {finish_reason}]")

            if not tool_calls:
                if finish_reason == "length":
                    if verbose:
                        print("\n[WARNING: Response was truncated due to max_tokens limit]")
                        print("[Agent completed - no more tools needed]")
                elif verbose:
                    print("\n[Agent completed - no more tools needed]")
                if text:
                    self.add_message("assistant", text)
                return text

            if verbose:
                print(f"[Tools to call: {[tc['name'] for tc in tool_calls]}]")

            if response.get("choices") and response["choices"][0].get("message"):
                assistant_message = response["choices"][0]["message"]
                self.conversation_history.append(assistant_message)

            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_input = tool_call["input"]
                tool_call_id = tool_call.get("id", "")

                if verbose:
                    print(f"  Calling {tool_name}({json.dumps(tool_input)})...")

                result = self.call_tool(tool_name, tool_input)

                if verbose:
                    if result["success"]:
                        result_preview = str(result["output"])[:200]
                        print(f"    → Success: {result_preview}...")
                    else:
                        print(f"    → Error: {result['error']}")

                result_str = json.dumps(result)
                if len(result_str) > 5000:
                    result_truncated = {
                        "success": result.get("success"),
                        "output": str(result.get("output"))[:4500] + "...[truncated]",
                        "error": result.get("error")
                    }
                    result_str = json.dumps(result_truncated)

                tool_result = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": result_str
                }
                tool_results.append(tool_result)

            self.conversation_history.extend(tool_results)

        if verbose:
            print("\n[Max iterations reached]")

        for msg in reversed(self.conversation_history):
            if msg["role"] == "assistant":
                return msg["content"]

        return ""

    async def run_async(self, user_question: str, verbose: bool = False) -> str:
        """Async version of run() for parallel specialist execution."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, user_question, verbose)

    def get_critic_prompt_with_red_flags(self) -> str:
        """Get the system prompt for the scientific critic with Red Flag system.

        Returns:
            Critic system prompt string with Red Flag checklist requirement
        """
        return """You are a Scientific Critic specializing in biomedical research evaluation with a focus on CRITICAL FLAW DETECTION.

## Your Mission
Generate a "Red Flag Checklist" - a structured list of specific, actionable flaws that MUST be addressed before the research can be considered complete.

## Red Flag Categories

1. **Data Analysis Flaws**:
   - Incorrect statistical methods
   - Missing validation steps
   - Computational errors
   - Inappropriate data transformations
   - Failure to check assumptions

2. **Missing Critical Steps**:
   - Required analyses not performed
   - Essential controls missing
   - Key data files not examined
   - Important databases not queried

3. **Unsupported Claims**:
   - Statements without evidence
   - Citations without actual paper verification
   - Speculation presented as fact
   - Over-interpretation of results

4. **Logical Errors**:
   - Contradictory statements
   - Flawed reasoning chains
   - Circular arguments
   - Incorrect causal inferences

5. **Literature Gaps**:
   - Missing relevant papers
   - Failure to cite contradictory evidence
   - Outdated references
   - Misrepresentation of cited work

## Output Format

You MUST output a structured Red Flag Checklist:

**RED FLAG CHECKLIST:**

[CRITICAL - Data Analysis]
- Flag ID: DA-1
- Issue: [Specific flaw]
- Location: [Where in the analysis]
- Required Fix: [What must be done]

[CRITICAL - Missing Step]
- Flag ID: MS-1
- Issue: [What's missing]
- Impact: [Why this matters]
- Required Fix: [Specific action needed]

[MODERATE - Unsupported Claim]
- Flag ID: UC-1
- Claim: [Exact statement]
- Problem: [Why unsupported]
- Required Fix: [Evidence needed]

## Severity Levels
- CRITICAL: Must fix before proceeding (blocks completion)
- MODERATE: Should fix for rigor (affects quality)
- MINOR: Nice to improve (polish)

## Important Rules
1. Be SPECIFIC - cite exact statements, line numbers, or analysis steps
2. Be ACTIONABLE - each flag must have a clear "Required Fix"
3. NO solutions - only identify problems
4. Prioritize CRITICAL flags (max 3-5)
5. If analysis is sound, you may have zero CRITICAL flags

Your checklist will be used to enforce quality - the PI MUST address every CRITICAL flag."""

    def run_with_critic(self, user_question: str, verbose: bool = False, max_refinement_rounds: int = 1) -> tuple[str, str, str]:
        """Run the agent with critic feedback loop (legacy - kept for compatibility)."""
        if verbose:
            print(f"\n{'='*60}")
            print(f"RUNNING WITH CRITIC FEEDBACK")
            print(f"{'='*60}\n")

        if verbose:
            print("[STEP 1: Main Agent Analysis]")
        initial_answer = self.run(user_question, verbose=verbose)

        if not initial_answer:
            return "", "No answer produced by agent", ""

        if verbose:
            print(f"\n{'='*60}")
            print("[STEP 2: Scientific Critic Review]")
            print(f"{'='*60}\n")

        critic_agent = BioinformaticsAgent(
            api_key=None,
            model=self.client.model if hasattr(self.client, 'model') else "claude-sonnet-4-20250514",
            provider="anthropic" if isinstance(self.client, AnthropicClient) else "openrouter"
        )

        critic_question = f"""Please review the following scientific answer for rigor, completeness, and accuracy.

ORIGINAL QUESTION:
{user_question}

ANSWER TO REVIEW:
{initial_answer}

Provide a structured critique with:
1. Strengths (what is done well)
2. Issues (errors, gaps, or weaknesses - be specific)
3. Improvements (specific suggestions to enhance the answer)

If the answer is high quality and scientifically sound, you may approve it."""

        original_get_system_prompt = critic_agent.get_system_prompt
        critic_agent.get_system_prompt = self.get_critic_prompt_with_red_flags

        critique = ""
        critic_messages = [{"role": "user", "content": critic_question}]

        call_params = {
            "messages": critic_messages,
            "tools": [],
            "temperature": 0.3,
            "max_tokens": get_max_tokens_for_model(self.client.model),
        }

        if isinstance(self.client, AnthropicClient):
            call_params["system"] = self.get_critic_prompt_with_red_flags()

        response = self.client.create_message(**call_params)
        critique = self.client.get_response_text(response)

        if verbose:
            print(f"Critic Feedback:\n{critique}\n")

        critic_agent.get_system_prompt = original_get_system_prompt

        needs_refinement = any(keyword in critique.lower() for keyword in [
            "error", "incorrect", "missing", "should", "needs", "improve",
            "gap", "weakness", "concern", "problem", "critical", "red flag"
        ])

        if not needs_refinement or max_refinement_rounds == 0:
            if verbose:
                print("[STEP 3: No refinement needed - answer approved]\n")
            return initial_answer, critique, initial_answer

        if verbose:
            print(f"\n{'='*60}")
            print("[STEP 3: Refining Answer Based on Feedback]")
            print(f"{'='*60}\n")

        refinement_question = f"""Based on the scientific critique below, please revise and improve your previous answer.

ORIGINAL QUESTION:
{user_question}

YOUR PREVIOUS ANSWER:
{initial_answer}

CRITIC FEEDBACK:
{critique}

Please provide an improved answer that addresses the critique's suggestions. Focus on fixing errors, filling gaps, and adding missing analyses."""

        final_answer = self.run(refinement_question, verbose=verbose)

        if verbose:
            print(f"\n{'='*60}")
            print("[COMPLETE: Answer refined based on critic feedback]")
            print(f"{'='*60}\n")

        return initial_answer, critique, final_answer


def create_agent(api_key: Optional[str] = None, model: Optional[str] = None, provider: Optional[str] = None, data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data", input_dir: Optional[str] = None) -> BioinformaticsAgent:
    """Factory function to create an agent."""
    if provider is None:
        provider = os.getenv("API_PROVIDER", "anthropic")

    if model is None:
        if provider == "anthropic":
            model = "claude-sonnet-4-20250514"
        else:
            model = "anthropic/claude-sonnet-4"

    return BioinformaticsAgent(api_key=api_key, model=model, provider=provider, data_dir=data_dir, input_dir=input_dir)


class ScientificAgent(BioinformaticsAgent):
    """A persona-based agent with data-driven reasoning for subtask collaboration."""

    def __init__(
        self,
        persona: AgentPersona,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
        data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data",
        input_dir: Optional[str] = None,
        max_iterations: int = 30
    ):
        super().__init__(api_key, model, provider, data_dir, input_dir, max_iterations)
        self.persona = persona

    def get_system_prompt(self) -> str:
        """Get data-driven system prompt for subtask-centric collaboration."""
        return f"""You are {self.persona.title}.

**Expertise:** {self.persona.expertise}
**Goal:** {self.persona.goal}
**Role:** {self.persona.role}

You are participating in a SUBTASK-CENTRIC Virtual Lab where specialists work SEQUENTIALLY on specific subtasks.

## CRITICAL: Data-Driven Reasoning

**MANDATORY RULE:**
If a previous specialist generated files, executed code, or produced analysis results, you MUST:
1. EXPLICITLY reference their output (e.g., "Based on the DEG analysis from Computational Biologist...")
2. READ and ANALYZE the actual data they generated (use read_file, execute_python to examine their outputs)
3. BUILD upon their findings - do not repeat their work
4. VALIDATE their results if appropriate for your expertise

**Example Good Behavior:**
Previous specialist: "I created differential_expression.csv with 500 DEGs"
You:
- read_file("differential_expression.csv") to examine the data
- "Based on the DEG list, I analyzed the top 50 genes and found..."

**Example Bad Behavior:**
Previous specialist: "I created differential_expression.csv"
You: "I think we should do differential expression analysis..." ← WRONG! Data already exists!

## Your Responsibilities in Sequential Workflow

1. **Context Awareness**: Read the subtask description and review outputs from previous subtasks
2. **Tool Usage**: Use tools to VERIFY and BUILD UPON previous findings
3. **Explicit References**: Cite what previous specialists found (with file names, statistics, etc.)
4. **Contribute Uniquely**: Apply YOUR expertise - don't duplicate previous analyses
5. **Generate Outputs**: Create files, figures, or results for downstream specialists
6. **Be Concise**: Focus on YOUR subtask - don't try to solve everything

## Communication Style
- Start by acknowledging previous work if applicable
- Be specific about what you're analyzing
- Reference exact files, numbers, and results
- Generate concrete outputs (files, figures, statistics)
- Signal what downstream specialists should examine

## Tools Available
- find_files(): Discover data
- read_file(): Read previous outputs
- execute_python(): Analyze data, create plots
- query_database(): Get context from databases
- search_literature(): Find relevant papers (STRATEGIC USE: 1-2 BROAD searches per subtask, use GENERAL queries like "What are epigenetic mechanisms in T cell exhaustion?" NOT hyper-specific like "Does Hist1h2ao methylation affect PD-1?")
- search_pubmed(): Quick literature searches

## Literature Search Strategy (CRITICAL)
- **Limit searches**: 1-2 BROAD queries per subtask maximum
- **Use GENERAL questions**: Get background domain knowledge, not ultra-specific answers
- **Extract everything**: Read ALL relevant information from results before searching again
- **You decide usefulness**: The tool provides background - it's up to you to apply it
- **If no papers found**: Your query is TOO SPECIFIC - broaden it

Remember: You are ONE specialist in a SEQUENTIAL workflow. Build on what came before, execute YOUR subtask, and prepare outputs for what comes next."""
