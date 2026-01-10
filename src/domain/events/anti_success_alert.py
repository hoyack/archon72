"""Anti-success alert event payload (Story 5.5, FR27).

This module defines the AntiSuccessAlertPayload for anti-success alert events.
Anti-success alerts are triggered when override trends indicate potential abuse.

Constitutional Constraints:
- FR27: Override trend analysis with anti-success alerts
- CT-11: Silent failure destroys legitimacy -> Alerts must be logged
- CT-12: Witnessing creates accountability -> AntiSuccessAlert MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before analysis
2. WITNESS EVERYTHING - All alerts must be witnessed
3. FAIL LOUD - Failed alert write = analysis failure
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# Event type constant for anti-success alerts
ANTI_SUCCESS_ALERT_EVENT_TYPE: str = "override.anti_success_alert"


class AlertType(Enum):
    """Types of anti-success alerts (FR27).

    Each alert type represents a different threshold breach pattern.
    """

    PERCENTAGE_INCREASE = "PERCENTAGE_INCREASE"
    """Override count increased >50% compared to previous period."""

    THRESHOLD_30_DAY = "THRESHOLD_30_DAY"
    """More than 5 overrides in any 30-day period."""


@dataclass(frozen=True, eq=True)
class AntiSuccessAlertPayload:
    """Payload for anti-success alert events (FR27).

    An AntiSuccessAlertPayload is created when override trends indicate
    potential abuse patterns. This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - FR27: Override trend analysis with anti-success alerts
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        alert_type: Type of anti-success alert (threshold breach pattern).
        before_count: Override count in the comparison period.
        after_count: Override count in the current period.
        percentage_change: Percentage change from before to after.
        window_days: Analysis window in days.
        detected_at: When the alert was detected (UTC).
    """

    alert_type: AlertType
    before_count: int
    after_count: int
    percentage_change: float
    window_days: int
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
                "event_type": "AntiSuccessAlert",
                "alert_type": self.alert_type.value,
                "before_count": self.before_count,
                "after_count": self.after_count,
                "percentage_change": self.percentage_change,
                "window_days": self.window_days,
                "detected_at": self.detected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
