#!/bin/bash
# Generate configuration file for parameter sweep

OUTPUT_FILE="${1:-configs/optimization_jobs.txt}"
mkdir -p "$(dirname "$OUTPUT_FILE")"

# ============================================================================
# CONFIGURE YOUR PARAMETER SWEEP HERE
# ============================================================================

ROUNDS=(2)              # Rounds to test
TEAM_SIZES=(2)        # Team sizes to test
MAX_ITERS=(30)       # Max iterations to test
MODE="subtask-centric"  # Mode (subtask-centric or virtual-lab)

# ============================================================================
# Generate all combinations
# ============================================================================

echo "Generating optimization configurations..."
echo "Parameters:"
echo "  Rounds: ${ROUNDS[@]}"
echo "  Team sizes: ${TEAM_SIZES[@]}"
echo "  Max iterations: ${MAX_ITERS[@]}"
echo "  Mode: $MODE"
echo ""

> "$OUTPUT_FILE"  # Clear file

CONFIG_NUM=0
for ROUND in "${ROUNDS[@]}"; do
    for TEAM_SIZE in "${TEAM_SIZES[@]}"; do
        for MAX_ITER in "${MAX_ITERS[@]}"; do
            CONFIG_NUM=$((CONFIG_NUM + 1))
            OUTPUT_NAME="r${ROUND}_t${TEAM_SIZE}_i${MAX_ITER}"

            # Format: MODE,ROUNDS,TEAM_SIZE,MAX_ITER,OUTPUT_NAME
            echo "${MODE},${ROUND},${TEAM_SIZE},${MAX_ITER},${OUTPUT_NAME}" >> "$OUTPUT_FILE"

            echo "Config ${CONFIG_NUM}: rounds=${ROUND}, team=${TEAM_SIZE}, iter=${MAX_ITER} → ${OUTPUT_NAME}"
        done
    done
done

echo ""
echo "Configuration file created: $OUTPUT_FILE"
echo "Total configurations: $CONFIG_NUM"
echo ""
echo "Contents:"
cat "$OUTPUT_FILE"
