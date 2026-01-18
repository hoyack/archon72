"""Tests for write-time validation errors.

Story: consent-gov-1.4: Write-Time Validation
AC5: WriteTimeValidationError with specific failure reason (not generic failure)
"""

from uuid import uuid4

import pytest

from src.domain.governance.errors.validation_errors import (
    HashChainBreakError,
    IllegalStateTransitionError,
    UnknownActorError,
    UnknownEventTypeError,
    WriteTimeValidationError,
)


class TestWriteTimeValidationError:
    """Tests for base WriteTimeValidationError."""

    def test_is_exception(self) -> None:
        """WriteTimeValidationError is an Exception."""
        assert issubclass(WriteTimeValidationError, Exception)

    def test_can_be_raised(self) -> None:
        """WriteTimeValidationError can be raised and caught."""
        with pytest.raises(WriteTimeValidationError):
            raise WriteTimeValidationError("test error")

    def test_subclasses_caught_as_base(self) -> None:
        """Subclasses can be caught as base WriteTimeValidationError."""
        with pytest.raises(WriteTimeValidationError):
            raise IllegalStateTransitionError(
                event_id=uuid4(),
                aggregate_type="task",
                aggregate_id="task-1",
                current_state="pending",
                attempted_state="completed",
                allowed_states=["authorized"],
            )


class TestIllegalStateTransitionError:
    """Tests for IllegalStateTransitionError."""

    @pytest.fixture
    def error(self) -> IllegalStateTransitionError:
        """Create a test error instance."""
        return IllegalStateTransitionError(
            event_id=uuid4(),
            aggregate_type="task",
            aggregate_id="task-123",
            current_state="authorized",
            attempted_state="completed",
            allowed_states=["activated", "expired", "cancelled"],
        )

    def test_is_write_time_validation_error(
        self, error: IllegalStateTransitionError
    ) -> None:
        """IllegalStateTransitionError is a WriteTimeValidationError."""
        assert isinstance(error, WriteTimeValidationError)

    def test_is_frozen_dataclass(self, error: IllegalStateTransitionError) -> None:
        """IllegalStateTransitionError is immutable."""
        with pytest.raises(AttributeError):
            error.current_state = "new_state"  # type: ignore

    def test_str_includes_aggregate_info(
        self, error: IllegalStateTransitionError
    ) -> None:
        """Error message includes aggregate type and ID."""
        msg = str(error)
        assert "task:task-123" in msg

    def test_str_includes_states(self, error: IllegalStateTransitionError) -> None:
        """Error message includes current and attempted states."""
        msg = str(error)
        assert "authorized" in msg
        assert "completed" in msg

    def test_str_includes_allowed_states(
        self, error: IllegalStateTransitionError
    ) -> None:
        """Error message includes allowed transitions."""
        msg = str(error)
        assert "activated" in msg
        assert "expired" in msg

    def test_str_includes_ad_reference(
        self, error: IllegalStateTransitionError
    ) -> None:
        """Error message includes architectural decision reference."""
        msg = str(error)
        assert "AD-12" in msg

    def test_hash_based_on_event_id(self) -> None:
        """Hash is based on event_id."""
        event_id = uuid4()
        error1 = IllegalStateTransitionError(
            event_id=event_id,
            aggregate_type="task",
            aggregate_id="task-1",
            current_state="pending",
            attempted_state="completed",
            allowed_states=[],
        )
        error2 = IllegalStateTransitionError(
            event_id=event_id,
            aggregate_type="different",
            aggregate_id="different",
            current_state="different",
            attempted_state="different",
            allowed_states=["different"],
        )
        assert hash(error1) == hash(error2)

    def test_equality_based_on_event_id(self) -> None:
        """Equality is based on event_id."""
        event_id = uuid4()
        error1 = IllegalStateTransitionError(
            event_id=event_id,
            aggregate_type="task",
            aggregate_id="task-1",
            current_state="pending",
            attempted_state="completed",
            allowed_states=[],
        )
        error2 = IllegalStateTransitionError(
            event_id=event_id,
            aggregate_type="different",
            aggregate_id="different",
            current_state="different",
            attempted_state="different",
            allowed_states=["different"],
        )
        assert error1 == error2

    def test_empty_allowed_states(self) -> None:
        """Error handles empty allowed states (terminal state)."""
        error = IllegalStateTransitionError(
            event_id=uuid4(),
            aggregate_type="task",
            aggregate_id="task-1",
            current_state="completed",
            attempted_state="activated",
            allowed_states=[],
        )
        msg = str(error)
        assert "none" in msg.lower()


class TestHashChainBreakError:
    """Tests for HashChainBreakError."""

    @pytest.fixture
    def error(self) -> HashChainBreakError:
        """Create a test error instance."""
        return HashChainBreakError(
            event_id=uuid4(),
            expected_prev_hash="blake3:abc123def456789012345678901234567890abcd",
            actual_prev_hash="blake3:wrong123456789012345678901234567890wxyz",
            latest_sequence=42,
        )

    def test_is_write_time_validation_error(self, error: HashChainBreakError) -> None:
        """HashChainBreakError is a WriteTimeValidationError."""
        assert isinstance(error, WriteTimeValidationError)

    def test_is_frozen_dataclass(self, error: HashChainBreakError) -> None:
        """HashChainBreakError is immutable."""
        with pytest.raises(AttributeError):
            error.expected_prev_hash = "new_hash"  # type: ignore

    def test_str_includes_hashes(self, error: HashChainBreakError) -> None:
        """Error message includes hash values (truncated)."""
        msg = str(error)
        assert "blake3:" in msg
        # Should be truncated
        assert "..." in msg

    def test_str_includes_sequence(self, error: HashChainBreakError) -> None:
        """Error message includes latest sequence for context."""
        msg = str(error)
        assert "42" in msg

    def test_str_includes_ad_reference(self, error: HashChainBreakError) -> None:
        """Error message includes architectural decision reference."""
        msg = str(error)
        assert "AD-6" in msg

    def test_without_sequence(self) -> None:
        """Error works without latest_sequence."""
        error = HashChainBreakError(
            event_id=uuid4(),
            expected_prev_hash="blake3:abc",
            actual_prev_hash="blake3:def",
        )
        msg = str(error)
        assert "blake3:" in msg


class TestUnknownEventTypeError:
    """Tests for UnknownEventTypeError."""

    @pytest.fixture
    def error(self) -> UnknownEventTypeError:
        """Create a test error instance."""
        return UnknownEventTypeError(
            event_id=uuid4(),
            event_type="fake.branch.action",
            suggestion="filter.branch.action",
        )

    def test_is_write_time_validation_error(self, error: UnknownEventTypeError) -> None:
        """UnknownEventTypeError is a WriteTimeValidationError."""
        assert isinstance(error, WriteTimeValidationError)

    def test_str_includes_event_type(self, error: UnknownEventTypeError) -> None:
        """Error message includes the unknown event type."""
        msg = str(error)
        assert "fake.branch.action" in msg

    def test_str_includes_suggestion(self, error: UnknownEventTypeError) -> None:
        """Error message includes suggestion when provided."""
        msg = str(error)
        assert "filter.branch.action" in msg
        assert "Did you mean" in msg

    def test_str_without_suggestion(self) -> None:
        """Error message works without suggestion."""
        error = UnknownEventTypeError(
            event_id=uuid4(),
            event_type="fake.branch.action",
        )
        msg = str(error)
        assert "fake.branch.action" in msg
        assert "Did you mean" not in msg

    def test_str_includes_ad_reference(self, error: UnknownEventTypeError) -> None:
        """Error message includes architectural decision reference."""
        msg = str(error)
        assert "AD-5" in msg


class TestUnknownActorError:
    """Tests for UnknownActorError."""

    @pytest.fixture
    def error(self) -> UnknownActorError:
        """Create a test error instance."""
        return UnknownActorError(
            event_id=uuid4(),
            actor_id="unknown-archon-99",
        )

    def test_is_write_time_validation_error(self, error: UnknownActorError) -> None:
        """UnknownActorError is a WriteTimeValidationError."""
        assert isinstance(error, WriteTimeValidationError)

    def test_str_includes_actor_id(self, error: UnknownActorError) -> None:
        """Error message includes the unknown actor ID."""
        msg = str(error)
        assert "unknown-archon-99" in msg

    def test_str_includes_ct_reference(self, error: UnknownActorError) -> None:
        """Error message includes Constitutional Truth reference."""
        msg = str(error)
        assert "CT-12" in msg
