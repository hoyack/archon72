"""Unit tests for OverrideTrendRepositoryStub (Story 5.5, FR27, RT-3).

Tests the stub implementation for proper protocol compliance and behavior.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.override_trend_repository import (
    OverrideTrendData,
    OverrideTrendRepositoryProtocol,
)
from src.infrastructure.stubs.override_trend_repository_stub import (
    OverrideTrendRepositoryStub,
)


class TestProtocolCompliance:
    """Verify stub implements protocol correctly."""

    def test_stub_has_protocol_methods(self) -> None:
        """Test stub has all methods defined by the protocol."""
        stub = OverrideTrendRepositoryStub()
        # Protocol defines these methods - verify they exist
        assert hasattr(stub, "get_override_count")
        assert hasattr(stub, "get_override_count_for_period")
        assert hasattr(stub, "get_rolling_trend")

    def test_stub_methods_are_callable(self) -> None:
        """Test stub methods are callable (async)."""
        stub = OverrideTrendRepositoryStub()
        assert callable(stub.get_override_count)
        assert callable(stub.get_override_count_for_period)
        assert callable(stub.get_rolling_trend)


class TestSetOverrideHistory:
    """Tests for set_override_history method."""

    def test_set_override_history_stores_data(self) -> None:
        """Test set_override_history stores the provided history."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        history = [now - timedelta(days=i) for i in range(5)]

        stub.set_override_history(history)

        # Internal state should be sorted newest first
        assert len(stub._override_history) == 5

    def test_set_override_history_sorts_newest_first(self) -> None:
        """Test history is sorted with newest first."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        # Provide in oldest-first order
        history = [now - timedelta(days=10), now - timedelta(days=5), now]

        stub.set_override_history(history)

        # Should be sorted newest first
        assert stub._override_history[0] == now
        assert stub._override_history[-1] == now - timedelta(days=10)

    def test_set_override_history_replaces_existing(self) -> None:
        """Test set_override_history replaces existing history."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)

        stub.set_override_history([now - timedelta(days=1)])
        assert len(stub._override_history) == 1

        stub.set_override_history([now, now - timedelta(days=2)])
        assert len(stub._override_history) == 2


class TestAddOverride:
    """Tests for add_override method."""

    def test_add_override_with_default_timestamp(self) -> None:
        """Test add_override uses current time by default."""
        stub = OverrideTrendRepositoryStub()
        before = datetime.now(timezone.utc)

        stub.add_override()

        after = datetime.now(timezone.utc)
        assert len(stub._override_history) == 1
        assert before <= stub._override_history[0] <= after

    def test_add_override_with_specific_timestamp(self) -> None:
        """Test add_override with specific timestamp."""
        stub = OverrideTrendRepositoryStub()
        specific_time = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

        stub.add_override(timestamp=specific_time)

        assert stub._override_history[0] == specific_time

    def test_add_override_maintains_sort_order(self) -> None:
        """Test add_override maintains newest-first sort order."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)

        stub.add_override(timestamp=now - timedelta(days=5))
        stub.add_override(timestamp=now)
        stub.add_override(timestamp=now - timedelta(days=10))

        assert stub._override_history[0] == now
        assert stub._override_history[-1] == now - timedelta(days=10)


class TestClearHistory:
    """Tests for clear_history method."""

    def test_clear_history_removes_all(self) -> None:
        """Test clear_history removes all entries."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        stub.set_override_history([now - timedelta(days=i) for i in range(10)])

        stub.clear_history()

        assert len(stub._override_history) == 0


class TestGetOverrideCount:
    """Tests for get_override_count method."""

    @pytest.mark.asyncio
    async def test_get_override_count_empty_history(self) -> None:
        """Test get_override_count returns 0 with empty history."""
        stub = OverrideTrendRepositoryStub()

        count = await stub.get_override_count(days=30)

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_override_count_all_in_window(self) -> None:
        """Test get_override_count when all overrides are in window."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        history = [now - timedelta(days=i) for i in range(10)]
        stub.set_override_history(history)

        count = await stub.get_override_count(days=30)

        assert count == 10

    @pytest.mark.asyncio
    async def test_get_override_count_partial_in_window(self) -> None:
        """Test get_override_count filters by window correctly."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        # 5 in last 30 days, 5 outside
        history = [
            now - timedelta(days=5),
            now - timedelta(days=10),
            now - timedelta(days=15),
            now - timedelta(days=20),
            now - timedelta(days=25),
            now - timedelta(days=40),  # Outside 30-day window
            now - timedelta(days=50),
            now - timedelta(days=60),
            now - timedelta(days=70),
            now - timedelta(days=80),
        ]
        stub.set_override_history(history)

        count = await stub.get_override_count(days=30)

        assert count == 5


class TestGetOverrideCountForPeriod:
    """Tests for get_override_count_for_period method."""

    @pytest.mark.asyncio
    async def test_get_override_count_for_period_empty(self) -> None:
        """Test get_override_count_for_period with empty history."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)

        count = await stub.get_override_count_for_period(
            start_date=now - timedelta(days=30),
            end_date=now,
        )

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_override_count_for_period_filters_correctly(self) -> None:
        """Test get_override_count_for_period filters by date range."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        history = [
            now - timedelta(days=5),   # In range
            now - timedelta(days=15),  # In range
            now - timedelta(days=25),  # In range
            now - timedelta(days=35),  # Outside range
            now - timedelta(days=45),  # Outside range
        ]
        stub.set_override_history(history)

        count = await stub.get_override_count_for_period(
            start_date=now - timedelta(days=30),
            end_date=now,
        )

        assert count == 3

    @pytest.mark.asyncio
    async def test_get_override_count_for_period_inclusive_boundaries(self) -> None:
        """Test boundaries are inclusive."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        exact_start = now - timedelta(days=30)
        exact_end = now

        stub.set_override_history([exact_start, exact_end])

        count = await stub.get_override_count_for_period(
            start_date=exact_start,
            end_date=exact_end,
        )

        assert count == 2


class TestGetRollingTrend:
    """Tests for get_rolling_trend method."""

    @pytest.mark.asyncio
    async def test_get_rolling_trend_empty_history(self) -> None:
        """Test get_rolling_trend with empty history."""
        stub = OverrideTrendRepositoryStub()

        trend = await stub.get_rolling_trend(days=90)

        assert isinstance(trend, OverrideTrendData)
        assert trend.total_count == 0
        assert trend.daily_rate == 0.0
        assert trend.period_days == 90
        assert trend.oldest_override is None
        assert trend.newest_override is None

    @pytest.mark.asyncio
    async def test_get_rolling_trend_with_data(self) -> None:
        """Test get_rolling_trend calculates correctly."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        history = [now - timedelta(days=i * 10) for i in range(5)]
        stub.set_override_history(history)

        trend = await stub.get_rolling_trend(days=90)

        assert trend.total_count == 5
        assert trend.period_days == 90
        assert trend.daily_rate == pytest.approx(5 / 90, rel=0.01)
        assert trend.oldest_override == now - timedelta(days=40)
        assert trend.newest_override == now

    @pytest.mark.asyncio
    async def test_get_rolling_trend_respects_window(self) -> None:
        """Test get_rolling_trend only includes events in window."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        history = [
            now - timedelta(days=10),
            now - timedelta(days=30),
            now - timedelta(days=50),
            now - timedelta(days=100),  # Outside 90-day window
            now - timedelta(days=200),  # Outside 90-day window
        ]
        stub.set_override_history(history)

        trend = await stub.get_rolling_trend(days=90)

        assert trend.total_count == 3
        assert trend.oldest_override == now - timedelta(days=50)
        assert trend.newest_override == now - timedelta(days=10)
