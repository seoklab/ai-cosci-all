#!/bin/bash
# Submit Q5 Final Run
# Usage:
#   ./submit_Q5_final.sh                    # Uses default: final_Q5
#   ./submit_Q5_final.sh final_Q5_test1     # Custom output directory
#   ./submit_Q5_final.sh final_Q5_round3    # Another custom directory

set -e

PROJECT_DIR="/data/galaxy4/user/j2ho/projects/ai-cosci-all"
cd "$PROJECT_DIR"

# Output directory: use first argument if provided, otherwise default
OUTPUT_DIR_NAME="${1:-final_Q5}"

echo "========================================"
echo "Q5 Final Run Submission"
echo "========================================"
echo "Output directory: ${OUTPUT_DIR_NAME}"
echo ""

# ============================================================================
# Step 1: Check required files
# ============================================================================

echo "Step 1: Checking required files..."

QUESTION_FILE="final_questions/Q5_question.txt"
SLURM_SCRIPT="scripts/run_Q5_final.sh"

if [ ! -f "$QUESTION_FILE" ]; then
    echo "  ERROR: Question file not found: $QUESTION_FILE"
    exit 1
fi

if [ ! -f "$SLURM_SCRIPT" ]; then
    echo "  ERROR: SLURM script not found: $SLURM_SCRIPT"
    exit 1
fi

echo "  ✓ Found: $QUESTION_FILE"
echo "  ✓ Found: $SLURM_SCRIPT"
echo ""

# ============================================================================
# Step 2: Create necessary directories
# ============================================================================

echo "Step 2: Setting up directories..."
mkdir -p logs final_Q5 scripts
echo "  ✓ Created: logs/"
echo "  ✓ Created: final_Q5/"
echo "  ✓ Created: scripts/"
echo ""

# ============================================================================
# Step 3: Display question preview
# ============================================================================

echo "Step 3: Question preview..."
echo "  Using: $QUESTION_FILE"
echo "  Preview (first 300 chars):"
echo "  ---"
head -c 300 "$QUESTION_FILE"
echo ""
echo "  ..."
echo "  ---"
echo ""

# ============================================================================
# Step 4: Display run configuration
# ============================================================================

echo "========================================"
echo "RUN CONFIGURATION"
echo "========================================"
echo "Mode: subtask-centric"
echo "Rounds: 2"
echo "Team size: 3"
echo "Verbose: enabled"
echo ""
echo "Output directory: ${OUTPUT_DIR_NAME}/"
echo "Output file: ${OUTPUT_DIR_NAME}/answer_Q5_final.md"
echo "Log file: logs/detailed_${OUTPUT_DIR_NAME}.log"
echo ""

# ============================================================================
# Step 5: Show estimates
# ============================================================================

echo "Estimates:"
echo "  Expected cost: ~\$2-3"
echo "  Expected time: ~2.5-3.5 hours"
echo "  Time limit: 6 hours"
echo ""

# ============================================================================
# Step 6: Submit job
# ============================================================================

echo "========================================"
read -p "Submit Q5 final run to SLURM? (y/n) " -n 1 -r
echo
echo "========================================"

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Make script executable
    chmod +x "$SLURM_SCRIPT"

    # Submit job with output directory parameter
    JOB_ID=$(sbatch "$SLURM_SCRIPT" "$OUTPUT_DIR_NAME" | grep -oP '\d+$')

    echo ""
    echo "✓ Job submitted!"
    echo "  Job ID: $JOB_ID"
    echo "  Output directory: ${OUTPUT_DIR_NAME}"
    echo ""
    echo "Monitor progress:"
    echo "  squeue -u $USER"
    echo "  watch -n 10 'squeue -u $USER'"
    echo ""
    echo "View logs (live):"
    echo "  tail -f logs/Q5_final_${JOB_ID}.out"
    echo "  tail -f logs/detailed_${OUTPUT_DIR_NAME}.log"
    echo ""
    echo "After completion, view results:"
    echo "  cat ${OUTPUT_DIR_NAME}/answer_Q5_final.md"
    echo "  cat logs/timing_${OUTPUT_DIR_NAME}.csv"
    echo ""
else
    echo ""
    echo "Cancelled. To submit manually:"
    echo "  cd $PROJECT_DIR"
    echo "  sbatch scripts/run_Q5_final.sh $OUTPUT_DIR_NAME"
    echo ""
fi
