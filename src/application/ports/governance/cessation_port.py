"""Cessation Port - Abstract interface for cessation operations.

Story: consent-gov-8.1: System Cessation Trigger

This port defines the contract for cessation operations.
Implementations must handle the irreversible nature of cessation.

IMPORTANT: This port intentionally has NO:
- cancel_cessation()
- undo_cessation()
- rollback_cessation()
- resume_operations()

Cessation is IRREVERSIBLE by design.

Constitutional Context:
- FR47: Human Operator can trigger cessation
- FR49: System can block new Motion Seeds on cessation
- FR50: System can halt execution on cessation
- AC6: Cessation trigger is irreversible (no "undo")
"""

from abc import ABC, abstractmethod
from typing import Protocol

from src.domain.governance.cessation import CessationState, CessationTrigger


class CessationPort(ABC):
    """Abstract interface for cessation operations.

    This port provides the minimal interface for cessation:
    - Get current state
    - Record a trigger

    THERE IS INTENTIONALLY NO:
    - cancel_cessation()
    - undo_cessation()
    - rollback_cessation()

    Example Usage:
        >>> cessation_port = get_cessation_port()
        >>> state = await cessation_port.get_state()
        >>> if state.is_active:
        ...     # Safe to trigger
        ...     await cessation_port.record_trigger(trigger)
    """

    @abstractmethod
    async def get_state(self) -> CessationState:
        """Get current cessation state.

        Returns:
            CessationState with status, trigger (if any), and operational flags.
        """
        ...

    @abstractmethod
    async def record_trigger(self, trigger: CessationTrigger) -> None:
        """Record cessation trigger.

        This persists the cessation trigger and transitions the system
        to CESSATION_TRIGGERED status.

        Args:
            trigger: The cessation trigger record.

        Raises:
            CessationAlreadyTriggeredError: If cessation already triggered.
        """
        ...

    @abstractmethod
    async def mark_ceased(self) -> None:
        """Mark system as fully ceased.

        Called when all in-flight operations have completed and
        the system has fully ceased.

        This transitions status from CESSATION_TRIGGERED to CEASED.
        """
        ...

    @abstractmethod
    async def update_in_flight_count(self, count: int) -> None:
        """Update the count of in-flight operations.

        Called as operations complete during graceful shutdown.

        Args:
            count: New count of in-flight operations.
        """
        ...


class MotionBlockerPort(Protocol):
    """Port for blocking new Motion Seeds during cessation.

    When cessation is triggered, new Motion Seeds (pre-admission submissions)
    must be blocked. Existing in-progress motions continue to completion.
    """

    async def block_new_motions(self, reason: str) -> None:
        """Block new Motion Seed submissions.

        Args:
            reason: Reason for blocking (e.g., "cessation_triggered").
        """
        ...

    async def is_blocked(self) -> bool:
        """Check if new Motion Seeds are blocked.

        Returns:
            True if blocked, False otherwise.
        """
        ...

    async def get_block_reason(self) -> str | None:
        """Get the reason for blocking.

        Returns:
            Block reason if blocked, None otherwise.
        """
        ...


class ExecutionHalterPort(Protocol):
    """Port for halting execution during cessation.

    Execution halt is graceful:
    1. Begin halt with grace period
    2. Allow in-flight operations to complete
    3. Force stop after timeout
    """

    async def begin_halt(
        self,
        trigger_id: str,
        grace_period_seconds: int,
    ) -> None:
        """Begin halting execution with grace period.

        Args:
            trigger_id: ID of the cessation trigger.
            grace_period_seconds: Time allowed for graceful completion.
        """
        ...

    async def get_in_flight_count(self) -> int:
        """Get count of in-flight operations.

        Returns:
            Number of operations still in progress.
        """
        ...

    async def is_halt_complete(self) -> bool:
        """Check if halt is complete (all operations finished).

        Returns:
            True if complete, False if operations still in progress.
        """
        ...

    async def force_halt(self) -> int:
        """Force halt remaining operations (after grace period).

        Returns:
            Number of operations that were forcefully stopped.
        """
        ...
