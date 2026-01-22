"""Petition submission repository stub implementation (Story 0.3, AC3, Story 1.6).

This module provides an in-memory stub implementation of
PetitionSubmissionRepositoryProtocol for development and testing purposes.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All operations logged
- CT-12: Witnessing creates accountability → All writes tracked
- FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
- FR-9.4: Petition ID preservation is MANDATORY during migration
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.domain.errors.concurrent_modification import ConcurrentModificationError
from src.domain.errors.state_transition import (
    InvalidStateTransitionError,
    PetitionAlreadyFatedError,
)
from src.domain.models.petition_submission import (
    TERMINAL_STATES,
    PetitionState,
    PetitionSubmission,
)


class PetitionSubmissionRepositoryStub(PetitionSubmissionRepositoryProtocol):
    """In-memory stub implementation of PetitionSubmissionRepositoryProtocol.

    This stub stores petition submissions in memory for development and testing.
    It is NOT suitable for production use.

    Constitutional Compliance:
    - FR-9.4: IDs are preserved exactly as provided (no remapping)

    Attributes:
        _submissions: Dictionary mapping submission.id to PetitionSubmission.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._submissions: dict[UUID, PetitionSubmission] = {}
        # Lock for simulating atomic CAS operations (FR-2.4)
        self._cas_lock = asyncio.Lock()

    async def save(self, submission: PetitionSubmission) -> None:
        """Save a new petition submission to storage.

        FR-9.4: The submission.id is preserved exactly.

        Args:
            submission: The petition submission to save.

        Raises:
            ValueError: If submission.id already exists.
        """
        if submission.id in self._submissions:
            raise ValueError(f"Submission already exists: {submission.id}")
        self._submissions[submission.id] = submission

    async def get(self, submission_id: UUID) -> PetitionSubmission | None:
        """Retrieve a petition submission by ID.

        FR-9.4: Returns the exact submission with preserved ID.

        Args:
            submission_id: The unique petition submission identifier.

        Returns:
            The petition submission if found, None otherwise.
        """
        return self._submissions.get(submission_id)

    async def list_by_state(
        self,
        state: PetitionState,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PetitionSubmission], int]:
        """List petition submissions filtered by lifecycle state.

        Returns petitions with the specified state, ordered by created_at desc.

        Args:
            state: The lifecycle state to filter by.
            limit: Maximum number of submissions to return.
            offset: Number of submissions to skip.

        Returns:
            Tuple of (list of submissions, total count matching state).
        """
        # Filter by state
        matching = [s for s in self._submissions.values() if s.state == state]
        # Sort by created_at descending
        matching.sort(key=lambda s: s.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

    async def update_state(
        self,
        submission_id: UUID,
        new_state: PetitionState,
        fate_reason: str | None = None,
    ) -> None:
        """Update a petition submission's lifecycle state.

        Args:
            submission_id: The petition submission to update.
            new_state: The new lifecycle state.
            fate_reason: Optional reason for fate assignment (Story 1.8).

        Raises:
            KeyError: If submission doesn't exist.
        """
        submission = self._submissions.get(submission_id)
        if submission is None:
            raise KeyError(f"Submission not found: {submission_id}")

        # Create updated submission with new state
        updated = PetitionSubmission(
            id=submission.id,
            type=submission.type,
            text=submission.text,
            state=new_state,
            submitter_id=submission.submitter_id,
            content_hash=submission.content_hash,
            realm=submission.realm,
            created_at=submission.created_at,
            updated_at=datetime.now(timezone.utc),
            fate_reason=fate_reason
            if fate_reason is not None
            else submission.fate_reason,
            co_signer_count=submission.co_signer_count,
        )
        self._submissions[submission_id] = updated

    async def assign_fate_cas(
        self,
        submission_id: UUID,
        expected_state: PetitionState,
        new_state: PetitionState,
        fate_reason: str | None = None,
        escalation_source: str | None = None,
        escalated_to_realm: str | None = None,
    ) -> PetitionSubmission:
        """Atomic fate assignment using compare-and-swap (Story 1.6, FR-2.4, Story 1.8, Story 6.1).

        This stub implementation simulates atomic CAS semantics using a lock.
        In production, PostgreSQL's UPDATE ... WHERE ... RETURNING provides
        true atomicity.

        Constitutional Constraints:
        - FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
        - NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
        - FR-5.4: Escalation metadata populated atomically (Story 6.1)

        Args:
            submission_id: The petition submission to update.
            expected_state: The state the petition must be in for update to succeed.
            new_state: The new terminal fate state (ACKNOWLEDGED, REFERRED, ESCALATED).
            fate_reason: Optional reason for fate assignment (Story 1.8).
            escalation_source: What triggered escalation (Story 6.1, for ESCALATED state).
            escalated_to_realm: Target King's realm (Story 6.1, for ESCALATED state).

        Returns:
            The updated PetitionSubmission with new state and escalation fields (if provided).

        Raises:
            ConcurrentModificationError: If expected_state doesn't match current state.
            KeyError: If submission doesn't exist.
            InvalidStateTransitionError: If new_state is not valid from expected_state.
            PetitionAlreadyFatedError: If petition is already in terminal state.
        """
        # Simulate atomic CAS with lock (in-memory equivalent of DB row lock)
        async with self._cas_lock:
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise KeyError(f"Submission not found: {submission_id}")

            # Check if petition is already in terminal state (FR-2.6)
            if submission.state in TERMINAL_STATES:
                raise PetitionAlreadyFatedError(
                    petition_id=str(submission_id),
                    terminal_state=submission.state,
                )

            # CAS check: expected state must match current state
            if submission.state != expected_state:
                raise ConcurrentModificationError(
                    petition_id=submission_id,
                    expected_state=expected_state,
                    operation="fate_assignment",
                )

            # Validate transition is allowed (FR-2.1, FR-2.3)
            valid_transitions = submission.state.valid_transitions()
            if new_state not in valid_transitions:
                raise InvalidStateTransitionError(
                    from_state=submission.state,
                    to_state=new_state,
                    allowed_transitions=list(valid_transitions),
                )

            # Populate escalation fields if transitioning to ESCALATED (Story 6.1, FR-5.4)
            effective_escalation_source = escalation_source
            effective_escalated_to_realm = escalated_to_realm
            escalated_at = None

            if new_state == PetitionState.ESCALATED:
                escalated_at = datetime.now(timezone.utc)
                # Default escalation_source if not provided
                if effective_escalation_source is None:
                    effective_escalation_source = "DELIBERATION"
                # Default escalated_to_realm if not provided (use petition's realm)
                if effective_escalated_to_realm is None:
                    effective_escalated_to_realm = submission.realm

            # Perform the atomic state update
            updated = PetitionSubmission(
                id=submission.id,
                type=submission.type,
                text=submission.text,
                state=new_state,
                submitter_id=submission.submitter_id,
                content_hash=submission.content_hash,
                realm=submission.realm,
                created_at=submission.created_at,
                updated_at=datetime.now(timezone.utc),
                fate_reason=fate_reason,
                co_signer_count=submission.co_signer_count,
                escalation_source=effective_escalation_source,
                escalated_at=escalated_at,
                escalated_to_realm=effective_escalated_to_realm,
                adopted_as_motion_id=submission.adopted_as_motion_id,
                adopted_at=submission.adopted_at,
                adopted_by_king_id=submission.adopted_by_king_id,
            )
            self._submissions[submission_id] = updated
            return updated

    async def mark_adopted(
        self,
        submission_id: UUID,
        motion_id: UUID,
        king_id: UUID,
    ) -> PetitionSubmission:
        """Mark petition as adopted by King with immutable provenance (Story 6.3, FR-5.7).

        This stub implementation simulates atomic update semantics using a lock.

        Constitutional Constraints:
        - FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]
        - NFR-6.2: Adoption provenance immutability
        - NFR-4.5: Budget consumption durability (survives restart)

        Args:
            submission_id: UUID of the petition to mark as adopted
            motion_id: UUID of the created Motion (back-reference)
            king_id: UUID of the King who adopted the petition

        Returns:
            The updated PetitionSubmission with adoption fields set

        Raises:
            KeyError: If submission doesn't exist
            ValueError: If petition already adopted by different motion
        """
        async with self._cas_lock:
            submission = self._submissions.get(submission_id)
            if submission is None:
                raise KeyError(f"Submission not found: {submission_id}")

            # Check if already adopted (immutability check)
            if submission.adopted_as_motion_id is not None:
                # Idempotent: if same motion_id, return existing
                if submission.adopted_as_motion_id == motion_id:
                    return submission
                # Error: trying to adopt as different motion
                raise ValueError(
                    f"Petition {submission_id} already adopted as motion "
                    f"{submission.adopted_as_motion_id}, cannot adopt as {motion_id}"
                )

            # Atomic update with adoption fields
            updated = PetitionSubmission(
                id=submission.id,
                type=submission.type,
                text=submission.text,
                state=submission.state,
                submitter_id=submission.submitter_id,
                content_hash=submission.content_hash,
                realm=submission.realm,
                created_at=submission.created_at,
                updated_at=datetime.now(timezone.utc),
                fate_reason=submission.fate_reason,
                co_signer_count=submission.co_signer_count,
                escalation_source=submission.escalation_source,
                escalated_at=submission.escalated_at,
                escalated_to_realm=submission.escalated_to_realm,
                adopted_as_motion_id=motion_id,
                adopted_at=datetime.now(timezone.utc),
                adopted_by_king_id=king_id,
            )
            self._submissions[submission_id] = updated
            return updated

    def clear(self) -> None:
        """Clear all submissions (for testing)."""
        self._submissions.clear()
