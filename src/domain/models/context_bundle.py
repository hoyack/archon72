"""Context Bundle domain model (Story 2.9, ADR-2).

Provides the ContextBundlePayload frozen dataclass for deterministic,
verifiable context bundles. Bundles enable agent coherence by providing
a snapshot of reality at a specific sequence number.

ADR-2 Decision: Use signed JSON context bundles with JSON Schema validation.

Format Requirements:
- Canonical JSON serialization (sorted keys, stable encoding)
- Required fields: schema_version, bundle_id (computed), meeting_id,
  as_of_event_seq, identity_prompt_ref, meeting_state_ref, precedent_refs[],
  bundle_hash, signature, signing_key_id, created_at

Integrity Requirements:
- Bundle is signed at creation time
- Receivers verify signature BEFORE parsing/using bundle
- Bundle references are content-addressed (hash refs) where possible

Constitutional Truths Honored:
- CT-1: LLMs are stateless -> Context bundles provide deterministic state
- CT-11: Silent failure destroys legitimacy -> Invalid bundles halt, never degrade
- CT-12: Witnessing creates accountability -> Bundle hash creates audit trail
- CT-13: Integrity outranks availability -> Signature verification mandatory
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

# ContentRef type for content-addressed references
# Format: ref:{sha256_hex} (68 chars total = 4 prefix + 64 hex)
ContentRef = str  # Pattern: "ref:[a-f0-9]{64}"

# Constants per ADR-2
CONTEXT_BUNDLE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MAX_PRECEDENT_REFS: int = 10
CONTENT_REF_PREFIX: str = "ref:"
CONTENT_REF_LENGTH: int = 68  # len("ref:") + 64 hex chars
BUNDLE_ID_PREFIX: str = "ctx_"

# Regex pattern for ContentRef validation
CONTENT_REF_PATTERN: re.Pattern[str] = re.compile(r"^ref:[a-f0-9]{64}$")


def validate_content_ref(ref: str, field_name: str) -> None:
    """Validate a ContentRef string format.

    ContentRef format: ref:{sha256_hex}
    Total length: 68 characters (4 prefix + 64 hex)

    Args:
        ref: The reference string to validate.
        field_name: Name of the field for error messages.

    Raises:
        ValueError: If ref is not a valid ContentRef format.
    """
    if not ref.startswith(CONTENT_REF_PREFIX):
        raise ValueError(
            f"{field_name} must be ContentRef format (ref:{{hash}}), got: {ref[:20]}..."
        )
    if len(ref) != CONTENT_REF_LENGTH:
        raise ValueError(
            f"{field_name} must be {CONTENT_REF_LENGTH} chars (ref: + 64 hex), got {len(ref)} chars"
        )
    if not CONTENT_REF_PATTERN.match(ref):
        raise ValueError(
            f"{field_name} must match pattern ref:[a-f0-9]{{64}}, got: {ref}"
        )


def create_content_ref(sha256_hash: str) -> ContentRef:
    """Create a ContentRef from a SHA-256 hash.

    Args:
        sha256_hash: 64-character lowercase hex string.

    Returns:
        ContentRef in format ref:{sha256_hash}

    Raises:
        ValueError: If sha256_hash is not valid.
    """
    if len(sha256_hash) != 64:
        raise ValueError(f"SHA-256 hash must be 64 chars, got {len(sha256_hash)}")
    if not re.match(r"^[a-f0-9]{64}$", sha256_hash):
        raise ValueError(f"SHA-256 hash must be lowercase hex, got: {sha256_hash[:20]}...")
    return f"{CONTENT_REF_PREFIX}{sha256_hash}"


@dataclass(frozen=True, eq=True)
class ContextBundlePayload:
    """Deterministic context for agent invocation (ADR-2).

    Context bundles provide agents with everything needed for deliberation.
    They are immutable, signed, and anchored to a specific event sequence
    for reproducibility.

    Key Insight (MA-3): "Latest" is non-deterministic. `as_of_event_seq`
    makes time explicit, enabling reproducible deliberations.

    Attributes:
        schema_version: Bundle schema version ("1.0").
        meeting_id: UUID of the meeting being deliberated.
        as_of_event_seq: Sequence number anchor for determinism (>= 1).
        identity_prompt_ref: ContentRef to agent identity prompt.
        meeting_state_ref: ContentRef to meeting state snapshot.
        precedent_refs: Tuple of ContentRefs to relevant precedents (max 10).
        created_at: When bundle was created (UTC).
        bundle_hash: SHA-256 hash of canonical JSON (64 hex chars).
        signature: Cryptographic signature of bundle_hash.
        signing_key_id: ID of key used for signing.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> payload = ContextBundlePayload(
        ...     schema_version="1.0",
        ...     meeting_id=uuid4(),
        ...     as_of_event_seq=42,
        ...     identity_prompt_ref="ref:" + "a" * 64,
        ...     meeting_state_ref="ref:" + "b" * 64,
        ...     precedent_refs=tuple(),
        ...     created_at=datetime.now(timezone.utc),
        ...     bundle_hash="c" * 64,
        ...     signature="sig123",
        ...     signing_key_id="key-001",
        ... )
        >>> payload.bundle_id
        'ctx_..._42'
    """

    schema_version: Literal["1.0"]
    meeting_id: UUID
    as_of_event_seq: int
    identity_prompt_ref: ContentRef
    meeting_state_ref: ContentRef
    precedent_refs: tuple[ContentRef, ...]
    created_at: datetime
    bundle_hash: str
    signature: str
    signing_key_id: str

    @property
    def bundle_id(self) -> str:
        """Compute bundle_id from meeting_id and as_of_event_seq.

        Format: ctx_{meeting_id}_{as_of_event_seq}

        Returns:
            Unique bundle identifier string.
        """
        return f"{BUNDLE_ID_PREFIX}{self.meeting_id}_{self.as_of_event_seq}"

    def __post_init__(self) -> None:  # noqa: C901
        """Validate all payload fields.

        Raises:
            ValueError: If any field has an invalid value.
            TypeError: If any field has an incorrect type.
        """
        # Schema version validation
        if self.schema_version != CONTEXT_BUNDLE_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be '{CONTEXT_BUNDLE_SCHEMA_VERSION}', "
                f"got '{self.schema_version}'"
            )

        # Meeting ID type validation
        if not isinstance(self.meeting_id, UUID):
            raise TypeError(
                f"meeting_id must be UUID, got {type(self.meeting_id).__name__}"
            )

        # Sequence number validation (must be >= 1, as seq 0 is invalid)
        if self.as_of_event_seq < 1:
            raise ValueError(
                f"as_of_event_seq must be >= 1, got {self.as_of_event_seq}"
            )

        # ContentRef validations
        validate_content_ref(self.identity_prompt_ref, "identity_prompt_ref")
        validate_content_ref(self.meeting_state_ref, "meeting_state_ref")

        # Precedent refs validation
        if len(self.precedent_refs) > MAX_PRECEDENT_REFS:
            raise ValueError(
                f"Maximum {MAX_PRECEDENT_REFS} precedent references allowed, "
                f"got {len(self.precedent_refs)}"
            )
        for i, ref in enumerate(self.precedent_refs):
            validate_content_ref(ref, f"precedent_refs[{i}]")

        # Created at type validation
        if not isinstance(self.created_at, datetime):
            raise TypeError(
                f"created_at must be datetime, got {type(self.created_at).__name__}"
            )

        # Bundle hash validation (64 hex chars)
        if len(self.bundle_hash) != 64:
            raise ValueError(
                f"bundle_hash must be 64 character hex string, got {len(self.bundle_hash)} chars"
            )
        if not re.match(r"^[a-f0-9]{64}$", self.bundle_hash):
            raise ValueError(
                f"bundle_hash must be lowercase hex, got: {self.bundle_hash[:20]}..."
            )

        # Signature validation (non-empty)
        if not self.signature:
            raise ValueError("signature must be non-empty")

        # Signing key ID validation (non-empty)
        if not self.signing_key_id:
            raise ValueError("signing_key_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns canonical representation suitable for hashing.
        Note: bundle_id is computed, not stored.

        Returns:
            Dictionary with all fields serialized.
        """
        return {
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "meeting_id": str(self.meeting_id),
            "as_of_event_seq": self.as_of_event_seq,
            "identity_prompt_ref": self.identity_prompt_ref,
            "meeting_state_ref": self.meeting_state_ref,
            "precedent_refs": list(self.precedent_refs),
            "created_at": self.created_at.isoformat(),
            "bundle_hash": self.bundle_hash,
            "signature": self.signature,
            "signing_key_id": self.signing_key_id,
        }

    def to_signable_dict(self) -> dict[str, Any]:
        """Convert to dictionary for signature computation.

        Returns dictionary WITHOUT signature fields, for computing
        the bundle_hash before signing.

        Returns:
            Dictionary with signable fields only (no signature, bundle_hash).
        """
        return {
            "schema_version": self.schema_version,
            "meeting_id": str(self.meeting_id),
            "as_of_event_seq": self.as_of_event_seq,
            "identity_prompt_ref": self.identity_prompt_ref,
            "meeting_state_ref": self.meeting_state_ref,
            "precedent_refs": list(self.precedent_refs),
            "created_at": self.created_at.isoformat(),
        }

    @staticmethod
    def canonical_json(data: dict[str, Any]) -> str:
        """Produce canonical JSON for deterministic hashing.

        Canonical JSON is:
        - Deterministic: same input always produces same output
        - Sorted: keys are sorted alphabetically
        - Compact: no whitespace between elements

        Args:
            data: Dictionary to serialize.

        Returns:
            Canonical JSON string.
        """
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )


@dataclass(frozen=True, eq=True)
class UnsignedContextBundle:
    """Context bundle before signing (intermediate state).

    Used during bundle creation before hash and signature are computed.

    Attributes:
        schema_version: Bundle schema version ("1.0").
        meeting_id: UUID of the meeting being deliberated.
        as_of_event_seq: Sequence number anchor for determinism.
        identity_prompt_ref: ContentRef to agent identity prompt.
        meeting_state_ref: ContentRef to meeting state snapshot.
        precedent_refs: Tuple of ContentRefs to relevant precedents.
        created_at: When bundle was created.
    """

    schema_version: Literal["1.0"]
    meeting_id: UUID
    as_of_event_seq: int
    identity_prompt_ref: ContentRef
    meeting_state_ref: ContentRef
    precedent_refs: tuple[ContentRef, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate fields before signing."""
        if self.schema_version != CONTEXT_BUNDLE_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be '{CONTEXT_BUNDLE_SCHEMA_VERSION}'"
            )
        if not isinstance(self.meeting_id, UUID):
            raise TypeError("meeting_id must be UUID")
        if self.as_of_event_seq < 1:
            raise ValueError("as_of_event_seq must be >= 1")
        validate_content_ref(self.identity_prompt_ref, "identity_prompt_ref")
        validate_content_ref(self.meeting_state_ref, "meeting_state_ref")
        if len(self.precedent_refs) > MAX_PRECEDENT_REFS:
            raise ValueError(f"Maximum {MAX_PRECEDENT_REFS} precedent references")
        for i, ref in enumerate(self.precedent_refs):
            validate_content_ref(ref, f"precedent_refs[{i}]")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be datetime")

    def to_signable_dict(self) -> dict[str, Any]:
        """Convert to dictionary for hash computation."""
        return {
            "schema_version": self.schema_version,
            "meeting_id": str(self.meeting_id),
            "as_of_event_seq": self.as_of_event_seq,
            "identity_prompt_ref": self.identity_prompt_ref,
            "meeting_state_ref": self.meeting_state_ref,
            "precedent_refs": list(self.precedent_refs),
            "created_at": self.created_at.isoformat(),
        }
