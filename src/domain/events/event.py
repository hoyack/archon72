"""Constitutional event entity (FR1, FR102-FR104).

This module defines the Event entity for the constitutional event store.
Events are immutable, append-only records that capture state changes
in the Archon 72 governance system.

Constitutional Constraints:
- FR1: Events must be witnessed
- FR2: Events must be hash-chained (Story 1.2)
- FR82: Hash chain continuity verification (Story 1.2)
- FR85: Hash algorithm version tracking (Story 1.2)
- FR102: Append-only enforcement (UPDATE, DELETE, TRUNCATE prohibited)
- FR103: Hash chaining (prev_hash links to previous event)
- FR104: Signature verification (Story 1.3)
- FR74: Agent signing key reference (Story 1.3)

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-12: Witnessing creates accountability → Unwitnessed actions are invalid
- CT-13: Integrity outranks availability → Availability may be sacrificed

Note: DeletePreventionMixin ensures `.delete()` raises
ConstitutionalViolationError before any DB interaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.events.hash_utils import (
    HASH_ALG_VERSION,
    compute_content_hash,
    get_prev_hash,
)
from src.domain.primitives import DeletePreventionMixin


@dataclass(frozen=True, eq=True)
class Event(DeletePreventionMixin):
    """Constitutional event - append-only, immutable.

    Events are the fundamental building blocks of the constitutional
    event store. Each event captures a witnessed state change and
    is linked to previous events via hash chaining.

    Constitutional Constraints:
    - FR1: Events must be witnessed (witness_id, witness_signature required)
    - FR102: Append-only enforcement (no UPDATE, DELETE, TRUNCATE)
    - FR103: Hash chaining (prev_hash links to previous event)
    - FR104: Signature verification (signature field)

    Attributes:
        event_id: Unique identifier for this event (UUID)
        sequence: Monotonic sequence number for ordering
        event_type: Type classification of the event
        payload: Structured event data
        prev_hash: Hash of previous event (chain verification)
        content_hash: Hash of this event content
        signature: Cryptographic signature of the event
        signing_key_id: ID of key used for signing (FR74)
        hash_alg_version: Version of hash algorithm used (default: 1)
        sig_alg_version: Version of signature algorithm used (default: 1)
        agent_id: ID of agent that created event (None for system events)
        witness_id: ID of witness that attested the event
        witness_signature: Signature of the witness
        local_timestamp: Timestamp from the event source
        authority_timestamp: Timestamp from time authority (set by DB)

    Note:
        DeletePreventionMixin ensures `.delete()` raises
        ConstitutionalViolationError before any DB interaction.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> event = Event(
        ...     event_id=uuid4(),
        ...     sequence=1,
        ...     event_type="vote.cast",
        ...     payload={"archon_id": 42, "vote": "aye"},
        ...     prev_hash="0" * 64,
        ...     content_hash="abc123...",
        ...     signature="sig123...",
        ...     witness_id="witness-001",
        ...     witness_signature="wsig123...",
        ...     local_timestamp=datetime.now(timezone.utc),
        ... )
        >>> event.delete()  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        ConstitutionalViolationError: FR80: Deletion prohibited...
    """

    # Primary identifier
    event_id: UUID

    # Sequence for ordering (append-only)
    sequence: int

    # Event type classification
    event_type: str

    # Event payload (structured data) - stored as immutable MappingProxyType
    # Pass a regular dict, it will be converted to MappingProxyType in __post_init__
    payload: MappingProxyType[str, Any] | dict[str, Any]

    # Hash chain fields (FR103)
    prev_hash: str
    content_hash: str

    # Signature field (FR104)
    signature: str

    # Witness attribution (FR1 - required for validity)
    witness_id: str
    witness_signature: str

    # Local timestamp from event source
    local_timestamp: datetime

    # Algorithm versioning for future upgrades
    hash_alg_version: int = field(default=1)
    sig_alg_version: int = field(default=1)

    # Signing key reference (FR74)
    signing_key_id: str = field(default="")

    # Agent attribution (nullable for system events)
    agent_id: str | None = field(default=None)

    # Authority timestamp (set by database)
    authority_timestamp: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate fields and freeze payload dict.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_event_id()
        self._validate_sequence()
        self._validate_event_type()
        self._freeze_payload()
        self._validate_hash_fields()
        self._validate_signature()
        self._validate_witness_fields()
        self._validate_timestamp()

    def _validate_event_id(self) -> None:
        """Validate event_id is UUID."""
        if not isinstance(self.event_id, UUID):
            raise ConstitutionalViolationError(
                f"FR102: Event validation failed - event_id must be UUID, got {type(self.event_id).__name__}"
            )

    def _validate_sequence(self) -> None:
        """Validate sequence is non-negative integer."""
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise ConstitutionalViolationError(
                f"FR102: Event validation failed - sequence must be non-negative integer, got {self.sequence}"
            )

    def _validate_event_type(self) -> None:
        """Validate event_type is non-empty string."""
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ConstitutionalViolationError(
                "FR102: Event validation failed - event_type must be non-empty string"
            )

    def _freeze_payload(self) -> None:
        """Validate and freeze payload dict."""
        if isinstance(self.payload, MappingProxyType):
            pass  # Already frozen
        elif isinstance(self.payload, dict):
            # Convert mutable dict to immutable MappingProxyType
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, "payload", MappingProxyType(self.payload))
        else:
            raise ConstitutionalViolationError(
                f"FR102: Event validation failed - payload must be dict, got {type(self.payload).__name__}"
            )

    def _validate_hash_fields(self) -> None:
        """Validate hash fields are non-empty strings."""
        if not isinstance(self.prev_hash, str) or not self.prev_hash:
            raise ConstitutionalViolationError(
                "FR102: Event validation failed - prev_hash must be non-empty string"
            )
        if not isinstance(self.content_hash, str) or not self.content_hash:
            raise ConstitutionalViolationError(
                "FR102: Event validation failed - content_hash must be non-empty string"
            )

    def _validate_signature(self) -> None:
        """Validate signature is non-empty string."""
        if not isinstance(self.signature, str) or not self.signature:
            raise ConstitutionalViolationError(
                "FR102: Event validation failed - signature must be non-empty string"
            )

    def _validate_witness_fields(self) -> None:
        """Validate witness fields (FR1 - witnessing required)."""
        if not isinstance(self.witness_id, str) or not self.witness_id.strip():
            raise ConstitutionalViolationError(
                "FR1: Event validation failed - witness_id must be non-empty string (witnessing required)"
            )
        if not isinstance(self.witness_signature, str) or not self.witness_signature:
            raise ConstitutionalViolationError(
                "FR1: Event validation failed - witness_signature must be non-empty string (witnessing required)"
            )

    def _validate_timestamp(self) -> None:
        """Validate local_timestamp is datetime."""
        if not isinstance(self.local_timestamp, datetime):
            raise ConstitutionalViolationError(
                f"FR102: Event validation failed - local_timestamp must be datetime, got {type(self.local_timestamp).__name__}"
            )

    def __hash__(self) -> int:
        """Hash based on event_id (unique identifier).

        Note: payload is excluded from hash since MappingProxyType is not hashable.
        Two events with same event_id are considered equal (same event).
        """
        return hash(self.event_id)

    @classmethod
    def create_with_hash(
        cls,
        *,
        sequence: int,
        event_type: str,
        payload: dict[str, Any],
        signature: str,
        witness_id: str,
        witness_signature: str,
        local_timestamp: datetime,
        previous_content_hash: str | None = None,
        agent_id: str | None = None,
        signing_key_id: str = "",
        event_id: UUID | None = None,
    ) -> Event:
        """Factory method to create an Event with computed content_hash and prev_hash.

        This method automatically computes the content_hash using SHA-256 and
        determines the correct prev_hash based on the sequence number.

        Args:
            sequence: The sequence number for this event (1 for first event).
            event_type: Type classification of the event.
            payload: Structured event data.
            signature: Cryptographic signature of the event.
            witness_id: ID of the witness that attested the event.
            witness_signature: Signature of the witness.
            local_timestamp: Timestamp from the event source.
            previous_content_hash: Content hash of the previous event.
                Required for sequence > 1. Ignored for sequence 1.
            agent_id: ID of agent that created event (None for system events).
            signing_key_id: ID of key used for signing (FR74).
            event_id: Optional UUID for the event. If not provided, generates a new one.

        Returns:
            A new Event instance with computed hashes.

        Raises:
            ValueError: If sequence > 1 and previous_content_hash is not provided.
            ConstitutionalViolationError: If event validation fails.

        Example:
            >>> from datetime import datetime, timezone
            >>> event = Event.create_with_hash(
            ...     sequence=1,
            ...     event_type="vote.cast",
            ...     payload={"archon_id": 42, "vote": "aye"},
            ...     signature="sig123",
            ...     witness_id="witness-001",
            ...     witness_signature="wsig123",
            ...     local_timestamp=datetime.now(timezone.utc),
            ... )
            >>> event.prev_hash == GENESIS_HASH
            True
            >>> len(event.content_hash)
            64
        """
        # Compute prev_hash based on sequence
        prev_hash = get_prev_hash(
            sequence=sequence,
            previous_content_hash=previous_content_hash,
        )

        # Build event data for content hash computation
        event_data = {
            "event_type": event_type,
            "payload": payload,
            "signature": signature,
            "witness_id": witness_id,
            "witness_signature": witness_signature,
            "local_timestamp": local_timestamp,
            "agent_id": agent_id,
        }

        # Compute content hash
        content_hash = compute_content_hash(event_data)

        # Create and return the Event
        return cls(
            event_id=event_id or uuid4(),
            sequence=sequence,
            event_type=event_type,
            payload=payload,
            prev_hash=prev_hash,
            content_hash=content_hash,
            signature=signature,
            hash_alg_version=HASH_ALG_VERSION,
            sig_alg_version=1,
            signing_key_id=signing_key_id,
            agent_id=agent_id,
            witness_id=witness_id,
            witness_signature=witness_signature,
            local_timestamp=local_timestamp,
        )
