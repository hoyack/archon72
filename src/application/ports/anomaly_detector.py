"""Anomaly Detector Port - Statistical anomaly detection (Story 5.9, FP-3, ADR-7).

This port defines the contract for detecting statistical anomalies in
override patterns, supporting the Statistics layer of ADR-7 Aggregate
Anomaly Detection.

Constitutional Constraints:
- CT-9: Attackers are patient - aggregate erosion must be detected
- FP-3: Patient attacker detection needs ADR-7 (Aggregate Anomaly Detection)
- CT-11: Silent failure destroys legitimacy -> All anomalies must be logged
- CT-12: Witnessing creates accountability -> Anomaly events MUST be witnessed

ADR-7 Context:
This port implements the Statistics layer of the three-layer detection system:
| Layer | Method | Response |
|-------|--------|----------|
| Rules | Predefined thresholds | Auto-alert, auto-halt if critical |
| Statistics (THIS PORT) | Baseline deviation detection | Queue for review |
| Human | Weekly anomaly review ceremony | Classify, escalate, or dismiss |

This port enables:
- Dependency inversion for anomaly detection algorithms
- Testability with mock implementations
- Separation between detection algorithms and service orchestration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from src.domain.events.override_abuse import AnomalyType


@dataclass(frozen=True)
class FrequencyData:
    """Data about override frequency for a Keeper.

    Used to track and analyze Keeper override patterns over time.

    Attributes:
        override_count: Total number of overrides in the time window.
        time_window_days: Analysis window in days.
        daily_rate: Average overrides per day.
        deviation_from_baseline: How many standard deviations from normal.
            Positive values indicate above-average frequency.
            Values > 2.0 typically indicate significant deviation.
    """

    override_count: int
    time_window_days: int
    daily_rate: float
    deviation_from_baseline: float


@dataclass(frozen=True)
class AnomalyResult:
    """Result of anomaly detection analysis.

    Represents a single detected anomaly for queuing to the
    weekly anomaly review ceremony (ADR-7).

    Attributes:
        anomaly_type: Type of anomaly detected.
        confidence_score: Confidence in the detection (0.0 to 1.0).
            Higher values indicate more certain detections.
            Typically only report anomalies with confidence > 0.7.
        affected_keepers: Tuple of Keeper IDs involved in the anomaly.
        details: Human-readable description of the anomaly.
    """

    anomaly_type: AnomalyType
    confidence_score: float
    affected_keepers: tuple[str, ...]
    details: str

    def __post_init__(self) -> None:
        """Validate confidence score is within bounds."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {self.confidence_score}"
            )


class AnomalyDetectorProtocol(Protocol):
    """Protocol for statistical anomaly detection (FP-3, ADR-7).

    This protocol defines the Statistics layer of ADR-7 Aggregate
    Anomaly Detection. Implementations analyze override patterns
    to detect potential abuse.

    Constitutional Constraints:
    - CT-9: Attackers are patient - must detect slow erosion
    - FP-3: Patient attacker detection using statistical methods

    ADR-7 Metrics Tracked:
    - Halt frequency by source
    - Ceremony frequency by type
    - Witness response times
    - Event rate patterns (override patterns)
    - Failed verification attempts (abuse rejections)

    Implementations should:
    - Maintain baseline statistics for normal behavior
    - Detect deviations from baseline
    - Assign confidence scores to detections
    - Support configurable detection thresholds
    """

    async def detect_keeper_anomalies(
        self,
        time_window_days: int,
    ) -> list[AnomalyResult]:
        """Detect anomalies across all Keeper override patterns.

        Analyzes override patterns for all Keepers within the time window
        to identify frequency spikes or unusual patterns.

        Args:
            time_window_days: Analysis window in days (e.g., 90 for FP-3).

        Returns:
            List of detected anomalies. Empty list if no anomalies found.

        Note:
            This method should analyze:
            - Individual Keeper frequency spikes
            - Unusual timing patterns
            - Scope distribution anomalies
        """
        ...

    async def detect_coordinated_patterns(
        self,
        keeper_ids: list[str],
        time_window_days: int,
    ) -> list[AnomalyResult]:
        """Detect coordinated override patterns across multiple Keepers.

        Constitutional Constraint (CT-9):
        Attackers are patient. Coordinated attacks may involve multiple
        Keepers issuing similar overrides in close temporal proximity.

        Args:
            keeper_ids: List of Keeper IDs to analyze for coordination.
            time_window_days: Analysis window in days.

        Returns:
            List of detected coordinated pattern anomalies.

        Note:
            Coordination detection looks for:
            - Temporal clustering of similar overrides
            - Similar scope patterns across Keepers
            - Unusual timing coincidences
        """
        ...

    async def get_keeper_override_frequency(
        self,
        keeper_id: str,
        time_window_days: int,
    ) -> FrequencyData:
        """Get override frequency data for a specific Keeper.

        Used to analyze individual Keeper behavior and compare
        against baseline statistics.

        Args:
            keeper_id: The Keeper to analyze.
            time_window_days: Analysis window in days.

        Returns:
            FrequencyData with override statistics and deviation metrics.
        """
        ...

    async def detect_slow_burn_erosion(
        self,
        time_window_days: int,
        threshold: float,
    ) -> list[AnomalyResult]:
        """Detect slow-burn erosion attacks over long time windows.

        Constitutional Constraint (CT-9):
        Attackers are patient. This method detects gradual increases
        in override frequency that might escape short-term detection.

        ADR-7 Context:
        This implements long-term pattern analysis to catch slow-burn
        attacks that erode system integrity below obvious thresholds.

        Args:
            time_window_days: Long analysis window (e.g., 365 days).
            threshold: Minimum rate of increase to flag (e.g., 0.1 for 10%).
                Represents the acceptable annual growth rate.

        Returns:
            List of detected slow-burn erosion anomalies.

        Note:
            Slow-burn detection looks for:
            - Gradual increase in override frequency
            - Steady erosion of specific constitutional constraints
            - Creeping scope expansion over time
        """
        ...
