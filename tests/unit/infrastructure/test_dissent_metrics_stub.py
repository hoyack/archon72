"""Unit tests for DissentMetricsStub (Story 2.4, FR12).

Tests the in-memory stub implementation for DissentMetricsPort.

Test categories:
- DEV_MODE_WATERMARK pattern
- record_vote_dissent method
- get_rolling_average method
- get_dissent_history method
- is_below_threshold method
- Time-based filtering
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.infrastructure.stubs.dissent_metrics_stub import (
    DEV_MODE_WATERMARK,
    DissentMetricsStub,
)


class TestDevModeWatermark:
    """Tests for DEV_MODE_WATERMARK pattern."""

    def test_dev_mode_watermark_exists(self) -> None:
        """DEV_MODE_WATERMARK constant exists."""
        assert DEV_MODE_WATERMARK is not None

    def test_dev_mode_watermark_is_string(self) -> None:
        """DEV_MODE_WATERMARK is a string."""
        assert isinstance(DEV_MODE_WATERMARK, str)


class TestDissentMetricsStub:
    """Tests for DissentMetricsStub implementation."""

    @pytest.fixture
    def stub(self) -> DissentMetricsStub:
        return DissentMetricsStub()

    @pytest.mark.asyncio
    async def test_record_vote_dissent(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """record_vote_dissent stores record in memory."""
        output_id = uuid4()
        recorded_at = datetime.now(timezone.utc)

        await stub.record_vote_dissent(output_id, 15.5, recorded_at)

        history = await stub.get_dissent_history(days=30)
        assert len(history) == 1
        assert history[0].output_id == output_id
        assert history[0].dissent_percentage == 15.5

    @pytest.mark.asyncio
    async def test_get_rolling_average_empty(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """get_rolling_average returns 0.0 for empty history."""
        average = await stub.get_rolling_average(days=30)
        assert average == 0.0

    @pytest.mark.asyncio
    async def test_get_rolling_average_single_record(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """get_rolling_average returns single record's value."""
        await stub.record_vote_dissent(uuid4(), 15.0, datetime.now(timezone.utc))

        average = await stub.get_rolling_average(days=30)
        assert average == 15.0

    @pytest.mark.asyncio
    async def test_get_rolling_average_multiple_records(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """get_rolling_average calculates correct average."""
        now = datetime.now(timezone.utc)
        await stub.record_vote_dissent(uuid4(), 10.0, now)
        await stub.record_vote_dissent(uuid4(), 20.0, now)
        await stub.record_vote_dissent(uuid4(), 30.0, now)

        average = await stub.get_rolling_average(days=30)
        assert average == 20.0  # (10 + 20 + 30) / 3

    @pytest.mark.asyncio
    async def test_get_rolling_average_filters_old_records(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """get_rolling_average excludes records older than period."""
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=31)

        await stub.record_vote_dissent(uuid4(), 5.0, old_date)  # Old, excluded
        await stub.record_vote_dissent(uuid4(), 15.0, now)  # Recent, included

        average = await stub.get_rolling_average(days=30)
        assert average == 15.0  # Only recent record

    @pytest.mark.asyncio
    async def test_get_dissent_history_returns_ordered_list(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """get_dissent_history returns records ordered by recorded_at."""
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(hours=1)

        await stub.record_vote_dissent(uuid4(), 20.0, now)
        await stub.record_vote_dissent(uuid4(), 10.0, earlier)

        history = await stub.get_dissent_history(days=30)
        assert len(history) == 2
        assert history[0].recorded_at < history[1].recorded_at

    @pytest.mark.asyncio
    async def test_is_below_threshold_true(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """is_below_threshold returns True when average < threshold."""
        now = datetime.now(timezone.utc)
        await stub.record_vote_dissent(uuid4(), 5.0, now)
        await stub.record_vote_dissent(uuid4(), 7.0, now)

        is_below = await stub.is_below_threshold(threshold=10.0, days=30)
        assert is_below is True

    @pytest.mark.asyncio
    async def test_is_below_threshold_false(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """is_below_threshold returns False when average >= threshold."""
        now = datetime.now(timezone.utc)
        await stub.record_vote_dissent(uuid4(), 15.0, now)
        await stub.record_vote_dissent(uuid4(), 20.0, now)

        is_below = await stub.is_below_threshold(threshold=10.0, days=30)
        assert is_below is False

    @pytest.mark.asyncio
    async def test_is_below_threshold_empty(
        self,
        stub: DissentMetricsStub,
    ) -> None:
        """is_below_threshold returns True for empty history (0 < 10)."""
        is_below = await stub.is_below_threshold(threshold=10.0, days=30)
        assert is_below is True
