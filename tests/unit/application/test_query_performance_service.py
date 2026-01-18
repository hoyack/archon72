"""Unit tests for QueryPerformanceService (Story 8.8, AC4, FR106).

Tests for query SLA monitoring and compliance tracking.
"""

import pytest

from src.application.services.query_performance_service import (
    QUERY_SLA_THRESHOLD_EVENTS,
    QUERY_SLA_TIMEOUT_SECONDS,
    QueryPerformanceService,
)
from src.domain.errors.failure_prevention import QueryPerformanceViolationError


@pytest.fixture
def service() -> QueryPerformanceService:
    """Create a QueryPerformanceService instance."""
    return QueryPerformanceService()


class TestStartQuery:
    """Tests for start_query method."""

    @pytest.mark.asyncio
    async def test_returns_query_id(self, service: QueryPerformanceService) -> None:
        """Test that starting a query returns a query ID."""
        query_id = await service.start_query(event_count=100)

        assert query_id is not None
        assert isinstance(query_id, str)

    @pytest.mark.asyncio
    async def test_tracks_query_start(self, service: QueryPerformanceService) -> None:
        """Test that query start is tracked."""
        query_id = await service.start_query(event_count=100)

        assert query_id in service._active_queries


class TestTrackQuery:
    """Tests for track_query method."""

    @pytest.mark.asyncio
    async def test_marks_query_complete(self, service: QueryPerformanceService) -> None:
        """Test that query is marked as complete."""
        query_id = await service.start_query(event_count=100)
        compliant = await service.track_query(
            query_id, event_count=100, duration_ms=1000.0
        )

        assert compliant is True
        assert query_id not in service._active_queries

    @pytest.mark.asyncio
    async def test_returns_compliance_status(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that compliance status is returned."""
        query_id = await service.start_query(event_count=100)
        compliant = await service.track_query(
            query_id, event_count=100, duration_ms=500.0
        )

        assert isinstance(compliant, bool)
        assert compliant is True  # 500ms is well under 30s SLA


class TestCheckCompliance:
    """Tests for check_compliance method (FR106)."""

    def test_compliant_when_within_sla(self, service: QueryPerformanceService) -> None:
        """Test that query is compliant when within SLA."""
        # Query with small event count and quick duration
        result = service.check_compliance(
            event_count=100,
            duration_seconds=1.0,
        )

        assert result is True

    def test_non_compliant_when_exceeds_timeout_for_small_query(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that query is non-compliant when exceeds 30s for <10k events."""
        # Query with < 10k events but over 30 seconds
        result = service.check_compliance(
            event_count=5000,
            duration_seconds=QUERY_SLA_TIMEOUT_SECONDS + 5.0,
        )

        assert result is False

    def test_compliant_for_large_queries_slow(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that large queries (>10k events) have no strict timeout."""
        # Large query over 10k events - SLA doesn't apply strictly
        result = service.check_compliance(
            event_count=QUERY_SLA_THRESHOLD_EVENTS + 1000,
            duration_seconds=QUERY_SLA_TIMEOUT_SECONDS + 10.0,
        )

        # Larger queries have extended SLA
        assert result is True


class TestRaiseIfNonCompliant:
    """Tests for raise_if_non_compliant method."""

    @pytest.mark.asyncio
    async def test_raises_when_non_compliant(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that error is raised when non-compliant."""
        with pytest.raises(QueryPerformanceViolationError):
            await service.raise_if_non_compliant(
                query_id="test_query",
                event_count=5000,  # Under threshold
                duration_seconds=QUERY_SLA_TIMEOUT_SECONDS + 10.0,
            )

    @pytest.mark.asyncio
    async def test_does_not_raise_when_compliant(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that no error is raised when compliant."""
        # Should not raise
        await service.raise_if_non_compliant(
            query_id="test_query",
            event_count=100,
            duration_seconds=1.0,
        )


class TestUpdateBatchProgress:
    """Tests for update_batch_progress method."""

    @pytest.mark.asyncio
    async def test_updates_batch_progress(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that batch progress is updated for large queries."""
        # Start a large query that requires batching
        query_id = await service.start_query(
            event_count=QUERY_SLA_THRESHOLD_EVENTS + 5000
        )

        progress = await service.update_batch_progress(
            query_id=query_id,
            processed_events=1000,
        )

        assert progress is not None
        assert progress.processed_events > 0

    @pytest.mark.asyncio
    async def test_returns_none_for_non_batched_query(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that None is returned for non-batched queries."""
        # Start a small query (not batched)
        query_id = await service.start_query(event_count=100)

        progress = await service.update_batch_progress(
            query_id=query_id,
            processed_events=50,
        )

        # Small queries don't have batch progress
        assert progress is None


class TestGetComplianceStats:
    """Tests for get_compliance_stats method."""

    @pytest.mark.asyncio
    async def test_returns_initial_stats(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that initial stats are returned."""
        stats = await service.get_compliance_stats()

        assert stats["total_queries"] == 0
        assert stats["compliant_count"] == 0
        assert stats["non_compliant_count"] == 0
        assert stats["compliance_rate"] == 100.0  # Perfect when no queries

    @pytest.mark.asyncio
    async def test_tracks_compliant_queries(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that compliant queries are tracked."""
        query_id = await service.start_query(event_count=100)
        await service.track_query(query_id, event_count=100, duration_ms=1000.0)

        stats = await service.get_compliance_stats()

        assert stats["total_queries"] == 1
        assert stats["compliant_count"] == 1

    @pytest.mark.asyncio
    async def test_calculates_compliance_rate(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that compliance rate is calculated correctly."""
        # Complete some queries
        for _ in range(4):
            query_id = await service.start_query(event_count=100)
            await service.track_query(query_id, event_count=100, duration_ms=500.0)

        stats = await service.get_compliance_stats()

        assert stats["total_queries"] == 4
        assert stats["compliance_rate"] == 100.0


class TestGetActiveQueries:
    """Tests for get_active_queries method."""

    @pytest.mark.asyncio
    async def test_returns_active_queries(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that active queries are returned."""
        query_id = await service.start_query(event_count=100)

        active = await service.get_active_queries()

        assert len(active) == 1
        assert active[0]["query_id"] == query_id


class TestGetRecentViolations:
    """Tests for get_recent_violations method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_violations(
        self, service: QueryPerformanceService
    ) -> None:
        """Test that empty list is returned when no violations."""
        violations = await service.get_recent_violations()

        assert violations == []

    @pytest.mark.asyncio
    async def test_returns_violations(self, service: QueryPerformanceService) -> None:
        """Test that violations are returned when present."""
        # Track a non-compliant query
        query_id = await service.start_query(event_count=5000)
        # Duration in ms: 35 seconds = 35000 ms
        await service.track_query(
            query_id,
            event_count=5000,
            duration_ms=35000.0,  # 35 seconds, over the 30s SLA
        )

        violations = await service.get_recent_violations()

        assert len(violations) == 1


class TestConstants:
    """Tests for service constants (FR106)."""

    def test_sla_threshold_is_10k(self) -> None:
        """Test that SLA threshold is 10,000 events (FR106)."""
        assert QUERY_SLA_THRESHOLD_EVENTS == 10000

    def test_sla_timeout_is_30_seconds(self) -> None:
        """Test that SLA timeout is 30 seconds (FR106)."""
        assert QUERY_SLA_TIMEOUT_SECONDS == 30.0
