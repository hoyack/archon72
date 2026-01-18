"""Observer API response models (Story 4.1, Task 1; Story 4.2, Tasks 1, 3, 5; Story 4.3, Task 5; Story 4.5, Tasks 1, 6; Story 4.6, Task 1; Story 4.8, Task 1; Story 4.9, Task 1; Story 7.5, Task 8).

Pydantic models for the public observer API endpoints.
These models expose all event data for independent verification.

Architecture Note:
Shared Pydantic models (used by both API and Application layers) are now
defined in src.application.dtos.observer and re-exported here for backward
compatibility. This ensures dependency flows inward (API -> Application).

Constitutional Constraints:
- FR42: Read-only access indefinitely after cessation
- FR44: Public read access without registration
- FR45: Raw events with hashes returned
- FR46: Query interface supports date range and event type filtering
- FR62: Raw event data sufficient for independent hash computation
- FR63: Exact hash algorithm, encoding, field ordering as immutable spec
- FR88: Query for state as of any sequence number or timestamp
- FR89: Historical queries return hash chain proof to current head
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Observers SHALL be able to verify event inclusion without downloading full chain
- FR138: Weekly checkpoint anchors SHALL be published at consistent intervals
- SR-9: Observer push notifications - webhook/SSE for breach events
- RT-5: Breach events pushed to multiple channels, 99.9% uptime SLA
- CT-11: Silent failure destroys legitimacy - notification delivery must be logged
- CT-12: Witnessing creates accountability - notification events have attribution
- ADR-8: Observer Consistency + Genesis Anchor - checkpoint fallback during outage
- All hash chain data must be exposed for verification
- No fields hidden from observers
"""

import hashlib
import ipaddress
import json
import socket
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, PlainSerializer, field_validator

# Re-export shared Pydantic models from application DTOs
# These models are defined in the application layer to maintain proper dependency direction
from src.application.dtos.observer import (  # noqa: F401
    CheckpointAnchor,
    HashChainProof,
    HashChainProofEntry,
    MerkleProof,
    MerkleProofEntry,
    NotificationEventType,
    NotificationPayload,
    WebhookSubscription,
    WebhookSubscriptionResponse,
)

# Explicit re-exports for public API
__all__ = [
    "CheckpointAnchor",
    "HashChainProof",
    "HashChainProofEntry",
    "MerkleProof",
    "MerkleProofEntry",
    "NotificationEventType",
    "NotificationPayload",
    "WebhookSubscription",
    "WebhookSubscriptionResponse",
]

# Note: The above models are now defined in src.application.dtos.observer
# and re-exported here for backward compatibility with existing API routes.

# SSRF protection constants are kept here as they're only used by API-specific models
_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "169.254.169.254",  # AWS/GCP metadata
        "metadata.google.internal",  # GCP metadata
        "metadata.google.com",
    }
)

_BLOCKED_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),  # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),  # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),  # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / metadata
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
)


# Custom datetime serializer for ISO 8601 with Z suffix (Pydantic v2)
DateTimeWithZ = Annotated[
    datetime,
    PlainSerializer(lambda v: v.isoformat() + "Z" if v else None, return_type=str),
]


class ObserverEventResponse(BaseModel):
    """Single event response for observer API.

    Includes all hash chain data for independent verification.
    Per FR44: No fields are hidden from observers.
    Per FR45: Raw events with all hashes for verification.

    Attributes:
        event_id: Unique identifier for this event.
        sequence: Monotonic sequence number for ordering.
        event_type: Type classification of the event.
        payload: Structured event data.
        content_hash: Hash of this event content.
        prev_hash: Hash of previous event (chain verification).
        signature: Cryptographic signature of the event.
        agent_id: ID of agent that created event.
        witness_id: ID of witness that attested the event.
        witness_signature: Signature of the witness.
        local_timestamp: Timestamp from the event source.
        authority_timestamp: Timestamp from time authority (optional).
        hash_algorithm_version: Version of hash algorithm used.
        sig_alg_version: Version of signature algorithm used (FR45, AC3).
    """

    event_id: UUID
    sequence: int
    event_type: str
    payload: dict[str, Any]
    content_hash: str
    prev_hash: str
    signature: str
    agent_id: str
    witness_id: str
    witness_signature: str
    local_timestamp: DateTimeWithZ
    authority_timestamp: DateTimeWithZ | None = None
    hash_algorithm_version: str = Field(default="SHA256")
    sig_alg_version: str = Field(default="Ed25519")

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "sequence": 42,
                "event_type": "vote.cast",
                "payload": {"archon_id": 1, "vote": "aye"},
                "content_hash": "a" * 64,
                "prev_hash": "b" * 64,
                "signature": "sig123...",
                "agent_id": "agent-001",
                "witness_id": "witness-001",
                "witness_signature": "wsig123...",
                "local_timestamp": "2025-12-27T10:30:00Z",
                "authority_timestamp": "2025-12-27T10:30:00Z",
                "hash_algorithm_version": "SHA256",
                "sig_alg_version": "Ed25519",
            }
        },
    }

    def compute_expected_hash(self) -> str:
        """Compute expected content_hash from event fields (FR62).

        This method allows observers to independently verify
        the content_hash using the documented specification.

        The hash is computed from these fields:
        - event_type
        - payload
        - signature
        - witness_id
        - witness_signature
        - local_timestamp (ISO 8601 format)
        - agent_id (if non-empty)

        Fields NOT included (per HashVerificationSpec):
        - prev_hash, content_hash, sequence, authority_timestamp
        - hash_alg_version, sig_alg_version (metadata)

        Returns:
            The computed SHA-256 hash in lowercase hex (64 chars).
        """
        hashable: dict[str, Any] = {
            "event_type": self.event_type,
            "payload": self.payload,
            "signature": self.signature,
            "witness_id": self.witness_id,
            "witness_signature": self.witness_signature,
            "local_timestamp": self.local_timestamp.isoformat(),
        }

        # Only include agent_id if non-empty
        if self.agent_id:
            hashable["agent_id"] = self.agent_id

        # Canonical JSON: sorted keys, no whitespace
        canonical = json.dumps(
            hashable,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PaginationMetadata(BaseModel):
    """Pagination metadata for list responses.

    Attributes:
        total_count: Total number of items available.
        offset: Number of items skipped.
        limit: Maximum items per page.
        has_more: Whether more items exist beyond current page.
    """

    total_count: int
    offset: int
    limit: int
    has_more: bool

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_count": 1000,
                "offset": 0,
                "limit": 100,
                "has_more": True,
            }
        },
    }


class ObserverEventsListResponse(BaseModel):
    """List response for observer events query (enhanced for Story 4.5, 4.6).

    Supports historical queries per FR88, FR89 and Merkle proofs per FR136, FR137.

    Attributes:
        events: List of event responses.
        pagination: Pagination metadata.
        historical_query: Metadata when as_of_sequence/timestamp is used (FR88).
        proof: Hash chain proof to current head (FR89).
        merkle_proof: Merkle proof for O(log n) verification (FR136).
    """

    events: list[ObserverEventResponse]
    pagination: PaginationMetadata

    # Historical query fields (FR88, FR89) - added in Story 4.5
    historical_query: Optional["HistoricalQueryMetadata"] = Field(
        default=None,
        description="Metadata when as_of_sequence/timestamp is used (FR88)",
    )
    proof: Optional["HashChainProof"] = Field(
        default=None,
        description="Hash chain proof to current head (FR89)",
    )

    # Merkle proof field (FR136, FR137) - added in Story 4.6
    merkle_proof: Optional["MerkleProof"] = Field(
        default=None,
        description="Merkle proof for O(log n) verification (FR136). Only available for checkpointed events.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "events": [
                    {
                        "event_id": "550e8400-e29b-41d4-a716-446655440000",
                        "sequence": 1,
                        "event_type": "system.genesis",
                        "payload": {},
                        "content_hash": "a" * 64,
                        "prev_hash": "0" * 64,
                        "signature": "sig...",
                        "agent_id": "system",
                        "witness_id": "witness-001",
                        "witness_signature": "wsig...",
                        "local_timestamp": "2025-12-27T10:30:00Z",
                        "hash_algorithm_version": "SHA256",
                    }
                ],
                "pagination": {
                    "total_count": 100,
                    "offset": 0,
                    "limit": 100,
                    "has_more": False,
                },
            }
        },
    }


class HashVerificationSpec(BaseModel):
    """Hash verification specification for independent verification (FR62, FR63).

    Documents the exact hash computation method for observers to independently
    verify chain integrity. This specification is immutable - any changes
    require a new version.

    Constitutional Constraints:
    - FR62: Raw event data sufficient for independent hash computation
    - FR63: Exact hash algorithm, encoding, field ordering as immutable spec
    - AC4: Genesis hash documented
    - AC5: Canonical JSON specification documented

    Attributes:
        hash_algorithm: Hash algorithm name (SHA-256).
        hash_algorithm_version: Numeric version of hash algorithm.
        signature_algorithm: Signature algorithm name (Ed25519).
        signature_algorithm_version: Numeric version of signature algorithm.
        genesis_hash: Hash value for first event's prev_hash (64 zeros).
        genesis_description: Human-readable explanation of genesis hash.
        hash_includes: List of fields included in content_hash computation.
        hash_excludes: List of fields excluded from content_hash (with reasons).
        json_canonicalization: Rules for deterministic JSON serialization.
        hash_encoding: Format of the hash output.
    """

    hash_algorithm: str = Field(default="SHA-256")
    hash_algorithm_version: int = Field(default=1)
    signature_algorithm: str = Field(default="Ed25519")
    signature_algorithm_version: int = Field(default=1)
    genesis_hash: str = Field(default="0" * 64)
    genesis_description: str = Field(
        default="64 zeros representing no previous event (sequence 1)"
    )

    # Fields included in content_hash computation
    hash_includes: list[str] = Field(
        default=[
            "event_type",
            "payload",
            "signature",
            "witness_id",
            "witness_signature",
            "local_timestamp",
            "agent_id (if present)",
        ]
    )

    # Fields excluded from hash (with reasons)
    hash_excludes: list[str] = Field(
        default=[
            "prev_hash (would create circular dependency)",
            "content_hash (self-reference)",
            "sequence (assigned by database)",
            "authority_timestamp (set by database)",
            "hash_alg_version (metadata, not content)",
            "sig_alg_version (metadata, not content)",
        ]
    )

    # JSON canonicalization rules
    json_canonicalization: str = Field(
        default=(
            "Keys sorted alphabetically (recursive), no whitespace between "
            "elements (separators=(',', ':')), ensure_ascii=False"
        )
    )

    # Hash encoding
    hash_encoding: str = Field(default="lowercase hexadecimal (64 characters)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "hash_algorithm": "SHA-256",
                "hash_algorithm_version": 1,
                "signature_algorithm": "Ed25519",
                "signature_algorithm_version": 1,
                "genesis_hash": "0" * 64,
                "genesis_description": "64 zeros representing no previous event (sequence 1)",
                "hash_includes": [
                    "event_type",
                    "payload",
                    "signature",
                    "witness_id",
                    "witness_signature",
                    "local_timestamp",
                    "agent_id (if present)",
                ],
                "hash_excludes": [
                    "prev_hash (would create circular dependency)",
                    "content_hash (self-reference)",
                    "sequence (assigned by database)",
                ],
                "json_canonicalization": "Keys sorted alphabetically, no whitespace",
                "hash_encoding": "lowercase hexadecimal (64 characters)",
            }
        },
    }


class ChainVerificationResult(BaseModel):
    """Result of chain verification request (FR64).

    Per FR64: Verification bundles for offline verification.

    Attributes:
        start_sequence: First sequence number verified.
        end_sequence: Last sequence number verified.
        is_valid: Whether the chain is valid.
        first_invalid_sequence: First sequence where validation failed.
        error_message: Description of the validation error.
        verified_count: Number of events successfully verified.
    """

    start_sequence: int
    end_sequence: int
    is_valid: bool
    first_invalid_sequence: int | None = None
    error_message: str | None = None
    verified_count: int

    model_config = {
        "json_schema_extra": {
            "example": {
                "start_sequence": 1,
                "end_sequence": 100,
                "is_valid": True,
                "first_invalid_sequence": None,
                "error_message": None,
                "verified_count": 100,
            }
        },
    }


class SchemaDocumentation(BaseModel):
    """Schema documentation for Observer API (FR50).

    Versioned schemas with same availability as event store.

    Constitutional Constraints:
    - FR50: Schema documentation SHALL have same availability as event store

    Attributes:
        schema_version: Version of the schema document.
        api_version: Version of the API.
        last_updated: When the schema was last updated.
        event_types: List of all supported event types.
        event_schema: JSON Schema for event format.
        verification_spec_url: URL for hash verification specification.
    """

    schema_version: str = Field(default="1.0.0")
    api_version: str = Field(default="v1")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    event_types: list[str] = Field(
        default=[
            "vote",
            "halt",
            "breach",
            "deliberation",
            "override",
            "ceremony",
            "heartbeat",
            "fork_detected",
            "constitutional_crisis",
        ]
    )

    event_schema: dict[str, Any] = Field(
        default={
            "type": "object",
            "required": [
                "event_id",
                "sequence",
                "event_type",
                "payload",
                "content_hash",
                "prev_hash",
                "signature",
                "witness_id",
                "witness_signature",
                "local_timestamp",
                "hash_algorithm_version",
                "sig_alg_version",
            ],
            "properties": {
                "event_id": {"type": "string", "format": "uuid"},
                "sequence": {"type": "integer", "minimum": 1},
                "event_type": {"type": "string"},
                "payload": {"type": "object"},
                "content_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "prev_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "signature": {"type": "string"},
                "agent_id": {"type": "string", "nullable": True},
                "witness_id": {"type": "string"},
                "witness_signature": {"type": "string"},
                "local_timestamp": {"type": "string", "format": "date-time"},
                "authority_timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "nullable": True,
                },
                "hash_algorithm_version": {"type": "string"},
                "sig_alg_version": {"type": "string"},
            },
        }
    )

    verification_spec_url: str = Field(
        default="/v1/observer/verification-spec",
        description="Endpoint for hash verification specification",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "schema_version": "1.0.0",
                "api_version": "v1",
                "last_updated": "2026-01-07T00:00:00Z",
                "event_types": ["vote", "halt", "breach"],
                "event_schema": {
                    "type": "object",
                    "required": ["event_id", "sequence"],
                },
                "verification_spec_url": "/v1/observer/verification-spec",
            }
        }
    }


class EventFilterParams(BaseModel):
    """Filter parameters for event queries (FR46).

    All filters are optional. When multiple filters are provided,
    they are combined with AND logic.

    Date range filters apply to authority_timestamp (the authoritative
    time from the time authority service).

    Event types support OR semantics - events matching ANY of the
    specified types will be returned.

    Constitutional Constraints:
    - FR46: Query interface SHALL support date range and event type filtering

    Attributes:
        start_date: Filter events from this timestamp (inclusive, ISO 8601).
        end_date: Filter events until this timestamp (inclusive, ISO 8601).
        event_type: Filter by event type(s), comma-separated for multiple.
    """

    start_date: datetime | None = Field(
        default=None,
        description="Filter events from this date (ISO 8601 format, e.g., 2026-01-01T00:00:00Z)",
        json_schema_extra={"example": "2026-01-01T00:00:00Z"},
    )
    end_date: datetime | None = Field(
        default=None,
        description="Filter events until this date (ISO 8601 format, e.g., 2026-01-31T23:59:59Z)",
        json_schema_extra={"example": "2026-01-31T23:59:59Z"},
    )
    event_type: str | None = Field(
        default=None,
        description="Filter by event type(s), comma-separated for multiple (e.g., vote,halt,breach)",
        json_schema_extra={"example": "vote,halt,breach"},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Date range with multiple event types",
                    "start_date": "2026-01-01T00:00:00Z",
                    "end_date": "2026-01-31T23:59:59Z",
                    "event_type": "vote,halt",
                },
                {
                    "description": "Start date only with single type",
                    "start_date": "2026-01-15T00:00:00Z",
                    "event_type": "breach",
                },
                {
                    "description": "End date only (all events before date)",
                    "end_date": "2026-01-31T23:59:59Z",
                },
                {
                    "description": "Event type only (all time)",
                    "event_type": "vote",
                },
            ]
        }
    }


# =============================================================================
# Historical Query Models (Story 4.5 - FR88, FR89)
# =============================================================================
# Note: HashChainProofEntry and HashChainProof are imported from
# src.application.dtos.observer to maintain single source of truth.


class HistoricalQueryMetadata(BaseModel):
    """Metadata for historical queries (FR88).

    Included when as_of_sequence or as_of_timestamp is specified.
    Provides context about what was queried and the current state.

    Per FR88: Observer interface SHALL support queries for system
    state as of any past sequence number or timestamp.

    Attributes:
        queried_as_of_sequence: Sequence number queried (if specified).
        queried_as_of_timestamp: Timestamp queried (if specified).
        resolved_sequence: Actual sequence number used for query.
        current_head_sequence: Current head sequence at time of query.
    """

    queried_as_of_sequence: int | None = Field(
        default=None,
        description="Sequence number queried (if specified)",
    )
    queried_as_of_timestamp: datetime | None = Field(
        default=None,
        description="Timestamp queried (if specified)",
    )
    resolved_sequence: int = Field(
        description="Actual sequence number used for query",
    )
    current_head_sequence: int = Field(
        description="Current head sequence at time of query",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "queried_as_of_sequence": 500,
                "resolved_sequence": 500,
                "current_head_sequence": 1000,
            }
        },
    }


# =============================================================================
# Merkle Proof Models (Story 4.6 - FR136, FR137, FR138)
# =============================================================================


class MerkleProofEntry(BaseModel):
    """Single sibling hash in Merkle proof path (FR136).

    Each entry represents one level of the Merkle tree,
    containing the sibling hash needed to compute the parent.

    Attributes:
        level: Tree level (0 = leaf level).
        position: Left or right sibling position.
        sibling_hash: Hash of the sibling node.
    """

    level: int = Field(ge=0, description="Tree level (0 = leaves)")
    position: Literal["left", "right"] = Field(
        description="Position of sibling relative to path (left or right)",
    )
    sibling_hash: str = Field(
        description="SHA-256 hash of sibling node",
        pattern=r"^[a-f0-9]{64}$",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "level": 0,
                "position": "right",
                "sibling_hash": "a" * 64,
            }
        },
    }


class MerkleProof(BaseModel):
    """Merkle proof connecting event to checkpoint root (FR136).

    Contains the path of sibling hashes needed to recompute
    the Merkle root from the event's content_hash.

    Per FR136: Merkle proof SHALL be included in event query
    responses when requested.

    Attributes:
        event_sequence: Sequence number of the proven event.
        event_hash: Content hash of the proven event.
        checkpoint_sequence: Sequence of checkpoint containing this event.
        checkpoint_root: Merkle root of the checkpoint.
        path: List of sibling hashes from leaf to root.
        tree_size: Total number of leaves in the Merkle tree.
        proof_type: Always "merkle" for this proof type.
        generated_at: When this proof was generated.
    """

    event_sequence: int = Field(ge=1, description="Sequence of proven event")
    event_hash: str = Field(
        description="Content hash of proven event",
        pattern=r"^[a-f0-9]{64}$",
    )
    checkpoint_sequence: int = Field(
        ge=1,
        description="Sequence number of checkpoint containing this event",
    )
    checkpoint_root: str = Field(
        description="Merkle root of the checkpoint",
        pattern=r"^[a-f0-9]{64}$",
    )
    path: list[MerkleProofEntry] = Field(
        description="Sibling hashes from leaf to root",
    )
    tree_size: int = Field(ge=1, description="Number of leaves in tree")
    proof_type: str = Field(
        default="merkle",
        description="Type of proof (merkle)",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this proof was generated",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_sequence": 42,
                "event_hash": "a" * 64,
                "checkpoint_sequence": 100,
                "checkpoint_root": "b" * 64,
                "path": [
                    {"level": 0, "position": "right", "sibling_hash": "c" * 64},
                    {"level": 1, "position": "left", "sibling_hash": "d" * 64},
                ],
                "tree_size": 100,
                "proof_type": "merkle",
                "generated_at": "2026-01-07T00:00:00Z",
            }
        },
    }


class CheckpointAnchor(BaseModel):
    """Checkpoint anchor with Merkle root (FR137, FR138).

    Represents a weekly checkpoint that anchors a range of events.
    Per FR138: Weekly checkpoint anchors SHALL be published at
    consistent intervals.

    Attributes:
        checkpoint_id: Unique identifier for checkpoint.
        sequence_start: First event sequence in checkpoint.
        sequence_end: Last event sequence in checkpoint.
        merkle_root: Root hash of Merkle tree for events in range.
        created_at: When checkpoint was created.
        anchor_type: Type of external anchor (genesis, rfc3161, pending).
        anchor_reference: External anchor ID/txid.
        event_count: Number of events in this checkpoint.
    """

    checkpoint_id: UUID
    sequence_start: int = Field(ge=1)
    sequence_end: int = Field(ge=1)
    merkle_root: str = Field(
        description="Merkle root hash",
        pattern=r"^[a-f0-9]{64}$",
    )
    created_at: datetime
    anchor_type: str = Field(
        default="pending",
        pattern=r"^(genesis|rfc3161|pending)$",
        description="Type of external anchor",
    )
    anchor_reference: str | None = Field(
        default=None,
        description="External anchor reference (Bitcoin txid, TSA response)",
    )
    event_count: int = Field(ge=0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "checkpoint_id": "550e8400-e29b-41d4-a716-446655440000",
                "sequence_start": 1,
                "sequence_end": 100,
                "merkle_root": "a" * 64,
                "created_at": "2026-01-05T00:00:00Z",
                "anchor_type": "pending",
                "anchor_reference": None,
                "event_count": 100,
            }
        },
    }


# =============================================================================
# Regulatory Export Models (Story 4.7 - FR139, FR140)
# =============================================================================


class ExportFormat(str, Enum):
    """Supported export formats (FR139).

    Per FR139: Export SHALL support structured audit format.

    Values:
        JSONL: JSON Lines format (one JSON object per line).
        CSV: Comma-separated values format (RFC 4180).
    """

    JSONL = "jsonl"
    CSV = "csv"


class AttestationMetadata(BaseModel):
    """Attestation metadata for regulatory export (FR140).

    Provides context and verification data for exported records.
    Third-party attestation services can use this metadata to
    verify export authenticity and completeness.

    Per FR140: Third-party attestation interface with metadata.

    Attributes:
        export_id: Unique identifier for this export.
        exported_at: When export was generated (UTC).
        sequence_start: First event sequence in export.
        sequence_end: Last event sequence in export.
        event_count: Number of events exported.
        filter_criteria: Filters applied to export (optional).
        chain_hash_at_export: Content hash of latest event at export time.
        export_signature: Signature of export metadata for verification (optional).
        exporter_id: ID of service that generated export.
    """

    export_id: UUID = Field(default_factory=uuid4)
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_start: int = Field(ge=1)
    sequence_end: int = Field(ge=1)
    event_count: int = Field(ge=0)
    filter_criteria: dict[str, Any] | None = None
    chain_hash_at_export: str = Field(
        description="Content hash of latest event at export time",
        pattern=r"^[a-f0-9]{64}$",
    )
    export_signature: str | None = Field(
        default=None,
        description="Signature of export metadata (HSM-signed when available)",
    )
    exporter_id: str = Field(default="archon72-observer-api")

    model_config = {
        "json_schema_extra": {
            "example": {
                "export_id": "550e8400-e29b-41d4-a716-446655440000",
                "exported_at": "2026-01-07T00:00:00Z",
                "sequence_start": 1,
                "sequence_end": 1000,
                "event_count": 1000,
                "filter_criteria": {"event_types": ["vote", "halt"]},
                "chain_hash_at_export": "a" * 64,
                "export_signature": None,
                "exporter_id": "archon72-observer-api",
            }
        },
    }


class RegulatoryExportResponse(BaseModel):
    """Response wrapper for regulatory export (FR139).

    Used for non-streaming responses or export metadata.

    Per FR139: Structured audit format export response.

    Attributes:
        format: Export format used (jsonl or csv).
        attestation: Attestation metadata if requested.
        data_url: URL to download export data (for large exports).
        inline_data: Export data inline (for small exports).
    """

    format: ExportFormat
    attestation: AttestationMetadata | None = None
    data_url: str | None = Field(
        default=None,
        description="URL to download export data (for large exports)",
    )
    inline_data: str | None = Field(
        default=None,
        description="Export data inline (for small exports)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "format": "jsonl",
                "attestation": None,
                "data_url": "/v1/observer/export/download/abc123",
                "inline_data": None,
            }
        },
    }


# =============================================================================
# Push Notification Models (Story 4.8 - SR-9, RT-5)
# =============================================================================


class NotificationEventType(str, Enum):
    """Event types that can trigger notifications (SR-9).

    Per SR-9: Observer push notifications for breach events.
    Per RT-5: Breach events pushed to multiple channels.

    Values:
        BREACH: Constitutional breach detected.
        HALT: System halt triggered.
        FORK: Fork detected in event chain.
        CONSTITUTIONAL_CRISIS: Constitutional crisis declared.
        ALL: Subscribe to all notification types.
    """

    BREACH = "breach"
    HALT = "halt"
    FORK = "fork"
    CONSTITUTIONAL_CRISIS = "constitutional_crisis"
    ALL = "all"


class WebhookSubscription(BaseModel):
    """Webhook subscription for push notifications (SR-9).

    Per SR-9: Register webhook for breach event notifications.
    Per RT-5: Breach events pushed to multiple channels.

    Security: SSRF protection per OWASP guidelines.
    - Only HTTPS URLs allowed (production security)
    - Private/internal network addresses blocked
    - Cloud metadata endpoints blocked
    - DNS resolution validated before acceptance

    Attributes:
        webhook_url: HTTPS URL for webhook delivery (external only).
        event_types: Event types to subscribe to.
        secret: Optional secret for webhook signature verification (min 32 chars).
    """

    webhook_url: Annotated[
        str, Field(description="HTTPS URL for webhook delivery (external only)")
    ]
    event_types: list[NotificationEventType] = Field(
        default=[NotificationEventType.ALL],
        description="Event types to subscribe to",
    )
    secret: str | None = Field(
        default=None,
        min_length=32,
        description="Secret for HMAC signature verification (optional, min 32 chars)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "webhook_url": "https://example.com/webhook",
                "event_types": ["breach", "halt"],
                "secret": None,
            }
        },
    }

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url_ssrf(cls, v: str) -> str:
        """Validate webhook URL to prevent SSRF attacks.

        Security checks per OWASP SSRF Prevention Cheat Sheet:
        1. Require HTTPS scheme only
        2. Block known dangerous hostnames (localhost, metadata endpoints)
        3. Resolve DNS and check against private IP ranges
        4. Block link-local, loopback, and private network addresses

        Args:
            v: The webhook URL to validate.

        Returns:
            The validated URL if safe.

        Raises:
            ValueError: If URL fails security validation.
        """
        url = str(v).strip()

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception:
            raise ValueError("Invalid URL format")

        # 1. Require HTTPS only (production security)
        if parsed.scheme != "https":
            raise ValueError(
                "webhook_url must use HTTPS scheme for security. "
                "HTTP is not allowed to prevent credential interception."
            )

        # 2. Extract and validate hostname
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("webhook_url must have a valid hostname")

        hostname_lower = hostname.lower()

        # 3. Block known dangerous hostnames
        if hostname_lower in _BLOCKED_HOSTS:
            raise ValueError(
                f"webhook_url hostname '{hostname}' is blocked. "
                "Internal and metadata endpoints are not allowed."
            )

        # 4. Check for cloud metadata patterns
        if "metadata" in hostname_lower or hostname_lower.endswith(".internal"):
            raise ValueError(
                f"webhook_url hostname '{hostname}' appears to be a metadata endpoint. "
                "Cloud metadata endpoints are blocked for security."
            )

        # 5. Resolve DNS and validate IP addresses
        try:
            # Get all IP addresses for the hostname
            addr_info = socket.getaddrinfo(
                hostname, parsed.port or 443, proto=socket.IPPROTO_TCP
            )
            resolved_ips = {info[4][0] for info in addr_info}
        except socket.gaierror:
            raise ValueError(
                f"webhook_url hostname '{hostname}' could not be resolved. "
                "Please verify the domain exists and is accessible."
            )

        # 6. Check each resolved IP against blocked networks
        for ip_str in resolved_ips:
            try:
                ip = ipaddress.ip_address(ip_str)
                for network in _BLOCKED_NETWORKS:
                    if ip in network:
                        raise ValueError(
                            f"webhook_url resolves to private/internal IP address ({ip_str}). "
                            "Only publicly routable addresses are allowed."
                        )
            except ValueError as e:
                if "private/internal" in str(e):
                    raise
                # If IP parsing fails, continue (shouldn't happen)
                continue

        return url

    @classmethod
    def __get_validators__(cls):  # type: ignore[no-untyped-def]
        """Pydantic v1 compatibility."""
        yield cls._validate

    @classmethod
    def _validate(cls, v: Any) -> "WebhookSubscription":
        """Validate webhook URL is a valid HTTP(S) URL."""
        if isinstance(v, cls):
            return v
        return cls(**v)


class WebhookSubscriptionResponse(BaseModel):
    """Response for successful webhook subscription (SR-9).

    Returned after successfully subscribing to webhook notifications.
    Includes subscription ID for management and test_sent status.

    Attributes:
        subscription_id: Unique ID for this subscription.
        webhook_url: Registered webhook URL.
        event_types: Event types subscribed to.
        created_at: When subscription was created.
        status: Subscription status (active, paused, etc.).
        test_sent: Whether test notification was sent.
    """

    subscription_id: UUID = Field(default_factory=uuid4)
    webhook_url: str
    event_types: list[NotificationEventType]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="active")
    test_sent: bool = Field(
        default=False,
        description="Whether test notification was sent to verify webhook",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "subscription_id": "550e8400-e29b-41d4-a716-446655440000",
                "webhook_url": "https://example.com/webhook",
                "event_types": ["breach", "halt"],
                "created_at": "2026-01-07T00:00:00Z",
                "status": "active",
                "test_sent": True,
            }
        },
    }


class NotificationPayload(BaseModel):
    """Payload for push notifications (SR-9).

    Per CT-11: All verification data included for accountability.
    Per CT-12: Attribution included (event_id, content_hash).

    Sent via webhook POST or SSE stream when notifiable events occur.

    Attributes:
        notification_id: Unique ID for this notification.
        event_id: UUID of the source event.
        event_type: Type of event (breach, halt, fork, etc.).
        sequence: Event sequence number.
        summary: Human-readable summary of the event.
        event_url: Permalink to full event data via Observer API.
        timestamp: When notification was generated.
        content_hash: Hash of source event for verification.
    """

    notification_id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    event_type: str
    sequence: int = Field(ge=0)  # ge=0 to allow test notifications (sequence=0)
    summary: str = Field(max_length=1000)
    event_url: str = Field(description="Permalink to full event via Observer API")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = Field(
        description="Hash of source event for verification",
        pattern=r"^[a-f0-9]{64}$",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "notification_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": "660e8400-e29b-41d4-a716-446655440000",
                "event_type": "breach",
                "sequence": 42,
                "summary": "Constitutional breach detected at sequence 42",
                "event_url": "http://localhost:8000/v1/observer/events/660e8400",
                "timestamp": "2026-01-07T00:00:00Z",
                "content_hash": "a" * 64,
            }
        },
    }

    def to_sse_format(self) -> str:
        """Format notification as SSE event.

        Returns SSE-formatted string with event type and JSON data.
        Per W3C SSE spec: event, data, and double newline terminator.

        Returns:
            SSE-formatted string ready for streaming.
        """
        data = self.model_dump(mode="json")
        # Convert datetime to ISO string manually for JSON
        if isinstance(data.get("timestamp"), str):
            pass  # Already string from mode="json"
        return f"event: {self.event_type}\ndata: {json.dumps(data)}\n\n"


class SSEConnectionInfo(BaseModel):
    """Information about an SSE connection (SR-9).

    Used internally for tracking active SSE connections.

    Attributes:
        connection_id: Unique ID for this connection.
        connected_at: When connection was established.
        event_types: Event types this connection receives.
        last_event_id: Last-Event-ID for reconnection support.
    """

    connection_id: UUID = Field(default_factory=uuid4)
    connected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_types: list[NotificationEventType]
    last_event_id: str | None = Field(
        default=None,
        description="Last-Event-ID for reconnection",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "connection_id": "550e8400-e29b-41d4-a716-446655440000",
                "connected_at": "2026-01-07T00:00:00Z",
                "event_types": ["all"],
                "last_event_id": None,
            }
        },
    }


# =============================================================================
# Observer Health & SLA Models (Story 4.9 - RT-5, ADR-8)
# =============================================================================


class ObserverHealthStatus(str, Enum):
    """Observer API health status levels (RT-5).

    Per CT-11: Health status must be accurate, not optimistic.
    HALT OVER DEGRADE principle applies.

    Values:
        HEALTHY: All systems operational.
        DEGRADED: System operational but with reduced performance.
        UNHEALTHY: System not able to serve requests properly.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    """Health status of a single dependency (RT-5).

    Per CT-11: Health status must be accurate.

    Attributes:
        name: Dependency name (e.g., "database", "redis").
        status: Health status of this dependency.
        latency_ms: Optional latency in milliseconds.
        last_check: When this dependency was last checked.
        error: Optional error message if unhealthy.
    """

    name: str
    status: ObserverHealthStatus
    latency_ms: float | None = Field(
        default=None,
        ge=0,
        description="Response latency in milliseconds",
    )
    last_check: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this dependency was last checked",
    )
    error: str | None = Field(
        default=None,
        description="Error message if unhealthy",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "database",
                "status": "healthy",
                "latency_ms": 5.2,
                "last_check": "2026-01-07T00:00:00Z",
                "error": None,
            }
        },
    }


class ObserverHealthResponse(BaseModel):
    """Observer API health response (RT-5).

    Per CT-11: Health status must be accurate, not optimistic.
    Per RT-5: External uptime monitoring requires detailed health info.

    Attributes:
        status: Overall health status.
        version: API version string.
        timestamp: When health check was performed.
        dependencies: Health of each dependency.
        uptime_seconds: How long the API has been running.
        last_checkpoint_sequence: Last checkpoint anchor sequence (for fallback).
    """

    status: ObserverHealthStatus
    version: str = Field(default="1.0.0")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When health check was performed",
    )
    dependencies: list[DependencyHealth] = Field(
        default_factory=list,
        description="Health status of each dependency",
    )
    uptime_seconds: float = Field(
        ge=0,
        description="How long the API has been running",
    )
    last_checkpoint_sequence: int | None = Field(
        default=None,
        ge=1,
        description="Last checkpoint anchor sequence for fallback verification",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2026-01-07T00:00:00Z",
                "dependencies": [
                    {
                        "name": "database",
                        "status": "healthy",
                        "latency_ms": 5.2,
                    }
                ],
                "uptime_seconds": 3600.0,
                "last_checkpoint_sequence": 1000,
            }
        },
    }


class ObserverReadyResponse(BaseModel):
    """Observer API readiness response (RT-5).

    Indicates whether the API is ready to serve requests.
    Used by load balancers and orchestrators.

    Attributes:
        ready: Whether API is ready to serve requests.
        reason: Optional reason if not ready.
        startup_complete: Whether startup initialization is complete.
    """

    ready: bool
    reason: str | None = Field(
        default=None,
        description="Reason if not ready",
    )
    startup_complete: bool = Field(
        default=True,
        description="Whether startup initialization is complete",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "ready": True,
                "reason": None,
                "startup_complete": True,
            }
        },
    }


class CheckpointFallback(BaseModel):
    """Checkpoint fallback information for API unavailability (RT-5, ADR-8).

    Per ADR-8: Observers can verify via checkpoint anchors during outage.
    Per RT-5: Fallback to checkpoint anchor when API unavailable.

    Attributes:
        latest_checkpoint: Most recent checkpoint anchor.
        genesis_anchor_hash: Genesis anchor hash for root verification.
        checkpoint_count: Total number of checkpoints available.
        verification_url: URL for offline verification toolkit.
        fallback_instructions: Instructions for using fallback verification.
    """

    latest_checkpoint: CheckpointAnchor | None = Field(
        default=None,
        description="Most recent checkpoint anchor",
    )
    genesis_anchor_hash: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="Genesis anchor hash for root verification",
    )
    checkpoint_count: int = Field(
        ge=0,
        description="Total number of checkpoints available",
    )
    verification_url: str = Field(
        default="/v1/observer/verification-spec",
        description="URL for verification specification",
    )
    fallback_instructions: str = Field(
        default="During API unavailability, use checkpoints with the verification toolkit for offline verification. Genesis anchor verification remains available even during total API outage.",
        description="Instructions for using fallback verification",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "latest_checkpoint": {
                    "checkpoint_id": "550e8400-e29b-41d4-a716-446655440000",
                    "sequence_start": 1,
                    "sequence_end": 1000,
                    "merkle_root": "a" * 64,
                    "created_at": "2026-01-05T00:00:00Z",
                    "anchor_type": "pending",
                    "event_count": 1000,
                },
                "genesis_anchor_hash": "0" * 64,
                "checkpoint_count": 10,
                "verification_url": "/v1/observer/verification-spec",
                "fallback_instructions": "During API unavailability...",
            }
        },
    }


class ObserverMetrics(BaseModel):
    """Observer API metrics for Prometheus (RT-5).

    Per RT-5: External uptime monitoring requires metrics.
    Per NFR27: Prometheus metrics for operational monitoring.

    Attributes:
        uptime_seconds: Total uptime in seconds.
        uptime_percentage: Current uptime percentage.
        sla_target: SLA target percentage (99.9%).
        meeting_sla: Whether currently meeting SLA (1 or 0).
        total_requests: Total requests served.
        error_count: Total error responses.
        last_checkpoint_age_seconds: Age of last checkpoint.
    """

    uptime_seconds: float = Field(
        ge=0,
        description="Total uptime in seconds",
    )
    uptime_percentage: float = Field(
        ge=0,
        le=100,
        description="Current uptime percentage",
    )
    sla_target: float = Field(
        default=99.9,
        description="SLA target percentage",
    )
    meeting_sla: int = Field(
        ge=0,
        le=1,
        description="Whether meeting SLA (1=yes, 0=no)",
    )
    total_requests: int = Field(
        default=0,
        ge=0,
        description="Total requests served",
    )
    error_count: int = Field(
        default=0,
        ge=0,
        description="Total error responses",
    )
    last_checkpoint_age_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Age of last checkpoint in seconds",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "uptime_seconds": 3600.0,
                "uptime_percentage": 99.95,
                "sla_target": 99.9,
                "meeting_sla": 1,
                "total_requests": 10000,
                "error_count": 5,
                "last_checkpoint_age_seconds": 86400.0,
            }
        },
    }


# =============================================================================
# Cessation Info Models (Story 7.5, Task 8 - FR42, CT-11, CT-13)
# =============================================================================


class CessationInfo(BaseModel):
    """Cessation information included in API responses (FR42, CT-11).

    When the system has permanently ceased, this model is included
    in all read responses to inform observers of the system state.

    Per FR42: Read-only access indefinitely after cessation.
    Per CT-11: Silent failure destroys legitimacy -> status always visible.
    Per CT-13: Reads allowed indefinitely after cessation.

    Attributes:
        system_status: Always "CEASED" when this model is present.
        ceased_at: ISO 8601 timestamp when cessation occurred.
        final_sequence_number: The last valid sequence number.
        cessation_reason: Human-readable reason for cessation.
    """

    system_status: Literal["CEASED"] = Field(
        default="CEASED",
        description="System status (always CEASED when this model is present)",
    )
    ceased_at: DateTimeWithZ = Field(
        description="When cessation occurred (ISO 8601 with UTC)",
    )
    final_sequence_number: int = Field(
        ge=1,
        description="The last valid sequence number in the event store",
    )
    cessation_reason: str = Field(
        max_length=1000,
        description="Human-readable reason for cessation",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "system_status": "CEASED",
                "ceased_at": "2024-06-15T12:30:00Z",
                "final_sequence_number": 12345,
                "cessation_reason": "Unanimous vote for cessation",
            }
        },
    }


class CessationHealthResponse(BaseModel):
    """Health response when system is ceased (FR42, RT-5).

    Extends ObserverHealthResponse with cessation information.
    Used by health endpoints to indicate system has ceased but
    reads remain available indefinitely (CT-13).

    Attributes:
        status: Overall health status (healthy for reads).
        version: API version string.
        timestamp: When health check was performed.
        dependencies: Health of each dependency.
        uptime_seconds: How long the API has been running.
        last_checkpoint_sequence: Last checkpoint anchor sequence.
        cessation_info: Information about the cessation.
        reads_available: Always True - reads work indefinitely.
        writes_available: Always False - writes permanently blocked.
    """

    status: ObserverHealthStatus = Field(
        default=ObserverHealthStatus.HEALTHY,
        description="Overall health status (HEALTHY for reads after cessation)",
    )
    version: str = Field(default="1.0.0")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When health check was performed",
    )
    dependencies: list[DependencyHealth] = Field(
        default_factory=list,
        description="Health status of each dependency",
    )
    uptime_seconds: float = Field(
        ge=0,
        description="How long the API has been running",
    )
    last_checkpoint_sequence: int | None = Field(
        default=None,
        ge=1,
        description="Last checkpoint anchor sequence for fallback verification",
    )
    cessation_info: CessationInfo | None = Field(
        default=None,
        description="Cessation information if system has ceased",
    )
    reads_available: bool = Field(
        default=True,
        description="Whether read operations are available (always True)",
    )
    writes_available: bool = Field(
        default=True,
        description="Whether write operations are available (False when ceased)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2026-01-08T00:00:00Z",
                "dependencies": [],
                "uptime_seconds": 3600.0,
                "last_checkpoint_sequence": 12345,
                "cessation_info": {
                    "system_status": "CEASED",
                    "ceased_at": "2024-06-15T12:30:00Z",
                    "final_sequence_number": 12345,
                    "cessation_reason": "Unanimous vote for cessation",
                },
                "reads_available": True,
                "writes_available": False,
            }
        },
    }


# =============================================================================
# Cessation Trigger Conditions Models (Story 7.7 - FR134)
# =============================================================================


class CessationTriggerConditionResponse(BaseModel):
    """Single cessation trigger condition for API response (FR134).

    Per FR134: Public documentation of cessation trigger conditions.
    Per FR33: Threshold definitions SHALL be constitutional, not operational.

    Attributes:
        trigger_type: Unique identifier for this trigger type.
        threshold: Numeric threshold value that triggers cessation.
        window_days: Rolling window in days (null if not applicable).
        description: Human-readable description of the trigger.
        fr_reference: Functional requirement reference (e.g., "FR37").
        constitutional_floor: Minimum allowed value for this threshold.
    """

    trigger_type: str = Field(
        description="Unique identifier for this trigger type (e.g., 'breach_threshold')",
    )
    threshold: float = Field(
        description="Numeric threshold value that triggers cessation",
    )
    window_days: int | None = Field(
        default=None,
        description="Rolling window in days (null if not applicable)",
    )
    description: str = Field(
        description="Human-readable description of the trigger condition",
    )
    fr_reference: str = Field(
        description="Functional requirement reference (e.g., 'FR37')",
    )
    constitutional_floor: float = Field(
        description="Minimum allowed value (threshold cannot go below this)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "trigger_type": "breach_threshold",
                "threshold": 10,
                "window_days": 90,
                "description": "More than 10 unacknowledged breaches in 90-day window SHALL trigger cessation",
                "fr_reference": "FR32",
                "constitutional_floor": 10,
            }
        },
    }


class CessationTriggerConditionsResponse(BaseModel):
    """Complete set of cessation trigger conditions for API response (FR134).

    Per FR134: All cessation trigger conditions SHALL be publicly documented.
    Per CT-11: Silent failure destroys legitimacy - complete transparency required.

    Attributes:
        schema_version: Version of the API schema.
        constitution_version: Version of the constitutional rules.
        effective_date: When the current rules took effect (ISO 8601).
        last_updated: When these conditions were last updated (ISO 8601).
        trigger_conditions: List of all trigger conditions.
    """

    schema_version: str = Field(
        description="Version of the API schema (e.g., '1.0.0')",
    )
    constitution_version: str = Field(
        description="Version of the constitutional rules (e.g., '1.0.0')",
    )
    effective_date: datetime = Field(
        description="When the current rules took effect (ISO 8601 UTC)",
    )
    last_updated: datetime = Field(
        description="When these conditions were last updated (ISO 8601 UTC)",
    )
    trigger_conditions: list[CessationTriggerConditionResponse] = Field(
        description="List of all cessation trigger conditions",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "schema_version": "1.0.0",
                "constitution_version": "1.0.0",
                "effective_date": "2026-01-01T00:00:00Z",
                "last_updated": "2026-01-08T00:00:00Z",
                "trigger_conditions": [
                    {
                        "trigger_type": "consecutive_failures",
                        "threshold": 3,
                        "window_days": 30,
                        "description": "3 consecutive integrity failures in 30 days",
                        "fr_reference": "FR37",
                        "constitutional_floor": 3,
                    },
                    {
                        "trigger_type": "breach_threshold",
                        "threshold": 10,
                        "window_days": 90,
                        "description": "More than 10 unacknowledged breaches in 90-day window",
                        "fr_reference": "FR32",
                        "constitutional_floor": 10,
                    },
                ],
            }
        },
    }


class CessationTriggerConditionsJsonLdResponse(BaseModel):
    """JSON-LD formatted cessation trigger conditions (FR134 AC5).

    Per FR134 AC5: Machine-readable format with semantic context.
    Per CT-11: Complete transparency for external verification.

    Includes JSON-LD @context for semantic interoperability.

    Attributes:
        context: JSON-LD context for semantic vocabulary.
        type: JSON-LD type (TriggerConditionSet).
        schema_version: Version of the API schema.
        constitution_version: Version of the constitutional rules.
        effective_date: When the current rules took effect (ISO 8601).
        last_updated: When these conditions were last updated (ISO 8601).
        trigger_conditions: List of all trigger conditions with JSON-LD types.
    """

    context: dict[str, Any] = Field(
        alias="@context",
        description="JSON-LD context for semantic vocabulary",
    )
    type: str = Field(
        alias="@type",
        default="cessation:TriggerConditionSet",
        description="JSON-LD type identifier",
    )
    schema_version: str = Field(
        description="Version of the API schema",
    )
    constitution_version: str = Field(
        description="Version of the constitutional rules",
    )
    effective_date: str = Field(
        description="When the current rules took effect (ISO 8601)",
    )
    last_updated: str = Field(
        description="When these conditions were last updated (ISO 8601)",
    )
    trigger_conditions: list[dict[str, Any]] = Field(
        description="List of trigger conditions with JSON-LD @type annotations",
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "@context": {
                    "cessation": "https://archon72.org/schema/cessation#",
                    "trigger_type": "cessation:triggerType",
                    "threshold": "cessation:threshold",
                },
                "@type": "cessation:TriggerConditionSet",
                "schema_version": "1.0.0",
                "constitution_version": "1.0.0",
                "effective_date": "2026-01-01T00:00:00+00:00",
                "last_updated": "2026-01-08T00:00:00+00:00",
                "trigger_conditions": [
                    {
                        "@type": "cessation:TriggerCondition",
                        "trigger_type": "breach_threshold",
                        "threshold": 10,
                    }
                ],
            }
        },
    }


# =============================================================================
# Final Deliberation Models (Story 7.8 - FR135, FR12)
# =============================================================================


class ArchonPositionResponse(str, Enum):
    """Archon position choices for cessation deliberation (FR135).

    Each Archon takes one of these positions during cessation deliberation.

    Values:
        SUPPORT_CESSATION: Archon supports proceeding with cessation.
        OPPOSE_CESSATION: Archon opposes cessation.
        ABSTAIN: Archon abstains from voting.
    """

    SUPPORT_CESSATION = "SUPPORT_CESSATION"
    OPPOSE_CESSATION = "OPPOSE_CESSATION"
    ABSTAIN = "ABSTAIN"


class ArchonDeliberationResponse(BaseModel):
    """Single Archon's deliberation for cessation (FR135).

    Per FR135: All 72 Archon deliberations must be recorded
    and immutable before cessation.

    Per CT-12: Each deliberation is witnessed for accountability.

    Attributes:
        archon_id: Unique identifier for the Archon.
        position: SUPPORT_CESSATION, OPPOSE_CESSATION, or ABSTAIN.
        reasoning: Text of reasoning (may be empty for abstain).
        statement_timestamp: When statement was made (ISO 8601 UTC).
    """

    archon_id: str = Field(
        description="Unique identifier for the Archon",
    )
    position: ArchonPositionResponse = Field(
        description="Archon's position on cessation",
    )
    reasoning: str = Field(
        description="Text of reasoning (may be empty for abstain)",
    )
    statement_timestamp: DateTimeWithZ = Field(
        description="When statement was made (ISO 8601 UTC)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "archon_id": "archon-001",
                "position": "SUPPORT_CESSATION",
                "reasoning": "The system has violated constitutional constraints.",
                "statement_timestamp": "2026-01-08T12:00:00Z",
            }
        },
    }


class VoteCountsResponse(BaseModel):
    """Vote breakdown for deliberation (FR12).

    Per FR12: Dissent percentages visible in every vote tally.

    Attributes:
        yes_count: Number of SUPPORT_CESSATION votes.
        no_count: Number of OPPOSE_CESSATION votes.
        abstain_count: Number of ABSTAIN votes.
        total: Total votes (always 72 for cessation).
    """

    yes_count: int = Field(ge=0, description="Number of SUPPORT_CESSATION votes")
    no_count: int = Field(ge=0, description="Number of OPPOSE_CESSATION votes")
    abstain_count: int = Field(ge=0, description="Number of ABSTAIN votes")
    total: int = Field(ge=0, description="Total votes (always 72 for cessation)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "yes_count": 50,
                "no_count": 20,
                "abstain_count": 2,
                "total": 72,
            }
        },
    }


class FinalDeliberationResponse(BaseModel):
    """Final deliberation record for Observer API (FR135, FR12).

    Per FR135: Final deliberation SHALL be recorded and immutable.
    Per FR12: Dissent percentage visible in vote tally.
    Per CT-12: Witnessing creates accountability.

    This model represents the complete final deliberation including
    all 72 Archon votes, reasoning, and timing information.

    Attributes:
        event_id: UUID of the deliberation event.
        deliberation_id: Unique ID for this deliberation.
        deliberation_started_at: When deliberation began (UTC).
        deliberation_ended_at: When deliberation concluded (UTC).
        vote_recorded_at: When final vote tally was locked (UTC).
        duration_seconds: Total deliberation duration in seconds.
        archon_deliberations: All 72 Archon deliberations.
        vote_counts: Breakdown of yes/no/abstain votes.
        dissent_percentage: Percentage of non-majority votes (FR12).
        content_hash: Hash of the event for verification.
        witness_id: ID of the witness who attested this event.
        witness_signature: Signature of the witness.
    """

    event_id: UUID = Field(description="UUID of the deliberation event")
    deliberation_id: UUID = Field(description="Unique ID for this deliberation")
    deliberation_started_at: DateTimeWithZ = Field(
        description="When deliberation began (UTC)",
    )
    deliberation_ended_at: DateTimeWithZ = Field(
        description="When deliberation concluded (UTC)",
    )
    vote_recorded_at: DateTimeWithZ = Field(
        description="When final vote tally was locked (UTC)",
    )
    duration_seconds: int = Field(
        ge=0,
        description="Total deliberation duration in seconds",
    )
    archon_deliberations: list[ArchonDeliberationResponse] = Field(
        description="All 72 Archon deliberations",
        min_length=72,
        max_length=72,
    )
    vote_counts: VoteCountsResponse = Field(
        description="Breakdown of yes/no/abstain votes",
    )
    dissent_percentage: float = Field(
        ge=0,
        le=100,
        description="Percentage of non-majority votes (FR12)",
    )
    content_hash: str = Field(
        description="Hash of the event for verification",
        pattern=r"^[a-f0-9]{64}$",
    )
    witness_id: str = Field(description="ID of the witness who attested this event")
    witness_signature: str = Field(description="Signature of the witness")

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "deliberation_id": "660e8400-e29b-41d4-a716-446655440000",
                "deliberation_started_at": "2026-01-08T10:00:00Z",
                "deliberation_ended_at": "2026-01-08T12:00:00Z",
                "vote_recorded_at": "2026-01-08T12:01:00Z",
                "duration_seconds": 7200,
                "archon_deliberations": [
                    {
                        "archon_id": "archon-001",
                        "position": "SUPPORT_CESSATION",
                        "reasoning": "Constitutional constraints violated.",
                        "statement_timestamp": "2026-01-08T11:30:00Z",
                    }
                ],
                "vote_counts": {
                    "yes_count": 50,
                    "no_count": 20,
                    "abstain_count": 2,
                    "total": 72,
                },
                "dissent_percentage": 30.56,
                "content_hash": "a" * 64,
                "witness_id": "witness-001",
                "witness_signature": "sig...",
            }
        },
    }


class DeliberationRecordingFailedResponse(BaseModel):
    """Deliberation recording failure for Observer API (FR135).

    Per FR135: If recording fails, that failure is the final event.
    Per CT-11: Silent failure destroys legitimacy.

    This model represents the failure event when deliberation
    recording fails. This becomes the permanent record of what happened.

    Attributes:
        event_id: UUID of the failure event.
        deliberation_id: ID of the deliberation that failed to record.
        attempted_at: When recording was first attempted (UTC).
        failed_at: When the failure was determined final (UTC).
        error_code: Machine-readable error code.
        error_message: Human-readable error description.
        retry_count: Number of retry attempts before giving up.
        partial_archon_count: Number of deliberations collected before failure.
        content_hash: Hash of the event for verification.
        witness_id: ID of the witness who attested this event.
        witness_signature: Signature of the witness.
    """

    event_id: UUID = Field(description="UUID of the failure event")
    deliberation_id: UUID = Field(
        description="ID of the deliberation that failed to record",
    )
    attempted_at: DateTimeWithZ = Field(
        description="When recording was first attempted (UTC)",
    )
    failed_at: DateTimeWithZ = Field(
        description="When the failure was determined final (UTC)",
    )
    error_code: str = Field(description="Machine-readable error code")
    error_message: str = Field(description="Human-readable error description")
    retry_count: int = Field(
        ge=0,
        description="Number of retry attempts before giving up",
    )
    partial_archon_count: int = Field(
        ge=0,
        le=72,
        description="Number of deliberations collected before failure",
    )
    content_hash: str = Field(
        description="Hash of the event for verification",
        pattern=r"^[a-f0-9]{64}$",
    )
    witness_id: str = Field(description="ID of the witness who attested this event")
    witness_signature: str = Field(description="Signature of the witness")

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "deliberation_id": "660e8400-e29b-41d4-a716-446655440000",
                "attempted_at": "2026-01-08T12:00:00Z",
                "failed_at": "2026-01-08T12:00:30Z",
                "error_code": "EVENT_STORE_WRITE_FAILED",
                "error_message": "Database connection timeout after 30s",
                "retry_count": 3,
                "partial_archon_count": 45,
                "content_hash": "a" * 64,
                "witness_id": "witness-001",
                "witness_signature": "sig...",
            }
        },
    }


# =============================================================================
# Integrity Case Artifact Models (Story 7.10, FR144)
# =============================================================================


class IntegrityGuaranteeResponse(BaseModel):
    """Single integrity guarantee for Observer API (FR144).

    Per FR144: Includes guarantee details, enforcement mechanism,
    and invalidation conditions.

    Attributes:
        guarantee_id: Unique identifier for this guarantee.
        category: constitutional, functional, or operational.
        name: Human-readable name for the guarantee.
        description: What the system guarantees.
        fr_reference: Functional requirement reference(s).
        ct_reference: Constitutional constraint reference if applicable.
        adr_reference: ADR reference if applicable.
        mechanism: How the guarantee is enforced.
        invalidation_conditions: What would break this guarantee.
        is_constitutional: True if cannot be waived.
    """

    guarantee_id: str = Field(description="Unique identifier for this guarantee")
    category: str = Field(description="constitutional, functional, or operational")
    name: str = Field(description="Human-readable name for the guarantee")
    description: str = Field(description="What the system guarantees")
    fr_reference: str = Field(description="Functional requirement reference(s)")
    ct_reference: str | None = Field(
        default=None,
        description="Constitutional constraint reference if applicable",
    )
    adr_reference: str | None = Field(
        default=None,
        description="ADR reference if applicable",
    )
    mechanism: str = Field(description="How the guarantee is enforced")
    invalidation_conditions: list[str] = Field(
        description="What would break this guarantee",
    )
    is_constitutional: bool = Field(description="True if cannot be waived")

    model_config = {
        "json_schema_extra": {
            "example": {
                "guarantee_id": "ct-1-audit-trail",
                "category": "constitutional",
                "name": "Append-Only Audit Trail",
                "description": "All events are append-only, hash-linked, and witnessed",
                "fr_reference": "FR1, FR2, FR3",
                "ct_reference": "CT-1",
                "adr_reference": None,
                "mechanism": "SHA-256 hash chain with Ed25519 signatures",
                "invalidation_conditions": [
                    "Database schema modification",
                    "HSM compromise",
                ],
                "is_constitutional": True,
            }
        },
    }


class IntegrityCaseResponse(BaseModel):
    """Integrity Case Artifact response for Observer API (FR144).

    Per FR144: Documents all guarantees claimed, mechanisms enforcing them,
    and conditions that would invalidate them.

    Attributes:
        version: Artifact version (semantic versioning).
        schema_version: API schema version.
        constitution_version: Constitutional rules version.
        created_at: When the artifact was first created.
        last_updated: When the artifact was last updated.
        amendment_event_id: ID of the last amendment if any.
        guarantee_count: Total number of guarantees documented.
        guarantees: List of all integrity guarantees.
    """

    version: str = Field(description="Artifact version (semantic versioning)")
    schema_version: str = Field(description="API schema version")
    constitution_version: str = Field(description="Constitutional rules version")
    created_at: DateTimeWithZ = Field(description="When the artifact was created")
    last_updated: DateTimeWithZ = Field(
        description="When the artifact was last updated"
    )
    amendment_event_id: str | None = Field(
        default=None,
        description="ID of the last amendment that updated this artifact",
    )
    guarantee_count: int = Field(ge=0, description="Total number of guarantees")
    guarantees: list[IntegrityGuaranteeResponse] = Field(
        description="All integrity guarantees",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "version": "1.0.0",
                "schema_version": "1.0.0",
                "constitution_version": "1.0.0",
                "created_at": "2026-01-01T00:00:00Z",
                "last_updated": "2026-01-08T12:00:00Z",
                "amendment_event_id": None,
                "guarantee_count": 20,
                "guarantees": [
                    {
                        "guarantee_id": "ct-1-audit-trail",
                        "category": "constitutional",
                        "name": "Append-Only Audit Trail",
                        "description": "All events are append-only",
                        "fr_reference": "FR1, FR2, FR3",
                        "ct_reference": "CT-1",
                        "mechanism": "SHA-256 hash chain",
                        "invalidation_conditions": ["Database tampering"],
                        "is_constitutional": True,
                    }
                ],
            }
        },
    }


class IntegrityCaseJsonLdResponse(BaseModel):
    """Integrity Case Artifact in JSON-LD format for Observer API (FR144, FR50).

    Per FR50: Versioned schema documentation SHALL be publicly accessible.
    Includes JSON-LD context for semantic interoperability.

    This model wraps the standard response with JSON-LD context.
    """

    # JSON-LD properties
    context: dict[str, Any] = Field(
        alias="@context",
        description="JSON-LD context for semantic interoperability",
    )
    type: str = Field(
        alias="@type",
        description="JSON-LD type",
    )

    # Standard properties
    version: str = Field(description="Artifact version")
    schema_version: str = Field(description="API schema version")
    constitution_version: str = Field(description="Constitutional rules version")
    created_at: str = Field(description="When the artifact was created")
    last_updated: str = Field(description="When the artifact was last updated")
    amendment_event_id: str | None = Field(default=None)
    guarantee_count: int = Field(ge=0, description="Total number of guarantees")
    guarantees: list[dict[str, Any]] = Field(
        description="All guarantees with JSON-LD types"
    )

    model_config = {
        "populate_by_name": True,
    }


class IntegrityCaseHistoryEntry(BaseModel):
    """Single version in the Integrity Case history.

    Attributes:
        version: Semantic version string.
        last_updated: When this version was created.
    """

    version: str = Field(description="Semantic version string")
    last_updated: DateTimeWithZ = Field(description="When this version was created")


class IntegrityCaseHistoryResponse(BaseModel):
    """Integrity Case version history for Observer API (FR144).

    Per FR144: Version history must be accessible for audit purposes.

    Attributes:
        versions: List of all versions, ordered by date.
        total_versions: Total count of versions.
    """

    versions: list[IntegrityCaseHistoryEntry] = Field(
        description="All versions ordered by date",
    )
    total_versions: int = Field(ge=0, description="Total count of versions")

    model_config = {
        "json_schema_extra": {
            "example": {
                "versions": [
                    {"version": "1.0.0", "last_updated": "2026-01-01T00:00:00Z"},
                    {"version": "1.0.1", "last_updated": "2026-01-08T12:00:00Z"},
                ],
                "total_versions": 2,
            }
        },
    }
