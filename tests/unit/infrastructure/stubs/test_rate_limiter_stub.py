"""Unit tests for RateLimiterStub (Story 1.4, FR-1.5, HC-4).

Tests for the configurable rate limiter stub used in testing.

Constitutional Constraints Tested:
- FR-1.5: Enforce rate limits per submitter_id
- HC-4: 10 petitions/user/hour (configurable)
- CT-11: Fail loud, not silent
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.infrastructure.stubs.rate_limiter_stub import RateLimiterStub


@pytest.fixture
def stub() -> RateLimiterStub:
    """Create fresh stub for each test."""
    return RateLimiterStub()


@pytest.fixture
def submitter_id():
    """Create a test submitter UUID."""
    return uuid4()


class TestRateLimiterStub:
    """Tests for RateLimiterStub."""

    class TestCheckRateLimit:
        """Tests for check_rate_limit method."""

        async def test_allows_first_submission(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """First submission should always be allowed."""
            result = await stub.check_rate_limit(submitter_id)

            assert result.allowed is True
            assert result.current_count == 0
            assert result.remaining == 10
            assert result.limit == 10

        async def test_allows_when_under_limit(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """Should allow when count < limit."""
            stub.set_count(submitter_id, 5)

            result = await stub.check_rate_limit(submitter_id)

            assert result.allowed is True
            assert result.remaining == 5

        async def test_rejects_when_at_limit(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """Should reject when count >= limit."""
            stub.set_count(submitter_id, 10)

            result = await stub.check_rate_limit(submitter_id)

            assert result.allowed is False
            assert result.remaining == 0

        async def test_returns_configured_reset_time(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """Should return the configured reset time."""
            expected_reset = datetime.now(timezone.utc) + timedelta(hours=1)
            stub.set_reset_at(submitter_id, expected_reset)

            result = await stub.check_rate_limit(submitter_id)

            assert result.reset_at == expected_reset

        async def test_default_reset_time_is_window_end(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """Default reset time should be window_minutes from now."""
            now = datetime.now(timezone.utc)

            result = await stub.check_rate_limit(submitter_id)

            # Should be ~60 minutes from now (default window)
            expected = now + timedelta(minutes=60)
            assert abs((result.reset_at - expected).total_seconds()) < 5

    class TestRecordSubmission:
        """Tests for record_submission method."""

        async def test_increments_count(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """Recording should increment the count."""
            assert stub.get_count(submitter_id) == 0

            await stub.record_submission(submitter_id)
            assert stub.get_count(submitter_id) == 1

            await stub.record_submission(submitter_id)
            assert stub.get_count(submitter_id) == 2

        async def test_sets_reset_time_on_first_submission(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """First submission should set reset time."""
            now = datetime.now(timezone.utc)

            await stub.record_submission(submitter_id)

            result = await stub.check_rate_limit(submitter_id)
            # Should be ~60 minutes from now
            expected = now + timedelta(minutes=60)
            assert abs((result.reset_at - expected).total_seconds()) < 5

        async def test_tracks_submitters_independently(
            self, stub: RateLimiterStub
        ) -> None:
            """Different submitters should have independent counts."""
            submitter_a = uuid4()
            submitter_b = uuid4()

            await stub.record_submission(submitter_a)
            await stub.record_submission(submitter_a)
            await stub.record_submission(submitter_b)

            assert stub.get_count(submitter_a) == 2
            assert stub.get_count(submitter_b) == 1

    class TestGetRemaining:
        """Tests for get_remaining method."""

        async def test_returns_limit_minus_count(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """Should return limit - current_count."""
            stub.set_count(submitter_id, 7)

            remaining = await stub.get_remaining(submitter_id)

            assert remaining == 3  # 10 - 7

        async def test_returns_zero_when_over_limit(
            self, stub: RateLimiterStub, submitter_id
        ) -> None:
            """Should return 0 when over limit."""
            stub.set_count(submitter_id, 15)

            remaining = await stub.get_remaining(submitter_id)

            assert remaining == 0

    class TestConfiguration:
        """Tests for configuration methods."""

        def test_default_limit(self, stub: RateLimiterStub) -> None:
            """Default limit should be 10 (HC-4)."""
            assert stub.get_limit() == 10

        def test_default_window(self, stub: RateLimiterStub) -> None:
            """Default window should be 60 minutes."""
            assert stub.get_window_minutes() == 60

        def test_custom_configuration(self) -> None:
            """Should accept custom configuration."""
            stub = RateLimiterStub(limit=50, window_minutes=30)

            assert stub.get_limit() == 50
            assert stub.get_window_minutes() == 30

    class TestTestHelpers:
        """Tests for test helper methods."""

        def test_set_count(self, stub: RateLimiterStub, submitter_id) -> None:
            """set_count should update the count."""
            stub.set_count(submitter_id, 42)
            assert stub.get_count(submitter_id) == 42

        def test_set_limit(self, stub: RateLimiterStub) -> None:
            """set_limit should update the limit."""
            stub.set_limit(25)
            assert stub.get_limit() == 25

        def test_set_reset_at(self, stub: RateLimiterStub, submitter_id) -> None:
            """set_reset_at should update reset time."""
            expected = datetime.now(timezone.utc) + timedelta(hours=2)
            stub.set_reset_at(submitter_id, expected)

            # Need to set count to populate the submitter
            stub.set_count(submitter_id, 1)
            result = stub._reset_at.get(submitter_id)
            assert result == expected

        def test_reset(self, stub: RateLimiterStub) -> None:
            """reset should clear all state."""
            submitter_a = uuid4()
            submitter_b = uuid4()
            stub.set_count(submitter_a, 5)
            stub.set_count(submitter_b, 10)

            stub.reset()

            assert stub.get_count(submitter_a) == 0
            assert stub.get_count(submitter_b) == 0

        def test_reset_submitter(self, stub: RateLimiterStub) -> None:
            """reset_submitter should clear only that submitter."""
            submitter_a = uuid4()
            submitter_b = uuid4()
            stub.set_count(submitter_a, 5)
            stub.set_count(submitter_b, 10)

            stub.reset_submitter(submitter_a)

            assert stub.get_count(submitter_a) == 0
            assert stub.get_count(submitter_b) == 10

    class TestFactoryMethods:
        """Tests for factory methods."""

        def test_allowing_factory(self) -> None:
            """allowing() should create stub that allows submissions."""
            stub = RateLimiterStub.allowing(limit=20)

            assert stub.get_limit() == 20
            # No counts set, so all submitters allowed

        async def test_at_limit_factory(self, submitter_id) -> None:
            """at_limit() should create stub at limit for submitter."""
            stub = RateLimiterStub.at_limit(
                submitter_id=submitter_id,
                limit=5,
                reset_in_seconds=3600,
            )

            result = await stub.check_rate_limit(submitter_id)

            assert result.allowed is False
            assert result.current_count == 5
            assert result.limit == 5

        async def test_over_limit_factory(self, submitter_id) -> None:
            """over_limit() should create stub over limit for submitter."""
            stub = RateLimiterStub.over_limit(
                submitter_id=submitter_id,
                limit=10,
                current_count=15,
                reset_in_seconds=1800,
            )

            result = await stub.check_rate_limit(submitter_id)

            assert result.allowed is False
            assert result.current_count == 15
            assert result.remaining == 0

        async def test_at_limit_other_submitters_allowed(self) -> None:
            """at_limit submitter shouldn't affect others."""
            blocked_submitter = uuid4()
            other_submitter = uuid4()

            stub = RateLimiterStub.at_limit(
                submitter_id=blocked_submitter,
                limit=10,
            )

            # Blocked submitter rejected
            result = await stub.check_rate_limit(blocked_submitter)
            assert result.allowed is False

            # Other submitter allowed
            result = await stub.check_rate_limit(other_submitter)
            assert result.allowed is True


class TestEdgeCases:
    """Edge case tests."""

    async def test_zero_limit(self, submitter_id) -> None:
        """Zero limit should block all submissions."""
        stub = RateLimiterStub(limit=0)

        result = await stub.check_rate_limit(submitter_id)

        assert result.allowed is False
        assert result.remaining == 0

    async def test_negative_count_not_possible(
        self, stub: RateLimiterStub, submitter_id
    ) -> None:
        """Negative remaining should be capped at 0."""
        stub.set_count(submitter_id, 100)  # Way over limit

        result = await stub.check_rate_limit(submitter_id)

        assert result.remaining == 0  # Not negative

    async def test_concurrent_submitters(self, stub: RateLimiterStub) -> None:
        """Many concurrent submitters should work correctly."""
        submitters = [uuid4() for _ in range(100)]

        for i, submitter in enumerate(submitters):
            stub.set_count(submitter, i % 15)  # Varied counts

        for i, submitter in enumerate(submitters):
            result = await stub.check_rate_limit(submitter)
            expected_count = i % 15
            expected_allowed = expected_count < 10
            assert result.allowed == expected_allowed
            assert result.current_count == expected_count
