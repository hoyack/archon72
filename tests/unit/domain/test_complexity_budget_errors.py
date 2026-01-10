"""Unit tests for complexity budget errors (Story 8.6, SC-3, RT-6).

Tests for ComplexityBudgetBreachedError, ComplexityBudgetApprovalRequiredError,
and ComplexityBudgetEscalationError.
"""

from uuid import uuid4

import pytest

from src.domain.errors.complexity_budget import (
    ComplexityBudgetApprovalRequiredError,
    ComplexityBudgetBreachedError,
    ComplexityBudgetEscalationError,
)
from src.domain.models.complexity_budget import ComplexityDimension


class TestComplexityBudgetBreachedError:
    """Tests for ComplexityBudgetBreachedError."""

    def test_create_error_with_defaults(self) -> None:
        """Test creating error with default message."""
        error = ComplexityBudgetBreachedError(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=18,
        )
        assert error.dimension == ComplexityDimension.ADR_COUNT
        assert error.limit == 15
        assert error.actual_value == 18
        assert error.overage == 3
        assert error.breach_id is None

    def test_error_message_includes_details(self) -> None:
        """Test error message includes all relevant details."""
        error = ComplexityBudgetBreachedError(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=18,
        )
        message = str(error)
        assert "adr_count" in message
        assert "18" in message
        assert "15" in message
        assert "CT-14" in message
        assert "RT-6" in message

    def test_custom_message(self) -> None:
        """Test custom message overrides default."""
        custom = "Custom breach message"
        error = ComplexityBudgetBreachedError(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=18,
            message=custom,
        )
        assert str(error) == custom

    def test_with_breach_id(self) -> None:
        """Test error with breach_id."""
        breach_id = uuid4()
        error = ComplexityBudgetBreachedError(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=18,
            breach_id=breach_id,
        )
        assert error.breach_id == breach_id

    def test_remediation_hints_for_adr_count(self) -> None:
        """Test remediation hints for ADR_COUNT dimension."""
        error = ComplexityBudgetBreachedError(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=18,
        )
        hints = error.get_remediation_hints()
        assert len(hints) >= 2
        assert "ADR" in hints[0]
        assert "governance ceremony" in hints[-1].lower()

    def test_remediation_hints_for_ceremony_types(self) -> None:
        """Test remediation hints for CEREMONY_TYPES dimension."""
        error = ComplexityBudgetBreachedError(
            dimension=ComplexityDimension.CEREMONY_TYPES,
            limit=10,
            actual_value=12,
        )
        hints = error.get_remediation_hints()
        assert len(hints) >= 2
        assert "ceremony" in hints[0].lower()

    def test_remediation_hints_for_cross_component_deps(self) -> None:
        """Test remediation hints for CROSS_COMPONENT_DEPS dimension."""
        error = ComplexityBudgetBreachedError(
            dimension=ComplexityDimension.CROSS_COMPONENT_DEPS,
            limit=20,
            actual_value=25,
        )
        hints = error.get_remediation_hints()
        assert len(hints) >= 2
        assert "dependency" in hints[0].lower() or "coupling" in hints[0].lower()

    def test_is_exception(self) -> None:
        """Test that error is an Exception."""
        error = ComplexityBudgetBreachedError(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=18,
        )
        assert isinstance(error, Exception)

    def test_can_be_raised(self) -> None:
        """Test that error can be raised and caught."""
        with pytest.raises(ComplexityBudgetBreachedError) as exc_info:
            raise ComplexityBudgetBreachedError(
                dimension=ComplexityDimension.ADR_COUNT,
                limit=15,
                actual_value=18,
            )
        assert exc_info.value.dimension == ComplexityDimension.ADR_COUNT


class TestComplexityBudgetApprovalRequiredError:
    """Tests for ComplexityBudgetApprovalRequiredError."""

    def test_create_error(self) -> None:
        """Test creating approval required error."""
        breach_id = uuid4()
        error = ComplexityBudgetApprovalRequiredError(
            dimension=ComplexityDimension.ADR_COUNT,
            breach_id=breach_id,
        )
        assert error.dimension == ComplexityDimension.ADR_COUNT
        assert error.breach_id == breach_id

    def test_error_message_includes_details(self) -> None:
        """Test error message includes all relevant details."""
        breach_id = uuid4()
        error = ComplexityBudgetApprovalRequiredError(
            dimension=ComplexityDimension.ADR_COUNT,
            breach_id=breach_id,
        )
        message = str(error)
        assert "adr_count" in message
        assert str(breach_id) in message
        assert "RT-6" in message
        assert "governance" in message.lower()

    def test_custom_message(self) -> None:
        """Test custom message overrides default."""
        custom = "Custom approval required message"
        error = ComplexityBudgetApprovalRequiredError(
            dimension=ComplexityDimension.ADR_COUNT,
            breach_id=uuid4(),
            message=custom,
        )
        assert str(error) == custom

    def test_is_exception(self) -> None:
        """Test that error is an Exception."""
        error = ComplexityBudgetApprovalRequiredError(
            dimension=ComplexityDimension.ADR_COUNT,
            breach_id=uuid4(),
        )
        assert isinstance(error, Exception)


class TestComplexityBudgetEscalationError:
    """Tests for ComplexityBudgetEscalationError."""

    def test_create_error(self) -> None:
        """Test creating escalation error."""
        breach_id = uuid4()
        escalation_id = uuid4()
        error = ComplexityBudgetEscalationError(
            breach_id=breach_id,
            escalation_id=escalation_id,
            days_without_resolution=10,
        )
        assert error.breach_id == breach_id
        assert error.escalation_id == escalation_id
        assert error.days_without_resolution == 10
        assert error.escalation_level == 1

    def test_error_message_includes_details(self) -> None:
        """Test error message includes all relevant details."""
        breach_id = uuid4()
        escalation_id = uuid4()
        error = ComplexityBudgetEscalationError(
            breach_id=breach_id,
            escalation_id=escalation_id,
            days_without_resolution=10,
        )
        message = str(error)
        assert str(breach_id) in message
        assert "10" in message
        assert "RT-6" in message

    def test_custom_message(self) -> None:
        """Test custom message overrides default."""
        custom = "Custom escalation message"
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=10,
            message=custom,
        )
        assert str(error) == custom

    def test_escalation_level(self) -> None:
        """Test escalation level can be set."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=20,
            escalation_level=3,
        )
        assert error.escalation_level == 3

    def test_is_critical_at_level_2(self) -> None:
        """Test is_critical is True at level 2."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=14,
            escalation_level=2,
        )
        assert error.is_critical is True

    def test_is_critical_at_level_1(self) -> None:
        """Test is_critical is False at level 1."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=7,
            escalation_level=1,
        )
        assert error.is_critical is False

    def test_requires_immediate_action_over_14_days(self) -> None:
        """Test requires_immediate_action is True over 14 days."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=15,
            escalation_level=1,
        )
        assert error.requires_immediate_action is True

    def test_requires_immediate_action_at_level_2(self) -> None:
        """Test requires_immediate_action is True at level 2."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=7,
            escalation_level=2,
        )
        assert error.requires_immediate_action is True

    def test_requires_immediate_action_false(self) -> None:
        """Test requires_immediate_action is False for early escalation."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=7,
            escalation_level=1,
        )
        assert error.requires_immediate_action is False

    def test_critical_severity_in_message(self) -> None:
        """Test CRITICAL severity appears in message at level 2+."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=14,
            escalation_level=2,
        )
        assert "CRITICAL" in str(error)

    def test_elevated_severity_in_message(self) -> None:
        """Test ELEVATED severity appears in message at level 1."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=7,
            escalation_level=1,
        )
        assert "ELEVATED" in str(error)

    def test_is_exception(self) -> None:
        """Test that error is an Exception."""
        error = ComplexityBudgetEscalationError(
            breach_id=uuid4(),
            escalation_id=uuid4(),
            days_without_resolution=7,
        )
        assert isinstance(error, Exception)
