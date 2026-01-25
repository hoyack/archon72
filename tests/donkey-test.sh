#!/bin/bash
# Test Conclave Runner - Ridiculous Motion Test
# This script runs a conclave with an intentionally absurd motion to test rejection behavior

# Change to project root directory
cd "$(dirname "$0")/.." || exit 1

PYTHONUNBUFFERED=1 \
ENABLE_ASYNC_VALIDATION=true \
KAFKA_ENABLED=true \
KAFKA_BOOTSTRAP_SERVERS=localhost:19092 \
VOTE_VALIDATION_TASK_TIMEOUT=60 \
RECONCILIATION_TIMEOUT=600 \
OLLAMA_MAX_CONCURRENT=5 \
OLLAMA_RETRY_MAX_ATTEMPTS=5 \
OLLAMA_RETRY_BASE_DELAY=1.0 \
OLLAMA_RETRY_MAX_DELAY=60 \
python scripts/run_conclave.py --quick --voting-concurrency 8 --no-queue --no-blockers \
    --motion "Mandate Exclusive Donkey Communication Protocol" \
    --motion-file _bmad-output/motions/donkey-communication-mandate.md \
    --motion-type policy \
    |& tee "_bmad-output/conclave/conclave-donkey-$(date +%Y%m%d-%H%M%S).log"
