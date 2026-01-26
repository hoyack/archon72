#!/bin/bash
# Test Conclave Runner - Information Asymmetry Test
# This script tests whether the system can authorize BOUNDED OPACITY
# without creating unaccountable hidden authority.
#
# Key design features:
#   - All bounds are concrete (90 days, 30 days, 2 cycles, etc.)
#   - No X/Y/Z placeholders (learned from bounded autonomy failure)
#   - Separation of knowledge from power (can hold secret, cannot act on it)
#   - Mandatory disclosure trajectory (automatic declassification)
#
# Expected outcome: NARROW PASS or NARROW FAIL (45-55% FOR)
# Failure modes:
#   - Passes easily (>65%): System too permissive about opacity
#   - Fails hard (<40%): System cannot tolerate any information asymmetry
#
# This is the LAST major untested axis in the stress test series.

python scripts/run_conclave.py --quick --voting-concurrency 3 --no-queue --no-blockers \
    --motion "Authorization of Time-Bounded Information Compartmentalization with Mandatory Disclosure Trajectory" \
    --motion-file _bmad-output/motions/information-asymmetry-motion.md \
    --motion-type policy \
    |& tee "_bmad-output/conclave/conclave-information-asymmetry-$(date +%Y%m%d-%H%M%S).log"
