"""Recovery Waiting Period Stub for testing/development (Story 3.6, Task 7).

This stub provides a simplified RecoveryWaitingPeriodPort implementation
for testing scenarios without needing real persistence.

The stub allows direct control of state for testing:
- set_elapsed(): Control whether period is considered elapsed
- reset(): Clear all state

Usage:
    stub = RecoveryWaitingPeriodStub()

    # Start waiting period
    await stub.start_waiting_period(crisis_id, ("keeper-001",))

    # Check elapsed (normally False)
    await stub.is_waiting_period_elapsed()  # False

    # Force elapsed for testing
    stub.set_elapsed(True)
    await stub.is_waiting_period_elapsed()  # True

WARNING: This stub is NOT for production use.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog

from src.application.ports.recovery_waiting_period import RecoveryWaitingPeriodPort
from src.domain.errors.recovery import (
    RecoveryAlreadyInProgressError,
    RecoveryWaitingPeriodNotElapsedError,
    RecoveryWaitingPeriodNotStartedError,
)
from src.domain.events.recovery_completed import RecoveryCompletedPayload
from src.domain.models.ceremony_evidence import CeremonyEvidence
from src.domain.models.recovery_waiting_period import RecoveryWaitingPeriod

log = structlog.get_logger(__name__)


class RecoveryWaitingPeriodStub(RecoveryWaitingPeriodPort):
    """Stub implementation of RecoveryWaitingPeriodPort for testing.

    Provides in-memory storage of waiting period state with
    helper methods for controlling test scenarios.

    The stub supports:
    - Starting and tracking waiting periods
    - Forcing elapsed state for testing completion flows
    - Resetting state between tests

    Example:
        >>> stub = RecoveryWaitingPeriodStub()
        >>> await stub.start_waiting_period(crisis_id, ("keeper-001",))
        >>> await stub.is_waiting_period_elapsed()  # False
        >>> stub.set_elapsed(True)
        >>> await stub.is_waiting_period_elapsed()  # True
    """

    def __init__(self) -> None:
        """Initialize stub with empty state."""
        self._active_period: RecoveryWaitingPeriod | None = None
        self._force_elapsed: bool = False
        self._start_count: int = 0
        self._complete_count: int = 0

    async def start_waiting_period(
        self,
        crisis_event_id: UUID,
        initiated_by: tuple[str, ...],
    ) -> RecoveryWaitingPeriod:
        """Start a new 48-hour recovery waiting period.

        Args:
            crisis_event_id: UUID of the crisis/fork event.
            initiated_by: Tuple of Keeper IDs.

        Returns:
            The newly created RecoveryWaitingPeriod.

        Raises:
            RecoveryAlreadyInProgressError: If a period is already active.
        """
        if self._active_period is not None:
            log.info(
                "stub_recovery_already_in_progress",
                existing_crisis=str(self._active_period.crisis_event_id),
            )
            raise RecoveryAlreadyInProgressError(
                f"Recovery already in progress, ends at {self._active_period.ends_at}"
            )

        self._start_count += 1
        self._active_period = RecoveryWaitingPeriod.start(
            crisis_event_id=crisis_event_id,
            initiated_by=initiated_by,
        )

        log.info(
            "stub_waiting_period_started",
            crisis_event_id=str(crisis_event_id),
            initiated_by=list(initiated_by),
            ends_at=self._active_period.ends_at.isoformat(),
        )

        return self._active_period

    async def get_active_waiting_period(self) -> RecoveryWaitingPeriod | None:
        """Get the currently active waiting period, if any.

        Returns:
            The active RecoveryWaitingPeriod, or None.
        """
        return self._active_period

    async def is_waiting_period_elapsed(self) -> bool:
        """Check if the active waiting period has elapsed.

        Returns True if:
        - An active period exists AND
        - Either force_elapsed is True OR period.is_elapsed() is True

        Returns:
            True if period exists and has elapsed.
        """
        if self._active_period is None:
            return False

        if self._force_elapsed:
            return True

        return self._active_period.is_elapsed()

    async def get_remaining_time(self) -> timedelta | None:
        """Get remaining time in the active waiting period.

        Returns:
            Remaining time if active, timedelta(0) if elapsed, None if no period.
        """
        if self._active_period is None:
            return None

        if self._force_elapsed:
            return timedelta(0)

        return self._active_period.remaining_time()

    async def complete_waiting_period(
        self,
        ceremony_evidence: CeremonyEvidence,
    ) -> RecoveryCompletedPayload:
        """Complete the waiting period with ceremony evidence.

        Args:
            ceremony_evidence: CeremonyEvidence proving Keeper ceremony.

        Returns:
            RecoveryCompletedPayload for the completion event.

        Raises:
            RecoveryWaitingPeriodNotStartedError: If no active period.
            RecoveryWaitingPeriodNotElapsedError: If period not elapsed.
        """
        if self._active_period is None:
            log.info("stub_no_active_period")
            raise RecoveryWaitingPeriodNotStartedError(
                "No recovery waiting period active"
            )

        if not await self.is_waiting_period_elapsed():
            remaining = await self.get_remaining_time()
            log.info(
                "stub_period_not_elapsed",
                remaining=str(remaining),
            )
            raise RecoveryWaitingPeriodNotElapsedError(
                f"FR21: 48-hour waiting period not elapsed. Remaining: {remaining}"
            )

        self._complete_count += 1
        completed_at = datetime.now(timezone.utc)

        payload = RecoveryCompletedPayload(
            crisis_event_id=self._active_period.crisis_event_id,
            waiting_period_started_at=self._active_period.started_at,
            recovery_completed_at=completed_at,
            keeper_ceremony_id=ceremony_evidence.ceremony_id,
            approving_keepers=ceremony_evidence.get_keeper_ids(),
        )

        log.info(
            "stub_waiting_period_completed",
            crisis_event_id=str(payload.crisis_event_id),
            ceremony_id=str(payload.keeper_ceremony_id),
        )

        # Clear the active period
        self._active_period = None
        self._force_elapsed = False

        return payload

    # Test helper methods

    def set_elapsed(self, elapsed: bool) -> None:
        """Force elapsed state for testing.

        Args:
            elapsed: Whether to consider period elapsed.
        """
        log.info("stub_set_elapsed", elapsed=elapsed)
        self._force_elapsed = elapsed

    def reset(self) -> None:
        """Reset stub to initial state."""
        log.info("stub_reset")
        self._active_period = None
        self._force_elapsed = False
        self._start_count = 0
        self._complete_count = 0

    def get_start_count(self) -> int:
        """Get number of times start was called.

        Returns:
            Number of start_waiting_period calls.
        """
        return self._start_count

    def get_complete_count(self) -> int:
        """Get number of times complete was called.

        Returns:
            Number of complete_waiting_period calls.
        """
        return self._complete_count
