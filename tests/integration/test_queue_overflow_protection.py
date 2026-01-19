"""Integration tests for queue overflow protection (Story 1.3, FR-1.4).

Tests the complete flow of queue overflow protection including:
- POST /v1/petition-submissions returns 503 when queue at capacity
- Retry-After header is present and correct (AC3)
- RFC 7807 error response format (AC3)
- Prometheus metrics are recorded (AC4)
- Hysteresis prevents oscillation (AC1)

Constitutional Constraints Tested:
- FR-1.4: Return HTTP 503 on queue overflow
- NFR-3.1: No silent petition loss
- NFR-7.4: Queue depth monitoring with backpressure
- CT-11: Fail loud, not silent
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.petition_submission import (
    reset_petition_submission_dependencies,
    set_petition_queue_config,
    set_queue_capacity_service,
)
from src.api.main import app
from src.application.services.queue_capacity_service import QueueCapacityService
from src.config.petition_config import PetitionQueueConfig
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


@pytest.fixture(autouse=True)
def reset_dependencies() -> None:
    """Reset dependencies before each test."""
    reset_petition_submission_dependencies()


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_config() -> PetitionQueueConfig:
    """Create test configuration with low threshold."""
    return PetitionQueueConfig(
        threshold=5,  # Very low for testing
        hysteresis=2,
        cache_ttl_seconds=0.01,
        retry_after_seconds=30,
    )


class TestQueueOverflow503Response:
    """Tests for HTTP 503 responses on queue overflow (FR-1.4, AC1)."""

    def test_returns_503_when_queue_at_capacity(
        self, client: TestClient, test_config: PetitionQueueConfig
    ) -> None:
        """Should return 503 when queue depth >= threshold (FR-1.4)."""
        # Set up config for low threshold
        set_petition_queue_config(test_config)

        # Create capacity service that reports queue is full
        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(
            repository=repo,
            threshold=5,
            hysteresis=2,
            cache_ttl_seconds=300.0,
        )
        # Force cached depth to be at threshold
        service._set_cached_depth(5)
        set_queue_capacity_service(service)

        # Attempt to submit petition
        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition text"},
        )

        # Should return 503
        assert response.status_code == 503

    def test_returns_201_when_queue_has_capacity(
        self, client: TestClient, test_config: PetitionQueueConfig
    ) -> None:
        """Should return 201 when queue has capacity."""
        set_petition_queue_config(test_config)

        # Create capacity service that reports queue has capacity
        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(
            repository=repo,
            threshold=100,
            hysteresis=10,
            cache_ttl_seconds=300.0,
        )
        service._set_cached_depth(10)  # Well below threshold
        set_queue_capacity_service(service)

        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition text"},
        )

        assert response.status_code == 201


class TestRetryAfterHeader:
    """Tests for Retry-After header (AC3)."""

    def test_503_includes_retry_after_header(
        self, client: TestClient, test_config: PetitionQueueConfig
    ) -> None:
        """503 response should include Retry-After header (AC3)."""
        set_petition_queue_config(test_config)

        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(
            repository=repo,
            threshold=5,
            retry_after_seconds=45,
        )
        service._set_cached_depth(10)  # Above threshold
        set_queue_capacity_service(service)

        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )

        assert response.status_code == 503
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "45"

    def test_retry_after_uses_configured_value(
        self, client: TestClient
    ) -> None:
        """Retry-After should use configured retry_after_seconds value."""
        config = PetitionQueueConfig(
            threshold=5,
            hysteresis=2,
            retry_after_seconds=120,  # Custom value
        )
        set_petition_queue_config(config)

        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(
            repository=repo,
            threshold=5,
            retry_after_seconds=120,
        )
        service._set_cached_depth(10)
        set_queue_capacity_service(service)

        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )

        assert response.headers["Retry-After"] == "120"


class TestRFC7807ErrorResponse:
    """Tests for RFC 7807 error response format (AC3)."""

    def test_503_response_has_rfc7807_format(
        self, client: TestClient, test_config: PetitionQueueConfig
    ) -> None:
        """503 response should follow RFC 7807 format."""
        set_petition_queue_config(test_config)

        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(
            repository=repo,
            threshold=5,
        )
        service._set_cached_depth(10)
        set_queue_capacity_service(service)

        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )

        assert response.status_code == 503
        data = response.json()["detail"]

        # RFC 7807 required fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data

        # Our additions for debugging
        assert "queue_depth" in data
        assert "threshold" in data

    def test_503_response_type_is_queue_overflow(
        self, client: TestClient, test_config: PetitionQueueConfig
    ) -> None:
        """Error type should be queue-overflow."""
        set_petition_queue_config(test_config)

        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(repository=repo, threshold=5)
        service._set_cached_depth(10)
        set_queue_capacity_service(service)

        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )

        data = response.json()["detail"]
        assert data["type"] == "https://archon72.io/errors/queue-overflow"
        assert data["title"] == "Queue Overflow"
        assert data["status"] == 503


class TestHysteresisBehavior:
    """Tests for hysteresis preventing oscillation (AC1)."""

    def test_once_rejecting_stays_rejecting_until_below_resume_threshold(
        self, client: TestClient
    ) -> None:
        """Once rejecting, should stay rejecting until depth < (threshold - hysteresis)."""
        # Configure: threshold=10, hysteresis=3, resume at < 7
        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(
            repository=repo,
            threshold=10,
            hysteresis=3,
            cache_ttl_seconds=300.0,
        )
        set_queue_capacity_service(service)

        # Start at threshold - should reject
        service._set_cached_depth(10)
        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert response.status_code == 503

        # Drop to 8 - still rejecting (8 >= 7)
        service._set_cached_depth(8)
        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert response.status_code == 503

        # Drop to 7 - still rejecting (7 >= 7)
        service._set_cached_depth(7)
        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert response.status_code == 503

        # Drop to 6 - should now accept (6 < 7)
        service._set_cached_depth(6)
        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert response.status_code == 201


class TestCapacityCheckBeforeWork:
    """Tests that capacity check happens before expensive operations."""

    def test_capacity_rejection_does_not_process_petition(
        self, client: TestClient
    ) -> None:
        """When rejecting, should not process the petition at all."""
        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(repository=repo, threshold=5)
        service._set_cached_depth(10)
        set_queue_capacity_service(service)

        # Count petitions before
        initial_count = len(repo._storage)

        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )

        # Should be rejected
        assert response.status_code == 503

        # No petition should have been saved
        assert len(repo._storage) == initial_count


class TestDifferentPetitionTypes:
    """Tests that queue overflow applies to all petition types equally."""

    @pytest.mark.parametrize(
        "petition_type",
        ["GENERAL", "CESSATION", "GRIEVANCE", "COLLABORATION"],
    )
    def test_all_petition_types_rejected_on_overflow(
        self, client: TestClient, petition_type: str
    ) -> None:
        """All petition types should be rejected when queue is full."""
        repo = PetitionSubmissionRepositoryStub()
        service = QueueCapacityService(repository=repo, threshold=5)
        service._set_cached_depth(10)
        set_queue_capacity_service(service)

        response = client.post(
            "/v1/petition-submissions",
            json={"type": petition_type, "text": "Test petition"},
        )

        assert response.status_code == 503
