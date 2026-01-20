"""Deliberation timeout event (Story 2B.2, FR-11.9, HC-7).

This module defines the DeliberationTimeoutEvent for recording when a
deliberation session has exceeded its configured timeout and is being
auto-escalated per constitutional constraints.

Constitutional Constraints:
- FR-11.9: System SHALL enforce deliberation timeout (5 min default) with auto-ESCALATE on expiry
- HC-7: Deliberation timeout auto-ESCALATE - Prevent stuck petitions
- CT-11: Silent failure destroys legitimacy - timeout event MUST be witnessed
- CT-14: Silence is expensive - every petition terminates in witnessed fate
- NFR-3.4: Timeout reliability - 100% timeouts fire
- NFR-10.4: 100% witness completeness
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationPhase

# Event type constant (used by Event envelope)
DELIBERATION_TIMEOUT_EVENT_TYPE: str = "deliberation.timeout.expired"

# Schema version for forward/backward compatibility (D2 requirement)
DELIBERATION_TIMEOUT_SCHEMA_VERSION: int = 1


@dataclass(frozen=True, eq=True)
class DeliberationTimeoutEvent:
    """Event emitted when deliberation times out (Story 2B.2, FR-11.9, HC-7).

    Emitted when a deliberation session exceeds its configured timeout.
    The system will auto-ESCALATE the petition per FR-11.9 and HC-7.

    Constitutional Constraints:
    - FR-11.9: Auto-ESCALATE on timeout expiry
    - HC-7: Prevent stuck petitions via timeout enforcement
    - CT-11: Silent failure destroys legitimacy - event MUST be emitted
    - CT-14: Every petition terminates in witnessed fate
    - NFR-3.4: 100% timeout reliability
    - NFR-10.4: 100% witness completeness

    Attributes:
        event_id: UUIDv7 for this timeout event.
        session_id: UUID of the deliberation session that timed out.
        petition_id: UUID of the petition being deliberated.
        phase_at_timeout: The phase the session was in when it timed out.
        started_at: When the deliberation session started (UTC).
        timeout_at: When the timeout fired (UTC).
        configured_timeout_seconds: The timeout duration that was exceeded.
        participating_archons: Tuple of 3 archon UUIDs assigned to session.
        schema_version: Event schema version for compatibility (D2).
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    session_id: UUID
    petition_id: UUID
    phase_at_timeout: DeliberationPhase
    started_at: datetime
    timeout_at: datetime
    configured_timeout_seconds: int
    participating_archons: tuple[UUID, UUID, UUID]
    schema_version: int = field(default=DELIBERATION_TIMEOUT_SCHEMA_VERSION)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate timeout event invariants.

        Raises:
            ValueError: If any invariant is violated.
        """
        self._validate_archon_count()
        self._validate_timestamps()
        self._validate_timeout_duration()
        self._validate_schema_version()

    def _validate_archon_count(self) -> None:
        """Validate exactly 3 archons were participating."""
        if len(self.participating_archons) != 3:
            raise ValueError(
                f"participating_archons must contain exactly 3 UUIDs, "
                f"got {len(self.participating_archons)}"
            )

    def _validate_timestamps(self) -> None:
        """Validate timeout_at is after started_at."""
        if self.timeout_at < self.started_at:
            raise ValueError("timeout_at must be >= started_at")

    def _validate_timeout_duration(self) -> None:
        """Validate configured timeout is positive."""
        if self.configured_timeout_seconds <= 0:
            raise ValueError(
                f"configured_timeout_seconds must be positive, "
                f"got {self.configured_timeout_seconds}"
            )

    def _validate_schema_version(self) -> None:
        """Validate schema version is current."""
        if self.schema_version != DELIBERATION_TIMEOUT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {DELIBERATION_TIMEOUT_SCHEMA_VERSION}, "
                f"got {self.schema_version}"
            )

    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time from start to timeout.

        Returns:
            Number of seconds elapsed.
        """
        return (self.timeout_at - self.started_at).total_seconds()

    @property
    def was_phase_in_progress(self) -> bool:
        """Check if the session was still in an active phase.

        Returns:
            True if session was in ASSESS, POSITION, CROSS_EXAMINE, or VOTE.
            False if already COMPLETE (shouldn't happen but for safety).
        """
        return not self.phase_at_timeout.is_terminal()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (D2 pattern).

        Uses explicit to_dict() per project-context.md, NOT asdict().

        Returns:
            Dictionary with serializable values.
        """
        return {
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "phase_at_timeout": self.phase_at_timeout.value,
            "started_at": self.started_at.isoformat(),
            "timeout_at": self.timeout_at.isoformat(),
            "configured_timeout_seconds": self.configured_timeout_seconds,
            "participating_archons": [str(a) for a in self.participating_archons],
            "elapsed_seconds": self.elapsed_seconds,
            "schema_version": self.schema_version,
            "created_at": self.created_at.isoformat(),
        }
