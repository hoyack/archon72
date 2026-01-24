"""Unit tests for LegitimacyDashboardService (Story 8.4, FR-8.4).

Tests dashboard data aggregation, caching, and query logic.

Constitutional Requirements:
- FR-8.4: Dashboard accessible to High Archon
- NFR-5.6: 5-minute cache TTL
- NFR-1.2: <500ms response time
"""

from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.application.services.legitimacy_dashboard_service import (
    LegitimacyDashboardService,
)
from src.domain.models.legitimacy_dashboard import (
    DeliberationMetrics,
    LegitimacyDashboardData,
    PetitionStateCounts,
)
from src.infrastructure.cache.dashboard_cache import DashboardCache


@pytest.fixture
def mock_db():
    """Mock database connection."""
    return Mock()


@pytest.fixture
def mock_cache():
    """Mock dashboard cache."""
    return Mock(spec=DashboardCache)


@pytest.fixture
def dashboard_service(mock_db, mock_cache):
    """LegitimacyDashboardService with mock dependencies."""
    return LegitimacyDashboardService(db_connection=mock_db, cache=mock_cache)


class TestGetDashboardData:
    """Tests for get_dashboard_data method (FR-8.4)."""

    def test_returns_cached_data_if_available(
        self, dashboard_service, mock_db, mock_cache
    ):
        """Test that cached data is returned when available (NFR-5.6)."""
        # Arrange
        cycle_id = "2026-W04"
        cached_dashboard = LegitimacyDashboardData(
            current_cycle_score=0.92,
            current_cycle_id=cycle_id,
            health_status="HEALTHY",
            historical_trend=[],
            petitions_by_state=PetitionStateCounts(
                received=10,
                deliberating=5,
                acknowledged=3,
                referred=2,
                escalated=1,
                deferred=0,
                no_response=0,
            ),
            orphan_petition_count=0,
            average_time_to_fate=120.0,
            median_time_to_fate=100.0,
            deliberation_metrics=DeliberationMetrics(
                total_deliberations=10,
                consensus_rate=0.9,
                timeout_rate=0.05,
                deadlock_rate=0.05,
            ),
            archon_acknowledgment_rates=[],
            data_refreshed_at=datetime.now(timezone.utc),
        )
        mock_cache.get.return_value = cached_dashboard

        # Act
        result = dashboard_service.get_dashboard_data(cycle_id)

        # Assert
        assert result == cached_dashboard
        mock_cache.get.assert_called_once_with(cycle_id)
        # Database should not be queried when cache hit
        mock_db.cursor.assert_not_called()

    def test_queries_database_on_cache_miss(
        self, dashboard_service, mock_db, mock_cache
    ):
        """Test that database is queried on cache miss."""
        # Arrange
        cycle_id = "2026-W04"
        mock_cache.get.return_value = None  # Cache miss

        # Mock cursor for all database queries
        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor

        # Mock current cycle metrics query
        mock_cursor.fetchone.side_effect = [
            # Current cycle metrics
            (0.85, 150.0, 120.0),
            # Orphan count
            (5,),
            # Deliberation metrics
            (20, 18, 1, 1),
        ]

        # Mock historical trend query
        mock_cursor.fetchall.side_effect = [
            # Historical trend
            [("2026-W03", 0.88, datetime.now(timezone.utc))],
            # Petition state counts
            [("RECEIVED", 10), ("DELIBERATING", 5)],
            # Archon rates
            [],
        ]

        # Act
        result = dashboard_service.get_dashboard_data(cycle_id)

        # Assert
        assert result.current_cycle_id == cycle_id
        assert result.current_cycle_score == 0.85
        assert result.average_time_to_fate == 150.0
        assert result.orphan_petition_count == 5
        mock_cache.set.assert_called_once_with(cycle_id, result)

    def test_handles_no_metrics_for_cycle(self, dashboard_service, mock_db, mock_cache):
        """Test handling when no metrics exist for cycle."""
        # Arrange
        cycle_id = "2026-W99"
        mock_cache.get.return_value = None

        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor

        # Mock no metrics found
        mock_cursor.fetchone.side_effect = [
            None,  # No current cycle metrics
            (0,),  # No orphans
            (0, 0, 0, 0),  # No deliberations
        ]

        mock_cursor.fetchall.side_effect = [
            [],  # No historical trend
            [],  # No petition state counts
            [],  # No archon rates
        ]

        # Act
        result = dashboard_service.get_dashboard_data(cycle_id)

        # Assert
        assert result.current_cycle_score is None
        assert result.health_status == "NO_DATA"
        assert result.average_time_to_fate is None
        assert result.median_time_to_fate is None


class TestQueryPetitionStateCounts:
    """Tests for _query_petition_state_counts method."""

    def test_aggregates_petition_counts_by_state(
        self, dashboard_service, mock_db, mock_cache
    ):
        """Test petition state count aggregation."""
        # Arrange
        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("RECEIVED", 10),
            ("DELIBERATING", 5),
            ("ACKNOWLEDGED", 20),
            ("REFERRED", 3),
            ("ESCALATED", 2),
            ("DEFERRED", 1),
            ("NO_RESPONSE", 4),
        ]

        # Act
        result = dashboard_service._query_petition_state_counts()

        # Assert
        assert result.received == 10
        assert result.deliberating == 5
        assert result.acknowledged == 20
        assert result.referred == 3
        assert result.escalated == 2
        assert result.deferred == 1
        assert result.no_response == 4
        assert result.total() == 45

    def test_handles_missing_states(self, dashboard_service, mock_db, mock_cache):
        """Test handling when some states have no petitions."""
        # Arrange
        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("RECEIVED", 5),
            # DELIBERATING missing
            ("ACKNOWLEDGED", 10),
        ]

        # Act
        result = dashboard_service._query_petition_state_counts()

        # Assert
        assert result.received == 5
        assert result.deliberating == 0  # Default value
        assert result.acknowledged == 10
        assert result.referred == 0
        assert result.escalated == 0
        assert result.deferred == 0
        assert result.no_response == 0


class TestQueryDeliberationMetrics:
    """Tests for _query_deliberation_metrics method."""

    def test_computes_deliberation_rates(self, dashboard_service, mock_db, mock_cache):
        """Test deliberation rate computation."""
        # Arrange
        cycle_id = "2026-W04"
        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (
            100,  # total_deliberations
            90,  # consensus_count
            5,  # timeout_count
            5,  # deadlock_count
        )

        # Act
        result = dashboard_service._query_deliberation_metrics(cycle_id)

        # Assert
        assert result.total_deliberations == 100
        assert result.consensus_rate == 0.90
        assert result.timeout_rate == 0.05
        assert result.deadlock_rate == 0.05

    def test_handles_no_deliberations(self, dashboard_service, mock_db, mock_cache):
        """Test handling when no deliberations in cycle."""
        # Arrange
        cycle_id = "2026-W04"
        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        # Act
        result = dashboard_service._query_deliberation_metrics(cycle_id)

        # Assert
        assert result.total_deliberations == 0
        assert result.consensus_rate == 0.0
        assert result.timeout_rate == 0.0
        assert result.deadlock_rate == 0.0


class TestQueryArchonAcknowledgmentRates:
    """Tests for _query_archon_acknowledgment_rates method."""

    def test_computes_per_archon_rates(self, dashboard_service, mock_db, mock_cache):
        """Test per-archon acknowledgment rate computation."""
        # Arrange
        cycle_id = "2026-W04"
        archon_id_1 = uuid4()
        archon_id_2 = uuid4()

        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            (archon_id_1, "Archon Alpha", 21, 7.0),  # 21 acks over 7 days = 3/day
            (archon_id_2, "Archon Beta", 14, 7.0),  # 14 acks over 7 days = 2/day
        ]

        # Act
        result = dashboard_service._query_archon_acknowledgment_rates(cycle_id)

        # Assert
        assert len(result) == 2
        assert result[0].archon_id == archon_id_1
        assert result[0].archon_name == "Archon Alpha"
        assert result[0].acknowledgment_count == 21
        assert result[0].rate == 3.0

        assert result[1].archon_id == archon_id_2
        assert result[1].archon_name == "Archon Beta"
        assert result[1].acknowledgment_count == 14
        assert result[1].rate == 2.0

    def test_handles_no_archon_activity(self, dashboard_service, mock_db, mock_cache):
        """Test handling when no archon acknowledgments in cycle."""
        # Arrange
        cycle_id = "2026-W04"
        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        # Act
        result = dashboard_service._query_archon_acknowledgment_rates(cycle_id)

        # Assert
        assert result == []
