# Quick Start: Output Directory Management
*Date: 2025-12-18*

## What Changed?

All generated files now go to organized run-specific directories instead of cluttering your working directory.

**Before:**
```
coscientist/
├── answer_20251211_173028.md
├── answer_20251216_131051.md
├── drug_ranking.csv
├── bindingdb_matches.csv
└── ... (50+ files)
```

**After:**
```
coscientist/
└── outputs/
    ├── 20251218_140532_virtual-lab_abc123/
    │   ├── QUESTION.txt
    │   ├── answer.md
    │   ├── drug_ranking.csv
    │   └── bindingdb_matches.csv
    └── 20251218_151245_single-agent_def456/
        ├── QUESTION.txt
        ├── answer.md
        └── results.csv
```

---

## Quick Test

Run the test script to verify everything works:

```bash
cd /data/galaxy4/user/j2ho/projects/coscientist
python test_output_manager.py
```

**Expected output:**
```
============================================================
Testing Output Directory Management System
============================================================

[Test 1] Importing output manager...
✓ Import successful

[Test 2] Creating output manager instance...
✓ Output manager created: <src.utils.output_manager.OutputManager object at 0x...>

[Test 3] Creating run directory...
✓ Run directory created: /data/galaxy4/user/j2ho/projects/coscientist/outputs/20251218_140532_test_abc123de

...

✅ All tests passed!
```

If all tests pass, you're good to go!

---

## Usage (No Changes Needed!)

Just run your CLI commands as usual:

```bash
# Virtual Lab mode
python -m src.cli \
    --question "Predicting Drug Repositioning Candidates..." \
    --virtual-lab \
    --rounds 2 \
    --team-size 3 \
    --verbose
```

**What you'll see:**
```
============================================================
VIRTUAL LAB MODE
============================================================
Question: Predicting Drug Repositioning Candidates...
Configuration: 2 rounds, max 3 specialists
============================================================
Output directory: /data/galaxy4/user/j2ho/projects/coscientist/outputs/20251218_140532_virtual-lab_abc123de

[PI]: Assembling research team...
...
```

**All files will be saved to that output directory!**

---

## Where Are My Files?

**Answer files:**
- Location: `outputs/YYYYMMDD_HHMMSS_mode_hash/answer.md`
- The CLI prints the full path when done

**Agent-generated files (CSV, plots, etc.):**
- Location: `outputs/YYYYMMDD_HHMMSS_mode_hash/`
- Agents automatically save there using `OUTPUT_DIR` variable

**To list all runs:**
```bash
ls -lt outputs/
```

**To find a specific run:**
```bash
# By date
ls outputs/20251218_*

# By mode
ls outputs/*_virtual-lab_*

# View question for a run
cat outputs/20251218_140532_virtual-lab_abc123de/QUESTION.txt
```

---

## Cleanup Old Files

Your cwd still has old files from before this change. You can clean them up:

```bash
# List old answer files
ls -lh answer_*.md

# List old CSV files (careful!)
ls -lh *.csv

# Move old files to archive (recommended)
mkdir -p archive_before_output_dirs
mv answer_*.md archive_before_output_dirs/
mv *.csv archive_before_output_dirs/  # Only if they're from old runs!

# Or delete them (if you're sure)
rm answer_*.md
```

**⚠️ Warning:** Be careful with `*.csv` - make sure they're old outputs, not important data files!

---

## Advanced: Custom Output Location

If you want to save the answer file to a specific location:

```bash
python -m src.cli \
    --question "..." \
    --output results/my_custom_answer.md
```

**What happens:**
- Answer file: `results/my_custom_answer.md` (your custom path)
- Agent-generated files: `outputs/20251218_140532_single-agent_abc123/` (still organized)
- QUESTION.txt: `outputs/20251218_140532_single-agent_abc123/QUESTION.txt`

---

## For Your Existing Question

Your original command:
```bash
python -m src.cli \
    --question "Predicting Drug Repositioning Candidates..." \
    --combined \
    --rounds 2 \
    --team-size 3 \
    --verbose
```

**Now it will:**
1. Create: `outputs/20251218_HHMMSS_combined_abc123/`
2. Save QUESTION.txt there
3. All agent-generated files go there
4. Answer saved as: `outputs/20251218_HHMMSS_combined_abc123/answer.md`

**No changes needed to your command!**

---

## Troubleshooting

### Files still in cwd?

**Check:**
1. Are you using the latest code?
   ```bash
   git status  # Should show modified files
   ```

2. Is OUTPUT_DIR being used?
   ```bash
   python test_output_manager.py  # Should pass all tests
   ```

3. Run with `--verbose` and look for OUTPUT_DIR in agent code:
   ```bash
   python -m src.cli --question "test" --verbose
   ```

---

### Can't find OUTPUT_DIR variable?

**This only happens in execute_python.** The variable is automatically injected by the system.

**Example agent code:**
```python
# Agent uses execute_python tool
execute_python(code="""
import pandas as pd

# OUTPUT_DIR is automatically available
df = pd.DataFrame({'a': [1, 2, 3]})
df.to_csv(f'{OUTPUT_DIR}/test.csv')

print('File saved!')
""")
```

---

### Input files not found?

**Remember:**
- **INPUT files** (data you're analyzing): Use basename only
  ```python
  df = pd.read_csv('genes.csv')  # Reads from configured input dir
  ```

- **OUTPUT files** (results you're creating): Use OUTPUT_DIR
  ```python
  df.to_csv(f'{OUTPUT_DIR}/results.csv')  # Saves to run dir
  ```

**Don't mix them up!**

---

## Summary

✅ **Zero config needed** - CLI handles everything
✅ **Clean working directory** - All outputs organized
✅ **Easy to find results** - Each run has its own directory
✅ **Backward compatible** - Old scripts still work

**That's it!** Just run your commands as usual and enjoy organized outputs.

For full details, see: `docs/OUTPUT_DIRECTORY_MANAGEMENT_2025-12-18.md`
