"""Recovery Waiting Period port (Story 3.6, FR21).

This port defines the contract for recovery waiting period storage.
Implementations manage the state of the 48-hour waiting period.

Constitutional Constraints:
- FR21: Mandatory 48-hour waiting period with public notification
- NFR41: Minimum 48 hours (constitutional floor)
- CT-11: Silent failure destroys legitimacy -> Process must be tracked
- CT-13: Integrity outranks availability -> Time is constitutional

Developer Golden Rules:
1. TIME IS CONSTITUTIONAL - 48 hours is a floor, not negotiable
2. WITNESS EVERYTHING - State changes create audit trail
3. FAIL LOUD - Early recovery attempts must fail clearly
"""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import TYPE_CHECKING, Optional
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.recovery_completed import RecoveryCompletedPayload
    from src.domain.models.ceremony_evidence import CeremonyEvidence
    from src.domain.models.recovery_waiting_period import RecoveryWaitingPeriod


class RecoveryWaitingPeriodPort(ABC):
    """Abstract interface for recovery waiting period storage.

    This port defines the contract for managing the 48-hour recovery
    waiting period state. Implementations are responsible for:
    - Persisting waiting period state
    - Tracking elapsed time
    - Validating ceremony completion

    Constitutional Constraints:
    - FR21: 48-hour waiting period with public notification
    - FR22: Unanimous Keeper agreement for completion
    - NFR41: Minimum 48 hours (constitutional floor)

    Example:
        >>> # Start waiting period
        >>> period = await port.start_waiting_period(
        ...     crisis_event_id=crisis_id,
        ...     initiated_by=("keeper-001", "keeper-002"),
        ... )
        >>> # Check if elapsed
        >>> if await port.is_waiting_period_elapsed():
        ...     # Proceed with recovery
        ...     pass
    """

    @abstractmethod
    async def start_waiting_period(
        self,
        crisis_event_id: UUID,
        initiated_by: tuple[str, ...],
    ) -> "RecoveryWaitingPeriod":
        """Start a new 48-hour recovery waiting period.

        Creates and persists a new waiting period linked to the crisis.
        Only one waiting period can be active at a time.

        Constitutional Constraint (FR21, AC1):
        - Timer starts when Keepers initiate recovery
        - Period lasts exactly 48 hours (NFR41)
        - Public notification should be sent (handled by coordinator)

        Args:
            crisis_event_id: UUID of the crisis/fork event triggering recovery.
            initiated_by: Tuple of Keeper IDs who initiated recovery.

        Returns:
            The newly created RecoveryWaitingPeriod.

        Raises:
            RecoveryAlreadyInProgressError: If a waiting period is already active.
        """
        ...

    @abstractmethod
    async def get_active_waiting_period(self) -> Optional["RecoveryWaitingPeriod"]:
        """Get the currently active waiting period, if any.

        Returns:
            The active RecoveryWaitingPeriod, or None if no active period.
        """
        ...

    @abstractmethod
    async def is_waiting_period_elapsed(self) -> bool:
        """Check if the active waiting period has elapsed.

        Convenience method that combines get + is_elapsed check.

        Returns:
            True if an active period exists AND has elapsed.
            False if no active period OR period has not elapsed.
        """
        ...

    @abstractmethod
    async def get_remaining_time(self) -> Optional[timedelta]:
        """Get remaining time in the active waiting period.

        Used for displaying remaining time when early recovery is rejected (AC3).

        Returns:
            The remaining time if active period exists.
            timedelta(0) if period has elapsed.
            None if no active period.
        """
        ...

    @abstractmethod
    async def complete_waiting_period(
        self,
        ceremony_evidence: "CeremonyEvidence",
    ) -> "RecoveryCompletedPayload":
        """Complete the waiting period with ceremony evidence.

        Marks the waiting period as completed and returns the completion
        payload for the RecoveryCompletedEvent.

        Constitutional Constraint (FR22, AC4):
        - Requires unanimous Keeper agreement
        - 48-hour period must have elapsed
        - Creates audit trail via event

        Args:
            ceremony_evidence: CeremonyEvidence proving Keeper ceremony.
                              Must have valid signatures.

        Returns:
            RecoveryCompletedPayload for the completion event.

        Raises:
            RecoveryWaitingPeriodNotStartedError: If no active waiting period.
            RecoveryWaitingPeriodNotElapsedError: If 48 hours not elapsed.
            InvalidCeremonyError: If ceremony evidence is invalid.
            InsufficientApproversError: If < 2 Keepers approved.
        """
        ...
