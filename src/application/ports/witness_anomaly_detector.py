"""Witness anomaly detector port (Story 6.6, FR116).

Defines the protocol for witness anomaly detection, supporting
statistical analysis of witness co-occurrence and unavailability patterns.

Constitutional Constraints:
- FR116: System SHALL detect patterns of witness unavailability affecting
         same witnesses repeatedly; pattern triggers security review
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability

ADR-7 Context:
This port supports the Statistics layer of ADR-7 Aggregate Anomaly Detection.
Anomalies are queued for human review rather than triggering automatic responses.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from src.domain.events.witness_anomaly import WitnessAnomalyType


@dataclass(frozen=True)
class WitnessAnomalyResult:
    """Result of witness anomaly analysis.

    Represents a detected anomaly for the review queue.

    Attributes:
        anomaly_type: Type of anomaly detected.
        confidence_score: Confidence in the detection (0.0 to 1.0).
        affected_witnesses: Tuple of witness IDs involved.
        occurrence_count: Number of occurrences detected.
        expected_count: Expected count by chance.
        details: Human-readable description of the anomaly.
    """

    anomaly_type: WitnessAnomalyType
    confidence_score: float
    affected_witnesses: tuple[str, ...]
    occurrence_count: int
    expected_count: float
    details: str

    def __post_init__(self) -> None:
        """Validate confidence score is within bounds."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {self.confidence_score}"
            )


@dataclass(frozen=True)
class PairExclusion:
    """Record of a temporarily excluded witness pair.

    Attributes:
        pair_key: Canonical pair key (sorted IDs joined with colon).
        excluded_at: When the pair was excluded.
        excluded_until: When the exclusion expires.
        reason: Reason for exclusion.
        confidence: Confidence score of the anomaly that triggered exclusion.
    """

    pair_key: str
    excluded_at: datetime
    excluded_until: datetime
    reason: str
    confidence: float


@runtime_checkable
class WitnessAnomalyDetectorProtocol(Protocol):
    """Protocol for witness anomaly detection (FR116).

    Constitutional Constraint (FR116):
    System SHALL detect patterns of witness unavailability affecting
    same witnesses repeatedly; pattern triggers security review.

    Implementations must:
    1. Analyze co-occurrence patterns for statistical anomalies
    2. Detect unavailability patterns suggesting targeted DoS
    3. Manage temporary pair exclusions pending review
    4. Support the ADR-7 Statistics layer review queue

    Example:
        detector: WitnessAnomalyDetectorProtocol = ...

        # Run analysis
        co_occurrence_anomalies = await detector.analyze_co_occurrence(168)
        unavailability_anomalies = await detector.analyze_unavailability_patterns(168)

        # Exclude suspicious pair
        if co_occurrence_anomalies:
            anomaly = co_occurrence_anomalies[0]
            pair_key = f"{anomaly.affected_witnesses[0]}:{anomaly.affected_witnesses[1]}"
            await detector.exclude_pair(pair_key, duration_hours=24)

        # Check exclusion during selection
        if await detector.is_pair_excluded(pair_key):
            # Skip this pair in selection
            ...
    """

    @abstractmethod
    async def analyze_co_occurrence(
        self,
        window_hours: int,
    ) -> list[WitnessAnomalyResult]:
        """Analyze witness pair co-occurrence for anomalies.

        Detects pairs that appear together more often than
        statistically expected, indicating potential collusion.

        Uses chi-square test to determine statistical significance:
        - Chi-square > 3.84 (p < 0.05): Flag for review
        - Chi-square > 6.63 (p < 0.01): High confidence anomaly
        - Chi-square > 10.83 (p < 0.001): Very high confidence

        Args:
            window_hours: Time window to analyze in hours.

        Returns:
            List of detected anomalies, sorted by confidence (highest first).
        """
        ...

    @abstractmethod
    async def analyze_unavailability_patterns(
        self,
        window_hours: int,
    ) -> list[WitnessAnomalyResult]:
        """Analyze unavailability patterns (FR116).

        Detects if same witnesses are repeatedly unavailable,
        which could indicate targeted DoS or manipulation.

        Args:
            window_hours: Time window to analyze in hours.

        Returns:
            List of detected unavailability pattern anomalies.
        """
        ...

    @abstractmethod
    async def get_excluded_pairs(self) -> set[str]:
        """Get canonical keys of currently excluded pairs.

        Returns:
            Set of pair keys that are currently excluded from selection.
        """
        ...

    @abstractmethod
    async def exclude_pair(
        self,
        pair_key: str,
        duration_hours: int,
        reason: str = "",
        confidence: float = 0.0,
    ) -> None:
        """Temporarily exclude a pair from selection.

        Excluded pairs are skipped during witness selection until
        the exclusion expires or is manually cleared.

        Args:
            pair_key: Canonical pair key to exclude.
            duration_hours: How long to exclude the pair.
            reason: Reason for exclusion (for audit trail).
            confidence: Confidence score of the anomaly.
        """
        ...

    @abstractmethod
    async def clear_pair_exclusion(self, pair_key: str) -> bool:
        """Remove exclusion for a pair (for review clearance).

        Called when human review clears a pair as false positive.

        Args:
            pair_key: Canonical pair key to clear.

        Returns:
            True if exclusion was removed, False if pair wasn't excluded.
        """
        ...

    @abstractmethod
    async def is_pair_excluded(self, pair_key: str) -> bool:
        """Check if a pair is currently excluded.

        Args:
            pair_key: Canonical pair key to check.

        Returns:
            True if the pair is excluded, False otherwise.
        """
        ...

    @abstractmethod
    async def get_exclusion_details(
        self, pair_key: str
    ) -> Optional[PairExclusion]:
        """Get details of a pair exclusion.

        Args:
            pair_key: Canonical pair key to look up.

        Returns:
            PairExclusion if the pair is excluded, None otherwise.
        """
        ...
