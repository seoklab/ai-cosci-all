# Configuration Guide: Virtual Lab Settings

## Environment Variables (.env)

### Required
```bash
# API Keys (at least one required)
OPENROUTER_API_KEY=sk-or-v1-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Optional (with defaults)
```bash
# Database directory
DATABASE_DIR=/home.galaxy4/sumin/project/aisci/Competition_Data

# Default provider
PROVIDER=openrouter                # or "anthropic"

# Default model (for direct VirtualLabMeeting and LangGraph)
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

# LangGraph-specific (optional overrides)
LANGGRAPH_PROVIDER=openrouter      # Override for classifier only
LANGGRAPH_MODEL=google/gemini-2.0-flash-exp:free  # Override for classifier only
```

---

## Configuration Priority

### For All Approaches

**Priority order** (highest to lowest):
1. **Explicit function parameters** - Always wins
2. **Environment variables (.env)** - Used if no explicit parameter
3. **Function defaults** - Fallback if nothing else specified

---

## Approach 1: Direct VirtualLabMeeting

```python
from src.agent.meeting import VirtualLabMeeting

meeting = VirtualLabMeeting(
    user_question="...",
    model="google/gemini-2.0-flash-exp:free",  # Explicit (highest priority)
    # OR uses: os.getenv("OPENROUTER_MODEL")   # From .env
    # OR uses: "claude-sonnet-4-20250514"      # Default
    
    provider="openrouter",                      # Explicit
    # OR uses: os.getenv("PROVIDER")           # From .env
    # OR uses: "anthropic"                     # Default
    
    api_key="sk-...",                          # Explicit
    # OR uses: os.getenv("OPENROUTER_API_KEY") # From .env
    
    data_dir="/path/to/data",                  # Explicit
    # OR uses: os.getenv("DATABASE_DIR")       # From .env
    # OR uses: hardcoded default               # Fallback
)
```

**What .env controls**:
- ✅ `OPENROUTER_API_KEY` → API authentication
- ✅ `OPENROUTER_MODEL` → Which model to use
- ✅ `PROVIDER` → openrouter vs anthropic
- ✅ `DATABASE_DIR` → Data file location

---

## Approach 2: LangGraph Workflow

```python
from src.virtuallab_workflow import run_research_workflow

result = run_research_workflow(
    question="...",
    # No model parameter - uses .env settings internally
)
```

**What .env controls**:

### For Classifier Node:
```python
# Reads from:
LANGGRAPH_PROVIDER=openrouter   # If set, overrides PROVIDER for classifier
LANGGRAPH_MODEL=...             # If set, overrides OPENROUTER_MODEL for classifier
# Falls back to:
PROVIDER=openrouter
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
```

### For Virtual Lab Nodes:
```python
# Always reads from:
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
PROVIDER=openrouter
DATABASE_DIR=/path/to/data
OPENROUTER_API_KEY=...
```

**Configuration hierarchy**:
1. `LANGGRAPH_*` variables (classifier only)
2. Standard `PROVIDER`, `OPENROUTER_MODEL` variables
3. Hardcoded defaults

---

## Approach 3: Consensus Mechanism

```python
from src.virtuallab_workflow import run_consensus_meeting

result = run_consensus_meeting(
    question="...",
    models=["model1", "model2"],  # Explicit list (highest priority)
    # OR uses: DEFAULT_CONSENSUS_MODELS (if models=None)
    
    provider="openrouter",         # Explicit
    # OR uses: "openrouter"        # Default (consensus always uses openrouter)
    
    data_dir="/path",              # Explicit
    # OR uses: os.getenv("DATABASE_DIR")  # From .env
)
```

**What .env controls**:
- ✅ `OPENROUTER_API_KEY` → API authentication
- ✅ `DATABASE_DIR` → Data file location
- ❌ `OPENROUTER_MODEL` → NOT used (consensus needs multiple models)

**Model selection**:
```python
# Priority 1: Explicit parameter
run_consensus_meeting(models=["gemini", "llama"])

# Priority 2: DEFAULT_CONSENSUS_MODELS (if models=None)
DEFAULT_CONSENSUS_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "microsoft/phi-4:free"
]
```

**Key difference**: Consensus **ignores** `OPENROUTER_MODEL` because it needs multiple models, not one.

---

## Summary Table

| Setting | Direct | LangGraph | Consensus | Notes |
|---------|--------|-----------|-----------|-------|
| `OPENROUTER_API_KEY` | ✅ Used | ✅ Used | ✅ Used | Required for all |
| `OPENROUTER_MODEL` | ✅ Used | ✅ Used | ❌ Ignored | Consensus uses list |
| `PROVIDER` | ✅ Used | ✅ Used | ✅ Used | openrouter or anthropic |
| `DATABASE_DIR` | ✅ Used | ✅ Used | ✅ Used | Data file location |
| `LANGGRAPH_PROVIDER` | ❌ N/A | ✅ Used (classifier) | ❌ N/A | Classifier override |
| `LANGGRAPH_MODEL` | ❌ N/A | ✅ Used (classifier) | ❌ N/A | Classifier override |

---

## Common Configurations

### Configuration 1: Simple (One Model)
```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
PROVIDER=openrouter
DATABASE_DIR=/path/to/data
```

**Works for**:
- ✅ Direct VirtualLabMeeting
- ✅ LangGraph (uses gemini for everything)
- ⚠️ Consensus (ignores model, uses DEFAULT_CONSENSUS_MODELS)

---

### Configuration 2: LangGraph Optimized
```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...

# Use fast/cheap model for classification
LANGGRAPH_PROVIDER=openrouter
LANGGRAPH_MODEL=google/gemini-2.0-flash-exp:free

# Use stronger model for Virtual Lab meetings
PROVIDER=openrouter
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

DATABASE_DIR=/path/to/data
```

**Behavior**:
- Classifier: Uses Gemini (fast, cheap)
- Virtual Lab: Uses Llama (stronger reasoning)
- Saves costs on classification, quality on analysis

---

### Configuration 3: Consensus Default
```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...
PROVIDER=openrouter
DATABASE_DIR=/path/to/data
# Don't set OPENROUTER_MODEL - not used by consensus
```

**Behavior**:
- Uses `DEFAULT_CONSENSUS_MODELS` (4 different free models)
- Each model gets independent Virtual Lab meeting
- Synthesizes consensus from all

---

### Configuration 4: Custom Consensus Models
```python
# In code (not .env)
from src.virtuallab_workflow import run_consensus_meeting

# Define your preferred models
MY_CONSENSUS_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "anthropic/claude-3.5-sonnet",  # Paid model
    "meta-llama/llama-3.3-70b-instruct:free"
]

result = run_consensus_meeting(
    question="...",
    models=MY_CONSENSUS_MODELS,  # Overrides DEFAULT_CONSENSUS_MODELS
    provider="openrouter"
)
```

---

## Does Consensus Override .env?

**Short answer**: No, it respects .env settings

**Long answer**:

### Consensus USES .env for:
- ✅ `OPENROUTER_API_KEY` - Always required
- ✅ `DATABASE_DIR` - Uses if not explicitly provided
- ✅ `PROVIDER` - Uses if not explicitly provided

### Consensus IGNORES .env for:
- ❌ `OPENROUTER_MODEL` - Because consensus needs **multiple** models

**Why `OPENROUTER_MODEL` is ignored**:
```python
# This makes no sense for consensus:
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

run_consensus_meeting(...)  # What should it do?
# Run same model multiple times? Pointless!
# Use only that one model? Not consensus!

# Instead, consensus uses:
DEFAULT_CONSENSUS_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "microsoft/phi-4:free"
]
```

---

## Recommended Setup

### For Most Users (Simple)
```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
PROVIDER=openrouter
DATABASE_DIR=/home.galaxy4/sumin/project/aisci/Competition_Data
```

**Works for**:
- ✅ Direct VirtualLabMeeting
- ✅ LangGraph workflow
- ✅ Consensus (uses its own model list)

### For Advanced Users (Optimized)
```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...
ANTHROPIC_API_KEY=sk-ant-...

# Cheap/fast for classification
LANGGRAPH_PROVIDER=openrouter
LANGGRAPH_MODEL=google/gemini-2.0-flash-exp:free

# Better for Virtual Lab
PROVIDER=openrouter
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

DATABASE_DIR=/path/to/data
```

Then in code, choose approach based on needs:
```python
# Simple question → Direct (uses OPENROUTER_MODEL)
meeting = VirtualLabMeeting(user_question="...")

# Route by type → LangGraph (uses both configs)
result = run_research_workflow(question="...")

# High stakes → Consensus (uses DEFAULT_CONSENSUS_MODELS)
result = run_consensus_meeting(question="...")

# Adaptive → Combined (uses all of the above)
result = run_research_workflow(
    question="...",
    requires_consensus=True  # For complex questions
)
```

---

## Override Examples

### Override Everything
```python
run_consensus_meeting(
    question="...",
    models=["custom-model-1", "custom-model-2"],  # Override default models
    provider="anthropic",                         # Override .env PROVIDER
    data_dir="/custom/path",                      # Override .env DATABASE_DIR
    team_size=5,                                  # Override default 3
    num_rounds=4                                  # Override default 2
)
```

### Override Nothing (Use All Defaults)
```python
run_consensus_meeting(question="...")
# Uses:
# - models: DEFAULT_CONSENSUS_MODELS
# - provider: "openrouter" (hardcoded default)
# - data_dir: DATABASE_DIR from .env
# - team_size: 3
# - num_rounds: 2
```

---

## FAQ

**Q: Why doesn't consensus use `OPENROUTER_MODEL`?**
A: Consensus needs multiple models. Using one model from .env makes no sense.

**Q: Can I set consensus models in .env?**
A: No, but you can modify `DEFAULT_CONSENSUS_MODELS` in `consensus.py` or pass explicitly:
```python
run_consensus_meeting(models=["model1", "model2"])
```

**Q: Does LangGraph override my .env?**
A: No, it **reads** from .env. You can override with explicit parameters.

**Q: Which settings should I put in .env vs code?**
A: 
- .env: Things that rarely change (API keys, paths, default model)
- Code: Things that vary per query (consensus models, team size, rounds)

**Q: Can I use different providers for different parts?**
A: Yes! Set `LANGGRAPH_PROVIDER` different from `PROVIDER`, or pass explicitly:
```python
run_consensus_meeting(provider="anthropic")
run_research_workflow(...)  # Uses PROVIDER from .env
```

---

## Summary

**Consensus does NOT override .env settings**. Instead:

1. **Respects** .env for: API keys, data directory, provider
2. **Ignores** `OPENROUTER_MODEL` (needs multiple models, not one)
3. **Uses** `DEFAULT_CONSENSUS_MODELS` if you don't specify
4. **Allows** explicit override of everything

**The hierarchy is always**: Explicit parameter > .env > Default
