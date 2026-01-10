"""Unit tests for escalation domain errors (Story 6.2, FR31).

Tests:
- All escalation error types
- Error inheritance hierarchy
- Error attributes and messages

Constitutional Constraints:
- FR31: Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda
- CT-11: Silent failure destroys legitimacy -> Errors must include FR reference
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.escalation import (
    BreachAlreadyAcknowledgedError,
    BreachAlreadyEscalatedError,
    BreachNotFoundError,
    EscalationError,
    EscalationTimerNotStartedError,
    InvalidAcknowledgmentError,
)


class TestEscalationError:
    """Tests for base EscalationError class."""

    def test_escalation_error_inherits_from_constitutional_violation(self) -> None:
        """Verify EscalationError inherits from ConstitutionalViolationError."""
        error = EscalationError("test error")
        assert isinstance(error, ConstitutionalViolationError)

    def test_escalation_error_is_exception(self) -> None:
        """Verify EscalationError is an exception."""
        error = EscalationError("test error")
        assert isinstance(error, Exception)

    def test_escalation_error_message(self) -> None:
        """Verify custom message is preserved."""
        error = EscalationError("custom escalation message")
        assert str(error) == "custom escalation message"


class TestBreachNotFoundError:
    """Tests for BreachNotFoundError class."""

    def test_inherits_from_escalation_error(self) -> None:
        """Verify BreachNotFoundError inherits from EscalationError."""
        breach_id = uuid4()
        error = BreachNotFoundError(breach_id)
        assert isinstance(error, EscalationError)

    def test_default_message_includes_fr31_and_breach_id(self) -> None:
        """Verify default message includes FR31 reference and breach ID."""
        breach_id = UUID("12345678-1234-5678-1234-567812345678")
        error = BreachNotFoundError(breach_id)
        message = str(error)

        assert "FR31" in message
        assert str(breach_id) in message

    def test_stores_breach_id_attribute(self) -> None:
        """Verify breach_id is stored as attribute."""
        breach_id = uuid4()
        error = BreachNotFoundError(breach_id)
        assert error.breach_id == breach_id

    def test_custom_message_overrides_default(self) -> None:
        """Verify custom message can override default."""
        breach_id = uuid4()
        custom = "Custom not found message"
        error = BreachNotFoundError(breach_id, message=custom)
        assert str(error) == custom


class TestBreachAlreadyAcknowledgedError:
    """Tests for BreachAlreadyAcknowledgedError class."""

    def test_inherits_from_escalation_error(self) -> None:
        """Verify BreachAlreadyAcknowledgedError inherits from EscalationError."""
        breach_id = uuid4()
        error = BreachAlreadyAcknowledgedError(breach_id)
        assert isinstance(error, EscalationError)

    def test_default_message_includes_fr31_and_breach_id(self) -> None:
        """Verify default message includes FR31 reference and breach ID."""
        breach_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        error = BreachAlreadyAcknowledgedError(breach_id)
        message = str(error)

        assert "FR31" in message
        assert str(breach_id) in message
        assert "acknowledged" in message.lower()

    def test_stores_breach_id_attribute(self) -> None:
        """Verify breach_id is stored as attribute."""
        breach_id = uuid4()
        error = BreachAlreadyAcknowledgedError(breach_id)
        assert error.breach_id == breach_id

    def test_custom_message_overrides_default(self) -> None:
        """Verify custom message can override default."""
        breach_id = uuid4()
        custom = "Custom already acknowledged message"
        error = BreachAlreadyAcknowledgedError(breach_id, message=custom)
        assert str(error) == custom


class TestBreachAlreadyEscalatedError:
    """Tests for BreachAlreadyEscalatedError class."""

    def test_inherits_from_escalation_error(self) -> None:
        """Verify BreachAlreadyEscalatedError inherits from EscalationError."""
        breach_id = uuid4()
        error = BreachAlreadyEscalatedError(breach_id)
        assert isinstance(error, EscalationError)

    def test_default_message_includes_fr31_and_breach_id(self) -> None:
        """Verify default message includes FR31 reference and breach ID."""
        breach_id = UUID("11111111-2222-3333-4444-555555555555")
        error = BreachAlreadyEscalatedError(breach_id)
        message = str(error)

        assert "FR31" in message
        assert str(breach_id) in message
        assert "escalated" in message.lower()

    def test_stores_breach_id_attribute(self) -> None:
        """Verify breach_id is stored as attribute."""
        breach_id = uuid4()
        error = BreachAlreadyEscalatedError(breach_id)
        assert error.breach_id == breach_id

    def test_custom_message_overrides_default(self) -> None:
        """Verify custom message can override default."""
        breach_id = uuid4()
        custom = "Custom already escalated message"
        error = BreachAlreadyEscalatedError(breach_id, message=custom)
        assert str(error) == custom


class TestInvalidAcknowledgmentError:
    """Tests for InvalidAcknowledgmentError class."""

    def test_inherits_from_escalation_error(self) -> None:
        """Verify InvalidAcknowledgmentError inherits from EscalationError."""
        error = InvalidAcknowledgmentError("missing response choice")
        assert isinstance(error, EscalationError)

    def test_default_message_includes_fr31_and_reason(self) -> None:
        """Verify default message includes FR31 reference and reason."""
        reason = "missing response choice"
        error = InvalidAcknowledgmentError(reason)
        message = str(error)

        assert "FR31" in message
        assert reason in message

    def test_stores_reason_attribute(self) -> None:
        """Verify reason is stored as attribute."""
        reason = "invalid keeper attribution"
        error = InvalidAcknowledgmentError(reason)
        assert error.reason == reason

    def test_custom_message_overrides_default(self) -> None:
        """Verify custom message can override default."""
        reason = "test reason"
        custom = "Custom invalid acknowledgment message"
        error = InvalidAcknowledgmentError(reason, message=custom)
        assert str(error) == custom


class TestEscalationTimerNotStartedError:
    """Tests for EscalationTimerNotStartedError class."""

    def test_inherits_from_escalation_error(self) -> None:
        """Verify EscalationTimerNotStartedError inherits from EscalationError."""
        breach_id = uuid4()
        error = EscalationTimerNotStartedError(breach_id)
        assert isinstance(error, EscalationError)

    def test_default_message_includes_fr31_and_breach_id(self) -> None:
        """Verify default message includes FR31 reference and breach ID."""
        breach_id = UUID("99999999-8888-7777-6666-555544443333")
        error = EscalationTimerNotStartedError(breach_id)
        message = str(error)

        assert "FR31" in message
        assert str(breach_id) in message
        assert "timer" in message.lower()

    def test_stores_breach_id_attribute(self) -> None:
        """Verify breach_id is stored as attribute."""
        breach_id = uuid4()
        error = EscalationTimerNotStartedError(breach_id)
        assert error.breach_id == breach_id

    def test_custom_message_overrides_default(self) -> None:
        """Verify custom message can override default."""
        breach_id = uuid4()
        custom = "Custom timer not started message"
        error = EscalationTimerNotStartedError(breach_id, message=custom)
        assert str(error) == custom


class TestErrorHierarchy:
    """Tests for error inheritance hierarchy."""

    def test_all_errors_inherit_from_escalation_error(self) -> None:
        """Verify all escalation errors inherit from EscalationError."""
        breach_id = uuid4()

        errors = [
            BreachNotFoundError(breach_id),
            BreachAlreadyAcknowledgedError(breach_id),
            BreachAlreadyEscalatedError(breach_id),
            InvalidAcknowledgmentError("reason"),
            EscalationTimerNotStartedError(breach_id),
        ]

        for error in errors:
            assert isinstance(error, EscalationError)
            assert isinstance(error, ConstitutionalViolationError)
            assert isinstance(error, Exception)

    def test_can_catch_all_with_escalation_error(self) -> None:
        """Verify all escalation errors can be caught with EscalationError."""
        breach_id = uuid4()

        with pytest.raises(EscalationError):
            raise BreachNotFoundError(breach_id)

        with pytest.raises(EscalationError):
            raise BreachAlreadyAcknowledgedError(breach_id)

        with pytest.raises(EscalationError):
            raise BreachAlreadyEscalatedError(breach_id)

        with pytest.raises(EscalationError):
            raise InvalidAcknowledgmentError("reason")

        with pytest.raises(EscalationError):
            raise EscalationTimerNotStartedError(breach_id)

    def test_can_catch_all_with_constitutional_violation_error(self) -> None:
        """Verify all escalation errors can be caught with ConstitutionalViolationError."""
        breach_id = uuid4()

        with pytest.raises(ConstitutionalViolationError):
            raise BreachNotFoundError(breach_id)

        with pytest.raises(ConstitutionalViolationError):
            raise BreachAlreadyAcknowledgedError(breach_id)
