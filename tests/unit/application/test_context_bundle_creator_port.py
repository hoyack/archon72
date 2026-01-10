"""Unit tests for ContextBundleCreatorPort interface (Story 2.9, ADR-2).

Tests cover:
- BundleCreationResult dataclass validation
- BundleVerificationResult dataclass validation
- Port interface definition
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.context_bundle_creator import (
    BundleCreationResult,
    BundleVerificationResult,
    ContextBundleCreatorPort,
)
from src.domain.models.context_bundle import (
    CONTENT_REF_PREFIX,
    ContextBundlePayload,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def valid_bundle_payload() -> ContextBundlePayload:
    """Return a valid ContextBundlePayload."""
    return ContextBundlePayload(
        schema_version="1.0",
        meeting_id=uuid4(),
        as_of_event_seq=42,
        identity_prompt_ref=f"{CONTENT_REF_PREFIX}{'a' * 64}",
        meeting_state_ref=f"{CONTENT_REF_PREFIX}{'b' * 64}",
        precedent_refs=tuple(),
        created_at=datetime.now(timezone.utc),
        bundle_hash="c" * 64,
        signature="test_signature",
        signing_key_id="key-001",
    )


# ============================================================================
# BundleCreationResult Tests
# ============================================================================


class TestBundleCreationResult:
    """Tests for BundleCreationResult dataclass."""

    def test_successful_result_requires_bundle(
        self,
        valid_bundle_payload: ContextBundlePayload,
    ) -> None:
        """Successful result should have bundle."""
        result = BundleCreationResult(
            success=True,
            bundle=valid_bundle_payload,
            bundle_hash="c" * 64,
        )
        assert result.success is True
        assert result.bundle is not None

    def test_successful_result_requires_bundle_hash(
        self,
        valid_bundle_payload: ContextBundlePayload,
    ) -> None:
        """Successful result should have bundle_hash."""
        with pytest.raises(ValueError, match="bundle_hash required"):
            BundleCreationResult(
                success=True,
                bundle=valid_bundle_payload,
                bundle_hash=None,
            )

    def test_successful_result_without_bundle_raises_error(self) -> None:
        """Successful result without bundle should raise error."""
        with pytest.raises(ValueError, match="bundle required"):
            BundleCreationResult(
                success=True,
                bundle=None,
                bundle_hash="c" * 64,
            )

    def test_failed_result_requires_error_message(self) -> None:
        """Failed result should have error_message."""
        with pytest.raises(ValueError, match="error_message required"):
            BundleCreationResult(
                success=False,
                bundle=None,
                bundle_hash=None,
                error_message=None,
            )

    def test_failed_result_with_error_message(self) -> None:
        """Failed result with error message should be valid."""
        result = BundleCreationResult(
            success=False,
            bundle=None,
            bundle_hash=None,
            error_message="Creation failed: HSM unavailable",
        )
        assert result.success is False
        assert result.error_message == "Creation failed: HSM unavailable"

    def test_result_is_frozen(
        self,
        valid_bundle_payload: ContextBundlePayload,
    ) -> None:
        """BundleCreationResult should be frozen."""
        result = BundleCreationResult(
            success=True,
            bundle=valid_bundle_payload,
            bundle_hash="c" * 64,
        )
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


# ============================================================================
# BundleVerificationResult Tests
# ============================================================================


class TestBundleVerificationResult:
    """Tests for BundleVerificationResult dataclass."""

    def test_valid_result_requires_bundle_id(self) -> None:
        """Valid result should have bundle_id."""
        result = BundleVerificationResult(
            valid=True,
            bundle_id="ctx_test_42",
            signing_key_id="key-001",
        )
        assert result.valid is True
        assert result.bundle_id == "ctx_test_42"

    def test_valid_result_without_bundle_id_raises_error(self) -> None:
        """Valid result without bundle_id should raise error."""
        with pytest.raises(ValueError, match="bundle_id required"):
            BundleVerificationResult(
                valid=True,
                bundle_id=None,
                signing_key_id="key-001",
            )

    def test_invalid_result_requires_error_message(self) -> None:
        """Invalid result should have error_message."""
        with pytest.raises(ValueError, match="error_message required"):
            BundleVerificationResult(
                valid=False,
                bundle_id=None,
                signing_key_id=None,
                error_message=None,
            )

    def test_invalid_result_with_error_message(self) -> None:
        """Invalid result with error message should be valid."""
        result = BundleVerificationResult(
            valid=False,
            bundle_id=None,
            signing_key_id=None,
            error_message="ADR-2: Invalid context bundle signature",
        )
        assert result.valid is False
        assert "ADR-2" in result.error_message

    def test_result_is_frozen(self) -> None:
        """BundleVerificationResult should be frozen."""
        result = BundleVerificationResult(
            valid=True,
            bundle_id="ctx_test_42",
            signing_key_id="key-001",
        )
        with pytest.raises(AttributeError):
            result.valid = False  # type: ignore[misc]


# ============================================================================
# ContextBundleCreatorPort Interface Tests
# ============================================================================


class TestContextBundleCreatorPort:
    """Tests for ContextBundleCreatorPort interface definition."""

    def test_port_is_abstract_class(self) -> None:
        """Port should be an abstract class."""
        from abc import ABC

        assert issubclass(ContextBundleCreatorPort, ABC)

    def test_port_has_create_bundle_method(self) -> None:
        """Port should have create_bundle abstract method."""
        assert hasattr(ContextBundleCreatorPort, "create_bundle")
        assert callable(ContextBundleCreatorPort.create_bundle)

    def test_port_has_verify_bundle_method(self) -> None:
        """Port should have verify_bundle abstract method."""
        assert hasattr(ContextBundleCreatorPort, "verify_bundle")
        assert callable(ContextBundleCreatorPort.verify_bundle)

    def test_port_has_get_signing_key_id_method(self) -> None:
        """Port should have get_signing_key_id abstract method."""
        assert hasattr(ContextBundleCreatorPort, "get_signing_key_id")
        assert callable(ContextBundleCreatorPort.get_signing_key_id)

    def test_cannot_instantiate_port_directly(self) -> None:
        """Should not be able to instantiate port directly."""
        with pytest.raises(TypeError, match="abstract"):
            ContextBundleCreatorPort()  # type: ignore[abstract]
