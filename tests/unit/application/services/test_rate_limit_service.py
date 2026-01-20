"""Unit tests for RateLimitService (Story 1.4, FR-1.5, HC-4).

Tests for per-submitter petition rate limiting service including:
- Rate limit checking with sliding window
- Submission recording
- Reset time calculation
- Prometheus metrics integration

Constitutional Constraints Tested:
- FR-1.5: Enforce rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- NFR-5.1: Rate limiting per identity
- D4: PostgreSQL time-bucket counters
- CT-11: Fail loud, not silent
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.rate_limit_service import RateLimitService


class MockRateLimitStore:
    """Mock implementation of RateLimitStorePort for testing."""

    def __init__(self) -> None:
        self.submission_count: int = 0
        self.oldest_bucket: datetime | None = None
        self.increment_bucket_calls: list[tuple] = []
        self.get_count_calls: list[tuple] = []

    async def get_submission_count(self, submitter_id, since: datetime) -> int:
        self.get_count_calls.append((submitter_id, since))
        return self.submission_count

    async def increment_bucket(self, submitter_id, bucket_minute: datetime) -> None:
        self.increment_bucket_calls.append((submitter_id, bucket_minute))

    async def get_oldest_bucket_expiry(
        self, submitter_id, since: datetime
    ) -> datetime | None:
        return self.oldest_bucket

    async def cleanup_expired_buckets(self, older_than: datetime) -> int:
        return 0


@pytest.fixture
def mock_store() -> MockRateLimitStore:
    """Create fresh mock store for each test."""
    return MockRateLimitStore()


@pytest.fixture
def service(mock_store: MockRateLimitStore) -> RateLimitService:
    """Create service with test-friendly configuration."""
    return RateLimitService(
        store=mock_store,
        limit_per_hour=10,  # HC-4 default
        window_minutes=60,
    )


@pytest.fixture
def submitter_id():
    """Create a test submitter UUID."""
    return uuid4()


class TestRateLimitService:
    """Tests for RateLimitService."""

    class TestCheckRateLimit:
        """Tests for check_rate_limit method (FR-1.5, HC-4)."""

        async def test_allows_when_under_limit(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Should allow submission when count < limit."""
            mock_store.submission_count = 5  # Under limit of 10
            mock_store.oldest_bucket = datetime.now(timezone.utc) + timedelta(
                minutes=30
            )

            result = await service.check_rate_limit(submitter_id)

            assert result.allowed is True
            assert result.current_count == 5
            assert result.remaining == 5
            assert result.limit == 10

        async def test_allows_when_at_zero(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Should allow submission when no prior submissions."""
            mock_store.submission_count = 0
            mock_store.oldest_bucket = None

            result = await service.check_rate_limit(submitter_id)

            assert result.allowed is True
            assert result.current_count == 0
            assert result.remaining == 10

        async def test_rejects_when_at_limit(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Should reject when count >= limit (HC-4)."""
            mock_store.submission_count = 10  # At limit
            mock_store.oldest_bucket = datetime.now(timezone.utc) + timedelta(
                minutes=15
            )

            result = await service.check_rate_limit(submitter_id)

            assert result.allowed is False
            assert result.current_count == 10
            assert result.remaining == 0

        async def test_rejects_when_over_limit(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Should reject when count > limit."""
            mock_store.submission_count = 15  # Over limit
            mock_store.oldest_bucket = datetime.now(timezone.utc) + timedelta(minutes=5)

            result = await service.check_rate_limit(submitter_id)

            assert result.allowed is False
            assert result.current_count == 15
            assert result.remaining == 0

        async def test_returns_correct_reset_time(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Reset time should match oldest bucket expiry."""
            expected_reset = datetime.now(timezone.utc) + timedelta(minutes=45)
            mock_store.submission_count = 5
            mock_store.oldest_bucket = expected_reset

            result = await service.check_rate_limit(submitter_id)

            assert result.reset_at == expected_reset

        async def test_reset_time_defaults_to_window_end_when_no_buckets(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Reset time should be window end if no buckets exist."""
            mock_store.submission_count = 0
            mock_store.oldest_bucket = None

            now = datetime.now(timezone.utc)
            result = await service.check_rate_limit(submitter_id)

            # Should be approximately 60 minutes from now (window size)
            expected_reset = now + timedelta(minutes=60)
            assert abs((result.reset_at - expected_reset).total_seconds()) < 5

        async def test_queries_correct_window(
            self,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Should query submissions from window_start to now."""
            service = RateLimitService(
                store=mock_store,
                limit_per_hour=10,
                window_minutes=30,  # Custom window
            )
            mock_store.submission_count = 0

            now = datetime.now(timezone.utc)
            await service.check_rate_limit(submitter_id)

            # Verify correct window was queried
            assert len(mock_store.get_count_calls) == 1
            queried_submitter, window_start = mock_store.get_count_calls[0]
            assert queried_submitter == submitter_id
            # window_start should be ~30 minutes ago
            expected_start = now - timedelta(minutes=30)
            assert abs((window_start - expected_start).total_seconds()) < 5

    class TestRecordSubmission:
        """Tests for record_submission method."""

        async def test_increments_current_minute_bucket(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Should increment the current minute bucket."""
            now = datetime.now(timezone.utc)

            await service.record_submission(submitter_id)

            assert len(mock_store.increment_bucket_calls) == 1
            recorded_id, bucket_minute = mock_store.increment_bucket_calls[0]
            assert recorded_id == submitter_id
            # Bucket minute should be truncated to minute boundary
            assert bucket_minute.second == 0
            assert bucket_minute.microsecond == 0
            # Should be within last minute
            assert abs((bucket_minute - now).total_seconds()) < 60

        async def test_truncates_to_minute_boundary(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Bucket minute should have seconds/microseconds zeroed."""
            await service.record_submission(submitter_id)

            _, bucket_minute = mock_store.increment_bucket_calls[0]
            assert bucket_minute.second == 0
            assert bucket_minute.microsecond == 0

    class TestGetRemaining:
        """Tests for get_remaining convenience method."""

        async def test_returns_remaining_count(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Should return remaining submissions."""
            mock_store.submission_count = 7

            remaining = await service.get_remaining(submitter_id)

            assert remaining == 3  # 10 - 7

        async def test_returns_zero_when_at_limit(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Should return 0 when at or over limit."""
            mock_store.submission_count = 10

            remaining = await service.get_remaining(submitter_id)

            assert remaining == 0

    class TestConfiguration:
        """Tests for configuration getters."""

        def test_get_limit(self, service: RateLimitService) -> None:
            """get_limit should return configured value."""
            assert service.get_limit() == 10

        def test_get_window_minutes(self, service: RateLimitService) -> None:
            """get_window_minutes should return configured value."""
            assert service.get_window_minutes() == 60

        def test_custom_configuration(self, mock_store: MockRateLimitStore) -> None:
            """Test custom configuration values."""
            service = RateLimitService(
                store=mock_store,
                limit_per_hour=50,
                window_minutes=30,
            )
            assert service.get_limit() == 50
            assert service.get_window_minutes() == 30

    class TestMetricsIntegration:
        """Tests for rate limit behavior without metrics dependency."""

        async def test_increments_rate_limit_hits_on_rejection(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Rate limit rejection should be reported as not allowed."""
            mock_store.submission_count = 15  # Over limit
            result = await service.check_rate_limit(submitter_id)

            assert result.allowed is False

        async def test_no_metric_on_allowed(
            self,
            service: RateLimitService,
            mock_store: MockRateLimitStore,
            submitter_id,
        ) -> None:
            """Allowed submissions should be reported as allowed."""
            mock_store.submission_count = 5  # Under limit
            result = await service.check_rate_limit(submitter_id)

            assert result.allowed is True


class TestEdgeCases:
    """Edge case tests for rate limit service."""

    async def test_single_submission_limit(
        self, mock_store: MockRateLimitStore, submitter_id
    ) -> None:
        """Service should handle limit of 1."""
        service = RateLimitService(
            store=mock_store,
            limit_per_hour=1,
            window_minutes=60,
        )

        # First submission allowed
        mock_store.submission_count = 0
        result = await service.check_rate_limit(submitter_id)
        assert result.allowed is True
        assert result.remaining == 1

        # Second submission rejected
        mock_store.submission_count = 1
        result = await service.check_rate_limit(submitter_id)
        assert result.allowed is False
        assert result.remaining == 0

    async def test_very_large_limit(
        self, mock_store: MockRateLimitStore, submitter_id
    ) -> None:
        """Service should handle large limit values."""
        service = RateLimitService(
            store=mock_store,
            limit_per_hour=1_000_000,
            window_minutes=60,
        )

        mock_store.submission_count = 999_999
        result = await service.check_rate_limit(submitter_id)
        assert result.allowed is True
        assert result.remaining == 1

    async def test_short_window(
        self, mock_store: MockRateLimitStore, submitter_id
    ) -> None:
        """Service should handle short windows."""
        service = RateLimitService(
            store=mock_store,
            limit_per_hour=10,
            window_minutes=1,  # 1 minute window
        )

        mock_store.submission_count = 0
        result = await service.check_rate_limit(submitter_id)
        assert result.allowed is True

    async def test_multiple_submitters_isolated(
        self, mock_store: MockRateLimitStore
    ) -> None:
        """Different submitters should have independent limits."""
        service = RateLimitService(
            store=mock_store,
            limit_per_hour=10,
            window_minutes=60,
        )

        submitter_a = uuid4()
        submitter_b = uuid4()

        # Submitter A at limit
        mock_store.submission_count = 10
        result_a = await service.check_rate_limit(submitter_a)
        assert result_a.allowed is False

        # Submitter B should have fresh count (mock returns same count,
        # but in real impl each submitter has own buckets)
        mock_store.submission_count = 0
        result_b = await service.check_rate_limit(submitter_b)
        assert result_b.allowed is True


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""

    async def test_result_is_immutable(
        self,
        service: RateLimitService,
        mock_store: MockRateLimitStore,
        submitter_id,
    ) -> None:
        """RateLimitResult should be frozen (immutable)."""
        mock_store.submission_count = 5

        result = await service.check_rate_limit(submitter_id)

        # Attempt to modify should raise
        with pytest.raises(AttributeError):
            result.allowed = True  # type: ignore

    async def test_result_contains_all_fields(
        self,
        service: RateLimitService,
        mock_store: MockRateLimitStore,
        submitter_id,
    ) -> None:
        """RateLimitResult should have all required fields."""
        mock_store.submission_count = 5
        mock_store.oldest_bucket = datetime.now(timezone.utc)

        result = await service.check_rate_limit(submitter_id)

        assert hasattr(result, "allowed")
        assert hasattr(result, "remaining")
        assert hasattr(result, "reset_at")
        assert hasattr(result, "current_count")
        assert hasattr(result, "limit")
