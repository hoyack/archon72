"""Observer DTOs for application layer.

Application-layer DTOs for observer-related operations including hash chain proofs,
Merkle proofs, checkpoint anchors, and notification payloads.

This module contains two types of definitions:
1. Dataclass-based DTOs (with DTO suffix) - for internal application layer use
2. Pydantic models (shared with API) - for cross-layer data transfer

Architecture Note:
Application layer defines its own DTOs to maintain independence from the API layer.
Pydantic models that need to be shared are defined here and re-exported by the API.
This ensures the dependency flows inward: API -> Application, not the reverse.

Constitutional Constraints:
- SR-9: Observer push notifications for breach events
- RT-5: Breach events pushed to multiple channels
- FR89: Hash chain proof for verification
- FR136: Merkle proof for O(log n) verification
- FR137, FR138: Checkpoint anchors with Merkle roots
"""

import ipaddress
import json
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class NotificationEventTypeDTO(str, Enum):
    """Event types that trigger notifications (SR-9).

    Per SR-9: Observer push notifications for breach events.

    Values:
        BREACH: Constitutional breach detected.
        HALT: System halted due to fork/conflict.
        CESSATION: System cessation initiated.
        AMENDMENT: Constitution amendment proposed or adopted.
        CHECKPOINT: New checkpoint anchor published.
    """

    BREACH = "breach"
    HALT = "halt"
    CESSATION = "cessation"
    AMENDMENT = "amendment"
    CHECKPOINT = "checkpoint"


@dataclass(frozen=True)
class HashChainProofEntryDTO:
    """Single entry in hash chain proof (FR89).

    Each entry contains the sequence, content_hash, and prev_hash
    to allow verification that the chain is continuous.

    Attributes:
        sequence: Event sequence number (monotonically increasing).
        content_hash: SHA-256 hash of event content.
        prev_hash: Hash of previous event (genesis constant for seq 1).
    """

    sequence: int
    content_hash: str
    prev_hash: str


@dataclass(frozen=True)
class HashChainProofDTO:
    """Hash chain proof connecting queried state to current head (FR89).

    Attributes:
        from_sequence: Start of proof (queried sequence).
        to_sequence: End of proof (current head).
        chain: List of hash chain entries from queried point to head.
        current_head_hash: Content hash of current head event.
        generated_at: When this proof was generated (UTC).
        proof_type: Type of proof (hash_chain or merkle_path).
    """

    from_sequence: int
    to_sequence: int
    chain: list[HashChainProofEntryDTO]
    current_head_hash: str
    proof_type: str = "hash_chain"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MerkleProofEntryDTO:
    """Single sibling hash in Merkle proof path (FR136).

    Attributes:
        level: Tree level (0 = leaf level).
        position: Left or right sibling position.
        sibling_hash: Hash of the sibling node.
    """

    level: int
    position: Literal["left", "right"]
    sibling_hash: str


@dataclass(frozen=True)
class MerkleProofDTO:
    """Merkle proof connecting event to checkpoint root (FR136).

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

    event_sequence: int
    event_hash: str
    checkpoint_sequence: int
    checkpoint_root: str
    path: list[MerkleProofEntryDTO]
    tree_size: int
    proof_type: str = "merkle"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class CheckpointAnchorDTO:
    """Checkpoint anchor with Merkle root (FR137, FR138).

    Attributes:
        sequence: Checkpoint sequence number.
        merkle_root: Merkle root hash of events in this checkpoint.
        event_count: Number of events in this checkpoint.
        created_at: When checkpoint was created.
        signature: Optional signature for verification.
    """

    sequence: int
    merkle_root: str
    event_count: int
    created_at: datetime
    signature: str | None = None


@dataclass(frozen=True)
class WebhookSubscriptionDTO:
    """Webhook subscription for push notifications.

    Attributes:
        subscription_id: Unique subscription identifier.
        callback_url: URL to receive notifications.
        event_types: List of event types to receive.
        secret: HMAC secret for signature verification.
        active: Whether subscription is active.
        created_at: When subscription was created.
    """

    subscription_id: UUID
    callback_url: str
    event_types: list[NotificationEventTypeDTO]
    secret: str
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class WebhookSubscriptionResponseDTO:
    """Response after creating webhook subscription.

    Attributes:
        subscription_id: Unique subscription identifier.
        callback_url: URL to receive notifications.
        event_types: List of event types subscribed to.
        active: Whether subscription is active.
        created_at: When subscription was created.
    """

    subscription_id: UUID
    callback_url: str
    event_types: list[str]
    active: bool
    created_at: datetime


@dataclass(frozen=True)
class NotificationPayloadDTO:
    """Notification payload for push delivery.

    Attributes:
        notification_id: Unique notification identifier.
        event_type: Type of event that triggered notification.
        event_id: ID of the triggering event.
        event_sequence: Sequence number of triggering event.
        timestamp: When notification was generated.
        payload: Event-specific data.
        signature: HMAC signature for verification.
    """

    notification_id: UUID
    event_type: str
    event_id: UUID
    event_sequence: int
    timestamp: datetime
    payload: dict[str, Any]
    signature: str | None = None


# =============================================================================
# Pydantic Models for Cross-Layer Data Transfer
# =============================================================================
# These Pydantic models are used by application services and shared with the
# API layer. They are defined here to ensure dependency flows inward
# (API -> Application), not outward (Application -> API).
# =============================================================================

# SSRF protection: blocked hosts and networks (per OWASP SSRF Prevention)
_BLOCKED_HOSTS = frozenset({
    'localhost',
    '127.0.0.1',
    '::1',
    '0.0.0.0',
    '169.254.169.254',  # AWS/GCP metadata
    'metadata.google.internal',  # GCP metadata
    'metadata.google.com',
})

_BLOCKED_NETWORKS = (
    ipaddress.ip_network('10.0.0.0/8'),       # Private Class A
    ipaddress.ip_network('172.16.0.0/12'),    # Private Class B
    ipaddress.ip_network('192.168.0.0/16'),   # Private Class C
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local / metadata
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),         # IPv6 private
    ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
)


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


class HashChainProofEntry(BaseModel):
    """Single entry in hash chain proof (FR89).

    Attributes:
        sequence: Event sequence number (monotonically increasing).
        content_hash: SHA-256 hash of event content.
        prev_hash: Hash of previous event (genesis constant for seq 1).
    """

    sequence: int = Field(ge=1, description="Event sequence number")
    content_hash: str = Field(
        description="SHA-256 hash of event content",
        pattern=r"^[a-f0-9]{64}$",
    )
    prev_hash: str = Field(
        description="Hash of previous event (genesis for seq 1)",
        pattern=r"^[a-f0-9]{64}$",
    )


class HashChainProof(BaseModel):
    """Hash chain proof connecting queried state to current head (FR89).

    Per FR89: Historical queries SHALL return hash chain proof
    connecting queried state to current head.

    Attributes:
        from_sequence: Start of proof (queried sequence).
        to_sequence: End of proof (current head).
        chain: List of hash chain entries from queried point to head.
        current_head_hash: Content hash of current head event.
        generated_at: When this proof was generated (UTC).
        proof_type: Type of proof (hash_chain or merkle_path).
    """

    from_sequence: int = Field(ge=1, description="Start of proof (queried sequence)")
    to_sequence: int = Field(ge=1, description="End of proof (current head)")
    chain: list[HashChainProofEntry] = Field(
        description="Hash chain entries from queried point to head",
    )
    current_head_hash: str = Field(
        description="Content hash of current head event",
        pattern=r"^[a-f0-9]{64}$",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this proof was generated",
    )
    proof_type: str = Field(
        default="hash_chain",
        description="Type of proof (hash_chain or merkle_path)",
    )


class MerkleProofEntry(BaseModel):
    """Single sibling hash in Merkle proof path (FR136).

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


class MerkleProof(BaseModel):
    """Merkle proof connecting event to checkpoint root (FR136).

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
    anchor_reference: Optional[str] = Field(
        default=None,
        description="External anchor reference (Bitcoin txid, TSA response)",
    )
    event_count: int = Field(ge=0)


class WebhookSubscription(BaseModel):
    """Webhook subscription for push notifications (SR-9).

    Per SR-9: Register webhook for breach event notifications.
    Per RT-5: Breach events pushed to multiple channels.

    Security: SSRF protection per OWASP guidelines.

    Attributes:
        webhook_url: HTTPS URL for webhook delivery (external only).
        event_types: Event types to subscribe to.
        secret: Optional secret for webhook signature verification (min 32 chars).
    """

    webhook_url: Annotated[str, Field(description="HTTPS URL for webhook delivery (external only)")]
    event_types: list[NotificationEventType] = Field(
        default=[NotificationEventType.ALL],
        description="Event types to subscribe to",
    )
    secret: Optional[str] = Field(
        default=None,
        min_length=32,
        description="Secret for HMAC signature verification (optional, min 32 chars)",
    )

    @field_validator('webhook_url')
    @classmethod
    def validate_webhook_url_ssrf(cls, v: str) -> str:
        """Validate webhook URL to prevent SSRF attacks."""
        url = str(v).strip()

        try:
            parsed = urlparse(url)
        except Exception:
            raise ValueError("Invalid URL format")

        if parsed.scheme != 'https':
            raise ValueError(
                "webhook_url must use HTTPS scheme for security. "
                "HTTP is not allowed to prevent credential interception."
            )

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("webhook_url must have a valid hostname")

        hostname_lower = hostname.lower()

        if hostname_lower in _BLOCKED_HOSTS:
            raise ValueError(
                f"webhook_url hostname '{hostname}' is blocked. "
                "Internal and metadata endpoints are not allowed."
            )

        if 'metadata' in hostname_lower or hostname_lower.endswith('.internal'):
            raise ValueError(
                f"webhook_url hostname '{hostname}' appears to be a metadata endpoint. "
                "Cloud metadata endpoints are blocked for security."
            )

        try:
            addr_info = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
            resolved_ips = {info[4][0] for info in addr_info}
        except socket.gaierror:
            raise ValueError(
                f"webhook_url hostname '{hostname}' could not be resolved. "
                "Please verify the domain exists and is accessible."
            )

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
                continue

        return url


class WebhookSubscriptionResponse(BaseModel):
    """Response for successful webhook subscription (SR-9).

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


class NotificationPayload(BaseModel):
    """Payload for push notifications (SR-9).

    Per CT-11: All verification data included for accountability.
    Per CT-12: Attribution included (event_id, content_hash).

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
    sequence: int = Field(ge=0)
    summary: str = Field(max_length=1000)
    event_url: str = Field(description="Permalink to full event via Observer API")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = Field(
        description="Hash of source event for verification",
        pattern=r"^[a-f0-9]{64}$",
    )

    def to_sse_format(self) -> str:
        """Format notification as SSE event."""
        data = self.model_dump(mode="json")
        return f"event: {self.event_type}\ndata: {json.dumps(data)}\n\n"
