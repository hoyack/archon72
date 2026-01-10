"""Breach declaration event payloads (Story 6.1, FR30).

This module defines event payloads for constitutional breach declarations:
- BreachEventPayload: When a constitutional breach is detected and recorded
- BreachType: Types of constitutional violations
- BreachSeverity: Severity levels aligned with architecture alert levels

Constitutional Constraints:
- FR30: Breach declarations SHALL create constitutional events with
        breach_type, violated_requirement, detection_timestamp
- CT-11: Silent failure destroys legitimacy -> All breaches must be logged
- CT-12: Witnessing creates accountability -> All breach events MUST be witnessed
- CT-13: Integrity outranks availability -> Availability may be sacrificed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating breach events
2. WITNESS EVERYTHING - All breach events must be witnessed
3. FAIL LOUD - Never silently swallow breach detection
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Optional
from uuid import UUID

# Event type constant for breach declaration
BREACH_DECLARED_EVENT_TYPE: str = "breach.declared"


class BreachType(Enum):
    """Types of constitutional breaches (FR30).

    Each breach type represents a specific category of constitutional violation.
    These are used to categorize and filter breach events for monitoring,
    escalation (Story 6.2), and cessation triggers (Story 6.3).
    """

    THRESHOLD_VIOLATION = "THRESHOLD_VIOLATION"
    """Threshold set below constitutional floor (FR33-34)."""

    WITNESS_COLLUSION = "WITNESS_COLLUSION"
    """Statistical anomaly in witness pair co-occurrence (FR59-61, FR116-118)."""

    HASH_MISMATCH = "HASH_MISMATCH"
    """Content hash verification failed (FR82, FR125)."""

    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    """Signature verification failed (FR104)."""

    CONSTITUTIONAL_CONSTRAINT = "CONSTITUTIONAL_CONSTRAINT"
    """General constitutional primitive violation (FR80-FR87)."""

    TIMING_VIOLATION = "TIMING_VIOLATION"
    """Recovery waiting period or other timing constraint not honored (FR21)."""

    QUORUM_VIOLATION = "QUORUM_VIOLATION"
    """Quorum not met for decision requiring supermajority (FR9)."""

    OVERRIDE_ABUSE = "OVERRIDE_ABUSE"
    """Override violated constitutional constraints (FR86-87)."""

    EMERGENCE_VIOLATION = "EMERGENCE_VIOLATION"
    """Emergence language violation detected (FR55, FR109)."""


class BreachSeverity(Enum):
    """Severity levels for breach events.

    Aligned with architecture alert levels from ADR-5:
    - CRITICAL: Page immediately, may halt system
    - HIGH: Page immediately
    - MEDIUM: Alert on-call, 15 min response
    - LOW: Next business day
    """

    CRITICAL = "CRITICAL"
    """Page immediately, halt system. Example: Signature verification failed."""

    HIGH = "HIGH"
    """Page immediately. Example: Halt signal detected."""

    MEDIUM = "MEDIUM"
    """Alert on-call, 15 min response. Example: Watchdog heartbeat missed."""

    LOW = "LOW"
    """Next business day. Example: Ceremony quorum warning."""


@dataclass(frozen=True, eq=True)
class BreachEventPayload:
    """Payload for constitutional breach events (FR30).

    A BreachEventPayload is created when a constitutional breach is detected.
    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR30: Breach declarations SHALL create constitutional events with
            breach_type, violated_requirement, detection_timestamp
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: Integrity outranks availability

    Attributes:
        breach_id: Unique identifier for this breach event.
        breach_type: Category of constitutional violation.
        violated_requirement: The FR/CT/NFR that was violated (e.g., "FR30", "CT-11").
        severity: Alert severity level for response prioritization.
        detection_timestamp: When the breach was detected (UTC).
        details: Additional context about the breach (varies by type).
        source_event_id: Optional ID of the event that triggered this breach.
    """

    breach_id: UUID
    breach_type: BreachType
    violated_requirement: str
    severity: BreachSeverity
    detection_timestamp: datetime
    details: MappingProxyType[str, Any]
    source_event_id: Optional[UUID] = None

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
            "breach_id": str(self.breach_id),
            "breach_type": self.breach_type.value,
            "violated_requirement": self.violated_requirement,
            "severity": self.severity.value,
            "detection_timestamp": self.detection_timestamp.isoformat(),
            "details": dict(self.details),
        }

        if self.source_event_id is not None:
            content["source_event_id"] = str(self.source_event_id)

        return json.dumps(content, sort_keys=True).encode("utf-8")
