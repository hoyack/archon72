"""Shared halt state for stub coordination (Story 3.2, Task 5).

This module provides a shared HaltState object that coordinates between
HaltCheckerStub and HaltTriggerStub, ensuring they see the same halt state.

Constitutional Constraints:
- AC4: When halt is triggered, HaltChecker.is_halted() must return True
- AC4: HaltChecker.get_halt_reason() must return the crisis details

Thread Safety:
- Uses asyncio.Lock for async-safe state updates
- All reads/writes are protected by the lock

Usage:
    # Get or create a named halt state (for test isolation)
    halt_state = HaltState.get_instance("test-1")

    # Set halt state
    await halt_state.set_halted(True, "FR17: Fork detected", crisis_id)

    # Read halt state
    if halt_state.is_halted:
        print(halt_state.halt_reason)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    pass


class HaltState:
    """Shared halt state for stub coordination.

    This class maintains the halt state that is shared between
    HaltCheckerStub (reads) and HaltTriggerStub (writes).

    Thread Safety:
    - Uses asyncio.Lock for async-safe updates
    - Properties are read-only (no async lock needed for reads)

    Instance Management:
    - get_instance(name) returns a named instance (for test isolation)
    - reset_all() clears all instances (for test cleanup)

    Attributes:
        is_halted: Current halt state
        halt_reason: Reason for current halt (if halted)
        crisis_event_id: UUID of triggering crisis event (if halted)
        trigger_count: Number of times halt has been triggered
    """

    # Registry of named instances for test isolation
    _instances: dict[str, HaltState] = {}

    def __init__(self) -> None:
        """Initialize the halt state."""
        self._is_halted = False
        self._halt_reason: str | None = None
        self._crisis_event_id: UUID | None = None
        self._trigger_count = 0
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls, name: str = "default") -> HaltState:
        """Get or create a named HaltState instance.

        Named instances allow test isolation - each test can use
        its own HaltState without affecting other tests.

        Args:
            name: Instance name (default: "default")

        Returns:
            The HaltState instance for the given name.
        """
        if name not in cls._instances:
            cls._instances[name] = cls()
        return cls._instances[name]

    @classmethod
    def reset_all(cls) -> None:
        """Reset all instances (for test cleanup)."""
        cls._instances.clear()

    @classmethod
    def reset_instance(cls, name: str = "default") -> None:
        """Reset a specific named instance.

        Args:
            name: Instance name to reset.
        """
        if name in cls._instances:
            del cls._instances[name]

    @property
    def is_halted(self) -> bool:
        """Check if system is halted."""
        return self._is_halted

    @property
    def halt_reason(self) -> str | None:
        """Get the halt reason (None if not halted)."""
        return self._halt_reason

    @property
    def crisis_event_id(self) -> UUID | None:
        """Get the crisis event ID that triggered halt (None if not halted)."""
        return self._crisis_event_id

    @property
    def trigger_count(self) -> int:
        """Get number of times halt has been triggered."""
        return self._trigger_count

    async def set_halted(
        self,
        halted: bool,
        reason: str | None = None,
        crisis_event_id: UUID | None = None,
    ) -> None:
        """Set the halt state (async-safe).

        Args:
            halted: New halt state
            reason: Reason for halt (required if halted=True)
            crisis_event_id: UUID of triggering crisis event

        Raises:
            ValueError: If halted=True but no reason provided
        """
        if halted and not reason:
            msg = "Reason required when setting halted=True"
            raise ValueError(msg)

        async with self._lock:
            # Track trigger count (only increment on new halts)
            if halted and not self._is_halted:
                self._trigger_count += 1

            self._is_halted = halted
            self._halt_reason = reason if halted else None
            self._crisis_event_id = crisis_event_id if halted else None

    def set_halted_sync(
        self,
        halted: bool,
        reason: str | None = None,
        crisis_event_id: UUID | None = None,
    ) -> None:
        """Set the halt state (synchronous, for testing).

        This method is provided for test setup where async is not
        convenient. For production code, use set_halted().

        Args:
            halted: New halt state
            reason: Reason for halt (required if halted=True)
            crisis_event_id: UUID of triggering crisis event

        Raises:
            ValueError: If halted=True but no reason provided
        """
        if halted and not reason:
            msg = "Reason required when setting halted=True"
            raise ValueError(msg)

        # Track trigger count (only increment on new halts)
        if halted and not self._is_halted:
            self._trigger_count += 1

        self._is_halted = halted
        self._halt_reason = reason if halted else None
        self._crisis_event_id = crisis_event_id if halted else None

    def reset(self) -> None:
        """Reset state to not halted (for testing)."""
        self._is_halted = False
        self._halt_reason = None
        self._crisis_event_id = None
        self._trigger_count = 0
