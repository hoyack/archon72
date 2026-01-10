"""Unit tests for certification domain errors (Story 2.8, FR99-FR101).

Tests the certification-related error classes.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.errors.certification import (
    CertificationError,
    CertificationSignatureError,
    ResultHashMismatchError,
)
from src.domain.exceptions import ConclaveError


class TestCertificationError:
    """Tests for CertificationError base class."""

    def test_inherits_from_conclave_error(self) -> None:
        """CertificationError should inherit from ConclaveError."""
        assert issubclass(CertificationError, ConclaveError)

    def test_can_be_raised_with_message(self) -> None:
        """Should be able to raise with a message."""
        with pytest.raises(CertificationError, match="Test error"):
            raise CertificationError("Test error")

    def test_str_representation(self) -> None:
        """Should have string representation."""
        error = CertificationError("Certification failed")
        assert str(error) == "Certification failed"


class TestCertificationSignatureError:
    """Tests for CertificationSignatureError."""

    def test_inherits_from_certification_error(self) -> None:
        """CertificationSignatureError should inherit from CertificationError."""
        assert issubclass(CertificationSignatureError, CertificationError)

    def test_create_with_all_fields(self) -> None:
        """Should create error with all fields."""
        result_id = uuid4()
        expected_key_id = "CERT:key-001"
        actual_key_id = "CERT:key-002"

        error = CertificationSignatureError(
            result_id=result_id,
            expected_key_id=expected_key_id,
            actual_key_id=actual_key_id,
        )

        assert error.result_id == result_id
        assert error.expected_key_id == expected_key_id
        assert error.actual_key_id == actual_key_id

    def test_create_with_none_actual_key_id(self) -> None:
        """Should allow actual_key_id to be None."""
        result_id = uuid4()
        expected_key_id = "CERT:key-001"

        error = CertificationSignatureError(
            result_id=result_id,
            expected_key_id=expected_key_id,
            actual_key_id=None,
        )

        assert error.result_id == result_id
        assert error.expected_key_id == expected_key_id
        assert error.actual_key_id is None

    def test_error_message_includes_details(self) -> None:
        """Error message should include result_id and key IDs."""
        result_id = uuid4()
        expected_key_id = "CERT:key-001"
        actual_key_id = "CERT:key-002"

        error = CertificationSignatureError(
            result_id=result_id,
            expected_key_id=expected_key_id,
            actual_key_id=actual_key_id,
        )

        error_str = str(error)
        assert str(result_id) in error_str
        assert expected_key_id in error_str
        assert actual_key_id in error_str

    def test_error_message_handles_none_actual_key(self) -> None:
        """Error message should handle None actual_key_id."""
        result_id = uuid4()
        expected_key_id = "CERT:key-001"

        error = CertificationSignatureError(
            result_id=result_id,
            expected_key_id=expected_key_id,
            actual_key_id=None,
        )

        error_str = str(error)
        assert str(result_id) in error_str
        assert expected_key_id in error_str
        assert "None" in error_str or "no key" in error_str.lower()


class TestResultHashMismatchError:
    """Tests for ResultHashMismatchError."""

    def test_inherits_from_certification_error(self) -> None:
        """ResultHashMismatchError should inherit from CertificationError."""
        assert issubclass(ResultHashMismatchError, CertificationError)

    def test_create_with_all_fields(self) -> None:
        """Should create error with all fields."""
        result_id = uuid4()
        stored_hash = "a" * 64
        computed_hash = "b" * 64

        error = ResultHashMismatchError(
            result_id=result_id,
            stored_hash=stored_hash,
            computed_hash=computed_hash,
        )

        assert error.result_id == result_id
        assert error.stored_hash == stored_hash
        assert error.computed_hash == computed_hash

    def test_error_message_includes_details(self) -> None:
        """Error message should include result_id and hashes."""
        result_id = uuid4()
        stored_hash = "a" * 64
        computed_hash = "b" * 64

        error = ResultHashMismatchError(
            result_id=result_id,
            stored_hash=stored_hash,
            computed_hash=computed_hash,
        )

        error_str = str(error)
        assert str(result_id) in error_str
        # Should include at least partial hashes for debugging
        assert stored_hash[:8] in error_str or stored_hash in error_str
        assert computed_hash[:8] in error_str or computed_hash in error_str
