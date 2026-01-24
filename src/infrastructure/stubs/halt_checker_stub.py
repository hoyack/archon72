"""Stub HaltChecker for Epic 1 and Story 3.2/3.3 testing (Story 1.6, Task 2.3).

This stub allows code to check halt state without depending on full Epic 3.
Updated in Story 3.3 to support DualChannelHaltTransport delegation.

Three modes of operation (in priority order):
1. DualChannelHaltTransport mode (Story 3.3): Delegates to dual-channel transport
2. Shared state mode (Story 3.2): Use halt_state parameter for coordination
3. Standalone mode (legacy): Use force_halted parameter for simple testing

Constitutional Constraints:
- AC4: When halt is triggered, is_halted() returns True
- AC4: get_halt_reason() returns the crisis details

ADR-3: Partition Behavior + Halt Durability (Story 3.3)
- DualChannelHaltTransport checks Redis Streams + DB halt flag
- If EITHER channel indicates halt -> is_halted() returns True
- DB is canonical when channels disagree

WARNING: This stub is for development/testing only.
Production should use DualChannelHaltTransport directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.ports.halt_checker import HaltChecker
from src.infrastructure.stubs.halt_state import HaltState

if TYPE_CHECKING:
    from src.application.ports.dual_channel_halt import DualChannelHaltTransport


class HaltCheckerStub(HaltChecker):
    """Stub implementation with multiple modes for halt state checking.

    This stub satisfies the HaltChecker interface with three modes of operation
    (in priority order):
    1. DualChannelHaltTransport mode: Delegates to dual-channel transport (ADR-3)
    2. Shared state mode: Uses HaltState for coordination with HaltTriggerStub
    3. Standalone mode: Uses force_halted for simple testing

    Priority Order:
    - If dual_channel_halt is provided and is_halted(), returns True
    - Else if halt_state.is_halted is True, returns True
    - Else returns force_halted

    Constitutional Constraints:
    - AC4: is_halted() returns True when halt is triggered
    - AC4: get_halt_reason() returns crisis details

    Attributes:
        dual_channel_halt: DualChannelHaltTransport for dual-channel checks
        halt_state: Shared halt state (if using coordination mode)
        force_halted: Force halted state (for standalone testing)
        halt_reason: Reason when force_halted (for standalone testing)
    """

    def __init__(
        self,
        *,
        dual_channel_halt: DualChannelHaltTransport | None = None,
        halt_state: HaltState | None = None,
        halt_state_name: str | None = None,
        is_halted: bool | None = None,
        initial_halted: bool | None = None,
        force_halted: bool = False,
        halt_reason: str | None = None,
    ) -> None:
        """Initialize the stub.

        Args:
            dual_channel_halt: DualChannelHaltTransport to delegate to (preferred).
            halt_state: Shared HaltState for coordination with HaltTriggerStub.
            halt_state_name: If provided and halt_state is None, gets named instance.
            force_halted: If True, is_halted() returns True (standalone mode).
            halt_reason: Reason to return when halted (standalone mode).
        """
        # Legacy aliases for force_halted
        if is_halted is not None:
            force_halted = is_halted
        elif initial_halted is not None:
            force_halted = initial_halted

        # DualChannelHaltTransport mode (highest priority)
        self._dual_channel_halt = dual_channel_halt

        # Resolve halt_state
        if halt_state is not None:
            self._halt_state = halt_state
        elif halt_state_name is not None:
            self._halt_state = HaltState.get_instance(halt_state_name)
        else:
            self._halt_state = None

        # Standalone mode fallback
        self._force_halted = force_halted
        self._halt_reason = halt_reason

    @property
    def dual_channel_halt(self) -> DualChannelHaltTransport | None:
        """Get the dual-channel halt transport (if using dual-channel mode)."""
        return self._dual_channel_halt

    @property
    def halt_state(self) -> HaltState | None:
        """Get the shared halt state (if using coordination mode)."""
        return self._halt_state

    async def is_halted(self) -> bool:
        """Check if system is halted.

        Checks in priority order:
        1. DualChannelHaltTransport.is_halted() (if provided)
        2. Shared halt_state.is_halted (coordination mode)
        3. force_halted (standalone mode)

        Returns:
            True if halted via any mode, False otherwise.
        """
        # Check dual-channel first (highest priority)
        if self._dual_channel_halt is not None:
            if await self._dual_channel_halt.is_halted():
                return True

        # Check shared state (coordination mode)
        if self._halt_state is not None and self._halt_state.is_halted:
            return True

        # Fall back to standalone mode
        return self._force_halted

    async def get_halt_reason(self) -> str | None:
        """Get the halt reason.

        Returns the reason from (in priority order):
        1. DualChannelHaltTransport.get_halt_reason() (if halted)
        2. Shared halt_state.halt_reason (if halted)
        3. halt_reason (if force_halted)

        Returns:
            Halt reason string if halted, None otherwise.
        """
        # Check dual-channel first (highest priority)
        if self._dual_channel_halt is not None:
            if await self._dual_channel_halt.is_halted():
                return await self._dual_channel_halt.get_halt_reason()

        # Check shared state (coordination mode)
        if self._halt_state is not None and self._halt_state.is_halted:
            return self._halt_state.halt_reason

        # Fall back to standalone mode
        if self._force_halted:
            return self._halt_reason or "Stub: Forced halt for testing"

        return None

    def set_halted(self, halted: bool, reason: str | None = None) -> None:
        """Test helper: Set the halt state (standalone mode).

        Note: If using dual-channel or shared state coordination, use
        DualChannelHaltTransport.write_halt() or halt_state.set_halted() instead.

        Args:
            halted: New halt state.
            reason: Optional halt reason.
        """
        self._force_halted = halted
        self._halt_reason = reason
