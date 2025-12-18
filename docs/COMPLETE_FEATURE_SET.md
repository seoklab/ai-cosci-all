# Virtual Lab: Complete Feature Set

## Summary

You now have **THREE complementary approaches** for running Virtual Lab, each serving different use cases:

1. ✅ **Direct VirtualLabMeeting** - Original implementation (fast, simple)
2. ✅ **LangGraph Workflow** - Intelligent routing + visualization + human review
3. ✅ **Consensus Mechanism** - Multi-model robustness
4. ✅ **Combined** - LangGraph + Consensus for adaptive intelligence

**All features are kept and work together!**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    VIRTUAL LAB SYSTEM                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: Core (Original)                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ VirtualLabMeeting                                   │   │
│  │  • PI designs team                                  │   │
│  │  • Specialists discuss (parallel)                   │   │
│  │  • Critic reviews                                   │   │
│  │  • PI synthesizes                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                         ▲                                   │
│                         │                                   │
│  Layer 2: Orchestration (LangGraph)                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Classifier → Routing → Virtual Lab → Human Review  │   │
│  │  • Question type analysis                           │   │
│  │  • Automatic team selection                         │   │
│  │  • Workflow visualization                           │   │
│  │  • Human-in-the-loop                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                         ▲                                   │
│                         │                                   │
│  Layer 3: Robustness (Consensus)                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Multi-Model Consensus                               │   │
│  │  • Run with Model 1 → Answer 1                     │   │
│  │  • Run with Model 2 → Answer 2                     │   │
│  │  • Run with Model 3 → Answer 3                     │   │
│  │  • Synthesize → Consensus + Agreement Score        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Use Cases

### Scenario 1: Quick Exploration
**Use**: Direct VirtualLabMeeting
```python
from src.agent.meeting import VirtualLabMeeting

meeting = VirtualLabMeeting(
    user_question="What is CAR-T therapy?",
    max_team_size=3,
    verbose=True
)
answer = meeting.run_meeting(num_rounds=2)
```

**Why**: Fast, simple, one API call set

---

### Scenario 2: Unknown Question Type
**Use**: LangGraph Workflow
```python
from src.virtuallab_workflow import run_research_workflow

result = run_research_workflow(
    question="Analyze my RNA-seq data for pathway enrichment",
    verbose=True
)
# Automatically classifies as "computational"
# Routes to bioinformatics specialists
```

**Why**: Let AI determine the best specialist team

---

### Scenario 3: High-Stakes Decision
**Use**: Consensus Mechanism
```python
from src.virtuallab_workflow import run_consensus_meeting

result = run_consensus_meeting(
    question="Should we proceed with this clinical trial design?",
    models=[
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "microsoft/phi-4:free"
    ],
    team_size=4,
    num_rounds=3
)
# Returns consensus with agreement score
# Shows where models agree/disagree
```

**Why**: Reduce model bias, identify uncertainty

---

### Scenario 4: Production System (Best!)
**Use**: Combined (LangGraph + Consensus)

```python
from src.virtuallab_workflow import run_research_workflow

result = run_research_workflow(
    question="Design a CRISPR screen for cancer drivers",
    enable_human_review=True,
    requires_consensus=True,  # Use consensus for complex
    consensus_models=[
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free"
    ],
    verbose=True
)

# Workflow:
# 1. Classifier analyzes → "wet_lab", "complex"
# 2. Routes to consensus (because complex)
# 3. Runs 2 meetings with different models
# 4. Synthesizes consensus
# 5. Pauses for human review
# 6. Returns final answer
```

**Why**: Adaptive intelligence + maximum reliability

---

## Feature Comparison

| Feature | Direct | LangGraph | Consensus | Combined |
|---------|--------|-----------|-----------|----------|
| **Speed** | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ |
| **Cost** | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ |
| **Robustness** | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Auto-routing** | ❌ | ✅ | ❌ | ✅ |
| **Visualization** | ❌ | ✅ | ❌ | ✅ |
| **Human review** | ❌ | ✅ | ❌ | ✅ |
| **Multi-model** | ❌ | ❌ | ✅ | ✅* |
| **Uncertainty detection** | ❌ | ❌ | ✅ | ✅* |

\* = For complex questions only (adaptive)

---

## Files Created

### Core LangGraph (6 files)
```
src/virtuallab_workflow/
├── __init__.py              # Exports
├── state.py                 # State definition (with consensus fields)
├── classifier.py            # Question classification
├── nodes.py                 # Virtual Lab wrappers
├── workflow.py              # Graph construction
└── visualization.py         # Diagrams + traces
```

### Consensus Mechanism (2 files)
```
src/virtuallab_workflow/
├── consensus.py             # Multi-model consensus
└── nodes_consensus.py       # Consensus graph nodes
```

### Tests & Demos (4 files)
```
test_langgraph.py           # LangGraph tests
demo_langgraph.py           # LangGraph demo
test_consensus.py           # Consensus tests
demo_all_approaches.py      # Complete comparison demo
```

### Documentation
```
docs/
├── LANGGRAPH_USAGE.md          # LangGraph user guide
├── LANGGRAPH_IMPLEMENTATION.md # Implementation details
└── SESSION_SUMMARY_2025-12-11.md # Today's work summary
```

---

## Quick Start

### 1. LangGraph Only
```bash
python demo_langgraph.py
```

### 2. Consensus Only
```bash
python test_consensus.py
```

### 3. See All Approaches
```bash
python demo_all_approaches.py
```

---

## Integration Examples

### Example 1: LangGraph with Conditional Consensus

```python
from src.virtuallab_workflow import run_research_workflow

# Simple questions use single model
# Complex questions automatically use consensus
result = run_research_workflow(
    question="What is apoptosis?",  # Simple → single model
    verbose=True
)

result = run_research_workflow(
    question="Design multi-omics experiment for cancer",  # Complex → consensus
    verbose=True
)
```

### Example 2: Force Consensus for Specific Topics

```python
from src.virtuallab_workflow import run_consensus_meeting

# Always use consensus for clinical decisions
if "clinical trial" in question or "patient" in question:
    result = run_consensus_meeting(
        question=question,
        models=CONSENSUS_MODELS,
        team_size=4,
        num_rounds=3
    )
else:
    result = run_research_workflow(
        question=question,
        verbose=True
    )
```

### Example 3: Human Review + Consensus

```python
from src.virtuallab_workflow import run_research_workflow, continue_after_human_review

# Run with both consensus and human review
result = run_research_workflow(
    question="Should we use CRISPR or base editing?",
    enable_human_review=True,
    requires_consensus=True,
    thread_id="decision_001"
)

# Workflow pauses after consensus synthesis
# Human reviews consensus of multiple models

# Continue
final = continue_after_human_review(
    thread_id="decision_001",
    approval_status="approved"
)
```

---

## When to Use What

### Use Direct VirtualLabMeeting when:
- Quick exploratory questions
- Testing/debugging
- You trust a specific model
- Cost is primary concern

### Use LangGraph when:
- Unknown question types
- Need workflow visibility
- Stakeholder presentations
- Require approval workflows
- Multiple question types in pipeline

### Use Consensus when:
- High-stakes decisions
- Publication-quality answers
- Medical/clinical applications
- Need uncertainty quantification
- Model bias is a concern

### Use Combined when:
- Production deployment
- Adaptive cost management
- Want best of both worlds
- Complex workflows with varying question types

---

## Summary

**Nothing was thrown away!**

- ✅ Original VirtualLabMeeting: Still works, still fast
- ✅ LangGraph: Adds orchestration layer
- ✅ Consensus: Adds robustness layer
- ✅ They all work together

Think of them as:
- **Level 1**: Basic meeting (original)
- **Level 2**: Smart routing (LangGraph)
- **Level 3**: Multi-model validation (Consensus)

You can use any level depending on your needs!

---

## Next Steps

1. **Try the demos**:
   ```bash
   python demo_all_approaches.py
   ```

2. **Choose your approach**:
   - Simple questions → Direct
   - Routing needed → LangGraph
   - High stakes → Consensus
   - Production → Combined

3. **Customize**:
   - Add more models to consensus
   - Customize routing logic
   - Add domain-specific specialist profiles
   - Integrate into your CLI/API

All approaches are production-ready and tested! 🚀
