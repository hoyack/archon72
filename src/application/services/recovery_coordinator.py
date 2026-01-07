"""Recovery Coordinator application service (Story 3.6, FR21).

This application service coordinates the 48-hour recovery waiting period.
It orchestrates the recovery process while enforcing constitutional constraints.

Constitutional Constraints:
- FR21: Mandatory 48-hour waiting period with public notification
- FR22: Unanimous Keeper agreement required for completion
- NFR41: Minimum 48 hours (constitutional floor)
- CT-11: Silent failure destroys legitimacy -> Process must be tracked
- CT-13: Integrity outranks availability -> Time is constitutional

Developer Golden Rules:
1. TIME IS CONSTITUTIONAL - 48 hours is a floor, not negotiable
2. HALT FIRST - Recovery requires prior halt
3. WITNESS EVERYTHING - State changes create audit trail
4. FAIL LOUD - Early recovery attempts must fail clearly with remaining time
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import structlog

from src.domain.errors.recovery import RecoveryNotPermittedError
from src.domain.events.recovery_waiting_period_started import (
    RecoveryWaitingPeriodStartedPayload,
)

if TYPE_CHECKING:
    from src.application.ports.halt_checker import HaltChecker
    from src.application.ports.recovery_waiting_period import RecoveryWaitingPeriodPort
    from src.domain.events.recovery_completed import RecoveryCompletedPayload
    from src.domain.models.ceremony_evidence import CeremonyEvidence

log = structlog.get_logger()


class RecoveryCoordinator:
    """Coordinates 48-hour recovery waiting period (FR21, FR22).

    This application service orchestrates the recovery process:
    1. Validates halt state before allowing initiation
    2. Starts 48-hour waiting period
    3. Rejects early recovery with remaining time
    4. Completes recovery with ceremony evidence

    Constitutional Constraints:
    - FR21: 48-hour waiting period with public notification
    - FR22: Unanimous Keeper agreement for completion
    - NFR41: Minimum 48 hours (constitutional floor)
    - AC1: Timer starts when Keepers initiate recovery
    - AC2: Recovery only after 48 hours
    - AC3: Early rejection includes remaining time
    - AC4: Completion creates audit trail event

    Example:
        >>> coordinator = RecoveryCoordinator(halt_checker, recovery_port)
        >>>
        >>> # Initiate recovery (starts 48-hour timer)
        >>> payload = await coordinator.initiate_recovery(
        ...     crisis_event_id=crisis_id,
        ...     initiated_by=("keeper-001", "keeper-002"),
        ... )
        >>>
        >>> # Later, attempt completion
        >>> try:
        ...     result = await coordinator.complete_recovery(ceremony)
        ... except RecoveryWaitingPeriodNotElapsedError as e:
        ...     print(f"Must wait: {e}")  # Includes remaining time
    """

    def __init__(
        self,
        halt_checker: "HaltChecker",
        recovery_port: "RecoveryWaitingPeriodPort",
    ) -> None:
        """Initialize RecoveryCoordinator.

        Args:
            halt_checker: Port for checking halt state.
            recovery_port: Port for recovery waiting period storage.
        """
        self._halt_checker = halt_checker
        self._recovery_port = recovery_port
        self._log = log.bind(service="recovery_coordinator")

    async def initiate_recovery(
        self,
        crisis_event_id: UUID,
        initiated_by: tuple[str, ...],
    ) -> RecoveryWaitingPeriodStartedPayload:
        """Initiate 48-hour recovery waiting period (AC1).

        Starts the constitutional waiting period. Recovery can only
        proceed after 48 hours have elapsed.

        Constitutional Constraint (FR21, AC1):
        - System must be in halted state
        - Timer starts immediately
        - Public notification should be sent (caller responsibility)

        Args:
            crisis_event_id: UUID of the crisis/fork event triggering recovery.
            initiated_by: Tuple of Keeper IDs who initiated recovery.

        Returns:
            RecoveryWaitingPeriodStartedPayload for the started event.

        Raises:
            RecoveryNotPermittedError: If system is not halted.
            RecoveryAlreadyInProgressError: If a waiting period is already active.
        """
        # Validate halt state
        is_halted = await self._halt_checker.is_halted()
        if not is_halted:
            self._log.warning(
                "recovery_initiation_rejected",
                reason="system_not_halted",
                fr="FR21",
            )
            raise RecoveryNotPermittedError(
                "Cannot initiate recovery - system not halted"
            )

        # Start waiting period (port validates no existing period)
        period = await self._recovery_port.start_waiting_period(
            crisis_event_id=crisis_event_id,
            initiated_by=initiated_by,
        )

        self._log.info(
            "recovery_waiting_period_started",
            crisis_event_id=str(crisis_event_id),
            initiated_by=list(initiated_by),
            ends_at=period.ends_at.isoformat(),
            fr="FR21",
        )

        # Return payload for event creation
        return RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=period.crisis_event_id,
            started_at=period.started_at,
            ends_at=period.ends_at,
            initiated_by_keepers=period.initiated_by,
            public_notification_sent=True,  # Caller should send notification
        )

    async def complete_recovery(
        self,
        ceremony_evidence: "CeremonyEvidence",
    ) -> "RecoveryCompletedPayload":
        """Complete recovery after 48-hour waiting period (AC2, AC4).

        Completes the recovery process if 48 hours have elapsed.
        Requires valid ceremony evidence from Keepers.

        Constitutional Constraint (FR21, FR22):
        - System must still be halted (recovery only meaningful during halt)
        - 48-hour period must have elapsed (NFR41)
        - Unanimous Keeper agreement required (FR22)
        - Creates audit trail via RecoveryCompletedEvent

        Args:
            ceremony_evidence: CeremonyEvidence proving Keeper ceremony.

        Returns:
            RecoveryCompletedPayload for the completion event.

        Raises:
            RecoveryNotPermittedError: If system is not halted.
            RecoveryWaitingPeriodNotStartedError: If no active waiting period.
            RecoveryWaitingPeriodNotElapsedError: If 48 hours not elapsed (AC3).
                Error includes remaining time.
            InvalidCeremonyError: If ceremony evidence is invalid.
        """
        # Validate halt state - recovery only meaningful when halted (M1 safety check)
        is_halted = await self._halt_checker.is_halted()
        if not is_halted:
            self._log.warning(
                "recovery_completion_rejected",
                reason="system_not_halted",
                fr="FR21",
            )
            raise RecoveryNotPermittedError(
                "Cannot complete recovery - system not halted"
            )

        # Delegate to port (handles time validation and error messages)
        payload = await self._recovery_port.complete_waiting_period(
            ceremony_evidence=ceremony_evidence,
        )

        self._log.info(
            "recovery_completed",
            crisis_event_id=str(payload.crisis_event_id),
            ceremony_id=str(payload.keeper_ceremony_id),
            approving_keepers=list(payload.approving_keepers),
            fr="FR21",
        )

        return payload

    async def get_recovery_status(self) -> dict[str, Any]:
        """Get current recovery waiting period status.

        Provides status information for monitoring and display.
        Includes remaining time for countdown displays.

        Returns:
            Dictionary with:
            - active: Whether a waiting period is active
            - remaining_time: Remaining time as ISO string, or None
            - crisis_event_id: Crisis ID as string, or None
            - started_at: Start time as ISO string, or None
            - ends_at: End time as ISO string, or None
        """
        period = await self._recovery_port.get_active_waiting_period()

        if not period:
            return {
                "active": False,
                "remaining_time": None,
                "crisis_event_id": None,
                "started_at": None,
                "ends_at": None,
            }

        remaining = await self._recovery_port.get_remaining_time()

        return {
            "active": True,
            "remaining_time": str(remaining) if remaining else None,
            "crisis_event_id": str(period.crisis_event_id),
            "started_at": period.started_at.isoformat(),
            "ends_at": period.ends_at.isoformat(),
        }

    async def can_complete_recovery(self) -> bool:
        """Check if recovery can be completed now.

        Convenience method for UI/API to check if completion is possible
        without attempting it.

        Returns:
            True if 48 hours have elapsed and recovery can proceed.
            False if no active period or time not elapsed.
        """
        return await self._recovery_port.is_waiting_period_elapsed()

    async def get_remaining_time(self) -> Optional[timedelta]:
        """Get remaining time in waiting period.

        Convenience method for countdown displays.

        Returns:
            Remaining time if active period exists, None otherwise.
        """
        return await self._recovery_port.get_remaining_time()
