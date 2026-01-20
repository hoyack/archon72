"""Petition submission domain model (Story 0.2, FR-2.2, Story 1.5).

This module defines the core petition domain for the Three Fates
deliberation system. This is SEPARATE from the existing petition
model (Story 7.2 co-signing petitions).

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Track all petitions
- CT-12: Witnessing creates accountability -> Frozen dataclass
- FR-2.1: System SHALL enforce valid state transitions only
- FR-2.2: States: RECEIVED, DELIBERATING, ACKNOWLEDGED, REFERRED, ESCALATED
- FR-2.3: System SHALL reject transitions not in transition matrix
- FR-2.6: System SHALL mark petition as terminal when fate assigned
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class PetitionType(Enum):
    """Type of petition submitted to the system.

    Types:
        GENERAL: General governance petition
        CESSATION: Request for system cessation review
        GRIEVANCE: Complaint about system behavior
        COLLABORATION: Request for inter-realm collaboration
    """

    GENERAL = "GENERAL"
    CESSATION = "CESSATION"
    GRIEVANCE = "GRIEVANCE"
    COLLABORATION = "COLLABORATION"


class PetitionState(Enum):
    """State in the petition lifecycle (FR-2.2, Story 1.5, FR-5.1).

    State Machine (FR-2.1, FR-2.3, FR-5.1):
        RECEIVED -> DELIBERATING (fate assignment begins)
        RECEIVED -> ACKNOWLEDGED (withdrawn before deliberation)
        RECEIVED -> ESCALATED (auto-escalation when co-signer threshold reached, FR-5.1)
        DELIBERATING -> ACKNOWLEDGED (Three Fates acknowledge)
        DELIBERATING -> REFERRED (referred to Knight)
        DELIBERATING -> ESCALATED (escalated to King)

    Terminal States (FR-2.6):
        ACKNOWLEDGED, REFERRED, ESCALATED are terminal (Three Fates).
        Once a petition reaches a terminal state, no further transitions
        are permitted (AT-1: exactly one fate per petition).

    States:
        RECEIVED: Initial state after submission
        DELIBERATING: Three Fates deliberation in progress
        ACKNOWLEDGED: Petition acknowledged (terminal fate)
        REFERRED: Referred to Knight for review (terminal fate)
        ESCALATED: Escalated to King for adoption (terminal fate)
    """

    RECEIVED = "RECEIVED"
    DELIBERATING = "DELIBERATING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REFERRED = "REFERRED"
    ESCALATED = "ESCALATED"

    def is_terminal(self) -> bool:
        """Check if this state is a terminal fate (FR-2.6).

        Terminal states are the Three Fates: ACKNOWLEDGED, REFERRED, ESCALATED.
        Once a petition reaches a terminal state, no further transitions
        are permitted.

        Returns:
            True if this is a terminal state, False otherwise.
        """
        return self in TERMINAL_STATES

    def valid_transitions(self) -> frozenset[PetitionState]:
        """Get valid transitions from this state (FR-2.3).

        Returns:
            Frozenset of states this state can transition to.
            Empty set for terminal states.
        """
        return STATE_TRANSITION_MATRIX.get(self, frozenset())


# Terminal states - the Three Fates (FR-2.6, AT-1)
TERMINAL_STATES: frozenset[PetitionState] = frozenset(
    {
        PetitionState.ACKNOWLEDGED,
        PetitionState.REFERRED,
        PetitionState.ESCALATED,
    }
)

# State transition matrix (FR-2.1, FR-2.3, FR-5.1)
# Maps each state to its valid target states
STATE_TRANSITION_MATRIX: dict[PetitionState, frozenset[PetitionState]] = {
    # RECEIVED can go to:
    # - DELIBERATING (normal flow)
    # - ACKNOWLEDGED (withdrawal)
    # - ESCALATED (auto-escalation when co-signer threshold reached, FR-5.1)
    #   Constitutional: CT-14 "Silence must be expensive" - petitions with
    #   sufficient collective support bypass deliberation to reach King attention
    PetitionState.RECEIVED: frozenset(
        {
            PetitionState.DELIBERATING,
            PetitionState.ACKNOWLEDGED,
            PetitionState.ESCALATED,
        }
    ),
    # DELIBERATING can reach any of the Three Fates
    PetitionState.DELIBERATING: frozenset(
        {
            PetitionState.ACKNOWLEDGED,
            PetitionState.REFERRED,
            PetitionState.ESCALATED,
        }
    ),
    # Terminal states have no valid transitions
    PetitionState.ACKNOWLEDGED: frozenset(),
    PetitionState.REFERRED: frozenset(),
    PetitionState.ESCALATED: frozenset(),
}


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class PetitionSubmission:
    """A petition submission for Three Fates deliberation.

    Constitutional Constraints:
    - CT-12: Frozen dataclass ensures immutability
    - FR-2.2: State field supports required lifecycle states
    - HP-2: content_hash field ready for Blake3 (Story 0.5)
    - FR-7.4: co_signer_count exposed in status response (Story 1.8)

    Attributes:
        id: UUIDv7 unique identifier.
        type: Type of petition (GENERAL, CESSATION, etc.).
        text: Petition content (max 10,000 chars).
        submitter_id: UUID of submitter (optional for anonymous).
        state: Current lifecycle state.
        content_hash: Blake3 hash bytes (32 bytes, optional until HP-2).
        realm: Routing realm for processing.
        created_at: Submission timestamp (UTC).
        updated_at: Last modification timestamp (UTC).
        fate_reason: Reason for fate assignment (for terminal states).
        co_signer_count: Number of co-signers (FR-7.4, placeholder until Epic 5).
    """

    id: UUID
    type: PetitionType
    text: str
    state: PetitionState = field(default=PetitionState.RECEIVED)
    submitter_id: UUID | None = field(default=None)
    content_hash: bytes | None = field(default=None)
    realm: str = field(default="default")
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    fate_reason: str | None = field(default=None)
    co_signer_count: int = field(default=0)

    MAX_TEXT_LENGTH: int = 10_000

    def __post_init__(self) -> None:
        """Validate petition submission fields."""
        if len(self.text) > self.MAX_TEXT_LENGTH:
            raise ValueError(
                f"Petition text exceeds maximum length of {self.MAX_TEXT_LENGTH} characters"
            )
        if self.content_hash is not None and len(self.content_hash) != 32:
            raise ValueError("Content hash must be 32 bytes (Blake3)")

    def with_state(
        self,
        new_state: PetitionState,
        reason: str | None = None,
    ) -> PetitionSubmission:
        """Create new petition with updated state (FR-2.1, FR-2.3, FR-2.6, Story 1.8).

        Enforces the petition state machine transition matrix.
        Raises appropriate exceptions for invalid transitions.

        Since PetitionSubmission is frozen, returns new instance.

        Args:
            new_state: The new state to transition to.
            reason: Optional reason for fate assignment (for terminal states).

        Returns:
            New PetitionSubmission with updated state and timestamp.

        Raises:
            PetitionAlreadyFatedError: If petition is in terminal state (FR-2.6).
            InvalidStateTransitionError: If transition is not valid (FR-2.1, FR-2.3).
        """
        # Import here to avoid circular dependency
        from src.domain.errors.state_transition import (
            InvalidStateTransitionError,
            PetitionAlreadyFatedError,
        )

        # Check for terminal state first (FR-2.6)
        if self.state.is_terminal():
            raise PetitionAlreadyFatedError(
                petition_id=str(self.id),
                terminal_state=self.state,
            )

        # Check if transition is valid (FR-2.1, FR-2.3)
        valid_transitions = self.state.valid_transitions()
        if new_state not in valid_transitions:
            raise InvalidStateTransitionError(
                from_state=self.state,
                to_state=new_state,
                allowed_transitions=list(valid_transitions),
            )

        # Preserve existing fate_reason if not provided
        effective_reason = reason if reason is not None else self.fate_reason

        return PetitionSubmission(
            id=self.id,
            type=self.type,
            text=self.text,
            state=new_state,
            submitter_id=self.submitter_id,
            content_hash=self.content_hash,
            realm=self.realm,
            created_at=self.created_at,
            updated_at=_utc_now(),
            fate_reason=effective_reason,
            co_signer_count=self.co_signer_count,
        )

    def with_content_hash(self, content_hash: bytes) -> PetitionSubmission:
        """Create new petition with content hash set.

        Used by HP-2 (Blake3 hashing service) for duplicate detection.

        Args:
            content_hash: 32-byte Blake3 hash.

        Returns:
            New PetitionSubmission with content hash set.
        """
        return PetitionSubmission(
            id=self.id,
            type=self.type,
            text=self.text,
            state=self.state,
            submitter_id=self.submitter_id,
            content_hash=content_hash,
            realm=self.realm,
            created_at=self.created_at,
            updated_at=_utc_now(),
            fate_reason=self.fate_reason,
            co_signer_count=self.co_signer_count,
        )

    def canonical_content_bytes(self) -> bytes:
        """Return canonical bytes for content hashing.

        Used by HP-2 (Blake3 hashing service) for duplicate detection.

        Returns:
            UTF-8 encoded petition text.
        """
        return self.text.encode("utf-8")
