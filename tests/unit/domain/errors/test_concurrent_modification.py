"""Unit tests for ConcurrentModificationError (Story 1.6, FR-2.4).

Tests verify:
- Error message formatting
- Attribute preservation
- Error inheritance hierarchy
"""

from uuid import uuid4

import pytest

from src.domain.errors.concurrent_modification import ConcurrentModificationError
from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.models.petition_submission import PetitionState


class TestConcurrentModificationError:
    """Tests for ConcurrentModificationError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """ConcurrentModificationError inherits from ConstitutionalViolationError."""
        petition_id = uuid4()
        error = ConcurrentModificationError(
            petition_id=petition_id,
            expected_state=PetitionState.DELIBERATING,
        )
        assert isinstance(error, ConstitutionalViolationError)
        assert isinstance(error, Exception)

    def test_error_message_contains_petition_id(self) -> None:
        """Error message includes petition ID."""
        petition_id = uuid4()
        error = ConcurrentModificationError(
            petition_id=petition_id,
            expected_state=PetitionState.DELIBERATING,
        )
        assert str(petition_id) in str(error)

    def test_error_message_contains_expected_state(self) -> None:
        """Error message includes expected state value."""
        petition_id = uuid4()
        error = ConcurrentModificationError(
            petition_id=petition_id,
            expected_state=PetitionState.DELIBERATING,
        )
        assert "DELIBERATING" in str(error)

    def test_error_message_contains_operation(self) -> None:
        """Error message includes operation description."""
        petition_id = uuid4()
        error = ConcurrentModificationError(
            petition_id=petition_id,
            expected_state=PetitionState.RECEIVED,
            operation="state_transition",
        )
        assert "state_transition" in str(error)

    def test_default_operation_is_fate_assignment(self) -> None:
        """Default operation is 'fate_assignment'."""
        petition_id = uuid4()
        error = ConcurrentModificationError(
            petition_id=petition_id,
            expected_state=PetitionState.DELIBERATING,
        )
        assert error.operation == "fate_assignment"
        assert "fate_assignment" in str(error)

    def test_attributes_preserved(self) -> None:
        """All attributes are preserved on the error object."""
        petition_id = uuid4()
        expected_state = PetitionState.DELIBERATING
        operation = "custom_operation"

        error = ConcurrentModificationError(
            petition_id=petition_id,
            expected_state=expected_state,
            operation=operation,
        )

        assert error.petition_id == petition_id
        assert error.expected_state == expected_state
        assert error.operation == operation

    def test_error_with_received_state(self) -> None:
        """Error works with RECEIVED state."""
        petition_id = uuid4()
        error = ConcurrentModificationError(
            petition_id=petition_id,
            expected_state=PetitionState.RECEIVED,
        )
        assert error.expected_state == PetitionState.RECEIVED
        assert "RECEIVED" in str(error)

    def test_error_can_be_raised_and_caught(self) -> None:
        """Error can be raised and caught as ConstitutionalViolationError."""
        petition_id = uuid4()
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            raise ConcurrentModificationError(
                petition_id=petition_id,
                expected_state=PetitionState.DELIBERATING,
            )
        assert isinstance(exc_info.value, ConcurrentModificationError)

    def test_error_message_indicates_concurrent_modification(self) -> None:
        """Error message clearly indicates concurrent modification."""
        petition_id = uuid4()
        error = ConcurrentModificationError(
            petition_id=petition_id,
            expected_state=PetitionState.DELIBERATING,
        )
        assert "concurrent" in str(error).lower() or "Concurrent" in str(error)

    def test_error_is_importable_from_domain_errors(self) -> None:
        """ConcurrentModificationError can be imported from domain errors."""
        from src.domain.errors import ConcurrentModificationError as ImportedError
        assert ImportedError is ConcurrentModificationError
