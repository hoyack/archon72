"""Keeper availability event payloads (FR77-FR79).

This module defines event payloads for Keeper availability tracking events.
These events create the constitutional audit trail for Keeper attestations,
missed attestations, replacements, and quorum warnings.

Constitutional Constraints:
- FR78: Keepers SHALL attest availability weekly
- FR79: If registered Keeper count falls below 3, system SHALL halt
- CT-11: Silent failure destroys legitimacy -> Events MUST be logged
- CT-12: Witnessing creates accountability -> Events MUST be witnessed
- SR-7: Alert when quorum drops to exactly 3 (critical threshold)

Event Types:
- KeeperAttestationPayload: Weekly attestation submitted
- KeeperMissedAttestationPayload: Attestation deadline passed without submission
- KeeperReplacementInitiatedPayload: Replacement process started
- KeeperQuorumWarningPayload: Quorum at minimum threshold (SR-7)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

# Event type constants
KEEPER_ATTESTATION_EVENT_TYPE: str = "keeper.attestation.submitted"
KEEPER_MISSED_ATTESTATION_EVENT_TYPE: str = "keeper.attestation.missed"
KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE: str = "keeper.replacement.initiated"
KEEPER_QUORUM_WARNING_EVENT_TYPE: str = "keeper.quorum.warning"


class AlertSeverity(str, Enum):
    """Alert severity levels for quorum warnings (SR-7)."""

    LOW = "LOW"  # Informational
    MEDIUM = "MEDIUM"  # Quorum at minimum threshold
    HIGH = "HIGH"  # Critical threshold breach imminent
    CRITICAL = "CRITICAL"  # System halt imminent


@dataclass(frozen=True, eq=True)
class KeeperAttestationPayload:
    """Payload for keeper attestation events - immutable.

    Created when a Keeper successfully submits a weekly attestation.
    This event confirms the Keeper's continued availability.

    Constitutional Constraints:
    - FR78: Weekly attestation requirement
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        keeper_id: ID of the Keeper attesting.
        attested_at: When the attestation was submitted (UTC).
        attestation_period_start: Start of the attestation period.
        attestation_period_end: End of the attestation period.
    """

    # Keeper making the attestation
    keeper_id: str

    # When attestation was submitted
    attested_at: datetime

    # Attestation period boundaries
    attestation_period_start: datetime
    attestation_period_end: datetime

    # Event timestamp
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": KEEPER_ATTESTATION_EVENT_TYPE,
                "keeper_id": self.keeper_id,
                "attested_at": self.attested_at.isoformat(),
                "attestation_period_start": self.attestation_period_start.isoformat(),
                "attestation_period_end": self.attestation_period_end.isoformat(),
                "timestamp": self.timestamp.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return explicit dictionary representation for event storage."""
        return {
            "keeper_id": self.keeper_id,
            "attested_at": self.attested_at.isoformat(),
            "attestation_period_start": self.attestation_period_start.isoformat(),
            "attestation_period_end": self.attestation_period_end.isoformat(),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class KeeperMissedAttestationPayload:
    """Payload for missed attestation events - immutable.

    Created when a Keeper fails to submit an attestation before the
    period deadline. This is part of the replacement tracking process.

    Constitutional Constraints:
    - FR78: Keepers SHALL attest availability weekly
    - CT-11: Silent failure destroys legitimacy -> Missed attestations MUST be logged

    Attributes:
        keeper_id: ID of the Keeper who missed attestation.
        missed_period_start: Start of the missed period.
        missed_period_end: End of the missed period.
        consecutive_misses: Number of consecutive missed attestations.
        deadline_passed_at: When the deadline passed (UTC).
    """

    # Keeper who missed
    keeper_id: str

    # Missed period boundaries
    missed_period_start: datetime
    missed_period_end: datetime

    # Consecutive missed count (tracking toward threshold)
    consecutive_misses: int

    # When deadline passed
    deadline_passed_at: datetime

    # Event timestamp
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": KEEPER_MISSED_ATTESTATION_EVENT_TYPE,
                "keeper_id": self.keeper_id,
                "missed_period_start": self.missed_period_start.isoformat(),
                "missed_period_end": self.missed_period_end.isoformat(),
                "consecutive_misses": self.consecutive_misses,
                "deadline_passed_at": self.deadline_passed_at.isoformat(),
                "timestamp": self.timestamp.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return explicit dictionary representation for event storage."""
        return {
            "keeper_id": self.keeper_id,
            "missed_period_start": self.missed_period_start.isoformat(),
            "missed_period_end": self.missed_period_end.isoformat(),
            "consecutive_misses": self.consecutive_misses,
            "deadline_passed_at": self.deadline_passed_at.isoformat(),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class KeeperReplacementInitiatedPayload:
    """Payload for replacement initiated events - immutable.

    Created when a Keeper misses 2 consecutive attestations (FR78)
    and the replacement process is triggered.

    Constitutional Constraints:
    - FR78: 2 missed attestations trigger replacement process
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        keeper_id: ID of the Keeper being replaced.
        missed_periods: List of missed attestation periods.
        initiated_at: When replacement was initiated (UTC).
        reason: Why replacement was triggered.
    """

    # Keeper being replaced
    keeper_id: str

    # Missed period boundaries (as tuple of tuples for immutability)
    missed_periods: tuple[tuple[str, str], ...]

    # When replacement initiated
    initiated_at: datetime

    # Why replacement was triggered
    reason: str

    # Event timestamp
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Convert lists to tuples for immutability."""
        if isinstance(self.missed_periods, list):
            converted = tuple(
                tuple(period) if isinstance(period, list) else period
                for period in self.missed_periods
            )
            object.__setattr__(self, "missed_periods", converted)

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE,
                "keeper_id": self.keeper_id,
                "missed_periods": [list(period) for period in self.missed_periods],
                "initiated_at": self.initiated_at.isoformat(),
                "reason": self.reason,
                "timestamp": self.timestamp.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return explicit dictionary representation for event storage."""
        return {
            "keeper_id": self.keeper_id,
            "missed_periods": [list(period) for period in self.missed_periods],
            "initiated_at": self.initiated_at.isoformat(),
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class KeeperQuorumWarningPayload:
    """Payload for quorum warning events - immutable (SR-7).

    Created when Keeper quorum drops to exactly 3 (the minimum).
    This provides proactive warning before a quorum violation.

    Constitutional Constraints:
    - FR79: If registered Keeper count falls below 3, system SHALL halt
    - SR-7: Alert when quorum drops to exactly 3 (critical threshold)
    - CT-11: Silent failure destroys legitimacy

    Attributes:
        current_count: Current number of active Keepers.
        minimum_required: Minimum required Keepers (3).
        alert_severity: Severity of the alert.
    """

    # Current active Keeper count
    current_count: int

    # Minimum required (FR79: 3)
    minimum_required: int

    # Alert severity (SR-7)
    alert_severity: str

    # Event timestamp
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12)."""
        return json.dumps(
            {
                "event_type": KEEPER_QUORUM_WARNING_EVENT_TYPE,
                "current_count": self.current_count,
                "minimum_required": self.minimum_required,
                "alert_severity": self.alert_severity,
                "timestamp": self.timestamp.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return explicit dictionary representation for event storage."""
        return {
            "current_count": self.current_count,
            "minimum_required": self.minimum_required,
            "alert_severity": self.alert_severity,
            "timestamp": self.timestamp.isoformat(),
        }
