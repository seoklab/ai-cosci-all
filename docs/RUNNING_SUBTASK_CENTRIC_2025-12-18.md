# Running Subtask-Centric Virtual Lab
*Date: 2025-12-18*

## Your Original Command

```bash
python -m src.cli \
    --question "Predicting Drug Repositioning Candidates..." \
    --combined \
    --rounds 2 \
    --team-size 3 \
    --verbose
```

**What this does:**
- Runs **LangGraph + Consensus workflow**
- Multiple models independently analyze the question
- Consensus mechanism synthesizes answers

---

## NEW: Running with Subtask-Centric Virtual Lab

### Option 1: Using Updated CLI (Recommended)

```bash
python -m src.cli_updated \
    --question "Predicting Drug Repositioning Candidates to Inhibit T-Cell Exhaustion

T-cell exhaustion is a phenomenon in which T cells, repeatedly stimulated under chronic infection or within the tumor microenvironment, lose their functional capacity. It is a major cause of reduced responsiveness to immunotherapy and treatment failure. Discovering drugs or drug combinations that can reverse exhaustion is considered a key challenge in advancing immunotherapy.

The goal of this problem is to integrate publicly available drug–gene/transcriptome databases to predict drug candidates capable of reversing a T-cell exhaustion gene signature, and to provide supporting rationale.

Below are the main three questions that should ultimately satisfy the requirements. Answer each in detail:

(A) Analysis of the T-cell Exhaustion Signature
(B) Candidate Discovery Using Drug–Gene Network Analysis
(C) Drug Candidate Selection and Mechanistic Hypothesis Generation
" \
    --subtask-centric \
    --rounds 1 \
    --team-size 3 \
    --verbose
```

**Key differences:**
- `--subtask-centric` instead of `--combined`
- `--rounds 1` (subtask-centric is more efficient with 1 round)
- Sequential execution with deeper collaboration
- Red Flag quality enforcement

---

### Option 2: Direct Python Script

Create `run_drug_repositioning.py`:

```python
from src.agent.meeting_refactored import run_virtual_lab

question = """Predicting Drug Repositioning Candidates to Inhibit T-Cell Exhaustion

T-cell exhaustion is a phenomenon in which T cells, repeatedly stimulated under
chronic infection or within the tumor microenvironment, lose their functional
capacity. It is a major cause of reduced responsiveness to immunotherapy and
treatment failure. Discovering drugs or drug combinations that can reverse
exhaustion is considered a key challenge in advancing immunotherapy.

The goal of this problem is to integrate publicly available drug–gene/transcriptome
databases to predict drug candidates capable of reversing a T-cell exhaustion gene
signature, and to provide supporting rationale.

Below are the main three questions that should ultimately satisfy the requirements.
Answer each in detail:

(A) Analysis of the T-cell Exhaustion Signature
(B) Candidate Discovery Using Drug–Gene Network Analysis. Here the candidate is a
    drug candidate that can reverse exhaustion.
(C) Drug Candidate Selection (selecting from candidates found by (B)?) and
    Mechanistic Hypothesis Generation.
"""

answer = run_virtual_lab(
    question=question,
    max_team_size=3,
    num_rounds=1,
    verbose=True
)

print("\n" + "="*80)
print("FINAL ANSWER:")
print("="*80)
print(answer)

# Save to file
with open('drug_repositioning_answer.md', 'w') as f:
    f.write(answer)
```

Run:
```bash
python run_drug_repositioning.py
```

---

## What to Expect (Subtask-Centric Workflow)

### Phase 1: Team Design & Research Planning

**PI will:**
1. Analyze your 3-part question (A, B, C)
2. Design a team (e.g., Bioinformatician, Drug Discovery Specialist, Immunologist)
3. Decompose into ~4-6 sequential subtasks

**Example Research Plan:**
```
Subtask 1: Literature Review of T-cell Exhaustion Signatures
  - Assigned: Immunologist
  - Expected: Key genes/pathways, published signatures

Subtask 2: Analyze Exhaustion Signature from Available Data
  - Assigned: Bioinformatician
  - Expected: DEG list, pathway enrichment results

Subtask 3: Query Drug-Gene Databases for Reversal Candidates
  - Assigned: Bioinformatician, Drug Discovery Specialist (SUB-MEETING)
  - Expected: List of drug candidates with mechanisms

Subtask 4: Validate Candidates via Literature
  - Assigned: Drug Discovery Specialist, Immunologist (SUB-MEETING)
  - Expected: Evidence for top candidates

Subtask 5: Mechanistic Hypothesis Generation
  - Assigned: Immunologist
  - Expected: Detailed mechanistic rationale
```

### Phase 2: Sequential Subtask Execution

**Subtask 1:**
```
[Immunologist]: Searching literature for T-cell exhaustion signatures...
  Tool: search_literature("T-cell exhaustion gene signature")
  Output: "Found exhaustion signature includes PD-1, CTLA-4, LAG3, TIM3..."
  File created: exhaustion_signature_literature.txt
```

**Subtask 2:**
```
[Bioinformatician]: Reading exhaustion_signature_literature.txt...
  Tool: read_file("exhaustion_signature_literature.txt")
  Tool: execute_python("# Analyze expression data...")
  Output: "Created differential_expression.csv with 200 exhaustion markers"
  File created: differential_expression.csv, exhaustion_heatmap.png
```

**Subtask 3 (Sub-Meeting):**
```
=== SUB-MEETING: Bioinformatician & Drug Discovery Specialist ===

Turn 1 - Bioinformatician:
  "Reading differential_expression.csv..."
  Tool: query_database("drugbank", query="Target Name:PD-1")
  Output: "Found 15 drugs targeting PD-1 pathway"

Turn 1 - Drug Discovery Specialist:
  "Building on Bioinformatician's PD-1 findings..."
  Tool: search_literature("PD-1 inhibitors exhaustion reversal")
  Output: "Nivolumab and Pembrolizumab validated in literature"

Turn 2 - Bioinformatician:
  "Validating Drug Discovery Specialist's findings computationally..."
  Tool: execute_python("# Check drug-gene network connectivity")
  Output: "Network analysis confirms PD-1 inhibitors target 87% of signature"

Turn 2 - Drug Discovery Specialist:
  "Based on network analysis, proposing combination therapy..."
  Output: "Top candidates: Nivolumab + Ipilimumab (dual checkpoint blockade)"
```

### Phase 3: Critic Red Flag Review

```
**RED FLAG CHECKLIST:**

[CRITICAL - Missing Analysis]
- Flag ID: MA-1
- Issue: CTLA-4 pathway not explored in drug search
- Location: Subtask 3, Drug database query
- Required Fix: Query DrugBank for CTLA-4 targeting drugs

[MODERATE - Citation Gap]
- Flag ID: CG-1
- Issue: Mechanism of LAG3 not supported by literature
- Location: Subtask 5, Mechanistic hypothesis
- Required Fix: Search literature and cite LAG3 mechanism papers
```

### Phase 4: PI Final Synthesis with Red Flag Resolution

```
## Executive Summary
Based on integrated analysis of T-cell exhaustion signatures and drug-gene
networks, we identify dual checkpoint blockade (Nivolumab + Ipilimumab) as
the top drug repositioning candidate...

## Key Findings

(A) T-cell Exhaustion Signature Analysis:
- 200 differentially expressed genes identified
- Core exhaustion markers: PD-1, CTLA-4, LAG3, TIM3, TIGIT
- Pathway enrichment: TCR signaling, apoptosis, energy metabolism

(B) Candidate Discovery:
- 45 drug candidates identified from DrugBank/BindingDB
- Network analysis: 87% signature coverage
- Top 5 candidates ranked by mechanism and evidence

(C) Drug Selection & Mechanism:
- Selected: Nivolumab (PD-1) + Ipilimumab (CTLA-4)
- Mechanism: Dual checkpoint blockade reverses exhaustion via...
- Evidence: 15 clinical trials (PMIDs listed)

## Red Flag Resolution

**MA-1: CTLA-4 Pathway Analysis**
RESOLVED: Queried DrugBank for "CTLA-4" and identified Ipilimumab as top
candidate. Added to drug combination recommendation. Network analysis updated
to show dual blockade targets 95% of exhaustion signature.

**CG-1: LAG3 Mechanism Citation**
RESOLVED: Searched literature and found "LAG3 inhibits T-cell activation via
MHC-II binding" (PMID: 12345678). Added citation and mechanistic detail to
Section 3.2.

## References
- PMID: 12345678 (LAG3 mechanism)
- PMID: 87654321 (Nivolumab trial)
- DrugBank: DB00078 (Ipilimumab)
- File: differential_expression.csv
```

---

## Comparison: Combined vs Subtask-Centric

| Aspect | --combined (Old) | --subtask-centric (New) |
|--------|-----------------|------------------------|
| **Approach** | Consensus across models | Sequential specialist collaboration |
| **Structure** | Parallel brainstorming | Structured research plan |
| **Data Flow** | Limited sharing | Full context passing |
| **File Usage** | May ignore generated files | MUST read previous files |
| **Quality** | Consensus voting | Red Flag enforcement |
| **Speed** | ~5-10 min | ~8-15 min (more thorough) |
| **Output** | Synthesized consensus | Structured with red flag resolution |

---

## Recommended Usage for Your Question

Your question has 3 clear parts (A, B, C), which makes it **PERFECT** for subtask-centric approach:

**Recommended command:**
```bash
python -m src.cli_updated \
    --question "$(cat your_question.txt)" \
    --subtask-centric \
    --team-size 3 \
    --rounds 1 \
    --verbose \
    --output results/drug_repositioning_subtask.md
```

**Why this is better for your question:**
1. **Part A (Exhaustion Signature)** → Subtask 1-2: Literature + Data Analysis
2. **Part B (Candidate Discovery)** → Subtask 3-4: Database queries + Network analysis
3. **Part C (Selection + Mechanism)** → Subtask 5-6: Validation + Hypothesis

Each part builds on the previous, which is exactly what subtask-centric excels at.

---

## Side-by-Side Comparison

Want to compare both approaches?

```bash
python -m src.cli_updated \
    --question "$(cat your_question.txt)" \
    --compare-vl \
    --team-size 3 \
    --verbose
```

This will:
1. Run original Virtual Lab (parallel)
2. Run subtask-centric Virtual Lab (sequential)
3. Save both outputs for comparison
4. Show differences in approach and results

---

## Expected Runtime

For your complex 3-part question:

- **--combined**: ~8-12 minutes (parallel consensus)
- **--subtask-centric**: ~12-20 minutes (deeper analysis)
- **--compare-vl**: ~20-30 minutes (runs both)

**Trade-off:** 50% longer runtime for 2-3x deeper analysis and better quality.

---

## Integration into Existing Workflow

### Minimal Changes
Just add refactored files and use new CLI:

```bash
# 1. Files are already created in src/agent/
ls src/agent/*_refactored.py

# 2. Use new CLI
python -m src.cli_updated --subtask-centric ...
```

### Replace Default
If you want to make subtask-centric the default Virtual Lab:

**Edit `src/cli.py` line 15:**
```python
# OLD:
from src.agent.meeting import run_virtual_lab

# NEW:
from src.agent.meeting_refactored import run_virtual_lab
```

Now `--virtual-lab` will use subtask-centric by default!

---

## Troubleshooting

### Issue: "No module named 'meeting_refactored'"

**Solution:**
```bash
# Verify files exist
ls src/agent/meeting_refactored.py
ls src/agent/agent_refactored.py
ls src/agent/team_manager_refactored.py

# If missing, they're in the root, move them:
mv meeting_refactored.py src/agent/
mv agent_refactored.py src/agent/
mv team_manager_refactored.py src/agent/
```

### Issue: API key errors

**Solution:**
Ensure `.env` has:
```
OPENROUTER_API_KEY=your-key-here
OPENROUTER_KEY=your-key-here  # Some models need this variant
```

### Issue: Too slow

**Optimize:**
```bash
# Reduce team size
--team-size 2

# Use faster model
--model "anthropic/claude-3-5-haiku"

# Reduce rounds (subtask-centric works well with 1)
--rounds 1
```

---

## Next Steps

1. **Test with your question:**
   ```bash
   python -m src.cli_updated --subtask-centric --question "..." --verbose
   ```

2. **Compare approaches:**
   ```bash
   python -m src.cli_updated --compare-vl --question "..." --verbose
   ```

3. **Integrate into workflow:**
   - Use `--subtask-centric` for complex multi-part questions
   - Use `--combined` for simpler questions needing consensus
   - Use `--virtual-lab` (old) if you prefer speed over depth

4. **Monitor quality:**
   - Check if red flags are addressed in final answer
   - Verify specialists are reading previous files
   - Look for sub-meetings in verbose output

The subtask-centric approach will give you **deeper, more rigorous** analysis of your drug repositioning question with **built-in quality checks** via the Red Flag system.
