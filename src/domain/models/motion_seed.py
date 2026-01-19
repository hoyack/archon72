"""Domain models for Motion Seeds and the Motion Gates system.

Motion Seeds are non-binding proposals that exist before formal Motion introduction.
The Motion Gates specification (docs/spikes/motion-gates.md) defines the boundary:

- Motion Seeds: Unbounded speech, recorded for visibility, no agenda eligibility
- Motions: Scarce, agenda-eligible artifacts requiring King sponsorship

Key Principle: "Speech is unlimited. Agenda is scarce."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class SeedStatus(Enum):
    """Status of a Motion Seed through its lifecycle."""

    RECORDED = "recorded"  # Initial state - seed captured
    CLUSTERED = "clustered"  # Grouped with similar seeds
    PROMOTED = "promoted"  # Promoted to Motion by a King
    ARCHIVED = "archived"  # Archived without promotion
    SUPERSEDED = "superseded"  # Replaced by newer seed


class AdmissionStatus(Enum):
    """Status of Motion admission through the gate."""

    PENDING = "pending"  # Awaiting gate evaluation
    ADMITTED = "admitted"  # Passed all validations
    REJECTED = "rejected"  # Failed one or more validations
    DEFERRED = "deferred"  # Deferred due to quota/capacity


class AdmissionRejectReason(Enum):
    """Reason codes for Motion admission rejection."""

    # Structural validation failures
    MISSING_TITLE = "missing_title"
    MISSING_NORMATIVE_INTENT = "missing_normative_intent"
    MISSING_SUCCESS_CRITERIA = "missing_success_criteria"
    MISSING_REALM_ASSIGNMENT = "missing_realm_assignment"
    MISSING_SPONSOR = "missing_sponsor"

    # Standing validation failures
    SPONSOR_NOT_KING = "sponsor_not_king"
    SPONSOR_WRONG_REALM = "sponsor_wrong_realm"
    CROSS_REALM_NO_COSPONSOR = "cross_realm_no_cosponsor"
    INVALID_COSPONSOR = "invalid_cosponsor"

    # Content validation failures
    HOW_IN_NORMATIVE_INTENT = "how_in_normative_intent"
    HOW_IN_CONSTRAINTS = "how_in_constraints"
    HOW_IN_SUCCESS_CRITERIA = "how_in_success_criteria"

    # Ambiguity validation failures
    AMBIGUOUS_SCOPE = "ambiguous_scope"
    UNDEFINED_TERMS = "undefined_terms"
    MISSING_ACTION = "missing_action"

    # Scope validation failures
    EXCESSIVE_REALM_SPAN = "excessive_realm_span"
    CONFLICTING_REALMS = "conflicting_realms"

    # Other
    MALFORMED = "malformed"
    DUPLICATE = "duplicate"


@dataclass
class SupportSignal:
    """Non-binding endorsement for a Motion Seed."""

    signaler_id: str
    signaler_name: str
    signaler_rank: str
    timestamp: datetime
    signal_type: str = "support"  # support, priority, concern

    def to_dict(self) -> dict[str, Any]:
        return {
            "signaler_id": self.signaler_id,
            "signaler_name": self.signaler_name,
            "signaler_rank": self.signaler_rank,
            "timestamp": self.timestamp.isoformat(),
            "signal_type": self.signal_type,
        }


@dataclass
class MotionSeed:
    """A non-binding proposal artifact recorded for visibility and future consideration.

    Motion Seeds:
    - May be submitted by any eligible participant
    - Do NOT claim agenda time
    - Do NOT trigger deliberation
    - Do NOT require Admission Gate validation
    - May be clustered, consolidated, or summarized
    - Can only become a Motion through formal King promotion
    """

    seed_id: UUID
    seed_text: str  # Unaltered original proposal
    submitted_by: str  # Archon ID
    submitted_by_name: str
    submitted_at: datetime

    # Optional hints (non-binding)
    proposed_realm: str | None = None  # Non-binding realm suggestion
    proposed_title: str | None = None  # Non-binding title suggestion

    # Status tracking
    status: SeedStatus = SeedStatus.RECORDED

    # Support signals (non-binding endorsements)
    support_signals: list[SupportSignal] = field(default_factory=list)

    # Provenance
    source_cycle: str | None = None  # e.g., "conclave-20260117-180111"
    source_event: str | None = None  # e.g., "secretary-extraction"
    source_references: list[str] = field(default_factory=list)

    # Clustering (if clustered)
    cluster_id: str | None = None
    cluster_position: int | None = None  # Position within cluster

    # Promotion tracking (if promoted)
    promoted_to_motion_id: str | None = None
    promoted_at: datetime | None = None
    promoted_by: str | None = None  # King who promoted

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        seed_text: str,
        submitted_by: str,
        submitted_by_name: str,
        proposed_realm: str | None = None,
        proposed_title: str | None = None,
        source_cycle: str | None = None,
        source_event: str | None = None,
    ) -> MotionSeed:
        """Create a new Motion Seed."""
        return cls(
            seed_id=uuid4(),
            seed_text=seed_text,
            submitted_by=submitted_by,
            submitted_by_name=submitted_by_name,
            submitted_at=datetime.now(timezone.utc),
            proposed_realm=proposed_realm,
            proposed_title=proposed_title,
            source_cycle=source_cycle,
            source_event=source_event,
        )

    def add_support(
        self,
        signaler_id: str,
        signaler_name: str,
        signaler_rank: str,
        signal_type: str = "support",
    ) -> SupportSignal:
        """Add a non-binding support signal."""
        signal = SupportSignal(
            signaler_id=signaler_id,
            signaler_name=signaler_name,
            signaler_rank=signaler_rank,
            timestamp=datetime.now(timezone.utc),
            signal_type=signal_type,
        )
        self.support_signals.append(signal)
        return signal

    def mark_clustered(self, cluster_id: str, position: int) -> None:
        """Mark this seed as part of a cluster."""
        self.status = SeedStatus.CLUSTERED
        self.cluster_id = cluster_id
        self.cluster_position = position

    def mark_promoted(self, motion_id: str, king_id: str) -> None:
        """Mark this seed as promoted to a Motion."""
        self.status = SeedStatus.PROMOTED
        self.promoted_to_motion_id = motion_id
        self.promoted_at = datetime.now(timezone.utc)
        self.promoted_by = king_id

    def mark_archived(self) -> None:
        """Archive this seed."""
        self.status = SeedStatus.ARCHIVED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "seed_id": str(self.seed_id),
            "seed_text": self.seed_text,
            "submitted_by": self.submitted_by,
            "submitted_by_name": self.submitted_by_name,
            "submitted_at": self.submitted_at.isoformat(),
            "proposed_realm": self.proposed_realm,
            "proposed_title": self.proposed_title,
            "status": self.status.value,
            "support_signals": [s.to_dict() for s in self.support_signals],
            "source_cycle": self.source_cycle,
            "source_event": self.source_event,
            "source_references": self.source_references,
            "cluster_id": self.cluster_id,
            "cluster_position": self.cluster_position,
            "promoted_to_motion_id": self.promoted_to_motion_id,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
            "promoted_by": self.promoted_by,
            "metadata": self.metadata,
        }


@dataclass
class SeedCluster:
    """A cluster of related Motion Seeds."""

    cluster_id: str
    theme: str
    description: str
    seed_refs: list[str]  # seed_ids
    created_at: datetime
    created_by: str  # System or archon that created cluster

    # Draft summary (non-binding)
    draft_summary: str | None = None
    draft_title: str | None = None

    # Provenance
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        theme: str,
        description: str,
        seed_refs: list[str],
        created_by: str,
    ) -> SeedCluster:
        return cls(
            cluster_id=f"cluster-{uuid4().hex[:12]}",
            theme=theme,
            description=description,
            seed_refs=seed_refs,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "theme": self.theme,
            "description": self.description,
            "seed_refs": self.seed_refs,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "draft_summary": self.draft_summary,
            "draft_title": self.draft_title,
            "provenance": self.provenance,
        }


@dataclass
class RealmAssignment:
    """Realm assignment for a Motion, including sponsor information."""

    primary_realm: str
    primary_sponsor_id: str  # King ID
    primary_sponsor_name: str

    # Co-sponsors for cross-realm motions
    co_sponsors: list[dict[str, str]] = field(default_factory=list)

    # Cross-realm flag
    is_cross_realm: bool = False

    def add_cosponsor(
        self, king_id: str, king_name: str, realm_id: str
    ) -> None:
        """Add a co-sponsor King for cross-realm motion."""
        self.co_sponsors.append({
            "king_id": king_id,
            "king_name": king_name,
            "realm_id": realm_id,
        })
        self.is_cross_realm = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_realm": self.primary_realm,
            "primary_sponsor_id": self.primary_sponsor_id,
            "primary_sponsor_name": self.primary_sponsor_name,
            "co_sponsors": self.co_sponsors,
            "is_cross_realm": self.is_cross_realm,
        }


@dataclass
class AdmissionRecord:
    """Record of Motion admission gate evaluation."""

    record_id: UUID
    motion_id: str
    evaluated_at: datetime
    status: AdmissionStatus

    # Validation results
    structural_valid: bool = True
    standing_valid: bool = True
    content_valid: bool = True
    ambiguity_valid: bool = True
    scope_valid: bool = True

    # Rejection reasons (if any)
    rejection_reasons: list[AdmissionRejectReason] = field(default_factory=list)
    rejection_details: dict[str, str] = field(default_factory=dict)

    # Warnings (not rejections, but logged)
    warnings: list[str] = field(default_factory=list)

    # Deferral info (if deferred)
    deferred_reason: str | None = None
    deferred_until: datetime | None = None

    @classmethod
    def create(
        cls,
        motion_id: str,
        status: AdmissionStatus,
    ) -> AdmissionRecord:
        return cls(
            record_id=uuid4(),
            motion_id=motion_id,
            evaluated_at=datetime.now(timezone.utc),
            status=status,
        )

    def add_rejection(
        self,
        reason: AdmissionRejectReason,
        detail: str,
    ) -> None:
        """Add a rejection reason."""
        self.rejection_reasons.append(reason)
        self.rejection_details[reason.value] = detail

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": str(self.record_id),
            "motion_id": self.motion_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "status": self.status.value,
            "structural_valid": self.structural_valid,
            "standing_valid": self.standing_valid,
            "content_valid": self.content_valid,
            "ambiguity_valid": self.ambiguity_valid,
            "scope_valid": self.scope_valid,
            "rejection_reasons": [r.value for r in self.rejection_reasons],
            "rejection_details": self.rejection_details,
            "warnings": self.warnings,
            "deferred_reason": self.deferred_reason,
            "deferred_until": self.deferred_until.isoformat()
            if self.deferred_until
            else None,
        }


# King-to-Realm mapping from archons-base.json
KING_REALM_MAP: dict[str, dict[str, str]] = {
    "5b8e679b-abb5-41e6-8d17-36531db04757": {
        "name": "Bael",
        "realm_id": "realm_privacy_discretion_services",
        "realm_label": "Privacy & Discretion Services",
    },
    "177ee194-ff00-45b7-a3b0-b05e7675e718": {
        "name": "Beleth",
        "realm_id": "realm_relationship_facilitation",
        "realm_label": "Relationship Facilitation",
    },
    "1a4a2056-e2b5-42a7-a338-8b8b67509f1f": {
        "name": "Paimon",
        "realm_id": "realm_knowledge_skill_development",
        "realm_label": "Knowledge & Skill Development",
    },
    "6a00c2d0-55e9-4b4e-89d5-c7de3a2fd26d": {
        "name": "Purson",
        "realm_id": "realm_predictive_analytics_forecasting",
        "realm_label": "Predictive Analytics & Forecasting",
    },
    "87a5c59f-369b-405d-975b-4369c4bd1488": {
        "name": "Asmoday",
        "realm_id": "realm_character_virtue_development",
        "realm_label": "Character & Virtue Development",
    },
    "782597cf-8a7b-48c9-bc9f-128019f4bcc2": {
        "name": "Balam",
        "realm_id": "realm_accurate_guidance_counsel",
        "realm_label": "Accurate Guidance & Counsel",
    },
    "85484a39-60e3-4e47-8aee-2dcbd68347df": {
        "name": "Vine",
        "realm_id": "realm_threat_anomaly_detection",
        "realm_label": "Threat & Anomaly Detection",
    },
    "9b439711-9217-4c30-8c0f-9a589c3c7e38": {
        "name": "Zagan",
        "realm_id": "realm_personality_charisma_enhancement",
        "realm_label": "Personality & Charisma Enhancement",
    },
    "da58a598-bfab-42e9-849c-1c34012104c6": {
        "name": "Belial",
        "realm_id": "realm_talent_acquisition_team_building",
        "realm_label": "Talent Acquisition & Team Building",
    },
}

# Reverse lookup: realm_id -> king_id
REALM_KING_MAP: dict[str, str] = {
    info["realm_id"]: king_id for king_id, info in KING_REALM_MAP.items()
}

# All valid realm IDs
VALID_REALMS: set[str] = {info["realm_id"] for info in KING_REALM_MAP.values()}

# All King IDs
KING_IDS: set[str] = set(KING_REALM_MAP.keys())


def is_king(archon_id: str) -> bool:
    """Check if an archon is a King."""
    return archon_id in KING_IDS


def get_king_realm(king_id: str) -> str | None:
    """Get the realm ID for a King."""
    if king_id in KING_REALM_MAP:
        return KING_REALM_MAP[king_id]["realm_id"]
    return None


def get_realm_king(realm_id: str) -> str | None:
    """Get the King ID for a realm."""
    return REALM_KING_MAP.get(realm_id)


def validate_king_realm_match(king_id: str, realm_id: str) -> bool:
    """Validate that a King can sponsor motions in a realm."""
    king_realm = get_king_realm(king_id)
    return king_realm == realm_id
