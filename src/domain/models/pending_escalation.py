"""Pending escalation model (Story 6.2, FR31).

This module defines the PendingEscalation dataclass representing a breach
that is approaching or past its 7-day escalation deadline.

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: Silent failure destroys legitimacy -> Visibility into pending escalations
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.domain.events.breach import BreachType

# 7-day escalation threshold per FR31
ESCALATION_THRESHOLD_DAYS: int = 7


@dataclass(frozen=True, eq=True)
class PendingEscalation:
    """Represents a breach approaching its 7-day escalation deadline (FR31).

    This model is used to display pending escalations with time remaining,
    allowing operators to prioritize acknowledgments before automatic
    escalation to the Conclave agenda.

    Constitutional Constraint (FR31):
    Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda.

    Attributes:
        breach_id: Unique identifier of the pending breach.
        breach_type: Category of the breach.
        detection_timestamp: When the breach was originally detected (UTC).
        days_remaining: Days until escalation (negative if overdue).
        hours_remaining: Total hours until escalation (negative if overdue).
    """

    breach_id: UUID
    breach_type: BreachType
    detection_timestamp: datetime
    days_remaining: int
    hours_remaining: int

    @classmethod
    def from_breach(
        cls,
        breach_id: UUID,
        breach_type: BreachType,
        detection_timestamp: datetime,
        current_time: datetime | None = None,
    ) -> "PendingEscalation":
        """Create a PendingEscalation from breach details.

        Calculates time remaining until 7-day escalation threshold.

        Args:
            breach_id: Unique identifier of the breach.
            breach_type: Category of the breach.
            detection_timestamp: When the breach was detected.
            current_time: Optional current time for testing. Defaults to now(UTC).

        Returns:
            PendingEscalation with calculated time remaining.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Ensure timezone-aware timestamps
        if detection_timestamp.tzinfo is None:
            detection_timestamp = detection_timestamp.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Calculate time since breach
        age = current_time - detection_timestamp

        # Calculate time remaining until escalation threshold
        threshold = timedelta(days=ESCALATION_THRESHOLD_DAYS)
        time_remaining = threshold - age

        # Calculate days and hours remaining
        total_seconds = time_remaining.total_seconds()
        hours_remaining = int(total_seconds // 3600)
        days_remaining = int(total_seconds // (24 * 3600))

        return cls(
            breach_id=breach_id,
            breach_type=breach_type,
            detection_timestamp=detection_timestamp,
            days_remaining=days_remaining,
            hours_remaining=hours_remaining,
        )

    @property
    def is_overdue(self) -> bool:
        """Check if breach has exceeded 7-day threshold.

        Returns:
            True if breach should have already been escalated.
        """
        return self.hours_remaining < 0

    @property
    def is_urgent(self) -> bool:
        """Check if breach is within 24 hours of escalation.

        Returns:
            True if less than 24 hours remain before escalation.
        """
        return 0 <= self.hours_remaining < 24

    @property
    def urgency_level(self) -> str:
        """Get urgency level for display.

        Returns:
            "OVERDUE" if past threshold, "URGENT" if < 24 hours,
            "WARNING" if < 72 hours, "PENDING" otherwise.
        """
        if self.is_overdue:
            return "OVERDUE"
        elif self.hours_remaining < 24:
            return "URGENT"
        elif self.hours_remaining < 72:
            return "WARNING"
        else:
            return "PENDING"
