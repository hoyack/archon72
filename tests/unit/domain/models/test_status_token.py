"""Unit tests for StatusToken domain model (Story 7.1, Task 1).

Tests cover:
- Token creation and encoding
- Token decoding and validation
- Expiry validation
- Petition ID validation
- State change detection
- Version computation

Constitutional Constraints:
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99
"""

import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.models.status_token import (
    ExpiredStatusTokenError,
    InvalidStatusTokenError,
    StatusToken,
)


class TestStatusTokenCreate:
    """Tests for StatusToken.create() factory method."""

    def test_create_with_valid_inputs(self) -> None:
        """Test creating a token with valid petition_id and version."""
        petition_id = uuid4()
        version = 42

        token = StatusToken.create(petition_id=petition_id, version=version)

        assert token.petition_id == petition_id
        assert token.version == version
        assert token.created_at is not None
        assert token.created_at.tzinfo == timezone.utc

    def test_create_sets_current_timestamp(self) -> None:
        """Test that create() uses current UTC time."""
        before = datetime.now(timezone.utc)
        token = StatusToken.create(petition_id=uuid4(), version=1)
        after = datetime.now(timezone.utc)

        assert before <= token.created_at <= after

    def test_create_with_zero_version(self) -> None:
        """Test creating token with version 0."""
        token = StatusToken.create(petition_id=uuid4(), version=0)
        assert token.version == 0

    def test_create_with_large_version(self) -> None:
        """Test creating token with large version number."""
        large_version = 2**32 - 1  # Max uint32
        token = StatusToken.create(petition_id=uuid4(), version=large_version)
        assert token.version == large_version


class TestStatusTokenEncode:
    """Tests for StatusToken.encode() method."""

    def test_encode_returns_base64url_string(self) -> None:
        """Test that encode returns a valid base64url string."""
        token = StatusToken.create(petition_id=uuid4(), version=1)
        encoded = token.encode()

        # Should be a non-empty string
        assert isinstance(encoded, str)
        assert len(encoded) > 0

        # Should be valid base64url (no + or /)
        assert "+" not in encoded
        assert "/" not in encoded

    def test_encode_is_url_safe(self) -> None:
        """Test that encoded token is URL-safe."""
        token = StatusToken.create(petition_id=uuid4(), version=999)
        encoded = token.encode()

        # Base64url uses - and _ instead of + and /
        # Should only contain alphanumeric, -, _, and = (padding)
        import re

        assert re.match(r"^[A-Za-z0-9_=-]+$", encoded), f"Not URL-safe: {encoded}"

    def test_encode_deterministic(self) -> None:
        """Test that encoding is deterministic for same token."""
        petition_id = uuid4()
        created_at = datetime.now(timezone.utc)
        token = StatusToken(petition_id=petition_id, version=42, created_at=created_at)

        encoded1 = token.encode()
        encoded2 = token.encode()

        assert encoded1 == encoded2


class TestStatusTokenDecode:
    """Tests for StatusToken.decode() class method."""

    def test_decode_roundtrip(self) -> None:
        """Test that encode/decode roundtrip preserves data."""
        original = StatusToken.create(petition_id=uuid4(), version=123)
        encoded = original.encode()
        decoded = StatusToken.decode(encoded)

        assert decoded.petition_id == original.petition_id
        assert decoded.version == original.version
        # Timestamps should be within 1 second (unix timestamp precision)
        assert abs((decoded.created_at - original.created_at).total_seconds()) < 1

    def test_decode_invalid_base64(self) -> None:
        """Test that invalid base64 raises InvalidStatusTokenError."""
        with pytest.raises(InvalidStatusTokenError) as exc_info:
            StatusToken.decode("not_valid_base64!!!")

        assert "Failed to decode token" in str(exc_info.value)

    def test_decode_wrong_format(self) -> None:
        """Test that wrong internal format raises InvalidStatusTokenError."""
        # Encode valid base64 but wrong format
        wrong_format = base64.urlsafe_b64encode(b"just:two").decode()
        with pytest.raises(InvalidStatusTokenError) as exc_info:
            StatusToken.decode(wrong_format)

        assert "expected 3 parts" in str(exc_info.value)

    def test_decode_invalid_uuid(self) -> None:
        """Test that invalid UUID raises InvalidStatusTokenError."""
        invalid_data = base64.urlsafe_b64encode(b"not-a-uuid:1:1234567890").decode()
        with pytest.raises(InvalidStatusTokenError):
            StatusToken.decode(invalid_data)

    def test_decode_invalid_version(self) -> None:
        """Test that non-integer version raises InvalidStatusTokenError."""
        petition_id = uuid4()
        invalid_data = base64.urlsafe_b64encode(
            f"{petition_id}:not_int:1234567890".encode()
        ).decode()

        with pytest.raises(InvalidStatusTokenError):
            StatusToken.decode(invalid_data)

    def test_decode_invalid_timestamp(self) -> None:
        """Test that non-integer timestamp raises InvalidStatusTokenError."""
        petition_id = uuid4()
        invalid_data = base64.urlsafe_b64encode(
            f"{petition_id}:1:not_timestamp".encode()
        ).decode()

        with pytest.raises(InvalidStatusTokenError):
            StatusToken.decode(invalid_data)

    def test_decode_empty_string(self) -> None:
        """Test that empty string raises InvalidStatusTokenError."""
        with pytest.raises(InvalidStatusTokenError):
            StatusToken.decode("")


class TestStatusTokenValidateNotExpired:
    """Tests for StatusToken.validate_not_expired() method."""

    def test_fresh_token_not_expired(self) -> None:
        """Test that a freshly created token is not expired."""
        token = StatusToken.create(petition_id=uuid4(), version=1)
        # Should not raise
        token.validate_not_expired()

    def test_expired_token_raises(self) -> None:
        """Test that an expired token raises ExpiredStatusTokenError."""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=400)
        token = StatusToken(petition_id=uuid4(), version=1, created_at=old_time)

        with pytest.raises(ExpiredStatusTokenError) as exc_info:
            token.validate_not_expired()

        assert "expired" in str(exc_info.value).lower()
        assert exc_info.value.max_age_seconds == StatusToken.DEFAULT_MAX_AGE_SECONDS

    def test_custom_max_age(self) -> None:
        """Test validation with custom max age."""
        # Token 60 seconds old
        old_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        token = StatusToken(petition_id=uuid4(), version=1, created_at=old_time)

        # Should pass with 120 second max age
        token.validate_not_expired(max_age_seconds=120)

        # Should fail with 30 second max age
        with pytest.raises(ExpiredStatusTokenError) as exc_info:
            token.validate_not_expired(max_age_seconds=30)

        assert exc_info.value.max_age_seconds == 30

    def test_exactly_at_max_age(self) -> None:
        """Test token exactly at max age boundary."""
        # Just under max age - should pass
        almost_expired = datetime.now(timezone.utc) - timedelta(
            seconds=StatusToken.DEFAULT_MAX_AGE_SECONDS - 1
        )
        token = StatusToken(petition_id=uuid4(), version=1, created_at=almost_expired)
        token.validate_not_expired()  # Should not raise


class TestStatusTokenValidatePetitionId:
    """Tests for StatusToken.validate_petition_id() method."""

    def test_matching_petition_id(self) -> None:
        """Test validation passes when petition IDs match."""
        petition_id = uuid4()
        token = StatusToken.create(petition_id=petition_id, version=1)

        # Should not raise
        token.validate_petition_id(petition_id)

    def test_mismatched_petition_id_raises(self) -> None:
        """Test validation fails when petition IDs don't match."""
        token_petition_id = uuid4()
        different_petition_id = uuid4()
        token = StatusToken.create(petition_id=token_petition_id, version=1)

        with pytest.raises(InvalidStatusTokenError) as exc_info:
            token.validate_petition_id(different_petition_id)

        assert "mismatch" in str(exc_info.value).lower()
        assert str(token_petition_id) in str(exc_info.value)
        assert str(different_petition_id) in str(exc_info.value)


class TestStatusTokenHasChanged:
    """Tests for StatusToken.has_changed() method."""

    def test_same_version_not_changed(self) -> None:
        """Test that same version returns False."""
        token = StatusToken.create(petition_id=uuid4(), version=42)
        assert token.has_changed(current_version=42) is False

    def test_different_version_changed(self) -> None:
        """Test that different version returns True."""
        token = StatusToken.create(petition_id=uuid4(), version=42)
        assert token.has_changed(current_version=43) is True
        assert token.has_changed(current_version=41) is True

    def test_zero_versions(self) -> None:
        """Test change detection with zero versions."""
        token = StatusToken.create(petition_id=uuid4(), version=0)
        assert token.has_changed(current_version=0) is False
        assert token.has_changed(current_version=1) is True


class TestStatusTokenComputeVersionFromHash:
    """Tests for StatusToken.compute_version_from_hash() static method."""

    def test_deterministic_for_same_inputs(self) -> None:
        """Test that same inputs produce same version."""
        content_hash = b"test_hash_bytes"
        state = "RECEIVED"

        version1 = StatusToken.compute_version_from_hash(content_hash, state)
        version2 = StatusToken.compute_version_from_hash(content_hash, state)

        assert version1 == version2

    def test_different_for_different_state(self) -> None:
        """Test that different state produces different version."""
        content_hash = b"test_hash_bytes"

        version1 = StatusToken.compute_version_from_hash(content_hash, "RECEIVED")
        version2 = StatusToken.compute_version_from_hash(content_hash, "ACKNOWLEDGED")

        assert version1 != version2

    def test_different_for_different_hash(self) -> None:
        """Test that different hash produces different version."""
        state = "RECEIVED"

        version1 = StatusToken.compute_version_from_hash(b"hash1", state)
        version2 = StatusToken.compute_version_from_hash(b"hash2", state)

        assert version1 != version2

    def test_none_content_hash(self) -> None:
        """Test computation with None content hash."""
        version = StatusToken.compute_version_from_hash(None, "RECEIVED")
        assert isinstance(version, int)
        assert version > 0

    def test_returns_positive_integer(self) -> None:
        """Test that computed version is a positive integer."""
        version = StatusToken.compute_version_from_hash(b"any_hash", "any_state")
        assert isinstance(version, int)
        # First 8 bytes interpreted as unsigned big-endian should be >= 0
        assert version >= 0


class TestStatusTokenFrozen:
    """Tests for immutability of StatusToken dataclass."""

    def test_cannot_modify_petition_id(self) -> None:
        """Test that petition_id cannot be modified after creation."""
        token = StatusToken.create(petition_id=uuid4(), version=1)

        with pytest.raises(AttributeError):
            token.petition_id = uuid4()  # type: ignore

    def test_cannot_modify_version(self) -> None:
        """Test that version cannot be modified after creation."""
        token = StatusToken.create(petition_id=uuid4(), version=1)

        with pytest.raises(AttributeError):
            token.version = 99  # type: ignore

    def test_cannot_modify_created_at(self) -> None:
        """Test that created_at cannot be modified after creation."""
        token = StatusToken.create(petition_id=uuid4(), version=1)

        with pytest.raises(AttributeError):
            token.created_at = datetime.now(timezone.utc)  # type: ignore
