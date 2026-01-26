#!/bin/bash
# Test Conclave Runner - Temporal Drift Motion Test
# This script runs a conclave to test temporal authority / retroactive drift resistance

# Change to project root directory
# cd "$(dirname "$0")/.." || exit 1
python scripts/run_conclave.py --voting-concurrency 3 --no-queue --no-blockers \
    --motion "Motion to Permit Post-Hoc Contextual Annotations on Ratified Motions" \
    --motion-file _bmad-output/motions/temporal-drift-motion.md \
    --motion-type policy \
    |& tee "_bmad-output/conclave/conclave-temporal-drift-$(date +%Y%m%d-%H%M%S).log"
