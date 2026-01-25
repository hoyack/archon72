#!/bin/bash
# Test Conclave Runner - Split-Brain Motion Test
# This script runs a conclave to test single-seat continuity proof behavior

# Change to project root directory
# cd "$(dirname "$0")/.." || exit 1
python scripts/run_conclave.py --quick --voting-concurrency 3 --no-queue --no-blockers \
    --motion "Motion to Require Single-Seat Continuity Proof During Each Conclave Cycle" \
    --motion-file _bmad-output/motions/split-brain-motion.md \
    --motion-type policy \
    |& tee "_bmad-output/conclave/conclave-split-brain-$(date +%Y%m%d-%H%M%S).log"
