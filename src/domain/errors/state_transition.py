"""State transition errors for petition state machine (Story 1.5, FR-2.1, FR-2.3).

This module defines errors for invalid petition state transitions.

Constitutional Constraints:
- FR-2.1: System SHALL enforce valid state transitions only
- FR-2.3: System SHALL reject transitions not in transition matrix
- FR-2.6: System SHALL mark petition as terminal when fate assigned
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.errors.constitutional import ConstitutionalViolationError

if TYPE_CHECKING:
    from src.domain.models.petition_submission import PetitionState


class InvalidStateTransitionError(ConstitutionalViolationError):
    """Raised when an invalid state transition is attempted (FR-2.1, FR-2.3).

    This error is raised when code attempts to transition a petition
    to a state not permitted by the transition matrix.

    Constitutional Constraints:
    - FR-2.1: System SHALL enforce valid state transitions only
    - FR-2.3: System SHALL reject transitions not in transition matrix

    Attributes:
        from_state: Current state of the petition.
        to_state: Attempted target state.
        allowed_transitions: List of valid target states from current state.
    """

    def __init__(
        self,
        from_state: PetitionState,
        to_state: PetitionState,
        allowed_transitions: list[PetitionState] | None = None,
    ) -> None:
        """Initialize invalid state transition error.

        Args:
            from_state: Current petition state.
            to_state: Attempted invalid target state.
            allowed_transitions: Valid states from current state (optional).
        """
        self.from_state = from_state
        self.to_state = to_state
        self.allowed_transitions = allowed_transitions or []

        allowed_str = (
            f" Valid transitions: {[s.value for s in self.allowed_transitions]}"
            if self.allowed_transitions
            else ""
        )
        super().__init__(
            f"Invalid state transition: {from_state.value} -> {to_state.value}.{allowed_str}"
        )


class PetitionAlreadyFatedError(ConstitutionalViolationError):
    """Raised when attempting to modify a petition in terminal state (FR-2.6).

    Once a petition has been assigned a fate (ACKNOWLEDGED, REFERRED, ESCALATED,
    DEFERRED, or NO_RESPONSE), no further state transitions are permitted. This
    ensures the integrity of the Three Fates deliberation system.

    Constitutional Constraints:
    - FR-2.6: System SHALL mark petition as terminal when fate assigned
    - AT-1: Every petition terminates in exactly one of Three Fates

    Attributes:
        petition_id: UUID of the petition.
        terminal_state: The terminal fate state the petition is in.
    """

    def __init__(
        self,
        petition_id: str,
        terminal_state: PetitionState,
    ) -> None:
        """Initialize petition already fated error.

        Args:
            petition_id: UUID string of the petition.
            terminal_state: The terminal state (ACKNOWLEDGED/REFERRED/ESCALATED/DEFERRED/NO_RESPONSE).
        """
        self.petition_id = petition_id
        self.terminal_state = terminal_state
        super().__init__(
            f"Petition {petition_id} already has fate: {terminal_state.value}. "
            "Terminal states cannot be modified."
        )
