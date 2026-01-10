"""Unit tests for anomaly detector port (Story 5.9, FP-3, ADR-7).

Tests the AnomalyDetectorProtocol interface, AnomalyResult, and FrequencyData.
"""

from __future__ import annotations

import pytest

from src.application.ports.anomaly_detector import (
    AnomalyDetectorProtocol,
    AnomalyResult,
    FrequencyData,
)
from src.domain.events.override_abuse import AnomalyType
from src.infrastructure.stubs.anomaly_detector_stub import AnomalyDetectorStub


class TestFrequencyData:
    """Tests for FrequencyData dataclass."""

    def test_create_with_required_fields(self) -> None:
        """Test FrequencyData creation with all fields."""
        freq = FrequencyData(
            override_count=10,
            time_window_days=90,
            daily_rate=0.11,
            deviation_from_baseline=1.5,
        )
        assert freq.override_count == 10
        assert freq.time_window_days == 90
        assert freq.daily_rate == 0.11
        assert freq.deviation_from_baseline == 1.5

    def test_data_is_frozen(self) -> None:
        """Test FrequencyData is immutable."""
        freq = FrequencyData(
            override_count=10,
            time_window_days=90,
            daily_rate=0.11,
            deviation_from_baseline=1.5,
        )
        with pytest.raises(AttributeError):
            freq.override_count = 20  # type: ignore[misc]

    def test_negative_deviation_allowed(self) -> None:
        """Test negative deviation (below baseline) is valid."""
        freq = FrequencyData(
            override_count=0,
            time_window_days=90,
            daily_rate=0.0,
            deviation_from_baseline=-1.5,
        )
        assert freq.deviation_from_baseline == -1.5


class TestAnomalyResult:
    """Tests for AnomalyResult dataclass."""

    def test_create_with_required_fields(self) -> None:
        """Test AnomalyResult creation with all fields."""
        result = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.85,
            affected_keepers=("keeper-1", "keeper-2"),
            details="Frequency spike detected",
        )
        assert result.anomaly_type == AnomalyType.FREQUENCY_SPIKE
        assert result.confidence_score == 0.85
        assert result.affected_keepers == ("keeper-1", "keeper-2")
        assert result.details == "Frequency spike detected"

    def test_result_is_frozen(self) -> None:
        """Test AnomalyResult is immutable."""
        result = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.85,
            affected_keepers=("keeper-1",),
            details="test",
        )
        with pytest.raises(AttributeError):
            result.confidence_score = 0.9  # type: ignore[misc]

    def test_confidence_score_validation_lower_bound(self) -> None:
        """Test confidence score cannot be below 0.0."""
        with pytest.raises(ValueError, match="confidence_score must be between"):
            AnomalyResult(
                anomaly_type=AnomalyType.FREQUENCY_SPIKE,
                confidence_score=-0.1,
                affected_keepers=("keeper-1",),
                details="test",
            )

    def test_confidence_score_validation_upper_bound(self) -> None:
        """Test confidence score cannot exceed 1.0."""
        with pytest.raises(ValueError, match="confidence_score must be between"):
            AnomalyResult(
                anomaly_type=AnomalyType.FREQUENCY_SPIKE,
                confidence_score=1.1,
                affected_keepers=("keeper-1",),
                details="test",
            )

    def test_confidence_score_valid_at_boundaries(self) -> None:
        """Test confidence score valid at 0.0 and 1.0."""
        result_zero = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.0,
            affected_keepers=("keeper-1",),
            details="test",
        )
        assert result_zero.confidence_score == 0.0

        result_one = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=1.0,
            affected_keepers=("keeper-1",),
            details="test",
        )
        assert result_one.confidence_score == 1.0


class TestAnomalyDetectorProtocol:
    """Tests for AnomalyDetectorProtocol using stub implementation."""

    @pytest.fixture
    def detector(self) -> AnomalyDetectorStub:
        """Create a fresh detector stub for each test."""
        return AnomalyDetectorStub()

    @pytest.mark.asyncio
    async def test_stub_implements_protocol(
        self,
        detector: AnomalyDetectorStub,
    ) -> None:
        """Test stub implements AnomalyDetectorProtocol."""
        assert hasattr(detector, "detect_keeper_anomalies")
        assert hasattr(detector, "detect_coordinated_patterns")
        assert hasattr(detector, "get_keeper_override_frequency")
        assert hasattr(detector, "detect_slow_burn_erosion")

    @pytest.mark.asyncio
    async def test_detect_keeper_anomalies_empty_by_default(
        self,
        detector: AnomalyDetectorStub,
    ) -> None:
        """Test detect_keeper_anomalies returns empty list by default."""
        results = await detector.detect_keeper_anomalies(time_window_days=90)
        assert results == []

    @pytest.mark.asyncio
    async def test_detect_keeper_anomalies_with_injected(
        self,
        detector: AnomalyDetectorStub,
    ) -> None:
        """Test detect_keeper_anomalies returns injected anomalies."""
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.85,
            affected_keepers=("keeper-1",),
            details="Test anomaly",
        )
        detector.set_detected_anomalies([anomaly])

        results = await detector.detect_keeper_anomalies(time_window_days=90)
        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.FREQUENCY_SPIKE

    @pytest.mark.asyncio
    async def test_get_keeper_override_frequency_default(
        self,
        detector: AnomalyDetectorStub,
    ) -> None:
        """Test get_keeper_override_frequency returns default for unknown keeper."""
        freq = await detector.get_keeper_override_frequency(
            keeper_id="unknown-keeper",
            time_window_days=90,
        )
        assert freq.override_count == 0
        assert freq.deviation_from_baseline == 0.0

    @pytest.mark.asyncio
    async def test_get_keeper_override_frequency_configured(
        self,
        detector: AnomalyDetectorStub,
    ) -> None:
        """Test get_keeper_override_frequency returns configured data."""
        detector.set_keeper_frequency(
            "keeper-1",
            FrequencyData(
                override_count=50,
                time_window_days=90,
                daily_rate=0.55,
                deviation_from_baseline=3.5,
            ),
        )

        freq = await detector.get_keeper_override_frequency(
            keeper_id="keeper-1",
            time_window_days=90,
        )
        assert freq.override_count == 50
        assert freq.deviation_from_baseline == 3.5

    @pytest.mark.asyncio
    async def test_detect_slow_burn_erosion_empty_by_default(
        self,
        detector: AnomalyDetectorStub,
    ) -> None:
        """Test detect_slow_burn_erosion returns empty list by default."""
        results = await detector.detect_slow_burn_erosion(
            time_window_days=365,
            threshold=0.1,
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_detect_slow_burn_erosion_with_injected(
        self,
        detector: AnomalyDetectorStub,
    ) -> None:
        """Test detect_slow_burn_erosion returns injected anomalies (CT-9)."""
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            confidence_score=0.75,
            affected_keepers=("keeper-1", "keeper-2"),
            details="Slow burn erosion detected",
        )
        detector.set_slow_burn_anomalies([anomaly])

        results = await detector.detect_slow_burn_erosion(
            time_window_days=365,
            threshold=0.1,
        )
        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.SLOW_BURN_EROSION

    @pytest.mark.asyncio
    async def test_detect_coordinated_patterns_empty_by_default(
        self,
        detector: AnomalyDetectorStub,
    ) -> None:
        """Test detect_coordinated_patterns returns empty list by default."""
        results = await detector.detect_coordinated_patterns(
            keeper_ids=["keeper-1", "keeper-2"],
            time_window_days=90,
        )
        assert results == []
