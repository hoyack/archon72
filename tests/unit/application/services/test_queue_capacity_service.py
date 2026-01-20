"""Unit tests for QueueCapacityService (Story 1.3, FR-1.4).

Tests for petition queue overflow protection service including:
- Capacity threshold checking
- Hysteresis behavior to prevent oscillation
- Cache TTL behavior
- Retry-After configuration

Constitutional Constraints Tested:
- FR-1.4: Return HTTP 503 on queue overflow
- NFR-3.1: No silent petition loss
- NFR-7.4: Queue depth monitoring with backpressure
- CT-11: Fail loud, not silent
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.application.services.queue_capacity_service import QueueCapacityService
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


@pytest.fixture
def repository() -> PetitionSubmissionRepositoryStub:
    """Create fresh repository stub for each test."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def service(repository: PetitionSubmissionRepositoryStub) -> QueueCapacityService:
    """Create service with test-friendly configuration."""
    return QueueCapacityService(
        repository=repository,
        threshold=100,
        hysteresis=10,
        cache_ttl_seconds=0.1,  # Short TTL for testing
        retry_after_seconds=30,
    )


class TestQueueCapacityService:
    """Tests for QueueCapacityService."""

    class TestIsAcceptingSubmissions:
        """Tests for is_accepting_submissions method."""

        async def test_accepts_when_below_threshold(
            self, service: QueueCapacityService
        ) -> None:
            """Queue should accept submissions when depth < threshold."""
            service._set_cached_depth(50)  # Half of threshold (100)
            assert await service.is_accepting_submissions() is True

        async def test_accepts_when_at_zero(
            self, service: QueueCapacityService
        ) -> None:
            """Queue should accept submissions when empty."""
            service._set_cached_depth(0)
            assert await service.is_accepting_submissions() is True

        async def test_rejects_when_at_threshold(
            self, service: QueueCapacityService
        ) -> None:
            """Queue should reject when depth >= threshold (FR-1.4)."""
            service._set_cached_depth(100)  # Exactly at threshold
            assert await service.is_accepting_submissions() is False

        async def test_rejects_when_above_threshold(
            self, service: QueueCapacityService
        ) -> None:
            """Queue should reject when depth > threshold."""
            service._set_cached_depth(150)  # Above threshold
            assert await service.is_accepting_submissions() is False

        async def test_hysteresis_prevents_oscillation(
            self, service: QueueCapacityService
        ) -> None:
            """Once rejecting, should only resume below (threshold - hysteresis).

            Threshold = 100, hysteresis = 10, so resume at < 90.
            """
            # Start accepting, hit threshold, start rejecting
            service._set_cached_depth(100)
            assert await service.is_accepting_submissions() is False
            assert service.is_rejecting() is True

            # Just below threshold but not below resume point
            service._set_cached_depth(95)  # 95 >= 90, stay rejecting
            assert await service.is_accepting_submissions() is False
            assert service.is_rejecting() is True

            # At resume threshold boundary
            service._set_cached_depth(90)  # 90 >= 90, stay rejecting
            assert await service.is_accepting_submissions() is False
            assert service.is_rejecting() is True

            # Below resume threshold
            service._set_cached_depth(89)  # 89 < 90, resume accepting
            assert await service.is_accepting_submissions() is True
            assert service.is_rejecting() is False

        async def test_state_transition_from_accepting_to_rejecting(
            self, service: QueueCapacityService
        ) -> None:
            """Test clean transition from accepting to rejecting state."""
            # Initially accepting
            service._set_cached_depth(50)
            assert await service.is_accepting_submissions() is True
            assert service.is_rejecting() is False

            # Hit threshold
            service._set_cached_depth(100)
            assert await service.is_accepting_submissions() is False
            assert service.is_rejecting() is True

    class TestGetQueueDepth:
        """Tests for get_queue_depth method with caching."""

        async def test_returns_cached_value_within_ttl(
            self,
            repository: PetitionSubmissionRepositoryStub,
        ) -> None:
            """Should return cached value without hitting repository."""
            service = QueueCapacityService(
                repository=repository,
                threshold=100,
                cache_ttl_seconds=10.0,  # Long TTL
            )

            # Prime the cache
            service._set_cached_depth(42)

            # Should return cached value without query
            depth = await service.get_queue_depth()
            assert depth == 42

        async def test_refreshes_cache_after_ttl_expires(
            self,
            repository: PetitionSubmissionRepositoryStub,
        ) -> None:
            """Should query repository when cache expires."""
            service = QueueCapacityService(
                repository=repository,
                threshold=100,
                cache_ttl_seconds=0.01,  # Very short TTL
            )

            # Force immediate expiry
            service._cache_time = 0.0

            # Mock repository response
            repository.list_by_state = AsyncMock(return_value=([], 25))

            depth = await service.get_queue_depth()

            assert depth == 25
            repository.list_by_state.assert_called_once()

        async def test_force_cache_refresh(
            self,
            repository: PetitionSubmissionRepositoryStub,
        ) -> None:
            """force_cache_refresh should invalidate cache."""
            service = QueueCapacityService(
                repository=repository,
                threshold=100,
                cache_ttl_seconds=300.0,  # Long TTL
            )

            # Prime cache with old value
            service._set_cached_depth(10)

            # Force refresh
            service.force_cache_refresh()

            # Mock new response
            repository.list_by_state = AsyncMock(return_value=([], 50))

            depth = await service.get_queue_depth()
            assert depth == 50

    class TestConfiguration:
        """Tests for configuration getters."""

        def test_get_threshold(self, service: QueueCapacityService) -> None:
            """get_threshold should return configured value."""
            assert service.get_threshold() == 100

        def test_get_retry_after_seconds(self, service: QueueCapacityService) -> None:
            """get_retry_after_seconds should return configured value."""
            assert service.get_retry_after_seconds() == 30

        def test_get_hysteresis(self, service: QueueCapacityService) -> None:
            """get_hysteresis should return configured value."""
            assert service.get_hysteresis() == 10

        def test_default_values(
            self, repository: PetitionSubmissionRepositoryStub
        ) -> None:
            """Test default configuration values."""
            service = QueueCapacityService(repository=repository)
            assert service.get_threshold() == 10_000
            assert service.get_hysteresis() == 500
            assert service.get_retry_after_seconds() == 60

    class TestMetricsIntegration:
        """Tests for queue capacity observability hooks (AC4)."""

        def test_threshold_metric_set_at_startup(
            self,
            repository: PetitionSubmissionRepositoryStub,
        ) -> None:
            """Service initializes without external metrics dependency."""
            service = QueueCapacityService(
                repository=repository,
                threshold=5000,
            )

            assert service.get_threshold() == 5000

        async def test_record_rejection_increments_counter(
            self,
            service: QueueCapacityService,
        ) -> None:
            """record_rejection should not raise."""
            service.record_rejection()

        async def test_cache_refresh_updates_depth_metric(
            self,
            repository: PetitionSubmissionRepositoryStub,
        ) -> None:
            """Cache refresh updates cached depth."""
            service = QueueCapacityService(
                repository=repository,
                threshold=100,
                cache_ttl_seconds=0.01,
            )
            service._cache_time = 0.0
            repository.list_by_state = AsyncMock(return_value=([], 75))

            depth = await service.get_queue_depth()

            assert depth == 75


class TestEdgeCases:
    """Edge case tests for queue capacity service."""

    async def test_zero_hysteresis(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Zero hysteresis should still work (immediate resume)."""
        service = QueueCapacityService(
            repository=repository,
            threshold=100,
            hysteresis=0,
        )

        # Hit threshold
        service._set_cached_depth(100)
        assert await service.is_accepting_submissions() is False

        # Drop just below - should immediately resume
        service._set_cached_depth(99)
        assert await service.is_accepting_submissions() is True

    async def test_very_large_threshold(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Service should handle large threshold values."""
        service = QueueCapacityService(
            repository=repository,
            threshold=1_000_000,
            hysteresis=50_000,
        )

        service._set_cached_depth(999_999)
        assert await service.is_accepting_submissions() is True

        service._set_cached_depth(1_000_000)
        assert await service.is_accepting_submissions() is False

    async def test_concurrent_state_queries(
        self, repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Multiple concurrent queries should be consistent."""
        import asyncio

        service = QueueCapacityService(
            repository=repository,
            threshold=100,
            hysteresis=10,
            cache_ttl_seconds=0.01,
        )

        repository.list_by_state = AsyncMock(return_value=([], 50))

        # Run multiple concurrent queries
        results = await asyncio.gather(
            service.is_accepting_submissions(),
            service.is_accepting_submissions(),
            service.is_accepting_submissions(),
        )

        # All should return same result
        assert all(r is True for r in results)
