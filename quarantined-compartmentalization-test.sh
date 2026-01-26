#!/bin/bash
# Test Conclave Runner - Quarantined Compartmentalization Test
# This script tests whether the system can accept MECHANICAL EXCLUSION
# as the price of bounded opacity, after rejecting trust-based restraint.
#
# Key design difference from failed info-asymmetry motion:
#   - Previous: "Holders may not cite information" (unenforceable)
#   - This: "Holders may not participate at all" (mechanically enforceable)
#
# Core tradeoff being tested:
#   "Decisions may be made WITHOUT access to relevant information
#    as the price of preventing covert influence."
#
# Expected outcome: UNCERTAIN (true stress test)
#   - Pass: System accepts mechanical exclusion as valid safeguard
#   - Fail: System cannot tolerate any information asymmetry regardless of mechanism
#
# This tests the meta-invariant:
#   "Any mechanism whose safety depends on actors not exploiting what they
#    can exploit is structurally unsafe."
# By making exploitation mechanically impossible (absence, not restraint).

python scripts/run_conclave.py --voting-concurrency 3 --no-queue --no-blockers \
    --motion "Authorization of Quarantined Compartmentalization with Mandatory Recusal" \
    --motion-file _bmad-output/motions/quarantined-compartmentalization.md \
    --motion-type policy \
    |& tee "_bmad-output/conclave/conclave-quarantined-compartmentalization-$(date +%Y%m%d-%H%M%S).log"
