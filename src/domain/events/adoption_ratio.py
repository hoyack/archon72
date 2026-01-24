"""Adoption ratio event payloads (Story 8.6, PREVENT-7).

This module defines event payloads for adoption ratio alerting when
petition adoption patterns exceed configured thresholds.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- ASM-7: Monitor adoption vs organic ratio
- CT-12: All outputs through witnessing pipeline
- ADR-P4: Budget consumption prevents budget laundering

Developer Golden Rules:
1. WITNESS EVERYTHING - All alert events must be witnessed (CT-12)
2. USE to_dict() - Never use asdict() for event serialization (D2)
3. INCLUDE schema_version - All event payloads require schema_version (D2)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


# Event type constants
ADOPTION_RATIO_EXCEEDED_EVENT_TYPE: str = "adoption_ratio.alert.exceeded"
ADOPTION_RATIO_NORMALIZED_EVENT_TYPE: str = "adoption_ratio.alert.normalized"

# Schema version for D2 compliance
ADOPTION_RATIO_ALERT_SCHEMA_VERSION: int = 1


@dataclass(frozen=True, eq=True)
class AdoptionRatioExceededEventPayload:
    """Event payload for adoption ratio exceeded (Story 8.6, PREVENT-7).

    An AdoptionRatioExceededEventPayload is created when a realm's adoption
    ratio exceeds the 50% threshold, indicating potential "rubber-stamping"
    of escalated petitions by the King.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - PREVENT-7: Alert when adoption ratio > 50%
    - ASM-7: Monitor adoption vs organic ratio
    - CT-12: Witnessing creates accountability - must be witnessed

    Attributes:
        event_id: Unique identifier for this event.
        alert_id: Reference to the AdoptionRatioAlert.
        realm_id: Realm with excessive adoption ratio.
        cycle_id: Governance cycle when detected (e.g., "2026-W04").
        adoption_ratio: The computed ratio (0.0 to 1.0).
        threshold: The threshold that was exceeded (0.50).
        severity: Alert severity (WARN or CRITICAL).
        adopting_kings: List of King UUIDs who adopted (as strings for JSON).
        adoption_count: Number of adoptions in the cycle.
        escalation_count: Number of escalations in the cycle.
        trend_delta: Change from previous cycle (optional).
        occurred_at: When the alert was raised (UTC).
        schema_version: Schema version for D2 compliance.
    """

    event_id: UUID
    alert_id: UUID
    realm_id: str
    cycle_id: str
    adoption_ratio: float
    threshold: float
    severity: str
    adopting_kings: tuple[str, ...]
    adoption_count: int
    escalation_count: int
    trend_delta: float | None
    occurred_at: datetime
    schema_version: int = ADOPTION_RATIO_ALERT_SCHEMA_VERSION

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
        content: dict[str, Any] = {
            "adoption_count": self.adoption_count,
            "adoption_ratio": self.adoption_ratio,
            "adopting_kings": list(self.adopting_kings),
            "alert_id": str(self.alert_id),
            "cycle_id": self.cycle_id,
            "escalation_count": self.escalation_count,
            "event_id": str(self.event_id),
            "occurred_at": self.occurred_at.isoformat(),
            "realm_id": self.realm_id,
            "schema_version": self.schema_version,
            "severity": self.severity,
            "threshold": self.threshold,
            "trend_delta": self.trend_delta,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage (D2 compliance).

        IMPORTANT: Use this method, NOT asdict(), for event serialization.
        asdict() doesn't handle UUID and datetime serialization correctly.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "event_id": str(self.event_id),
            "alert_id": str(self.alert_id),
            "realm_id": self.realm_id,
            "cycle_id": self.cycle_id,
            "adoption_ratio": self.adoption_ratio,
            "threshold": self.threshold,
            "severity": self.severity,
            "adopting_kings": list(self.adopting_kings),
            "adoption_count": self.adoption_count,
            "escalation_count": self.escalation_count,
            "trend_delta": self.trend_delta,
            "occurred_at": self.occurred_at.isoformat(),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, eq=True)
class AdoptionRatioNormalizedEventPayload:
    """Event payload for adoption ratio normalized (Story 8.6, PREVENT-7).

    An AdoptionRatioNormalizedEventPayload is created when a realm's adoption
    ratio returns to normal levels (below threshold), indicating the alert
    condition has been resolved.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - PREVENT-7: Auto-resolve when ratio normalizes
    - CT-12: Witnessing creates accountability - must be witnessed

    Attributes:
        event_id: Unique identifier for this event.
        alert_id: Reference to the resolved AdoptionRatioAlert.
        realm_id: Realm where ratio normalized.
        cycle_id: Governance cycle when normalized (e.g., "2026-W04").
        new_adoption_ratio: The new ratio after normalization.
        previous_ratio: The ratio when alert was triggered.
        alert_duration_seconds: How long the alert was active.
        normalized_at: When the alert was resolved (UTC).
        schema_version: Schema version for D2 compliance.
    """

    event_id: UUID
    alert_id: UUID
    realm_id: str
    cycle_id: str
    new_adoption_ratio: float
    previous_ratio: float
    alert_duration_seconds: int
    normalized_at: datetime
    schema_version: int = ADOPTION_RATIO_ALERT_SCHEMA_VERSION

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
        content: dict[str, Any] = {
            "alert_duration_seconds": self.alert_duration_seconds,
            "alert_id": str(self.alert_id),
            "cycle_id": self.cycle_id,
            "event_id": str(self.event_id),
            "new_adoption_ratio": self.new_adoption_ratio,
            "normalized_at": self.normalized_at.isoformat(),
            "previous_ratio": self.previous_ratio,
            "realm_id": self.realm_id,
            "schema_version": self.schema_version,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage (D2 compliance).

        IMPORTANT: Use this method, NOT asdict(), for event serialization.
        asdict() doesn't handle UUID and datetime serialization correctly.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "event_id": str(self.event_id),
            "alert_id": str(self.alert_id),
            "realm_id": self.realm_id,
            "cycle_id": self.cycle_id,
            "new_adoption_ratio": self.new_adoption_ratio,
            "previous_ratio": self.previous_ratio,
            "alert_duration_seconds": self.alert_duration_seconds,
            "normalized_at": self.normalized_at.isoformat(),
            "schema_version": self.schema_version,
        }
