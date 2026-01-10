"""Witness anomaly event payloads (Story 6.6, FR116-FR117).

This module defines event payloads for witness pool anomaly detection:
- WitnessAnomalyEventPayload: When statistical anomalies are detected in witness patterns
- WitnessPoolDegradedEventPayload: When witness pool falls below operational minimum

Constitutional Constraints:
- FR116: System SHALL detect patterns of witness unavailability affecting same witnesses
         repeatedly; pattern triggers security review
- FR117: If witness pool <12, continue only for low-stakes events; high-stakes events
         pause until restored. Degraded mode publicly surfaced.
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy -> Anomalies must be logged
- CT-12: Witnessing creates accountability -> All anomaly events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before analysis
2. WITNESS EVERYTHING - All anomaly events must be witnessed
3. FAIL LOUD - Failed event write = analysis failure
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


# Event type constants for witness anomaly detection
WITNESS_ANOMALY_EVENT_TYPE: str = "witness.anomaly"
WITNESS_POOL_DEGRADED_EVENT_TYPE: str = "witness.pool_degraded"


class WitnessAnomalyType(Enum):
    """Types of witness anomalies detected (FR116).

    Each anomaly type represents a specific pattern that may indicate
    witness manipulation or collusion.
    """

    CO_OCCURRENCE = "co_occurrence"
    """Same witness pair appears together more than statistically expected."""

    UNAVAILABILITY_PATTERN = "unavailability_pattern"
    """Same witnesses repeatedly unavailable (potential targeted DoS)."""

    EXCESSIVE_PAIRING = "excessive_pairing"
    """Witness appears in too many pairs relative to pool size."""


class ReviewStatus(Enum):
    """Status of anomaly review (ADR-7 Statistics layer).

    Anomalies are queued for the weekly review ceremony where humans
    classify each anomaly.
    """

    PENDING = "pending"
    """Awaiting human review."""

    INVESTIGATING = "investigating"
    """Under active investigation."""

    CLEARED = "cleared"
    """Determined to be false positive."""

    CONFIRMED = "confirmed"
    """Confirmed as real anomaly, response triggered."""


@dataclass(frozen=True, eq=True)
class WitnessAnomalyEventPayload:
    """Payload for witness anomaly detection events (FR116, ADR-7).

    A WitnessAnomalyEventPayload is created when statistical anomalies
    are detected in witness patterns. This supports the Statistics layer
    of ADR-7 Aggregate Anomaly Detection. This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - FR116: System SHALL detect patterns affecting same witnesses repeatedly
    - CT-9: Attackers are patient - aggregate erosion must be detected
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    ADR-7 Context:
    This event is queued for the weekly anomaly review ceremony,
    where humans classify each anomaly as:
    - True positive: Triggers documented response (pair exclusion)
    - False positive: Dismissed
    - Needs investigation: Escalated for further analysis

    Attributes:
        anomaly_type: Type of anomaly detected.
        affected_witnesses: Tuple of witness IDs involved in the anomaly.
        confidence_score: Confidence in the anomaly detection (0.0 to 1.0).
        detection_window_hours: Time window analyzed in hours.
        occurrence_count: Number of occurrences detected.
        expected_count: Expected count by chance (for chi-square comparison).
        detected_at: When the anomaly was detected (UTC).
        review_status: Current review status (defaults to pending).
        details: Additional context about the anomaly.
    """

    anomaly_type: WitnessAnomalyType
    affected_witnesses: tuple[str, ...]
    confidence_score: float
    detection_window_hours: int
    occurrence_count: int
    expected_count: float
    detected_at: datetime
    review_status: ReviewStatus = ReviewStatus.PENDING
    details: str = ""

    def __post_init__(self) -> None:
        """Validate confidence score is within bounds."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {self.confidence_score}"
            )
        if self.detection_window_hours <= 0:
            raise ValueError(
                f"detection_window_hours must be positive, got {self.detection_window_hours}"
            )
        if self.occurrence_count < 0:
            raise ValueError(
                f"occurrence_count must be non-negative, got {self.occurrence_count}"
            )
        if self.expected_count < 0.0:
            raise ValueError(
                f"expected_count must be non-negative, got {self.expected_count}"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": WITNESS_ANOMALY_EVENT_TYPE,
                "anomaly_type": self.anomaly_type.value,
                "affected_witnesses": list(self.affected_witnesses),
                "confidence_score": self.confidence_score,
                "detection_window_hours": self.detection_window_hours,
                "occurrence_count": self.occurrence_count,
                "expected_count": self.expected_count,
                "detected_at": self.detected_at.isoformat(),
                "review_status": self.review_status.value,
                "details": self.details,
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "anomaly_type": self.anomaly_type.value,
            "affected_witnesses": list(self.affected_witnesses),
            "confidence_score": self.confidence_score,
            "detection_window_hours": self.detection_window_hours,
            "occurrence_count": self.occurrence_count,
            "expected_count": self.expected_count,
            "detected_at": self.detected_at.isoformat(),
            "review_status": self.review_status.value,
            "details": self.details,
        }

    @property
    def chi_square_value(self) -> float:
        """Calculate chi-square value for this anomaly.

        Chi-square = (observed - expected)^2 / expected

        Returns:
            The chi-square statistic, or infinity if expected is 0.
        """
        if self.expected_count == 0.0:
            return float("inf") if self.occurrence_count > 0 else 0.0
        return (self.occurrence_count - self.expected_count) ** 2 / self.expected_count


@dataclass(frozen=True, eq=True)
class WitnessPoolDegradedEventPayload:
    """Payload for witness pool degraded events (FR117).

    A WitnessPoolDegradedEventPayload is created when the witness pool
    falls below the minimum required for high-stakes operations.
    Degraded mode is publicly surfaced per FR117.

    Constitutional Constraints:
    - FR117: If witness pool <12, continue only for low-stakes events;
             high-stakes events pause until restored. Degraded mode publicly surfaced.
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        available_witnesses: Current number of available witnesses.
        minimum_required: Minimum required for the blocked operation type.
        operation_type: Type of operation affected ("high_stakes" or "standard").
        is_blocking: True if operations are paused, False if degraded but continuing.
        degraded_at: When degraded mode was entered (UTC).
        excluded_witnesses: Witnesses currently excluded due to anomalies.
        reason: Human-readable explanation of the degraded state.
    """

    available_witnesses: int
    minimum_required: int
    operation_type: str
    is_blocking: bool
    degraded_at: datetime
    excluded_witnesses: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        """Validate available witnesses is non-negative."""
        if self.available_witnesses < 0:
            raise ValueError(
                f"available_witnesses must be non-negative, got {self.available_witnesses}"
            )
        if self.minimum_required <= 0:
            raise ValueError(
                f"minimum_required must be positive, got {self.minimum_required}"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": WITNESS_POOL_DEGRADED_EVENT_TYPE,
                "available_witnesses": self.available_witnesses,
                "minimum_required": self.minimum_required,
                "operation_type": self.operation_type,
                "is_blocking": self.is_blocking,
                "degraded_at": self.degraded_at.isoformat(),
                "excluded_witnesses": list(self.excluded_witnesses),
                "reason": self.reason,
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "available_witnesses": self.available_witnesses,
            "minimum_required": self.minimum_required,
            "operation_type": self.operation_type,
            "is_blocking": self.is_blocking,
            "degraded_at": self.degraded_at.isoformat(),
            "excluded_witnesses": list(self.excluded_witnesses),
            "reason": self.reason,
        }

    @property
    def effective_count(self) -> int:
        """Calculate effective witness count (available minus excluded).

        Returns:
            Number of witnesses actually available for selection.
        """
        return max(0, self.available_witnesses - len(self.excluded_witnesses))
