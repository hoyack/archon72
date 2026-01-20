"""Referral domain events (Story 4.2, FR-4.1, FR-4.2).

This module defines domain events emitted during referral execution.

Constitutional Constraints:
- FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
- FR-4.2: System SHALL assign referral deadline (3 cycles default)
- CT-12: Every action that affects an Archon must be witnessed
- NFR-6.1: All fate transitions witnessed
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from src.domain.models.referral import Referral


# Event type constants
PETITION_REFERRED_EVENT_TYPE: str = "petition.referral.created"
REFERRAL_EXTENDED_EVENT_TYPE: str = "petition.referral.extended"
REFERRAL_COMPLETED_EVENT_TYPE: str = "petition.referral.completed"
REFERRAL_EXPIRED_EVENT_TYPE: str = "petition.referral.expired"
REFERRAL_ASSIGNED_EVENT_TYPE: str = "petition.referral.assigned"
REFERRAL_DEFERRED_EVENT_TYPE: str = "petition.referral.deferred"

# Schema version for referral events (D2 compliance)
REFERRAL_EVENT_SCHEMA_VERSION: str = "1.0.0"


@dataclass(frozen=True, eq=True)
class PetitionReferredEvent:
    """Event emitted when a petition is referred to a Knight (Story 4.2).

    This event is created when Three Fates deliberation reaches REFER
    consensus and the referral is executed. It captures all metadata
    needed for downstream processing and audit trails.

    Constitutional Constraints:
    - FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
    - FR-4.2: System SHALL assign referral deadline (3 cycles default)
    - CT-12: Every action that affects an Archon must be witnessed
    - NFR-6.1: All fate transitions witnessed

    Attributes:
        event_id: Unique identifier for this event.
        petition_id: The petition being referred.
        referral_id: The created referral record ID.
        realm_id: The realm the petition is referred to.
        deadline: When the referral must be completed by (UTC).
        witness_hash: BLAKE3 hash of the referral record (CT-12).
        emitted_at: When this event was emitted (UTC).
        event_type: The event type identifier.
        schema_version: Schema version for deterministic replay.
    """

    event_id: UUID
    petition_id: UUID
    referral_id: UUID
    realm_id: UUID
    deadline: datetime
    witness_hash: str
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = field(default=PETITION_REFERRED_EVENT_TYPE, init=False)
    schema_version: str = field(default=REFERRAL_EVENT_SCHEMA_VERSION, init=False)

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "deadline": self.deadline.isoformat(),
            "event_id": str(self.event_id),
            "petition_id": str(self.petition_id),
            "realm_id": str(self.realm_id),
            "referral_id": str(self.referral_id),
            "witness_hash": self.witness_hash,
        }
        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dict for storage/transmission.

        D2 Compliance: Includes schema_version for deterministic replay.

        Returns:
            Dict representation suitable for event storage.
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "petition_id": str(self.petition_id),
            "referral_id": str(self.referral_id),
            "realm_id": str(self.realm_id),
            "deadline": self.deadline.isoformat(),
            "witness_hash": self.witness_hash,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_referral(
        cls,
        event_id: UUID,
        referral: Referral,
        witness_hash: str,
        emitted_at: datetime | None = None,
    ) -> PetitionReferredEvent:
        """Create event from a Referral domain model.

        Args:
            event_id: Unique identifier for this event.
            referral: The Referral domain model.
            witness_hash: BLAKE3 hash of the referral record.
            emitted_at: When this event was emitted (defaults to now UTC).

        Returns:
            A new PetitionReferredEvent instance.
        """
        return cls(
            event_id=event_id,
            petition_id=referral.petition_id,
            referral_id=referral.referral_id,
            realm_id=referral.realm_id,
            deadline=referral.deadline,
            witness_hash=witness_hash,
            emitted_at=emitted_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True, eq=True)
class ReferralExtendedEvent:
    """Event emitted when a referral deadline is extended (Story 4.5).

    This event is created when a Knight requests and receives
    a deadline extension for their referral.

    Constitutional Constraints:
    - FR-4.4: Knight SHALL be able to request extension (max 2)
    - CT-12: Every action that affects an Archon must be witnessed

    Attributes:
        event_id: Unique identifier for this event.
        referral_id: The referral being extended.
        petition_id: The petition being reviewed.
        knight_id: The Knight requesting the extension.
        previous_deadline: The deadline before extension.
        new_deadline: The deadline after extension.
        extensions_granted: Total extensions granted (1 or 2).
        reason: The Knight's reason for requesting extension.
        witness_hash: BLAKE3 hash for witnessing (CT-12).
        emitted_at: When this event was emitted (UTC).
        event_type: The event type identifier.
        schema_version: Schema version for deterministic replay.
    """

    event_id: UUID
    referral_id: UUID
    petition_id: UUID
    knight_id: UUID
    previous_deadline: datetime
    new_deadline: datetime
    extensions_granted: int
    reason: str
    witness_hash: str
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = field(default=REFERRAL_EXTENDED_EVENT_TYPE, init=False)
    schema_version: str = field(default=REFERRAL_EVENT_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dict for storage/transmission."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "referral_id": str(self.referral_id),
            "petition_id": str(self.petition_id),
            "knight_id": str(self.knight_id),
            "previous_deadline": self.previous_deadline.isoformat(),
            "new_deadline": self.new_deadline.isoformat(),
            "extensions_granted": self.extensions_granted,
            "reason": self.reason,
            "witness_hash": self.witness_hash,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, eq=True)
class ReferralCompletedEvent:
    """Event emitted when a Knight submits a recommendation (Story 4.4).

    This event is created when a Knight completes their review
    and submits a recommendation (ACKNOWLEDGE or ESCALATE).

    Constitutional Constraints:
    - FR-4.6: Knight SHALL submit recommendation with mandatory rationale
    - CT-12: Every action that affects an Archon must be witnessed

    Attributes:
        event_id: Unique identifier for this event.
        referral_id: The completed referral.
        petition_id: The petition that was reviewed.
        knight_id: The Knight who submitted the recommendation.
        recommendation: The Knight's recommendation (ACKNOWLEDGE/ESCALATE).
        rationale: The Knight's rationale (required).
        completed_at: When the recommendation was submitted.
        witness_hash: BLAKE3 hash for witnessing (CT-12).
        emitted_at: When this event was emitted (UTC).
        event_type: The event type identifier.
        schema_version: Schema version for deterministic replay.
    """

    event_id: UUID
    referral_id: UUID
    petition_id: UUID
    knight_id: UUID
    recommendation: str
    rationale: str
    completed_at: datetime
    witness_hash: str
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = field(default=REFERRAL_COMPLETED_EVENT_TYPE, init=False)
    schema_version: str = field(default=REFERRAL_EVENT_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dict for storage/transmission."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "referral_id": str(self.referral_id),
            "petition_id": str(self.petition_id),
            "knight_id": str(self.knight_id),
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "completed_at": self.completed_at.isoformat(),
            "witness_hash": self.witness_hash,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, eq=True)
class ReferralExpiredEvent:
    """Event emitted when a referral deadline expires (Story 4.6).

    This event is created when a referral deadline passes without
    a Knight submitting a recommendation. Per FR-4.5, this triggers
    auto-ACKNOWLEDGE with reason code EXPIRED.

    Constitutional Constraints:
    - FR-4.5: System SHALL auto-ACKNOWLEDGE on referral timeout
    - NFR-3.4: Referral timeout reliability: 100% timeouts fire
    - CT-12: Every action that affects an Archon must be witnessed

    Attributes:
        event_id: Unique identifier for this event.
        referral_id: The expired referral.
        petition_id: The petition that was referred.
        realm_id: The realm the petition was referred to.
        deadline: The deadline that was exceeded.
        expired_at: When the expiration was processed.
        witness_hash: BLAKE3 hash for witnessing (CT-12).
        emitted_at: When this event was emitted (UTC).
        event_type: The event type identifier.
        schema_version: Schema version for deterministic replay.
    """

    event_id: UUID
    referral_id: UUID
    petition_id: UUID
    realm_id: UUID
    deadline: datetime
    expired_at: datetime
    witness_hash: str
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = field(default=REFERRAL_EXPIRED_EVENT_TYPE, init=False)
    schema_version: str = field(default=REFERRAL_EVENT_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dict for storage/transmission."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "referral_id": str(self.referral_id),
            "petition_id": str(self.petition_id),
            "realm_id": str(self.realm_id),
            "deadline": self.deadline.isoformat(),
            "expired_at": self.expired_at.isoformat(),
            "witness_hash": self.witness_hash,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, eq=True)
class ReferralAssignedEvent:
    """Event emitted when a referral is assigned to a Knight (Story 4.7).

    This event is created when the system successfully assigns a
    referral to an eligible Knight with available capacity.

    Constitutional Constraints:
    - FR-4.7: System SHALL enforce max concurrent referrals per Knight
    - NFR-7.3: Referral load balancing - max concurrent per Knight configurable
    - CT-12: Every action that affects an Archon must be witnessed

    Attributes:
        event_id: Unique identifier for this event.
        referral_id: The referral being assigned.
        petition_id: The petition being referred.
        knight_id: The Knight receiving the assignment.
        realm_id: The realm for the referral.
        knight_workload_before: Knight's referral count before assignment.
        knight_workload_after: Knight's referral count after assignment.
        realm_capacity: The realm's knight_capacity setting.
        witness_hash: BLAKE3 hash for witnessing (CT-12).
        emitted_at: When this event was emitted (UTC).
        event_type: The event type identifier.
        schema_version: Schema version for deterministic replay.
    """

    event_id: UUID
    referral_id: UUID
    petition_id: UUID
    knight_id: UUID
    realm_id: UUID
    knight_workload_before: int
    knight_workload_after: int
    realm_capacity: int
    witness_hash: str
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = field(default=REFERRAL_ASSIGNED_EVENT_TYPE, init=False)
    schema_version: str = field(default=REFERRAL_EVENT_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dict for storage/transmission."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "referral_id": str(self.referral_id),
            "petition_id": str(self.petition_id),
            "knight_id": str(self.knight_id),
            "realm_id": str(self.realm_id),
            "knight_workload_before": self.knight_workload_before,
            "knight_workload_after": self.knight_workload_after,
            "realm_capacity": self.realm_capacity,
            "witness_hash": self.witness_hash,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, eq=True)
class ReferralDeferredEvent:
    """Event emitted when a referral assignment is deferred (Story 4.7).

    This event is created when the system cannot assign a referral
    because all Knights in the realm are at capacity. The referral
    remains in PENDING status.

    Constitutional Constraints:
    - FR-4.7: System SHALL enforce max concurrent referrals per Knight
    - NFR-7.3: Referral load balancing - max concurrent per Knight configurable
    - CT-12: Every action that affects an Archon must be witnessed

    Attributes:
        event_id: Unique identifier for this event.
        referral_id: The referral that was deferred.
        petition_id: The petition being referred.
        realm_id: The realm with no available Knights.
        total_knights: Total number of Knights in the realm.
        knights_at_capacity: Number of Knights at capacity.
        realm_capacity: The realm's knight_capacity setting.
        reason: Human-readable deferral reason.
        witness_hash: BLAKE3 hash for witnessing (CT-12).
        emitted_at: When this event was emitted (UTC).
        event_type: The event type identifier.
        schema_version: Schema version for deterministic replay.
    """

    event_id: UUID
    referral_id: UUID
    petition_id: UUID
    realm_id: UUID
    total_knights: int
    knights_at_capacity: int
    realm_capacity: int
    reason: str
    witness_hash: str
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = field(default=REFERRAL_DEFERRED_EVENT_TYPE, init=False)
    schema_version: str = field(default=REFERRAL_EVENT_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dict for storage/transmission."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "referral_id": str(self.referral_id),
            "petition_id": str(self.petition_id),
            "realm_id": str(self.realm_id),
            "total_knights": self.total_knights,
            "knights_at_capacity": self.knights_at_capacity,
            "realm_capacity": self.realm_capacity,
            "reason": self.reason,
            "witness_hash": self.witness_hash,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": self.schema_version,
        }
