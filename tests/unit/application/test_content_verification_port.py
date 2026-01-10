"""Unit tests for ContentVerificationPort interface (Story 2.5, FR13).

Tests the application port interface for content verification
and the ContentVerificationResult dataclass.

Constitutional Constraints Verified:
- FR13: Published hash must equal canonical hash
- AC3: Verification endpoint returns TRUE/FALSE with hash values
"""

from uuid import uuid4

import pytest

from src.application.ports.content_verification import (
    ContentVerificationPort,
    ContentVerificationResult,
)


class TestContentVerificationResult:
    """Test suite for ContentVerificationResult dataclass."""

    def test_result_with_matching_hashes(self) -> None:
        """ContentVerificationResult captures matching hash state."""
        content_id = uuid4()
        hash_value = "a" * 64

        result = ContentVerificationResult(
            matches=True,
            stored_hash=hash_value,
            computed_hash=hash_value,
            content_id=content_id,
        )

        assert result.matches is True
        assert result.stored_hash == hash_value
        assert result.computed_hash == hash_value
        assert result.content_id == content_id

    def test_result_with_mismatched_hashes(self) -> None:
        """ContentVerificationResult captures mismatched hash state."""
        content_id = uuid4()
        stored = "a" * 64
        computed = "b" * 64

        result = ContentVerificationResult(
            matches=False,
            stored_hash=stored,
            computed_hash=computed,
            content_id=content_id,
        )

        assert result.matches is False
        assert result.stored_hash == stored
        assert result.computed_hash == computed

    def test_result_is_frozen(self) -> None:
        """ContentVerificationResult is immutable (frozen dataclass)."""
        content_id = uuid4()
        result = ContentVerificationResult(
            matches=True,
            stored_hash="a" * 64,
            computed_hash="a" * 64,
            content_id=content_id,
        )

        with pytest.raises(AttributeError):
            result.matches = False  # type: ignore[misc]

    def test_result_equality(self) -> None:
        """ContentVerificationResult equality based on values."""
        content_id = uuid4()
        hash_value = "c" * 64

        result1 = ContentVerificationResult(
            matches=True,
            stored_hash=hash_value,
            computed_hash=hash_value,
            content_id=content_id,
        )
        result2 = ContentVerificationResult(
            matches=True,
            stored_hash=hash_value,
            computed_hash=hash_value,
            content_id=content_id,
        )

        assert result1 == result2


class TestContentVerificationPort:
    """Test suite for ContentVerificationPort protocol."""

    def test_port_is_protocol(self) -> None:
        """ContentVerificationPort is a typing.Protocol."""
        from typing import Protocol

        assert issubclass(ContentVerificationPort, Protocol)

    def test_port_defines_get_stored_hash(self) -> None:
        """Port defines get_stored_hash method."""
        assert hasattr(ContentVerificationPort, "get_stored_hash")

    def test_port_defines_verify_content(self) -> None:
        """Port defines verify_content method (AC3)."""
        assert hasattr(ContentVerificationPort, "verify_content")
