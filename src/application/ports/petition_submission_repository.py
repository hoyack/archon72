"""Petition submission repository port (Story 0.3, AC3, FR-9.1, Story 1.6).

This module defines the abstract interface for petition submission storage operations
in the new Three Fates petition system.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All operations must be logged
- CT-12: Witnessing creates accountability → All writes are witnessed
- FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
- FR-9.1: System SHALL migrate Story 7.2 cessation_petition to CESSATION type
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]

Developer Golden Rules:
1. HALT CHECK FIRST - Service layer checks halt, not repository
2. WITNESS EVERYTHING - Repository stores, service witnesses
3. FAIL LOUD - Repository raises on errors
4. READS DURING HALT - Repository reads work during halt (CT-13)
5. CAS FOR FATE - Use assign_fate_cas() for all fate assignments (FR-2.4)
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.models.petition_submission import PetitionState, PetitionSubmission


class PetitionSubmissionRepositoryProtocol(Protocol):
    """Protocol for petition submission storage operations (Story 0.3, AC3).

    Defines the contract for petition submission persistence. Implementations
    may use Supabase, in-memory storage, or other backends.

    Constitutional Constraints:
    - AC3: Support save, get, list_by_state, update_state operations
    - FR-9.4: Petition ID preservation is MANDATORY during migration

    Methods:
        save: Store a new petition submission
        get: Retrieve a petition submission by ID
        list_by_state: List petitions filtered by lifecycle state
        update_state: Update a petition's lifecycle state
    """

    async def save(self, submission: PetitionSubmission) -> None:
        """Save a new petition submission to storage.

        Args:
            submission: The petition submission to save.

        Raises:
            PetitionSubmissionAlreadyExistsError: If submission.id already exists.
        """
        ...

    async def get(self, submission_id: UUID) -> PetitionSubmission | None:
        """Retrieve a petition submission by ID.

        Args:
            submission_id: The unique petition submission identifier.

        Returns:
            The petition submission if found, None otherwise.
        """
        ...

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
        ...

    async def update_state(
        self,
        submission_id: UUID,
        new_state: PetitionState,
    ) -> None:
        """Update a petition submission's lifecycle state.

        Args:
            submission_id: The petition submission to update.
            new_state: The new lifecycle state.

        Raises:
            PetitionSubmissionNotFoundError: If submission doesn't exist.
        """
        ...

    async def assign_fate_cas(
        self,
        submission_id: UUID,
        expected_state: PetitionState,
        new_state: PetitionState,
    ) -> PetitionSubmission:
        """Atomic fate assignment using compare-and-swap (Story 1.6, FR-2.4).

        This method ensures exactly-once fate assignment using optimistic
        concurrency control. The state is only updated if the current state
        matches the expected state.

        Constitutional Constraints:
        - FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
        - NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]

        Implementation Notes:
        - Use PostgreSQL: UPDATE ... WHERE state = expected_state RETURNING *
        - Verify row count = 1 for success
        - This is the ONLY method that should be used for fate assignment

        Args:
            submission_id: The petition submission to update.
            expected_state: The state the petition must be in for update to succeed.
            new_state: The new terminal fate state (ACKNOWLEDGED, REFERRED, ESCALATED).

        Returns:
            The updated PetitionSubmission with new state.

        Raises:
            ConcurrentModificationError: If expected_state doesn't match current state.
            PetitionSubmissionNotFoundError: If submission doesn't exist.
            InvalidStateTransitionError: If new_state is not valid from expected_state.
            PetitionAlreadyFatedError: If petition is already in terminal state.
        """
        ...
