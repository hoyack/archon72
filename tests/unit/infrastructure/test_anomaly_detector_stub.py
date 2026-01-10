"""Unit tests for AnomalyDetectorStub (Story 5.9, FP-3, ADR-7).

Tests validate:
- AC3: FP-3 - Statistical pattern detection
- AC4: ADR-7 - Aggregate anomaly detection ceremony support
- CT-9: Patient attacker detection
- Stub behavior for test isolation
"""

from __future__ import annotations

import pytest

from src.application.ports.anomaly_detector import AnomalyResult, FrequencyData
from src.domain.events.override_abuse import AnomalyType
from src.infrastructure.stubs.anomaly_detector_stub import (
    DEFAULT_BASELINE_DAILY_RATE,
    DEFAULT_OVERRIDE_COUNT,
    AnomalyDetectorStub,
)


class TestAnomalyDetectorStubInitialization:
    """Tests for stub initialization."""

    def test_stub_initializes_with_empty_state(self) -> None:
        """Stub should initialize with no anomalies configured."""
        stub = AnomalyDetectorStub()

        assert len(stub._detected_anomalies) == 0
        assert len(stub._coordinated_anomalies) == 0
        assert len(stub._slow_burn_anomalies) == 0
        assert len(stub._keeper_frequencies) == 0

    def test_stub_has_default_frequency(self) -> None:
        """Stub should have default frequency data configured."""
        stub = AnomalyDetectorStub()

        assert stub._default_frequency.override_count == DEFAULT_OVERRIDE_COUNT
        assert stub._default_frequency.daily_rate == DEFAULT_BASELINE_DAILY_RATE
        assert stub._default_frequency.deviation_from_baseline == 0.0


class TestDetectKeeperAnomalies:
    """Tests for detect_keeper_anomalies method."""

    @pytest.fixture
    def stub(self) -> AnomalyDetectorStub:
        """Create fresh stub for each test."""
        return AnomalyDetectorStub()

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return empty list when no anomalies configured."""
        results = await stub.detect_keeper_anomalies(90)
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_configured_anomalies(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return configured anomalies."""
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.85,
            affected_keepers=("keeper-1",),
            details="Test anomaly",
        )
        stub.set_detected_anomalies([anomaly])

        results = await stub.detect_keeper_anomalies(90)

        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.FREQUENCY_SPIKE

    @pytest.mark.asyncio
    async def test_returns_copy_not_reference(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return copy of list to prevent mutation."""
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.85,
            affected_keepers=("keeper-1",),
            details="Test anomaly",
        )
        stub.set_detected_anomalies([anomaly])

        results = await stub.detect_keeper_anomalies(90)
        results.clear()  # Mutate returned list

        # Original should be unchanged
        results2 = await stub.detect_keeper_anomalies(90)
        assert len(results2) == 1


class TestDetectCoordinatedPatterns:
    """Tests for detect_coordinated_patterns method."""

    @pytest.fixture
    def stub(self) -> AnomalyDetectorStub:
        """Create fresh stub for each test."""
        return AnomalyDetectorStub()

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return empty list when no anomalies configured."""
        results = await stub.detect_coordinated_patterns(["k1", "k2"], 90)
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_configured_coordinated_anomalies(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return configured coordinated anomalies."""
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.COORDINATED_OVERRIDES,
            confidence_score=0.8,
            affected_keepers=("keeper-1", "keeper-2"),
            details="Coordinated pattern",
        )
        stub.set_coordinated_anomalies([anomaly])

        results = await stub.detect_coordinated_patterns(["keeper-1", "keeper-2"], 90)

        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.COORDINATED_OVERRIDES

    @pytest.mark.asyncio
    async def test_filters_by_keeper_ids_when_matches_exist(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should filter to anomalies affecting specified keepers."""
        anomaly1 = AnomalyResult(
            anomaly_type=AnomalyType.COORDINATED_OVERRIDES,
            confidence_score=0.8,
            affected_keepers=("keeper-1", "keeper-2"),
            details="Pattern 1",
        )
        anomaly2 = AnomalyResult(
            anomaly_type=AnomalyType.COORDINATED_OVERRIDES,
            confidence_score=0.7,
            affected_keepers=("keeper-3", "keeper-4"),
            details="Pattern 2",
        )
        stub.set_coordinated_anomalies([anomaly1, anomaly2])

        # Only request keeper-1
        results = await stub.detect_coordinated_patterns(["keeper-1"], 90)

        assert len(results) == 1
        assert "keeper-1" in results[0].affected_keepers


class TestDetectSlowBurnErosion:
    """Tests for detect_slow_burn_erosion method (CT-9, ADR-7)."""

    @pytest.fixture
    def stub(self) -> AnomalyDetectorStub:
        """Create fresh stub for each test."""
        return AnomalyDetectorStub()

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return empty list when no anomalies configured."""
        results = await stub.detect_slow_burn_erosion(365, 0.1)
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_configured_slow_burn_anomalies(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return configured slow-burn anomalies."""
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            confidence_score=0.75,
            affected_keepers=("keeper-1",),
            details="Slow burn detected",
        )
        stub.set_slow_burn_anomalies([anomaly])

        results = await stub.detect_slow_burn_erosion(365, 0.1)

        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.SLOW_BURN_EROSION


class TestGetKeeperOverrideFrequency:
    """Tests for get_keeper_override_frequency method."""

    @pytest.fixture
    def stub(self) -> AnomalyDetectorStub:
        """Create fresh stub for each test."""
        return AnomalyDetectorStub()

    @pytest.mark.asyncio
    async def test_returns_default_for_unknown_keeper(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return default frequency for unknown keepers."""
        freq = await stub.get_keeper_override_frequency("unknown-keeper", 90)

        assert freq.override_count == DEFAULT_OVERRIDE_COUNT
        assert freq.daily_rate == DEFAULT_BASELINE_DAILY_RATE
        assert freq.deviation_from_baseline == 0.0
        assert freq.time_window_days == 90  # Uses requested window

    @pytest.mark.asyncio
    async def test_returns_configured_frequency_for_keeper(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should return configured frequency for known keepers."""
        custom_freq = FrequencyData(
            override_count=50,
            time_window_days=90,
            daily_rate=0.55,
            deviation_from_baseline=3.0,
        )
        stub.set_keeper_frequency("keeper-1", custom_freq)

        freq = await stub.get_keeper_override_frequency("keeper-1", 90)

        assert freq.override_count == 50
        assert freq.daily_rate == 0.55
        assert freq.deviation_from_baseline == 3.0

    @pytest.mark.asyncio
    async def test_updates_time_window_in_response(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should update time window to match request."""
        custom_freq = FrequencyData(
            override_count=50,
            time_window_days=90,
            daily_rate=0.55,
            deviation_from_baseline=3.0,
        )
        stub.set_keeper_frequency("keeper-1", custom_freq)

        # Request different time window
        freq = await stub.get_keeper_override_frequency("keeper-1", 30)

        assert freq.time_window_days == 30


class TestInjectionHelpers:
    """Tests for helper injection methods."""

    @pytest.fixture
    def stub(self) -> AnomalyDetectorStub:
        """Create fresh stub for each test."""
        return AnomalyDetectorStub()

    @pytest.mark.asyncio
    async def test_inject_frequency_spike(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should inject frequency spike anomaly and set keeper frequency."""
        stub.inject_frequency_spike(
            keeper_id="keeper-1",
            override_count=50,
            deviation=3.5,
            confidence=0.85,
        )

        # Check anomaly was added
        anomalies = await stub.detect_keeper_anomalies(90)
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.FREQUENCY_SPIKE
        assert anomalies[0].confidence_score == 0.85
        assert "keeper-1" in anomalies[0].affected_keepers

        # Check frequency was set
        freq = await stub.get_keeper_override_frequency("keeper-1", 90)
        assert freq.override_count == 50
        assert freq.deviation_from_baseline == 3.5

    @pytest.mark.asyncio
    async def test_inject_coordinated_pattern(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should inject coordinated pattern anomaly."""
        stub.inject_coordinated_pattern(
            keeper_ids=("keeper-1", "keeper-2", "keeper-3"),
            confidence=0.8,
        )

        anomalies = await stub.detect_coordinated_patterns(["keeper-1"], 90)

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.COORDINATED_OVERRIDES
        assert anomalies[0].confidence_score == 0.8
        assert len(anomalies[0].affected_keepers) == 3

    @pytest.mark.asyncio
    async def test_inject_slow_burn_erosion(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should inject slow-burn erosion anomaly."""
        stub.inject_slow_burn_erosion(
            keeper_ids=("keeper-1",),
            confidence=0.75,
            growth_rate=0.15,
        )

        anomalies = await stub.detect_slow_burn_erosion(365, 0.1)

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.SLOW_BURN_EROSION
        assert anomalies[0].confidence_score == 0.75
        assert "15%" in anomalies[0].details


class TestClearMethod:
    """Tests for clear method and test isolation."""

    @pytest.fixture
    def stub(self) -> AnomalyDetectorStub:
        """Create fresh stub for each test."""
        return AnomalyDetectorStub()

    @pytest.mark.asyncio
    async def test_clear_removes_all_anomalies(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Clear should remove all configured anomalies."""
        stub.inject_frequency_spike("keeper-1", 50, 3.0, 0.8)
        stub.inject_coordinated_pattern(("k1", "k2"), 0.7)
        stub.inject_slow_burn_erosion(("k3",), 0.6, 0.1)

        stub.clear()

        assert await stub.detect_keeper_anomalies(90) == []
        assert await stub.detect_coordinated_patterns(["k1"], 90) == []
        assert await stub.detect_slow_burn_erosion(365, 0.1) == []

    @pytest.mark.asyncio
    async def test_clear_removes_keeper_frequencies(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Clear should remove configured keeper frequencies."""
        stub.set_keeper_frequency(
            "keeper-1",
            FrequencyData(
                override_count=100,
                time_window_days=90,
                daily_rate=1.1,
                deviation_from_baseline=5.0,
            ),
        )

        stub.clear()

        freq = await stub.get_keeper_override_frequency("keeper-1", 90)
        assert freq.override_count == DEFAULT_OVERRIDE_COUNT
        assert freq.daily_rate == DEFAULT_BASELINE_DAILY_RATE

    @pytest.mark.asyncio
    async def test_clear_resets_default_frequency(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Clear should reset default frequency to original values."""
        stub.set_default_frequency(
            FrequencyData(
                override_count=999,
                time_window_days=90,
                daily_rate=11.0,
                deviation_from_baseline=10.0,
            ),
        )

        stub.clear()

        freq = await stub.get_keeper_override_frequency("any-keeper", 90)
        assert freq.override_count == DEFAULT_OVERRIDE_COUNT
        assert freq.daily_rate == DEFAULT_BASELINE_DAILY_RATE


class TestDefaultConstants:
    """Tests for module-level default constants."""

    def test_default_baseline_daily_rate_is_positive(self) -> None:
        """DEFAULT_BASELINE_DAILY_RATE should be positive."""
        assert DEFAULT_BASELINE_DAILY_RATE > 0

    def test_default_baseline_daily_rate_is_reasonable(self) -> None:
        """DEFAULT_BASELINE_DAILY_RATE should be a reasonable low value."""
        # 0.1 overrides per day = about 3 per month on average
        assert DEFAULT_BASELINE_DAILY_RATE <= 1.0

    def test_default_override_count_is_zero(self) -> None:
        """DEFAULT_OVERRIDE_COUNT should be zero for testing fresh state."""
        assert DEFAULT_OVERRIDE_COUNT == 0


class TestMultipleAnomalyTypes:
    """Tests for handling multiple anomaly types together."""

    @pytest.fixture
    def stub(self) -> AnomalyDetectorStub:
        """Create fresh stub for each test."""
        return AnomalyDetectorStub()

    @pytest.mark.asyncio
    async def test_multiple_frequency_spikes(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Should handle multiple frequency spike anomalies."""
        stub.inject_frequency_spike("keeper-1", 50, 3.0, 0.8)
        stub.inject_frequency_spike("keeper-2", 75, 4.5, 0.9)

        anomalies = await stub.detect_keeper_anomalies(90)

        assert len(anomalies) == 2
        keeper_ids = {a.affected_keepers[0] for a in anomalies}
        assert keeper_ids == {"keeper-1", "keeper-2"}

    @pytest.mark.asyncio
    async def test_all_anomaly_types_independent(
        self,
        stub: AnomalyDetectorStub,
    ) -> None:
        """Different anomaly types should be stored independently."""
        stub.inject_frequency_spike("k1", 50, 3.0, 0.8)
        stub.inject_coordinated_pattern(("k2", "k3"), 0.7)
        stub.inject_slow_burn_erosion(("k4",), 0.6, 0.1)

        # Each method should return only its type
        freq_anomalies = await stub.detect_keeper_anomalies(90)
        coord_anomalies = await stub.detect_coordinated_patterns(["k2", "k3"], 90)
        slow_anomalies = await stub.detect_slow_burn_erosion(365, 0.1)

        assert all(a.anomaly_type == AnomalyType.FREQUENCY_SPIKE for a in freq_anomalies)
        assert all(a.anomaly_type == AnomalyType.COORDINATED_OVERRIDES for a in coord_anomalies)
        assert all(a.anomaly_type == AnomalyType.SLOW_BURN_EROSION for a in slow_anomalies)
