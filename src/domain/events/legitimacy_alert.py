"""Legitimacy alert event payloads (Story 8.2, FR-8.3, NFR-7.2).

This module defines event payloads for legitimacy decay alerting when
petition system responsiveness drops below configured thresholds.

Constitutional Constraints:
- FR-8.3: System SHALL alert on decay below 0.85 threshold [P1]
- NFR-7.2: Legitimacy decay alerting - Alert at < 0.85 threshold
- CT-12: All outputs through witnessing pipeline

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

from src.domain._compat import StrEnum

# Event type constants
LEGITIMACY_ALERT_TRIGGERED_EVENT_TYPE: str = "legitimacy.alert.triggered"
LEGITIMACY_ALERT_RECOVERED_EVENT_TYPE: str = "legitimacy.alert.recovered"

# Schema version for D2 compliance
LEGITIMACY_ALERT_SCHEMA_VERSION: int = 1


class AlertSeverity(StrEnum):
    """Alert severity levels for legitimacy decay (FR-8.3).

    Severity is determined by legitimacy score thresholds:
    - WARNING: score < 0.85 and >= 0.70
    - CRITICAL: score < 0.70
    """

    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, eq=True)
class LegitimacyAlertTriggeredEvent:
    """Event payload for legitimacy alert triggered (Story 8.2, FR-8.3).

    A LegitimacyAlertTriggeredEvent is created when the petition system's
    legitimacy score drops below configured health thresholds, indicating
    degraded responsiveness or processing failures.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-8.3: System SHALL alert on decay below 0.85 threshold
    - NFR-7.2: Alert delivery within 1 minute of trigger
    - CT-12: Witnessing creates accountability - must be witnessed

    Attributes:
        alert_id: Unique identifier for this alert event.
        cycle_id: The governance cycle that triggered the alert (e.g., "2026-W04").
        current_score: The legitimacy score that triggered the alert (0.0-1.0).
        threshold: The threshold that was breached (0.85 or 0.70).
        severity: Alert severity (WARNING or CRITICAL).
        stuck_petition_count: Count of petitions not fated within SLA.
        triggered_at: When the alert was triggered (UTC).
        schema_version: Schema version for D2 compliance.
    """

    alert_id: UUID
    cycle_id: str
    current_score: float
    threshold: float
    severity: AlertSeverity
    stuck_petition_count: int
    triggered_at: datetime
    schema_version: int = LEGITIMACY_ALERT_SCHEMA_VERSION

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
            "alert_id": str(self.alert_id),
            "current_score": self.current_score,
            "cycle_id": self.cycle_id,
            "schema_version": self.schema_version,
            "severity": self.severity.value,
            "stuck_petition_count": self.stuck_petition_count,
            "threshold": self.threshold,
            "triggered_at": self.triggered_at.isoformat(),
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
            "alert_id": str(self.alert_id),
            "cycle_id": self.cycle_id,
            "current_score": self.current_score,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "stuck_petition_count": self.stuck_petition_count,
            "triggered_at": self.triggered_at.isoformat(),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, eq=True)
class LegitimacyAlertRecoveredEvent:
    """Event payload for legitimacy alert recovered (Story 8.2, FR-8.3).

    A LegitimacyAlertRecoveredEvent is created when the petition system's
    legitimacy score recovers above the alert threshold, indicating
    restored responsiveness.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-8.3: System SHALL alert on recovery
    - NFR-7.2: Alert delivery within 1 minute of recovery
    - CT-12: Witnessing creates accountability - must be witnessed

    Attributes:
        recovery_id: Unique identifier for this recovery event.
        alert_id: The alert_id that is being recovered.
        cycle_id: The governance cycle when recovery occurred (e.g., "2026-W04").
        current_score: The legitimacy score at recovery (0.0-1.0).
        previous_score: The score when alert was triggered.
        alert_duration_seconds: How long the system was in alert state (seconds).
        recovered_at: When the alert was resolved (UTC).
        schema_version: Schema version for D2 compliance.
    """

    recovery_id: UUID
    alert_id: UUID
    cycle_id: str
    current_score: float
    previous_score: float
    alert_duration_seconds: int
    recovered_at: datetime
    schema_version: int = LEGITIMACY_ALERT_SCHEMA_VERSION

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
            "current_score": self.current_score,
            "cycle_id": self.cycle_id,
            "previous_score": self.previous_score,
            "recovered_at": self.recovered_at.isoformat(),
            "recovery_id": str(self.recovery_id),
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
            "recovery_id": str(self.recovery_id),
            "alert_id": str(self.alert_id),
            "cycle_id": self.cycle_id,
            "current_score": self.current_score,
            "previous_score": self.previous_score,
            "alert_duration_seconds": self.alert_duration_seconds,
            "recovered_at": self.recovered_at.isoformat(),
            "schema_version": self.schema_version,
        }
