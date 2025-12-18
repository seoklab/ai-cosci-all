# Virtual Lab Enhancements - Parallel Execution & LangGraph Integration Plan

## ✅ COMPLETED: Parallel Specialist Execution (Custom Asyncio)

### Implementation
Added asynchronous execution support to enable multiple specialists to work simultaneously instead of sequentially.

**Changes:**
1. **src/agent/agent.py**:
   - Added `import asyncio`
   - Added `async def run_async()` method to `BioinformaticsAgent`
   - Uses `loop.run_in_executor()` to run sync code in thread pool without blocking

2. **src/agent/meeting.py**:
   - Added `import asyncio` and typing imports
   - Added `_run_specialists_parallel()` method:
     - Builds shared context for all specialists
     - Creates async tasks for each specialist using `run_async()`
     - Uses `asyncio.gather()` to run all specialists concurrently
     - Returns responses in same order as specialists list
   - Updated `run_meeting()` to call parallel execution instead of sequential loop

### Benefits
- **Faster meetings**: 3 specialists running simultaneously instead of one-at-a-time
- **Better resource utilization**: While one specialist waits for API/tool response, others continue working
- **Scalable**: Easily handles larger teams (5-7 specialists) without proportional time increase

### How It Works
```python
# OLD (Sequential - slow):
for specialist in specialists:
    response = specialist.run(prompt)  # Wait for each
    
# NEW (Parallel - fast):
responses = await asyncio.gather(*[
    specialist.run_async(prompt) for specialist in specialists
])
```

**Time savings**: For 3 specialists with ~10s response time each:
- Sequential: 30+ seconds
- Parallel: ~10 seconds (70% faster!)

---

## 📋 TODO: LangGraph Integration (Items 2-4)

### Architecture: Hybrid Approach

We'll wrap the existing Virtual Lab system with LangGraph for orchestration while keeping the core logic intact:

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph StateGraph                      │
│                     (Orchestration Layer)                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐      ┌──────────────────────────────────┐ │
│  │  Question   │──────▶│   Question Classifier Node       │ │
│  │   Input     │      │   (Analyze question type)        │ │
│  └─────────────┘      └──────────────┬───────────────────┘ │
│                                       │                      │
│                            ┌──────────┴──────────┐          │
│                            │  Conditional Router │          │
│                            └──┬──────┬──────┬───┘          │
│                               │      │      │               │
│               Wet-lab ────────┘      │      └──── Computational
│               question           Literature                  │
│                                  question                    │
│               ↓                      ↓           ↓           │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌─────────┐ │
│  │ Virtual Lab Meeting │  │ Virtual Lab ... │  │  Virt.. │ │
│  │  (Experimental)     │  │ (Literature)    │  │  (Comp) │ │
│  │  - Wet lab expert   │  │ - Bioinformatics│  │  -Stats │ │
│  │  - Molecular bio    │  │ - Literature..  │  │  -ML    │ │
│  │  - Cell biology     │  │ - Clinician     │  │  -Viz   │ │
│  └──────────┬──────────┘  └────────┬────────┘  └────┬────┘ │
│             │                      │                 │       │
│             └──────────────────────┴─────────────────┘       │
│                                    │                         │
│                          ┌─────────▼──────────┐             │
│                          │ Human Review Node  │ ◄─── Checkpoint
│                          │ (Optional: --human-approval)     │ │
│                          └─────────┬──────────┘             │
│                                    │                         │
│                          ┌─────────▼──────────┐             │
│                          │  Final Answer Node │             │
│                          └────────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Setup LangGraph Dependencies

```bash
pip install langgraph langchain-core langchain-anthropic langchain-openai
```

### Phase 2: Implement Question Classifier Node (#2 - Dynamic Routing)

**File**: `src/langgraph/classifier.py`

```python
from typing import TypedDict, Literal
from langgraph.graph import StateGraph

class ResearchState(TypedDict):
    """State shared across all nodes."""
    question: str
    question_type: Literal["wet_lab", "computational", "literature", "general"]
    team_composition: list[dict]
    meeting_transcript: list[dict]
    final_answer: str
    human_feedback: str | None

def classify_question(state: ResearchState) -> ResearchState:
    """Classify question to route to appropriate specialist team."""
    question = state["question"]
    
    # Use LLM to classify
    classification_prompt = f'''Classify this research question:
    
"{question}"

Categories:
- wet_lab: Requires experimental/lab techniques (e.g., CRISPR, cell culture, animal models)
- computational: Requires data analysis/ML/bioinformatics (e.g., RNA-seq, drug discovery, simulations)
- literature: Primarily requires literature review and synthesis
- general: Broad question needing diverse expertise

Return only the category name.'''
    
    # Call LLM (using existing client)
    ...
    
    state["question_type"] = result
    return state

def route_by_question_type(state: ResearchState) -> str:
    """Conditional edge routing function."""
    return state["question_type"]  # Returns node name to route to
```

### Phase 3: Wrap Virtual Lab in Graph Nodes

**File**: `src/langgraph/nodes.py`

```python
from src.agent.meeting import VirtualLabMeeting

def virtual_lab_wet_lab(state: ResearchState) -> ResearchState:
    """Run Virtual Lab with wet-lab specialist team."""
    meeting = VirtualLabMeeting(
        user_question=state["question"],
        max_team_size=3,
        # Force wet-lab specialists in team design prompt
    )
    answer = meeting.run_meeting(num_rounds=2)
    state["final_answer"] = answer
    state["meeting_transcript"] = meeting.meeting_transcript
    return state

def virtual_lab_computational(state: ResearchState) -> ResearchState:
    """Run Virtual Lab with computational specialist team."""
    ...

def virtual_lab_literature(state: ResearchState) -> ResearchState:
    """Run Virtual Lab with literature-focused team."""
    ...
```

### Phase 4: Human-in-the-Loop Checkpoint (#4)

```python
def human_review_node(state: ResearchState) -> ResearchState:
    """Checkpoint for human review."""
    # LangGraph will pause here if interrupt_before=["human_review"]
    if state.get("human_feedback"):
        # Human provided feedback - incorporate it
        state["final_answer"] = f"{state['final_answer']}\n\nHuman Feedback: {state['human_feedback']}"
    return state

# Build graph with interrupt
graph_builder = StateGraph(ResearchState)
...
graph = graph_builder.compile(
    checkpointer=MemorySaver(),  # Enable persistence
    interrupt_before=["human_review"]  # Pause before this node
)

# Usage
config = {"configurable": {"thread_id": "42"}}
result = graph.invoke({"question": "..."}, config)
# Graph pauses at human_review

# Human reviews, provides feedback
graph.update_state(config, {"human_feedback": "Please add more details on..."})

# Resume execution
final_result = graph.invoke(None, config)
```

### Phase 5: Workflow Visualization (#3)

```python
from langgraph.graph import StateGraph

# After building graph
print(graph.get_graph().draw_mermaid())

# Generates:
# graph TD
#     Question --> Classifier
#     Classifier -->|wet_lab| VirtualLab_WetLab
#     Classifier -->|computational| VirtualLab_Computational
#     ...
```

**Also export execution trace:**
```python
import json

# Run with tracing
events = []
for event in graph.stream({"question": "..."}, config):
    events.append(event)

# Save trace
with open("execution_trace.json", "w") as f:
    json.dump(events, f, indent=2)
```

---

## CLI Integration

**File**: `src/cli.py`

```python
parser.add_argument(
    "--human-approval",
    action="store_true",
    help="Enable human-in-the-loop checkpoints (requires LangGraph)"
)

if args.use_langgraph or args.human_approval:
    from src.langgraph.workflow import run_langgraph_workflow
    answer = run_langgraph_workflow(
        question=args.question,
        human_approval=args.human_approval,
        ...
    )
else:
    # Use direct Virtual Lab (faster, no checkpoints)
    meeting = VirtualLabMeeting(...)
    answer = meeting.run_meeting()
```

---

## Benefits of Hybrid Approach

✅ **Keep what works**: Your Virtual Lab meeting logic stays unchanged  
✅ **Add orchestration**: LangGraph handles routing and checkpoints  
✅ **Visual workflows**: Auto-generated graphs for stakeholders  
✅ **Flexible**: Can use Virtual Lab directly OR via LangGraph  
✅ **Debuggable**: Execution traces show exact path taken  
✅ **Human oversight**: Pause/resume for critical decisions  

---

## Next Steps

1. Install LangGraph: `pip install langgraph langchain-core`
2. Create `src/langgraph/` directory structure
3. Implement question classifier
4. Wrap Virtual Lab in graph nodes
5. Add human-in-the-loop checkpoints
6. Test with visualization
7. Update documentation

---

## Files to Create

```
src/langgraph/
  ├── __init__.py
  ├── state.py          # ResearchState TypedDict definition
  ├── classifier.py     # Question classification node
  ├── nodes.py          # Virtual Lab wrapper nodes
  ├── workflow.py       # Main graph construction
  └── visualization.py  # Graph and trace export utilities
```

Ready to implement Phase 1? 🚀
