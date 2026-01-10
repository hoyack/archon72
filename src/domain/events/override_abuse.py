"""Override abuse event payloads (Story 5.9, FR86-FR87, FP-3).

This module defines event payloads for override abuse detection:
- OverrideAbuseRejectedPayload: When an override is rejected for constitutional violations
- AnomalyDetectedPayload: When statistical anomalies are detected in override patterns

Constitutional Constraints:
- FR86: System SHALL validate override commands against constitutional constraints
- FR87: Override commands violating constitutional constraints SHALL be rejected and logged
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy -> Rejections must be logged
- CT-12: Witnessing creates accountability -> All abuse events MUST be witnessed
- FP-3: Patient attacker detection needs ADR-7 (Aggregate Anomaly Detection)

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before validation
2. WITNESS EVERYTHING - All abuse events must be witnessed
3. FAIL LOUD - Failed event write = validation failure
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

# Event type constants for override abuse detection
OVERRIDE_ABUSE_REJECTED_EVENT_TYPE: str = "override.abuse_rejected"
ANOMALY_DETECTED_EVENT_TYPE: str = "override.anomaly_detected"


class ViolationType(Enum):
    """Types of constitutional violations for override abuse (FR86, FR87).

    Each violation type represents a specific constitutional constraint breach.
    """

    WITNESS_SUPPRESSION = "WITNESS_SUPPRESSION"
    """Attempt to suppress witnessing (FR26 violation)."""

    HISTORY_EDIT = "HISTORY_EDIT"
    """Attempt to edit event history (FR87 - history edit attempt)."""

    EVIDENCE_DESTRUCTION = "EVIDENCE_DESTRUCTION"
    """Attempt to destroy evidence (FR87 - evidence destruction attempt)."""

    FORBIDDEN_SCOPE = "FORBIDDEN_SCOPE"
    """Override scope is in forbidden list (FR86 - constitutional constraint)."""

    CONSTITUTIONAL_CONSTRAINT = "CONSTITUTIONAL_CONSTRAINT"
    """General constitutional constraint violation (FR86)."""


class AnomalyType(Enum):
    """Types of anomalies detected in override patterns (FP-3, ADR-7).

    Each anomaly type represents a different pattern of potential abuse.
    These support the Statistics layer of ADR-7 Aggregate Anomaly Detection.
    """

    COORDINATED_OVERRIDES = "COORDINATED_OVERRIDES"
    """Multiple Keepers issuing similar overrides in close temporal proximity."""

    FREQUENCY_SPIKE = "FREQUENCY_SPIKE"
    """Sudden increase in override frequency for a single Keeper."""

    PATTERN_CORRELATION = "PATTERN_CORRELATION"
    """Statistical correlation detected between override patterns."""

    SLOW_BURN_EROSION = "SLOW_BURN_EROSION"
    """Gradual increase in overrides over long time window (CT-9 patient attacker)."""


@dataclass(frozen=True, eq=True)
class OverrideAbuseRejectedPayload:
    """Payload for override abuse rejection events (FR86, FR87).

    An OverrideAbuseRejectedPayload is created when an override command
    is rejected for violating constitutional constraints. This event
    MUST be witnessed (CT-12).

    Constitutional Constraints:
    - FR86: System SHALL validate override commands against constitutional constraints
    - FR87: Override commands violating constitutional constraints SHALL be rejected and logged
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        keeper_id: ID of the Keeper who attempted the override.
        scope: The override scope that was rejected.
        violation_type: Type of constitutional violation detected.
        violation_details: Human-readable description of the violation.
        rejected_at: When the override was rejected (UTC).
    """

    keeper_id: str
    scope: str
    violation_type: ViolationType
    violation_details: str
    rejected_at: datetime

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
                "event_type": "OverrideAbuseRejected",
                "keeper_id": self.keeper_id,
                "scope": self.scope,
                "violation_type": self.violation_type.value,
                "violation_details": self.violation_details,
                "rejected_at": self.rejected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")


@dataclass(frozen=True, eq=True)
class AnomalyDetectedPayload:
    """Payload for anomaly detection events (FP-3, ADR-7).

    An AnomalyDetectedPayload is created when statistical anomalies
    are detected in override patterns. This supports the Statistics layer
    of ADR-7 Aggregate Anomaly Detection. This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - CT-9: Attackers are patient - aggregate erosion must be detected
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability
    - FP-3: Patient attacker detection needs ADR-7

    ADR-7 Context:
    This event is queued for the weekly anomaly review ceremony,
    where humans classify each anomaly as:
    - True positive: Triggers documented response
    - False positive: Dismissed
    - Needs investigation: Escalated for further analysis

    Attributes:
        anomaly_type: Type of anomaly detected.
        keeper_ids: List of Keeper IDs involved in the anomaly.
        detection_method: Method used to detect the anomaly (e.g., "baseline_deviation").
        confidence_score: Confidence in the anomaly detection (0.0 to 1.0).
        time_window_days: Analysis window in days.
        details: Additional context about the anomaly.
        detected_at: When the anomaly was detected (UTC).
    """

    anomaly_type: AnomalyType
    keeper_ids: tuple[str, ...]
    detection_method: str
    confidence_score: float
    time_window_days: int
    details: str
    detected_at: datetime

    def __post_init__(self) -> None:
        """Validate confidence score is within bounds."""
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {self.confidence_score}"
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
                "event_type": "AnomalyDetected",
                "anomaly_type": self.anomaly_type.value,
                "keeper_ids": list(self.keeper_ids),
                "detection_method": self.detection_method,
                "confidence_score": self.confidence_score,
                "time_window_days": self.time_window_days,
                "details": self.details,
                "detected_at": self.detected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
