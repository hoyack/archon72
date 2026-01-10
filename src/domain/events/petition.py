"""Petition event payloads for external observer petitions (Story 7.2, FR39).

This module defines the event payloads for external observer petition capability:
- PetitionCreatedEventPayload: When a petition is submitted
- PetitionCoSignedEventPayload: When an observer co-signs a petition
- PetitionThresholdMetEventPayload: When 100+ co-signers trigger agenda placement

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All petition events must be logged
- CT-12: Witnessing creates accountability → All events MUST be witnessed
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
PETITION_CREATED_EVENT_TYPE: str = "petition.created"
PETITION_COSIGNED_EVENT_TYPE: str = "petition.cosigned"
PETITION_THRESHOLD_MET_EVENT_TYPE: str = "petition.threshold_met"

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
