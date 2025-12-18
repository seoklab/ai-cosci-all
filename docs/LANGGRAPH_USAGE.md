# LangGraph Integration - User Guide

## Overview

The LangGraph integration adds advanced workflow orchestration to Virtual Lab:

1. **Intelligent Routing**: Automatically selects specialist teams based on question type
2. **Workflow Visualization**: Generate diagrams showing execution flow
3. **Human-in-the-Loop**: Optional checkpoint for human approval/revision
4. **State Persistence**: Maintains execution state across checkpoints

## Quick Start

### Basic Usage

```python
from src.langgraph import run_research_workflow

# Simple execution
result = run_research_workflow(
    question="What is T cell exhaustion?",
    enable_human_review=False,
    verbose=True
)

print(result["final_answer"])
```

### With Human Review

```python
from src.langgraph import run_research_workflow, continue_after_human_review

# Start workflow (pauses at human review)
result = run_research_workflow(
    question="How do I design a CRISPR screen?",
    enable_human_review=True,
    thread_id="review_001",
    verbose=True
)

# Human reviews the answer...

# Continue after approval
final = continue_after_human_review(
    thread_id="review_001",
    approval_status="approved",  # or "revise" or "rejected"
    human_feedback="Excellent experimental design!"
)
```

## Architecture

### Workflow Graph

```
START
  ↓
[classifier]
  ↓
  ├─ wet_lab → [virtual_lab_wetlab]
  ├─ computational → [virtual_lab_computational]
  ├─ literature → [virtual_lab_literature]
  └─ general → [virtual_lab_general]
      ↓
  [human_review] (optional)
      ↓
  ├─ approved → END
  ├─ rejected → END
  └─ revise → [classifier]
```

### Question Type Routing

| Question Type | Specialist Team | Use Cases |
|--------------|----------------|-----------|
| **wet_lab** | Experimental Design, Molecular Biology, Cell Biology, Model Organism | CRISPR experiments, cell culture, animal models |
| **computational** | Bioinformatics, Biostatistics, Machine Learning, Data Science | RNA-seq analysis, pathway analysis, drug discovery |
| **literature** | Literature Review, Mechanism Expert, Clinical Translation | Systematic reviews, mechanism synthesis |
| **general** | Generalist Researchers, Methodology Experts, Integration | Broad questions spanning multiple domains |

### Complexity-Based Scaling

The classifier also determines complexity:

| Complexity | Team Size | Rounds | Examples |
|-----------|-----------|--------|----------|
| **simple** | 2 specialists | 1 round | "What is apoptosis?" |
| **moderate** | 3 specialists | 2 rounds | "Compare CRISPR vs TALENs" |
| **complex** | 4 specialists | 3 rounds | "Design multi-omics experiment" |

## Features

### 1. Intelligent Classification

The `classifier` node analyzes questions using an LLM to determine:

- **Question Type**: wet_lab, computational, literature, or general
- **Complexity**: simple, moderate, or complex

This enables dynamic routing to the most appropriate specialist team.

**Example Classifications:**

```python
"What is the mechanism of CRISPR-Cas9?"
→ Type: literature, Complexity: simple

"Design a RNA-seq experiment to identify DEGs in T cell activation"
→ Type: wet_lab, Complexity: moderate

"Build a machine learning model to predict drug-target interactions"
→ Type: computational, Complexity: complex
```

### 2. Specialist Team Profiles

Each question type has a specialized team:

#### Wet Lab Team
- **Experimental Design Specialist**: Rigorous protocols, controls, statistical power
- **Molecular Biology Specialist**: CRISPR, cloning, protein expression
- **Cell Biology Specialist**: Cell culture, microscopy, flow cytometry
- **Model Organism Specialist**: Animal models, tissue handling

#### Computational Team
- **Bioinformatics Specialist**: Genomics, transcriptomics, databases
- **Biostatistics Specialist**: Statistical modeling, differential expression
- **Machine Learning Specialist**: Predictive modeling, deep learning
- **Data Science Specialist**: Data integration, visualization, pipelines

#### Literature Team
- **Literature Review Specialist**: Systematic search, meta-analysis
- **Mechanism Expert**: Biological mechanisms, pathways
- **Clinical Translation Specialist**: Clinical applications, therapeutics

#### General Team
- **Generalist Researcher**: Broad biomedical knowledge
- **Methodology Expert**: Cross-domain experimental design
- **Integration Specialist**: Multi-modal evidence synthesis

### 3. Workflow Visualization

Generate workflow diagrams for documentation and stakeholder communication.

```python
from src.langgraph import visualize_workflow, print_workflow_summary

# Print text summary
print_workflow_summary()

# Generate Mermaid diagram
diagram = visualize_workflow(
    enable_human_review=True,
    output_file="workflow_diagram.mmd"
)

# Compare workflows
from src.langgraph import compare_workflows
compare_workflows(
    question="What is T cell exhaustion?",
    output_dir="workflow_comparison"
)
```

View diagrams at [Mermaid Live](https://mermaid.live) or use Mermaid CLI:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i workflow_diagram.mmd -o workflow_diagram.png
```

### 4. Human-in-the-Loop Review

Add approval checkpoints for critical decisions.

**Workflow with Review:**

1. Question is classified
2. Virtual Lab executes with specialists
3. **⏸️ PAUSE** at `human_review` checkpoint
4. Human reviews answer and provides feedback
5. Continue based on decision:
   - **approved**: Return final answer
   - **rejected**: Return with rejection note
   - **revise**: Route back to classifier with feedback

**Implementation:**

```python
# Start workflow
result = run_research_workflow(
    question="Should we use CRISPR-Cas9 or base editing?",
    enable_human_review=True,
    thread_id="exp_design_001"
)

# Workflow pauses - human reviews in external system

# Continue after review
final = continue_after_human_review(
    thread_id="exp_design_001",
    approval_status="revise",
    human_feedback="Please include cost comparison"
)
```

### 5. Execution Traces

Export detailed execution traces for debugging and auditing.

```python
from src.langgraph import export_execution_trace

# After workflow completes
export_execution_trace(
    result,
    output_file="execution_trace.json",
    format="json"
)

# Human-readable trace
export_execution_trace(
    result,
    output_file="execution_trace.txt",
    format="txt"
)
```

**Trace Contents:**
- Question and classification
- Execution path (nodes visited)
- Team composition
- Full meeting transcript
- Human feedback (if enabled)
- Final answer and confidence
- Errors (if any)

## State Management

The workflow maintains a shared state dictionary:

```python
{
    "question": str,                    # Research question
    "question_type": str,               # wet_lab | computational | literature | general
    "question_complexity": str,         # simple | moderate | complex
    "team_composition": list[str],      # Specialist roles
    "meeting_transcript": str,          # Full conversation
    "requires_human_approval": bool,    # Human review enabled?
    "human_feedback": str | None,       # Reviewer feedback
    "approval_status": str,             # approved | rejected | revise | pending
    "final_answer": str,                # Synthesized answer
    "confidence_score": float,          # 0.0-1.0
    "references": list[str],            # Citations
    "execution_path": list[str],        # Nodes executed
    "errors": list[str]                 # Error messages
}
```

State updates are automatically merged using LangGraph's annotation system.

## Configuration

### Environment Variables

```bash
# Required
OPENROUTER_API_KEY=your_key_here
DATABASE_DIR=/path/to/databases

# Optional
LANGGRAPH_PROVIDER=openrouter       # or "anthropic"
LANGGRAPH_MODEL=google/gemini-2.0-flash-exp:free
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
PROVIDER=openrouter
```

### Customization

#### Custom Specialist Profiles

Edit `src/langgraph/nodes.py`:

```python
SPECIALIST_PROFILES = {
    "wet_lab": [
        {
            "role": "Your Custom Specialist",
            "expertise": "Domain-specific expertise"
        },
        # ... more specialists
    ]
}
```

#### Custom Routing Logic

Edit `src/langgraph/classifier.py`:

```python
def route_by_question_type(state: ResearchState) -> str:
    question_type = state.get("question_type", "general")
    
    # Add custom routing logic
    if "drug discovery" in state["question"].lower():
        return "virtual_lab_drug_discovery"  # custom node
    
    # ... default routing
```

## Examples

### Example 1: Literature Review

```python
from src.langgraph import run_research_workflow

question = "What are the mechanisms of T cell exhaustion in chronic infection?"

result = run_research_workflow(
    question=question,
    enable_human_review=False,
    verbose=True
)

# Result:
# - Type: literature
# - Team: Literature Review Specialist, Mechanism Expert, Clinical Translation
# - Complexity: moderate (3 specialists, 2 rounds)
```

### Example 2: Computational Analysis

```python
question = "Analyze Q5 RNA-seq data to identify pathways enriched in T cell activation"

result = run_research_workflow(
    question=question,
    enable_human_review=False,
    verbose=True
)

# Result:
# - Type: computational
# - Team: Bioinformatics, Biostatistics, Data Science
# - Complexity: complex (3-4 specialists, 2-3 rounds)
```

### Example 3: Experimental Design with Review

```python
from src.langgraph import run_research_workflow, continue_after_human_review

question = "Design a CRISPR screen to identify regulators of T cell exhaustion"

# Start with human review
result = run_research_workflow(
    question=question,
    enable_human_review=True,
    thread_id="crispr_screen_001"
)

# Review the proposed design...

# Approve
final = continue_after_human_review(
    thread_id="crispr_screen_001",
    approval_status="approved",
    human_feedback="Design looks comprehensive"
)
```

### Example 4: Workflow Comparison

```python
from src.langgraph import compare_workflows

# Generate comparison diagrams
compare_workflows(
    question="What is T cell exhaustion?",
    output_dir="docs/workflow_diagrams"
)

# Creates:
# - docs/workflow_diagrams/workflow_basic.mmd
# - docs/workflow_diagrams/workflow_human_review.mmd
# - docs/workflow_diagrams/README.md
```

## Testing

Run the test suite:

```bash
python test_langgraph.py
```

Run the demo:

```bash
python demo_langgraph.py
```

## Benefits

### 1. Efficiency
- Parallel specialist execution (from asyncio integration)
- Smart routing reduces unnecessary iterations
- Complexity-based scaling (simple questions get smaller teams)

### 2. Transparency
- Visual workflow diagrams for stakeholders
- Execution traces for debugging
- Clear execution path tracking

### 3. Control
- Human-in-the-loop for critical decisions
- State persistence for resumable workflows
- Customizable routing and team composition

### 4. Maintainability
- Modular node architecture
- Clear separation of concerns
- Type-safe state management

## Troubleshooting

### Import Errors

```python
# If you see "Module langgraph not found"
pip install langgraph langchain-core langchain-anthropic langchain-openai
```

### Classification Issues

If questions are misclassified:

1. Check classification prompt in `src/langgraph/classifier.py`
2. Adjust temperature (currently 0.3 for consistency)
3. Add custom routing logic in `route_by_question_type()`

### Execution Failures

Check execution traces:

```python
export_execution_trace(result, "debug_trace.json", format="json")
```

Look for:
- `errors` field for error messages
- `execution_path` to see which nodes ran
- `meeting_transcript` for conversation details

## Migration from Direct Virtual Lab

**Before (Direct):**
```python
from src.agent.meeting import run_virtual_lab_meeting

answer = run_virtual_lab_meeting(
    question="What is T cell exhaustion?",
    num_specialists=3,
    num_rounds=2
)
```

**After (LangGraph):**
```python
from src.langgraph import run_research_workflow

result = run_research_workflow(
    question="What is T cell exhaustion?",
    enable_human_review=False
)
answer = result["final_answer"]
```

Benefits of migration:
- Automatic team selection (no manual specialist configuration)
- Complexity-based scaling
- Visualization and tracing
- Human review option

## Next Steps

1. **Try the demo**: `python demo_langgraph.py`
2. **Run tests**: `python test_langgraph.py`
3. **View diagrams**: Check `*.mmd` files at [mermaid.live](https://mermaid.live)
4. **Customize**: Edit specialist profiles in `src/langgraph/nodes.py`
5. **Integrate**: Add to your CLI or API

## Reference

- **Source Code**: `src/langgraph/`
- **Test Suite**: `test_langgraph.py`
- **Demo**: `demo_langgraph.py`
- **Architecture**: `docs/LANGGRAPH_INTEGRATION_PLAN.md`
