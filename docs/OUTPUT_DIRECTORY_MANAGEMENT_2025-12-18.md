# Output Directory Management System
*Date: 2025-12-18*

## Overview

The output directory management system organizes all generated files into question-specific/run-specific directories instead of cluttering the current working directory (cwd).

**Problem it solves:**
- Before: All outputs (answer files, CSV files, plots) saved to cwd, causing clutter
- After: Each run gets its own organized directory under `outputs/`

---

## Directory Structure

```
outputs/
├── 20251218_140532_virtual-lab_abc123de/
│   ├── QUESTION.txt                    # The research question + metadata
│   ├── answer.md                       # Final answer
│   ├── drug_ranking.csv                # Agent-generated analysis files
│   ├── bindingdb_matches.csv
│   ├── exhaustion_heatmap.png
│   └── network_analysis.csv
├── 20251218_151245_single-agent_def456ab/
│   ├── QUESTION.txt
│   ├── answer.md
│   └── results.csv
└── 20251218_162033_combined_9876fedc/
    ├── QUESTION.txt
    ├── answer.md
    └── ...
```

**Directory naming format:**
```
outputs/{YYYYMMDD}_{HHMMSS}_{mode}_{question_hash}/
```

- `YYYYMMDD_HHMMSS`: Timestamp when run started
- `mode`: Execution mode (virtual-lab, single-agent, combined, etc.)
- `question_hash`: First 8 characters of MD5 hash of question (for uniqueness)

---

## What Changed

### 1. New Module: `src/utils/output_manager.py`

**Purpose:** Central management of output directories

**Key components:**
- `OutputManager` class: Creates and tracks run directories
- `get_output_manager()`: Get global manager instance
- `run_context()`: Context manager for runs (optional)

**Example usage:**
```python
from src.utils.output_manager import get_output_manager

# Create run directory
output_mgr = get_output_manager()
run_dir = output_mgr.create_run_directory(
    question="What is CRISPR?",
    mode="single-agent"
)
# Returns: outputs/20251218_140532_single-agent_abc123de/

# Get current run directory
current_dir = output_mgr.get_current_run_dir()

# Get path for a specific output file
output_path = output_mgr.get_output_path("results.csv")
# Returns: outputs/20251218_140532_single-agent_abc123de/results.csv
```

---

### 2. Updated: `src/tools/implementations.py`

**execute_python tool changes:**

1. **Injects `OUTPUT_DIR` variable** into Python execution environment
2. Agents can use `OUTPUT_DIR` to save files in the right location

**Before:**
```python
# Agent code (saved to cwd)
df.to_csv('drug_ranking.csv')
```

**After:**
```python
# Agent code (saved to run directory)
df.to_csv(f'{OUTPUT_DIR}/drug_ranking.csv')

# Reading files saved earlier
df = pd.read_csv(f'{OUTPUT_DIR}/drug_ranking.csv')
```

**Implementation:**
```python
def execute(self, code: str, timeout: int = 30):
    from src.utils.output_manager import get_current_run_dir

    # Inject OUTPUT_DIR
    run_dir = get_current_run_dir()
    if run_dir:
        self.globals_dict['OUTPUT_DIR'] = str(run_dir)
    else:
        self.globals_dict['OUTPUT_DIR'] = os.getcwd()  # Fallback

    exec(code, self.globals_dict, self.locals_dict)
```

**Tool description updated:**
```json
{
  "name": "execute_python",
  "description": "Execute Python code to analyze data, perform calculations, or create visualizations. IMPORTANT: When saving output files (CSV, plots, etc.), prefix paths with OUTPUT_DIR to organize files properly (e.g., f'{OUTPUT_DIR}/results.csv'). OUTPUT_DIR is automatically available in your code.",
  ...
}
```

---

### 3. Updated: `src/cli.py`

**Changes:**
- Imports `get_output_manager()`
- Creates run directory before each execution
- Prints output directory path for user visibility
- `save_answer_to_file()` uses output manager

**Example (--virtual-lab mode):**
```python
elif args.virtual_lab:
    print("VIRTUAL LAB MODE")

    # Create run-specific output directory
    output_mgr = get_output_manager()
    run_dir = output_mgr.create_run_directory(args.question, mode="virtual-lab")
    print(f"Output directory: {run_dir}\n")  # User sees this

    final_answer = run_virtual_lab(...)

    # Automatically saved to run_dir/answer.md
    output_file = save_answer_to_file(final_answer, args.question, args.output, mode="virtual-lab")
```

**All modes updated:**
- `--combined`
- `--langgraph`
- `--virtual-lab`
- `--with-critic`
- Single agent mode
- Interactive mode

---

### 4. Updated: Agent System Prompts

**Files updated:**
- `src/agent/agent.py` - `get_system_prompt()`
- `src/agent/agent_refactored.py` - `get_base_system_prompt()`

**New instructions added:**
```
3. **Data Exploration**: When analyzing data:
   - ALWAYS use find_files() FIRST to discover available data files
   - When reading INPUT files: the input directory is pre-configured, so use ONLY the filename (e.g., 'file.csv', NOT 'data/Q5/file.csv')
   - When SAVING OUTPUT files (CSV, plots, etc.): ALWAYS prefix paths with OUTPUT_DIR (e.g., f'{OUTPUT_DIR}/results.csv')
     - OUTPUT_DIR is automatically available in execute_python code
     - This organizes all outputs into a run-specific directory
     - To read files you saved earlier: use f'{OUTPUT_DIR}/filename.csv'
   ...
```

**Why this matters:**
- Agents are explicitly instructed to use OUTPUT_DIR
- Clear distinction between INPUT files (from data dir) and OUTPUT files (to run dir)
- Agents can read files they created earlier in the same run

---

## Usage Examples

### Example 1: Running with Virtual Lab

```bash
python -m src.cli \
    --question "Predicting Drug Repositioning Candidates..." \
    --virtual-lab \
    --rounds 2 \
    --team-size 3 \
    --verbose
```

**Output:**
```
============================================================
VIRTUAL LAB MODE
============================================================
Question: Predicting Drug Repositioning Candidates...
Configuration: 2 rounds, max 3 specialists
============================================================
Output directory: /data/galaxy4/user/j2ho/projects/coscientist/outputs/20251218_140532_virtual-lab_abc123de

[PI]: Assembling team...
[Bioinformatician]: Analyzing gene signatures...
  Tool: execute_python
  Code:
    import pandas as pd
    # Save to OUTPUT_DIR
    df.to_csv(f'{OUTPUT_DIR}/gene_signature.csv')

[Drug Discovery Specialist]: Reading previous analysis...
  Tool: execute_python
  Code:
    df = pd.read_csv(f'{OUTPUT_DIR}/gene_signature.csv')
    # Analyze and save results
    results.to_csv(f'{OUTPUT_DIR}/drug_candidates.csv')

...

✓ Answer saved to: /data/galaxy4/user/j2ho/projects/coscientist/outputs/20251218_140532_virtual-lab_abc123de/answer.md
```

**Result:**
```
outputs/20251218_140532_virtual-lab_abc123de/
├── QUESTION.txt
├── answer.md
├── gene_signature.csv           # Created by Bioinformatician
├── drug_candidates.csv          # Created by Drug Discovery Specialist
├── network_analysis.csv
└── final_ranking.csv
```

---

### Example 2: Running with Custom Output Path

```bash
python -m src.cli \
    --question "What is CRISPR?" \
    --output custom_results/my_answer.md
```

**Behavior:**
- Run directory still created: `outputs/20251218_150123_single-agent_def456ab/`
- Answer saved to custom path: `custom_results/my_answer.md`
- But agent-generated files (CSV, etc.) still go to run directory

**Why?** Custom `--output` overrides answer file location, but doesn't affect OUTPUT_DIR.

---

### Example 3: Programmatic Usage

```python
from src.agent.agent import create_agent
from src.utils.output_manager import get_output_manager

# Create run directory
output_mgr = get_output_manager()
run_dir = output_mgr.create_run_directory(
    question="Analyze T-cell exhaustion markers",
    mode="custom-script"
)

print(f"Outputs will be saved to: {run_dir}")

# Run agent
agent = create_agent()
answer = agent.run("Analyze T-cell exhaustion markers", verbose=True)

# All agent-generated files are now in run_dir
print(f"Results in: {run_dir}")
```

---

## Key Benefits

### 1. Clean Working Directory
**Before:**
```
coscientist/
├── answer_20251211_173028.md
├── answer_20251211_173609.md
├── answer_20251216_131051.md
├── drug_ranking.csv
├── bindingdb_matches.csv
├── exhaustion_meta_signature.csv
├── network_proximity_results.csv
├── ...
└── (50+ files cluttering root)
```

**After:**
```
coscientist/
├── outputs/
│   ├── 20251211_173028_virtual-lab_abc123/  # All files from run 1
│   ├── 20251211_173609_single-agent_def456/ # All files from run 2
│   └── 20251216_131051_combined_789abc/     # All files from run 3
├── src/
├── data/
└── README.md
```

### 2. Easy Run Tracking
- Each directory contains `QUESTION.txt` with the research question
- Timestamp in directory name shows when run occurred
- Mode in directory name shows which workflow was used
- Question hash ensures uniqueness for similar questions

### 3. Reproducibility
- All outputs from a single run are in one directory
- Easy to archive entire run: `tar -czf run_abc123.tar.gz outputs/20251218_140532_virtual-lab_abc123de/`
- Easy to share results with collaborators

### 4. No Path Confusion
- **Input data files:** Still accessed from configured data directory
  - Example: `find_files()` → `"genes.csv"` → reads from `data/Q5/genes.csv`
- **Output files:** Automatically saved to run directory
  - Example: `df.to_csv(f'{OUTPUT_DIR}/results.csv')` → saves to `outputs/.../results.csv`

### 5. Multi-Run Workflows
- Can run multiple questions in sequence without file conflicts
- Each gets its own directory
- No overwriting of previous results

---

## Input vs Output Paths - Detailed Guide

### Input Files (Reading Data)

**Source:** Configured data directory (`--data-dir`, `--input-dir`)

**How to access:**
```python
# 1. Find files
find_files()  # Returns: ['genes.csv', 'expression_data.txt']

# 2. Read file (use basename only)
read_file('genes.csv')  # Reads from configured input directory

# 3. In execute_python
df = pd.read_csv('genes.csv')  # No prefix needed - uses input directory
```

**Important:** Don't change this behavior - input files stay where they are.

---

### Output Files (Saving Results)

**Destination:** Run-specific output directory (`outputs/YYYYMMDD_HHMMSS_mode_hash/`)

**How to save:**
```python
# CORRECT - Use OUTPUT_DIR prefix
df.to_csv(f'{OUTPUT_DIR}/results.csv')
plt.savefig(f'{OUTPUT_DIR}/plot.png')
with open(f'{OUTPUT_DIR}/summary.txt', 'w') as f:
    f.write(summary)

# WRONG - Don't use absolute paths or cwd
df.to_csv('results.csv')  # Goes to cwd (clutters root directory)
df.to_csv('/tmp/results.csv')  # Goes to /tmp (lost after run)
```

**Reading your own output files later:**
```python
# First, you saved it
df.to_csv(f'{OUTPUT_DIR}/intermediate_results.csv')

# Later in the same run, read it back
df = pd.read_csv(f'{OUTPUT_DIR}/intermediate_results.csv')
```

---

## Advanced Usage

### Custom Output Directory Name

```python
from src.utils.output_manager import get_output_manager

output_mgr = get_output_manager()
run_dir = output_mgr.create_run_directory(
    question="What is CRISPR?",
    mode="single-agent",
    custom_name="crispr_analysis_final"  # Custom name instead of timestamp
)
# Creates: outputs/crispr_analysis_final/
```

### Subdirectories within Run Directory

```python
from src.utils.output_manager import get_output_manager

output_mgr = get_output_manager()

# Save to subdirectory
plot_path = output_mgr.get_output_path("heatmap.png", subdir="figures")
# Returns: outputs/20251218_140532_virtual-lab_abc123/figures/heatmap.png

# In execute_python
import os
os.makedirs(f'{OUTPUT_DIR}/figures', exist_ok=True)
plt.savefig(f'{OUTPUT_DIR}/figures/heatmap.png')
```

### Accessing Run Directory from Anywhere

```python
from src.utils.output_manager import get_current_run_dir

# Get current run directory
run_dir = get_current_run_dir()

if run_dir:
    print(f"Current run directory: {run_dir}")
    # Do something with run_dir
else:
    print("No run directory set")
```

---

## Migration Guide

### For Existing Scripts

**No changes required!** Old behavior:
- If you don't use `OUTPUT_DIR`, files still go to cwd
- This is the fallback when no run directory is set

**To adopt new system:**
```python
# OLD
df.to_csv('results.csv')

# NEW
df.to_csv(f'{OUTPUT_DIR}/results.csv')
```

### For CLI Users

**No changes required!** The CLI automatically:
1. Creates run directory
2. Sets OUTPUT_DIR
3. Saves answer file to run directory
4. Prints directory path so you know where files are

**Optional:** Use `--output` to customize answer file location
```bash
python -m src.cli --question "..." --output my_custom_path.md
```

---

## Troubleshooting

### Issue: Files still going to cwd

**Cause:** Agent code not using `OUTPUT_DIR`

**Check:**
```bash
grep -r "to_csv(" outputs/*/  # Search for CSV saves in old runs
```

**Fix:** Update agent prompt or code to use `OUTPUT_DIR`:
```python
# In execute_python
df.to_csv(f'{OUTPUT_DIR}/results.csv')  # Not: df.to_csv('results.csv')
```

---

### Issue: Can't find OUTPUT_DIR variable

**Cause:** Not using `execute_python` tool, or running outside of CLI

**Check:**
```python
from src.utils.output_manager import get_current_run_dir

run_dir = get_current_run_dir()
print(f"Run directory: {run_dir}")
```

**If None:** Create run directory first:
```python
from src.utils.output_manager import get_output_manager

output_mgr = get_output_manager()
run_dir = output_mgr.create_run_directory("Your question", mode="custom")
```

---

### Issue: Input data files not found

**Cause:** Confusing OUTPUT_DIR with input directory

**Fix:**
- **Input files:** Don't use OUTPUT_DIR, use basename only
  ```python
  df = pd.read_csv('genes.csv')  # Reads from input directory
  ```
- **Output files:** Use OUTPUT_DIR
  ```python
  df.to_csv(f'{OUTPUT_DIR}/results.csv')  # Saves to run directory
  ```

---

### Issue: Can't read files from previous runs

**Expected:** Each run is isolated with its own directory

**If you need cross-run access:**
```python
# In execute_python
import pandas as pd

# Read from specific previous run
previous_run = 'outputs/20251218_140532_virtual-lab_abc123de'
df = pd.read_csv(f'{previous_run}/results.csv')

# Compare with current run
current_df = pd.read_csv('genes.csv')  # Input file
merged = pd.merge(df, current_df, on='gene_id')

# Save comparison to current run
merged.to_csv(f'{OUTPUT_DIR}/comparison.csv')
```

---

## File Organization Best Practices

### 1. Use Descriptive Filenames
```python
# GOOD
df.to_csv(f'{OUTPUT_DIR}/drug_candidates_filtered_by_affinity.csv')
df.to_csv(f'{OUTPUT_DIR}/exhaustion_signature_top200_genes.csv')

# AVOID
df.to_csv(f'{OUTPUT_DIR}/output.csv')
df.to_csv(f'{OUTPUT_DIR}/data.csv')
```

### 2. Organize with Subdirectories
```python
# Analysis results
df.to_csv(f'{OUTPUT_DIR}/analysis/drug_ranking.csv')

# Figures
plt.savefig(f'{OUTPUT_DIR}/figures/heatmap.png')

# Raw intermediate data
raw_data.to_csv(f'{OUTPUT_DIR}/intermediate/raw_scores.csv')

# Final deliverables
final.to_csv(f'{OUTPUT_DIR}/final_results.csv')
```

### 3. Include Metadata Files
```python
# Save metadata about the analysis
metadata = {
    "date": datetime.now().isoformat(),
    "parameters": {"threshold": 0.05, "max_genes": 200},
    "input_files": ["genes.csv", "expression_data.csv"],
    "output_files": ["drug_ranking.csv", "heatmap.png"]
}

import json
with open(f'{OUTPUT_DIR}/metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)
```

---

## Summary

✅ **All outputs organized** - No more cluttered cwd
✅ **Automatic directory creation** - CLI handles everything
✅ **Agent-aware** - System prompts updated to use OUTPUT_DIR
✅ **Backward compatible** - Old scripts still work (fallback to cwd)
✅ **Easy tracking** - Each run has timestamp + question hash
✅ **Input/output separation** - Clear distinction between data and results
✅ **Reproducible** - All files from one run in one directory

**Quick start:**
1. Run your CLI command as usual (no changes needed)
2. CLI prints output directory path
3. All files (answer, CSVs, plots) saved to that directory
4. Find results in `outputs/YYYYMMDD_HHMMSS_mode_hash/`

**For agents:**
- Read input: `pd.read_csv('genes.csv')`
- Save output: `df.to_csv(f'{OUTPUT_DIR}/results.csv')`
- Read your output later: `pd.read_csv(f'{OUTPUT_DIR}/results.csv')`

That's it! The system handles the rest.
