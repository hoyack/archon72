"""Context Bundle Created event (Story 2.9, ADR-2).

Domain event for context bundle creation. This event is recorded when
a context bundle is created for agent deliberation.

Constitutional Constraints:
- CT-12: Witnessing creates accountability -> Event recorded for audit trail
- CT-1: LLMs are stateless -> Context bundles provide deterministic state
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.models.context_bundle import ContentRef, validate_content_ref

# Event type constant per architecture conventions
CONTEXT_BUNDLE_CREATED_EVENT_TYPE: str = "context.bundle.created"


@dataclass(frozen=True, eq=True)
class ContextBundleCreatedPayload:
    """Payload for context bundle created events.

    Captures the essential information when a context bundle is created
    for agent deliberation.

    Attributes:
        bundle_id: Unique bundle identifier (ctx_{meeting_id}_{seq}).
        meeting_id: UUID of the meeting for this bundle.
        as_of_event_seq: Sequence number anchor for determinism.
        identity_prompt_ref: ContentRef to agent identity.
        meeting_state_ref: ContentRef to meeting state.
        precedent_count: Number of precedent references included.
        bundle_hash: SHA-256 hash of bundle content.
        signing_key_id: ID of key used for signing.
        created_at: When bundle was created.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> payload = ContextBundleCreatedPayload(
        ...     bundle_id="ctx_abc_42",
        ...     meeting_id=uuid4(),
        ...     as_of_event_seq=42,
        ...     identity_prompt_ref="ref:" + "a" * 64,
        ...     meeting_state_ref="ref:" + "b" * 64,
        ...     precedent_count=3,
        ...     bundle_hash="c" * 64,
        ...     signing_key_id="key-001",
        ...     created_at=datetime.now(timezone.utc),
        ... )
    """

    bundle_id: str
    meeting_id: UUID
    as_of_event_seq: int
    identity_prompt_ref: ContentRef
    meeting_state_ref: ContentRef
    precedent_count: int
    bundle_hash: str
    signing_key_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate payload fields.

        Raises:
            ValueError: If any field has an invalid value.
            TypeError: If any field has an incorrect type.
        """
        # Bundle ID validation
        if not self.bundle_id:
            raise ValueError("bundle_id must be non-empty")
        if not self.bundle_id.startswith("ctx_"):
            raise ValueError("bundle_id must start with 'ctx_'")

        # Meeting ID type validation
        if not isinstance(self.meeting_id, UUID):
            raise TypeError(
                f"meeting_id must be UUID, got {type(self.meeting_id).__name__}"
            )

        # Sequence number validation
        if self.as_of_event_seq < 1:
            raise ValueError(
                f"as_of_event_seq must be >= 1, got {self.as_of_event_seq}"
            )

        # ContentRef validations
        validate_content_ref(self.identity_prompt_ref, "identity_prompt_ref")
        validate_content_ref(self.meeting_state_ref, "meeting_state_ref")

        # Precedent count validation
        if self.precedent_count < 0:
            raise ValueError(
                f"precedent_count must be >= 0, got {self.precedent_count}"
            )

        # Bundle hash validation
        if len(self.bundle_hash) != 64:
            raise ValueError(
                f"bundle_hash must be 64 character hex string, got {len(self.bundle_hash)}"
            )

        # Signing key ID validation
        if not self.signing_key_id:
            raise ValueError("signing_key_id must be non-empty")

        # Created at type validation
        if not isinstance(self.created_at, datetime):
            raise TypeError(
                f"created_at must be datetime, got {type(self.created_at).__name__}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event payload serialization.

        Returns:
            Dictionary with all fields serialized.
        """
        return {
            "bundle_id": self.bundle_id,
            "meeting_id": str(self.meeting_id),
            "as_of_event_seq": self.as_of_event_seq,
            "identity_prompt_ref": self.identity_prompt_ref,
            "meeting_state_ref": self.meeting_state_ref,
            "precedent_count": self.precedent_count,
            "bundle_hash": self.bundle_hash,
            "signing_key_id": self.signing_key_id,
            "created_at": self.created_at.isoformat(),
        }
