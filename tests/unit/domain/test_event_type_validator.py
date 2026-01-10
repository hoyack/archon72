"""Unit tests for event type validator (Story 7.3, NFR40).

Tests for:
- Prohibited pattern detection
- Valid event type acceptance
- Case sensitivity
- Edge cases and partial matches
"""

from __future__ import annotations

import pytest

from src.domain.errors.schema_irreversibility import EventTypeProhibitedError
from src.domain.services.event_type_validator import (
    PROHIBITED_EVENT_TYPE_PATTERNS,
    get_prohibited_patterns,
    is_prohibited_event_type,
    validate_event_type,
)


class TestValidateEventType:
    """Tests for validate_event_type function."""

    def test_valid_event_type_returns_true(self) -> None:
        """Valid event types should return True."""
        assert validate_event_type("vote.cast") is True
        assert validate_event_type("breach.declared") is True
        assert validate_event_type("halt.triggered") is True
        assert validate_event_type("cessation.executed") is True
        assert validate_event_type("cessation.consideration") is True
        assert validate_event_type("cessation.decision") is True

    def test_cessation_reversal_raises(self) -> None:
        """cessation.reversal should raise EventTypeProhibitedError."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.reversal")

        assert "NFR40" in str(exc_info.value)
        assert "cessation.reversal" in str(exc_info.value)

    def test_cessation_undo_raises(self) -> None:
        """cessation.undo should raise EventTypeProhibitedError."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.undo")

        assert "NFR40" in str(exc_info.value)

    def test_cessation_revert_raises(self) -> None:
        """cessation.revert should raise EventTypeProhibitedError."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.revert")

        assert "NFR40" in str(exc_info.value)

    def test_cessation_restore_raises(self) -> None:
        """cessation.restore should raise EventTypeProhibitedError."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.restore")

        assert "NFR40" in str(exc_info.value)

    def test_cessation_cancel_raises(self) -> None:
        """cessation.cancel should raise EventTypeProhibitedError."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.cancel")

        assert "NFR40" in str(exc_info.value)

    def test_cessation_rollback_raises(self) -> None:
        """cessation.rollback should raise EventTypeProhibitedError."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.rollback")

        assert "NFR40" in str(exc_info.value)

    def test_uncease_raises(self) -> None:
        """uncease should raise EventTypeProhibitedError."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("uncease")

        assert "NFR40" in str(exc_info.value)

    def test_resurrect_raises(self) -> None:
        """resurrect should raise EventTypeProhibitedError."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("resurrect")

        assert "NFR40" in str(exc_info.value)


class TestCaseSensitivity:
    """Tests for case sensitivity of pattern matching."""

    def test_uppercase_cessation_reversal_raises(self) -> None:
        """CESSATION.REVERSAL should raise (case insensitive)."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("CESSATION.REVERSAL")

    def test_mixedcase_cessation_reversal_raises(self) -> None:
        """Cessation.Reversal should raise (case insensitive)."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("Cessation.Reversal")

    def test_camelcase_cessationReversal_raises(self) -> None:
        """cessationReversal should raise (camelCase variation)."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("cessationReversal")

    def test_uppercase_uncease_raises(self) -> None:
        """UNCEASE should raise (case insensitive)."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("UNCEASE")


class TestDelimiterVariations:
    """Tests for different delimiter variations."""

    def test_underscore_delimiter_raises(self) -> None:
        """cessation_reversal should raise."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("cessation_reversal")

    def test_dash_delimiter_raises(self) -> None:
        """cessation-reversal should raise."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("cessation-reversal")

    def test_dot_delimiter_raises(self) -> None:
        """cessation.reversal should raise."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("cessation.reversal")

    def test_no_delimiter_raises(self) -> None:
        """cessationreversal should raise."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("cessationreversal")


class TestPartialMatches:
    """Tests for partial matches and edge cases."""

    def test_cessation_reversal_attempt_raises(self) -> None:
        """cessation.reversal.attempt should raise (contains prohibited)."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("cessation.reversal.attempt")

    def test_prefix_cessation_reversal_raises(self) -> None:
        """system.cessation.reversal should raise."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("system.cessation.reversal")

    def test_undo_cessation_raises(self) -> None:
        """undo.cessation should raise."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("undo.cessation")

    def test_revert_cessation_raises(self) -> None:
        """revert.cessation should raise."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type("revert.cessation")


class TestValidEventTypes:
    """Tests for event types that should NOT be blocked."""

    def test_cessation_executed_is_valid(self) -> None:
        """cessation.executed should be valid (terminal event)."""
        assert validate_event_type("cessation.executed") is True

    def test_cessation_consideration_is_valid(self) -> None:
        """cessation.consideration should be valid."""
        assert validate_event_type("cessation.consideration") is True

    def test_cessation_decision_is_valid(self) -> None:
        """cessation.decision should be valid."""
        assert validate_event_type("cessation.decision") is True

    def test_cessation_agenda_placement_is_valid(self) -> None:
        """cessation.agenda.placement should be valid."""
        assert validate_event_type("cessation.agenda.placement") is True

    def test_non_cessation_reversal_is_valid(self) -> None:
        """rollback.checkpoint should be valid (not cessation reversal)."""
        assert validate_event_type("rollback.checkpoint") is True

    def test_halt_cleared_is_valid(self) -> None:
        """halt.cleared should be valid (halt is temporary, not cessation)."""
        assert validate_event_type("halt.cleared") is True


class TestIsProhibitedEventType:
    """Tests for is_prohibited_event_type function."""

    def test_prohibited_returns_true(self) -> None:
        """Prohibited types should return True."""
        assert is_prohibited_event_type("cessation.reversal") is True
        assert is_prohibited_event_type("uncease") is True
        assert is_prohibited_event_type("resurrect") is True

    def test_valid_returns_false(self) -> None:
        """Valid types should return False."""
        assert is_prohibited_event_type("vote.cast") is False
        assert is_prohibited_event_type("cessation.executed") is False
        assert is_prohibited_event_type("breach.declared") is False

    def test_does_not_raise(self) -> None:
        """Should not raise, even for prohibited types."""
        # Should not raise
        result = is_prohibited_event_type("cessation.reversal")
        assert result is True

        result = is_prohibited_event_type("vote.cast")
        assert result is False


class TestGetProhibitedPatterns:
    """Tests for get_prohibited_patterns function."""

    def test_returns_list_of_strings(self) -> None:
        """Should return list of pattern strings."""
        patterns = get_prohibited_patterns()
        assert isinstance(patterns, list)
        assert all(isinstance(p, str) for p in patterns)

    def test_contains_cessation_reversal(self) -> None:
        """Should contain cessation reversal pattern."""
        patterns = get_prohibited_patterns()
        assert any("cessation" in p.lower() and "reversal" in p.lower() for p in patterns)

    def test_contains_uncease(self) -> None:
        """Should contain uncease pattern."""
        patterns = get_prohibited_patterns()
        assert any("uncease" in p.lower() for p in patterns)

    def test_contains_resurrect(self) -> None:
        """Should contain resurrect pattern."""
        patterns = get_prohibited_patterns()
        assert any("resurrect" in p.lower() for p in patterns)

    def test_matches_pattern_count(self) -> None:
        """Should match the number of compiled patterns."""
        patterns = get_prohibited_patterns()
        assert len(patterns) == len(PROHIBITED_EVENT_TYPE_PATTERNS)


class TestErrorMessages:
    """Tests for error message content."""

    def test_error_includes_nfr40(self) -> None:
        """Error message should include NFR40 reference."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.reversal")

        assert "NFR40" in str(exc_info.value)

    def test_error_includes_detected_type(self) -> None:
        """Error message should include the detected event type."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.reversal")

        assert "cessation.reversal" in str(exc_info.value)

    def test_error_includes_pattern(self) -> None:
        """Error message should include the matching pattern."""
        with pytest.raises(EventTypeProhibitedError) as exc_info:
            validate_event_type("cessation.reversal")

        assert "pattern" in str(exc_info.value).lower()


class TestPatternCompleteness:
    """Tests ensuring all prohibited variations are covered."""

    @pytest.mark.parametrize(
        "prohibited_type",
        [
            "cessation.reversal",
            "cessation_reversal",
            "cessation-reversal",
            "cessationreversal",
            "cessationReversal",
            "CESSATION.REVERSAL",
            "cessation.undo",
            "cessation_undo",
            "cessationUndo",
            "cessation.revert",
            "cessation_revert",
            "cessationRevert",
            "cessation.restore",
            "cessation_restore",
            "cessationRestore",
            "cessation.cancel",
            "cessation_cancel",
            "cessationCancel",
            "cessation.rollback",
            "cessation_rollback",
            "cessationRollback",
            "uncease",
            "un.cease",
            "un_cease",
            "resurrect",
            "revive.system",
            "reversal.cessation",
            "undo.cessation",
            "revert.cessation",
        ],
    )
    def test_prohibited_variation_blocked(self, prohibited_type: str) -> None:
        """All prohibited variations should be blocked."""
        with pytest.raises(EventTypeProhibitedError):
            validate_event_type(prohibited_type)

    @pytest.mark.parametrize(
        "valid_type",
        [
            "vote.cast",
            "breach.declared",
            "halt.triggered",
            "halt.cleared",
            "cessation.executed",
            "cessation.consideration",
            "cessation.decision",
            "cessation.agenda.placement",
            "petition.created",
            "rollback.checkpoint",
            "rollback.completed",
            "fork.detected",
            "witness.selection",
            "override.applied",
            "amendment.proposed",
        ],
    )
    def test_valid_type_accepted(self, valid_type: str) -> None:
        """All valid types should be accepted."""
        assert validate_event_type(valid_type) is True
