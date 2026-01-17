"""Governance event envelope domain model.

This module defines the canonical event envelope structure for the consent-based
governance system as specified in governance-architecture.md.

Event Envelope Pattern (Locked):
{
  "metadata": {
    "event_id": "uuid",
    "event_type": "executive.task.accepted",
    "schema_version": "1.0.0",
    "timestamp": "2026-01-16T00:00:00Z",
    "actor_id": "archon-or-officer-id",
    "trace_id": "correlation-id",
    "prev_hash": "blake3:abc123...",
    "hash": "blake3:def456..."
  },
  "payload": {
    // Domain-specific event data
  }
}

Hash fields (prev_hash, hash) added in story consent-gov-1-3.
- prev_hash: Links to previous event's hash (genesis uses all-zeros)
- hash: Computed from canonical_json(metadata_without_hash) + canonical_json(payload)

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → Validation errors raise, never silently pass
- CT-12: Witnessing creates accountability → All events attributable via actor_id
- CT-13: Integrity outranks availability → Invalid events rejected
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.governance.events.event_types import derive_branch, validate_event_type
from src.domain.governance.events.schema_versions import (
    CURRENT_SCHEMA_VERSION,
    validate_schema_version,
)


@dataclass(frozen=True, eq=True)
class EventMetadata:
    """Immutable metadata for governance events.

    Per governance-architecture.md, all governance events share common metadata
    fields that enable tracking, validation, and replay.

    Attributes:
        event_id: Unique identifier for this event (UUID).
        event_type: Type classification following branch.noun.verb convention.
        timestamp: When the event occurred (UTC datetime).
        actor_id: ID of the archon or officer that caused the event.
        schema_version: Semver version for deterministic replay.
        trace_id: Correlation ID for request tracing.
        prev_hash: Hash of previous event (empty until persisted, genesis uses zeros).
        hash: Hash of this event (empty until computed by hash chain).

    Hash fields (prev_hash, hash) per story consent-gov-1-3:
    - Empty strings ("") when event is first created
    - Set by hash chain computation before persistence
    - Format: "algorithm:hex_digest" (e.g., "blake3:abc123...")
    """

    event_id: UUID
    event_type: str
    timestamp: datetime
    actor_id: str
    schema_version: str
    trace_id: str
    prev_hash: str = ""
    hash: str = ""

    def __post_init__(self) -> None:
        """Validate all metadata fields.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_event_id()
        self._validate_event_type()
        self._validate_timestamp()
        self._validate_actor_id()
        self._validate_schema_version()
        self._validate_trace_id()

    def _validate_event_id(self) -> None:
        """Validate event_id is UUID."""
        if not isinstance(self.event_id, UUID):
            raise ConstitutionalViolationError(
                f"AD-4: Event metadata validation failed - "
                f"event_id must be UUID, got {type(self.event_id).__name__}"
            )

    def _validate_event_type(self) -> None:
        """Validate event_type follows branch.noun.verb convention."""
        validate_event_type(self.event_type)

    def _validate_timestamp(self) -> None:
        """Validate timestamp is datetime."""
        if not isinstance(self.timestamp, datetime):
            raise ConstitutionalViolationError(
                f"AD-4: Event metadata validation failed - "
                f"timestamp must be datetime, got {type(self.timestamp).__name__}"
            )

    def _validate_actor_id(self) -> None:
        """Validate actor_id is non-empty string."""
        if not isinstance(self.actor_id, str):
            raise ConstitutionalViolationError(
                f"AD-4: Event metadata validation failed - "
                f"actor_id must be string, got {type(self.actor_id).__name__}"
            )
        if not self.actor_id.strip():
            raise ConstitutionalViolationError(
                "AD-4: Event metadata validation failed - "
                "actor_id must be non-empty string"
            )

    def _validate_schema_version(self) -> None:
        """Validate schema_version is valid semver."""
        validate_schema_version(self.schema_version)

    def _validate_trace_id(self) -> None:
        """Validate trace_id is non-empty string."""
        if not isinstance(self.trace_id, str):
            raise ConstitutionalViolationError(
                f"AD-4: Event metadata validation failed - "
                f"trace_id must be string, got {type(self.trace_id).__name__}"
            )
        if not self.trace_id.strip():
            raise ConstitutionalViolationError(
                "AD-4: Event metadata validation failed - "
                "trace_id must be non-empty string"
            )

    @property
    def branch(self) -> str:
        """Derive branch from event_type.

        Per AD-15: Branch is derived at write-time, never trusted from caller.
        """
        return derive_branch(self.event_type)

    def __hash__(self) -> int:
        """Hash based on event_id (unique identifier)."""
        return hash(self.event_id)


@dataclass(frozen=True, eq=True)
class GovernanceEvent:
    """Canonical event envelope for governance system.

    Per governance-architecture.md, all governance events use this envelope
    structure with metadata and payload separation. This enables:
    - Consistent validation across all event types
    - Deterministic replay via schema versioning
    - External verification via hash chaining (added in story 1-3)
    - Request tracing via trace_id

    Attributes:
        metadata: Event metadata (event_id, type, timestamp, actor, etc.)
        payload: Domain-specific event data (immutable MappingProxyType)

    Both fields are immutable after creation.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> metadata = EventMetadata(
        ...     event_id=uuid4(),
        ...     event_type="executive.task.accepted",
        ...     timestamp=datetime.now(timezone.utc),
        ...     actor_id="archon-42",
        ...     schema_version="1.0.0",
        ...     trace_id="req-12345",
        ... )
        >>> event = GovernanceEvent(
        ...     metadata=metadata,
        ...     payload={"task_id": "task-001", "accepted_at": "2026-01-16"},
        ... )
        >>> event.metadata.branch
        'executive'
    """

    metadata: EventMetadata
    payload: MappingProxyType[str, Any] | dict[str, Any]

    def __post_init__(self) -> None:
        """Validate and freeze payload.

        Raises:
            ConstitutionalViolationError: If validation fails.
        """
        self._validate_metadata()
        self._freeze_payload()

    def _validate_metadata(self) -> None:
        """Validate metadata is EventMetadata instance."""
        if not isinstance(self.metadata, EventMetadata):
            raise ConstitutionalViolationError(
                f"AD-4: GovernanceEvent validation failed - "
                f"metadata must be EventMetadata, got {type(self.metadata).__name__}"
            )

    def _freeze_payload(self) -> None:
        """Convert payload dict to immutable MappingProxyType."""
        if isinstance(self.payload, MappingProxyType):
            pass  # Already frozen
        elif isinstance(self.payload, dict):
            # Convert mutable dict to immutable MappingProxyType
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, "payload", MappingProxyType(self.payload))
        else:
            raise ConstitutionalViolationError(
                f"AD-4: GovernanceEvent validation failed - "
                f"payload must be dict, got {type(self.payload).__name__}"
            )

    @property
    def event_id(self) -> UUID:
        """Convenience accessor for metadata.event_id."""
        return self.metadata.event_id

    @property
    def event_type(self) -> str:
        """Convenience accessor for metadata.event_type."""
        return self.metadata.event_type

    @property
    def branch(self) -> str:
        """Convenience accessor for derived branch."""
        return self.metadata.branch

    @property
    def timestamp(self) -> datetime:
        """Convenience accessor for metadata.timestamp."""
        return self.metadata.timestamp

    @property
    def actor_id(self) -> str:
        """Convenience accessor for metadata.actor_id."""
        return self.metadata.actor_id

    @property
    def schema_version(self) -> str:
        """Convenience accessor for metadata.schema_version."""
        return self.metadata.schema_version

    @property
    def trace_id(self) -> str:
        """Convenience accessor for metadata.trace_id."""
        return self.metadata.trace_id

    @property
    def prev_hash(self) -> str:
        """Convenience accessor for metadata.prev_hash."""
        return self.metadata.prev_hash

    @property
    def hash(self) -> str:
        """Convenience accessor for metadata.hash."""
        return self.metadata.hash

    def has_hash(self) -> bool:
        """Check if event has computed hash fields.

        Returns:
            True if both prev_hash and hash are non-empty.
        """
        return bool(self.metadata.prev_hash and self.metadata.hash)

    def __hash__(self) -> int:
        """Hash based on event_id (unique identifier).

        Note: payload is excluded from hash since MappingProxyType is not hashable.
        """
        return hash(self.metadata.event_id)

    @classmethod
    def create(
        cls,
        *,
        event_id: UUID,
        event_type: str,
        timestamp: datetime,
        actor_id: str,
        trace_id: str,
        payload: dict[str, Any],
        schema_version: str = CURRENT_SCHEMA_VERSION,
    ) -> GovernanceEvent:
        """Factory method to create a GovernanceEvent.

        This method creates both the EventMetadata and GovernanceEvent
        in a single call for convenience.

        Args:
            event_id: Unique identifier for this event.
            event_type: Type classification following branch.noun.verb convention.
            timestamp: When the event occurred (UTC datetime).
            actor_id: ID of the archon or officer that caused the event.
            trace_id: Correlation ID for request tracing.
            payload: Domain-specific event data.
            schema_version: Semver version (defaults to CURRENT_SCHEMA_VERSION).

        Returns:
            A new GovernanceEvent instance.

        Raises:
            ConstitutionalViolationError: If validation fails.
        """
        metadata = EventMetadata(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            actor_id=actor_id,
            schema_version=schema_version,
            trace_id=trace_id,
        )
        return cls(metadata=metadata, payload=payload)

    @classmethod
    def create_with_hash(
        cls,
        *,
        event_id: UUID,
        event_type: str,
        timestamp: datetime,
        actor_id: str,
        trace_id: str,
        payload: dict[str, Any],
        prev_event: "GovernanceEvent | None" = None,
        algorithm: str = "blake3",
        schema_version: str = CURRENT_SCHEMA_VERSION,
    ) -> "GovernanceEvent":
        """Factory method to create a GovernanceEvent with computed hash.

        This method creates a GovernanceEvent and computes the hash chain
        fields (prev_hash and hash) automatically.

        Args:
            event_id: Unique identifier for this event.
            event_type: Type classification following branch.noun.verb convention.
            timestamp: When the event occurred (UTC datetime).
            actor_id: ID of the archon or officer that caused the event.
            trace_id: Correlation ID for request tracing.
            payload: Domain-specific event data.
            prev_event: Previous event in the chain. If None, this is a genesis event.
            algorithm: Hash algorithm to use ('blake3' or 'sha256').
            schema_version: Semver version (defaults to CURRENT_SCHEMA_VERSION).

        Returns:
            A new GovernanceEvent instance with hash fields computed.

        Raises:
            ConstitutionalViolationError: If validation or hash computation fails.
        """
        # Import here to avoid circular dependency
        from src.domain.governance.events.hash_chain import add_hash_to_event

        # Create unhashed event first
        event = cls.create(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            actor_id=actor_id,
            trace_id=trace_id,
            payload=payload,
            schema_version=schema_version,
        )

        # Determine prev_hash
        prev_hash = prev_event.hash if prev_event else None

        # Add hash to event
        return add_hash_to_event(event, prev_hash, algorithm)
