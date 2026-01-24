"""Unit tests for adoption ratio compute service (Story 8.6, PREVENT-7).

Tests adoption ratio metrics computation service including escalation querying,
ratio computation, and storage operations.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.adoption_ratio_compute_service import (
    AdoptionRatioComputeService,
)
from src.domain.models.adoption_ratio import AdoptionRatioMetrics


class TestAdoptionRatioComputeServiceCompute:
    """Test adoption ratio computation (PREVENT-7)."""

    @pytest.mark.asyncio
    async def test_compute_metrics_with_escalations_calculates_ratio(self):
        """Given escalations in cycle, compute adoption ratio metrics."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        # Mock escalation data: 10 escalations, 6 adopted
        king1_id = uuid4()
        king2_id = uuid4()
        cursor.fetchone.return_value = (10, 6, [str(king1_id), str(king2_id)])

        repository = AsyncMock()
        service = AdoptionRatioComputeService(db, repository)

        realm_id = "governance"
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = await service.compute_metrics_for_realm(
            realm_id=realm_id,
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        # Then
        assert metrics.realm_id == realm_id
        assert metrics.cycle_id == cycle_id
        assert metrics.escalation_count == 10
        assert metrics.adoption_count == 6
        assert metrics.adoption_ratio == 0.6  # 6/10 = 60% (PREVENT-7: exceeds 50%)
        assert len(metrics.adopting_kings) == 2

    @pytest.mark.asyncio
    async def test_compute_metrics_with_zero_escalations_has_none_ratio(self):
        """Given no escalations, ratio is None (not zero)."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        cursor.fetchone.return_value = (0, 0, [])

        repository = AsyncMock()
        service = AdoptionRatioComputeService(db, repository)

        realm_id = "governance"
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = await service.compute_metrics_for_realm(
            realm_id=realm_id,
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        # Then
        assert metrics.escalation_count == 0
        assert metrics.adoption_count == 0
        assert metrics.adoption_ratio is None
        assert len(metrics.adopting_kings) == 0

    @pytest.mark.asyncio
    async def test_compute_metrics_rejects_invalid_cycle_period(self):
        """Given cycle_end <= cycle_start, raise ValueError."""
        # Given
        db = MagicMock()
        repository = AsyncMock()
        service = AdoptionRatioComputeService(db, repository)

        realm_id = "governance"
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)

        # When/Then
        with pytest.raises(ValueError, match="must be after"):
            await service.compute_metrics_for_realm(
                realm_id=realm_id,
                cycle_id=cycle_id,
                cycle_start=cycle_start,
                cycle_end=cycle_end,
            )

    @pytest.mark.asyncio
    async def test_compute_metrics_queries_escalation_data_in_cycle_period(self):
        """Computation queries escalations within cycle period."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.return_value = (0, 0, [])

        repository = AsyncMock()
        service = AdoptionRatioComputeService(db, repository)

        realm_id = "governance"
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        await service.compute_metrics_for_realm(
            realm_id=realm_id,
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        # Then
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args[0]
        # Verify realm_id and cycle boundaries are in query parameters
        assert realm_id in call_args[1]
        assert cycle_start in call_args[1]
        assert cycle_end in call_args[1]


class TestAdoptionRatioComputeServiceStore:
    """Test adoption ratio metrics storage."""

    @pytest.mark.asyncio
    async def test_compute_and_store_saves_metrics_via_repository(self):
        """Given metrics computed, store via repository."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.return_value = (10, 5, [str(uuid4())])

        repository = AsyncMock()
        service = AdoptionRatioComputeService(db, repository)

        realm_id = "governance"
        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics = await service.compute_and_store_metrics(
            realm_id=realm_id,
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        # Then
        repository.save_metrics.assert_called_once_with(metrics)
        assert metrics.adoption_ratio == 0.5


class TestAdoptionRatioComputeServiceAllRealms:
    """Test computing metrics for all realms."""

    @pytest.mark.asyncio
    async def test_compute_all_realms_discovers_and_computes(self):
        """Compute metrics for all realms with escalations."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        # First call: discover realms
        # Second+ calls: get escalation data for each realm
        cursor.fetchall.return_value = [("governance",), ("council",)]
        cursor.fetchone.return_value = (5, 2, [str(uuid4())])

        repository = AsyncMock()
        service = AdoptionRatioComputeService(db, repository)

        cycle_id = "2026-W04"
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        metrics_list = await service.compute_all_realms(
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        # Then
        assert len(metrics_list) == 2
        assert repository.save_metrics.call_count == 2


class TestAdoptionRatioComputeServiceTrend:
    """Test trend delta computation."""

    @pytest.mark.asyncio
    async def test_compute_trend_delta_calculates_difference(self):
        """Given previous metrics, compute trend delta."""
        # Given
        db = MagicMock()
        repository = AsyncMock()

        previous_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W03",
            escalation_count=10,
            adoption_count=4,  # 40%
            adopting_kings=[uuid4()],
        )
        repository.get_previous_cycle_metrics.return_value = previous_metrics

        service = AdoptionRatioComputeService(db, repository)

        current_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=10,
            adoption_count=6,  # 60%
            adopting_kings=[uuid4()],
        )

        # When
        trend_delta = await service.compute_trend_delta(current_metrics)

        # Then
        # 60% - 40% = 20% increase (concerning trend)
        assert trend_delta is not None
        assert abs(trend_delta - 0.2) < 0.001

    @pytest.mark.asyncio
    async def test_compute_trend_delta_none_when_no_previous(self):
        """Given no previous metrics, trend delta is None."""
        # Given
        db = MagicMock()
        repository = AsyncMock()
        repository.get_previous_cycle_metrics.return_value = None

        service = AdoptionRatioComputeService(db, repository)

        current_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=10,
            adoption_count=6,
            adopting_kings=[uuid4()],
        )

        # When
        trend_delta = await service.compute_trend_delta(current_metrics)

        # Then
        assert trend_delta is None

    @pytest.mark.asyncio
    async def test_compute_trend_delta_none_when_current_ratio_none(self):
        """Given current ratio is None (no escalations), trend delta is None."""
        # Given
        db = MagicMock()
        repository = AsyncMock()

        service = AdoptionRatioComputeService(db, repository)

        current_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=0,  # No escalations
            adoption_count=0,
            adopting_kings=[],
        )

        # When
        trend_delta = await service.compute_trend_delta(current_metrics)

        # Then
        assert trend_delta is None
        # Repository should not be queried
        repository.get_previous_cycle_metrics.assert_not_called()


class TestAdoptionRatioComputeServiceThresholds:
    """Test threshold detection (PREVENT-7)."""

    @pytest.mark.asyncio
    async def test_computed_metrics_detect_threshold_breach(self):
        """Computed metrics can detect threshold breach (PREVENT-7)."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        # 55% adoption ratio - exceeds 50% threshold
        cursor.fetchone.return_value = (20, 11, [str(uuid4())])

        repository = AsyncMock()
        service = AdoptionRatioComputeService(db, repository)

        # When
        metrics = await service.compute_metrics_for_realm(
            realm_id="governance",
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
        )

        # Then
        assert metrics.exceeds_threshold(0.50) is True  # PREVENT-7
        assert metrics.severity() == "WARN"
        assert metrics.health_status() == "WARN"

    @pytest.mark.asyncio
    async def test_computed_metrics_detect_critical_threshold(self):
        """Computed metrics detect critical threshold (>70%)."""
        # Given
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor

        # 75% adoption ratio - critical level
        cursor.fetchone.return_value = (20, 15, [str(uuid4())])

        repository = AsyncMock()
        service = AdoptionRatioComputeService(db, repository)

        # When
        metrics = await service.compute_metrics_for_realm(
            realm_id="governance",
            cycle_id="2026-W04",
            cycle_start=datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
            cycle_end=datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc),
        )

        # Then
        assert metrics.exceeds_threshold(0.50) is True
        assert metrics.severity() == "CRITICAL"
        assert metrics.health_status() == "CRITICAL"
