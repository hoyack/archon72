"""Unit tests for override abuse detection service (Story 5.9, FR86-FR87, FP-3).

Tests the OverrideAbuseDetectionService with mock dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.anomaly_detector import AnomalyResult, FrequencyData
from src.application.ports.override_abuse_validator import ValidationResult
from src.application.services.override_abuse_detection_service import (
    OverrideAbuseDetectionService,
)
from src.domain.errors.override_abuse import (
    ConstitutionalConstraintViolationError,
    EvidenceDestructionAttemptError,
    HistoryEditAttemptError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.override_abuse import AnomalyType, ViolationType


class TestOverrideAbuseDetectionServiceValidation:
    """Tests for validate_override_command (FR86, FR87)."""

    @pytest.fixture
    def mock_validator(self) -> MagicMock:
        """Create mock abuse validator."""
        validator = MagicMock()
        validator.validate_constitutional_constraints = AsyncMock(
            return_value=ValidationResult.success()
        )
        validator.is_history_edit_attempt = AsyncMock(return_value=False)
        validator.is_evidence_destruction_attempt = AsyncMock(return_value=False)
        return validator

    @pytest.fixture
    def mock_anomaly_detector(self) -> MagicMock:
        """Create mock anomaly detector."""
        detector = MagicMock()
        detector.detect_keeper_anomalies = AsyncMock(return_value=[])
        detector.detect_slow_burn_erosion = AsyncMock(return_value=[])
        detector.get_keeper_override_frequency = AsyncMock(
            return_value=FrequencyData(
                override_count=0,
                time_window_days=90,
                daily_rate=0.0,
                deviation_from_baseline=0.0,
            )
        )
        return detector

    @pytest.fixture
    def mock_event_writer(self) -> MagicMock:
        """Create mock event writer."""
        writer = MagicMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def mock_halt_checker_operational(self) -> MagicMock:
        """Create mock halt checker that returns not halted."""
        checker = MagicMock()
        checker.is_halted = AsyncMock(return_value=False)
        checker.get_halt_reason = AsyncMock(return_value=None)
        return checker

    @pytest.fixture
    def mock_halt_checker_halted(self) -> MagicMock:
        """Create mock halt checker that returns halted."""
        checker = MagicMock()
        checker.is_halted = AsyncMock(return_value=True)
        checker.get_halt_reason = AsyncMock(return_value="Test halt reason")
        return checker

    @pytest.fixture
    def service(
        self,
        mock_validator: MagicMock,
        mock_anomaly_detector: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> OverrideAbuseDetectionService:
        """Create service with mock dependencies."""
        return OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

    @pytest.mark.asyncio
    async def test_validate_valid_override_passes(
        self,
        service: OverrideAbuseDetectionService,
    ) -> None:
        """Test validation passes for valid override scope."""
        result = await service.validate_override_command(
            scope="voting.extension",
            action_type="test",
            keeper_id="keeper-1",
        )
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_halt_check_first(
        self,
        mock_validator: MagicMock,
        mock_anomaly_detector: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_halted: MagicMock,
    ) -> None:
        """Test HALT CHECK FIRST pattern (CT-11)."""
        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_halted,
        )

        with pytest.raises(SystemHaltedError, match="CT-11"):
            await service.validate_override_command(
                scope="voting.extension",
                action_type="test",
                keeper_id="keeper-1",
            )

        # Validator should not be called during halt
        mock_validator.is_history_edit_attempt.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_rejects_history_edit_fr87(
        self,
        mock_validator: MagicMock,
        mock_anomaly_detector: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test validation rejects history edit attempt (FR87)."""
        mock_validator.is_history_edit_attempt.return_value = True

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        with pytest.raises(HistoryEditAttemptError):
            await service.validate_override_command(
                scope="history.delete",
                action_type="test",
                keeper_id="keeper-1",
            )

        # Event should be written for abuse rejection
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_rejects_evidence_destruction_fr87(
        self,
        mock_validator: MagicMock,
        mock_anomaly_detector: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test validation rejects evidence destruction attempt (FR87)."""
        mock_validator.is_evidence_destruction_attempt.return_value = True

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        with pytest.raises(EvidenceDestructionAttemptError):
            await service.validate_override_command(
                scope="witness.remove",
                action_type="test",
                keeper_id="keeper-1",
            )

        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_rejects_constitutional_constraint_fr86(
        self,
        mock_validator: MagicMock,
        mock_anomaly_detector: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test validation rejects constitutional constraint violation (FR86)."""
        mock_validator.validate_constitutional_constraints.return_value = (
            ValidationResult.failure(
                violation_type=ViolationType.FORBIDDEN_SCOPE,
                violation_details="Scope is forbidden",
            )
        )

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_anomaly_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        with pytest.raises(ConstitutionalConstraintViolationError):
            await service.validate_override_command(
                scope="forbidden.scope",
                action_type="test",
                keeper_id="keeper-1",
            )

        mock_event_writer.write_event.assert_called_once()


class TestOverrideAbuseDetectionServiceAnomalies:
    """Tests for detect_anomalies (FP-3, ADR-7)."""

    @pytest.fixture
    def mock_validator(self) -> MagicMock:
        """Create mock abuse validator."""
        validator = MagicMock()
        return validator

    @pytest.fixture
    def mock_event_writer(self) -> MagicMock:
        """Create mock event writer."""
        writer = MagicMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def mock_halt_checker_operational(self) -> MagicMock:
        """Create mock halt checker that returns not halted."""
        checker = MagicMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def mock_halt_checker_halted(self) -> MagicMock:
        """Create mock halt checker that returns halted."""
        checker = MagicMock()
        checker.is_halted = AsyncMock(return_value=True)
        checker.get_halt_reason = AsyncMock(return_value="Test halt reason")
        return checker

    @pytest.mark.asyncio
    async def test_detect_anomalies_halt_check_first(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_halted: MagicMock,
    ) -> None:
        """Test detect_anomalies HALT CHECK FIRST (CT-11)."""
        mock_detector = MagicMock()

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_halted,
        )

        with pytest.raises(SystemHaltedError, match="CT-11"):
            await service.detect_anomalies()

    @pytest.mark.asyncio
    async def test_detect_anomalies_empty_when_none(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test detect_anomalies returns empty when no anomalies."""
        mock_detector = MagicMock()
        mock_detector.detect_keeper_anomalies = AsyncMock(return_value=[])
        mock_detector.detect_slow_burn_erosion = AsyncMock(return_value=[])

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        results = await service.detect_anomalies()
        assert results == []
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_detect_anomalies_filters_by_confidence(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test detect_anomalies filters by confidence threshold."""
        low_confidence = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.5,  # Below threshold
            affected_keepers=("keeper-1",),
            details="Low confidence",
        )
        high_confidence = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.85,  # Above threshold
            affected_keepers=("keeper-2",),
            details="High confidence",
        )

        mock_detector = MagicMock()
        mock_detector.detect_keeper_anomalies = AsyncMock(
            return_value=[low_confidence, high_confidence]
        )
        mock_detector.detect_slow_burn_erosion = AsyncMock(return_value=[])

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        results = await service.detect_anomalies()
        assert len(results) == 1
        assert results[0].confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_detect_anomalies_writes_events(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test detect_anomalies writes events for detected anomalies (CT-12)."""
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            confidence_score=0.8,
            affected_keepers=("keeper-1", "keeper-2"),
            details="Slow burn detected",
        )

        mock_detector = MagicMock()
        mock_detector.detect_keeper_anomalies = AsyncMock(return_value=[])
        mock_detector.detect_slow_burn_erosion = AsyncMock(return_value=[anomaly])

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        await service.detect_anomalies()
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_slow_burn_erosion_ct9(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test slow-burn erosion detection (CT-9 patient attacker)."""
        slow_burn = AnomalyResult(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            confidence_score=0.75,
            affected_keepers=("keeper-1",),
            details="15% annual growth rate detected",
        )

        mock_detector = MagicMock()
        mock_detector.detect_keeper_anomalies = AsyncMock(return_value=[])
        mock_detector.detect_slow_burn_erosion = AsyncMock(return_value=[slow_burn])

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        results = await service.detect_anomalies()
        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.SLOW_BURN_EROSION


class TestOverrideAbuseDetectionServiceKeeperAnalysis:
    """Tests for analyze_keeper_behavior."""

    @pytest.fixture
    def mock_validator(self) -> MagicMock:
        """Create mock abuse validator."""
        return MagicMock()

    @pytest.fixture
    def mock_event_writer(self) -> MagicMock:
        """Create mock event writer."""
        writer = MagicMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def mock_halt_checker_operational(self) -> MagicMock:
        """Create mock halt checker."""
        checker = MagicMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.mark.asyncio
    async def test_analyze_keeper_behavior_normal(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test analyze_keeper_behavior for normal behavior."""
        mock_detector = MagicMock()
        mock_detector.get_keeper_override_frequency = AsyncMock(
            return_value=FrequencyData(
                override_count=5,
                time_window_days=90,
                daily_rate=0.055,
                deviation_from_baseline=0.5,  # Within 2 std
            )
        )

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        report = await service.analyze_keeper_behavior("keeper-1")
        assert report.is_outlier is False
        assert report.outlier_reason is None

    @pytest.mark.asyncio
    async def test_analyze_keeper_behavior_outlier_above(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test analyze_keeper_behavior for outlier above baseline."""
        mock_detector = MagicMock()
        mock_detector.get_keeper_override_frequency = AsyncMock(
            return_value=FrequencyData(
                override_count=50,
                time_window_days=90,
                daily_rate=0.55,
                deviation_from_baseline=3.5,  # > 2 std above
            )
        )

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        report = await service.analyze_keeper_behavior("keeper-1")
        assert report.is_outlier is True
        assert "above baseline" in report.outlier_reason


class TestWeeklyAnomalyReview:
    """Tests for run_weekly_anomaly_review (ADR-7)."""

    @pytest.fixture
    def mock_validator(self) -> MagicMock:
        """Create mock abuse validator."""
        return MagicMock()

    @pytest.fixture
    def mock_event_writer(self) -> MagicMock:
        """Create mock event writer."""
        writer = MagicMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def mock_halt_checker_operational(self) -> MagicMock:
        """Create mock halt checker."""
        checker = MagicMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def mock_halt_checker_halted(self) -> MagicMock:
        """Create mock halt checker that returns halted."""
        checker = MagicMock()
        checker.is_halted = AsyncMock(return_value=True)
        checker.get_halt_reason = AsyncMock(return_value="Test halt reason")
        return checker

    @pytest.mark.asyncio
    async def test_weekly_review_halt_check_first(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_halted: MagicMock,
    ) -> None:
        """Test weekly review HALT CHECK FIRST (CT-11)."""
        mock_detector = MagicMock()

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_halted,
        )

        with pytest.raises(SystemHaltedError, match="CT-11"):
            await service.run_weekly_anomaly_review()

    @pytest.mark.asyncio
    async def test_weekly_review_aggregates_all_detections(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test weekly review aggregates all detections (ADR-7)."""
        keeper_anomaly = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.8,
            affected_keepers=("keeper-1",),
            details="Frequency spike",
        )
        slow_burn_anomaly = AnomalyResult(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            confidence_score=0.75,
            affected_keepers=("keeper-2",),
            details="Slow burn",
        )

        mock_detector = MagicMock()
        mock_detector.detect_keeper_anomalies = AsyncMock(return_value=[keeper_anomaly])
        mock_detector.detect_slow_burn_erosion = AsyncMock(
            return_value=[slow_burn_anomaly]
        )

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        report = await service.run_weekly_anomaly_review()
        assert report.anomaly_count == 2
        assert len(report.anomalies_detected) == 2

    @pytest.mark.asyncio
    async def test_weekly_review_counts_confidence_levels(
        self,
        mock_validator: MagicMock,
        mock_event_writer: MagicMock,
        mock_halt_checker_operational: MagicMock,
    ) -> None:
        """Test weekly review counts high/medium confidence anomalies."""
        high_confidence = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.95,  # >= 0.9 = high
            affected_keepers=("keeper-1",),
            details="High confidence",
        )
        medium_confidence = AnomalyResult(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            confidence_score=0.8,  # 0.7 <= x < 0.9 = medium
            affected_keepers=("keeper-2",),
            details="Medium confidence",
        )

        mock_detector = MagicMock()
        mock_detector.detect_keeper_anomalies = AsyncMock(
            return_value=[high_confidence]
        )
        mock_detector.detect_slow_burn_erosion = AsyncMock(
            return_value=[medium_confidence]
        )

        service = OverrideAbuseDetectionService(
            abuse_validator=mock_validator,
            anomaly_detector=mock_detector,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_operational,
        )

        report = await service.run_weekly_anomaly_review()
        assert report.high_confidence_count == 1
        assert report.medium_confidence_count == 1
