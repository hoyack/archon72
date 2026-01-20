"""Disposition domain events (Story 2A.8, FR-11.11).

This module defines the domain events for disposition emission and
pipeline routing after Three Fates deliberation completes.

Constitutional Constraints:
- CT-14: Silence is expensive - every claim terminates in witnessed fate
- CT-12: Witnessing creates accountability
- FR-11.11: Route to appropriate pipeline based on deliberation outcome

Developer Golden Rules:
1. Events are immutable (frozen dataclasses)
2. All events include schema_version for D2 compliance
3. Use to_dict() not asdict() for serialization
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

# Current schema version for disposition events (D2 compliance)
DISPOSITION_EVENT_SCHEMA_VERSION: int = 1


class DispositionOutcome(str, Enum):
    """Possible outcomes from Three Fates deliberation.

    These map directly to DeliberationOutcome but are used in the
    disposition/pipeline routing context for clearer semantics.

    Outcomes:
        ACKNOWLEDGE: Petition heard, no action required
        REFER: Refer to Knight for review
        ESCALATE: Escalate to King for decision
    """

    ACKNOWLEDGE = "ACKNOWLEDGE"
    REFER = "REFER"
    ESCALATE = "ESCALATE"


class PipelineType(str, Enum):
    """Target pipelines for disposition routing.

    Each pipeline corresponds to a downstream epic:
    - ACKNOWLEDGMENT: Epic 3
    - KNIGHT_REFERRAL: Epic 4
    - KING_ESCALATION: Epic 6
    """

    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    KNIGHT_REFERRAL = "KNIGHT_REFERRAL"
    KING_ESCALATION = "KING_ESCALATION"


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class DeliberationCompleteEvent:
    """Event emitted when deliberation reaches consensus (Story 2A.8, FR-11.11).

    Captures the final disposition from Three Fates deliberation,
    including vote breakdown and any dissent.

    Constitutional Constraints:
    - CT-14: Every claim terminates in witnessed fate
    - CT-12: Outcome witnessed by participating archons
    - FR-11.11: Route to appropriate pipeline

    Attributes:
        event_id: UUIDv7 for this event.
        petition_id: UUID of the petition.
        session_id: UUID of the deliberation session.
        outcome: The consensus disposition.
        vote_breakdown: Dict mapping archon_id -> (vote, rationale).
        dissent_present: Whether vote was not unanimous.
        final_witness_hash: Hash of VOTE phase witness for audit chain.
        completed_at: When deliberation completed.
        dissent_archon_id: UUID of dissenter (if any).
        dissent_disposition: What dissenter voted for (if any).
    """

    event_id: UUID
    petition_id: UUID
    session_id: UUID
    outcome: DispositionOutcome
    vote_breakdown: dict[UUID, tuple[DispositionOutcome, str]]
    dissent_present: bool
    final_witness_hash: bytes
    completed_at: datetime = field(default_factory=_utc_now)
    dissent_archon_id: UUID | None = field(default=None)
    dissent_disposition: DispositionOutcome | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate event invariants."""
        self._validate_vote_breakdown()
        self._validate_witness_hash()
        self._validate_dissent()

    def _validate_vote_breakdown(self) -> None:
        """Validate vote breakdown has exactly 3 archon votes."""
        if len(self.vote_breakdown) != 3:
            raise ValueError(
                f"vote_breakdown must contain exactly 3 archon votes, "
                f"got {len(self.vote_breakdown)}"
            )

    def _validate_witness_hash(self) -> None:
        """Validate witness hash is 32 bytes (Blake3)."""
        if len(self.final_witness_hash) != 32:
            raise ValueError(
                f"final_witness_hash must be 32 bytes (Blake3), "
                f"got {len(self.final_witness_hash)}"
            )

    def _validate_dissent(self) -> None:
        """Validate dissent consistency."""
        if self.dissent_present:
            if self.dissent_archon_id is None:
                raise ValueError("dissent_present=True requires dissent_archon_id")
            if self.dissent_disposition is None:
                raise ValueError("dissent_present=True requires dissent_disposition")
            if self.dissent_archon_id not in self.vote_breakdown:
                raise ValueError("dissent_archon_id must be in vote_breakdown")
        else:
            if self.dissent_archon_id is not None:
                raise ValueError("dissent_present=False but dissent_archon_id is set")
            if self.dissent_disposition is not None:
                raise ValueError("dissent_present=False but dissent_disposition is set")

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        # Convert vote breakdown to serializable format
        vote_breakdown_serializable: dict[str, list[str]] = {}
        for archon_id, (vote, rationale) in self.vote_breakdown.items():
            vote_breakdown_serializable[str(archon_id)] = [vote.value, rationale]

        content: dict[str, Any] = {
            "completed_at": self.completed_at.isoformat(),
            "dissent_archon_id": str(self.dissent_archon_id)
            if self.dissent_archon_id
            else None,
            "dissent_disposition": self.dissent_disposition.value
            if self.dissent_disposition
            else None,
            "dissent_present": self.dissent_present,
            "event_id": str(self.event_id),
            "final_witness_hash": self.final_witness_hash.hex(),
            "outcome": self.outcome.value,
            "petition_id": str(self.petition_id),
            "session_id": str(self.session_id),
            "vote_breakdown": vote_breakdown_serializable,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event serialization.

        D2 Compliance: Includes schema_version for deterministic replay.

        Returns:
            Dictionary representation suitable for event payloads.
        """
        # Convert vote breakdown to serializable format
        vote_breakdown_serializable: dict[str, dict[str, str]] = {}
        for archon_id, (vote, rationale) in self.vote_breakdown.items():
            vote_breakdown_serializable[str(archon_id)] = {
                "vote": vote.value,
                "rationale": rationale,
            }

        return {
            "event_id": str(self.event_id),
            "petition_id": str(self.petition_id),
            "session_id": str(self.session_id),
            "outcome": self.outcome.value,
            "vote_breakdown": vote_breakdown_serializable,
            "dissent_present": self.dissent_present,
            "dissent_archon_id": str(self.dissent_archon_id)
            if self.dissent_archon_id
            else None,
            "dissent_disposition": self.dissent_disposition.value
            if self.dissent_disposition
            else None,
            "final_witness_hash": self.final_witness_hash.hex(),
            "completed_at": self.completed_at.isoformat(),
            "schema_version": DISPOSITION_EVENT_SCHEMA_VERSION,
        }


@dataclass(frozen=True, eq=True)
class PipelineRoutingEvent:
    """Event emitted when petition is routed to a pipeline.

    This event tracks the routing decision made after deliberation
    completes, linking the petition to its target downstream pipeline.

    Attributes:
        event_id: UUIDv7 for this event.
        petition_id: UUID of the petition.
        pipeline: Target pipeline type.
        deliberation_event_id: ID of DeliberationCompleteEvent that triggered routing.
        routed_at: When routing occurred.
        routing_metadata: Additional pipeline-specific routing data.
    """

    event_id: UUID
    petition_id: UUID
    pipeline: PipelineType
    deliberation_event_id: UUID
    routed_at: datetime = field(default_factory=_utc_now)
    routing_metadata: dict[str, Any] = field(default_factory=dict)

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "deliberation_event_id": str(self.deliberation_event_id),
            "event_id": str(self.event_id),
            "petition_id": str(self.petition_id),
            "pipeline": self.pipeline.value,
            "routed_at": self.routed_at.isoformat(),
            "routing_metadata": self.routing_metadata,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event serialization.

        D2 Compliance: Includes schema_version for deterministic replay.

        Returns:
            Dictionary representation suitable for event payloads.
        """
        return {
            "event_id": str(self.event_id),
            "petition_id": str(self.petition_id),
            "pipeline": self.pipeline.value,
            "deliberation_event_id": str(self.deliberation_event_id),
            "routed_at": self.routed_at.isoformat(),
            "routing_metadata": self.routing_metadata,
            "schema_version": DISPOSITION_EVENT_SCHEMA_VERSION,
        }
