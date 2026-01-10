"""Witness anomaly detection service (Story 6.6, FR116).

Provides statistical anomaly detection for witness patterns,
supporting the ADR-7 Statistics layer for aggregate erosion detection.

Constitutional Constraints:
- FR116: System SHALL detect patterns of witness unavailability affecting
         same witnesses repeatedly; pattern triggers security review
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> Events must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All anomaly events must be witnessed
3. FAIL LOUD - Failed event write = analysis failure
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.witness_anomaly_detector import (
    PairExclusion,
    WitnessAnomalyDetectorProtocol,
    WitnessAnomalyResult,
)
from src.domain.errors.witness_anomaly import (
    AnomalyScanError,
    WitnessCollusionSuspectedError,
    WitnessPairExcludedError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.witness_anomaly import (
    WITNESS_ANOMALY_EVENT_TYPE,
    ReviewStatus,
    WitnessAnomalyEventPayload,
    WitnessAnomalyType,
)


# Confidence threshold for reporting anomalies (ADR-7)
CONFIDENCE_THRESHOLD: float = 0.7

# Chi-square critical values
CHI_SQUARE_P05: float = 3.84   # p < 0.05
CHI_SQUARE_P01: float = 6.63   # p < 0.01
CHI_SQUARE_P001: float = 10.83  # p < 0.001

# Default exclusion duration in hours
DEFAULT_EXCLUSION_HOURS: int = 24

# Default analysis window in hours (1 week)
DEFAULT_WINDOW_HOURS: int = 168


def calculate_expected_occurrence(pool_size: int, events_count: int) -> float:
    """Calculate expected co-occurrence for a random pair.

    If we have N witnesses and M witnessed events, the expected
    frequency for any specific pair is:

    E[pair] = M / (N * (N-1) / 2)

    Where N*(N-1)/2 is the total possible unique pairs.

    Args:
        pool_size: Number of witnesses in the pool.
        events_count: Number of witnessed events.

    Returns:
        Expected occurrence count for any single pair.
    """
    if pool_size < 2:
        return 0.0
    total_pairs = pool_size * (pool_size - 1) / 2
    return events_count / total_pairs if total_pairs > 0 else 0.0


def calculate_chi_square(observed: int, expected: float) -> float:
    """Calculate chi-square statistic for a single pair.

    Chi-square = (observed - expected)^2 / expected

    Critical values:
    - Chi-square > 3.84 : p < 0.05 (flag for review)
    - Chi-square > 6.63 : p < 0.01 (high confidence anomaly)
    - Chi-square > 10.83: p < 0.001 (very high confidence)

    Args:
        observed: Observed occurrence count.
        expected: Expected occurrence count.

    Returns:
        Chi-square statistic.
    """
    if expected == 0.0:
        return float("inf") if observed > 0 else 0.0
    return (observed - expected) ** 2 / expected


def chi_square_to_confidence(chi_square: float) -> float:
    """Convert chi-square to confidence score (0.0 to 1.0).

    Based on chi-square distribution with 1 degree of freedom.

    Args:
        chi_square: The chi-square statistic.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    if chi_square < CHI_SQUARE_P05:
        # Below threshold, low confidence (0.0 to 0.5)
        return (chi_square / CHI_SQUARE_P05) * 0.5
    elif chi_square < CHI_SQUARE_P01:
        # p < 0.05, medium confidence (0.5 to 0.7)
        return 0.5 + (chi_square - CHI_SQUARE_P05) / (CHI_SQUARE_P01 - CHI_SQUARE_P05) * 0.2
    elif chi_square < CHI_SQUARE_P001:
        # p < 0.01, high confidence (0.7 to 0.9)
        return 0.7 + (chi_square - CHI_SQUARE_P01) / (CHI_SQUARE_P001 - CHI_SQUARE_P01) * 0.2
    else:
        # p < 0.001, very high confidence (0.9 to 1.0)
        return min(0.9 + (chi_square - CHI_SQUARE_P001) / 20.0, 1.0)


class WitnessAnomalyDetectionService:
    """Service for witness anomaly detection (FR116, ADR-7).

    Provides statistical analysis of witness patterns to detect:
    1. Co-occurrence anomalies (pairs appearing too frequently)
    2. Unavailability patterns (same witnesses repeatedly unavailable)

    Constitutional Pattern:
    1. HALT CHECK FIRST at every public operation (CT-11)
    2. Analyze patterns using chi-square statistics
    3. Filter by confidence threshold (0.7)
    4. Create witnessed events for detected anomalies (CT-12)
    5. Support pair exclusion for suspicious pairs

    ADR-7 Integration:
    This service implements the Statistics layer of ADR-7.
    Detected anomalies are queued for human review rather than
    triggering automatic responses.

    Example:
        service = WitnessAnomalyDetectionService(
            halt_checker=halt_checker,
            anomaly_detector=detector,
        )

        # Run weekly scan
        anomalies = await service.run_anomaly_scan(window_hours=168)

        # Check pair before selection
        is_excluded = await service.check_pair_for_anomaly("witness1:witness2")
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        anomaly_detector: WitnessAnomalyDetectorProtocol,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ) -> None:
        """Initialize the witness anomaly detection service.

        Args:
            halt_checker: For CT-11 halt check before operations.
            anomaly_detector: For analyzing and managing anomalies.
            confidence_threshold: Minimum confidence to report (default 0.7).
        """
        self._halt_checker = halt_checker
        self._anomaly_detector = anomaly_detector
        self._confidence_threshold = confidence_threshold

    async def run_anomaly_scan(
        self,
        window_hours: int = DEFAULT_WINDOW_HOURS,
    ) -> list[WitnessAnomalyEventPayload]:
        """Run comprehensive anomaly scan (FR116, ADR-7).

        Analyzes both co-occurrence and unavailability patterns,
        creating event payloads for anomalies above the confidence threshold.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Run co-occurrence analysis
        3. Run unavailability analysis
        4. Filter by confidence threshold
        5. Create event payloads for review queue

        Args:
            window_hours: Time window to analyze in hours (default 168 = 1 week).

        Returns:
            List of WitnessAnomalyEventPayload for detected anomalies.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            AnomalyScanError: If scan fails.
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - anomaly scan blocked")

        detected_payloads: list[WitnessAnomalyEventPayload] = []
        now = datetime.now(timezone.utc)

        try:
            # Run co-occurrence analysis
            co_occurrence_results = await self._anomaly_detector.analyze_co_occurrence(
                window_hours
            )

            for result in co_occurrence_results:
                if result.confidence_score >= self._confidence_threshold:
                    payload = WitnessAnomalyEventPayload(
                        anomaly_type=result.anomaly_type,
                        affected_witnesses=result.affected_witnesses,
                        confidence_score=result.confidence_score,
                        detection_window_hours=window_hours,
                        occurrence_count=result.occurrence_count,
                        expected_count=result.expected_count,
                        detected_at=now,
                        review_status=ReviewStatus.PENDING,
                        details=result.details,
                    )
                    detected_payloads.append(payload)

            # Run unavailability pattern analysis
            unavailability_results = await self._anomaly_detector.analyze_unavailability_patterns(
                window_hours
            )

            for result in unavailability_results:
                if result.confidence_score >= self._confidence_threshold:
                    payload = WitnessAnomalyEventPayload(
                        anomaly_type=result.anomaly_type,
                        affected_witnesses=result.affected_witnesses,
                        confidence_score=result.confidence_score,
                        detection_window_hours=window_hours,
                        occurrence_count=result.occurrence_count,
                        expected_count=result.expected_count,
                        detected_at=now,
                        review_status=ReviewStatus.PENDING,
                        details=result.details,
                    )
                    detected_payloads.append(payload)

        except SystemHaltedError:
            raise
        except Exception as e:
            raise AnomalyScanError(str(e)) from e

        # Sort by confidence (highest first)
        detected_payloads.sort(key=lambda p: p.confidence_score, reverse=True)

        return detected_payloads

    async def check_pair_for_anomaly(self, pair_key: str) -> bool:
        """Check if a pair is excluded due to prior anomaly (FR116).

        Called by witness selection service before selecting a pair.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Check exclusion status

        Args:
            pair_key: Canonical pair key to check.

        Returns:
            True if pair is excluded, False if it can be used.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - pair check blocked")

        return await self._anomaly_detector.is_pair_excluded(pair_key)

    async def exclude_suspicious_pair(
        self,
        pair_key: str,
        confidence: float,
        duration_hours: int = DEFAULT_EXCLUSION_HOURS,
        reason: str = "",
    ) -> WitnessAnomalyEventPayload:
        """Exclude a suspicious pair from selection (FR116).

        Temporarily excludes a pair pending human review. Creates
        an anomaly event recording the exclusion.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Exclude the pair
        3. Create event payload for witnessing (CT-12)

        Args:
            pair_key: Canonical pair key to exclude.
            confidence: Confidence score of the anomaly.
            duration_hours: How long to exclude (default 24 hours).
            reason: Reason for exclusion.

        Returns:
            WitnessAnomalyEventPayload for the exclusion event.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - pair exclusion blocked")

        # Exclude the pair
        await self._anomaly_detector.exclude_pair(
            pair_key=pair_key,
            duration_hours=duration_hours,
            reason=reason,
            confidence=confidence,
        )

        # Extract witness IDs from pair key (format: "ID1:ID2" where IDs may contain colons)
        # Use a smarter split: find the delimiter between two witness IDs
        # Canonical format is sorted alphabetically, so we can split on the middle ":"
        # For simple IDs like "w1:w2", split on ":"
        # For complex IDs like "WITNESS:001:WITNESS:002", we need to find the boundary
        if pair_key.count(":") == 1:
            # Simple format: "w1:w2"
            witnesses = tuple(pair_key.split(":"))
        else:
            # Complex format: try to split in the middle
            # Look for pattern where second witness ID starts
            mid_point = len(pair_key) // 2
            # Find the nearest ":" to the middle
            left_colon = pair_key.rfind(":", 0, mid_point + 1)
            right_colon = pair_key.find(":", mid_point)

            if left_colon != -1 and right_colon != -1:
                # Use the colon closer to the middle
                split_pos = left_colon if (mid_point - left_colon) <= (right_colon - mid_point) else right_colon
                witnesses = (pair_key[:split_pos], pair_key[split_pos + 1:])
            else:
                witnesses = (pair_key,)

        now = datetime.now(timezone.utc)

        # Create event payload for witnessing
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=witnesses,
            confidence_score=confidence,
            detection_window_hours=DEFAULT_WINDOW_HOURS,
            occurrence_count=0,  # Not applicable for exclusion
            expected_count=0.0,  # Not applicable for exclusion
            detected_at=now,
            review_status=ReviewStatus.PENDING,
            details=f"Pair excluded: {reason}" if reason else "Pair excluded for anomaly",
        )

        return payload

    async def clear_pair_exclusion(
        self,
        pair_key: str,
    ) -> bool:
        """Clear exclusion for a pair (for review clearance).

        Called when human review determines the anomaly was a false positive.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Clear the exclusion

        Args:
            pair_key: Canonical pair key to clear.

        Returns:
            True if exclusion was cleared, False if pair wasn't excluded.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - exclusion clear blocked")

        return await self._anomaly_detector.clear_pair_exclusion(pair_key)

    async def get_exclusion_details(
        self,
        pair_key: str,
    ) -> Optional[PairExclusion]:
        """Get details of a pair exclusion.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Return exclusion details

        Args:
            pair_key: Canonical pair key to look up.

        Returns:
            PairExclusion if the pair is excluded, None otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - exclusion lookup blocked")

        return await self._anomaly_detector.get_exclusion_details(pair_key)

    async def get_all_excluded_pairs(self) -> set[str]:
        """Get all currently excluded pair keys.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Return excluded pairs

        Returns:
            Set of canonical pair keys currently excluded.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - exclusion list blocked")

        return await self._anomaly_detector.get_excluded_pairs()
