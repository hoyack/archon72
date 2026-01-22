"""Unit tests for legitimacy metrics service (Story 8.1, FR-8.1, FR-8.2).

Tests legitimacy metrics computation service including petition querying,
score computation, and storage operations.

Constitutional Constraints:
- FR-8.1: System SHALL compute legitimacy decay metric per cycle
- FR-8.2: Decay formula: (fated_petitions / total_petitions) within SLA
- NFR-1.5: Metric computation completes within 60 seconds
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

from src.application.services.legitimacy_metrics_service import (
    LegitimacyMetricsService,
)
from src.domain.models.legitimacy_metrics import LegitimacyMetrics


class TestLegitimacyMetricsServiceCompute:
    """Test legitimacy metrics computation (FR-8.1, FR-8.2)."""

    def test_compute_metrics_with_petitions_calculates_score(self):
        """Given petitions in cycle, compute legitimacy metrics."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        # Mock petition data: 10 petitions, 8 fated
        petition_rows = [
            (
                str(uuid4()),
                "ACKNOWLEDGED",
                datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 20, 11, 0, 0, tzinfo=timezone.utc),
                3600.0,
            )
            for _ in range(8)
        ] + [
            (
                str(uuid4()),
                "RECEIVED",
                datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
                0.0,
            )
            for _ in range(2)
        ]

        cursor.fetchall.return_value = petition_rows

        service = LegitimacyMetricsService(db)

        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = service.compute_metrics(cycle_id, cycle_start, cycle_end)

        # Then
        assert metrics.cycle_id == cycle_id
        assert metrics.total_petitions == 10
        assert metrics.fated_petitions == 8
        assert metrics.legitimacy_score == 0.8  # FR-8.2: 8/10
        assert metrics.average_time_to_fate is not None
        assert metrics.median_time_to_fate is not None

    def test_compute_metrics_with_zero_petitions_handles_gracefully(self):
        """Given no petitions, compute metrics with None score."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        cursor.fetchall.return_value = []  # No petitions

        service = LegitimacyMetricsService(db)

        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = service.compute_metrics(cycle_id, cycle_start, cycle_end)

        # Then
        assert metrics.total_petitions == 0
        assert metrics.fated_petitions == 0
        assert metrics.legitimacy_score is None
        assert metrics.average_time_to_fate is None
        assert metrics.median_time_to_fate is None

    def test_compute_metrics_rejects_invalid_cycle_period(self):
        """Given cycle_end <= cycle_start, raise ValueError."""
        # Given
        db = MagicMock()
        service = LegitimacyMetricsService(db)

        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)

        # When/Then
        with pytest.raises(ValueError, match="must be after"):
            service.compute_metrics(cycle_id, cycle_start, cycle_end)

    def test_compute_metrics_queries_petition_data_in_cycle_period(self):
        """Computation queries petitions within cycle period."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = []

        service = LegitimacyMetricsService(db)

        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        service.compute_metrics(cycle_id, cycle_start, cycle_end)

        # Then
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args
        assert cycle_start in call_args[0]
        assert cycle_end in call_args[0]


class TestLegitimacyMetricsServiceStore:
    """Test legitimacy metrics storage."""

    def test_store_metrics_inserts_to_database(self):
        """Given metrics, store to legitimacy_metrics table."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        service = LegitimacyMetricsService(db)

        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=90,
            legitimacy_score=0.9,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When
        service.store_metrics(metrics)

        # Then
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args[0]
        assert "INSERT INTO legitimacy_metrics" in call_args[0]
        assert metrics.cycle_id in call_args[1]
        db.commit.assert_called_once()

    def test_store_metrics_commits_transaction(self):
        """Storage commits database transaction."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        service = LegitimacyMetricsService(db)

        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=90,
            legitimacy_score=0.9,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When
        service.store_metrics(metrics)

        # Then
        db.commit.assert_called_once()

    def test_store_metrics_rolls_back_on_error(self):
        """Given storage error, rollback transaction."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        cursor.execute.side_effect = Exception("Database error")

        service = LegitimacyMetricsService(db)

        metrics = LegitimacyMetrics(
            metrics_id=uuid4(),
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            total_petitions=100,
            fated_petitions=90,
            legitimacy_score=0.9,
            average_time_to_fate=3600.0,
            median_time_to_fate=3000.0,
            computed_at=datetime.now(timezone.utc),
        )

        # When/Then
        with pytest.raises(Exception):
            service.store_metrics(metrics)

        db.rollback.assert_called_once()


class TestLegitimacyMetricsServiceGet:
    """Test legitimacy metrics retrieval."""

    def test_get_metrics_retrieves_by_cycle_id(self):
        """Given cycle_id, retrieve metrics."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        metrics_id = uuid4()
        cursor.fetchone.return_value = (
            metrics_id,
            "2026-W04",
            datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
            100,
            90,
            0.9,
            3600.0,
            3000.0,
            datetime.now(timezone.utc),
        )

        service = LegitimacyMetricsService(db)

        # When
        metrics = service.get_metrics("2026-W04")

        # Then
        assert metrics is not None
        assert metrics.cycle_id == "2026-W04"
        assert metrics.legitimacy_score == 0.9

    def test_get_metrics_returns_none_when_not_found(self):
        """Given non-existent cycle_id, return None."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.return_value = None

        service = LegitimacyMetricsService(db)

        # When
        metrics = service.get_metrics("2026-W99")

        # Then
        assert metrics is None

    def test_get_recent_metrics_retrieves_ordered_by_cycle_start(self):
        """Retrieve recent metrics ordered by cycle_start descending."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        cursor.fetchall.return_value = [
            (
                uuid4(),
                "2026-W05",
                datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 3, 0, 0, 0, tzinfo=timezone.utc),
                100,
                85,
                0.85,
                3600.0,
                3000.0,
                datetime.now(timezone.utc),
            ),
            (
                uuid4(),
                "2026-W04",
                datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
                100,
                90,
                0.9,
                3600.0,
                3000.0,
                datetime.now(timezone.utc),
            ),
        ]

        service = LegitimacyMetricsService(db)

        # When
        metrics_list = service.get_recent_metrics(limit=2)

        # Then
        assert len(metrics_list) == 2
        assert metrics_list[0].cycle_id == "2026-W05"
        assert metrics_list[1].cycle_id == "2026-W04"

    def test_get_recent_metrics_respects_limit(self):
        """get_recent_metrics respects limit parameter."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = []

        service = LegitimacyMetricsService(db)

        # When
        service.get_recent_metrics(limit=5)

        # Then
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args[0]
        assert (5,) in call_args or call_args[1] == (5,)
