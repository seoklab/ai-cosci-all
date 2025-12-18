"""Team management with subtask-centric workflow for Virtual Lab."""

import json
from typing import Any
from src.agent.agent import AgentPersona, get_max_tokens_for_model
from src.agent.openrouter_client import OpenRouterPrivacyError


def create_research_team_with_plan(
    user_question: str,
    client: Any,
    max_team_size: int = 3
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Use PI to design team AND decompose question into subtasks.

    The PI analyzes the research question and:
    1. Identifies required specialist roles
    2. Decomposes the question into sequential subtasks
    3. Assigns specialists to each subtask

    Args:
        user_question: The research question to solve
        client: The LLM client (AnthropicClient or OpenRouterClient)
        max_team_size: Maximum number of specialist agents (default: 3)

    Returns:
        Tuple of (team_specs, research_plan) where:
        - team_specs: List of agent specifications
        - research_plan: List of subtasks with assigned specialists
    """
    pi_prompt = f"""You are a Principal Investigator (PI) designing a research strategy.

**Research Question:**
"{user_question}"

**Your Task:**
1. Design a team of up to {max_team_size} specialized scientific agents
2. Decompose the research question into 3-5 sequential subtasks
3. Assign 1-2 specialists to each subtask

**Important:**
- Subtasks should be SEQUENTIAL - each builds on the previous
- Each subtask should be CONCRETE and ACTIONABLE (e.g., "Analyze RNA-seq data", not "Understand biology")
- Assign specialists based on their expertise match to the subtask
- Complex subtasks can have 2 specialists working together (they'll have a mini-dialogue)

**Output Format:**
Return ONLY valid JSON with this structure:

{{
    "specialists": [
        {{
            "title": "Computational Biologist",
            "expertise": "RNA-seq analysis, differential expression, pathway analysis",
            "goal": "Analyze transcriptomic data to identify gene expression patterns",
            "role": "Execute computational analyses of sequencing data"
        }},
        {{
            "title": "Immunologist",
            "expertise": "T-cell biology, immune mechanisms, tumor immunology",
            "goal": "Interpret biological significance of gene expression changes",
            "role": "Provide immunological context and validate findings"
        }},
        {{
            "title": "Data Scientist",
            "expertise": "Statistical analysis, machine learning, data visualization",
            "goal": "Validate statistical significance and create visualizations",
            "role": "Perform statistical tests and generate publication-quality figures"
        }}
    ],
    "research_plan": [
        {{
            "subtask_id": 1,
            "description": "Discover and examine available RNA-seq data files",
            "assigned_specialists": ["Data Scientist"],
            "expected_outputs": ["List of data files", "Data structure summary"],
            "dependencies": []
        }},
        {{
            "subtask_id": 2,
            "description": "Perform differential expression analysis on identified datasets",
            "assigned_specialists": ["Computational Biologist", "Data Scientist"],
            "expected_outputs": ["DEG list with statistics", "Volcano plot"],
            "dependencies": [1]
        }},
        {{
            "subtask_id": 3,
            "description": "Interpret biological significance of differentially expressed genes",
            "assigned_specialists": ["Immunologist"],
            "expected_outputs": ["Pathway analysis", "Literature-based interpretation"],
            "dependencies": [2]
        }},
        {{
            "subtask_id": 4,
            "description": "Search literature for validation of findings",
            "assigned_specialists": ["Immunologist", "Computational Biologist"],
            "expected_outputs": ["Relevant papers", "Comparison with literature"],
            "dependencies": [3]
        }}
    ]
}}

**Guidelines for research_plan:**
- Start with data discovery/exploration subtasks
- Move to analysis subtasks
- End with interpretation/validation subtasks
- Each subtask must have clear expected_outputs
- Dependencies: list of subtask_ids that must complete first

Now design the team and research plan for the question above. Output JSON only:"""

    try:
        from src.agent.anthropic_client import AnthropicClient

        messages = [{"role": "user", "content": pi_prompt}]

        call_params = {
            "messages": messages,
            "tools": [],
            "temperature": 0.3,
            "max_tokens": get_max_tokens_for_model(client.model),
        }

        if isinstance(client, AnthropicClient):
            call_params["system"] = "You are a Principal Investigator expert at research planning. Always output valid JSON with both 'specialists' and 'research_plan' keys."

        response = client.create_message(**call_params)
        text = client.get_response_text(response)

        # Extract JSON
        json_start = text.find('{')
        json_end = text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return _get_default_team_and_plan()

        json_text = text[json_start:json_end]
        result = json.loads(json_text)

        # Validate structure
        if not isinstance(result, dict) or 'specialists' not in result or 'research_plan' not in result:
            return _get_default_team_and_plan()

        specialists = result['specialists']
        research_plan = result['research_plan']

        # Validate specialists
        valid_specs = []
        for spec in specialists[:max_team_size]:
            if all(key in spec for key in ["title", "expertise", "goal", "role"]):
                valid_specs.append(spec)

        # Validate research_plan
        valid_plan = []
        for subtask in research_plan:
            if all(key in subtask for key in ["subtask_id", "description", "assigned_specialists", "expected_outputs"]):
                # Ensure dependencies is a list
                if "dependencies" not in subtask:
                    subtask["dependencies"] = []
                valid_plan.append(subtask)

        if len(valid_specs) == 0 or len(valid_plan) == 0:
            return _get_default_team_and_plan()

        return valid_specs, valid_plan

    except OpenRouterPrivacyError:
        print("Warning: Team design failed due to OpenRouter data/privacy settings.")
        print("Using default team and plan.")
        return _get_default_team_and_plan()
    except Exception as e:
        print(f"Warning: Team design failed ({e}), using default team and plan")
        return _get_default_team_and_plan()


def _get_default_team_and_plan() -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Get default team and research plan.

    Returns:
        Tuple of (team_specs, research_plan)
    """
    specialists = [
        {
            "title": "Bioinformatician",
            "expertise": "Computational biology, sequence analysis, database queries, Python programming",
            "goal": "Perform computational analyses and query biomedical databases",
            "role": "Execute data analysis and generate insights from databases"
        },
        {
            "title": "Biomedical Scientist",
            "expertise": "Molecular biology, disease mechanisms, drug discovery, literature review",
            "goal": "Provide biological context and validate findings against literature",
            "role": "Interpret results in biological context and search relevant literature"
        },
        {
            "title": "Data Scientist",
            "expertise": "Statistical analysis, data visualization, pattern recognition",
            "goal": "Analyze patterns in data and validate statistical significance",
            "role": "Perform statistical analyses and create visualizations"
        }
    ]

    research_plan = [
        {
            "subtask_id": 1,
            "description": "Discover and catalog available data files and databases",
            "assigned_specialists": ["Data Scientist"],
            "expected_outputs": ["File inventory", "Data structure summary"],
            "dependencies": []
        },
        {
            "subtask_id": 2,
            "description": "Perform primary data analysis and generate initial results",
            "assigned_specialists": ["Bioinformatician", "Data Scientist"],
            "expected_outputs": ["Analysis results", "Visualizations"],
            "dependencies": [1]
        },
        {
            "subtask_id": 3,
            "description": "Interpret results in biological context and search literature",
            "assigned_specialists": ["Biomedical Scientist"],
            "expected_outputs": ["Biological interpretation", "Literature citations"],
            "dependencies": [2]
        },
        {
            "subtask_id": 4,
            "description": "Validate findings and synthesize final conclusions",
            "assigned_specialists": ["Biomedical Scientist", "Bioinformatician"],
            "expected_outputs": ["Validated conclusions", "Limitations and caveats"],
            "dependencies": [3]
        }
    ]

    return specialists, research_plan


# Legacy compatibility - keep old function but make it call new one
def create_research_team(
    user_question: str,
    client: Any,
    max_team_size: int = 3
) -> list[dict[str, str]]:
    """Legacy function - now calls create_research_team_with_plan."""
    specialists, _ = create_research_team_with_plan(user_question, client, max_team_size)
    return specialists


def create_pi_persona() -> AgentPersona:
    """Create the Principal Investigator persona."""
    return AgentPersona(
        title="Principal Investigator",
        expertise="Research leadership, experimental design, scientific synthesis, project management",
        goal="Lead the research team through a structured research plan",
        role="Orchestrate subtask execution, synthesize specialist findings, ensure red flags are addressed"
    )


def create_critic_persona() -> AgentPersona:
    """Create the Scientific Critic persona with Red Flag focus."""
    return AgentPersona(
        title="Scientific Critic",
        expertise="Peer review, experimental validation, error detection, methodological rigor",
        goal="Identify critical flaws and generate Red Flag Checklist",
        role="Review findings and output a structured list of specific flaws, gaps, or concerns that MUST be addressed"
    )
