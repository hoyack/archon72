"""Unit tests for TopicDailyLimiterStub (Story 6.9, FR118).

Tests the in-memory implementation of daily rate limiting.

Constitutional Constraints:
- FR118: External topic rate limiting (10/day)
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.topic_daily_limiter import (
    DAILY_TOPIC_LIMIT,
    TopicDailyLimiterProtocol,
)
from src.infrastructure.stubs.topic_daily_limiter_stub import (
    DailySubmissionRecord,
    TopicDailyLimiterStub,
)


class TestTopicDailyLimiterStubImplementsProtocol:
    """Test stub implements protocol correctly."""

    def test_implements_protocol(self) -> None:
        """Test stub inherits from protocol."""
        stub = TopicDailyLimiterStub()
        assert isinstance(stub, TopicDailyLimiterProtocol)


class TestCheckDailyLimit:
    """Tests for check_daily_limit method."""

    @pytest.mark.asyncio
    async def test_returns_bool(self) -> None:
        """Test returns boolean."""
        stub = TopicDailyLimiterStub()
        result = await stub.check_daily_limit("source-1")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_new_source_within_limit(self) -> None:
        """Test new source is within limit."""
        stub = TopicDailyLimiterStub()
        within_limit = await stub.check_daily_limit("new-source")
        assert within_limit is True

    @pytest.mark.asyncio
    async def test_source_at_limit_returns_false(self) -> None:
        """Test source at limit returns False."""
        stub = TopicDailyLimiterStub()
        # Fill up to limit
        for i in range(DAILY_TOPIC_LIMIT):
            stub.add_submission("source-1", f"topic-{i}")

        within_limit = await stub.check_daily_limit("source-1")
        assert within_limit is False

    @pytest.mark.asyncio
    async def test_source_below_limit_returns_true(self) -> None:
        """Test source below limit returns True."""
        stub = TopicDailyLimiterStub()
        stub.add_submission("source-1", "topic-1")

        within_limit = await stub.check_daily_limit("source-1")
        assert within_limit is True


class TestGetDailyCount:
    """Tests for get_daily_count method."""

    @pytest.mark.asyncio
    async def test_new_source_has_zero_count(self) -> None:
        """Test new source has zero count."""
        stub = TopicDailyLimiterStub()
        count = await stub.get_daily_count("new-source")
        assert count == 0

    @pytest.mark.asyncio
    async def test_counts_todays_submissions_only(self) -> None:
        """Test only counts today's submissions."""
        stub = TopicDailyLimiterStub()
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Yesterday's submission
        stub.add_submission("source-1", "topic-old", yesterday)
        # Today's submissions
        stub.add_submission("source-1", "topic-1", now)
        stub.add_submission("source-1", "topic-2", now)

        count = await stub.get_daily_count("source-1")
        assert count == 2  # Only today's


class TestRecordDailySubmission:
    """Tests for record_daily_submission method."""

    @pytest.mark.asyncio
    async def test_records_submission_and_returns_count(self) -> None:
        """Test records submission and returns new count."""
        stub = TopicDailyLimiterStub()
        count = await stub.record_daily_submission("source-1")

        assert count == 1
        submissions = stub.get_submissions_for_source("source-1")
        assert len(submissions) == 1

    @pytest.mark.asyncio
    async def test_count_increments_with_each_submission(self) -> None:
        """Test count increments correctly."""
        stub = TopicDailyLimiterStub()

        count1 = await stub.record_daily_submission("source-1")
        count2 = await stub.record_daily_submission("source-1")
        count3 = await stub.record_daily_submission("source-1")

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3


class TestGetDailyLimit:
    """Tests for get_daily_limit method."""

    @pytest.mark.asyncio
    async def test_returns_default_limit(self) -> None:
        """Test returns default limit (FR118 = 10)."""
        stub = TopicDailyLimiterStub()
        limit = await stub.get_daily_limit()
        assert limit == DAILY_TOPIC_LIMIT
        assert limit == 10  # FR118 specifies 10

    @pytest.mark.asyncio
    async def test_configurable_limit(self) -> None:
        """Test limit can be configured."""
        stub = TopicDailyLimiterStub()
        stub.set_daily_limit(5)

        limit = await stub.get_daily_limit()
        assert limit == 5


class TestGetLimitResetTime:
    """Tests for get_limit_reset_time method."""

    @pytest.mark.asyncio
    async def test_returns_midnight_utc(self) -> None:
        """Test returns midnight UTC tomorrow."""
        stub = TopicDailyLimiterStub()
        reset_time = await stub.get_limit_reset_time("any-source")

        # Should be midnight UTC
        assert reset_time.hour == 0
        assert reset_time.minute == 0
        assert reset_time.second == 0

        # Should be tomorrow or later
        now = datetime.now(timezone.utc)
        assert reset_time > now


class TestIsExternalSource:
    """Tests for is_external_source method."""

    @pytest.mark.asyncio
    async def test_default_is_internal(self) -> None:
        """Test default sources are internal."""
        stub = TopicDailyLimiterStub()
        is_external = await stub.is_external_source("any-source")
        assert is_external is False

    @pytest.mark.asyncio
    async def test_configured_external_sources(self) -> None:
        """Test external sources can be configured."""
        stub = TopicDailyLimiterStub()
        stub.add_external_source("external-api-1")

        is_external = await stub.is_external_source("external-api-1")
        assert is_external is True

    @pytest.mark.asyncio
    async def test_can_remove_external_source(self) -> None:
        """Test external sources can be removed."""
        stub = TopicDailyLimiterStub()
        stub.add_external_source("source-1")
        stub.remove_external_source("source-1")

        is_external = await stub.is_external_source("source-1")
        assert is_external is False


class TestTestHelpers:
    """Tests for test helper methods."""

    def test_get_submissions_returns_all(self) -> None:
        """Test get_submissions returns all submissions."""
        stub = TopicDailyLimiterStub()
        stub.add_submission("source-1", "topic-1")
        stub.add_submission("source-2", "topic-2")

        submissions = stub.get_submissions()
        assert len(submissions) == 2

    def test_get_submissions_for_source_filters(self) -> None:
        """Test get_submissions_for_source filters correctly."""
        stub = TopicDailyLimiterStub()
        stub.add_submission("source-1", "topic-1a")
        stub.add_submission("source-1", "topic-1b")
        stub.add_submission("source-2", "topic-2")

        submissions = stub.get_submissions_for_source("source-1")
        assert len(submissions) == 2
        assert all(s.source_id == "source-1" for s in submissions)

    def test_clear_removes_all_data(self) -> None:
        """Test clear removes all stored data."""
        stub = TopicDailyLimiterStub()
        stub.add_submission("source-1", "topic-1")
        stub.add_external_source("external-1")
        stub.set_daily_limit(5)

        stub.clear()

        assert len(stub.get_submissions()) == 0
        assert len(stub._external_sources) == 0
        assert stub._daily_limit == DAILY_TOPIC_LIMIT
