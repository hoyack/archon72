"""Unit tests for CoSignRateLimiterStub (Story 5.4, FR-6.6, SYBIL-1).

Tests for the configurable co-sign rate limiter stub used in testing.

Constitutional Constraints Tested:
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- NFR-5.1: Rate limiting per identity: Configurable per type
- SYBIL-1: Identity verification + rate limiting per verified identity
- CT-11: Fail loud, not silent
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.infrastructure.stubs.co_sign_rate_limiter_stub import CoSignRateLimiterStub


@pytest.fixture
def stub() -> CoSignRateLimiterStub:
    """Create fresh stub for each test."""
    return CoSignRateLimiterStub()


@pytest.fixture
def signer_id():
    """Create a test signer UUID."""
    return uuid4()


class TestCoSignRateLimiterStub:
    """Tests for CoSignRateLimiterStub."""

    class TestCheckRateLimit:
        """Tests for check_rate_limit method (AC1, AC2)."""

        async def test_allows_first_co_sign(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """First co-sign should always be allowed."""
            result = await stub.check_rate_limit(signer_id)

            assert result.allowed is True
            assert result.current_count == 0
            assert result.remaining == 50  # Default limit
            assert result.limit == 50

        async def test_allows_when_under_limit(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """Should allow when count < limit."""
            stub.set_count(signer_id, 25)

            result = await stub.check_rate_limit(signer_id)

            assert result.allowed is True
            assert result.remaining == 25

        async def test_rejects_when_at_limit(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """Should reject when count >= limit (AC1)."""
            stub.set_count(signer_id, 50)

            result = await stub.check_rate_limit(signer_id)

            assert result.allowed is False
            assert result.remaining == 0

        async def test_rejects_when_over_limit(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """Should reject when count > limit."""
            stub.set_count(signer_id, 55)

            result = await stub.check_rate_limit(signer_id)

            assert result.allowed is False
            assert result.remaining == 0

        async def test_returns_configured_reset_time(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """Should return the configured reset time."""
            expected_reset = datetime.now(timezone.utc) + timedelta(hours=1)
            stub.set_reset_at(signer_id, expected_reset)

            result = await stub.check_rate_limit(signer_id)

            assert result.reset_at == expected_reset

        async def test_default_reset_time_is_window_end(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """Default reset time should be window_minutes from now."""
            now = datetime.now(timezone.utc)

            result = await stub.check_rate_limit(signer_id)

            # Should be ~60 minutes from now (default window)
            expected = now + timedelta(minutes=60)
            assert abs((result.reset_at - expected).total_seconds()) < 5

    class TestRecordCoSign:
        """Tests for record_co_sign method (AC4)."""

        async def test_increments_count(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """Recording should increment the count (AC4)."""
            assert stub.get_count(signer_id) == 0

            await stub.record_co_sign(signer_id)
            assert stub.get_count(signer_id) == 1

            await stub.record_co_sign(signer_id)
            assert stub.get_count(signer_id) == 2

        async def test_sets_reset_time_on_first_co_sign(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """First co-sign should set reset time."""
            now = datetime.now(timezone.utc)

            await stub.record_co_sign(signer_id)

            result = await stub.check_rate_limit(signer_id)
            # Should be ~60 minutes from now
            expected = now + timedelta(minutes=60)
            assert abs((result.reset_at - expected).total_seconds()) < 5

        async def test_tracks_signers_independently(
            self, stub: CoSignRateLimiterStub
        ) -> None:
            """Different signers should have independent counts."""
            signer_a = uuid4()
            signer_b = uuid4()

            await stub.record_co_sign(signer_a)
            await stub.record_co_sign(signer_a)
            await stub.record_co_sign(signer_b)

            assert stub.get_count(signer_a) == 2
            assert stub.get_count(signer_b) == 1

    class TestGetRemaining:
        """Tests for get_remaining method."""

        async def test_returns_limit_minus_count(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """Should return limit - current_count."""
            stub.set_count(signer_id, 35)

            remaining = await stub.get_remaining(signer_id)

            assert remaining == 15  # 50 - 35

        async def test_returns_zero_when_over_limit(
            self, stub: CoSignRateLimiterStub, signer_id
        ) -> None:
            """Should return 0 when over limit."""
            stub.set_count(signer_id, 75)

            remaining = await stub.get_remaining(signer_id)

            assert remaining == 0

    class TestConfiguration:
        """Tests for configuration methods (AC7)."""

        def test_default_limit(self, stub: CoSignRateLimiterStub) -> None:
            """Default limit should be 50 (FR-6.6)."""
            assert stub.get_limit() == 50

        def test_default_window(self, stub: CoSignRateLimiterStub) -> None:
            """Default window should be 60 minutes."""
            assert stub.get_window_minutes() == 60

        def test_custom_configuration(self) -> None:
            """Should accept custom configuration (AC7)."""
            stub = CoSignRateLimiterStub(limit=100, window_minutes=30)

            assert stub.get_limit() == 100
            assert stub.get_window_minutes() == 30

    class TestTestHelpers:
        """Tests for test helper methods."""

        def test_set_count(self, stub: CoSignRateLimiterStub, signer_id) -> None:
            """set_count should update the count."""
            stub.set_count(signer_id, 42)
            assert stub.get_count(signer_id) == 42

        def test_set_limit(self, stub: CoSignRateLimiterStub) -> None:
            """set_limit should update the limit."""
            stub.set_limit(75)
            assert stub.get_limit() == 75

        def test_set_reset_at(self, stub: CoSignRateLimiterStub, signer_id) -> None:
            """set_reset_at should update reset time."""
            expected = datetime.now(timezone.utc) + timedelta(hours=2)
            stub.set_reset_at(signer_id, expected)

            # Need to check rate limit to get reset_at
            stub.set_count(signer_id, 1)
            result = stub._reset_at.get(signer_id)
            assert result == expected

        def test_reset(self, stub: CoSignRateLimiterStub) -> None:
            """reset should clear all state."""
            signer_a = uuid4()
            signer_b = uuid4()
            stub.set_count(signer_a, 5)
            stub.set_count(signer_b, 10)

            stub.reset()

            assert stub.get_count(signer_a) == 0
            assert stub.get_count(signer_b) == 0

        def test_reset_signer(self, stub: CoSignRateLimiterStub) -> None:
            """reset_signer should clear only that signer."""
            signer_a = uuid4()
            signer_b = uuid4()
            stub.set_count(signer_a, 5)
            stub.set_count(signer_b, 10)

            stub.reset_signer(signer_a)

            assert stub.get_count(signer_a) == 0
            assert stub.get_count(signer_b) == 10

    class TestFactoryMethods:
        """Tests for factory methods."""

        def test_allowing_factory(self) -> None:
            """allowing() should create stub that allows co-signs."""
            stub = CoSignRateLimiterStub.allowing(limit=100)

            assert stub.get_limit() == 100
            # No counts set, so all signers allowed

        async def test_at_limit_factory(self, signer_id) -> None:
            """at_limit() should create stub at limit for signer."""
            stub = CoSignRateLimiterStub.at_limit(
                signer_id=signer_id,
                limit=50,
                reset_in_seconds=3600,
            )

            result = await stub.check_rate_limit(signer_id)

            assert result.allowed is False
            assert result.current_count == 50
            assert result.limit == 50

        async def test_over_limit_factory(self, signer_id) -> None:
            """over_limit() should create stub over limit for signer."""
            stub = CoSignRateLimiterStub.over_limit(
                signer_id=signer_id,
                limit=50,
                current_count=55,
                reset_in_seconds=1800,
            )

            result = await stub.check_rate_limit(signer_id)

            assert result.allowed is False
            assert result.current_count == 55
            assert result.remaining == 0

        async def test_at_limit_other_signers_allowed(self) -> None:
            """at_limit signer shouldn't affect others."""
            blocked_signer = uuid4()
            other_signer = uuid4()

            stub = CoSignRateLimiterStub.at_limit(
                signer_id=blocked_signer,
                limit=50,
            )

            # Blocked signer rejected
            result = await stub.check_rate_limit(blocked_signer)
            assert result.allowed is False

            # Other signer allowed
            result = await stub.check_rate_limit(other_signer)
            assert result.allowed is True


class TestEdgeCases:
    """Edge case tests."""

    async def test_zero_limit(self, signer_id) -> None:
        """Zero limit should block all co-signs."""
        stub = CoSignRateLimiterStub(limit=0)

        result = await stub.check_rate_limit(signer_id)

        assert result.allowed is False
        assert result.remaining == 0

    async def test_negative_count_not_possible(
        self, stub: CoSignRateLimiterStub, signer_id
    ) -> None:
        """Negative remaining should be capped at 0."""
        stub.set_count(signer_id, 100)  # Way over limit

        result = await stub.check_rate_limit(signer_id)

        assert result.remaining == 0  # Not negative

    async def test_concurrent_signers(self, stub: CoSignRateLimiterStub) -> None:
        """Many concurrent signers should work correctly."""
        signers = [uuid4() for _ in range(100)]

        for i, signer in enumerate(signers):
            stub.set_count(signer, i % 60)  # Varied counts

        for i, signer in enumerate(signers):
            result = await stub.check_rate_limit(signer)
            expected_count = i % 60
            expected_allowed = expected_count < 50
            assert result.allowed == expected_allowed
            assert result.current_count == expected_count
