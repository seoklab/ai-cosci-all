#!/bin/bash
# Submit optimization tests with parameter sweep
# Usage: ./submit_tests.sh [question_file]
#   question_file: Path to question text file (default: question.txt)

set -e

PROJECT_DIR="/data/galaxy4/user/j2ho/projects/ai-cosci-all"
cd "$PROJECT_DIR"

# Get question file from argument or use default
QUESTION_FILE="${1:-question.txt}"

echo "========================================"
echo "CoScientist Optimization Test Suite"
echo "========================================"
echo ""

# ============================================================================
# Step 1: Generate configuration file
# ============================================================================

echo "Step 1: Generating configurations..."
bash /data/galaxy4/user/j2ho/projects/ai-cosci-all/opt_test/generate_configs.sh configs/optimization_jobs.txt

NUM_CONFIGS=$(wc -l < configs/optimization_jobs.txt)
echo ""

# ============================================================================
# Step 2: Create necessary directories
# ============================================================================

echo "Step 2: Setting up directories..."
mkdir -p logs optimization_results configs scripts
echo "  ✓ Created: logs/"
echo "  ✓ Created: optimization_results/"
echo "  ✓ Created: configs/"
echo ""

# ============================================================================
# Step 3: Copy SLURM script
# ============================================================================

echo "Step 3: Copying SLURM script..."
cp /data/galaxy4/user/j2ho/projects/ai-cosci-all/opt_test/slurm_optimize.sh scripts/slurm_optimize.sh
chmod +x scripts/slurm_optimize.sh
echo "  ✓ Copied to: scripts/slurm_optimize.sh"
echo ""

# ============================================================================
# Step 4: Check question file
# ============================================================================

echo "Step 4: Checking question file..."
echo "  Using: $QUESTION_FILE"
if [ ! -f "$QUESTION_FILE" ]; then
    echo "  WARNING: $QUESTION_FILE not found!"
    echo "  Please create it before submitting jobs."
    echo ""
    read -p "Create question.txt now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cat > "$QUESTION_FILE" << 'EOF'
Predicting Drug Repositioning Candidates to Inhibit T-Cell Exhaustion

T-cell exhaustion is a phenomenon in which T cells, repeatedly stimulated under chronic infection or within the tumor microenvironment, lose their functional capacity. It is a major cause of reduced responsiveness to immunotherapy and treatment failure. Discovering drugs or drug combinations that can reverse exhaustion is considered a key challenge in advancing immunotherapy.

The goal of this problem is to integrate publicly available drug–gene/transcriptome databases to predict drug candidates capable of reversing a T-cell exhaustion gene signature, and to provide supporting rationale.

below are the main three questions that should ultimately satisfy the requirements. answer each in detail.
(A) Analysis of the T-cell Exhaustion Signature

(B) Candidate Discovery Using Drug–Gene Network Analysis. Here the candidate is a drug candidate that can reverse exhaustion.

(C) Drug Candidate Selection (selecting from candidates found by (B)?) and Mechanistic Hypothesis Generation.
EOF
        echo "  ✓ Created $QUESTION_FILE"
    else
        echo "  Cancelled. Create $QUESTION_FILE manually before submitting."
        exit 1
    fi
else
    echo "  ✓ Found: $QUESTION_FILE"
    echo "  Preview (first 100 chars):"
    head -c 100 "$QUESTION_FILE"
    echo "..."
fi

# Pass question file path to SLURM jobs via environment variable
export QUESTION_FILE_PATH="$QUESTION_FILE"
echo ""

# ============================================================================
# Step 5: Initialize timing summary
# ============================================================================

echo "Step 5: Initializing timing summary..."
echo "config,mode,rounds,team_size,max_iter,elapsed_sec,hours,minutes,seconds,exit_code,start_time,end_time" > logs/timing_summary.csv
echo "  ✓ Created: logs/timing_summary.csv"
echo ""

# ============================================================================
# Step 6: Show test plan
# ============================================================================

echo "========================================"
echo "TEST PLAN"
echo "========================================"
echo "Number of configurations: $NUM_CONFIGS"
echo "SLURM array size: 1-${NUM_CONFIGS}"
echo ""
echo "Configurations to test:"
cat configs/optimization_jobs.txt | nl -v 1 -w 2 -s ". "
echo ""

# Estimate costs
echo "Cost estimates (per configuration):"
echo "  rounds=2, team=2, iter=15: ~\$0.90"
echo "  rounds=2, team=2, iter=30: ~\$1.50"
echo "  rounds=2, team=3, iter=15: ~\$1.20"
echo "  rounds=2, team=3, iter=30: ~\$2.00"
echo ""
echo "Total estimated cost: ~\$5-6"
echo "Your remaining credits: \$580.80 ✓"
echo ""

echo "Time estimates (per configuration):"
echo "  rounds=2, team=2, iter=15: ~90-120 min"
echo "  rounds=2, team=2, iter=30: ~120-150 min"
echo "  rounds=2, team=3, iter=15: ~120-150 min"
echo "  rounds=2, team=3, iter=30: ~150-200 min"
echo ""
echo "Jobs will run IN PARALLEL on different nodes!"
echo "Expected total wall time: ~150-200 min (2.5-3.5 hours)"
echo ""

# ============================================================================
# Step 7: Submit jobs
# ============================================================================

echo "========================================"
read -p "Submit ${NUM_CONFIGS} jobs to SLURM? (y/n) " -n 1 -r
echo
echo "========================================"

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Update SBATCH array directive in script
    sed -i "s/#SBATCH --array=.*/#SBATCH --array=1-${NUM_CONFIGS}/" scripts/slurm_optimize.sh

    # Submit job array with question file path
    JOB_ID=$(sbatch --export=ALL,QUESTION_FILE_PATH="$QUESTION_FILE" scripts/slurm_optimize.sh | grep -oP '\d+$')

    echo ""
    echo "✓ Jobs submitted!"
    echo "  Job ID: $JOB_ID"
    echo "  Array size: 1-${NUM_CONFIGS}"
    echo ""
    echo "Monitor progress:"
    echo "  squeue -u $USER"
    echo "  watch -n 10 'squeue -u $USER'"
    echo ""
    echo "View logs (live):"
    echo "  tail -f logs/opt_${JOB_ID}_1.out"
    echo "  tail -f logs/detailed_r2_t2_i15.log"
    echo ""
    echo "After completion, view results:"
    echo "  cat logs/timing_summary.csv"
    echo "  ls -lh optimization_results/"
    echo "  diff optimization_results/answer_r2_t2_i15.md optimization_results/answer_r2_t3_i30.md"
    echo ""
else
    echo ""
    echo "Cancelled. To submit manually:"
    echo "  cd $PROJECT_DIR"
    echo "  sbatch scripts/slurm_optimize.sh"
    echo ""
fi
