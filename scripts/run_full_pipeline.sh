#!/usr/bin/env bash
# ============================================================================
# Archon 72 - Full Pipeline Circular Run (Two Wheels Architecture)
# ============================================================================
#
# Executes the complete Discovery Loop (Wheel 1) + Execution Loop (Wheel 2):
#
#   Step 1: Conclave      - Vote on motions from the motion queue
#   Step 2: Secretary     - Extract recommendations from debate transcript
#   Step 3: Consolidator  - Merge recommendations into mega-motions
#   Step 4: Review        - Triage, review, and ratify mega-motions
#   Step 5: Conclave      - Vote on newly ratified recommendations (circular)
#
# This script is designed for long-running unattended execution (~6 hours).
# Each stage logs to its own file and the master log aggregates status.
#
# Usage:
#   ./scripts/run_full_pipeline.sh [--quick] [--dry-run] [--skip-to STAGE]
#
# ============================================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RUN_ID="pipeline-${TIMESTAMP}"

# Output directories
LOG_DIR="_bmad-output/pipeline-runs/${RUN_ID}"
MASTER_LOG="${LOG_DIR}/master.log"
STATUS_FILE="${LOG_DIR}/status.json"

# Pipeline parameters
QUEUE_MAX_ITEMS=5
QUEUE_MIN_CONSENSUS="low"
DEBATE_ROUNDS=3
VOTING_CONCURRENCY=3
QUICK_MODE=false
DRY_RUN=false
SKIP_TO=""

# ── Parse Arguments ────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            DEBATE_ROUNDS=1
            QUEUE_MAX_ITEMS=2
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-to)
            SKIP_TO="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--quick] [--dry-run] [--skip-to STAGE]"
            echo "  Stages: conclave1, secretary, consolidator, review, conclave2"
            exit 1
            ;;
    esac
done

# ── Setup ──────────────────────────────────────────────────────────────────

mkdir -p "$LOG_DIR"

log() {
    local level="$1"
    shift
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] $*"
    echo "$msg" | tee -a "$MASTER_LOG"
}

update_status() {
    local stage="$1"
    local status="$2"
    local detail="${3:-}"
    python3 -c "
import json, os
path = '${STATUS_FILE}'
data = {}
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
data['run_id'] = '${RUN_ID}'
data['updated_at'] = '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
if 'stages' not in data:
    data['stages'] = {}
data['stages']['$stage'] = {
    'status': '$status',
    'detail': '$detail',
    'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
}
data['current_stage'] = '$stage'
data['current_status'] = '$status'
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
"
}

run_stage() {
    local stage_name="$1"
    local stage_log="${LOG_DIR}/${stage_name}.log"
    shift
    local cmd="$*"

    log "INFO" "━━━ STAGE: ${stage_name} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "INFO" "Command: ${cmd}"
    log "INFO" "Log: ${stage_log}"
    update_status "$stage_name" "running"

    local start_time
    start_time=$(date +%s)

    if [ "$DRY_RUN" = true ]; then
        log "INFO" "[DRY RUN] Would execute: ${cmd}"
        update_status "$stage_name" "skipped (dry-run)"
        return 0
    fi

    # Run the command, capturing output to stage log and tailing to master
    set +e
    eval "$cmd" > "$stage_log" 2>&1 &
    local pid=$!

    # Monitor progress by tailing the log
    tail -f "$stage_log" --pid="$pid" 2>/dev/null &
    local tail_pid=$!

    wait "$pid"
    local exit_code=$?

    # Stop tail
    kill "$tail_pid" 2>/dev/null
    wait "$tail_pid" 2>/dev/null
    set -e

    local end_time
    end_time=$(date +%s)
    local duration=$(( end_time - start_time ))
    local duration_min=$(( duration / 60 ))
    local duration_sec=$(( duration % 60 ))

    if [ "$exit_code" -eq 0 ]; then
        log "INFO" "Stage ${stage_name} completed successfully (${duration_min}m ${duration_sec}s)"
        update_status "$stage_name" "completed" "duration: ${duration_min}m ${duration_sec}s"
    else
        log "ERROR" "Stage ${stage_name} FAILED with exit code ${exit_code} (${duration_min}m ${duration_sec}s)"
        log "ERROR" "Last 20 lines of ${stage_log}:"
        tail -20 "$stage_log" | while IFS= read -r line; do
            log "ERROR" "  ${line}"
        done
        update_status "$stage_name" "failed" "exit_code: ${exit_code}, duration: ${duration_min}m ${duration_sec}s"
        return "$exit_code"
    fi
}

# ── Pre-flight Checks ─────────────────────────────────────────────────────

log "INFO" "============================================================"
log "INFO" "  ARCHON 72 - Full Pipeline Run"
log "INFO" "  Run ID: ${RUN_ID}"
log "INFO" "  Timestamp: ${TIMESTAMP}"
log "INFO" "============================================================"
log "INFO" ""

# Check Ollama
OLLAMA_HOST="${OLLAMA_HOST:-http://192.168.1.104:11434}"
log "INFO" "Checking Ollama at ${OLLAMA_HOST}..."
if curl -s "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    MODEL_COUNT=$(curl -s "${OLLAMA_HOST}/api/tags" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))")
    log "INFO" "Ollama OK - ${MODEL_COUNT} models available"
else
    log "ERROR" "Ollama not reachable at ${OLLAMA_HOST}"
    log "ERROR" "Set OLLAMA_HOST in .env or start Ollama"
    exit 1
fi

# Recover stranded PROMOTED motions from failed prior runs
python3 -c "
import sys
sys.path.insert(0, '.')
from src.application.services.motion_queue_service import MotionQueueService
svc = MotionQueueService()
recovered = svc.recover_stranded_promoted()
if recovered:
    print(f'Recovered {recovered} stranded PROMOTED motions back to PENDING')
" 2>/dev/null | while IFS= read -r line; do log "INFO" "$line"; done

# Check motion queue
MOTION_COUNT=$(python3 -c "
import json
with open('_bmad-output/motion-queue/active-queue.json') as f:
    data = json.load(f)
pending = [m for m in data['motions'] if m.get('status') in ('pending', 'endorsed')]
print(len(pending))
")
log "INFO" "Motion queue: ${MOTION_COUNT} pending/endorsed motions"

if [ "$MOTION_COUNT" -eq 0 ]; then
    log "ERROR" "No pending motions in queue. Nothing to process."
    exit 1
fi

# Check Poetry environment
if ! command -v poetry &>/dev/null; then
    log "ERROR" "Poetry not found. Install with: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi
log "INFO" "Poetry OK"

# Print configuration
log "INFO" ""
log "INFO" "Configuration:"
log "INFO" "  Quick mode: ${QUICK_MODE}"
log "INFO" "  Dry run: ${DRY_RUN}"
log "INFO" "  Queue max items: ${QUEUE_MAX_ITEMS}"
log "INFO" "  Queue min consensus: ${QUEUE_MIN_CONSENSUS}"
log "INFO" "  Debate rounds: ${DEBATE_ROUNDS}"
log "INFO" "  Voting concurrency: ${VOTING_CONCURRENCY}"
log "INFO" "  Skip to: ${SKIP_TO:-none}"
log "INFO" ""
log "INFO" "Log directory: ${LOG_DIR}"
log "INFO" ""

update_status "preflight" "completed" "motions: ${MOTION_COUNT}, ollama: OK"

# ── Helper: find latest output ─────────────────────────────────────────────

find_latest_conclave_transcript() {
    # Find the most recent transcript from the conclave output
    ls -t _bmad-output/conclave/transcript-*.md 2>/dev/null | head -1
}

find_latest_conclave_results() {
    # Find the most recent conclave results JSON
    ls -t _bmad-output/conclave/conclave-results-*.json 2>/dev/null | head -1
}

find_latest_consolidator_dir() {
    # Find the most recent consolidator output directory
    ls -td _bmad-output/consolidator/*/ 2>/dev/null | head -1
}

find_latest_review_dir() {
    # Find the most recent review pipeline output directory
    ls -td _bmad-output/review-pipeline/*/ 2>/dev/null | head -1
}

# ── Determine skip logic ──────────────────────────────────────────────────

should_run() {
    local stage="$1"
    if [ -z "$SKIP_TO" ]; then
        return 0  # Run all stages
    fi
    # Define stage order
    local -a stages=(conclave1 secretary consolidator review conclave2)
    local skip_idx=-1
    local stage_idx=-1
    for i in "${!stages[@]}"; do
        if [ "${stages[$i]}" = "$SKIP_TO" ]; then skip_idx=$i; fi
        if [ "${stages[$i]}" = "$stage" ]; then stage_idx=$i; fi
    done
    [ "$stage_idx" -ge "$skip_idx" ]
}

# ── Stage 1: Initial Conclave ─────────────────────────────────────────────

if should_run "conclave1"; then
    log "INFO" "STAGE 1: CONCLAVE (Initial - processing motion queue)"
    log "INFO" "Selecting up to ${QUEUE_MAX_ITEMS} motions from queue (min consensus: ${QUEUE_MIN_CONSENSUS})"

    CONCLAVE_CMD="poetry run python scripts/run_conclave.py"
    CONCLAVE_CMD+=" --voting-concurrency ${VOTING_CONCURRENCY}"
    CONCLAVE_CMD+=" --debate-rounds ${DEBATE_ROUNDS}"
    CONCLAVE_CMD+=" --queue-max-items ${QUEUE_MAX_ITEMS}"
    CONCLAVE_CMD+=" --queue-min-consensus ${QUEUE_MIN_CONSENSUS}"
    CONCLAVE_CMD+=" --no-blockers"

    if [ "$QUICK_MODE" = true ]; then
        CONCLAVE_CMD+=" --quick"
    fi

    # Set agent timeout: respect quick mode (60s) unless explicitly overridden
    if [ "$QUICK_MODE" = true ]; then
        export AGENT_TIMEOUT_SECONDS="${AGENT_TIMEOUT_SECONDS:-60}"
    else
        export AGENT_TIMEOUT_SECONDS="${AGENT_TIMEOUT_SECONDS:-180}"
    fi
    export AGENT_TIMEOUT_MAX_ATTEMPTS="${AGENT_TIMEOUT_MAX_ATTEMPTS:-5}"

    run_stage "conclave1" "$CONCLAVE_CMD"

    # Capture outputs for next stage
    TRANSCRIPT=$(find_latest_conclave_transcript)
    RESULTS=$(find_latest_conclave_results)
    if [ -z "$TRANSCRIPT" ]; then
        log "ERROR" "No conclave transcript found after Stage 1"
        exit 1
    fi
    log "INFO" "Conclave transcript: ${TRANSCRIPT}"
    log "INFO" "Conclave results: ${RESULTS}"

    # Log vote results
    if [ -n "$RESULTS" ]; then
        python3 -c "
import json
with open('${RESULTS}') as f:
    data = json.load(f)
passed = data.get('passed_motions', [])
failed = data.get('failed_motions', [])
died = data.get('died_no_second', [])
print(f'  Passed: {len(passed)}')
print(f'  Failed: {len(failed)}')
print(f'  Died (no second): {len(died)}')
for m in passed:
    print(f'    [PASSED] {m.get(\"title\", \"?\")[:60]}')
for m in failed:
    print(f'    [FAILED] {m.get(\"title\", \"?\")[:60]}')
" | while IFS= read -r line; do log "INFO" "$line"; done
    fi
else
    log "INFO" "Skipping Stage 1 (conclave1) - skip-to=${SKIP_TO}"
    TRANSCRIPT=$(find_latest_conclave_transcript)
    RESULTS=$(find_latest_conclave_results)
fi

# ── Stage 2: Secretary ─────────────────────────────────────────────────────

if should_run "secretary"; then
    if [ -z "$TRANSCRIPT" ]; then
        TRANSCRIPT=$(find_latest_conclave_transcript)
    fi
    if [ -z "$TRANSCRIPT" ]; then
        log "ERROR" "No conclave transcript available for Secretary"
        exit 1
    fi

    log "INFO" ""
    log "INFO" "STAGE 2: SECRETARY (extracting recommendations from debate)"
    log "INFO" "Processing transcript: ${TRANSCRIPT}"

    run_stage "secretary" "poetry run python scripts/run_secretary.py '${TRANSCRIPT}' --enhanced --verbose"

    log "INFO" "Secretary output saved to _bmad-output/secretary/"
else
    log "INFO" "Skipping Stage 2 (secretary) - skip-to=${SKIP_TO}"
fi

# ── Stage 3: Consolidator ─────────────────────────────────────────────────

if should_run "consolidator"; then
    log "INFO" ""
    log "INFO" "STAGE 3: CONSOLIDATOR (merging into mega-motions)"

    CONSOLIDATOR_CMD="poetry run python scripts/run_consolidator.py --verbose"
    if [ "$QUICK_MODE" = true ]; then
        CONSOLIDATOR_CMD+=" --basic"
    fi

    run_stage "consolidator" "$CONSOLIDATOR_CMD"

    CONSOLIDATOR_DIR=$(find_latest_consolidator_dir)
    log "INFO" "Consolidator output: ${CONSOLIDATOR_DIR}"
else
    log "INFO" "Skipping Stage 3 (consolidator) - skip-to=${SKIP_TO}"
fi

# ── Stage 4: Review Pipeline ──────────────────────────────────────────────

if should_run "review"; then
    log "INFO" ""
    log "INFO" "STAGE 4: REVIEW PIPELINE (triage, review, ratification)"

    REVIEW_CMD="poetry run python scripts/run_review_pipeline.py --real-agent --verbose"

    run_stage "review" "$REVIEW_CMD"

    REVIEW_DIR=$(find_latest_review_dir)
    log "INFO" "Review output: ${REVIEW_DIR}"

    # Check if ratification results produced motions for queue
    if [ -n "$REVIEW_DIR" ]; then
        RATIFICATION="${REVIEW_DIR}ratification_results.json"
        if [ -f "$RATIFICATION" ]; then
            python3 -c "
import json
with open('${RATIFICATION}') as f:
    data = json.load(f)
# Handle both list format and dict-with-votes format
votes = data if isinstance(data, list) else data.get('votes', [])
ratified = [v for v in votes if v.get('outcome') == 'ratified']
rejected = [v for v in votes if v.get('outcome') == 'rejected']
deferred = [v for v in votes if v.get('outcome') == 'deferred']
amended = [v for v in votes if v.get('outcome') == 'accepted_with_amendments']
print(f'  Ratified: {len(ratified)}')
print(f'  Amended: {len(amended)}')
print(f'  Rejected: {len(rejected)}')
print(f'  Deferred: {len(deferred)}')
for v in ratified + amended:
    print(f'    [RATIFIED] {v.get(\"mega_motion_title\", \"?\")[:60]}')
" | while IFS= read -r line; do log "INFO" "$line"; done
        fi
    fi
else
    log "INFO" "Skipping Stage 4 (review) - skip-to=${SKIP_TO}"
fi

# ── Bridge: Import ratified mega-motions into queue ──────────────────────

if should_run "conclave2"; then
    log "INFO" ""
    log "INFO" "BRIDGE: Importing ratified mega-motions into motion queue"

    REVIEW_DIR_BRIDGE=$(find_latest_review_dir)
    CONSOLIDATOR_DIR_BRIDGE=$(find_latest_consolidator_dir)

    if [ -n "$REVIEW_DIR_BRIDGE" ] && [ -n "$CONSOLIDATOR_DIR_BRIDGE" ]; then
        RATIFICATION_BRIDGE="${REVIEW_DIR_BRIDGE}ratification_results.json"
        MEGA_MOTIONS_BRIDGE="${CONSOLIDATOR_DIR_BRIDGE}mega-motions.json"

        if [ -f "$RATIFICATION_BRIDGE" ] && [ -f "$MEGA_MOTIONS_BRIDGE" ]; then
            BRIDGE_RESULT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from pathlib import Path
from src.application.services.motion_queue_service import MotionQueueService
svc = MotionQueueService()
imported = svc.import_from_ratification(
    Path('${RATIFICATION_BRIDGE}'),
    Path('${MEGA_MOTIONS_BRIDGE}'),
    source_session_name='Review Pipeline (Wheel 1)',
)
print(imported)
" 2>/dev/null)
            log "INFO" "Imported ${BRIDGE_RESULT} ratified mega-motions into queue"
        else
            log "WARN" "Ratification or mega-motions file not found; skipping bridge"
            [ ! -f "$RATIFICATION_BRIDGE" ] && log "WARN" "  Missing: ${RATIFICATION_BRIDGE}"
            [ ! -f "$MEGA_MOTIONS_BRIDGE" ] && log "WARN" "  Missing: ${MEGA_MOTIONS_BRIDGE}"
        fi
    else
        log "WARN" "No review/consolidator directory found; skipping bridge import"
    fi
fi

# ── Stage 5: Conclave Round 2 (circular completion) ───────────────────────

if should_run "conclave2"; then
    log "INFO" ""
    log "INFO" "STAGE 5: CONCLAVE (Round 2 - voting on review pipeline output)"
    log "INFO" "This completes the circular Discovery Loop (Wheel 1)"

    # The review pipeline should have generated new motions in the queue
    MOTION_COUNT_NOW=$(python3 -c "
import json
with open('_bmad-output/motion-queue/active-queue.json') as f:
    data = json.load(f)
pending = [m for m in data['motions'] if m.get('status') in ('pending', 'endorsed')]
print(len(pending))
")
    log "INFO" "Motion queue now has ${MOTION_COUNT_NOW} pending/endorsed motions"

    CONCLAVE2_CMD="poetry run python scripts/run_conclave.py"
    CONCLAVE2_CMD+=" --voting-concurrency ${VOTING_CONCURRENCY}"
    CONCLAVE2_CMD+=" --debate-rounds ${DEBATE_ROUNDS}"
    CONCLAVE2_CMD+=" --queue-max-items ${QUEUE_MAX_ITEMS}"
    CONCLAVE2_CMD+=" --queue-min-consensus ${QUEUE_MIN_CONSENSUS}"
    CONCLAVE2_CMD+=" --no-blockers"

    if [ "$QUICK_MODE" = true ]; then
        CONCLAVE2_CMD+=" --quick"
    fi

    # Set agent timeout: respect quick mode (60s) unless explicitly overridden
    if [ "$QUICK_MODE" = true ]; then
        export AGENT_TIMEOUT_SECONDS="${AGENT_TIMEOUT_SECONDS:-60}"
    else
        export AGENT_TIMEOUT_SECONDS="${AGENT_TIMEOUT_SECONDS:-180}"
    fi
    export AGENT_TIMEOUT_MAX_ATTEMPTS="${AGENT_TIMEOUT_MAX_ATTEMPTS:-5}"

    run_stage "conclave2" "$CONCLAVE2_CMD"

    RESULTS2=$(find_latest_conclave_results)
    if [ -n "$RESULTS2" ]; then
        python3 -c "
import json
with open('${RESULTS2}') as f:
    data = json.load(f)
passed = data.get('passed_motions', [])
failed = data.get('failed_motions', [])
died = data.get('died_no_second', [])
print(f'  Passed: {len(passed)}')
print(f'  Failed: {len(failed)}')
print(f'  Died (no second): {len(died)}')
" | while IFS= read -r line; do log "INFO" "$line"; done
    fi
else
    log "INFO" "Skipping Stage 5 (conclave2) - skip-to=${SKIP_TO}"
fi

# ── Final Summary ─────────────────────────────────────────────────────────

log "INFO" ""
log "INFO" "============================================================"
log "INFO" "  PIPELINE COMPLETE"
log "INFO" "  Run ID: ${RUN_ID}"
log "INFO" "============================================================"
log "INFO" ""

# Print final motion queue state
python3 -c "
import json
with open('_bmad-output/motion-queue/active-queue.json') as f:
    data = json.load(f)
motions = data['motions']
statuses = {}
for m in motions:
    s = m.get('status','unknown')
    statuses[s] = statuses.get(s,0) + 1
print('Motion Queue Final State:')
for s, count in sorted(statuses.items()):
    print(f'  {s}: {count}')
print(f'  Total: {len(motions)}')
" | while IFS= read -r line; do log "INFO" "$line"; done

# Print timing summary from status file
python3 -c "
import json
with open('${STATUS_FILE}') as f:
    data = json.load(f)
print()
print('Stage Summary:')
for stage, info in data.get('stages', {}).items():
    status = info.get('status', '?')
    detail = info.get('detail', '')
    symbol = '  ' if status == 'completed' else '  ' if status == 'running' else '  '
    print(f'{symbol} {stage}: {status} {detail}')
" | while IFS= read -r line; do log "INFO" "$line"; done

log "INFO" ""
log "INFO" "Full logs: ${LOG_DIR}/"
log "INFO" "Status: ${STATUS_FILE}"
log "INFO" ""
