"""Audit timeline domain models (Story 2B.6, FR-11.12, NFR-6.5).

This module defines the domain models for audit trail reconstruction,
enabling complete deliberation timeline replay and verification.

Constitutional Constraints:
- FR-11.12: Complete deliberation transcript preservation for audit
- NFR-6.5: Full state history reconstruction from event log
- CT-12: Every action witnessed - verify unbroken chain of accountability
- CT-14: Every claim terminates in visible, witnessed fate
- NFR-4.2: Event log durability - append-only, no deletion
- NFR-10.4: 100% witness completeness

Developer Golden Rules:
1. All models are immutable (frozen dataclasses)
2. All models include schema_version for D2 compliance
3. Use to_dict() not asdict() for serialization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

# Schema version for audit timeline models (D2 compliance)
AUDIT_TIMELINE_SCHEMA_VERSION: int = 1

# Blake3 hash size in bytes
BLAKE3_HASH_SIZE: int = 32


class TerminationReason(str, Enum):
    """Reason why a deliberation terminated (Story 2B.6).

    Deliberations can terminate normally with consensus, or
    be forced to terminate due to timeout, deadlock, or abort.

    Values:
        NORMAL: Consensus reached normally (2-of-3 supermajority)
        TIMEOUT: Deliberation timed out (FR-11.9, HC-7)
        DEADLOCK: Max rounds without consensus (FR-11.10, CT-11)
        ABORT: Multiple archon failures (Story 2B.4, AC-7, AC-8)
    """

    NORMAL = "NORMAL"
    TIMEOUT = "TIMEOUT"
    DEADLOCK = "DEADLOCK"
    ABORT = "ABORT"


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class TimelineEvent:
    """A single event in the audit timeline (Story 2B.6, NFR-6.5).

    Represents any event that occurred during deliberation, providing
    a unified view for audit trail reconstruction. Events are immutable
    and include optional witness hashes for verified events.

    Constitutional Constraints:
    - CT-12: Witnessed events include witness_hash
    - NFR-6.5: Enables full state history reconstruction
    - NFR-4.2: Immutable once created

    Attributes:
        event_id: UUIDv7 of the event.
        event_type: String identifying event kind.
        occurred_at: Timestamp of the event (UTC).
        payload: Dict with event-specific data.
        witness_hash: Optional Blake3 hash for witnessed events (32 bytes).
    """

    event_id: UUID
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    witness_hash: bytes | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate timeline event invariants.

        Raises:
            ValueError: If event_type is empty or witness_hash is wrong size.
        """
        if not self.event_type:
            raise ValueError("event_type cannot be empty")
        if self.witness_hash is not None and len(self.witness_hash) != BLAKE3_HASH_SIZE:
            raise ValueError(
                f"witness_hash must be {BLAKE3_HASH_SIZE} bytes (Blake3), "
                f"got {len(self.witness_hash)}"
            )

    @property
    def witness_hash_hex(self) -> str | None:
        """Return witness hash as hex string if present.

        Returns:
            Hex-encoded witness hash (64 chars) or None.
        """
        if self.witness_hash is None:
            return None
        return self.witness_hash.hex()

    @property
    def has_witness(self) -> bool:
        """Check if this event has a witness hash.

        Returns:
            True if witness_hash is present.
        """
        return self.witness_hash is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        D2 Compliance: Includes schema_version.

        Returns:
            Dictionary representation suitable for storage/events.
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self.payload,
            "witness_hash": self.witness_hash_hex,
            "schema_version": AUDIT_TIMELINE_SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineEvent:
        """Create TimelineEvent from dictionary.

        Args:
            data: Dictionary with event_id, event_type, occurred_at, etc.

        Returns:
            TimelineEvent instance.

        Raises:
            ValueError: If required fields are missing.
        """
        event_id_str = data.get("event_id")
        if not event_id_str:
            raise ValueError("event_id is required")

        event_type = data.get("event_type")
        if not event_type:
            raise ValueError("event_type is required")

        occurred_at_str = data.get("occurred_at")
        if not occurred_at_str:
            raise ValueError("occurred_at is required")
        occurred_at = datetime.fromisoformat(occurred_at_str)

        payload = data.get("payload", {})

        witness_hash_hex = data.get("witness_hash")
        witness_hash = bytes.fromhex(witness_hash_hex) if witness_hash_hex else None

        return cls(
            event_id=UUID(event_id_str),
            event_type=event_type,
            occurred_at=occurred_at,
            payload=payload,
            witness_hash=witness_hash,
        )


@dataclass(frozen=True, eq=True)
class WitnessChainVerification:
    """Result of witness chain verification (Story 2B.6, CT-12).

    Captures the results of verifying the witness hash chain
    and transcript integrity for a deliberation session.

    Constitutional Constraints:
    - CT-12: Verify unbroken chain of accountability
    - NFR-10.4: Verify 100% witness completeness

    Attributes:
        is_valid: True if entire chain verifies.
        broken_links: Tuple of (from_event_id, to_event_id) where chain breaks.
        missing_transcripts: Tuple of transcript hashes not found in store.
        integrity_failures: Tuple of transcript hashes that don't verify.
        verified_events: Count of events successfully verified.
        total_events: Total events that should have been verified.
    """

    is_valid: bool
    broken_links: tuple[tuple[UUID, UUID], ...] = field(default_factory=tuple)
    missing_transcripts: tuple[bytes, ...] = field(default_factory=tuple)
    integrity_failures: tuple[bytes, ...] = field(default_factory=tuple)
    verified_events: int = field(default=0)
    total_events: int = field(default=0)

    def __post_init__(self) -> None:
        """Validate verification result invariants.

        Raises:
            ValueError: If verified_events > total_events.
        """
        if self.verified_events < 0:
            raise ValueError(
                f"verified_events must be >= 0, got {self.verified_events}"
            )
        if self.total_events < 0:
            raise ValueError(f"total_events must be >= 0, got {self.total_events}")
        if self.verified_events > self.total_events:
            raise ValueError(
                f"verified_events ({self.verified_events}) cannot exceed "
                f"total_events ({self.total_events})"
            )
        # Validate missing_transcripts are 32 bytes
        for h in self.missing_transcripts:
            if len(h) != BLAKE3_HASH_SIZE:
                raise ValueError(
                    f"missing_transcripts hashes must be {BLAKE3_HASH_SIZE} bytes, "
                    f"got {len(h)}"
                )
        # Validate integrity_failures are 32 bytes
        for h in self.integrity_failures:
            if len(h) != BLAKE3_HASH_SIZE:
                raise ValueError(
                    f"integrity_failures hashes must be {BLAKE3_HASH_SIZE} bytes, "
                    f"got {len(h)}"
                )

    @property
    def has_broken_links(self) -> bool:
        """Check if any chain links are broken.

        Returns:
            True if broken_links is not empty.
        """
        return len(self.broken_links) > 0

    @property
    def has_missing_transcripts(self) -> bool:
        """Check if any transcripts are missing.

        Returns:
            True if missing_transcripts is not empty.
        """
        return len(self.missing_transcripts) > 0

    @property
    def has_integrity_failures(self) -> bool:
        """Check if any transcripts failed integrity check.

        Returns:
            True if integrity_failures is not empty.
        """
        return len(self.integrity_failures) > 0

    @property
    def verification_coverage(self) -> float:
        """Calculate verification coverage ratio.

        Returns:
            Ratio of verified_events to total_events (0.0 to 1.0).
            Returns 1.0 if total_events is 0.
        """
        if self.total_events == 0:
            return 1.0
        return self.verified_events / self.total_events

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        D2 Compliance: Includes schema_version.

        Returns:
            Dictionary representation suitable for storage/events.
        """
        return {
            "is_valid": self.is_valid,
            "broken_links": [
                [str(from_id), str(to_id)] for from_id, to_id in self.broken_links
            ],
            "missing_transcripts": [h.hex() for h in self.missing_transcripts],
            "integrity_failures": [h.hex() for h in self.integrity_failures],
            "verified_events": self.verified_events,
            "total_events": self.total_events,
            "verification_coverage": self.verification_coverage,
            "schema_version": AUDIT_TIMELINE_SCHEMA_VERSION,
        }


# Required archon count (same as DeliberationSession)
REQUIRED_ARCHON_COUNT = 3


@dataclass(frozen=True, eq=True)
class AuditTimeline:
    """Complete audit timeline for a deliberation session (Story 2B.6, FR-11.12).

    Provides a full chronological reconstruction of a deliberation,
    enabling complete audit trail verification per NFR-6.5.

    Constitutional Constraints:
    - FR-11.12: Complete deliberation transcript preservation
    - NFR-6.5: Full state history reconstruction
    - CT-12: Unbroken chain of accountability
    - CT-14: Every claim terminates in visible, witnessed fate

    Attributes:
        session_id: UUID of the deliberation session.
        petition_id: UUID of the petition.
        events: Tuple of TimelineEvents in chronological order.
        assigned_archons: Initial 3-archon assignment.
        outcome: Final outcome (ACKNOWLEDGE, REFER, ESCALATE).
        termination_reason: Normal, Timeout, Deadlock, or Abort.
        started_at: When deliberation started (UTC).
        completed_at: When deliberation completed (UTC).
        witness_chain_valid: Boolean indicating if all witnesses verify.
        transcripts: Dict mapping phase name to transcript content.
        dissent_record: Optional dissent record if 2-1 vote.
        substitutions: Tuple of substitution records if any occurred.
    """

    session_id: UUID
    petition_id: UUID
    events: tuple[TimelineEvent, ...]
    assigned_archons: tuple[UUID, UUID, UUID]
    outcome: str  # ACKNOWLEDGE, REFER, ESCALATE
    termination_reason: TerminationReason
    started_at: datetime
    completed_at: datetime | None = field(default=None)
    witness_chain_valid: bool = field(default=False)
    transcripts: dict[str, str | None] = field(default_factory=dict)
    dissent_record: dict[str, Any] | None = field(default=None)
    substitutions: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate audit timeline invariants.

        Raises:
            ValueError: If archon count wrong or outcome invalid.
        """
        # Validate archon count
        if len(self.assigned_archons) != REQUIRED_ARCHON_COUNT:
            raise ValueError(
                f"assigned_archons must contain exactly {REQUIRED_ARCHON_COUNT} UUIDs, "
                f"got {len(self.assigned_archons)}"
            )
        # Validate archons are unique
        if len(set(self.assigned_archons)) != REQUIRED_ARCHON_COUNT:
            raise ValueError("assigned_archons must be unique")
        # Validate outcome is one of Three Fates
        valid_outcomes = ("ACKNOWLEDGE", "REFER", "ESCALATE")
        if self.outcome not in valid_outcomes:
            raise ValueError(
                f"outcome must be one of {valid_outcomes}, got '{self.outcome}'"
            )

    @property
    def event_count(self) -> int:
        """Get total number of events in timeline.

        Returns:
            Count of events.
        """
        return len(self.events)

    @property
    def has_dissent(self) -> bool:
        """Check if deliberation had a dissent.

        Returns:
            True if dissent_record is present.
        """
        return self.dissent_record is not None

    @property
    def has_substitutions(self) -> bool:
        """Check if any archon substitutions occurred.

        Returns:
            True if substitutions is not empty.
        """
        return len(self.substitutions) > 0

    @property
    def duration_seconds(self) -> float | None:
        """Get duration of deliberation in seconds.

        Returns:
            Duration in seconds, or None if not completed.
        """
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def is_normal_completion(self) -> bool:
        """Check if deliberation completed normally.

        Returns:
            True if termination_reason is NORMAL.
        """
        return self.termination_reason == TerminationReason.NORMAL

    @property
    def was_forced_escalation(self) -> bool:
        """Check if outcome was forced (timeout, deadlock, abort).

        Returns:
            True if termination was not NORMAL.
        """
        return self.termination_reason != TerminationReason.NORMAL

    def get_events_by_type(self, event_type: str) -> tuple[TimelineEvent, ...]:
        """Filter events by type.

        Args:
            event_type: Event type string to filter by.

        Returns:
            Tuple of matching TimelineEvents.
        """
        return tuple(e for e in self.events if e.event_type == event_type)

    def get_transcript(self, phase: str) -> str | None:
        """Get transcript content for a specific phase.

        Args:
            phase: Phase name (ASSESS, POSITION, CROSS_EXAMINE, VOTE).

        Returns:
            Transcript content or None if not available.
        """
        return self.transcripts.get(phase)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        D2 Compliance: Includes schema_version.

        Returns:
            Dictionary representation suitable for storage/events.
        """
        return {
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "events": [e.to_dict() for e in self.events],
            "assigned_archons": [str(a) for a in self.assigned_archons],
            "outcome": self.outcome,
            "termination_reason": self.termination_reason.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "witness_chain_valid": self.witness_chain_valid,
            "transcripts": self.transcripts,
            "dissent_record": self.dissent_record,
            "substitutions": list(self.substitutions),
            "event_count": self.event_count,
            "duration_seconds": self.duration_seconds,
            "has_dissent": self.has_dissent,
            "has_substitutions": self.has_substitutions,
            "was_forced_escalation": self.was_forced_escalation,
            "schema_version": AUDIT_TIMELINE_SCHEMA_VERSION,
        }
