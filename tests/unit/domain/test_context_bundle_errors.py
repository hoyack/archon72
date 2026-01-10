"""Unit tests for context bundle domain errors (Story 2.9, ADR-2).

Tests cover:
- Error hierarchy (all inherit from ContextBundleError)
- Error messages and attributes
- ADR-2 specific error messages
"""

import pytest

from src.domain.errors.context_bundle import (
    BundleCreationError,
    BundleNotFoundError,
    BundleSchemaValidationError,
    ContextBundleError,
    InvalidBundleSignatureError,
    StaleBundleError,
)
from src.domain.exceptions import ConclaveError

# ============================================================================
# Error Hierarchy Tests
# ============================================================================


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_context_bundle_error_inherits_from_conclave_error(self) -> None:
        """ContextBundleError should inherit from ConclaveError."""
        assert issubclass(ContextBundleError, ConclaveError)

    def test_invalid_bundle_signature_error_inherits_from_context_bundle_error(
        self,
    ) -> None:
        """InvalidBundleSignatureError should inherit from ContextBundleError."""
        assert issubclass(InvalidBundleSignatureError, ContextBundleError)

    def test_stale_bundle_error_inherits_from_context_bundle_error(self) -> None:
        """StaleBundleError should inherit from ContextBundleError."""
        assert issubclass(StaleBundleError, ContextBundleError)

    def test_bundle_schema_validation_error_inherits_from_context_bundle_error(
        self,
    ) -> None:
        """BundleSchemaValidationError should inherit from ContextBundleError."""
        assert issubclass(BundleSchemaValidationError, ContextBundleError)

    def test_bundle_not_found_error_inherits_from_context_bundle_error(self) -> None:
        """BundleNotFoundError should inherit from ContextBundleError."""
        assert issubclass(BundleNotFoundError, ContextBundleError)

    def test_bundle_creation_error_inherits_from_context_bundle_error(self) -> None:
        """BundleCreationError should inherit from ContextBundleError."""
        assert issubclass(BundleCreationError, ContextBundleError)


# ============================================================================
# InvalidBundleSignatureError Tests
# ============================================================================


class TestInvalidBundleSignatureError:
    """Tests for InvalidBundleSignatureError."""

    def test_default_message_includes_adr_reference(self) -> None:
        """Default message should include ADR-2 reference."""
        error = InvalidBundleSignatureError()
        assert "ADR-2" in str(error)
        assert "Invalid context bundle signature" in str(error)

    def test_custom_message(self) -> None:
        """Custom message should override default."""
        error = InvalidBundleSignatureError(message="Custom error")
        assert str(error) == "Custom error"

    def test_bundle_id_appended_to_message(self) -> None:
        """bundle_id should be appended to message."""
        error = InvalidBundleSignatureError(bundle_id="ctx_test_123")
        assert "ctx_test_123" in str(error)

    def test_error_has_adr_reference_constant(self) -> None:
        """Should have ADR_REFERENCE constant."""
        assert InvalidBundleSignatureError.ADR_REFERENCE == "ADR-2"

    def test_error_attributes_stored(self) -> None:
        """Error attributes should be stored."""
        error = InvalidBundleSignatureError(
            bundle_id="ctx_test_1",
            expected_key_id="key-001",
            provided_key_id="key-002",
        )
        assert error.bundle_id == "ctx_test_1"
        assert error.expected_key_id == "key-001"
        assert error.provided_key_id == "key-002"


# ============================================================================
# StaleBundleError Tests
# ============================================================================


class TestStaleBundleError:
    """Tests for StaleBundleError."""

    def test_default_message_with_sequence_info(self) -> None:
        """Message should include sequence information."""
        error = StaleBundleError(as_of_event_seq=10, current_head_seq=100)
        assert "10" in str(error)
        assert "100" in str(error)
        assert "stale" in str(error).lower()

    def test_default_message_without_sequence_info(self) -> None:
        """Message without sequence info should be generic."""
        error = StaleBundleError()
        assert "not in canonical chain" in str(error)

    def test_custom_message(self) -> None:
        """Custom message should override default."""
        error = StaleBundleError(message="Custom stale error")
        assert str(error) == "Custom stale error"

    def test_bundle_id_appended_to_message(self) -> None:
        """bundle_id should be appended to message."""
        error = StaleBundleError(
            bundle_id="ctx_test_42",
            as_of_event_seq=10,
            current_head_seq=100,
        )
        assert "ctx_test_42" in str(error)

    def test_error_attributes_stored(self) -> None:
        """Error attributes should be stored."""
        error = StaleBundleError(
            bundle_id="ctx_test_1",
            as_of_event_seq=10,
            current_head_seq=100,
        )
        assert error.bundle_id == "ctx_test_1"
        assert error.as_of_event_seq == 10
        assert error.current_head_seq == 100


# ============================================================================
# BundleSchemaValidationError Tests
# ============================================================================


class TestBundleSchemaValidationError:
    """Tests for BundleSchemaValidationError."""

    def test_default_message_without_errors(self) -> None:
        """Default message without validation errors."""
        error = BundleSchemaValidationError()
        assert "schema validation failed" in str(error).lower()

    def test_message_with_validation_errors(self) -> None:
        """Message should include validation errors."""
        error = BundleSchemaValidationError(
            validation_errors=["missing field: bundle_id", "invalid type: meeting_id"]
        )
        assert "missing field" in str(error)
        assert "invalid type" in str(error)

    def test_message_truncates_many_errors(self) -> None:
        """Message should truncate if many errors."""
        errors = [f"error {i}" for i in range(10)]
        error = BundleSchemaValidationError(validation_errors=errors)
        assert "+7 more" in str(error)

    def test_custom_message(self) -> None:
        """Custom message should override default."""
        error = BundleSchemaValidationError(message="Custom schema error")
        assert str(error) == "Custom schema error"

    def test_bundle_id_appended_to_message(self) -> None:
        """bundle_id should be appended to message."""
        error = BundleSchemaValidationError(
            bundle_id="ctx_test_1",
            validation_errors=["test error"],
        )
        assert "ctx_test_1" in str(error)

    def test_error_attributes_stored(self) -> None:
        """Error attributes should be stored."""
        errors = ["error1", "error2"]
        error = BundleSchemaValidationError(
            bundle_id="ctx_test_1",
            validation_errors=errors,
        )
        assert error.bundle_id == "ctx_test_1"
        assert error.validation_errors == errors


# ============================================================================
# BundleNotFoundError Tests
# ============================================================================


class TestBundleNotFoundError:
    """Tests for BundleNotFoundError."""

    def test_default_message(self) -> None:
        """Default message without bundle_id."""
        error = BundleNotFoundError()
        assert "not found" in str(error).lower()

    def test_message_with_bundle_id(self) -> None:
        """Message should include bundle_id."""
        error = BundleNotFoundError(bundle_id="ctx_test_123")
        assert "ctx_test_123" in str(error)
        assert "not found" in str(error).lower()

    def test_custom_message(self) -> None:
        """Custom message should override default."""
        error = BundleNotFoundError(message="Custom not found")
        assert str(error) == "Custom not found"

    def test_error_attributes_stored(self) -> None:
        """Error attributes should be stored."""
        error = BundleNotFoundError(bundle_id="ctx_test_1")
        assert error.bundle_id == "ctx_test_1"


# ============================================================================
# BundleCreationError Tests
# ============================================================================


class TestBundleCreationError:
    """Tests for BundleCreationError."""

    def test_default_message(self) -> None:
        """Default message without context."""
        error = BundleCreationError()
        assert "creation failed" in str(error).lower()

    def test_message_with_cause(self) -> None:
        """Message should include cause."""
        error = BundleCreationError(cause="HSM unavailable")
        assert "HSM unavailable" in str(error)

    def test_message_with_meeting_id(self) -> None:
        """Message should include meeting_id."""
        error = BundleCreationError(meeting_id="meeting-123")
        assert "meeting-123" in str(error)

    def test_custom_message(self) -> None:
        """Custom message should override default."""
        error = BundleCreationError(message="Custom creation error")
        assert str(error) == "Custom creation error"

    def test_error_attributes_stored(self) -> None:
        """Error attributes should be stored."""
        error = BundleCreationError(
            meeting_id="meeting-123",
            cause="test cause",
        )
        assert error.meeting_id == "meeting-123"
        assert error.cause == "test cause"


# ============================================================================
# Exception Catching Tests
# ============================================================================


class TestExceptionCatching:
    """Tests for catching exceptions at different levels."""

    def test_catch_as_context_bundle_error(self) -> None:
        """All bundle errors should be catchable as ContextBundleError."""
        errors = [
            InvalidBundleSignatureError(),
            StaleBundleError(),
            BundleSchemaValidationError(),
            BundleNotFoundError(),
            BundleCreationError(),
        ]
        for error in errors:
            with pytest.raises(ContextBundleError):
                raise error

    def test_catch_as_conclave_error(self) -> None:
        """All bundle errors should be catchable as ConclaveError."""
        errors = [
            InvalidBundleSignatureError(),
            StaleBundleError(),
            BundleSchemaValidationError(),
            BundleNotFoundError(),
            BundleCreationError(),
        ]
        for error in errors:
            with pytest.raises(ConclaveError):
                raise error
