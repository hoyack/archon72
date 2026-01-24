"""Unit tests for StatusTokenService (Story 7.1, Task 3).

Tests cover:
- Token generation
- Token validation (valid, expired, wrong petition ID)
- Change detection
- Version computation

Constitutional Constraints:
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.status_token_service import StatusTokenService
from src.domain.models.status_token import (
    ExpiredStatusTokenError,
    InvalidStatusTokenError,
    StatusToken,
)


@pytest.fixture
def service() -> StatusTokenService:
    """Create a StatusTokenService instance for testing."""
    return StatusTokenService()


@pytest.fixture
def service_with_short_max_age() -> StatusTokenService:
    """Create a StatusTokenService with short max age for testing expiry."""
    return StatusTokenService(default_max_age_seconds=5)


class TestStatusTokenServiceGenerateToken:
    """Tests for StatusTokenService.generate_token()."""

    def test_generate_token_returns_status_token(
        self, service: StatusTokenService
    ) -> None:
        """generate_token returns a StatusToken instance."""
        petition_id = uuid4()
        version = 42

        token = service.generate_token(petition_id, version)

        assert isinstance(token, StatusToken)

    def test_generate_token_sets_petition_id(self, service: StatusTokenService) -> None:
        """generate_token sets the correct petition_id."""
        petition_id = uuid4()

        token = service.generate_token(petition_id, 1)

        assert token.petition_id == petition_id

    def test_generate_token_sets_version(self, service: StatusTokenService) -> None:
        """generate_token sets the correct version."""
        version = 12345

        token = service.generate_token(uuid4(), version)

        assert token.version == version

    def test_generate_token_sets_current_timestamp(
        self, service: StatusTokenService
    ) -> None:
        """generate_token sets created_at to current time."""
        before = datetime.now(timezone.utc)
        token = service.generate_token(uuid4(), 1)
        after = datetime.now(timezone.utc)

        assert before <= token.created_at <= after


class TestStatusTokenServiceValidateToken:
    """Tests for StatusTokenService.validate_token()."""

    def test_validate_valid_token(self, service: StatusTokenService) -> None:
        """validate_token returns parsed token for valid input."""
        petition_id = uuid4()
        original_token = service.generate_token(petition_id, 99)
        token_string = original_token.encode()

        validated = service.validate_token(token_string, petition_id)

        assert validated.petition_id == petition_id
        assert validated.version == 99

    def test_validate_invalid_base64_raises(self, service: StatusTokenService) -> None:
        """validate_token raises InvalidStatusTokenError for invalid base64."""
        with pytest.raises(InvalidStatusTokenError):
            service.validate_token("not-valid-base64!!!", uuid4())

    def test_validate_wrong_petition_id_raises(
        self, service: StatusTokenService
    ) -> None:
        """validate_token raises InvalidStatusTokenError for petition ID mismatch."""
        petition_id = uuid4()
        different_id = uuid4()
        token = service.generate_token(petition_id, 1)
        token_string = token.encode()

        with pytest.raises(InvalidStatusTokenError) as exc_info:
            service.validate_token(token_string, different_id)

        assert "mismatch" in str(exc_info.value).lower()

    def test_validate_expired_token_raises(
        self, service_with_short_max_age: StatusTokenService
    ) -> None:
        """validate_token raises ExpiredStatusTokenError for expired tokens."""
        petition_id = uuid4()
        # Create an old token manually
        old_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        old_token = StatusToken(petition_id=petition_id, version=1, created_at=old_time)
        token_string = old_token.encode()

        with pytest.raises(ExpiredStatusTokenError):
            service_with_short_max_age.validate_token(token_string, petition_id)

    def test_validate_with_custom_max_age(self, service: StatusTokenService) -> None:
        """validate_token respects custom max_age_seconds parameter."""
        petition_id = uuid4()
        # Token 100 seconds old
        old_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        old_token = StatusToken(petition_id=petition_id, version=1, created_at=old_time)
        token_string = old_token.encode()

        # Should pass with 200 second max age
        validated = service.validate_token(
            token_string, petition_id, max_age_seconds=200
        )
        assert validated.petition_id == petition_id

        # Should fail with 50 second max age
        with pytest.raises(ExpiredStatusTokenError):
            service.validate_token(token_string, petition_id, max_age_seconds=50)

    def test_validate_fresh_token_not_expired(
        self, service: StatusTokenService
    ) -> None:
        """validate_token accepts fresh tokens."""
        petition_id = uuid4()
        token = service.generate_token(petition_id, 1)
        token_string = token.encode()

        # Should not raise
        validated = service.validate_token(token_string, petition_id)
        assert validated is not None


class TestStatusTokenServiceHasChanged:
    """Tests for StatusTokenService.has_changed()."""

    def test_has_changed_same_version_returns_false(
        self, service: StatusTokenService
    ) -> None:
        """has_changed returns False when versions match."""
        token = service.generate_token(uuid4(), 42)

        assert service.has_changed(token, 42) is False

    def test_has_changed_different_version_returns_true(
        self, service: StatusTokenService
    ) -> None:
        """has_changed returns True when versions differ."""
        token = service.generate_token(uuid4(), 42)

        assert service.has_changed(token, 43) is True
        assert service.has_changed(token, 41) is True

    def test_has_changed_zero_version(self, service: StatusTokenService) -> None:
        """has_changed works correctly with version 0."""
        token = service.generate_token(uuid4(), 0)

        assert service.has_changed(token, 0) is False
        assert service.has_changed(token, 1) is True


class TestStatusTokenServiceComputeVersion:
    """Tests for StatusTokenService.compute_version()."""

    def test_compute_version_deterministic(self, service: StatusTokenService) -> None:
        """compute_version returns same result for same inputs."""
        content_hash = b"test_hash"
        state = "RECEIVED"

        v1 = service.compute_version(content_hash, state)
        v2 = service.compute_version(content_hash, state)

        assert v1 == v2

    def test_compute_version_differs_for_different_state(
        self, service: StatusTokenService
    ) -> None:
        """compute_version returns different result for different state."""
        content_hash = b"test_hash"

        v1 = service.compute_version(content_hash, "RECEIVED")
        v2 = service.compute_version(content_hash, "ACKNOWLEDGED")

        assert v1 != v2

    def test_compute_version_differs_for_different_hash(
        self, service: StatusTokenService
    ) -> None:
        """compute_version returns different result for different hash."""
        state = "RECEIVED"

        v1 = service.compute_version(b"hash1", state)
        v2 = service.compute_version(b"hash2", state)

        assert v1 != v2

    def test_compute_version_handles_none_hash(
        self, service: StatusTokenService
    ) -> None:
        """compute_version handles None content_hash."""
        version = service.compute_version(None, "RECEIVED")

        assert isinstance(version, int)
        assert version >= 0

    def test_compute_version_returns_positive_int(
        self, service: StatusTokenService
    ) -> None:
        """compute_version returns a positive integer."""
        version = service.compute_version(b"any_hash", "any_state")

        assert isinstance(version, int)
        assert version >= 0


class TestStatusTokenServiceProtocolCompliance:
    """Tests verifying protocol compliance."""

    def test_implements_protocol_methods(self, service: StatusTokenService) -> None:
        """Service implements all StatusTokenServiceProtocol methods."""
        # Verify all required methods exist and are callable
        assert callable(getattr(service, "generate_token", None))
        assert callable(getattr(service, "validate_token", None))
        assert callable(getattr(service, "has_changed", None))
        assert callable(getattr(service, "compute_version", None))

    def test_service_can_be_used_through_protocol_type(self) -> None:
        """Service can be assigned to protocol type."""
        from src.application.ports.status_token_service import (
            StatusTokenServiceProtocol,
        )

        service: StatusTokenServiceProtocol = StatusTokenService()

        # Should work through protocol type
        token = service.generate_token(uuid4(), 1)
        assert token is not None
