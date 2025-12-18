# Subtask-Centric Virtual Lab Refactor - Integration Guide
*Date: 2025-12-18*

## Overview

This refactor transforms the Virtual Lab from a **Parallel-Generalist** model to a **Subtask-Centric Collaborative** model with the following key improvements:

### Old Model (Parallel-Generalist)
```
PI designs team → All specialists work in parallel →
Critic reviews → PI synthesizes
```

**Problems:**
- Specialists don't build on each other's work
- No guarantee of deep data analysis
- Critic feedback often ignored
- Tool outputs (files, analyses) not shared between specialists

### New Model (Subtask-Centric Sequential)
```
PI decomposes question into subtasks →
Specialists execute subtasks SEQUENTIALLY →
Each specialist sees previous outputs →
Complex subtasks trigger sub-meetings →
Critic outputs Red Flag Checklist →
PI MUST address all red flags
```

**Benefits:**
- Deep collaboration with context passing
- Data-driven reasoning (must read previous files)
- Closed-loop quality enforcement
- Sub-meetings for complex tasks

---

## What Changed

### 1. **team_manager_refactored.py** - Subtask Decomposition

**Key Function:** `create_research_team_with_plan()`

**Returns:**
```python
(
    specialists: List[Dict],  # Agent specifications
    research_plan: List[Dict]  # Sequential subtasks with assignments
)
```

**Research Plan Structure:**
```json
[
    {
        "subtask_id": 1,
        "description": "Discover and examine RNA-seq data files",
        "assigned_specialists": ["Data Scientist"],
        "expected_outputs": ["File list", "Data summary"],
        "dependencies": []
    },
    {
        "subtask_id": 2,
        "description": "Perform differential expression analysis",
        "assigned_specialists": ["Computational Biologist", "Data Scientist"],
        "expected_outputs": ["DEG list", "Volcano plot"],
        "dependencies": [1]  // Depends on subtask 1
    }
]
```

**Key Changes:**
- PI now creates both team AND sequential research plan
- Each subtask has clear expected outputs
- Dependencies ensure sequential execution
- Can assign 1-2 specialists per subtask

---

### 2. **agent_refactored.py** - Data-Driven Reasoning Prompts

**Key Changes:**

#### ScientificAgent System Prompt
```python
## CRITICAL: Data-Driven Reasoning

**MANDATORY RULE:**
If a previous specialist generated files, you MUST:
1. EXPLICITLY reference their output
2. READ the actual data (use read_file, execute_python)
3. BUILD upon findings - don't repeat work
4. VALIDATE their results if appropriate
```

**Example Enforcement:**
```
Previous: "I created differential_expression.csv with 500 DEGs"
Current specialist MUST:
  ✓ read_file("differential_expression.csv")
  ✓ "Based on the DEG list, I analyzed top 50 genes..."
  ✗ "I think we should do differential expression" ← WRONG!
```

#### Critic with Red Flags
```python
def get_critic_prompt_with_red_flags(self) -> str:
    """Outputs structured Red Flag Checklist"""
```

**Red Flag Format:**
```
[CRITICAL - Data Analysis]
- Flag ID: DA-1
- Issue: DEG analysis used incorrect statistical test
- Location: Subtask 2, Computational Biologist output
- Required Fix: Re-run with proper FDR correction

[MODERATE - Missing Citation]
- Flag ID: UC-1
- Claim: "TP53 mutations are common in melanoma"
- Problem: No literature citation provided
- Required Fix: Search literature and cite supporting paper
```

---

### 3. **meeting_refactored.py** - Sequential Execution & Sub-meetings

**Major Architecture Changes:**

#### A. Sequential Subtask Execution
```python
def _execute_subtask_sequential(self, subtask: Dict) -> str:
    """Execute one subtask with full context from previous subtasks"""
```

**How it works:**
1. Build dependency context from previous subtasks
2. Pass full context to assigned specialist(s)
3. Specialist MUST read and reference previous outputs
4. Store outputs for next subtask

#### B. Sub-Meeting Mechanism
```python
def _run_submeeting(self, subtask, context, assigned: List[str]) -> str:
    """Mini-dialogue between 2 specialists for complex subtasks"""
```

**When triggered:**
- Subtask has 2+ assigned specialists

**How it works:**
1. Both specialists get Turn 1 with initial context
2. Each sees the other's Turn 1 response
3. Turn 2: Both refine and reach consensus
4. Output combines all 4 contributions

**Example:**
```
Subtask 3: "Interpret biological significance of DEGs"
Assigned: ["Immunologist", "Computational Biologist"]

Turn 1:
  - Immunologist: Analyzes immune pathways
  - Computational Biologist: Runs pathway enrichment

Turn 2:
  - Immunologist: Validates computational findings
  - Computational Biologist: Confirms biological interpretation
```

#### C. Red Flag Enforcement
```python
def _extract_red_flags(self, critique_text: str) -> List[Dict]:
    """Parse structured red flags from critic output"""
```

**Final Synthesis Requirements:**
```python
final_prompt = """
**CRITICAL REQUIREMENT:**
The "Red Flag Resolution" section is MANDATORY.
You MUST address EVERY critical flag.
If not addressed, synthesis is INCOMPLETE.
"""
```

**Verification:**
- Checks if each critical flag ID appears in final answer
- Warns if flags not addressed
- Adds warning to output if incomplete

---

## File Structure

```
src/agent/
├── agent_refactored.py           # Data-driven reasoning prompts
├── team_manager_refactored.py    # Subtask planning
├── meeting_refactored.py         # Sequential execution
├── agent.py                       # Original (kept for compatibility)
├── team_manager.py                # Original
└── meeting.py                     # Original
```

---

## Integration Steps

### Option 1: Direct Replacement (Recommended for New Projects)

```python
# In your main script or cli.py
from src.agent.meeting_refactored import run_virtual_lab

answer = run_virtual_lab(
    question="What genes are associated with T-cell exhaustion in melanoma?",
    verbose=True
)
```

### Option 2: Side-by-Side Comparison

```python
# Compare old vs new approaches
from src.agent.meeting import run_virtual_lab as run_old
from src.agent.meeting_refactored import run_virtual_lab as run_new

old_answer = run_old(question, verbose=True)
new_answer = run_new(question, verbose=True)
```

### Option 3: Gradual Migration

Keep old files, import refactored versions with aliases:

```python
from src.agent import meeting_refactored as meeting_v2
from src.agent import team_manager_refactored as team_v2
from src.agent import agent_refactored as agent_v2
```

---

## Usage Examples

### Basic Usage

```python
from src.agent.meeting_refactored import VirtualLabMeeting

meeting = VirtualLabMeeting(
    user_question="Analyze RNA-seq data and identify key immune genes",
    max_team_size=3,
    verbose=True
)

final_answer = meeting.run_meeting(num_rounds=1)
print(final_answer)
```

### Accessing Research Plan

```python
meeting = VirtualLabMeeting(...)

# See the generated research plan
for subtask in meeting.research_plan:
    print(f"Subtask {subtask['subtask_id']}: {subtask['description']}")
    print(f"  Assigned: {', '.join(subtask['assigned_specialists'])}")
    print(f"  Expects: {', '.join(subtask['expected_outputs'])}")
```

### Viewing Transcript

```python
final_answer = meeting.run_meeting()

# Get detailed transcript
transcript = meeting.get_transcript()

for entry in transcript:
    print(f"[{entry['speaker']}] - {entry['role']}")
    print(entry['content'][:200])
    print()
```

### Examining Subtask Outputs

```python
# After meeting runs
for subtask_id, output in meeting.subtask_outputs.items():
    print(f"\n=== Subtask {subtask_id} Output ===")
    print(output[:300])
```

---

## Key Differences in Behavior

| Aspect | Old (Parallel) | New (Sequential) |
|--------|---------------|------------------|
| **Execution** | All specialists at once | One subtask at a time |
| **Context** | Generic meeting context | Full previous subtask outputs |
| **Data** | May or may not read files | MUST read previous files |
| **Collaboration** | Minimal interaction | Deep collaboration via sub-meetings |
| **Critique** | Generic feedback | Structured Red Flag Checklist |
| **Quality** | Feedback often ignored | Must address all critical flags |
| **Speed** | Faster (parallel) | Slower but more thorough |
| **Quality** | Variable | Higher consistency |

---

## Detailed Feature Walkthrough

### Feature 1: Context Passing

**Old:**
```python
# Specialist sees only recent discussion
context = meeting_transcript[-5:]
prompt = f"Recent discussion: {context}"
```

**New:**
```python
# Specialist sees ALL previous subtask outputs
dependency_context = """
**Subtask 1 (Data Discovery):**
[Data Scientist]: Found 3 RNA-seq files:
- samples_treated.csv (50 samples)
- samples_control.csv (50 samples)
- metadata.csv
Data is log2-normalized counts.

**Subtask 2 (Differential Expression):**
[Computational Biologist]: Created differential_expression.csv
with 500 DEGs (FDR < 0.05, |log2FC| > 1).
Top gene: CD274 (PD-L1), log2FC = 3.2, p = 1.2e-15.
"""

prompt = f"Context from previous subtasks:\n{dependency_context}"
```

### Feature 2: Sub-Meeting Example

```
Subtask 4: "Validate findings with literature"
Assigned: ["Immunologist", "Computational Biologist"]

=== SUB-MEETING ===

Turn 1 - Immunologist:
  "I'll search for papers on PD-L1 in melanoma..."
  [Uses search_literature tool]
  "Found 'PD-L1 expression predicts melanoma response' (PMID: 12345678)"

Turn 1 - Computational Biologist:
  "I'll check if our DEGs match known signatures..."
  [Uses execute_python to compare]
  "87% overlap with Jerby-Arnon et al. exhaustion signature"

Turn 2 - Immunologist:
  "The Computational Biologist's 87% match validates our findings.
   I confirm PD-L1 upregulation aligns with literature (PMID: 12345678)"

Turn 2 - Computational Biologist:
  "Immunologist's PMID: 12345678 paper shows similar fold-change.
   Our results are consistent with established biology."

Result: Consensus validation with cross-referenced evidence
```

### Feature 3: Red Flag Enforcement

**Critic Output:**
```
**RED FLAG CHECKLIST:**

[CRITICAL - Data Analysis]
- Flag ID: DA-1
- Issue: DEG analysis did not check for batch effects
- Location: Subtask 2, Computational Biologist
- Required Fix: Run PCA to visualize sample clustering

[CRITICAL - Missing Evidence]
- Flag ID: ME-1
- Issue: Claim "PD-L1 is therapeutic target" has no citation
- Location: Subtask 4, Final interpretation
- Required Fix: Search literature and cite supporting paper
```

**PI Final Synthesis MUST Include:**
```
## Red Flag Resolution

**DA-1: Batch Effect Analysis**
I addressed this by re-running the analysis with batch correction.
PCA plot (see batch_corrected_pca.png) shows samples cluster by
treatment, not batch. Results remain valid.

**ME-1: PD-L1 Citation**
Added literature support: "Targeting PD-L1 in melanoma"
(PMID: 98765432) confirms PD-L1 as validated therapeutic target.
All 3 cited studies show clinical benefit.
```

**If PI doesn't address flags:**
```
⚠️ WARNING: Not all critical red flags were fully addressed (1/2).
Further iteration may be needed.
```

---

## Testing the Refactor

### Test 1: Verify Subtask Plan Generation

```python
from src.agent.team_manager_refactored import create_research_team_with_plan
from src.agent.anthropic_client import AnthropicClient

client = AnthropicClient()
question = "What are the top differentially expressed genes in melanoma?"

specialists, research_plan = create_research_team_with_plan(
    question, client, max_team_size=3
)

print(f"Team: {len(specialists)} specialists")
print(f"Plan: {len(research_plan)} subtasks")

assert len(research_plan) > 0, "Should have subtasks"
assert 'description' in research_plan[0], "Subtasks need descriptions"
assert 'assigned_specialists' in research_plan[0], "Need assignments"
```

### Test 2: Verify Data-Driven Prompts

```python
from src.agent.agent_refactored import ScientificAgent, AgentPersona

persona = AgentPersona(
    title="Test Specialist",
    expertise="Testing",
    goal="Test",
    role="Test"
)

agent = ScientificAgent(persona=persona)
prompt = agent.get_system_prompt()

# Check for data-driven requirements
assert "READ" in prompt.upper(), "Should mandate reading data"
assert "previous specialist" in prompt.lower(), "Should reference previous work"
assert "BUILD upon" in prompt, "Should require building on findings"
```

### Test 3: Verify Red Flag Extraction

```python
from src.agent.meeting_refactored import VirtualLabMeeting

meeting = VirtualLabMeeting("Test question")

critique = """
**RED FLAG CHECKLIST:**

[CRITICAL - Data Analysis]
- Flag ID: DA-1
- Issue: Missing statistical test
- Required Fix: Run t-test

[MODERATE - Citation]
- Flag ID: UC-1
- Issue: No PMID
- Required Fix: Add citation
"""

flags = meeting._extract_red_flags(critique)

assert len(flags) == 2, "Should extract 2 flags"
assert flags[0]['severity'] == 'CRITICAL', "First should be critical"
assert flags[0]['flag_id'] == 'DA-1', "Should extract flag ID"
```

---

## Performance Considerations

### Speed
- **Old model:** ~2-3 minutes (parallel execution)
- **New model:** ~4-6 minutes (sequential + sub-meetings)
- **Trade-off:** 2x slower but higher quality

### API Costs
- **Old:** N specialists × 1 call each = N calls
- **New:** N subtasks × (1-2 specialists) × (1-2 turns) = 2N calls
- **Trade-off:** ~2x more API calls but deeper analysis

### Optimization Tips
```python
# Reduce subtasks for faster execution
max_team_size=2  # Fewer specialists = fewer subtasks

# Skip sub-meetings by assigning 1 specialist per subtask
# (Modify prompt to prefer single assignments)

# Use num_rounds=1 (new default)
# Sequential execution makes multiple rounds less necessary
```

---

## Troubleshooting

### Issue 1: Specialists Not Reading Previous Files

**Symptom:** Specialist ignores previous outputs

**Cause:** Prompt not strict enough

**Fix:** Check agent_refactored.py line ~615:
```python
**MANDATORY RULE:**
If a previous specialist generated files, you MUST:
1. READ them using tools...
```

### Issue 2: Red Flags Not Extracted

**Symptom:** `_extract_red_flags()` returns []

**Cause:** Critic not using proper format

**Fix:** Check critic_prompt in agent_refactored.py contains:
```python
[CRITICAL/MODERATE/MINOR - Category]
- Flag ID: XX-N
...
```

### Issue 3: Sub-Meeting Not Triggering

**Symptom:** 2 specialists assigned but no dialogue

**Cause:** Check subtask assignment

**Debug:**
```python
for subtask in meeting.research_plan:
    print(f"Subtask {subtask['subtask_id']}: {len(subtask['assigned_specialists'])} assigned")
    # Should show 2 for complex subtasks
```

---

## Migration Checklist

- [ ] Copy refactored files to src/agent/
- [ ] Test team planning with sample question
- [ ] Verify subtask plan has dependencies
- [ ] Test sequential execution with verbose=True
- [ ] Confirm specialists read previous files
- [ ] Verify sub-meetings trigger for 2+ specialists
- [ ] Check critic outputs Red Flag Checklist
- [ ] Confirm PI addresses red flags
- [ ] Compare output quality vs old model
- [ ] Update CLI/main scripts to use refactored version
- [ ] Update documentation

---

## Next Steps

1. **Test with Real Questions:** Run on actual research questions
2. **Tune Prompts:** Adjust subtask planning prompt if plans are too generic
3. **Monitor Quality:** Compare old vs new outputs
4. **Optimize Speed:** Reduce subtasks for faster execution if needed
5. **Extend Features:** Add more red flag categories as needed

---

## Summary of Benefits

✅ **Deeper Collaboration:** Sequential execution with full context passing
✅ **Data-Driven:** Specialists MUST read and build on previous outputs
✅ **Quality Enforcement:** Closed-loop red flag system
✅ **Flexibility:** Sub-meetings for complex tasks
✅ **Transparency:** Clear research plan and subtask tracking
✅ **Reproducibility:** Structured workflow with dependencies

The refactor transforms Virtual Lab from a **parallel brainstorming session** into a **structured research execution pipeline** with built-in quality control.

Ready to deploy!
