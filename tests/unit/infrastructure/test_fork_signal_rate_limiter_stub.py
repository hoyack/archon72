"""Unit tests for ForkSignalRateLimiterStub (Story 3.8, FR85).

Tests the stub implementation of ForkSignalRateLimiterPort for testing.

Constitutional Constraints:
- FR85: More than 3 fork signals per hour triggers rate limiting
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.fork_signal_rate_limiter import ForkSignalRateLimiterPort
from src.infrastructure.stubs.fork_signal_rate_limiter_stub import (
    ForkSignalRateLimiterStub,
)


class TestForkSignalRateLimiterStubCreation:
    """Tests for ForkSignalRateLimiterStub creation."""

    def test_create_stub(self) -> None:
        """Should create stub instance."""
        stub = ForkSignalRateLimiterStub()
        assert stub is not None

    def test_implements_port(self) -> None:
        """Stub should implement ForkSignalRateLimiterPort."""
        stub = ForkSignalRateLimiterStub()
        assert isinstance(stub, ForkSignalRateLimiterPort)

    def test_default_threshold(self) -> None:
        """Stub should have default threshold of 3."""
        stub = ForkSignalRateLimiterStub()
        assert stub._rate_limit_threshold == 3

    def test_default_window_hours(self) -> None:
        """Stub should have default window of 1 hour."""
        stub = ForkSignalRateLimiterStub()
        assert stub._window_hours == 1

    def test_custom_threshold(self) -> None:
        """Stub should accept custom threshold."""
        stub = ForkSignalRateLimiterStub(rate_limit_threshold=5)
        assert stub._rate_limit_threshold == 5

    def test_custom_window(self) -> None:
        """Stub should accept custom window."""
        stub = ForkSignalRateLimiterStub(window_hours=2)
        assert stub._window_hours == 2


class TestForkSignalRateLimiterStubCheckRateLimit:
    """Tests for check_rate_limit method."""

    @pytest.fixture
    def stub(self) -> ForkSignalRateLimiterStub:
        """Fixture providing a fresh stub."""
        return ForkSignalRateLimiterStub()

    @pytest.mark.asyncio
    async def test_allows_first_signal(self, stub: ForkSignalRateLimiterStub) -> None:
        """Should allow first signal from any source."""
        result = await stub.check_rate_limit("source-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_allows_up_to_threshold(
        self, stub: ForkSignalRateLimiterStub
    ) -> None:
        """Should allow signals up to threshold."""
        # Record 3 signals (threshold)
        for _ in range(3):
            await stub.record_signal("source-001")

        # Check if another is allowed (should be blocked)
        result = await stub.check_rate_limit("source-001")
        assert result is False

    @pytest.mark.asyncio
    async def test_allows_different_sources(
        self, stub: ForkSignalRateLimiterStub
    ) -> None:
        """Should track sources independently."""
        # Fill up source-001
        for _ in range(3):
            await stub.record_signal("source-001")

        # source-002 should still be allowed
        result = await stub.check_rate_limit("source-002")
        assert result is True

    @pytest.mark.asyncio
    async def test_blocks_after_threshold(
        self, stub: ForkSignalRateLimiterStub
    ) -> None:
        """Should block after threshold exceeded."""
        # Record 3 signals
        for _ in range(3):
            await stub.record_signal("source-001")

        # 4th should be blocked
        result = await stub.check_rate_limit("source-001")
        assert result is False


class TestForkSignalRateLimiterStubRecordSignal:
    """Tests for record_signal method."""

    @pytest.fixture
    def stub(self) -> ForkSignalRateLimiterStub:
        """Fixture providing a fresh stub."""
        return ForkSignalRateLimiterStub()

    @pytest.mark.asyncio
    async def test_records_signal(self, stub: ForkSignalRateLimiterStub) -> None:
        """Should record signal timestamp."""
        await stub.record_signal("source-001")
        count = await stub.get_signal_count("source-001")
        assert count == 1

    @pytest.mark.asyncio
    async def test_records_multiple_signals(
        self, stub: ForkSignalRateLimiterStub
    ) -> None:
        """Should track multiple signals."""
        await stub.record_signal("source-001")
        await stub.record_signal("source-001")
        await stub.record_signal("source-001")

        count = await stub.get_signal_count("source-001")
        assert count == 3


class TestForkSignalRateLimiterStubGetSignalCount:
    """Tests for get_signal_count method."""

    @pytest.fixture
    def stub(self) -> ForkSignalRateLimiterStub:
        """Fixture providing a fresh stub."""
        return ForkSignalRateLimiterStub()

    @pytest.mark.asyncio
    async def test_returns_zero_for_unknown_source(
        self, stub: ForkSignalRateLimiterStub
    ) -> None:
        """Should return 0 for unknown source."""
        count = await stub.get_signal_count("unknown-source")
        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_correct_count(self, stub: ForkSignalRateLimiterStub) -> None:
        """Should return correct count."""
        await stub.record_signal("source-001")
        await stub.record_signal("source-001")

        count = await stub.get_signal_count("source-001")
        assert count == 2

    @pytest.mark.asyncio
    async def test_respects_window_hours(self, stub: ForkSignalRateLimiterStub) -> None:
        """Should only count signals within window."""
        # This test uses mock time to simulate window expiry
        now = datetime.now(timezone.utc)

        # Add old signal (outside window)
        old_time = now - timedelta(hours=2)
        stub._signal_counts["source-001"] = [old_time]

        # Add new signal
        await stub.record_signal("source-001")

        # Should only count the new signal (1, not 2)
        count = await stub.get_signal_count("source-001", window_hours=1)
        assert count == 1


class TestForkSignalRateLimiterStubWindowExpiry:
    """Tests for window-based expiry."""

    @pytest.mark.asyncio
    async def test_allows_after_window_expires(self) -> None:
        """Should allow signals after window expires."""
        stub = ForkSignalRateLimiterStub()

        # Fill up the rate limit
        for _ in range(3):
            await stub.record_signal("source-001")

        # Verify blocked
        assert await stub.check_rate_limit("source-001") is False

        # Simulate time passing (add old timestamps instead)
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=2)
        stub._signal_counts["source-001"] = [old_time, old_time, old_time]

        # Should now be allowed (old signals expired)
        assert await stub.check_rate_limit("source-001") is True


class TestForkSignalRateLimiterStubTestHelpers:
    """Tests for test helper methods."""

    @pytest.mark.asyncio
    async def test_reset_clears_all_data(self) -> None:
        """reset() should clear all signal data."""
        stub = ForkSignalRateLimiterStub()
        await stub.record_signal("source-001")
        await stub.record_signal("source-002")

        stub.reset()

        count1 = await stub.get_signal_count("source-001")
        count2 = await stub.get_signal_count("source-002")
        assert count1 == 0
        assert count2 == 0

    @pytest.mark.asyncio
    async def test_set_rate_limited_simulates_limit(self) -> None:
        """set_rate_limited() should simulate rate limit state."""
        stub = ForkSignalRateLimiterStub()

        # Force rate limited state
        stub.set_rate_limited("source-001", True)

        # Should be blocked
        result = await stub.check_rate_limit("source-001")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_rate_limited(self) -> None:
        """set_rate_limited(False) should clear limit."""
        stub = ForkSignalRateLimiterStub()
        stub.set_rate_limited("source-001", True)
        stub.set_rate_limited("source-001", False)

        # Should be allowed again
        result = await stub.check_rate_limit("source-001")
        assert result is True
