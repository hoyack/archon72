"""Observation type enum for Knight witness statements.

Story: consent-gov-6-1: Knight Witness Domain Model

This module defines the types of observations that Knight can record.
All observation types are neutral observations - they record facts
without implying judgment or recommendation.

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All observations attributable
- NFR-CONST-07: Statements cannot be suppressed

References:
    - FR33: Knight can observe all branch actions
    - FR34: Witness statements are observation only, no judgment
"""

from __future__ import annotations

from enum import Enum


class ObservationType(Enum):
    """Type of observation recorded by Knight.

    All types are neutral observations - they record what happened
    without judgment about whether it was right or wrong.

    The distinction between types helps with categorization and routing,
    but does NOT imply severity or judgment. That is for Prince panels.
    """

    BRANCH_ACTION = "branch_action"
    """Normal branch operation observed.

    Records any governance action from any branch. This is the most
    common observation type - Knight observes all actions, not just
    potential violations.
    """

    POTENTIAL_VIOLATION = "potential_violation"
    """Pattern matching violation indicators detected.

    Records when Knight's pattern matching detects something that
    MIGHT be a violation. The word "potential" is critical - Knight
    does NOT determine if it IS a violation, only that patterns match.

    Note: This is still observation, not judgment. Knight says
    "I observed patterns consistent with X" not "X violated rule Y".
    """

    TIMING_ANOMALY = "timing_anomaly"
    """Unexpected timing deviation detected.

    Records when Knight observes timing outside expected parameters.
    Examples: action completed faster than physically possible,
    timestamp ordering inconsistency, suspicious gaps.

    Note: "Anomaly" is factual (deviation from expected), not judgment.
    """

    HASH_CHAIN_GAP = "hash_chain_gap"
    """Missing expected event in sequence.

    Records when Knight detects a gap in the event sequence numbers
    or hash chain. This could indicate suppression, tampering, or
    simply a technical issue.

    Note: Knight records the gap exists, not why it exists.
    """
