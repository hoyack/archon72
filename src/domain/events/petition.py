"""Petition event payloads for petition lifecycle events.

This module defines the event payloads for petition capability:
- PetitionReceivedEventPayload: When a petition is received via Three Fates intake (FR-1.7)
- PetitionCreatedEventPayload: When an external observer submits a cessation petition (Story 7.2)
- PetitionCoSignedEventPayload: When an observer co-signs a petition
- PetitionThresholdMetEventPayload: When 100+ co-signers trigger agenda placement
- PetitionFateEventPayload: When a petition reaches terminal fate state (Story 1.7, FR-2.5)

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All petition events must be logged
- CT-12: Witnessing creates accountability → All events MUST be witnessed
- CT-13: No writes during halt → Event emission blocked during system halt
- FR-1.7: System SHALL emit PetitionReceived event on successful intake
- FR39: External observers can petition with 100+ co-signers

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating petition events (writes)
2. WITNESS EVERYTHING - All petition events require attribution
3. FAIL LOUD - Never silently swallow signature errors
4. READS DURING HALT - Petition queries work during halt (CT-13)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

# Event type constants for petition events
PETITION_RECEIVED_EVENT_TYPE: str = "petition.submission.received"
PETITION_CREATED_EVENT_TYPE: str = "petition.submission.created"
PETITION_COSIGNED_EVENT_TYPE: str = "petition.submission.cosigned"
PETITION_THRESHOLD_MET_EVENT_TYPE: str = "petition.submission.threshold_met"

# Fate event type constants (Story 1.7, FR-2.5)
# These events are emitted when a petition reaches a terminal fate state.
# Constitutional constraint: HC-1 - Fate transition requires witness event.
PETITION_ACKNOWLEDGED_EVENT_TYPE: str = "petition.submission.acknowledged"
PETITION_REFERRED_EVENT_TYPE: str = "petition.submission.referred"
PETITION_ESCALATED_EVENT_TYPE: str = "petition.submission.escalated"

# Petition system agent ID for event attribution
PETITION_SYSTEM_AGENT_ID: str = "petition-system"

# Threshold for agenda placement trigger
PETITION_THRESHOLD_COSIGNERS: int = 100


class PetitionStatus(str, Enum):
    """Status of a petition (FR39).

    Petition lifecycle states:
    - OPEN: Accepting co-signatures
    - THRESHOLD_MET: 100+ co-signers, agenda placed
    - CLOSED: No longer accepting co-signatures

    Constitutional Constraint:
    Each status transition must be witnessed and logged with attribution.
    """

    OPEN = "open"
    """Petition is open and accepting co-signatures."""

    THRESHOLD_MET = "threshold_met"
    """Petition reached 100 co-signers, cessation placed on agenda."""

    CLOSED = "closed"
    """Petition is closed and no longer accepting co-signatures."""


@dataclass(frozen=True, eq=True)
class PetitionReceivedEventPayload:
    """Payload for petition received events (FR-1.7, Story 1.2).

    A PetitionReceivedEventPayload is created when a petition is successfully
    submitted and persisted via the Three Fates intake system.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-1.7: System SHALL emit PetitionReceived event on successful intake
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: No writes during halt -> Event emission blocked during halt

    Attributes:
        petition_id: Unique identifier for this petition.
        petition_type: Type of petition (GENERAL, CESSATION, GRIEVANCE, etc.)
        realm: The realm assigned for routing.
        content_hash: Base64-encoded Blake3 hash of petition text.
        submitter_id: Optional submitter identity (UUID).
        received_timestamp: When the petition was received (UTC).
    """

    petition_id: UUID
    petition_type: str
    realm: str
    content_hash: str
    submitter_id: UUID | None
    received_timestamp: datetime

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
            "content_hash": self.content_hash,
            "petition_id": str(self.petition_id),
            "petition_type": self.petition_type,
            "realm": self.realm,
            "received_timestamp": self.received_timestamp.isoformat(),
            "submitter_id": str(self.submitter_id) if self.submitter_id else None,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for GovernanceLedger.append_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "petition_type": self.petition_type,
            "realm": self.realm,
            "content_hash": self.content_hash,
            "submitter_id": str(self.submitter_id) if self.submitter_id else None,
            "received_timestamp": self.received_timestamp.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class PetitionCreatedEventPayload:
    """Payload for petition creation events (FR39, AC1).

    A PetitionCreatedEventPayload is created when an external observer
    submits a new cessation petition with their signature.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR39: External observers can petition with 100+ co-signers
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        petition_id: Unique identifier for this petition.
        submitter_public_key: Observer's hex-encoded Ed25519 public key.
        submitter_signature: Hex-encoded signature over petition content.
        petition_content: Reason for cessation concern.
        created_timestamp: When submitted (UTC).
    """

    petition_id: UUID
    submitter_public_key: str
    submitter_signature: str
    petition_content: str
    created_timestamp: datetime

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
            "created_timestamp": self.created_timestamp.isoformat(),
            "petition_content": self.petition_content,
            "petition_id": str(self.petition_id),
            "submitter_public_key": self.submitter_public_key,
            "submitter_signature": self.submitter_signature,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "submitter_public_key": self.submitter_public_key,
            "submitter_signature": self.submitter_signature,
            "petition_content": self.petition_content,
            "created_timestamp": self.created_timestamp.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class PetitionCoSignedEventPayload:
    """Payload for petition co-signature events (FR39, AC2).

    A PetitionCoSignedEventPayload is created when an external observer
    co-signs an existing petition with their signature.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR39: External observers can petition with 100+ co-signers
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - AC2: Duplicate co-signatures from same public key are rejected

    Attributes:
        petition_id: Reference to the petition being co-signed.
        cosigner_public_key: Co-signer's hex-encoded Ed25519 public key.
        cosigner_signature: Hex-encoded signature over petition content.
        cosigned_timestamp: When co-signed (UTC).
        cosigner_sequence: Order of this co-signer (1-based).
    """

    petition_id: UUID
    cosigner_public_key: str
    cosigner_signature: str
    cosigned_timestamp: datetime
    cosigner_sequence: int

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
            "cosigned_timestamp": self.cosigned_timestamp.isoformat(),
            "cosigner_public_key": self.cosigner_public_key,
            "cosigner_sequence": self.cosigner_sequence,
            "cosigner_signature": self.cosigner_signature,
            "petition_id": str(self.petition_id),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "cosigner_public_key": self.cosigner_public_key,
            "cosigner_signature": self.cosigner_signature,
            "cosigned_timestamp": self.cosigned_timestamp.isoformat(),
            "cosigner_sequence": self.cosigner_sequence,
        }


@dataclass(frozen=True, eq=True)
class PetitionThresholdMetEventPayload:
    """Payload for petition threshold met events (FR39, AC3).

    A PetitionThresholdMetEventPayload is created when a petition reaches
    100 co-signers, triggering cessation agenda placement.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR39: 100+ co-signers triggers cessation agenda placement
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - AC5: Idempotent - additional co-signatures don't create duplicate agenda

    Attributes:
        petition_id: Reference to the petition that met threshold.
        threshold: The threshold that was met (100).
        final_cosigner_count: Actual count of co-signers (>= 100).
        trigger_timestamp: When the threshold was met (UTC).
        cosigner_public_keys: All public keys of co-signers.
        agenda_placement_reason: Human-readable reason for placement.
    """

    petition_id: UUID
    threshold: int
    final_cosigner_count: int
    trigger_timestamp: datetime
    cosigner_public_keys: tuple[str, ...]
    agenda_placement_reason: str

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
            "agenda_placement_reason": self.agenda_placement_reason,
            "cosigner_public_keys": list(self.cosigner_public_keys),
            "final_cosigner_count": self.final_cosigner_count,
            "petition_id": str(self.petition_id),
            "threshold": self.threshold,
            "trigger_timestamp": self.trigger_timestamp.isoformat(),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "threshold": self.threshold,
            "final_cosigner_count": self.final_cosigner_count,
            "trigger_timestamp": self.trigger_timestamp.isoformat(),
            "cosigner_public_keys": list(self.cosigner_public_keys),
            "agenda_placement_reason": self.agenda_placement_reason,
        }


# Current schema version for fate events (D2 compliance)
# This is embedded in the payload for deterministic replay
FATE_EVENT_SCHEMA_VERSION: str = "1.0.0"


@dataclass(frozen=True, eq=True)
class PetitionFateEventPayload:
    """Payload for petition fate events (Story 1.7, FR-2.5).

    A PetitionFateEventPayload is created when a petition reaches a terminal
    fate state through Three Fates deliberation. The fate can be:
    - ACKNOWLEDGED: Petition noted, no further action required
    - REFERRED: Petition routed to realm-specific Knight
    - ESCALATED: Petition elevated to Conclave for constitutional review

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-2.5: System SHALL emit fate event in same transaction as state update
    - NFR-3.3: Event witnessing: 100% fate events persisted [CRITICAL]
    - HC-1: Fate transition requires witness event - NO silent fate assignment
    - CT-12: Witnessing creates accountability - Events MUST be witnessed

    CRITICAL DIFFERENCE from PetitionReceivedEventPayload:
    - Fate events MUST NOT fail silently - if emission fails, state is rolled back
    - No graceful degradation - fate without witness is constitutionally invalid

    Attributes:
        petition_id: Unique identifier for the petition.
        previous_state: State before fate assignment (RECEIVED or DELIBERATING).
        new_state: Terminal fate state (ACKNOWLEDGED, REFERRED, or ESCALATED).
        actor_id: Agent or system identifier that assigned the fate.
        timestamp: When the fate was assigned (UTC).
        reason: Optional reason code or rationale for the fate decision.
    """

    petition_id: UUID
    previous_state: str
    new_state: str
    actor_id: str
    timestamp: datetime
    reason: str | None

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
            "actor_id": self.actor_id,
            "new_state": self.new_state,
            "petition_id": str(self.petition_id),
            "previous_state": self.previous_state,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.

        Returns:
            Dict representation suitable for GovernanceLedger.append_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "actor_id": self.actor_id,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "schema_version": FATE_EVENT_SCHEMA_VERSION,
        }


# Story 6.3: Petition Adoption Event


# Event type constant for petition adoption (Story 6.3, FR-5.5)
PETITION_ADOPTED_EVENT_TYPE: str = "petition.adoption.adopted"

# Schema version for adoption events (deterministic replay)
ADOPTION_EVENT_SCHEMA_VERSION: str = "1.0.0"


@dataclass(frozen=True, eq=True)
class PetitionAdoptedEventPayload:
    """Payload for petition adoption events (Story 6.3, FR-5.5, FR-5.7).

    A PetitionAdoptedEventPayload is created when a King adopts an escalated
    petition and creates a Motion. This event provides immutable provenance
    linking the Motion to its source Petition.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-5.5: King SHALL be able to ADOPT petition (creates Motion) [P0]
    - FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]
    - NFR-6.2: Adoption provenance immutability
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: No writes during halt -> Event emission blocked during halt

    Attributes:
        petition_id: UUID of the adopted petition (source)
        motion_id: UUID of the created Motion (target)
        sponsor_king_id: UUID of the King who adopted the petition
        adoption_rationale: King's rationale for adoption (min 50 chars)
        adopted_at: When the adoption occurred (UTC)
        budget_consumed: Amount of promotion budget consumed (always 1)
        realm_id: Realm where the adoption occurred (for provenance)
    """

    petition_id: UUID
    motion_id: UUID
    sponsor_king_id: UUID
    adoption_rationale: str
    adopted_at: datetime
    budget_consumed: int = 1
    realm_id: str = "default"

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
            "adopted_at": self.adopted_at.isoformat(),
            "adoption_rationale": self.adoption_rationale,
            "budget_consumed": self.budget_consumed,
            "motion_id": str(self.motion_id),
            "petition_id": str(self.petition_id),
            "realm_id": self.realm_id,
            "sponsor_king_id": str(self.sponsor_king_id),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.
        FR-5.7: Immutable provenance (petition_id → motion_id).

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "motion_id": str(self.motion_id),
            "sponsor_king_id": str(self.sponsor_king_id),
            "adoption_rationale": self.adoption_rationale,
            "adopted_at": self.adopted_at.isoformat(),
            "budget_consumed": self.budget_consumed,
            "realm_id": self.realm_id,
            "schema_version": ADOPTION_EVENT_SCHEMA_VERSION,
        }


# Story 6.5: King Escalation Acknowledgment Event


# Event type constant for king acknowledgment (Story 6.5, FR-5.8)
KING_ACKNOWLEDGED_ESCALATION_EVENT_TYPE: str = "petition.escalation.acknowledged_by_king"

# Story 7.3: Petition Withdrawal Event
PETITION_WITHDRAWN_EVENT_TYPE: str = "petition.submission.withdrawn"

# Schema version for king acknowledgment events (deterministic replay)
KING_ACKNOWLEDGMENT_EVENT_SCHEMA_VERSION: str = "1.0.0"


@dataclass(frozen=True, eq=True)
class KingAcknowledgedEscalationEventPayload:
    """Payload for King escalation acknowledgment events (Story 6.5, FR-5.8).

    A KingAcknowledgedEscalationEventPayload is created when a King formally
    declines to adopt an escalated petition, providing a rationale to respect
    the petitioners' concerns.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-5.8: King SHALL be able to ACKNOWLEDGE escalation (with rationale) [P0]
    - FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code [P0]
    - FR-3.2: System SHALL require reason_code from enumerated list [P0]
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: No writes during halt -> Event emission blocked during halt
    - RULING-3: Realm-scoped data access (King can only acknowledge their realm)

    Attributes:
        petition_id: UUID of the acknowledged escalated petition
        king_id: UUID of the King who acknowledged
        reason_code: Reason from AcknowledgmentReasonCode enum
        rationale: King's explanation (min 100 chars per Story 6.5)
        acknowledged_at: When the acknowledgment occurred (UTC)
        realm_id: Realm where the acknowledgment occurred
    """

    petition_id: UUID
    king_id: UUID
    reason_code: str  # AcknowledgmentReasonCode.value
    rationale: str
    acknowledged_at: datetime
    realm_id: str

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
            "acknowledged_at": self.acknowledged_at.isoformat(),
            "king_id": str(self.king_id),
            "petition_id": str(self.petition_id),
            "rationale": self.rationale,
            "reason_code": self.reason_code,
            "realm_id": self.realm_id,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.
        FR-5.8: Immutable acknowledgment record with King provenance.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "king_id": str(self.king_id),
            "reason_code": self.reason_code,
            "rationale": self.rationale,
            "acknowledged_at": self.acknowledged_at.isoformat(),
            "realm_id": self.realm_id,
            "schema_version": KING_ACKNOWLEDGMENT_EVENT_SCHEMA_VERSION,
        }


# Story 7.3: Petition Withdrawal Event Payload

# Schema version for withdrawal events (D2 compliance)
WITHDRAWAL_EVENT_SCHEMA_VERSION: str = "1.0.0"


@dataclass(frozen=True, eq=True)
class PetitionWithdrawnEventPayload:
    """Payload for petition withdrawal events (Story 7.3, FR-7.5).

    A PetitionWithdrawnEventPayload is created when a petitioner withdraws
    their petition before fate assignment. The petition transitions to
    ACKNOWLEDGED state with WITHDRAWN reason code.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-7.5: Petitioner SHALL be able to withdraw petition before fate assignment
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed
    - CT-13: No writes during halt -> Event emission blocked during halt

    Attributes:
        petition_id: UUID of the withdrawn petition
        withdrawn_by: UUID of the petitioner who withdrew (submitter_id)
        reason: Optional explanation for withdrawal
        withdrawn_at: When the withdrawal occurred (UTC)
    """

    petition_id: UUID
    withdrawn_by: UUID
    reason: str | None
    withdrawn_at: datetime

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
            "petition_id": str(self.petition_id),
            "reason": self.reason,
            "withdrawn_at": self.withdrawn_at.isoformat(),
            "withdrawn_by": str(self.withdrawn_by),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "petition_id": str(self.petition_id),
            "withdrawn_by": str(self.withdrawn_by),
            "reason": self.reason,
            "withdrawn_at": self.withdrawn_at.isoformat(),
            "schema_version": WITHDRAWAL_EVENT_SCHEMA_VERSION,
        }
