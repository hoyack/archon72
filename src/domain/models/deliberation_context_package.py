"""Deliberation context package domain model (Story 2A.3, FR-11.3).

This module defines the DeliberationContextPackage for the Three Fates
petition deliberation system. The package provides all information needed
by Fate Archons to render judgment on a petition.

Constitutional Constraints:
- CT-1: LLMs are stateless -> Package provides deterministic state
- CT-12: Witnessing creates accountability -> content_hash enables audit
- CT-14: Silence is expensive -> Every petition gets context for judgment
- Ruling-3: Similar petitions deferred to M2 -> similar_petitions empty

Design Notes:
- Simpler than ContextBundlePayload (ADR-2) which is for meeting deliberations
- Content hash enables replay verification and audit trail
- Schema version enables future evolution without breaking consumers
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, cast
from uuid import UUID

# Schema version for D2 compliance
CONTEXT_PACKAGE_SCHEMA_VERSION: Literal["1.1.0"] = "1.1.0"


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class DeliberationContextPackage:
    """Context package for Three Fates deliberation (Story 2A.3, FR-11.3).

    Provides deliberating Archons with all information needed to render
    judgment on a petition. Package is immutable and content-hashed for
    integrity verification.

    Constitutional Constraints:
    - CT-1: Provides deterministic state for stateless LLMs
    - CT-12: content_hash enables witnessing and audit
    - Ruling-3: similar_petitions explicitly empty in M1

    Attributes:
        petition_id: UUID of the petition being deliberated.
        petition_text: Full text content of petition.
        petition_type: Type classification (GENERAL, CESSATION, etc.).
        co_signer_count: Current number of co-signers.
        submitter_id: Anonymized submitter identifier (nullable).
        realm: Routing realm for the petition.
        submitted_at: When petition was submitted (UTC).
        session_id: UUID of the deliberation session.
        assigned_archons: Tuple of 3 assigned archon UUIDs.
        similar_petitions: Empty tuple (Ruling-3 deferred to M2).
        ruling_3_deferred: Flag indicating similar petitions deferred.
        severity_tier: Heuristic severity tier (low, medium, high).
        severity_signals: Non-binding signals used to derive severity.
        schema_version: Package schema version for evolution.
        built_at: When package was built (UTC).
        content_hash: SHA-256 hash of canonical JSON (64 hex chars).
    """

    # Core petition data
    petition_id: UUID
    petition_text: str
    petition_type: str  # PetitionType.value
    co_signer_count: int
    submitter_id: UUID | None
    realm: str
    submitted_at: datetime

    # Session data
    session_id: UUID
    assigned_archons: tuple[UUID, UUID, UUID]

    # M2 deferred (Ruling-3)
    similar_petitions: tuple[()] = field(default_factory=tuple)
    ruling_3_deferred: bool = field(default=True)

    # Heuristic severity signals (non-binding)
    severity_tier: str = field(default="low")
    severity_signals: tuple[str, ...] = field(default_factory=tuple)

    # Metadata
    schema_version: str = field(default=CONTEXT_PACKAGE_SCHEMA_VERSION)
    built_at: datetime = field(default_factory=_utc_now)
    content_hash: str = field(default="")

    def __post_init__(self) -> None:
        """Validate package fields."""
        # Validate archon count
        if len(self.assigned_archons) != 3:
            raise ValueError(
                f"Exactly 3 archons required, got {len(self.assigned_archons)}"
            )

        # Validate unique archons
        if len(set(self.assigned_archons)) != 3:
            raise ValueError("Duplicate archon IDs not allowed")

        # Validate schema version
        if self.schema_version != CONTEXT_PACKAGE_SCHEMA_VERSION:
            raise ValueError(
                f"Schema version must be '{CONTEXT_PACKAGE_SCHEMA_VERSION}', "
                f"got '{self.schema_version}'"
            )

        # Validate severity tier
        if self.severity_tier not in {"low", "medium", "high"}:
            raise ValueError("Severity tier must be one of: low, medium, high")

        # Validate content hash format if provided
        if self.content_hash and len(self.content_hash) != 64:
            raise ValueError(
                f"Content hash must be 64 hex chars (SHA-256), "
                f"got {len(self.content_hash)} chars"
            )

        # Validate Ruling-3 compliance
        if self.similar_petitions and not self.ruling_3_deferred:
            raise ValueError("Cannot have similar_petitions in M1 (Ruling-3 deferred)")

    def to_hashable_dict(self) -> dict[str, Any]:
        """Convert to dictionary for hash computation.

        Excludes content_hash itself (would be circular).

        Returns:
            Dictionary with all hashable fields.
        """
        return {
            "petition_id": str(self.petition_id),
            "petition_text": self.petition_text,
            "petition_type": self.petition_type,
            "co_signer_count": self.co_signer_count,
            "submitter_id": str(self.submitter_id) if self.submitter_id else None,
            "realm": self.realm,
            "submitted_at": self.submitted_at.isoformat(),
            "session_id": str(self.session_id),
            "assigned_archons": [str(a) for a in self.assigned_archons],
            "similar_petitions": list(self.similar_petitions),
            "ruling_3_deferred": self.ruling_3_deferred,
            "severity_tier": self.severity_tier,
            "severity_signals": list(self.severity_signals),
            "schema_version": self.schema_version,
            "built_at": self.built_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with all fields including content_hash.
        """
        result = self.to_hashable_dict()
        result["content_hash"] = self.content_hash
        return result

    def to_canonical_json(self) -> str:
        """Produce canonical JSON for deterministic serialization.

        Canonical JSON is:
        - Deterministic: same input always produces same output
        - Sorted: keys are sorted alphabetically
        - Compact: no whitespace between elements

        Returns:
            Canonical JSON string.
        """
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeliberationContextPackage:
        """Create package from dictionary.

        Args:
            data: Dictionary with package fields.

        Returns:
            DeliberationContextPackage instance.
        """
        assigned_archons_raw = tuple(UUID(a) for a in data["assigned_archons"])
        if len(assigned_archons_raw) != 3:
            raise ValueError("assigned_archons must contain exactly 3 UUIDs")

        return cls(
            petition_id=UUID(data["petition_id"]),
            petition_text=data["petition_text"],
            petition_type=data["petition_type"],
            co_signer_count=data["co_signer_count"],
            submitter_id=UUID(data["submitter_id"])
            if data.get("submitter_id")
            else None,
            realm=data["realm"],
            submitted_at=datetime.fromisoformat(data["submitted_at"]),
            session_id=UUID(data["session_id"]),
            assigned_archons=cast(tuple[UUID, UUID, UUID], assigned_archons_raw),
            similar_petitions=tuple(),
            ruling_3_deferred=data.get("ruling_3_deferred", True),
            severity_tier=data.get("severity_tier", "low"),
            severity_signals=tuple(data.get("severity_signals", [])),
            schema_version=data.get("schema_version", CONTEXT_PACKAGE_SCHEMA_VERSION),
            built_at=datetime.fromisoformat(data["built_at"]),
            content_hash=data.get("content_hash", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> DeliberationContextPackage:
        """Create package from JSON string.

        Args:
            json_str: JSON string representation.

        Returns:
            DeliberationContextPackage instance.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def verify_hash(self) -> bool:
        """Verify content hash matches package contents.

        Returns:
            True if hash is valid, False otherwise.
        """
        if not self.content_hash:
            return False

        computed = compute_content_hash(self.to_hashable_dict())
        return computed == self.content_hash


def compute_content_hash(hashable_dict: dict[str, Any]) -> str:
    """Compute SHA-256 hash of canonical JSON.

    Args:
        hashable_dict: Dictionary to hash (excluding content_hash field).

    Returns:
        64-character lowercase hex string (SHA-256).
    """
    canonical = json.dumps(
        hashable_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
