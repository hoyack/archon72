"""Unit tests for OverrideTrendRepositoryProtocol (Story 5.5, FR27, RT-3)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.override_trend_repository import (
    OverrideTrendData,
    OverrideTrendRepositoryProtocol,
)
from src.infrastructure.stubs.override_trend_repository_stub import (
    OverrideTrendRepositoryStub,
)


class TestOverrideTrendData:
    """Tests for OverrideTrendData dataclass."""

    def test_trend_data_creation(self) -> None:
        """Test OverrideTrendData can be created with all fields."""
        now = datetime.now(timezone.utc)
        oldest = now - timedelta(days=30)
        trend_data = OverrideTrendData(
            total_count=10,
            daily_rate=0.33,
            period_days=30,
            oldest_override=oldest,
            newest_override=now,
        )

        assert trend_data.total_count == 10
        assert trend_data.daily_rate == 0.33
        assert trend_data.period_days == 30
        assert trend_data.oldest_override == oldest
        assert trend_data.newest_override == now

    def test_trend_data_with_no_overrides(self) -> None:
        """Test OverrideTrendData with no overrides."""
        trend_data = OverrideTrendData(
            total_count=0,
            daily_rate=0.0,
            period_days=90,
            oldest_override=None,
            newest_override=None,
        )

        assert trend_data.total_count == 0
        assert trend_data.daily_rate == 0.0
        assert trend_data.oldest_override is None
        assert trend_data.newest_override is None

    def test_trend_data_is_frozen(self) -> None:
        """Test OverrideTrendData is immutable."""
        trend_data = OverrideTrendData(
            total_count=10,
            daily_rate=0.33,
            period_days=30,
            oldest_override=None,
            newest_override=None,
        )

        with pytest.raises(AttributeError):
            trend_data.total_count = 20  # type: ignore[misc]


class TestOverrideTrendRepositoryStubCompliance:
    """Tests that stub complies with OverrideTrendRepositoryProtocol."""

    def test_stub_implements_protocol(self) -> None:
        """Test stub is compatible with protocol."""
        stub = OverrideTrendRepositoryStub()
        # This should type-check if stub implements protocol
        _repo: OverrideTrendRepositoryProtocol = stub
        assert _repo is not None

    @pytest.mark.asyncio
    async def test_get_override_count_empty_history(self) -> None:
        """Test get_override_count with empty history."""
        stub = OverrideTrendRepositoryStub()
        count = await stub.get_override_count(days=30)
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_override_count_with_history(self) -> None:
        """Test get_override_count returns correct count."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)

        # Add 5 overrides in last 10 days
        history = [now - timedelta(days=i * 2) for i in range(5)]
        stub.set_override_history(history)

        count = await stub.get_override_count(days=30)
        assert count == 5

    @pytest.mark.asyncio
    async def test_get_override_count_filters_by_days(self) -> None:
        """Test get_override_count respects day filter."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)

        # Add overrides: 3 recent, 2 older
        history = [
            now - timedelta(days=5),
            now - timedelta(days=10),
            now - timedelta(days=15),
            now - timedelta(days=45),  # Outside 30-day window
            now - timedelta(days=60),  # Outside 30-day window
        ]
        stub.set_override_history(history)

        count = await stub.get_override_count(days=30)
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_override_count_for_period(self) -> None:
        """Test get_override_count_for_period returns correct count."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)

        history = [
            now - timedelta(days=5),
            now - timedelta(days=10),
            now - timedelta(days=35),
            now - timedelta(days=40),
        ]
        stub.set_override_history(history)

        # Query 30-60 days ago
        start = now - timedelta(days=60)
        end = now - timedelta(days=30)
        count = await stub.get_override_count_for_period(start, end)
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_rolling_trend_empty_history(self) -> None:
        """Test get_rolling_trend with empty history."""
        stub = OverrideTrendRepositoryStub()
        trend = await stub.get_rolling_trend(days=90)

        assert trend.total_count == 0
        assert trend.daily_rate == 0.0
        assert trend.period_days == 90
        assert trend.oldest_override is None
        assert trend.newest_override is None

    @pytest.mark.asyncio
    async def test_get_rolling_trend_with_data(self) -> None:
        """Test get_rolling_trend returns correct data."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)

        oldest = now - timedelta(days=30)
        newest = now - timedelta(days=5)
        history = [newest, now - timedelta(days=15), oldest]
        stub.set_override_history(history)

        trend = await stub.get_rolling_trend(days=90)

        assert trend.total_count == 3
        assert trend.daily_rate == 3 / 90
        assert trend.period_days == 90
        assert trend.oldest_override == oldest
        assert trend.newest_override == newest


class TestOverrideTrendRepositoryStubMethods:
    """Tests for stub helper methods."""

    def test_set_override_history(self) -> None:
        """Test set_override_history configures stub."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        history = [now, now - timedelta(days=1)]
        stub.set_override_history(history)

        # Verify history is set (check internal state)
        assert len(stub._override_history) == 2

    def test_add_override(self) -> None:
        """Test add_override adds single entry."""
        stub = OverrideTrendRepositoryStub()
        stub.add_override()

        assert len(stub._override_history) == 1

    def test_add_override_with_timestamp(self) -> None:
        """Test add_override with specific timestamp."""
        stub = OverrideTrendRepositoryStub()
        specific_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        stub.add_override(specific_time)

        assert stub._override_history[0] == specific_time

    def test_clear_history(self) -> None:
        """Test clear_history removes all entries."""
        stub = OverrideTrendRepositoryStub()
        now = datetime.now(timezone.utc)
        stub.set_override_history([now, now - timedelta(days=1)])
        stub.clear_history()

        assert len(stub._override_history) == 0
