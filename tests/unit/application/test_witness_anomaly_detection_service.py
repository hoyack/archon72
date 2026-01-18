"""Unit tests for witness anomaly detection service (Story 6.6, FR116)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.witness_anomaly_detector import (
    PairExclusion,
    WitnessAnomalyResult,
)
from src.application.services.witness_anomaly_detection_service import (
    CHI_SQUARE_P001,
    CHI_SQUARE_P01,
    CHI_SQUARE_P05,
    CONFIDENCE_THRESHOLD,
    DEFAULT_EXCLUSION_HOURS,
    WitnessAnomalyDetectionService,
    calculate_chi_square,
    calculate_expected_occurrence,
    chi_square_to_confidence,
)
from src.domain.errors.witness_anomaly import AnomalyScanError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.witness_anomaly import (
    ReviewStatus,
    WitnessAnomalyEventPayload,
    WitnessAnomalyType,
)


class TestCalculateExpectedOccurrence:
    """Tests for calculate_expected_occurrence function."""

    def test_with_standard_pool(self) -> None:
        """Test expected occurrence with standard pool size."""
        # 15 witnesses, 100 events
        # Total pairs = 15 * 14 / 2 = 105
        # Expected per pair = 100 / 105 ≈ 0.952
        result = calculate_expected_occurrence(pool_size=15, events_count=100)
        assert abs(result - 0.952) < 0.01

    def test_with_small_pool(self) -> None:
        """Test expected occurrence with minimum pool."""
        # 2 witnesses, 10 events
        # Total pairs = 2 * 1 / 2 = 1
        # Expected per pair = 10 / 1 = 10
        result = calculate_expected_occurrence(pool_size=2, events_count=10)
        assert result == 10.0

    def test_with_single_witness(self) -> None:
        """Test expected occurrence with single witness returns 0."""
        result = calculate_expected_occurrence(pool_size=1, events_count=100)
        assert result == 0.0

    def test_with_zero_pool(self) -> None:
        """Test expected occurrence with zero witnesses returns 0."""
        result = calculate_expected_occurrence(pool_size=0, events_count=100)
        assert result == 0.0

    def test_with_zero_events(self) -> None:
        """Test expected occurrence with zero events returns 0."""
        result = calculate_expected_occurrence(pool_size=15, events_count=0)
        assert result == 0.0


class TestCalculateChiSquare:
    """Tests for calculate_chi_square function."""

    def test_significant_deviation(self) -> None:
        """Test chi-square with significant deviation."""
        # Observed = 15, Expected = 5
        # Chi-square = (15-5)^2 / 5 = 100 / 5 = 20
        result = calculate_chi_square(observed=15, expected=5.0)
        assert result == 20.0

    def test_no_deviation(self) -> None:
        """Test chi-square with no deviation."""
        result = calculate_chi_square(observed=10, expected=10.0)
        assert result == 0.0

    def test_small_deviation(self) -> None:
        """Test chi-square with small deviation."""
        # Observed = 6, Expected = 5
        # Chi-square = (6-5)^2 / 5 = 1 / 5 = 0.2
        result = calculate_chi_square(observed=6, expected=5.0)
        assert result == 0.2

    def test_zero_expected_with_observed(self) -> None:
        """Test chi-square with zero expected but non-zero observed."""
        result = calculate_chi_square(observed=5, expected=0.0)
        assert result == float("inf")

    def test_zero_expected_zero_observed(self) -> None:
        """Test chi-square with zero expected and zero observed."""
        result = calculate_chi_square(observed=0, expected=0.0)
        assert result == 0.0


class TestChiSquareToConfidence:
    """Tests for chi_square_to_confidence function."""

    def test_below_threshold(self) -> None:
        """Test confidence for chi-square below p=0.05 threshold."""
        result = chi_square_to_confidence(2.0)
        assert 0.0 < result < 0.5

    def test_at_p05_threshold(self) -> None:
        """Test confidence at p=0.05 threshold."""
        result = chi_square_to_confidence(CHI_SQUARE_P05)
        assert result == 0.5

    def test_between_p05_and_p01(self) -> None:
        """Test confidence between p=0.05 and p=0.01."""
        result = chi_square_to_confidence(5.0)
        assert 0.5 < result < 0.7

    def test_at_p01_threshold(self) -> None:
        """Test confidence at p=0.01 threshold."""
        result = chi_square_to_confidence(CHI_SQUARE_P01)
        assert abs(result - 0.7) < 0.01

    def test_between_p01_and_p001(self) -> None:
        """Test confidence between p=0.01 and p=0.001."""
        result = chi_square_to_confidence(8.0)
        assert 0.7 < result < 0.9

    def test_at_p001_threshold(self) -> None:
        """Test confidence at p=0.001 threshold."""
        result = chi_square_to_confidence(CHI_SQUARE_P001)
        assert abs(result - 0.9) < 0.01

    def test_high_chi_square(self) -> None:
        """Test confidence for very high chi-square."""
        result = chi_square_to_confidence(50.0)
        assert result >= 0.9
        assert result <= 1.0

    def test_very_high_chi_square_capped(self) -> None:
        """Test confidence is capped at 1.0 for extreme values."""
        result = chi_square_to_confidence(1000.0)
        assert result == 1.0


class TestWitnessAnomalyDetectionServiceInit:
    """Tests for WitnessAnomalyDetectionService initialization."""

    def test_init_with_defaults(self) -> None:
        """Test service initialization with default confidence threshold."""
        halt_checker = MagicMock()
        anomaly_detector = MagicMock()

        service = WitnessAnomalyDetectionService(
            halt_checker=halt_checker,
            anomaly_detector=anomaly_detector,
        )

        assert service._confidence_threshold == CONFIDENCE_THRESHOLD

    def test_init_with_custom_threshold(self) -> None:
        """Test service initialization with custom confidence threshold."""
        halt_checker = MagicMock()
        anomaly_detector = MagicMock()

        service = WitnessAnomalyDetectionService(
            halt_checker=halt_checker,
            anomaly_detector=anomaly_detector,
            confidence_threshold=0.9,
        )

        assert service._confidence_threshold == 0.9


class TestRunAnomalyScan:
    """Tests for run_anomaly_scan method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_anomaly_detector(self) -> AsyncMock:
        """Create mock anomaly detector."""
        detector = AsyncMock()
        detector.analyze_co_occurrence.return_value = []
        detector.analyze_unavailability_patterns.return_value = []
        return detector

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.run_anomaly_scan()

        assert "System halted" in str(exc_info.value)
        mock_halt_checker.is_halted.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_anomalies(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test returns empty list when no anomalies detected."""
        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        results = await service.run_anomaly_scan()

        assert results == []

    @pytest.mark.asyncio
    async def test_filters_by_confidence_threshold(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test filters anomalies below confidence threshold."""
        low_confidence = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.5,  # Below threshold
            affected_witnesses=("witness1", "witness2"),
            occurrence_count=10,
            expected_count=5.0,
            details="Low confidence",
        )
        high_confidence = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.85,  # Above threshold
            affected_witnesses=("witness3", "witness4"),
            occurrence_count=20,
            expected_count=5.0,
            details="High confidence",
        )
        mock_anomaly_detector.analyze_co_occurrence.return_value = [
            low_confidence,
            high_confidence,
        ]

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        results = await service.run_anomaly_scan()

        assert len(results) == 1
        assert results[0].confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_combines_co_occurrence_and_unavailability(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test combines both analysis types."""
        co_occurrence = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.8,
            affected_witnesses=("witness1", "witness2"),
            occurrence_count=15,
            expected_count=5.0,
            details="Co-occurrence",
        )
        unavailability = WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.UNAVAILABILITY_PATTERN,
            confidence_score=0.75,
            affected_witnesses=("witness3",),
            occurrence_count=10,
            expected_count=2.0,
            details="Unavailability",
        )
        mock_anomaly_detector.analyze_co_occurrence.return_value = [co_occurrence]
        mock_anomaly_detector.analyze_unavailability_patterns.return_value = [
            unavailability
        ]

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        results = await service.run_anomaly_scan()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_sorts_by_confidence_descending(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test results are sorted by confidence (highest first)."""
        anomalies = [
            WitnessAnomalyResult(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                confidence_score=0.75,
                affected_witnesses=("w1", "w2"),
                occurrence_count=10,
                expected_count=5.0,
                details="Medium",
            ),
            WitnessAnomalyResult(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                confidence_score=0.95,
                affected_witnesses=("w3", "w4"),
                occurrence_count=20,
                expected_count=5.0,
                details="High",
            ),
            WitnessAnomalyResult(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                confidence_score=0.8,
                affected_witnesses=("w5", "w6"),
                occurrence_count=15,
                expected_count=5.0,
                details="Medium-high",
            ),
        ]
        mock_anomaly_detector.analyze_co_occurrence.return_value = anomalies

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        results = await service.run_anomaly_scan()

        assert results[0].confidence_score == 0.95
        assert results[1].confidence_score == 0.8
        assert results[2].confidence_score == 0.75

    @pytest.mark.asyncio
    async def test_uses_custom_window(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test uses custom window hours."""
        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        await service.run_anomaly_scan(window_hours=24)

        mock_anomaly_detector.analyze_co_occurrence.assert_called_once_with(24)
        mock_anomaly_detector.analyze_unavailability_patterns.assert_called_once_with(
            24
        )

    @pytest.mark.asyncio
    async def test_wraps_analysis_exception(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test wraps analysis exceptions in AnomalyScanError."""
        mock_anomaly_detector.analyze_co_occurrence.side_effect = RuntimeError(
            "Database error"
        )

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        with pytest.raises(AnomalyScanError) as exc_info:
            await service.run_anomaly_scan()

        assert "Database error" in str(exc_info.value)


class TestCheckPairForAnomaly:
    """Tests for check_pair_for_anomaly method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_anomaly_detector(self) -> AsyncMock:
        """Create mock anomaly detector."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        with pytest.raises(SystemHaltedError):
            await service.check_pair_for_anomaly("witness1:witness2")

    @pytest.mark.asyncio
    async def test_returns_true_for_excluded_pair(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test returns True for excluded pair."""
        mock_anomaly_detector.is_pair_excluded.return_value = True

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        result = await service.check_pair_for_anomaly("witness1:witness2")

        assert result is True
        mock_anomaly_detector.is_pair_excluded.assert_called_once_with(
            "witness1:witness2"
        )

    @pytest.mark.asyncio
    async def test_returns_false_for_non_excluded_pair(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test returns False for non-excluded pair."""
        mock_anomaly_detector.is_pair_excluded.return_value = False

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        result = await service.check_pair_for_anomaly("witness1:witness2")

        assert result is False


class TestExcludeSuspiciousPair:
    """Tests for exclude_suspicious_pair method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_anomaly_detector(self) -> AsyncMock:
        """Create mock anomaly detector."""
        detector = AsyncMock()
        detector.exclude_pair.return_value = None
        return detector

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        with pytest.raises(SystemHaltedError):
            await service.exclude_suspicious_pair("witness1:witness2", confidence=0.8)

    @pytest.mark.asyncio
    async def test_excludes_pair(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test excludes pair via anomaly detector."""
        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        await service.exclude_suspicious_pair(
            "witness1:witness2", confidence=0.8, reason="Test"
        )

        mock_anomaly_detector.exclude_pair.assert_called_once_with(
            pair_key="witness1:witness2",
            duration_hours=DEFAULT_EXCLUSION_HOURS,
            reason="Test",
            confidence=0.8,
        )

    @pytest.mark.asyncio
    async def test_returns_event_payload(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test returns WitnessAnomalyEventPayload."""
        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        result = await service.exclude_suspicious_pair(
            "witness1:witness2", confidence=0.85, reason="Test exclusion"
        )

        assert isinstance(result, WitnessAnomalyEventPayload)
        assert result.anomaly_type == WitnessAnomalyType.CO_OCCURRENCE
        assert result.affected_witnesses == ("witness1", "witness2")
        assert result.confidence_score == 0.85
        assert result.review_status == ReviewStatus.PENDING
        assert "Test exclusion" in result.details

    @pytest.mark.asyncio
    async def test_uses_custom_duration(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test uses custom duration hours."""
        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        await service.exclude_suspicious_pair(
            "witness1:witness2", confidence=0.8, duration_hours=48
        )

        mock_anomaly_detector.exclude_pair.assert_called_once()
        call_kwargs = mock_anomaly_detector.exclude_pair.call_args.kwargs
        assert call_kwargs["duration_hours"] == 48


class TestClearPairExclusion:
    """Tests for clear_pair_exclusion method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_anomaly_detector(self) -> AsyncMock:
        """Create mock anomaly detector."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        with pytest.raises(SystemHaltedError):
            await service.clear_pair_exclusion("witness1:witness2")

    @pytest.mark.asyncio
    async def test_clears_exclusion(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test clears exclusion via anomaly detector."""
        mock_anomaly_detector.clear_pair_exclusion.return_value = True

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        result = await service.clear_pair_exclusion("witness1:witness2")

        assert result is True
        mock_anomaly_detector.clear_pair_exclusion.assert_called_once_with(
            "witness1:witness2"
        )


class TestGetExclusionDetails:
    """Tests for get_exclusion_details method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_anomaly_detector(self) -> AsyncMock:
        """Create mock anomaly detector."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_exclusion_details("witness1:witness2")

    @pytest.mark.asyncio
    async def test_returns_exclusion_details(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test returns PairExclusion when pair is excluded."""
        now = datetime.now(timezone.utc)
        exclusion = PairExclusion(
            pair_key="witness1:witness2",
            excluded_at=now,
            excluded_until=now,
            reason="Test",
            confidence=0.8,
        )
        mock_anomaly_detector.get_exclusion_details.return_value = exclusion

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        result = await service.get_exclusion_details("witness1:witness2")

        assert result == exclusion

    @pytest.mark.asyncio
    async def test_returns_none_when_not_excluded(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test returns None when pair is not excluded."""
        mock_anomaly_detector.get_exclusion_details.return_value = None

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        result = await service.get_exclusion_details("witness1:witness2")

        assert result is None


class TestGetAllExcludedPairs:
    """Tests for get_all_excluded_pairs method."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock halt checker."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_anomaly_detector(self) -> AsyncMock:
        """Create mock anomaly detector."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test CT-11: HALT CHECK FIRST."""
        mock_halt_checker.is_halted.return_value = True

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_all_excluded_pairs()

    @pytest.mark.asyncio
    async def test_returns_excluded_pairs(
        self, mock_halt_checker: AsyncMock, mock_anomaly_detector: AsyncMock
    ) -> None:
        """Test returns set of excluded pair keys."""
        mock_anomaly_detector.get_excluded_pairs.return_value = {
            "witness1:witness2",
            "witness3:witness4",
        }

        service = WitnessAnomalyDetectionService(
            halt_checker=mock_halt_checker,
            anomaly_detector=mock_anomaly_detector,
        )

        result = await service.get_all_excluded_pairs()

        assert result == {"witness1:witness2", "witness3:witness4"}
