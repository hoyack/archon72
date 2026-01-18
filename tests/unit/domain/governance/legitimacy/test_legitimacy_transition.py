"""Unit tests for LegitimacyTransition domain model.

Tests AC7: All transitions recorded with timestamp
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)
from src.domain.governance.legitimacy.transition_type import TransitionType


class TestLegitimacyTransitionCreation:
    """Tests for creating LegitimacyTransition records."""

    def test_create_automatic_transition(self) -> None:
        """Can create automatic (decay) transition."""
        transition_id = uuid4()
        triggering_event_id = uuid4()
        now = datetime.now(timezone.utc)

        transition = LegitimacyTransition(
            transition_id=transition_id,
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=triggering_event_id,
            acknowledgment_id=None,
            timestamp=now,
            reason="Violation detected: hash chain gap",
        )

        assert transition.transition_id == transition_id
        assert transition.from_band == LegitimacyBand.STABLE
        assert transition.to_band == LegitimacyBand.STRAINED
        assert transition.transition_type == TransitionType.AUTOMATIC
        assert transition.actor == "system"
        assert transition.triggering_event_id == triggering_event_id
        assert transition.acknowledgment_id is None
        assert transition.timestamp == now
        assert "hash chain gap" in transition.reason

    def test_create_acknowledged_transition(self) -> None:
        """Can create acknowledged (restoration) transition."""
        transition_id = uuid4()
        acknowledgment_id = uuid4()
        operator_id = str(uuid4())
        now = datetime.now(timezone.utc)

        transition = LegitimacyTransition(
            transition_id=transition_id,
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            transition_type=TransitionType.ACKNOWLEDGED,
            actor=operator_id,
            triggering_event_id=None,
            acknowledgment_id=acknowledgment_id,
            timestamp=now,
            reason="Issue resolved and verified by operator",
        )

        assert transition.transition_type == TransitionType.ACKNOWLEDGED
        assert transition.actor == operator_id
        assert transition.acknowledgment_id == acknowledgment_id
        assert transition.triggering_event_id is None

    def test_transition_is_immutable(self) -> None:
        """LegitimacyTransition is frozen (immutable)."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="Test transition",
        )

        with pytest.raises(AttributeError):
            transition.to_band = LegitimacyBand.FAILED  # type: ignore


class TestLegitimacyTransitionValidation:
    """Tests for transition validation."""

    def test_automatic_requires_triggering_event(self) -> None:
        """Automatic transitions must have triggering_event_id."""
        with pytest.raises(ValueError, match="triggering_event_id"):
            LegitimacyTransition(
                transition_id=uuid4(),
                from_band=LegitimacyBand.STABLE,
                to_band=LegitimacyBand.STRAINED,
                transition_type=TransitionType.AUTOMATIC,
                actor="system",
                triggering_event_id=None,  # Missing!
                acknowledgment_id=None,
                timestamp=datetime.now(timezone.utc),
                reason="Test transition",
            )

    def test_acknowledged_requires_acknowledgment_id(self) -> None:
        """Acknowledged transitions must have acknowledgment_id."""
        with pytest.raises(ValueError, match="acknowledgment_id"):
            LegitimacyTransition(
                transition_id=uuid4(),
                from_band=LegitimacyBand.STRAINED,
                to_band=LegitimacyBand.STABLE,
                transition_type=TransitionType.ACKNOWLEDGED,
                actor=str(uuid4()),
                triggering_event_id=None,
                acknowledgment_id=None,  # Missing!
                timestamp=datetime.now(timezone.utc),
                reason="Test restoration",
            )

    def test_reason_required(self) -> None:
        """Transitions must have a reason."""
        with pytest.raises(ValueError, match="reason"):
            LegitimacyTransition(
                transition_id=uuid4(),
                from_band=LegitimacyBand.STABLE,
                to_band=LegitimacyBand.STRAINED,
                transition_type=TransitionType.AUTOMATIC,
                actor="system",
                triggering_event_id=uuid4(),
                acknowledgment_id=None,
                timestamp=datetime.now(timezone.utc),
                reason="",  # Empty!
            )

    def test_whitespace_only_reason_invalid(self) -> None:
        """Whitespace-only reason is invalid."""
        with pytest.raises(ValueError, match="reason"):
            LegitimacyTransition(
                transition_id=uuid4(),
                from_band=LegitimacyBand.STABLE,
                to_band=LegitimacyBand.STRAINED,
                transition_type=TransitionType.AUTOMATIC,
                actor="system",
                triggering_event_id=uuid4(),
                acknowledgment_id=None,
                timestamp=datetime.now(timezone.utc),
                reason="   ",  # Whitespace only!
            )

    def test_same_band_transition_invalid(self) -> None:
        """Transition must change bands."""
        with pytest.raises(ValueError, match="change bands"):
            LegitimacyTransition(
                transition_id=uuid4(),
                from_band=LegitimacyBand.STABLE,
                to_band=LegitimacyBand.STABLE,  # Same!
                transition_type=TransitionType.AUTOMATIC,
                actor="system",
                triggering_event_id=uuid4(),
                acknowledgment_id=None,
                timestamp=datetime.now(timezone.utc),
                reason="Test transition",
            )


class TestLegitimacyTransitionProperties:
    """Tests for transition helper properties."""

    def test_is_decay_for_downward(self) -> None:
        """is_decay returns True for downward transitions."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="Violation detected",
        )

        assert transition.is_decay
        assert not transition.is_restoration

    def test_is_restoration_for_upward(self) -> None:
        """is_restoration returns True for upward transitions."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            transition_type=TransitionType.ACKNOWLEDGED,
            actor=str(uuid4()),
            triggering_event_id=None,
            acknowledgment_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            reason="Issue resolved",
        )

        assert transition.is_restoration
        assert not transition.is_decay

    def test_severity_change_positive_for_decay(self) -> None:
        """severity_change is positive for decay."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.COMPROMISED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="Critical violation",
        )

        assert transition.severity_change == 3  # 0 -> 3

    def test_severity_change_negative_for_restoration(self) -> None:
        """severity_change is negative for restoration."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.ERODING,
            to_band=LegitimacyBand.STRAINED,
            transition_type=TransitionType.ACKNOWLEDGED,
            actor=str(uuid4()),
            triggering_event_id=None,
            acknowledgment_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            reason="Issue resolved",
        )

        assert transition.severity_change == -1  # 2 -> 1

    def test_crossed_critical_threshold_into_critical(self) -> None:
        """Detects crossing into critical state."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.ERODING,
            to_band=LegitimacyBand.COMPROMISED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="Crossed critical threshold",
        )

        assert transition.crossed_critical_threshold

    def test_crossed_critical_threshold_out_of_critical(self) -> None:
        """Detects crossing out of critical state."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.COMPROMISED,
            to_band=LegitimacyBand.ERODING,
            transition_type=TransitionType.ACKNOWLEDGED,
            actor=str(uuid4()),
            triggering_event_id=None,
            acknowledgment_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            reason="Restored from critical",
        )

        assert transition.crossed_critical_threshold

    def test_not_crossed_critical_within_healthy(self) -> None:
        """No threshold crossed within healthy bands."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="Minor issue",
        )

        assert not transition.crossed_critical_threshold

    def test_resulted_in_failure_true(self) -> None:
        """resulted_in_failure True when to_band is FAILED."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.COMPROMISED,
            to_band=LegitimacyBand.FAILED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="System failure",
        )

        assert transition.resulted_in_failure

    def test_resulted_in_failure_false(self) -> None:
        """resulted_in_failure False when not transitioning to FAILED."""
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.COMPROMISED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="Severe violation",
        )

        assert not transition.resulted_in_failure
