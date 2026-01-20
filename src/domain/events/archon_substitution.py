"""Archon substitution events (Story 2B.4, NFR-10.6).

This module defines events for Archon failure and substitution during deliberation.
Substitution ensures deliberation can continue despite individual agent failure.

Constitutional Constraints:
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment, not unilateral decision
- CT-11: Silent failure destroys legitimacy - failures must be handled gracefully
- CT-14: Silence must be expensive - every petition terminates in witnessed fate
- NFR-10.6: Archon substitution latency < 10 seconds on failure
- NFR-10.2: Individual Archon response time p95 < 30 seconds
- NFR-10.4: 100% witness completeness
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationPhase

# =============================================================================
# Event Type Constants
# =============================================================================

# Event emitted when an Archon is successfully substituted
ARCHON_SUBSTITUTED_EVENT_TYPE: str = "deliberation.archon.substituted"

# Event emitted when deliberation is aborted due to multiple failures or pool exhaustion
DELIBERATION_ABORTED_EVENT_TYPE: str = "deliberation.aborted"

# Schema version for forward/backward compatibility (D2 requirement)
ARCHON_SUBSTITUTION_SCHEMA_VERSION: int = 1


@dataclass(frozen=True, eq=True)
class ArchonSubstitutedEvent:
    """Event emitted when an Archon is substituted during deliberation (Story 2B.4).

    This event is witnessed in the hash chain. Substitution ensures
    deliberation can continue despite individual agent failure.

    Constitutional Constraints:
    - AT-6: Maintains 3 active Archons for collective judgment
    - CT-11: Silent failure destroys legitimacy - substitution is recorded
    - NFR-10.6: substitution_latency_ms must be < 10000 (10 seconds)
    - NFR-10.4: 100% witness completeness

    Attributes:
        event_id: UUIDv7 for this event.
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        failed_archon_id: ID of the Archon that failed.
        substitute_archon_id: ID of the replacement Archon.
        phase_at_failure: Which phase the failure occurred in.
        failure_reason: Why the Archon failed (RESPONSE_TIMEOUT, API_ERROR, INVALID_RESPONSE).
        substitution_latency_ms: Time from failure detection to substitute ready (ms).
        transcript_pages_provided: Count of transcript pages given to substitute.
        schema_version: Event schema version for compatibility (D2).
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    session_id: UUID
    petition_id: UUID
    failed_archon_id: UUID
    substitute_archon_id: UUID
    phase_at_failure: DeliberationPhase
    failure_reason: str
    substitution_latency_ms: int
    transcript_pages_provided: int
    schema_version: int = field(default=ARCHON_SUBSTITUTION_SCHEMA_VERSION)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Valid failure reasons per AC-6
    VALID_FAILURE_REASONS: tuple[str, ...] = (
        "RESPONSE_TIMEOUT",
        "API_ERROR",
        "INVALID_RESPONSE",
    )

    # Maximum latency per NFR-10.6
    MAX_SUBSTITUTION_LATENCY_MS: int = 10_000

    def __post_init__(self) -> None:
        """Validate event invariants.

        Raises:
            ValueError: If any invariant is violated.
        """
        self._validate_different_archons()
        self._validate_failure_reason()
        self._validate_latency()
        self._validate_transcript_pages()
        self._validate_schema_version()

    def _validate_different_archons(self) -> None:
        """Validate failed and substitute archons are different."""
        if self.failed_archon_id == self.substitute_archon_id:
            raise ValueError(
                "failed_archon_id and substitute_archon_id must be different"
            )

    def _validate_failure_reason(self) -> None:
        """Validate failure_reason is one of the expected values."""
        if self.failure_reason not in self.VALID_FAILURE_REASONS:
            raise ValueError(
                f"failure_reason must be one of {self.VALID_FAILURE_REASONS}, "
                f"got '{self.failure_reason}'"
            )

    def _validate_latency(self) -> None:
        """Validate latency is non-negative."""
        if self.substitution_latency_ms < 0:
            raise ValueError(
                f"substitution_latency_ms must be >= 0, "
                f"got {self.substitution_latency_ms}"
            )

    def _validate_transcript_pages(self) -> None:
        """Validate transcript_pages_provided is non-negative."""
        if self.transcript_pages_provided < 0:
            raise ValueError(
                f"transcript_pages_provided must be >= 0, "
                f"got {self.transcript_pages_provided}"
            )

    def _validate_schema_version(self) -> None:
        """Validate schema version is current."""
        if self.schema_version != ARCHON_SUBSTITUTION_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {ARCHON_SUBSTITUTION_SCHEMA_VERSION}, "
                f"got {self.schema_version}"
            )

    @property
    def met_latency_sla(self) -> bool:
        """Check if substitution met the NFR-10.6 latency SLA.

        Returns:
            True if substitution_latency_ms <= 10000.
        """
        return self.substitution_latency_ms <= self.MAX_SUBSTITUTION_LATENCY_MS

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (D2 pattern).

        Uses explicit to_dict() per project-context.md, NOT asdict().

        Returns:
            Dictionary with serializable values.
        """
        return {
            "event_type": ARCHON_SUBSTITUTED_EVENT_TYPE,
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "failed_archon_id": str(self.failed_archon_id),
            "substitute_archon_id": str(self.substitute_archon_id),
            "phase_at_failure": self.phase_at_failure.value,
            "failure_reason": self.failure_reason,
            "substitution_latency_ms": self.substitution_latency_ms,
            "transcript_pages_provided": self.transcript_pages_provided,
            "schema_version": self.schema_version,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class DeliberationAbortedEvent:
    """Event emitted when deliberation is aborted due to failures (Story 2B.4, AC-7, AC-8).

    This is a terminal event - the petition will be ESCALATED.
    Emitted when 2+ Archons fail or the pool is exhausted.

    Constitutional Constraints:
    - AT-1: Every petition terminates in exactly one of Three Fates (ESCALATE)
    - CT-11: Silent failure destroys legitimacy - abort must be recorded
    - CT-14: Silence must be expensive - petition still terminates
    - NFR-10.4: 100% witness completeness

    Attributes:
        event_id: UUIDv7 for this abort event.
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        reason: Why deliberation was aborted (INSUFFICIENT_ARCHONS or ARCHON_POOL_EXHAUSTED).
        failed_archons: Details of Archons that failed.
        surviving_archon_id: ID of any Archon that didn't fail (optional).
        phase_at_abort: Which phase the abort occurred in.
        schema_version: Event schema version for compatibility (D2).
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    session_id: UUID
    petition_id: UUID
    reason: str
    failed_archons: tuple[dict[str, Any], ...]
    phase_at_abort: DeliberationPhase
    surviving_archon_id: UUID | None = field(default=None)
    schema_version: int = field(default=ARCHON_SUBSTITUTION_SCHEMA_VERSION)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Valid abort reasons per AC-7, AC-8
    VALID_ABORT_REASONS: tuple[str, ...] = (
        "INSUFFICIENT_ARCHONS",
        "ARCHON_POOL_EXHAUSTED",
    )

    def __post_init__(self) -> None:
        """Validate abort event invariants.

        Raises:
            ValueError: If any invariant is violated.
        """
        self._validate_reason()
        self._validate_failed_archons()
        self._validate_schema_version()

    def _validate_reason(self) -> None:
        """Validate reason is one of the expected values."""
        if self.reason not in self.VALID_ABORT_REASONS:
            raise ValueError(
                f"reason must be one of {self.VALID_ABORT_REASONS}, got '{self.reason}'"
            )

    def _validate_failed_archons(self) -> None:
        """Validate failed_archons is not empty and has required fields."""
        if not self.failed_archons:
            raise ValueError("failed_archons must not be empty")

        required_fields = {"archon_id", "failure_reason", "phase"}
        for i, archon_info in enumerate(self.failed_archons):
            missing = required_fields - set(archon_info.keys())
            if missing:
                raise ValueError(
                    f"failed_archons[{i}] missing required fields: {missing}"
                )

    def _validate_schema_version(self) -> None:
        """Validate schema version is current."""
        if self.schema_version != ARCHON_SUBSTITUTION_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {ARCHON_SUBSTITUTION_SCHEMA_VERSION}, "
                f"got {self.schema_version}"
            )

    @property
    def failed_archon_count(self) -> int:
        """Get the number of Archons that failed.

        Returns:
            Count of failed Archons.
        """
        return len(self.failed_archons)

    @property
    def was_pool_exhausted(self) -> bool:
        """Check if abort was due to pool exhaustion.

        Returns:
            True if reason is ARCHON_POOL_EXHAUSTED.
        """
        return self.reason == "ARCHON_POOL_EXHAUSTED"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (D2 pattern).

        Uses explicit to_dict() per project-context.md, NOT asdict().

        Returns:
            Dictionary with serializable values.
        """
        return {
            "event_type": DELIBERATION_ABORTED_EVENT_TYPE,
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "reason": self.reason,
            "failed_archons": list(self.failed_archons),
            "surviving_archon_id": (
                str(self.surviving_archon_id) if self.surviving_archon_id else None
            ),
            "phase_at_abort": self.phase_at_abort.value,
            "schema_version": self.schema_version,
            "created_at": self.created_at.isoformat(),
        }
