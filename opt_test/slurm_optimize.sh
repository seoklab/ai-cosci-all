#!/bin/bash
#SBATCH --job-name=cosci_opt
#SBATCH -p gpu-micro.q
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --ntasks=1
#SBATCH --mem=16G
#SBATCH --array=1-4
#SBATCH -o logs/opt_%A_%a.out
#SBATCH -e logs/opt_%A_%a.err
#SBATCH --time=04:00:00

# ============================================================================
# SLURM Array Job for CoScientist Optimization Testing
# Reads parameters from configs/optimization_jobs.txt
# ============================================================================

set -e
set -u

PROJECT_DIR="/data/galaxy4/user/j2ho/projects/ai-cosci-all"
# Question file can be passed via environment variable or default to question.txt
QUESTION_FILE="${PROJECT_DIR}/${QUESTION_FILE_PATH:-question.txt}"
CONFIG_FILE="${PROJECT_DIR}/configs/optimization_jobs.txt"
LOG_DIR="${PROJECT_DIR}/logs"
OUTPUT_DIR="${PROJECT_DIR}/optimization_results"

cd "$PROJECT_DIR"

# Create directories
mkdir -p "$LOG_DIR" "$OUTPUT_DIR"

echo "========================================"
echo "SLURM ARRAY JOB"
echo "========================================"
echo "Job ID: ${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "Array Task ID: ${SLURM_ARRAY_TASK_ID}"
echo "Node: $(hostname)"
echo "Start time: $(date)"
echo "========================================"

# ============================================================================
# Read configuration for this array task
# ============================================================================

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    echo "Run generate_configs.sh first!"
    exit 1
fi

CONFIG_LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$CONFIG_FILE")

if [ -z "$CONFIG_LINE" ]; then
    echo "ERROR: No configuration for task ${SLURM_ARRAY_TASK_ID}"
    exit 1
fi

# Parse: MODE,ROUNDS,TEAM_SIZE,MAX_ITER,OUTPUT_NAME
IFS=',' read -r MODE ROUNDS TEAM_SIZE MAX_ITER OUTPUT_NAME <<< "$CONFIG_LINE"

echo "Configuration: $OUTPUT_NAME"
echo "  Mode: $MODE"
echo "  Rounds: $ROUNDS"
echo "  Team size: $TEAM_SIZE"
echo "  Max iterations: $MAX_ITER"
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
# Setup output files
# ============================================================================

OUTPUT_FILE="${OUTPUT_DIR}/answer_${OUTPUT_NAME}.md"
DETAILED_LOG="${LOG_DIR}/detailed_${OUTPUT_NAME}.log"
TIMING_LOG="${LOG_DIR}/timing_${OUTPUT_NAME}.csv"

echo "Output files:"
echo "  Answer: $OUTPUT_FILE"
echo "  Detailed log: $DETAILED_LOG"
echo "  Timing: $TIMING_LOG"
echo "========================================"
echo ""

# ============================================================================
# Run optimization test with detailed logging
# ============================================================================

START_TIME=$(date +%s)
START_TIME_STR=$(date)

echo "Starting test at: $START_TIME_STR"
echo ""

# Run with timestamped logging
{
    echo "=== DETAILED LOG START ==="
    echo "Configuration: $CONFIG_LINE"
    echo "Start: $START_TIME_STR"
    echo "=========================="
    echo ""

    if [ "$MODE" == "subtask-centric" ]; then
        python -m src.cli \
            --question "$QUESTION" \
            --subtask-centric \
            --rounds "$ROUNDS" \
            --team-size "$TEAM_SIZE" \
            --max-iterations "$MAX_ITER" \
            --output "$OUTPUT_FILE" \
            --verbose 2>&1
    elif [ "$MODE" == "virtual-lab" ]; then
        python -m src.cli \
            --question "$QUESTION" \
            --virtual-lab \
            --rounds "$ROUNDS" \
            --team-size "$TEAM_SIZE" \
            --max-iterations "$MAX_ITER" \
            --output "$OUTPUT_FILE" \
            --verbose 2>&1
    else
        echo "ERROR: Unknown mode: $MODE"
        exit 1
    fi

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
echo "RESULTS SUMMARY: $OUTPUT_NAME"
echo "========================================"
echo "Configuration:"
echo "  Mode: $MODE"
echo "  Rounds: $ROUNDS"
echo "  Team size: $TEAM_SIZE"
echo "  Max iterations: $MAX_ITER"
echo ""
echo "Timing:"
echo "  Start: $START_TIME_STR"
echo "  End: $END_TIME_STR"
echo "  Elapsed: ${HOURS}h ${MINUTES}m ${SECONDS}s (${ELAPSED}s total)"
echo ""
echo "Output:"
echo "  Answer: $OUTPUT_FILE"
echo "  Detailed log: $DETAILED_LOG"
echo "  Exit code: $FINAL_EXIT_CODE"
echo "========================================"

# Save timing to CSV
{
    echo "config,mode,rounds,team_size,max_iter,elapsed_sec,hours,minutes,seconds,exit_code,start_time,end_time"
    echo "${OUTPUT_NAME},${MODE},${ROUNDS},${TEAM_SIZE},${MAX_ITER},${ELAPSED},${HOURS},${MINUTES},${SECONDS},${FINAL_EXIT_CODE},${START_TIME},${END_TIME}"
} > "$TIMING_LOG"

echo ""
echo "Job completed!"

exit $FINAL_EXIT_CODE
