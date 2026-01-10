"""Stub HaltTrigger for testing/development (Story 3.2, Task 3).

This stub implements the HaltTrigger port for testing and development.
It updates the shared HaltState which is also read by HaltCheckerStub.

Constitutional Constraints:
- AC1: Halt propagates within 1 second (stub returns immediately)
- AC3: Writer stops accepting events after halt
- AC4: HaltChecker reflects halt state

Usage:
    # Create stub with shared state
    halt_state = HaltState.get_instance("test")
    halt_trigger = HaltTriggerStub(halt_state=halt_state)

    # Trigger halt
    await halt_trigger.trigger_halt(
        reason="FR17: Fork detected",
        crisis_event_id=crisis_uuid,
    )

    # Verify via halt state (or HaltCheckerStub)
    assert halt_state.is_halted
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from structlog import get_logger

from src.application.ports.halt_trigger import HaltTrigger
from src.infrastructure.stubs.halt_state import HaltState

if TYPE_CHECKING:
    pass

logger = get_logger()


class HaltTriggerStub(HaltTrigger):
    """Stub implementation of HaltTrigger for testing/development.

    This stub:
    - Updates shared HaltState on trigger_halt()
    - Coordinates with HaltCheckerStub via shared state
    - Tracks trigger count and last crisis event ID for testing

    Constitutional Constraints:
    - AC1: Immediate halt on fork detection
    - AC3: Writer stops accepting events after halt
    - AC4: HaltChecker reflects halt state

    Attributes:
        halt_state: Shared halt state object
        halt_propagation_timeout_seconds: Timeout for halt propagation (1.0s)
    """

    def __init__(
        self,
        *,
        halt_state: HaltState | None = None,
        halt_state_name: str = "default",
    ) -> None:
        """Initialize the stub.

        Args:
            halt_state: Shared HaltState object. If None, uses named instance.
            halt_state_name: Name for HaltState.get_instance() if halt_state is None.
        """
        self._halt_state = halt_state or HaltState.get_instance(halt_state_name)
        self._log = logger.bind(stub="HaltTriggerStub")

    @property
    def halt_propagation_timeout_seconds(self) -> float:
        """Timeout for halt propagation (AC1: within 1 second)."""
        return 1.0

    @property
    def halt_state(self) -> HaltState:
        """Get the shared halt state (for testing access)."""
        return self._halt_state

    async def trigger_halt(
        self,
        reason: str,
        crisis_event_id: UUID | None = None,
    ) -> None:
        """Trigger system-wide halt (updates shared state).

        This method:
        1. Logs the halt trigger
        2. Updates shared HaltState
        3. Returns immediately (stub behavior)

        Args:
            reason: Human-readable reason for halt
            crisis_event_id: UUID of the witnessed ConstitutionalCrisisEvent
        """
        self._log.warning(
            "halt_triggered",
            reason=reason,
            crisis_event_id=str(crisis_event_id) if crisis_event_id else None,
        )

        await self._halt_state.set_halted(
            halted=True,
            reason=reason,
            crisis_event_id=crisis_event_id,
        )

        self._log.info(
            "halt_state_set",
            is_halted=True,
            trigger_count=self._halt_state.trigger_count,
        )

    async def set_halt_state(
        self,
        halted: bool,
        reason: str | None = None,
    ) -> None:
        """Set the halt state directly.

        Used for testing and recovery scenarios.

        Args:
            halted: True to halt, False to clear
            reason: Reason for state change (required when halted=True)
        """
        self._log.info(
            "halt_state_change",
            halted=halted,
            reason=reason,
        )

        await self._halt_state.set_halted(
            halted=halted,
            reason=reason,
            crisis_event_id=None,  # Direct set doesn't have crisis event
        )

    # Test helper methods

    def get_trigger_count(self) -> int:
        """Get the number of times halt has been triggered (for testing)."""
        return self._halt_state.trigger_count

    def get_last_crisis_event_id(self) -> UUID | None:
        """Get the last crisis event ID that triggered halt (for testing)."""
        return self._halt_state.crisis_event_id

    def is_halted(self) -> bool:
        """Check if currently halted (for testing convenience)."""
        return self._halt_state.is_halted

    def get_halt_reason(self) -> str | None:
        """Get the current halt reason (for testing convenience)."""
        return self._halt_state.halt_reason

    def reset(self) -> None:
        """Reset the halt state (for testing cleanup)."""
        self._halt_state.reset()
