"""Co-sign event payloads for Three Fates petition co-signing (Story 5.2, Story 5.3).

This module defines the event payloads for co-sign submission:
- CoSignRecordedEvent: When a Seeker co-signs a petition (FR-6.1)

Constitutional Constraints:
- FR-6.1: Seeker SHALL be able to co-sign active petition
- FR-6.4: System SHALL increment co-signer count atomically
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- CT-11: Silent failure destroys legitimacy -> All events must be logged
- CT-12: Witnessing creates accountability -> All events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before emitting events (writes)
2. WITNESS EVERYTHING - All co-sign events require attribution
3. FAIL LOUD - Never silently swallow event emission errors
4. ATOMIC OPERATIONS - Count increment and event emission must be atomic
5. VERIFY IDENTITY - Check signer identity before accepting co-sign (NFR-5.2)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

# Event type constant for co-sign recorded event
CO_SIGN_RECORDED_EVENT_TYPE: str = "petition.co_sign.recorded"

# Schema version for co-sign events (D2 compliance)
CO_SIGN_EVENT_SCHEMA_VERSION: str = "1.0.0"

# System agent ID for co-sign event attribution
CO_SIGN_SYSTEM_AGENT_ID: str = "co-sign-system"


@dataclass(frozen=True, eq=True)
class CoSignRecordedEvent:
    """Payload for co-sign recorded events (Story 5.2, Story 5.3, FR-6.1, CT-12).

    A CoSignRecordedEvent is created when a Seeker successfully co-signs
    a petition in the Three Fates system.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR-6.1: Seeker SHALL be able to co-sign active petition
    - FR-6.4: Co-signer count is incremented atomically
    - NFR-3.5: 0 duplicate signatures ever exist
    - NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
    - CT-11: Silent failure destroys legitimacy -> Must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        cosign_id: Unique identifier for this co-signature (UUIDv7).
        petition_id: Reference to the petition being co-signed.
        signer_id: UUID of the Seeker adding their support.
        signed_at: When the co-signature was recorded (UTC).
        content_hash: BLAKE3 hex-encoded hash for witness integrity.
        co_signer_count: Updated co-signer count after this signature.
        identity_verified: Whether signer identity was verified (NFR-5.2, LEGIT-1).
    """

    cosign_id: UUID
    petition_id: UUID
    signer_id: UUID
    signed_at: datetime
    content_hash: str
    co_signer_count: int
    identity_verified: bool = False

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
            "co_signer_count": self.co_signer_count,
            "content_hash": self.content_hash,
            "cosign_id": str(self.cosign_id),
            "identity_verified": self.identity_verified,
            "petition_id": str(self.petition_id),
            "signed_at": self.signed_at.isoformat(),
            "signer_id": str(self.signer_id),
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        D2 Compliance: Includes schema_version for deterministic replay.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "cosign_id": str(self.cosign_id),
            "petition_id": str(self.petition_id),
            "signer_id": str(self.signer_id),
            "signed_at": self.signed_at.isoformat(),
            "content_hash": self.content_hash,
            "co_signer_count": self.co_signer_count,
            "identity_verified": self.identity_verified,
            "schema_version": CO_SIGN_EVENT_SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoSignRecordedEvent:
        """Deserialize from dictionary.

        Args:
            data: Dictionary representation of a CoSignRecordedEvent.

        Returns:
            CoSignRecordedEvent instance.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If field values are invalid.
        """
        return cls(
            cosign_id=UUID(data["cosign_id"]),
            petition_id=UUID(data["petition_id"]),
            signer_id=UUID(data["signer_id"]),
            signed_at=datetime.fromisoformat(data["signed_at"]),
            content_hash=data["content_hash"],
            co_signer_count=data["co_signer_count"],
            identity_verified=data.get("identity_verified", False),
        )
