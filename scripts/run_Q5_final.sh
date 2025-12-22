#!/bin/bash
#SBATCH --job-name=Q5_final
#SBATCH -p gpu-micro.q
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH -o logs/Q5_final_%j.out
#SBATCH -e logs/Q5_final_%j.err
#SBATCH --time=06:00:00

# ============================================================================
# SLURM Job for Q5 Final Run
# Usage:
#   sbatch scripts/run_Q5_final.sh                    # Uses default: final_Q5
#   sbatch scripts/run_Q5_final.sh final_Q5_test1    # Custom output dir
#   sbatch scripts/run_Q5_final.sh final_Q5_round3   # Another custom dir
# ============================================================================

set -e
set -u

PROJECT_DIR="/data/galaxy4/user/j2ho/projects/ai-cosci-all"
QUESTION_FILE="${PROJECT_DIR}/final_questions/Q5_question.txt"

# Output directory: use first argument if provided, otherwise default
OUTPUT_DIR="${PROJECT_DIR}/${1:-final_Q5}"

LOG_DIR="${PROJECT_DIR}/logs"

cd "$PROJECT_DIR"

# Create directories
mkdir -p "$LOG_DIR" "$OUTPUT_DIR"

echo "========================================"
echo "Q5 FINAL RUN"
echo "========================================"
echo "Job ID: ${SLURM_JOB_ID}"
echo "Node: $(hostname)"
echo "Start time: $(date)"
echo "========================================"

# ============================================================================
# Configuration
# ============================================================================

MODE="subtask-centric"
ROUNDS=2
TEAM_SIZE=3
VERBOSE="--verbose"

echo "Configuration:"
echo "  Mode: $MODE"
echo "  Rounds: $ROUNDS"
echo "  Team size: $TEAM_SIZE"
echo "  Verbose: enabled"
echo "========================================"

# ============================================================================
# Check question file
# ============================================================================

if [ ! -f "$QUESTION_FILE" ]; then
    echo "ERROR: Question file not found: $QUESTION_FILE"
    exit 1
fi

QUESTION=$(cat "$QUESTION_FILE")
echo "Question (first 200 chars):"
echo "${QUESTION:0:200}..."
echo "========================================"

# ============================================================================
# Setup output files (use unique names based on output directory)
# ============================================================================

OUTPUT_BASENAME=$(basename "$OUTPUT_DIR")
OUTPUT_FILE="${OUTPUT_DIR}/answer_Q5_final.md"
DETAILED_LOG="${LOG_DIR}/detailed_${OUTPUT_BASENAME}.log"
TIMING_LOG="${LOG_DIR}/timing_${OUTPUT_BASENAME}.csv"

echo "Output files:"
echo "  Answer: $OUTPUT_FILE"
echo "  Detailed log: $DETAILED_LOG"
echo "  Timing: $TIMING_LOG"
echo "========================================"
echo ""

# ============================================================================
# Run with detailed logging
# ============================================================================

START_TIME=$(date +%s)
START_TIME_STR=$(date)

echo "Starting run at: $START_TIME_STR"
echo ""

# Run with timestamped logging
{
    echo "=== DETAILED LOG START ==="
    echo "Configuration: Q5 Final Run"
    echo "  Mode: $MODE"
    echo "  Rounds: $ROUNDS"
    echo "  Team size: $TEAM_SIZE"
    echo "Start: $START_TIME_STR"
    echo "=========================="
    echo ""

    python -m src.cli \
        --question "$QUESTION" \
        --subtask-centric \
        --rounds "$ROUNDS" \
        --team-size "$TEAM_SIZE" \
        --output "$OUTPUT_FILE" \
        --input-dir "${PROJECT_DIR}/data/Q5" \
        --verbose 2>&1

    EXIT_CODE=$?

    echo ""
    echo "=== DETAILED LOG END ==="
    echo "Exit code: $EXIT_CODE"
    exit $EXIT_CODE

} 2>&1 | while IFS= read -r line; do
    # Add timestamp to each line
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
done | tee "$DETAILED_LOG"

# Capture exit code from pipeline
FINAL_EXIT_CODE=${PIPESTATUS[0]}

# ============================================================================
# Calculate timing and save results
# ============================================================================

END_TIME=$(date +%s)
END_TIME_STR=$(date)
ELAPSED=$((END_TIME - START_TIME))

HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "========================================"
echo "RESULTS SUMMARY: ${OUTPUT_BASENAME}"
echo "========================================"
echo "Configuration:"
echo "  Mode: $MODE"
echo "  Rounds: $ROUNDS"
echo "  Team size: $TEAM_SIZE"
echo ""
echo "Timing:"
echo "  Start: $START_TIME_STR"
echo "  End: $END_TIME_STR"
echo "  Elapsed: ${HOURS}h ${MINUTES}m ${SECONDS}s (${ELAPSED}s total)"
echo ""
echo "Output:"
echo "  Directory: $OUTPUT_DIR"
echo "  Answer: $OUTPUT_FILE"
echo "  Detailed log: $DETAILED_LOG"
echo "  Exit code: $FINAL_EXIT_CODE"
echo "========================================"

# Save timing to CSV
{
    echo "config,mode,rounds,team_size,elapsed_sec,hours,minutes,seconds,exit_code,start_time,end_time"
    echo "${OUTPUT_BASENAME},${MODE},${ROUNDS},${TEAM_SIZE},${ELAPSED},${HOURS},${MINUTES},${SECONDS},${FINAL_EXIT_CODE},${START_TIME},${END_TIME}"
} > "$TIMING_LOG"

# Append to overall timing summary if it exists
if [ -f "${LOG_DIR}/timing_summary.csv" ]; then
    tail -n 1 "$TIMING_LOG" >> "${LOG_DIR}/timing_summary.csv"
fi

echo ""
echo "Job completed!"

exit $FINAL_EXIT_CODE
