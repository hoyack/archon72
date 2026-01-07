"""RecoveryWaitingPeriod domain model for 48-hour recovery waiting period (Story 3.6, FR21).

This module provides the RecoveryWaitingPeriod value object that represents
an active recovery waiting period. The 48-hour duration is a constitutional
floor that cannot be reduced.

Constitutional Constraints:
- FR21: Mandatory 48-hour waiting period with public notification
- NFR41: Minimum 48 hours (constitutional floor)
- CT-11: Silent failure destroys legitimacy → Process must be publicly visible
- CT-13: Integrity outranks availability → 48-hour delay prioritizes integrity

Usage:
    period = RecoveryWaitingPeriod.start(
        crisis_event_id=crisis_id,
        initiated_by=("keeper-001", "keeper-002"),
    )

    if period.is_elapsed():
        # Recovery can proceed
        pass
    else:
        remaining = period.remaining_time()
        # Reject early recovery with remaining time
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from src.domain.errors.recovery import RecoveryWaitingPeriodNotElapsedError

# Constitutional floor - cannot be reduced (NFR41)
WAITING_PERIOD_HOURS: int = 48


@dataclass(frozen=True, eq=True)
class RecoveryWaitingPeriod:
    """48-hour recovery waiting period (FR21, NFR41).

    Represents an active recovery waiting period. The 48-hour duration
    is a constitutional floor that cannot be reduced.

    This is a pure domain value object with no I/O dependencies.
    Time calculations accept optional current_time for testability.

    Constitutional Constraints:
    - FR21: Mandatory 48-hour waiting period with public notification
    - NFR41: Minimum 48 hours (constitutional floor)
    - CT-11: Process must be publicly visible

    Attributes:
        started_at: When recovery process was initiated (UTC).
        ends_at: When 48-hour period expires (UTC).
        crisis_event_id: Reference to the triggering crisis/fork event.
        initiated_by: Tuple of Keeper IDs who initiated recovery.
    """

    started_at: datetime
    ends_at: datetime
    crisis_event_id: UUID
    initiated_by: tuple[str, ...]

    @classmethod
    def start(
        cls,
        crisis_event_id: UUID,
        initiated_by: tuple[str, ...],
        started_at: Optional[datetime] = None,
    ) -> RecoveryWaitingPeriod:
        """Factory to start a new 48-hour waiting period.

        Args:
            crisis_event_id: The fork/crisis that triggered recovery.
            initiated_by: Tuple of Keeper IDs who initiated recovery.
            started_at: Override start time (for testing). Defaults to now (UTC).

        Returns:
            New RecoveryWaitingPeriod with 48-hour window.
        """
        start = started_at or datetime.now(timezone.utc)
        end = start + timedelta(hours=WAITING_PERIOD_HOURS)
        return cls(
            started_at=start,
            ends_at=end,
            crisis_event_id=crisis_event_id,
            initiated_by=initiated_by,
        )

    def is_elapsed(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the 48-hour period has elapsed.

        Args:
            current_time: Override current time (for testing). Defaults to now (UTC).

        Returns:
            True if period has elapsed (current_time >= ends_at), False otherwise.
        """
        now = current_time or datetime.now(timezone.utc)
        return now >= self.ends_at

    def remaining_time(self, current_time: Optional[datetime] = None) -> timedelta:
        """Get remaining time in waiting period.

        Args:
            current_time: Override current time (for testing). Defaults to now (UTC).

        Returns:
            Remaining time. Returns timedelta(0) if already elapsed (never negative).
        """
        now = current_time or datetime.now(timezone.utc)
        remaining = self.ends_at - now
        return max(remaining, timedelta(0))

    def check_elapsed(self, current_time: Optional[datetime] = None) -> None:
        """Verify the 48-hour period has elapsed, raise error if not.

        This method enforces the constitutional waiting period requirement.
        Use this before allowing recovery completion.

        Args:
            current_time: Override current time (for testing). Defaults to now (UTC).

        Returns:
            None if period has elapsed.

        Raises:
            RecoveryWaitingPeriodNotElapsedError: If 48 hours have not elapsed.
                Error message includes remaining time per AC3.
        """
        if not self.is_elapsed(current_time):
            remaining = self.remaining_time(current_time)
            raise RecoveryWaitingPeriodNotElapsedError(
                f"FR21: 48-hour waiting period not elapsed. Remaining: {remaining}"
            )
