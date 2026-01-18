"""Unit tests for LegitimacyState domain model.

Tests AC3: Current band tracked and queryable
Tests AC7: All transitions recorded with timestamp
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.transition_type import TransitionType


class TestLegitimacyStateCreation:
    """Tests for creating LegitimacyState."""

    def test_create_state_with_all_fields(self) -> None:
        """Can create state with all fields."""
        now = datetime.now(timezone.utc)
        event_id = uuid4()

        state = LegitimacyState(
            current_band=LegitimacyBand.STABLE,
            entered_at=now,
            violation_count=0,
            last_triggering_event_id=event_id,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        assert state.current_band == LegitimacyBand.STABLE
        assert state.entered_at == now
        assert state.violation_count == 0
        assert state.last_triggering_event_id == event_id
        assert state.last_transition_type == TransitionType.AUTOMATIC

    def test_create_state_without_event_id(self) -> None:
        """Can create state without triggering event ID."""
        now = datetime.now(timezone.utc)

        state = LegitimacyState(
            current_band=LegitimacyBand.STABLE,
            entered_at=now,
            violation_count=0,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        assert state.last_triggering_event_id is None

    def test_state_is_immutable(self) -> None:
        """LegitimacyState is frozen (immutable)."""
        now = datetime.now(timezone.utc)

        state = LegitimacyState(
            current_band=LegitimacyBand.STABLE,
            entered_at=now,
            violation_count=0,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        with pytest.raises(AttributeError):
            state.current_band = LegitimacyBand.FAILED  # type: ignore

    def test_negative_violation_count_raises(self) -> None:
        """Negative violation count raises ValueError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="cannot be negative"):
            LegitimacyState(
                current_band=LegitimacyBand.STABLE,
                entered_at=now,
                violation_count=-1,
                last_triggering_event_id=None,
                last_transition_type=TransitionType.AUTOMATIC,
            )


class TestLegitimacyStateInitial:
    """Tests for initial state factory method."""

    def test_initial_state_is_stable(self) -> None:
        """Initial state starts at STABLE."""
        now = datetime.now(timezone.utc)
        state = LegitimacyState.initial(entered_at=now)

        assert state.current_band == LegitimacyBand.STABLE

    def test_initial_state_has_zero_violations(self) -> None:
        """Initial state has zero violations."""
        now = datetime.now(timezone.utc)
        state = LegitimacyState.initial(entered_at=now)

        assert state.violation_count == 0

    def test_initial_state_has_correct_timestamp(self) -> None:
        """Initial state uses provided timestamp."""
        now = datetime.now(timezone.utc)
        state = LegitimacyState.initial(entered_at=now)

        assert state.entered_at == now

    def test_initial_state_no_triggering_event(self) -> None:
        """Initial state has no triggering event."""
        now = datetime.now(timezone.utc)
        state = LegitimacyState.initial(entered_at=now)

        assert state.last_triggering_event_id is None


class TestLegitimacyStateProperties:
    """Tests for state helper properties."""

    def test_is_healthy_for_stable(self) -> None:
        """STABLE state is healthy."""
        state = LegitimacyState.initial(datetime.now(timezone.utc))
        assert state.is_healthy

    def test_is_healthy_for_strained(self) -> None:
        """STRAINED state is healthy."""
        now = datetime.now(timezone.utc)
        state = LegitimacyState(
            current_band=LegitimacyBand.STRAINED,
            entered_at=now,
            violation_count=1,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )
        assert state.is_healthy

    def test_is_not_healthy_for_eroding(self) -> None:
        """ERODING state is not healthy."""
        now = datetime.now(timezone.utc)
        state = LegitimacyState(
            current_band=LegitimacyBand.ERODING,
            entered_at=now,
            violation_count=2,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )
        assert not state.is_healthy

    def test_is_critical_for_compromised(self) -> None:
        """COMPROMISED state is critical."""
        now = datetime.now(timezone.utc)
        state = LegitimacyState(
            current_band=LegitimacyBand.COMPROMISED,
            entered_at=now,
            violation_count=5,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )
        assert state.is_critical

    def test_is_critical_for_failed(self) -> None:
        """FAILED state is critical."""
        now = datetime.now(timezone.utc)
        state = LegitimacyState(
            current_band=LegitimacyBand.FAILED,
            entered_at=now,
            violation_count=10,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )
        assert state.is_critical

    def test_is_terminal_only_for_failed(self) -> None:
        """Only FAILED is terminal."""
        now = datetime.now(timezone.utc)

        for band in LegitimacyBand:
            state = LegitimacyState(
                current_band=band,
                entered_at=now,
                violation_count=0,
                last_triggering_event_id=None,
                last_transition_type=TransitionType.AUTOMATIC,
            )

            if band == LegitimacyBand.FAILED:
                assert state.is_terminal
            else:
                assert not state.is_terminal

    def test_severity_property(self) -> None:
        """Severity property returns band severity."""
        now = datetime.now(timezone.utc)

        for band in LegitimacyBand:
            state = LegitimacyState(
                current_band=band,
                entered_at=now,
                violation_count=0,
                last_triggering_event_id=None,
                last_transition_type=TransitionType.AUTOMATIC,
            )
            assert state.severity == band.severity


class TestLegitimacyStateWithNewBand:
    """Tests for with_new_band method (AC7)."""

    def test_with_new_band_creates_new_state(self) -> None:
        """with_new_band creates a new state instance."""
        now = datetime.now(timezone.utc)
        later = datetime.now(timezone.utc)
        event_id = uuid4()

        original = LegitimacyState.initial(entered_at=now)
        updated = original.with_new_band(
            new_band=LegitimacyBand.STRAINED,
            entered_at=later,
            triggering_event_id=event_id,
            transition_type=TransitionType.AUTOMATIC,
        )

        # Original unchanged
        assert original.current_band == LegitimacyBand.STABLE
        assert original.entered_at == now

        # Updated has new values
        assert updated.current_band == LegitimacyBand.STRAINED
        assert updated.entered_at == later
        assert updated.last_triggering_event_id == event_id
        assert updated.last_transition_type == TransitionType.AUTOMATIC

    def test_with_new_band_preserves_violation_count(self) -> None:
        """with_new_band preserves violation count by default."""
        now = datetime.now(timezone.utc)

        original = LegitimacyState(
            current_band=LegitimacyBand.STRAINED,
            entered_at=now,
            violation_count=5,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        updated = original.with_new_band(
            new_band=LegitimacyBand.ERODING,
            entered_at=datetime.now(timezone.utc),
            triggering_event_id=uuid4(),
            transition_type=TransitionType.AUTOMATIC,
        )

        assert updated.violation_count == 5

    def test_with_new_band_can_increment_violations(self) -> None:
        """with_new_band can increment violation count."""
        now = datetime.now(timezone.utc)

        original = LegitimacyState(
            current_band=LegitimacyBand.STRAINED,
            entered_at=now,
            violation_count=5,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        updated = original.with_new_band(
            new_band=LegitimacyBand.ERODING,
            entered_at=datetime.now(timezone.utc),
            triggering_event_id=uuid4(),
            transition_type=TransitionType.AUTOMATIC,
            increment_violations=True,
        )

        assert updated.violation_count == 6

    def test_with_new_band_records_acknowledgment_type(self) -> None:
        """with_new_band records acknowledged transition type."""
        now = datetime.now(timezone.utc)

        original = LegitimacyState(
            current_band=LegitimacyBand.STRAINED,
            entered_at=now,
            violation_count=0,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )

        updated = original.with_new_band(
            new_band=LegitimacyBand.STABLE,
            entered_at=datetime.now(timezone.utc),
            triggering_event_id=None,
            transition_type=TransitionType.ACKNOWLEDGED,
        )

        assert updated.last_transition_type == TransitionType.ACKNOWLEDGED
