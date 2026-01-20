"""Integration tests for submitter rate limiting (Story 1.4, FR-1.5, HC-4).

Tests the complete flow of per-submitter rate limiting including:
- POST /v1/petition-submissions returns 429 when rate limit exceeded
- Retry-After header is present and correct (AC1)
- RFC 7807 error response with rate limit extensions (AC1)
- Rate limit check happens AFTER capacity check (AC2)
- Rate limit recorded AFTER successful submission (Golden Rule)
- Prometheus metrics are recorded (AC4)

Constitutional Constraints Tested:
- FR-1.5: Enforce rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- NFR-5.1: Rate limiting per identity
- D4: PostgreSQL time-bucket counters (via stub)
- CT-11: Fail loud, not silent - return 429
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.petition_submission import (
    reset_petition_submission_dependencies,
    set_queue_capacity_service,
    set_rate_limit_config,
    set_rate_limiter,
)
from src.api.main import app
from src.application.services.queue_capacity_service import QueueCapacityService
from src.config.petition_config import PetitionRateLimitConfig
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.rate_limiter_stub import RateLimiterStub


@pytest.fixture(autouse=True)
def reset_dependencies() -> None:
    """Reset dependencies before each test."""
    reset_petition_submission_dependencies()


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def submitter_id():
    """Create a test submitter UUID."""
    return uuid4()


@pytest.fixture
def test_config() -> PetitionRateLimitConfig:
    """Create test configuration with low limit."""
    return PetitionRateLimitConfig(
        limit_per_hour=3,  # Low for testing
        window_minutes=5,
        bucket_ttl_hours=1,
    )


def _setup_queue_with_capacity() -> None:
    """Set up queue capacity service that always has capacity."""
    repo = PetitionSubmissionRepositoryStub()
    service = QueueCapacityService(
        repository=repo,
        threshold=10000,
        cache_ttl_seconds=300.0,
    )
    service._set_cached_depth(0)  # Empty queue
    set_queue_capacity_service(service)


class TestRateLimiting429Response:
    """Tests for HTTP 429 responses on rate limit exceeded (FR-1.5, AC1)."""

    def test_returns_429_when_rate_limit_exceeded(
        self, client: TestClient, submitter_id
    ) -> None:
        """Should return 429 when submitter exceeds rate limit (FR-1.5)."""
        _setup_queue_with_capacity()

        # Set up rate limiter that's at limit
        limiter = RateLimiterStub.at_limit(
            submitter_id=submitter_id,
            limit=10,
            reset_in_seconds=1800,
        )
        set_rate_limiter(limiter)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition text",
                "submitter_id": str(submitter_id),
            },
        )

        assert response.status_code == 429

    def test_returns_201_when_under_rate_limit(
        self, client: TestClient, submitter_id
    ) -> None:
        """Should return 201 when submitter is under rate limit."""
        _setup_queue_with_capacity()

        # Set up rate limiter that allows submissions
        limiter = RateLimiterStub(limit=10)
        limiter.set_count(submitter_id, 5)  # Under limit
        set_rate_limiter(limiter)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition text",
                "submitter_id": str(submitter_id),
            },
        )

        assert response.status_code == 201

    def test_different_submitters_have_independent_limits(
        self, client: TestClient
    ) -> None:
        """Different submitters should have independent rate limits."""
        _setup_queue_with_capacity()

        submitter_a = uuid4()
        submitter_b = uuid4()

        # Submitter A is at limit, submitter B is not
        limiter = RateLimiterStub(limit=10)
        limiter.set_count(submitter_a, 10)  # At limit
        limiter.set_count(submitter_b, 5)  # Under limit
        set_rate_limiter(limiter)

        # Submitter A should be rejected
        response_a = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_a),
            },
        )
        assert response_a.status_code == 429

        # Submitter B should be accepted
        response_b = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_b),
            },
        )
        assert response_b.status_code == 201


class TestRetryAfterHeader:
    """Tests for Retry-After header on 429 responses (AC1)."""

    def test_429_includes_retry_after_header(
        self, client: TestClient, submitter_id
    ) -> None:
        """429 response should include Retry-After header (AC1)."""
        _setup_queue_with_capacity()

        # Set up rate limiter at limit with known reset time
        limiter = RateLimiterStub.at_limit(
            submitter_id=submitter_id,
            limit=10,
            reset_in_seconds=1800,  # 30 minutes
        )
        set_rate_limiter(limiter)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_id),
            },
        )

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        # Should be approximately 1800 seconds (may be slightly less due to time passing)
        retry_after = int(response.headers["Retry-After"])
        assert 1700 <= retry_after <= 1800


class TestRFC7807ErrorResponse:
    """Tests for RFC 7807 error response with rate limit extensions (AC1)."""

    def test_429_response_has_rfc7807_format(
        self, client: TestClient, submitter_id
    ) -> None:
        """429 response should follow RFC 7807 format with rate limit extensions."""
        _setup_queue_with_capacity()

        limiter = RateLimiterStub.at_limit(
            submitter_id=submitter_id,
            limit=10,
        )
        set_rate_limiter(limiter)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_id),
            },
        )

        assert response.status_code == 429
        data = response.json()["detail"]

        # RFC 7807 required fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data

        # Rate limit extensions (AC1)
        assert "rate_limit_remaining" in data
        assert "rate_limit_reset" in data
        assert "rate_limit_limit" in data
        assert "rate_limit_current" in data

        # Governance extension (D7)
        assert "actor" in data

    def test_429_response_type_is_rate_limit_exceeded(
        self, client: TestClient, submitter_id
    ) -> None:
        """Error type should be rate-limit-exceeded."""
        _setup_queue_with_capacity()

        limiter = RateLimiterStub.at_limit(submitter_id=submitter_id, limit=10)
        set_rate_limiter(limiter)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_id),
            },
        )

        data = response.json()["detail"]
        assert data["type"] == "urn:archon72:petition:rate-limit-exceeded"
        assert data["title"] == "Rate Limit Exceeded"
        assert data["status"] == 429

    def test_429_response_includes_rate_limit_info(
        self, client: TestClient, submitter_id
    ) -> None:
        """429 response should include detailed rate limit info."""
        _setup_queue_with_capacity()

        limiter = RateLimiterStub.over_limit(
            submitter_id=submitter_id,
            limit=10,
            current_count=15,
        )
        set_rate_limiter(limiter)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_id),
            },
        )

        data = response.json()["detail"]
        assert data["rate_limit_limit"] == 10
        assert data["rate_limit_current"] == 15
        assert data["rate_limit_remaining"] == 0


class TestRateLimitOrderOfOperations:
    """Tests for correct order: capacity check FIRST, rate limit check SECOND (AC2)."""

    def test_capacity_check_before_rate_limit(
        self, client: TestClient, submitter_id
    ) -> None:
        """Queue overflow should return 503 even if rate limit would be 429."""
        # Set up queue that rejects (at capacity)
        repo = PetitionSubmissionRepositoryStub()
        capacity_service = QueueCapacityService(
            repository=repo,
            threshold=5,
        )
        capacity_service._set_cached_depth(10)  # Over threshold
        set_queue_capacity_service(capacity_service)

        # Set up rate limiter that would also reject
        limiter = RateLimiterStub.at_limit(submitter_id=submitter_id, limit=10)
        set_rate_limiter(limiter)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_id),
            },
        )

        # Should get 503 (capacity) not 429 (rate limit)
        # because capacity check happens FIRST
        assert response.status_code == 503


class TestRateLimitRecordingAfterSuccess:
    """Tests that rate limit is recorded only after successful submission."""

    def test_successful_submission_increments_rate_limit(
        self, client: TestClient, submitter_id
    ) -> None:
        """Successful submission should increment rate limit counter."""
        _setup_queue_with_capacity()

        limiter = RateLimiterStub(limit=10)
        set_rate_limiter(limiter)

        # Verify initial count is 0
        assert limiter.get_count(submitter_id) == 0

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_id),
            },
        )

        assert response.status_code == 201
        # Count should now be 1
        assert limiter.get_count(submitter_id) == 1

    def test_rejected_submission_does_not_increment_rate_limit(
        self, client: TestClient, submitter_id
    ) -> None:
        """Rate-limited submission should NOT increment rate limit counter."""
        _setup_queue_with_capacity()

        # Start at limit
        limiter = RateLimiterStub(limit=10)
        limiter.set_count(submitter_id, 10)
        set_rate_limiter(limiter)

        initial_count = limiter.get_count(submitter_id)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition",
                "submitter_id": str(submitter_id),
            },
        )

        assert response.status_code == 429
        # Count should NOT have increased
        assert limiter.get_count(submitter_id) == initial_count


class TestDifferentPetitionTypes:
    """Tests that rate limiting applies to all petition types equally."""

    @pytest.mark.parametrize(
        "petition_type",
        ["GENERAL", "CESSATION", "GRIEVANCE", "COLLABORATION"],
    )
    def test_all_petition_types_rate_limited(
        self, client: TestClient, submitter_id, petition_type: str
    ) -> None:
        """All petition types should be rate limited."""
        _setup_queue_with_capacity()

        limiter = RateLimiterStub.at_limit(submitter_id=submitter_id, limit=10)
        set_rate_limiter(limiter)

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": petition_type,
                "text": "Test petition",
                "submitter_id": str(submitter_id),
            },
        )

        assert response.status_code == 429


class TestHC4DefaultLimit:
    """Tests for HC-4 compliant default limit (10 petitions/user/hour)."""

    def test_allows_exactly_10_submissions(
        self, client: TestClient, submitter_id
    ) -> None:
        """Should allow up to 10 submissions per hour per HC-4."""
        _setup_queue_with_capacity()

        # Use default limit of 10
        limiter = RateLimiterStub(limit=10)
        set_rate_limiter(limiter)

        # Submit 10 petitions (all should succeed)
        for i in range(10):
            response = client.post(
                "/v1/petition-submissions",
                json={
                    "type": "GENERAL",
                    "text": f"Test petition {i + 1}",
                    "submitter_id": str(submitter_id),
                },
            )
            assert response.status_code == 201, f"Submission {i + 1} failed"

        # 11th should fail
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition 11",
                "submitter_id": str(submitter_id),
            },
        )
        assert response.status_code == 429


class TestEnvironmentConfiguration:
    """Tests for environment variable configuration (AC5)."""

    def test_custom_limit_from_config(
        self, client: TestClient, submitter_id, test_config: PetitionRateLimitConfig
    ) -> None:
        """Rate limit should respect configured limit."""
        _setup_queue_with_capacity()
        set_rate_limit_config(test_config)  # limit=3

        # Use config values for limiter
        limiter = RateLimiterStub(
            limit=test_config.limit_per_hour,
            window_minutes=test_config.window_minutes,
        )
        set_rate_limiter(limiter)

        # Submit 3 petitions (all should succeed)
        for i in range(3):
            response = client.post(
                "/v1/petition-submissions",
                json={
                    "type": "GENERAL",
                    "text": f"Test petition {i + 1}",
                    "submitter_id": str(submitter_id),
                },
            )
            assert response.status_code == 201

        # 4th should fail (limit is 3)
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition 4",
                "submitter_id": str(submitter_id),
            },
        )
        assert response.status_code == 429
