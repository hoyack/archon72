"""Unit tests for override abuse domain errors (Story 5.9, FR86-FR87).

Tests error classes for override abuse detection:
- OverrideAbuseError (base class)
- HistoryEditAttemptError (FR87)
- EvidenceDestructionAttemptError (FR87)
- ConstitutionalConstraintViolationError (FR86)
"""

from __future__ import annotations

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.override_abuse import (
    ConstitutionalConstraintViolationError,
    EvidenceDestructionAttemptError,
    HistoryEditAttemptError,
    OverrideAbuseError,
)


class TestOverrideAbuseError:
    """Tests for OverrideAbuseError base class."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Test OverrideAbuseError inherits from ConstitutionalViolationError."""
        assert issubclass(OverrideAbuseError, ConstitutionalViolationError)

    def test_can_be_raised(self) -> None:
        """Test OverrideAbuseError can be raised with message."""
        with pytest.raises(OverrideAbuseError, match="test error"):
            raise OverrideAbuseError("test error")


class TestHistoryEditAttemptError:
    """Tests for HistoryEditAttemptError (FR87)."""

    def test_inherits_from_override_abuse_error(self) -> None:
        """Test HistoryEditAttemptError inherits from OverrideAbuseError."""
        assert issubclass(HistoryEditAttemptError, OverrideAbuseError)

    def test_default_message_includes_fr87(self) -> None:
        """Test default message includes FR87 reference."""
        error = HistoryEditAttemptError(scope="history.delete")
        assert "FR87" in str(error)

    def test_default_message_includes_scope(self) -> None:
        """Test default message includes the scope."""
        error = HistoryEditAttemptError(scope="event_store.modify")
        assert "event_store.modify" in str(error)

    def test_scope_attribute(self) -> None:
        """Test scope attribute is accessible."""
        error = HistoryEditAttemptError(scope="history")
        assert error.scope == "history"

    def test_custom_message(self) -> None:
        """Test custom message can be provided."""
        custom_msg = "Custom history edit error message"
        error = HistoryEditAttemptError(scope="test", message=custom_msg)
        assert str(error) == custom_msg
        assert error.scope == "test"

    def test_can_be_caught_as_constitutional_violation(self) -> None:
        """Test can be caught as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise HistoryEditAttemptError(scope="history.delete")


class TestEvidenceDestructionAttemptError:
    """Tests for EvidenceDestructionAttemptError (FR87)."""

    def test_inherits_from_override_abuse_error(self) -> None:
        """Test EvidenceDestructionAttemptError inherits from OverrideAbuseError."""
        assert issubclass(EvidenceDestructionAttemptError, OverrideAbuseError)

    def test_default_message_includes_fr87(self) -> None:
        """Test default message includes FR87 reference."""
        error = EvidenceDestructionAttemptError(scope="evidence.delete")
        assert "FR87" in str(error)

    def test_default_message_includes_scope(self) -> None:
        """Test default message includes the scope."""
        error = EvidenceDestructionAttemptError(scope="witness.remove")
        assert "witness.remove" in str(error)

    def test_scope_attribute(self) -> None:
        """Test scope attribute is accessible."""
        error = EvidenceDestructionAttemptError(scope="evidence")
        assert error.scope == "evidence"

    def test_custom_message(self) -> None:
        """Test custom message can be provided."""
        custom_msg = "Custom evidence destruction error message"
        error = EvidenceDestructionAttemptError(scope="test", message=custom_msg)
        assert str(error) == custom_msg
        assert error.scope == "test"

    def test_can_be_caught_as_constitutional_violation(self) -> None:
        """Test can be caught as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise EvidenceDestructionAttemptError(scope="witness.delete")


class TestConstitutionalConstraintViolationError:
    """Tests for ConstitutionalConstraintViolationError (FR86)."""

    def test_inherits_from_override_abuse_error(self) -> None:
        """Test ConstitutionalConstraintViolationError inherits from OverrideAbuseError."""
        assert issubclass(ConstitutionalConstraintViolationError, OverrideAbuseError)

    def test_default_message_includes_fr86(self) -> None:
        """Test default message includes FR86 reference."""
        error = ConstitutionalConstraintViolationError(
            scope="test.scope",
            constraint="test constraint",
        )
        assert "FR86" in str(error)

    def test_default_message_includes_scope(self) -> None:
        """Test default message includes the scope."""
        error = ConstitutionalConstraintViolationError(
            scope="witness.disable",
            constraint="witness suppression forbidden",
        )
        assert "witness.disable" in str(error)

    def test_default_message_includes_constraint(self) -> None:
        """Test default message includes the constraint."""
        error = ConstitutionalConstraintViolationError(
            scope="test",
            constraint="immutability violated",
        )
        assert "immutability violated" in str(error)

    def test_scope_attribute(self) -> None:
        """Test scope attribute is accessible."""
        error = ConstitutionalConstraintViolationError(
            scope="forbidden.scope",
            constraint="test",
        )
        assert error.scope == "forbidden.scope"

    def test_constraint_attribute(self) -> None:
        """Test constraint attribute is accessible."""
        error = ConstitutionalConstraintViolationError(
            scope="test",
            constraint="specific constraint",
        )
        assert error.constraint == "specific constraint"

    def test_custom_message(self) -> None:
        """Test custom message can be provided."""
        custom_msg = "Custom constitutional constraint error message"
        error = ConstitutionalConstraintViolationError(
            scope="test",
            constraint="test",
            message=custom_msg,
        )
        assert str(error) == custom_msg
        assert error.scope == "test"
        assert error.constraint == "test"

    def test_can_be_caught_as_constitutional_violation(self) -> None:
        """Test can be caught as ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError):
            raise ConstitutionalConstraintViolationError(
                scope="test",
                constraint="test",
            )
