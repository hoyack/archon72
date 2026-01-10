"""Anomaly Detector Stub - Test implementation (Story 5.9, FP-3, ADR-7).

This stub implements the AnomalyDetectorProtocol for testing purposes.
It provides configurable anomaly detection behavior for unit and integration tests.

Constitutional Constraints:
- CT-9: Attackers are patient - aggregate erosion must be detected
- FP-3: Patient attacker detection needs ADR-7 (Aggregate Anomaly Detection)
- CT-11: Silent failure destroys legitimacy -> All anomalies must be logged
- CT-12: Witnessing creates accountability -> Anomaly events MUST be witnessed
"""

from __future__ import annotations

from src.application.ports.anomaly_detector import (
    AnomalyDetectorProtocol,
    AnomalyResult,
    FrequencyData,
)
from src.domain.events.override_abuse import AnomalyType


# Default baseline values for testing
DEFAULT_BASELINE_DAILY_RATE: float = 0.1  # 0.1 overrides per day average
DEFAULT_OVERRIDE_COUNT: int = 0


class AnomalyDetectorStub(AnomalyDetectorProtocol):
    """Stub implementation of AnomalyDetectorProtocol for testing.

    This stub provides configurable anomaly detection behavior:
    - Inject detected anomalies for specific test scenarios
    - Configure keeper frequency data
    - Configure slow-burn erosion detection results
    - Clear methods for test isolation

    Usage:
        detector = AnomalyDetectorStub()

        # Inject anomaly for test
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=0.85,
            affected_keepers=("keeper-1",),
            details="Frequency spike detected",
        )
        detector.set_detected_anomalies([anomaly])

        # Run detection
        results = await detector.detect_keeper_anomalies(90)
        assert len(results) == 1

        # Clean up for next test
        detector.clear()
    """

    def __init__(self) -> None:
        """Initialize the stub with empty state."""
        self._detected_anomalies: list[AnomalyResult] = []
        self._coordinated_anomalies: list[AnomalyResult] = []
        self._slow_burn_anomalies: list[AnomalyResult] = []
        self._keeper_frequencies: dict[str, FrequencyData] = {}
        self._default_frequency = FrequencyData(
            override_count=DEFAULT_OVERRIDE_COUNT,
            time_window_days=90,
            daily_rate=DEFAULT_BASELINE_DAILY_RATE,
            deviation_from_baseline=0.0,
        )

    def set_detected_anomalies(self, anomalies: list[AnomalyResult]) -> None:
        """Set anomalies to be returned by detect_keeper_anomalies.

        Args:
            anomalies: List of anomalies to inject.
        """
        self._detected_anomalies = list(anomalies)

    def set_coordinated_anomalies(self, anomalies: list[AnomalyResult]) -> None:
        """Set anomalies to be returned by detect_coordinated_patterns.

        Args:
            anomalies: List of coordinated pattern anomalies to inject.
        """
        self._coordinated_anomalies = list(anomalies)

    def set_slow_burn_anomalies(self, anomalies: list[AnomalyResult]) -> None:
        """Set anomalies to be returned by detect_slow_burn_erosion.

        Args:
            anomalies: List of slow-burn erosion anomalies to inject.
        """
        self._slow_burn_anomalies = list(anomalies)

    def set_keeper_frequency(
        self,
        keeper_id: str,
        frequency: FrequencyData,
    ) -> None:
        """Set frequency data for a specific keeper.

        Args:
            keeper_id: ID of the keeper.
            frequency: Frequency data to return for this keeper.
        """
        self._keeper_frequencies[keeper_id] = frequency

    def set_default_frequency(self, frequency: FrequencyData) -> None:
        """Set default frequency data for keepers without specific config.

        Args:
            frequency: Default frequency data.
        """
        self._default_frequency = frequency

    def clear(self) -> None:
        """Reset all state for test isolation."""
        self._detected_anomalies = []
        self._coordinated_anomalies = []
        self._slow_burn_anomalies = []
        self._keeper_frequencies = {}
        self._default_frequency = FrequencyData(
            override_count=DEFAULT_OVERRIDE_COUNT,
            time_window_days=90,
            daily_rate=DEFAULT_BASELINE_DAILY_RATE,
            deviation_from_baseline=0.0,
        )

    async def detect_keeper_anomalies(
        self,
        time_window_days: int,
    ) -> list[AnomalyResult]:
        """Detect anomalies across all Keeper override patterns.

        Returns pre-configured anomalies for testing.

        Args:
            time_window_days: Analysis window in days (ignored in stub).

        Returns:
            List of pre-configured detected anomalies.
        """
        return list(self._detected_anomalies)

    async def detect_coordinated_patterns(
        self,
        keeper_ids: list[str],
        time_window_days: int,
    ) -> list[AnomalyResult]:
        """Detect coordinated override patterns across multiple Keepers.

        Returns pre-configured coordinated anomalies for testing.

        Args:
            keeper_ids: List of Keeper IDs to analyze (used for filtering).
            time_window_days: Analysis window in days (ignored in stub).

        Returns:
            List of pre-configured coordinated pattern anomalies.
            Filtered to only include anomalies affecting specified keepers.
        """
        # Filter anomalies to those affecting the specified keepers
        keeper_set = set(keeper_ids)
        filtered = [
            a for a in self._coordinated_anomalies
            if any(k in keeper_set for k in a.affected_keepers)
        ]
        return filtered if filtered else list(self._coordinated_anomalies)

    async def get_keeper_override_frequency(
        self,
        keeper_id: str,
        time_window_days: int,
    ) -> FrequencyData:
        """Get override frequency data for a specific Keeper.

        Returns pre-configured frequency data or default.

        Args:
            keeper_id: The Keeper to analyze.
            time_window_days: Analysis window in days.

        Returns:
            Pre-configured FrequencyData for keeper or default.
        """
        if keeper_id in self._keeper_frequencies:
            freq = self._keeper_frequencies[keeper_id]
            # Return with updated time window
            return FrequencyData(
                override_count=freq.override_count,
                time_window_days=time_window_days,
                daily_rate=freq.daily_rate,
                deviation_from_baseline=freq.deviation_from_baseline,
            )

        # Return default with updated time window
        return FrequencyData(
            override_count=self._default_frequency.override_count,
            time_window_days=time_window_days,
            daily_rate=self._default_frequency.daily_rate,
            deviation_from_baseline=self._default_frequency.deviation_from_baseline,
        )

    async def detect_slow_burn_erosion(
        self,
        time_window_days: int,
        threshold: float,
    ) -> list[AnomalyResult]:
        """Detect slow-burn erosion attacks over long time windows.

        Returns pre-configured slow-burn anomalies for testing.

        Args:
            time_window_days: Long analysis window (ignored in stub).
            threshold: Minimum rate of increase to flag (ignored in stub).

        Returns:
            List of pre-configured slow-burn erosion anomalies.
        """
        return list(self._slow_burn_anomalies)

    # Helper methods for test setup

    def inject_frequency_spike(
        self,
        keeper_id: str,
        override_count: int = 50,
        deviation: float = 3.5,
        confidence: float = 0.85,
    ) -> None:
        """Helper to inject a frequency spike anomaly for a keeper.

        Args:
            keeper_id: ID of the keeper with the spike.
            override_count: Number of overrides to simulate.
            deviation: Standard deviations from baseline.
            confidence: Confidence score for the anomaly.
        """
        # Set keeper frequency data
        self.set_keeper_frequency(
            keeper_id,
            FrequencyData(
                override_count=override_count,
                time_window_days=90,
                daily_rate=override_count / 90.0,
                deviation_from_baseline=deviation,
            ),
        )

        # Add anomaly
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            confidence_score=confidence,
            affected_keepers=(keeper_id,),
            details=f"Frequency spike: {override_count} overrides in 90 days ({deviation:.1f} std above baseline)",
        )
        self._detected_anomalies.append(anomaly)

    def inject_coordinated_pattern(
        self,
        keeper_ids: tuple[str, ...],
        confidence: float = 0.8,
    ) -> None:
        """Helper to inject a coordinated pattern anomaly.

        Args:
            keeper_ids: IDs of keepers involved in coordination.
            confidence: Confidence score for the anomaly.
        """
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.COORDINATED_OVERRIDES,
            confidence_score=confidence,
            affected_keepers=keeper_ids,
            details=f"Coordinated override pattern detected across {len(keeper_ids)} keepers",
        )
        self._coordinated_anomalies.append(anomaly)

    def inject_slow_burn_erosion(
        self,
        keeper_ids: tuple[str, ...],
        confidence: float = 0.75,
        growth_rate: float = 0.15,
    ) -> None:
        """Helper to inject a slow-burn erosion anomaly.

        Args:
            keeper_ids: IDs of keepers involved in erosion.
            confidence: Confidence score for the anomaly.
            growth_rate: Annual growth rate detected.
        """
        anomaly = AnomalyResult(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            confidence_score=confidence,
            affected_keepers=keeper_ids,
            details=f"Slow-burn erosion: {growth_rate:.0%} annual growth rate detected",
        )
        self._slow_burn_anomalies.append(anomaly)
