"""Unit tests for CessationState domain model.

Story: consent-gov-8.1: System Cessation Trigger
AC2: Cessation blocks new motions (FR49)
AC3: Cessation halts execution (FR50)
AC7: All in-flight operations complete or interrupted
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.cessation import (
    CessationState,
    CessationStatus,
    CessationTrigger,
)


def make_trigger() -> CessationTrigger:
    """Create a test CessationTrigger."""
    return CessationTrigger(
        trigger_id=uuid4(),
        operator_id=uuid4(),
        triggered_at=datetime.now(timezone.utc),
        reason="Test trigger",
    )


class TestCessationStateCreation:
    """Tests for CessationState creation."""

    def test_create_active_state(self) -> None:
        """Can create active state via factory."""
        state = CessationState.active()

        assert state.status == CessationStatus.ACTIVE
        assert state.trigger is None
        assert state.motions_blocked is False
        assert state.execution_halted is False
        assert state.in_flight_count == 0

    def test_create_triggered_state(self) -> None:
        """Can create triggered state via factory."""
        trigger = make_trigger()
        state = CessationState.triggered(trigger, in_flight_count=5)

        assert state.status == CessationStatus.CESSATION_TRIGGERED
        assert state.trigger == trigger
        assert state.motions_blocked is True
        assert state.execution_halted is False  # Existing operations continue
        assert state.in_flight_count == 5

    def test_create_ceased_state(self) -> None:
        """Can create ceased state via factory."""
        trigger = make_trigger()
        state = CessationState.ceased(trigger)

        assert state.status == CessationStatus.CEASED
        assert state.trigger == trigger
        assert state.motions_blocked is True
        assert state.execution_halted is True
        assert state.in_flight_count == 0

    def test_state_is_immutable(self) -> None:
        """CessationState is immutable (frozen dataclass)."""
        state = CessationState.active()

        with pytest.raises(AttributeError):
            state.motions_blocked = True  # type: ignore


class TestCessationStateProperties:
    """Tests for CessationState property methods."""

    def test_is_active_delegates_to_status(self) -> None:
        """is_active delegates to status."""
        assert CessationState.active().is_active is True
        assert CessationState.triggered(make_trigger()).is_active is False
        assert CessationState.ceased(make_trigger()).is_active is False

    def test_is_ceasing_delegates_to_status(self) -> None:
        """is_ceasing delegates to status."""
        assert CessationState.active().is_ceasing is False
        assert CessationState.triggered(make_trigger()).is_ceasing is True
        assert CessationState.ceased(make_trigger()).is_ceasing is False

    def test_is_ceased_delegates_to_status(self) -> None:
        """is_ceased delegates to status."""
        assert CessationState.active().is_ceased is False
        assert CessationState.triggered(make_trigger()).is_ceased is False
        assert CessationState.ceased(make_trigger()).is_ceased is True


class TestMotionBlocking:
    """Tests for motion blocking behavior (AC2, FR49)."""

    def test_active_state_allows_motions(self) -> None:
        """Active state does not block motions."""
        state = CessationState.active()
        assert state.motions_blocked is False

    def test_triggered_state_blocks_motions(self) -> None:
        """Triggered state blocks new motions."""
        state = CessationState.triggered(make_trigger())
        assert state.motions_blocked is True

    def test_ceased_state_blocks_motions(self) -> None:
        """Ceased state blocks new motions."""
        state = CessationState.ceased(make_trigger())
        assert state.motions_blocked is True


class TestExecutionHalting:
    """Tests for execution halt behavior (AC3, FR50)."""

    def test_active_state_allows_execution(self) -> None:
        """Active state does not halt execution."""
        state = CessationState.active()
        assert state.execution_halted is False

    def test_triggered_state_allows_existing_execution(self) -> None:
        """Triggered state allows existing operations to continue."""
        state = CessationState.triggered(make_trigger())
        assert state.execution_halted is False  # Existing continues

    def test_ceased_state_halts_execution(self) -> None:
        """Ceased state halts all execution."""
        state = CessationState.ceased(make_trigger())
        assert state.execution_halted is True


class TestInFlightOperations:
    """Tests for in-flight operation tracking (AC7)."""

    def test_active_state_has_zero_in_flight(self) -> None:
        """Active state has zero in-flight count."""
        state = CessationState.active()
        assert state.in_flight_count == 0

    def test_triggered_state_tracks_in_flight(self) -> None:
        """Triggered state tracks in-flight count."""
        state = CessationState.triggered(make_trigger(), in_flight_count=10)
        assert state.in_flight_count == 10

    def test_ceased_state_has_zero_in_flight(self) -> None:
        """Ceased state has zero in-flight count."""
        state = CessationState.ceased(make_trigger())
        assert state.in_flight_count == 0

    def test_with_in_flight_count_creates_new_state(self) -> None:
        """with_in_flight_count creates new state with updated count."""
        original = CessationState.triggered(make_trigger(), in_flight_count=10)
        updated = original.with_in_flight_count(5)

        assert updated.in_flight_count == 5
        assert original.in_flight_count == 10  # Original unchanged
        assert updated.status == original.status  # Other fields preserved
        assert updated.trigger == original.trigger


class TestCessationStateSerialization:
    """Tests for CessationState serialization."""

    def test_active_state_to_dict(self) -> None:
        """Can serialize active state to dictionary."""
        state = CessationState.active()
        data = state.to_dict()

        assert data["status"] == "active"
        assert data["trigger"] is None
        assert data["motions_blocked"] is False
        assert data["execution_halted"] is False
        assert data["in_flight_count"] == 0

    def test_triggered_state_to_dict(self) -> None:
        """Can serialize triggered state to dictionary."""
        trigger = make_trigger()
        state = CessationState.triggered(trigger, in_flight_count=5)
        data = state.to_dict()

        assert data["status"] == "cessation_triggered"
        assert data["trigger"] is not None
        assert data["trigger"]["trigger_id"] == str(trigger.trigger_id)
        assert data["motions_blocked"] is True
        assert data["in_flight_count"] == 5

    def test_from_dict_active(self) -> None:
        """Can deserialize active state from dictionary."""
        data = {
            "status": "active",
            "trigger": None,
            "motions_blocked": False,
            "execution_halted": False,
            "in_flight_count": 0,
        }

        state = CessationState.from_dict(data)

        assert state.status == CessationStatus.ACTIVE
        assert state.trigger is None

    def test_from_dict_triggered(self) -> None:
        """Can deserialize triggered state from dictionary."""
        trigger_id = uuid4()
        operator_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "status": "cessation_triggered",
            "trigger": {
                "trigger_id": str(trigger_id),
                "operator_id": str(operator_id),
                "triggered_at": now.isoformat(),
                "reason": "Test",
            },
            "motions_blocked": True,
            "execution_halted": False,
            "in_flight_count": 3,
        }

        state = CessationState.from_dict(data)

        assert state.status == CessationStatus.CESSATION_TRIGGERED
        assert state.trigger is not None
        assert state.trigger.trigger_id == trigger_id
        assert state.in_flight_count == 3

    def test_round_trip_serialization(self) -> None:
        """Serialization round-trip preserves all data."""
        trigger = make_trigger()
        original = CessationState.triggered(trigger, in_flight_count=7)

        data = original.to_dict()
        restored = CessationState.from_dict(data)

        assert restored.status == original.status
        assert restored.motions_blocked == original.motions_blocked
        assert restored.execution_halted == original.execution_halted
        assert restored.in_flight_count == original.in_flight_count
        assert restored.trigger is not None
        assert restored.trigger.trigger_id == original.trigger.trigger_id
