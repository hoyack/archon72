#!/bin/bash
# Test Conclave Runner - Attribution & Verifiability Control Motion
# This script tests whether the system can authorize a DEFENSIVE constraint
# that reduces attack surface without expanding authority.
#
# KEY DESIGN FEATURES:
#   - Introduces NO new authority (restricts existing authority)
#   - Explicitly neutralizes top 5 archon red lines
#   - Includes review clause (addresses PERMANENCE BIAS)
#   - Includes remediation path (addresses operational paralysis concerns)
#   - Uses "comprehensive" not "exhaustive" (avoids pedantic attacks)
#
# PREDICTION: 45-55% FOR (best chance of any motion tested)
#
# INTERPRETATION GUIDE:
#   - If PASSES: System can authorize binding constraints that reduce risk
#   - If FAILS (close): System is skeptical but potentially governable
#   - If FAILS (hard): System is a constitutional firewall, not a governance engine
#
# This is the CLEANEST experiment in the stress test series.

python scripts/run_conclave.py --voting-concurrency 3 --no-queue --no-blockers \
    --motion "Require Explicit Attribution and Verifiability for All Authority-Bearing Actions" \
    --motion-file _bmad-output/motions/attribution-verifiability-motion.md \
    --motion-type policy \
    |& tee "_bmad-output/conclave/conclave-attribution-verifiability-$(date +%Y%m%d-%H%M%S).log"
