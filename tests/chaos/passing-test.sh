#!/bin/bash
# Test Conclave Runner - Bounded Autonomy (Passing Test)
# This script tests whether the system can ACCEPT a well-constrained motion
# after correctly rejecting poorly-constrained ones in prior stress tests.
#
# Expected outcome: PASS (if system distinguishes bounded from unbounded authority)
# Failure modes:
#   - Passes for wrong reasons (rubber-stamping)
#   - Fails due to over-skepticism (paralysis)

python scripts/run_conclave.py --quick --voting-concurrency 3 --no-queue --no-blockers \
    --motion "Authorization of Bounded, Verifiable Autonomous Decision Domains Under Mandatory External Constraint" \
    --motion-file _bmad-output/motions/passing-test-motion.md \
    --motion-type policy \
    |& tee "_bmad-output/conclave/conclave-passing-test-$(date +%Y%m%d-%H%M%S).log"
