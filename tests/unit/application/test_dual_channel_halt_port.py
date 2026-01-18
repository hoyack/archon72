"""Unit tests for DualChannelHaltTransport port interface (Story 3.3, Task 1).

Tests the abstract interface definition for dual-channel halt transport.
This verifies the contract that implementations must fulfill.

ADR-3: Partition Behavior + Halt Durability
- Dual-channel halt: Redis Streams + DB halt flag
- If EITHER channel indicates halt -> component halts
- DB is canonical when channels disagree
"""

from abc import ABC
from uuid import UUID, uuid4

import pytest

from src.application.ports.dual_channel_halt import (
    CONFIRMATION_TIMEOUT_SECONDS,
    DualChannelHaltTransport,
    HaltFlagState,
)
from src.domain.events.halt_cleared import HaltClearedPayload
from src.domain.models.ceremony_evidence import CeremonyEvidence


class TestDualChannelHaltTransportInterface:
    """Test that DualChannelHaltTransport is properly defined as ABC."""

    def test_is_abstract_base_class(self) -> None:
        """DualChannelHaltTransport should be an abstract base class."""
        assert issubclass(DualChannelHaltTransport, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Should not be able to instantiate abstract class directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DualChannelHaltTransport()  # type: ignore[abstract]

    def test_has_write_halt_method(self) -> None:
        """Interface should define write_halt method."""
        assert hasattr(DualChannelHaltTransport, "write_halt")
        assert callable(DualChannelHaltTransport.write_halt)

    def test_has_is_halted_method(self) -> None:
        """Interface should define is_halted method."""
        assert hasattr(DualChannelHaltTransport, "is_halted")
        assert callable(DualChannelHaltTransport.is_halted)

    def test_has_get_halt_reason_method(self) -> None:
        """Interface should define get_halt_reason method."""
        assert hasattr(DualChannelHaltTransport, "get_halt_reason")
        assert callable(DualChannelHaltTransport.get_halt_reason)

    def test_has_check_channels_consistent_method(self) -> None:
        """Interface should define check_channels_consistent method."""
        assert hasattr(DualChannelHaltTransport, "check_channels_consistent")
        assert callable(DualChannelHaltTransport.check_channels_consistent)

    def test_has_resolve_conflict_method(self) -> None:
        """Interface should define resolve_conflict method."""
        assert hasattr(DualChannelHaltTransport, "resolve_conflict")
        assert callable(DualChannelHaltTransport.resolve_conflict)

    def test_has_confirmation_timeout_property(self) -> None:
        """Interface should define confirmation_timeout_seconds property."""
        assert hasattr(DualChannelHaltTransport, "confirmation_timeout_seconds")


class TestHaltFlagState:
    """Test HaltFlagState dataclass."""

    def test_create_halt_flag_state_halted(self) -> None:
        """Should create HaltFlagState when halted."""
        crisis_id = uuid4()
        state = HaltFlagState(
            is_halted=True,
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        assert state.is_halted is True
        assert state.reason == "FR17: Fork detected"
        assert state.crisis_event_id == crisis_id

    def test_create_halt_flag_state_not_halted(self) -> None:
        """Should create HaltFlagState when not halted."""
        state = HaltFlagState(
            is_halted=False,
            reason=None,
            crisis_event_id=None,
        )

        assert state.is_halted is False
        assert state.reason is None
        assert state.crisis_event_id is None

    def test_halt_flag_state_is_frozen(self) -> None:
        """HaltFlagState should be immutable (frozen dataclass)."""
        state = HaltFlagState(
            is_halted=True,
            reason="Test",
            crisis_event_id=uuid4(),
        )

        with pytest.raises(AttributeError):
            state.is_halted = False  # type: ignore[misc]


class TestConfirmationTimeoutConstant:
    """Test CONFIRMATION_TIMEOUT_SECONDS constant."""

    def test_confirmation_timeout_is_5_seconds(self) -> None:
        """RT-2: Halt from Redis must be confirmed against DB within 5 seconds."""
        assert CONFIRMATION_TIMEOUT_SECONDS == 5.0

    def test_confirmation_timeout_is_float(self) -> None:
        """Timeout should be a float for asyncio compatibility."""
        assert isinstance(CONFIRMATION_TIMEOUT_SECONDS, float)


class TestDualChannelHaltTransportConcreteImplementation:
    """Test that a concrete implementation can be created."""

    def test_concrete_implementation_satisfies_interface(self) -> None:
        """Verify a concrete implementation can satisfy the interface."""

        class ConcreteDualChannelHalt(DualChannelHaltTransport):
            """Concrete implementation for testing."""

            @property
            def confirmation_timeout_seconds(self) -> float:
                return CONFIRMATION_TIMEOUT_SECONDS

            async def write_halt(self, reason: str, crisis_event_id: UUID) -> None:
                pass

            async def is_halted(self) -> bool:
                return False

            async def get_halt_reason(self) -> str | None:
                return None

            async def check_channels_consistent(self) -> bool:
                return True

            async def resolve_conflict(self) -> None:
                pass

            async def clear_halt(
                self, ceremony_evidence: CeremonyEvidence
            ) -> HaltClearedPayload:
                return HaltClearedPayload(
                    cleared_at=ceremony_evidence.ceremony_timestamp,
                    ceremony_id=ceremony_evidence.ceremony_id,
                    approvers=ceremony_evidence.approvers,
                    cleared_by_db=True,
                    cleared_by_redis=True,
                )

        # Should be instantiable
        impl = ConcreteDualChannelHalt()
        assert isinstance(impl, DualChannelHaltTransport)
        assert impl.confirmation_timeout_seconds == 5.0
