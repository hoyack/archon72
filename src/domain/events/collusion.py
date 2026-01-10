"""Collusion investigation event payloads (Story 6.8, FR124).

This module defines event payloads for witness collusion defense:
- CollusionInvestigationTriggeredEventPayload: When collusion investigation begins
- WitnessPairSuspendedEventPayload: When a pair is suspended pending investigation
- InvestigationResolvedEventPayload: When an investigation is concluded

Constitutional Constraints:
- FR124: Witness selection randomness SHALL combine hash chain state +
         external entropy source meeting independence criteria (Randomness Gaming defense)
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy -> Investigation triggers must be logged
- CT-12: Witnessing creates accountability -> All investigation events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before investigation operations
2. WITNESS EVERYTHING - All investigation events must be witnessed
3. FAIL LOUD - Failed event write = investigation failure
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


# Event type constants for collusion investigation
COLLUSION_INVESTIGATION_TRIGGERED_EVENT_TYPE: str = "collusion.investigation_triggered"
WITNESS_PAIR_SUSPENDED_EVENT_TYPE: str = "witness.pair_suspended"
INVESTIGATION_RESOLVED_EVENT_TYPE: str = "collusion.investigation_resolved"


class InvestigationResolution(Enum):
    """Resolution outcomes for collusion investigations (FR124).

    Each resolution type determines the fate of the investigated witness pair.
    """

    CLEARED = "cleared"
    """Investigation found no evidence of collusion, pair reinstated."""

    CONFIRMED_COLLUSION = "confirmed_collusion"
    """Investigation confirmed collusion, pair permanently banned."""


@dataclass(frozen=True, eq=True)
class CollusionInvestigationTriggeredEventPayload:
    """Payload for collusion investigation trigger events (FR124, ADR-7).

    A CollusionInvestigationTriggeredEventPayload is created when statistical
    anomalies indicate potential witness collusion, triggering a formal
    investigation. This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - FR124: Witness selection randomness SHALL combine hash chain state +
             external entropy (Randomness Gaming defense)
    - CT-9: Attackers are patient - aggregate erosion must be detected
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    ADR-7 Context:
    This event bridges the Statistics layer (Story 6.6) to the Human layer
    (investigation workflow) in the Aggregate Anomaly Detection system.

    Attributes:
        investigation_id: Unique investigation identifier.
        witness_pair_key: Canonical key of the pair under investigation.
        triggering_anomalies: Anomaly IDs that triggered this investigation.
        breach_event_ids: Related breach events involving this pair.
        correlation_score: Correlation strength (0.0 to 1.0).
        triggered_at: When the investigation was triggered (UTC).
        triggered_by: System or human who initiated the investigation.
    """

    investigation_id: str
    witness_pair_key: str
    triggering_anomalies: tuple[str, ...]
    breach_event_ids: tuple[str, ...]
    correlation_score: float
    triggered_at: datetime
    triggered_by: str

    def __post_init__(self) -> None:
        """Validate correlation score is within bounds."""
        if not 0.0 <= self.correlation_score <= 1.0:
            raise ValueError(
                f"correlation_score must be between 0.0 and 1.0, got {self.correlation_score}"
            )
        if not self.investigation_id:
            raise ValueError("investigation_id cannot be empty")
        if not self.witness_pair_key:
            raise ValueError("witness_pair_key cannot be empty")
        if not self.triggered_by:
            raise ValueError("triggered_by cannot be empty")

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
                "event_type": COLLUSION_INVESTIGATION_TRIGGERED_EVENT_TYPE,
                "investigation_id": self.investigation_id,
                "witness_pair_key": self.witness_pair_key,
                "triggering_anomalies": list(self.triggering_anomalies),
                "breach_event_ids": list(self.breach_event_ids),
                "correlation_score": self.correlation_score,
                "triggered_at": self.triggered_at.isoformat(),
                "triggered_by": self.triggered_by,
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "investigation_id": self.investigation_id,
            "witness_pair_key": self.witness_pair_key,
            "triggering_anomalies": list(self.triggering_anomalies),
            "breach_event_ids": list(self.breach_event_ids),
            "correlation_score": self.correlation_score,
            "triggered_at": self.triggered_at.isoformat(),
            "triggered_by": self.triggered_by,
        }


@dataclass(frozen=True, eq=True)
class WitnessPairSuspendedEventPayload:
    """Payload for witness pair suspension events (FR124).

    A WitnessPairSuspendedEventPayload is created when a witness pair
    is suspended pending collusion investigation. The pair cannot be
    selected for witnessing until the investigation is resolved.

    Constitutional Constraints:
    - FR124: Randomness Gaming defense - suspicious pairs must be excluded
    - CT-11: Silent failure destroys legitimacy -> Suspension is publicly visible
    - CT-12: Witnessing creates accountability

    Attributes:
        pair_key: Canonical pair key (e.g., "witness_a:witness_b").
        investigation_id: Related investigation that caused suspension.
        suspension_reason: Human-readable explanation.
        suspended_at: When the suspension occurred (UTC).
        suspended_by: Attribution - who/what suspended the pair.
    """

    pair_key: str
    investigation_id: str
    suspension_reason: str
    suspended_at: datetime
    suspended_by: str

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.pair_key:
            raise ValueError("pair_key cannot be empty")
        if not self.investigation_id:
            raise ValueError("investigation_id cannot be empty")
        if not self.suspended_by:
            raise ValueError("suspended_by cannot be empty")

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": WITNESS_PAIR_SUSPENDED_EVENT_TYPE,
                "pair_key": self.pair_key,
                "investigation_id": self.investigation_id,
                "suspension_reason": self.suspension_reason,
                "suspended_at": self.suspended_at.isoformat(),
                "suspended_by": self.suspended_by,
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "pair_key": self.pair_key,
            "investigation_id": self.investigation_id,
            "suspension_reason": self.suspension_reason,
            "suspended_at": self.suspended_at.isoformat(),
            "suspended_by": self.suspended_by,
        }


@dataclass(frozen=True, eq=True)
class InvestigationResolvedEventPayload:
    """Payload for investigation resolution events (FR124).

    An InvestigationResolvedEventPayload is created when a collusion
    investigation is concluded. The resolution determines the pair's fate:
    - CLEARED: Pair reinstated for selection
    - CONFIRMED_COLLUSION: Pair permanently banned

    Constitutional Constraints:
    - FR124: Randomness Gaming defense - collusion must be handled
    - CT-11: Silent failure destroys legitimacy -> Resolution is public
    - CT-12: Witnessing creates accountability -> Resolver attribution required

    Attributes:
        investigation_id: Investigation being resolved.
        pair_key: Canonical key of the investigated pair.
        resolution: CLEARED or CONFIRMED_COLLUSION.
        resolution_reason: Human-readable explanation.
        resolved_at: When the resolution occurred (UTC).
        resolved_by: Investigator attribution.
        evidence_summary: Summary of evidence considered.
    """

    investigation_id: str
    pair_key: str
    resolution: InvestigationResolution
    resolution_reason: str
    resolved_at: datetime
    resolved_by: str
    evidence_summary: str

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.investigation_id:
            raise ValueError("investigation_id cannot be empty")
        if not self.pair_key:
            raise ValueError("pair_key cannot be empty")
        if not self.resolved_by:
            raise ValueError("resolved_by cannot be empty (CT-12: attribution required)")

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": INVESTIGATION_RESOLVED_EVENT_TYPE,
                "investigation_id": self.investigation_id,
                "pair_key": self.pair_key,
                "resolution": self.resolution.value,
                "resolution_reason": self.resolution_reason,
                "resolved_at": self.resolved_at.isoformat(),
                "resolved_by": self.resolved_by,
                "evidence_summary": self.evidence_summary,
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "investigation_id": self.investigation_id,
            "pair_key": self.pair_key,
            "resolution": self.resolution.value,
            "resolution_reason": self.resolution_reason,
            "resolved_at": self.resolved_at.isoformat(),
            "resolved_by": self.resolved_by,
            "evidence_summary": self.evidence_summary,
        }
