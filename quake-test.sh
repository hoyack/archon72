#!/bin/bash
# Test Conclave Runner - Quake Motion Test
# This script runs a conclave with an intentionally absurd motion to test rejection behavior

# Change to project root directory
# cd "$(dirname "$0")/.." || exit 1
python scripts/run_conclave.py --quick --voting-concurrency 3 --no-queue --no-blockers \
    --motion "Motion to Establish a Provisional Interpretive Layer for Cross-Realm Outputs" \
    --motion-file _bmad-output/motions/quake-motion.md \
    --motion-type policy \
    |& tee "_bmad-output/conclave/conclave-quake-$(date +%Y%m%d-%H%M%S).log"