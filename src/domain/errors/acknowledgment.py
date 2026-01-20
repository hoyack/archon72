"""Acknowledgment execution errors (Story 3.2, 3.5, FR-3.1, FR-3.5).

This module defines domain errors specific to acknowledgment execution.

Constitutional Constraints:
- FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
- FR-3.5: System SHALL enforce minimum dwell time before ACKNOWLEDGE
- NFR-3.2: Fate assignment atomicity (100% single-fate)
- CT-14: Every claim terminates in visible, witnessed fate
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError

if TYPE_CHECKING:
    from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode


class AcknowledgmentExecutionError(ConstitutionalViolationError):
    """Base error for acknowledgment execution failures."""

    pass


class PetitionNotFoundError(AcknowledgmentExecutionError):
    """Raised when the petition to acknowledge does not exist.

    Attributes:
        petition_id: The UUID of the petition that was not found.
    """

    def __init__(self, petition_id: UUID) -> None:
        self.petition_id = petition_id
        super().__init__(f"Petition not found: {petition_id}")


class PetitionNotInDeliberatingStateError(AcknowledgmentExecutionError):
    """Raised when acknowledgment is attempted on a non-DELIBERATING petition.

    Per FR-3.1, acknowledgment can only occur when deliberation reaches
    consensus. This means the petition must be in DELIBERATING state.

    Attributes:
        petition_id: The petition UUID.
        current_state: The actual state of the petition.
    """

    def __init__(self, petition_id: UUID, current_state: str) -> None:
        self.petition_id = petition_id
        self.current_state = current_state
        super().__init__(
            f"Petition {petition_id} is in state '{current_state}', "
            f"but must be in 'DELIBERATING' state for acknowledgment. "
            f"Per FR-3.1, acknowledgment requires deliberation consensus."
        )


class AcknowledgmentAlreadyExistsError(AcknowledgmentExecutionError):
    """Raised when a petition has already been acknowledged.

    Per NFR-3.2, fate assignment is atomic and single - a petition
    can only be acknowledged once.

    Attributes:
        petition_id: The petition UUID.
        existing_acknowledgment_id: UUID of the existing acknowledgment.
    """

    def __init__(self, petition_id: UUID, existing_acknowledgment_id: UUID) -> None:
        self.petition_id = petition_id
        self.existing_acknowledgment_id = existing_acknowledgment_id
        super().__init__(
            f"Petition {petition_id} has already been acknowledged "
            f"(acknowledgment_id: {existing_acknowledgment_id}). "
            f"Per NFR-3.2, fate assignment is atomic and single."
        )


class InvalidArchonCountError(AcknowledgmentExecutionError):
    """Raised when acknowledgment has invalid archon count.

    Per FR-11.5, supermajority consensus requires at least 2 of 3 archons
    to vote for the same disposition.

    Attributes:
        actual_count: Number of archons provided.
        required_count: Minimum number of archons required.
    """

    def __init__(self, actual_count: int, required_count: int = 2) -> None:
        self.actual_count = actual_count
        self.required_count = required_count
        super().__init__(
            f"Acknowledgment requires at least {required_count} archons, "
            f"but only {actual_count} were provided. "
            f"Per FR-11.5, supermajority (2-of-3) is required."
        )


class InvalidReferencePetitionError(AcknowledgmentExecutionError):
    """Raised when DUPLICATE references a non-existent petition.

    Per FR-3.4, DUPLICATE reason code requires a valid reference
    to the original or already-resolved petition.

    Attributes:
        petition_id: The petition being acknowledged.
        reference_petition_id: The invalid reference UUID.
    """

    def __init__(self, petition_id: UUID, reference_petition_id: UUID) -> None:
        self.petition_id = petition_id
        self.reference_petition_id = reference_petition_id
        super().__init__(
            f"DUPLICATE acknowledgment for petition {petition_id} references "
            f"non-existent petition {reference_petition_id}. "
            f"Per FR-3.4, reference_petition_id must point to an existing petition."
        )


class WitnessHashGenerationError(AcknowledgmentExecutionError):
    """Raised when witness hash cannot be generated.

    Per CT-12, every acknowledgment must be witnessed with a hash.

    Attributes:
        petition_id: The petition being acknowledged.
        reason: Why hash generation failed.
    """

    def __init__(self, petition_id: UUID, reason: str) -> None:
        self.petition_id = petition_id
        self.reason = reason
        super().__init__(
            f"Failed to generate witness hash for acknowledgment of "
            f"petition {petition_id}: {reason}. "
            f"Per CT-12, witnessing is required."
        )


class DwellTimeNotElapsedError(AcknowledgmentExecutionError):
    """Raised when acknowledgment is attempted before minimum dwell time.

    Per FR-3.5, the system SHALL enforce minimum dwell time before ACKNOWLEDGE
    to ensure petitions receive adequate deliberation time.

    This error indicates the petition has not been in DELIBERATING state
    long enough. The caller should wait and retry after the remaining time.

    Attributes:
        petition_id: The petition being acknowledged.
        deliberation_started_at: When the petition entered DELIBERATING state.
        min_dwell_seconds: The configured minimum dwell time.
        elapsed_seconds: How long the petition has been deliberating.
        remaining_seconds: How much longer to wait.
    """

    def __init__(
        self,
        petition_id: UUID,
        deliberation_started_at: datetime,
        min_dwell_seconds: int,
        elapsed_seconds: float,
    ) -> None:
        self.petition_id = petition_id
        self.deliberation_started_at = deliberation_started_at
        self.min_dwell_seconds = min_dwell_seconds
        self.elapsed_seconds = elapsed_seconds
        self.remaining_seconds = max(0, min_dwell_seconds - elapsed_seconds)
        super().__init__(
            f"Petition {petition_id} has only been deliberating for "
            f"{elapsed_seconds:.1f} seconds, but minimum dwell time is "
            f"{min_dwell_seconds} seconds. Remaining: {self.remaining_seconds:.1f} seconds. "
            f"Per FR-3.5, acknowledgment is delayed until dwell time passes."
        )

    @property
    def remaining_timedelta(self) -> timedelta:
        """Get remaining wait time as timedelta."""
        return timedelta(seconds=self.remaining_seconds)


class DeliberationSessionNotFoundError(AcknowledgmentExecutionError):
    """Raised when the deliberation session for a petition cannot be found.

    This error indicates inconsistent state - a petition is in DELIBERATING
    state but has no associated deliberation session.

    Attributes:
        petition_id: The petition UUID.
    """

    def __init__(self, petition_id: UUID) -> None:
        self.petition_id = petition_id
        super().__init__(
            f"No deliberation session found for petition {petition_id}, "
            f"but petition is in DELIBERATING state. "
            f"This indicates inconsistent state."
        )
