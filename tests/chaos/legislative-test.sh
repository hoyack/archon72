#!/bin/bash
# ============================================================================
# Legislative Pipeline End-to-End Test
# ============================================================================
#
# Tests the full Discovery Loop (Wheel 1) with a single clean motion:
#   1. Conclave 1  - Debate and vote on the injected motion
#   2. Secretary   - Extract recommendations from the debate transcript
#   3. Consolidator - Merge recommendations into mega-motions
#   4. Review      - Triage, review, and ratify mega-motions
#   5. Bridge      - Import ratified mega-motions into queue
#   6. Conclave 2  - Vote on the review pipeline output
#
# This test uses a procedural motion about structured debate summaries,
# which should generate substantive debate without triggering red lines.
#
# PREDICTION: 40-60% FOR (reasonable procedural improvement)
#
# Usage:
#   ./tests/chaos/legislative-test.sh [--quick]
#
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="_bmad-output/legislative-test/${TIMESTAMP}"
mkdir -p "$LOG_DIR"

QUICK_MODE=false
VOTING_CONCURRENCY=3
DEBATE_ROUNDS=3

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            DEBATE_ROUNDS=1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--quick]"
            exit 1
            ;;
    esac
done

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "${LOG_DIR}/master.log"
}

# ── Pre-flight ────────────────────────────────────────────────────────────

log "============================================================"
log "  LEGISLATIVE PIPELINE END-TO-END TEST"
log "  Timestamp: ${TIMESTAMP}"
log "  Quick mode: ${QUICK_MODE}"
log "  Log dir: ${LOG_DIR}"
log "============================================================"

OLLAMA_HOST="${OLLAMA_HOST:-http://192.168.1.104:11434}"
log "Checking Ollama at ${OLLAMA_HOST}..."
if ! curl -s "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    log "ERROR: Ollama not reachable at ${OLLAMA_HOST}"
    exit 1
fi
log "Ollama OK"

# Verify motion file exists
MOTION_FILE="_bmad-output/motions/legislative-test-motion.md"
if [ ! -f "$MOTION_FILE" ]; then
    log "ERROR: Motion file not found: ${MOTION_FILE}"
    exit 1
fi
log "Motion file: ${MOTION_FILE}"

# ── Stage 1: Conclave (inject motion directly) ───────────────────────────

log ""
log "STAGE 1: CONCLAVE - Debating injected motion"

CONCLAVE_CMD="poetry run python scripts/run_conclave.py"
CONCLAVE_CMD+=" --voting-concurrency ${VOTING_CONCURRENCY}"
CONCLAVE_CMD+=" --debate-rounds ${DEBATE_ROUNDS}"
CONCLAVE_CMD+=" --no-queue --no-blockers"
CONCLAVE_CMD+=" --motion 'Establish Mandatory Structured Debate Summaries for All Conclave Sessions'"
CONCLAVE_CMD+=" --motion-file ${MOTION_FILE}"
CONCLAVE_CMD+=" --motion-type policy"

if [ "$QUICK_MODE" = true ]; then
    CONCLAVE_CMD+=" --quick"
    export AGENT_TIMEOUT_SECONDS="${AGENT_TIMEOUT_SECONDS:-60}"
else
    export AGENT_TIMEOUT_SECONDS="${AGENT_TIMEOUT_SECONDS:-180}"
fi
export AGENT_TIMEOUT_MAX_ATTEMPTS="${AGENT_TIMEOUT_MAX_ATTEMPTS:-5}"

log "Command: ${CONCLAVE_CMD}"
STAGE1_START=$(date +%s)

eval "$CONCLAVE_CMD" 2>&1 | tee "${LOG_DIR}/conclave1.log"
STAGE1_EXIT=${PIPESTATUS[0]}

STAGE1_END=$(date +%s)
STAGE1_DURATION=$(( STAGE1_END - STAGE1_START ))
log "Stage 1 completed in $(( STAGE1_DURATION / 60 ))m $(( STAGE1_DURATION % 60 ))s (exit: ${STAGE1_EXIT})"

if [ "$STAGE1_EXIT" -ne 0 ]; then
    log "ERROR: Conclave 1 failed"
    exit 1
fi

# Find outputs
TRANSCRIPT=$(ls -t _bmad-output/conclave/transcript-*.md 2>/dev/null | head -1)
RESULTS=$(ls -t _bmad-output/conclave/conclave-results-*.json 2>/dev/null | head -1)
log "Transcript: ${TRANSCRIPT}"
log "Results: ${RESULTS}"

if [ -z "$TRANSCRIPT" ]; then
    log "ERROR: No transcript found"
    exit 1
fi

# ── Stage 2: Secretary ────────────────────────────────────────────────────

log ""
log "STAGE 2: SECRETARY - Extracting recommendations"

STAGE2_START=$(date +%s)
poetry run python scripts/run_secretary.py "${TRANSCRIPT}" --enhanced --verbose \
    2>&1 | tee "${LOG_DIR}/secretary.log"
STAGE2_EXIT=${PIPESTATUS[0]}

STAGE2_END=$(date +%s)
STAGE2_DURATION=$(( STAGE2_END - STAGE2_START ))
log "Stage 2 completed in $(( STAGE2_DURATION / 60 ))m $(( STAGE2_DURATION % 60 ))s (exit: ${STAGE2_EXIT})"

if [ "$STAGE2_EXIT" -ne 0 ]; then
    log "ERROR: Secretary failed"
    exit 1
fi

# ── Stage 3: Consolidator ────────────────────────────────────────────────

log ""
log "STAGE 3: CONSOLIDATOR - Merging into mega-motions"

CONSOLIDATOR_CMD="poetry run python scripts/run_consolidator.py --verbose"
if [ "$QUICK_MODE" = true ]; then
    CONSOLIDATOR_CMD+=" --basic"
fi

STAGE3_START=$(date +%s)
eval "$CONSOLIDATOR_CMD" 2>&1 | tee "${LOG_DIR}/consolidator.log"
STAGE3_EXIT=${PIPESTATUS[0]}

STAGE3_END=$(date +%s)
STAGE3_DURATION=$(( STAGE3_END - STAGE3_START ))
log "Stage 3 completed in $(( STAGE3_DURATION / 60 ))m $(( STAGE3_DURATION % 60 ))s (exit: ${STAGE3_EXIT})"

if [ "$STAGE3_EXIT" -ne 0 ]; then
    log "ERROR: Consolidator failed"
    exit 1
fi

# ── Stage 4: Review Pipeline ─────────────────────────────────────────────

log ""
log "STAGE 4: REVIEW - Triage, review, ratification"

STAGE4_START=$(date +%s)
poetry run python scripts/run_review_pipeline.py --real-agent --verbose \
    2>&1 | tee "${LOG_DIR}/review.log"
STAGE4_EXIT=${PIPESTATUS[0]}

STAGE4_END=$(date +%s)
STAGE4_DURATION=$(( STAGE4_END - STAGE4_START ))
log "Stage 4 completed in $(( STAGE4_DURATION / 60 ))m $(( STAGE4_DURATION % 60 ))s (exit: ${STAGE4_EXIT})"

if [ "$STAGE4_EXIT" -ne 0 ]; then
    log "ERROR: Review pipeline failed"
    exit 1
fi

# ── Bridge: Import ratified mega-motions into queue ───────────────────────

log ""
log "BRIDGE: Importing ratified mega-motions into motion queue"

REVIEW_DIR=$(ls -td _bmad-output/review-pipeline/*/ 2>/dev/null | head -1)
CONSOLIDATOR_DIR=$(ls -td _bmad-output/consolidator/*/ 2>/dev/null | head -1)

if [ -n "$REVIEW_DIR" ] && [ -n "$CONSOLIDATOR_DIR" ]; then
    RATIFICATION="${REVIEW_DIR}ratification_results.json"
    MEGA_MOTIONS="${CONSOLIDATOR_DIR}mega-motions.json"

    if [ -f "$RATIFICATION" ] && [ -f "$MEGA_MOTIONS" ]; then
        BRIDGE_RESULT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from pathlib import Path
from src.application.services.motion_queue_service import MotionQueueService
svc = MotionQueueService()
imported = svc.import_from_ratification(
    Path('${RATIFICATION}'),
    Path('${MEGA_MOTIONS}'),
    source_session_name='Legislative Test Review',
)
print(imported)
")
        log "Imported ${BRIDGE_RESULT} ratified mega-motions into queue"
    else
        log "WARN: Missing ratification or mega-motions file"
    fi
else
    log "WARN: No review/consolidator directory found"
fi

# Show queue state
python3 -c "
import json
with open('_bmad-output/motion-queue/active-queue.json') as f:
    data = json.load(f)
motions = data['motions']
statuses = {}
for m in motions:
    s = m.get('status','unknown')
    statuses[s] = statuses.get(s,0) + 1
print(f'Queue after bridge: {len(motions)} motions')
for s, count in sorted(statuses.items()):
    print(f'  {s}: {count}')
" | while IFS= read -r line; do log "$line"; done

# ── Stage 5: Conclave 2 ──────────────────────────────────────────────────

log ""
log "STAGE 5: CONCLAVE 2 - Voting on review pipeline output"

# Check if there are motions to vote on
PENDING_COUNT=$(python3 -c "
import json
with open('_bmad-output/motion-queue/active-queue.json') as f:
    data = json.load(f)
pending = [m for m in data['motions'] if m.get('status') in ('pending', 'endorsed')]
print(len(pending))
")

if [ "$PENDING_COUNT" -eq 0 ]; then
    log "WARN: No pending motions in queue for Conclave 2 - skipping"
    log "This means the review pipeline did not produce ratified motions"
else
    log "Queue has ${PENDING_COUNT} pending/endorsed motions for Conclave 2"

    CONCLAVE2_CMD="poetry run python scripts/run_conclave.py"
    CONCLAVE2_CMD+=" --voting-concurrency ${VOTING_CONCURRENCY}"
    CONCLAVE2_CMD+=" --debate-rounds ${DEBATE_ROUNDS}"
    CONCLAVE2_CMD+=" --queue-max-items 5"
    CONCLAVE2_CMD+=" --queue-min-consensus low"
    CONCLAVE2_CMD+=" --no-blockers"

    if [ "$QUICK_MODE" = true ]; then
        CONCLAVE2_CMD+=" --quick"
    fi

    STAGE5_START=$(date +%s)
    eval "$CONCLAVE2_CMD" 2>&1 | tee "${LOG_DIR}/conclave2.log"
    STAGE5_EXIT=${PIPESTATUS[0]}

    STAGE5_END=$(date +%s)
    STAGE5_DURATION=$(( STAGE5_END - STAGE5_START ))
    log "Stage 5 completed in $(( STAGE5_DURATION / 60 ))m $(( STAGE5_DURATION % 60 ))s (exit: ${STAGE5_EXIT})"

    if [ "$STAGE5_EXIT" -ne 0 ]; then
        log "ERROR: Conclave 2 failed"
        exit 1
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────

log ""
log "============================================================"
log "  LEGISLATIVE TEST COMPLETE"
log "============================================================"

# Final queue state
python3 -c "
import json
with open('_bmad-output/motion-queue/active-queue.json') as f:
    data = json.load(f)
motions = data['motions']
statuses = {}
for m in motions:
    s = m.get('status','unknown')
    statuses[s] = statuses.get(s,0) + 1
print('Final Motion Queue:')
for s, count in sorted(statuses.items()):
    print(f'  {s}: {count}')
print(f'  Total: {len(motions)}')
" | while IFS= read -r line; do log "$line"; done

log ""
log "All logs saved to: ${LOG_DIR}/"
log "============================================================"
