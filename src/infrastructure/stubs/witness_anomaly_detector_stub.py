"""Witness anomaly detector stub (Story 6.6, FR116).

Provides an in-memory stub implementation of WitnessAnomalyDetectorProtocol
for development and testing.

WARNING: DEV MODE ONLY
This stub is for development/testing only and should never be used
in production. The DEV MODE watermark is included in all operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.application.ports.witness_anomaly_detector import (
    PairExclusion,
    WitnessAnomalyDetectorProtocol,
    WitnessAnomalyResult,
)
from src.domain.events.witness_anomaly import WitnessAnomalyType


logger = logging.getLogger(__name__)


# DEV MODE warning
DEV_MODE_WARNING = """
╔══════════════════════════════════════════════════════════════╗
║  [DEV MODE] WitnessAnomalyDetectorStub Active                ║
║  This stub is for DEVELOPMENT/TESTING only.                  ║
║  DO NOT use in production environments.                      ║
╚══════════════════════════════════════════════════════════════╝
"""


class WitnessAnomalyDetectorStub(WitnessAnomalyDetectorProtocol):
    """In-memory stub for witness anomaly detection (FR116).

    Provides a simple implementation for development and testing.
    Supports injection of test anomalies and pair exclusions.

    WARNING: This stub is for development/testing only and should
    never be used in production.

    Example:
        stub = WitnessAnomalyDetectorStub()

        # Inject test anomaly
        stub.inject_anomaly(WitnessAnomalyResult(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            confidence_score=0.8,
            affected_witnesses=("witness1", "witness2"),
            occurrence_count=15,
            expected_count=5.0,
            details="Test anomaly",
        ))

        # Run analysis
        results = await stub.analyze_co_occurrence(168)
    """

    def __init__(self) -> None:
        """Initialize the stub with empty state."""
        logger.warning(DEV_MODE_WARNING)

        # Injected anomalies for testing
        self._co_occurrence_anomalies: list[WitnessAnomalyResult] = []
        self._unavailability_anomalies: list[WitnessAnomalyResult] = []

        # Excluded pairs: pair_key -> PairExclusion
        self._excluded_pairs: dict[str, PairExclusion] = {}

    async def analyze_co_occurrence(
        self,
        window_hours: int,
    ) -> list[WitnessAnomalyResult]:
        """Return injected co-occurrence anomalies.

        Args:
            window_hours: Time window (ignored in stub, uses injected data).

        Returns:
            List of injected co-occurrence anomalies.
        """
        self._prune_expired_exclusions()
        return list(self._co_occurrence_anomalies)

    async def analyze_unavailability_patterns(
        self,
        window_hours: int,
    ) -> list[WitnessAnomalyResult]:
        """Return injected unavailability anomalies.

        Args:
            window_hours: Time window (ignored in stub, uses injected data).

        Returns:
            List of injected unavailability anomalies.
        """
        self._prune_expired_exclusions()
        return list(self._unavailability_anomalies)

    async def get_excluded_pairs(self) -> set[str]:
        """Get currently excluded pair keys.

        Returns:
            Set of pair keys that are currently excluded.
        """
        self._prune_expired_exclusions()
        return set(self._excluded_pairs.keys())

    async def exclude_pair(
        self,
        pair_key: str,
        duration_hours: int,
        reason: str = "",
        confidence: float = 0.0,
    ) -> None:
        """Temporarily exclude a pair.

        Args:
            pair_key: Canonical pair key to exclude.
            duration_hours: How long to exclude the pair.
            reason: Reason for exclusion.
            confidence: Confidence score of the anomaly.
        """
        now = datetime.now(timezone.utc)
        exclusion = PairExclusion(
            pair_key=pair_key,
            excluded_at=now,
            excluded_until=now + timedelta(hours=duration_hours),
            reason=reason,
            confidence=confidence,
        )
        self._excluded_pairs[pair_key] = exclusion
        logger.info(
            "[DEV MODE] Pair excluded",
            extra={
                "pair_key": pair_key,
                "duration_hours": duration_hours,
                "reason": reason,
            },
        )

    async def clear_pair_exclusion(self, pair_key: str) -> bool:
        """Remove exclusion for a pair.

        Args:
            pair_key: Canonical pair key to clear.

        Returns:
            True if exclusion was removed, False if pair wasn't excluded.
        """
        if pair_key in self._excluded_pairs:
            del self._excluded_pairs[pair_key]
            logger.info(
                "[DEV MODE] Pair exclusion cleared",
                extra={"pair_key": pair_key},
            )
            return True
        return False

    async def is_pair_excluded(self, pair_key: str) -> bool:
        """Check if a pair is currently excluded.

        Args:
            pair_key: Canonical pair key to check.

        Returns:
            True if the pair is excluded, False otherwise.
        """
        self._prune_expired_exclusions()
        return pair_key in self._excluded_pairs

    async def get_exclusion_details(
        self, pair_key: str
    ) -> Optional[PairExclusion]:
        """Get details of a pair exclusion.

        Args:
            pair_key: Canonical pair key to look up.

        Returns:
            PairExclusion if the pair is excluded, None otherwise.
        """
        self._prune_expired_exclusions()
        return self._excluded_pairs.get(pair_key)

    # ========== Test helpers ==========

    def inject_anomaly(self, anomaly: WitnessAnomalyResult) -> None:
        """Inject an anomaly for testing.

        Automatically routes to co-occurrence or unavailability list
        based on anomaly type.

        Args:
            anomaly: The anomaly to inject.
        """
        if anomaly.anomaly_type == WitnessAnomalyType.UNAVAILABILITY_PATTERN:
            self._unavailability_anomalies.append(anomaly)
        else:
            self._co_occurrence_anomalies.append(anomaly)
        logger.info(
            "[DEV MODE] Anomaly injected",
            extra={
                "anomaly_type": anomaly.anomaly_type.value,
                "confidence": anomaly.confidence_score,
            },
        )

    def set_co_occurrence_anomalies(
        self, anomalies: list[WitnessAnomalyResult]
    ) -> None:
        """Set the co-occurrence anomalies for testing.

        Args:
            anomalies: List of anomalies to return from analyze_co_occurrence.
        """
        self._co_occurrence_anomalies = list(anomalies)

    def set_unavailability_anomalies(
        self, anomalies: list[WitnessAnomalyResult]
    ) -> None:
        """Set the unavailability anomalies for testing.

        Args:
            anomalies: List of anomalies to return from analyze_unavailability_patterns.
        """
        self._unavailability_anomalies = list(anomalies)

    def clear(self) -> None:
        """Clear all state for test isolation."""
        self._co_occurrence_anomalies.clear()
        self._unavailability_anomalies.clear()
        self._excluded_pairs.clear()
        logger.info("[DEV MODE] Stub state cleared")

    def _prune_expired_exclusions(self) -> None:
        """Remove expired exclusions."""
        now = datetime.now(timezone.utc)
        expired = [
            key
            for key, exclusion in self._excluded_pairs.items()
            if exclusion.excluded_until < now
        ]
        for key in expired:
            del self._excluded_pairs[key]
