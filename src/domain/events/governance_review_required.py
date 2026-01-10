"""Governance review required event payload (Story 5.5, RT-3).

This module defines the GovernanceReviewRequiredPayload for governance review events.
A governance review is triggered when override count exceeds 20 in 365-day window.

Constitutional Constraints:
- RT-3: >20 overrides in 365-day window triggers governance review
- CT-11: Silent failure destroys legitimacy -> Event must be logged
- CT-12: Witnessing creates accountability -> GovernanceReviewRequired MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before analysis
2. WITNESS EVERYTHING - All events must be witnessed
3. FAIL LOUD - Failed event write = analysis failure
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

# Event type constant for governance review required
GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE: str = "override.governance_review_required"

# RT-3 threshold constants
RT3_THRESHOLD: int = 20
RT3_WINDOW_DAYS: int = 365


@dataclass(frozen=True, eq=True)
class GovernanceReviewRequiredPayload:
    """Payload for governance review required events (RT-3).

    A GovernanceReviewRequiredPayload is created when the override count
    exceeds the RT-3 threshold (>20 overrides in 365-day window).
    This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - RT-3: >20 overrides in 365-day window triggers governance review
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        override_count: Total override count in the window.
        window_days: Analysis window in days (365 for RT-3).
        threshold: The threshold that was exceeded.
        detected_at: When the threshold breach was detected (UTC).
    """

    override_count: int
    window_days: int
    threshold: int
    detected_at: datetime

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": "GovernanceReviewRequired",
                "override_count": self.override_count,
                "window_days": self.window_days,
                "threshold": self.threshold,
                "detected_at": self.detected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
