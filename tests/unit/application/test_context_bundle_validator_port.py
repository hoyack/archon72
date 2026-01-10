"""Unit tests for ContextBundleValidatorPort interface (Story 2.9, ADR-2).

Tests cover:
- BundleValidationResult dataclass validation
- FreshnessCheckResult dataclass validation
- Port interface definition
"""


import pytest

from src.application.ports.context_bundle_validator import (
    BundleValidationResult,
    ContextBundleValidatorPort,
    FreshnessCheckResult,
)

# ============================================================================
# BundleValidationResult Tests
# ============================================================================


class TestBundleValidationResult:
    """Tests for BundleValidationResult dataclass."""

    def test_valid_result_creates_successfully(self) -> None:
        """Valid result should create successfully."""
        result = BundleValidationResult(
            valid=True,
            bundle_id="ctx_test_42",
        )
        assert result.valid is True
        assert result.bundle_id == "ctx_test_42"

    def test_invalid_result_requires_error_message(self) -> None:
        """Invalid result should require error_message."""
        with pytest.raises(ValueError, match="error_message required"):
            BundleValidationResult(
                valid=False,
                bundle_id=None,
            )

    def test_invalid_result_with_error_message(self) -> None:
        """Invalid result with error message should be valid."""
        result = BundleValidationResult(
            valid=False,
            bundle_id="ctx_test_1",
            error_code="INVALID_SIGNATURE",
            error_message="ADR-2: Invalid context bundle signature",
        )
        assert result.valid is False
        assert result.error_code == "INVALID_SIGNATURE"
        assert "ADR-2" in result.error_message

    def test_result_is_frozen(self) -> None:
        """BundleValidationResult should be frozen."""
        result = BundleValidationResult(
            valid=True,
            bundle_id="ctx_test_1",
        )
        with pytest.raises(AttributeError):
            result.valid = False  # type: ignore[misc]

    def test_result_with_error_code_only(self) -> None:
        """Result can have error_code without error_message when valid."""
        result = BundleValidationResult(
            valid=True,
            bundle_id="ctx_test_1",
            error_code=None,
        )
        assert result.error_code is None


# ============================================================================
# FreshnessCheckResult Tests
# ============================================================================


class TestFreshnessCheckResult:
    """Tests for FreshnessCheckResult dataclass."""

    def test_fresh_result_creates_successfully(self) -> None:
        """Fresh result should create successfully."""
        result = FreshnessCheckResult(
            fresh=True,
            as_of_event_seq=42,
            current_head_seq=100,
        )
        assert result.fresh is True
        assert result.as_of_event_seq == 42
        assert result.current_head_seq == 100

    def test_stale_result_requires_error_message(self) -> None:
        """Stale result should require error_message."""
        with pytest.raises(ValueError, match="error_message required"):
            FreshnessCheckResult(
                fresh=False,
                as_of_event_seq=10,
                current_head_seq=100,
            )

    def test_stale_result_with_error_message(self) -> None:
        """Stale result with error message should be valid."""
        result = FreshnessCheckResult(
            fresh=False,
            as_of_event_seq=10,
            current_head_seq=100,
            error_message="Bundle references stale sequence",
        )
        assert result.fresh is False
        assert result.as_of_event_seq == 10
        assert result.current_head_seq == 100
        assert "stale" in result.error_message.lower()

    def test_result_is_frozen(self) -> None:
        """FreshnessCheckResult should be frozen."""
        result = FreshnessCheckResult(
            fresh=True,
            as_of_event_seq=42,
            current_head_seq=100,
        )
        with pytest.raises(AttributeError):
            result.fresh = False  # type: ignore[misc]

    def test_future_sequence_scenario(self) -> None:
        """Future sequence (as_of > head) should be stale."""
        result = FreshnessCheckResult(
            fresh=False,
            as_of_event_seq=150,  # Future
            current_head_seq=100,  # Current head
            error_message="Bundle references future sequence",
        )
        assert result.fresh is False
        assert result.as_of_event_seq > result.current_head_seq


# ============================================================================
# ContextBundleValidatorPort Interface Tests
# ============================================================================


class TestContextBundleValidatorPort:
    """Tests for ContextBundleValidatorPort interface definition."""

    def test_port_is_abstract_class(self) -> None:
        """Port should be an abstract class."""
        from abc import ABC

        assert issubclass(ContextBundleValidatorPort, ABC)

    def test_port_has_validate_signature_method(self) -> None:
        """Port should have validate_signature abstract method."""
        assert hasattr(ContextBundleValidatorPort, "validate_signature")
        assert callable(ContextBundleValidatorPort.validate_signature)

    def test_port_has_validate_schema_method(self) -> None:
        """Port should have validate_schema abstract method."""
        assert hasattr(ContextBundleValidatorPort, "validate_schema")
        assert callable(ContextBundleValidatorPort.validate_schema)

    def test_port_has_validate_freshness_method(self) -> None:
        """Port should have validate_freshness abstract method."""
        assert hasattr(ContextBundleValidatorPort, "validate_freshness")
        assert callable(ContextBundleValidatorPort.validate_freshness)

    def test_port_has_validate_all_method(self) -> None:
        """Port should have validate_all abstract method."""
        assert hasattr(ContextBundleValidatorPort, "validate_all")
        assert callable(ContextBundleValidatorPort.validate_all)

    def test_cannot_instantiate_port_directly(self) -> None:
        """Should not be able to instantiate port directly."""
        with pytest.raises(TypeError, match="abstract"):
            ContextBundleValidatorPort()  # type: ignore[abstract]
