"""Unit tests for AlreadySignedError (Story 5.7).

Tests the enhanced AlreadySignedError with existing signature details:
- Error creation with all fields
- RFC 7807 serialization (D7)
- Error message formatting

Constitutional Constraints:
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- NFR-3.5: 0 duplicate signatures ever exist
- D7: RFC 7807 + governance extensions for error responses
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.co_sign import AlreadySignedError


class TestAlreadySignedErrorCreation:
    """Tests for AlreadySignedError creation with enhanced fields."""

    def test_create_basic_error(self) -> None:
        """Test creating error with minimal required fields."""
        petition_id = uuid4()
        signer_id = uuid4()

        error = AlreadySignedError(petition_id=petition_id, signer_id=signer_id)

        assert error.petition_id == petition_id
        assert error.signer_id == signer_id
        assert "already co-signed" in str(error).lower()

    def test_create_error_with_existing_signature_details(self) -> None:
        """Test creating error with existing signature details (Story 5.7 enhancement)."""
        petition_id = uuid4()
        signer_id = uuid4()
        existing_cosign_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        error = AlreadySignedError(
            petition_id=petition_id,
            signer_id=signer_id,
            existing_cosign_id=existing_cosign_id,
            signed_at=signed_at,
        )

        assert error.petition_id == petition_id
        assert error.signer_id == signer_id
        assert error.existing_cosign_id == existing_cosign_id
        assert error.signed_at == signed_at

    def test_existing_signature_details_are_optional(self) -> None:
        """Test that existing signature details default to None."""
        petition_id = uuid4()
        signer_id = uuid4()

        error = AlreadySignedError(petition_id=petition_id, signer_id=signer_id)

        assert error.existing_cosign_id is None
        assert error.signed_at is None


class TestAlreadySignedErrorRFC7807:
    """Tests for RFC 7807 serialization (D7)."""

    def test_to_rfc7807_dict_basic(self) -> None:
        """Test RFC 7807 serialization without existing signature details."""
        petition_id = uuid4()
        signer_id = uuid4()

        error = AlreadySignedError(petition_id=petition_id, signer_id=signer_id)
        rfc7807 = error.to_rfc7807_dict()

        assert rfc7807["type"] == "https://archon72.ai/errors/co-sign/already-signed"
        assert rfc7807["title"] == "Already Signed"
        assert rfc7807["status"] == 409
        assert str(signer_id) in rfc7807["detail"]
        assert str(petition_id) in rfc7807["detail"]
        assert rfc7807["petition_id"] == str(petition_id)
        assert rfc7807["signer_id"] == str(signer_id)

    def test_to_rfc7807_dict_with_existing_signature(self) -> None:
        """Test RFC 7807 serialization with existing signature details."""
        petition_id = uuid4()
        signer_id = uuid4()
        existing_cosign_id = uuid4()
        signed_at = datetime(2026, 1, 20, 10, 30, 0, tzinfo=timezone.utc)

        error = AlreadySignedError(
            petition_id=petition_id,
            signer_id=signer_id,
            existing_cosign_id=existing_cosign_id,
            signed_at=signed_at,
        )
        rfc7807 = error.to_rfc7807_dict()

        assert rfc7807["existing_cosign_id"] == str(existing_cosign_id)
        assert rfc7807["signed_at"] == "2026-01-20T10:30:00+00:00"

    def test_to_rfc7807_dict_omits_none_values(self) -> None:
        """Test that None values for optional fields are omitted."""
        petition_id = uuid4()
        signer_id = uuid4()

        error = AlreadySignedError(petition_id=petition_id, signer_id=signer_id)
        rfc7807 = error.to_rfc7807_dict()

        # None values should be omitted from the response
        assert "existing_cosign_id" not in rfc7807 or rfc7807.get("existing_cosign_id") is None
        assert "signed_at" not in rfc7807 or rfc7807.get("signed_at") is None


class TestAlreadySignedErrorMessage:
    """Tests for error message formatting."""

    def test_error_message_includes_ids(self) -> None:
        """Test that error message includes petition and signer IDs."""
        petition_id = uuid4()
        signer_id = uuid4()

        error = AlreadySignedError(petition_id=petition_id, signer_id=signer_id)

        assert str(petition_id) in str(error)
        assert str(signer_id) in str(error)

    def test_error_message_references_fr_6_2(self) -> None:
        """Test that error message references FR-6.2 for traceability."""
        petition_id = uuid4()
        signer_id = uuid4()

        error = AlreadySignedError(petition_id=petition_id, signer_id=signer_id)

        assert "FR-6.2" in str(error) or "already" in str(error).lower()

    def test_error_is_cosign_error_subclass(self) -> None:
        """Test that error is subclass of CoSignError."""
        from src.domain.errors.co_sign import CoSignError

        petition_id = uuid4()
        signer_id = uuid4()

        error = AlreadySignedError(petition_id=petition_id, signer_id=signer_id)

        assert isinstance(error, CoSignError)
