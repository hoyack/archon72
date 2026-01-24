"""PostgreSQL PetitionSubmission Repository adapter (Story 0.3, FR-2.4, NFR-3.2).

This module provides the production PostgreSQL implementation of
PetitionSubmissionRepositoryProtocol for petition persistence.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All operations logged
- CT-12: Witnessing creates accountability → Content hash stored
- FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
- FR-9.4: Petition ID preservation is MANDATORY
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]

Database Table: petition_submissions (migration 012)
- PostgreSQL enums: petition_type_enum, petition_state_enum
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from src.domain.errors.concurrent_modification import ConcurrentModificationError
from src.domain.errors.petition import PetitionSubmissionNotFoundError
from src.domain.errors.state_transition import (
    InvalidStateTransitionError,
    PetitionAlreadyFatedError,
)
from src.domain.models.petition_submission import (
    TERMINAL_STATES,
    PetitionState,
    PetitionSubmission,
    PetitionType,
)

if TYPE_CHECKING:
    pass

logger = get_logger()


class PostgresPetitionSubmissionRepository:
    """PostgreSQL implementation of PetitionSubmissionRepository (Story 0.3, FR-2.4).

    Uses the petition_submissions table created by migration 012.

    Constitutional Compliance:
    - FR-2.4: Atomic CAS via UPDATE...WHERE state = expected RETURNING *
    - FR-9.4: Petition IDs preserved exactly as provided
    - NFR-3.2: Database-level atomic fate assignment
    - CT-11: All operations logged with structlog
    - CT-12: Content hash stored for witness integrity

    Attributes:
        _session_factory: SQLAlchemy async session factory for DB access
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the PostgreSQL petition submission repository.

        Args:
            session_factory: SQLAlchemy async session factory for DB access.
        """
        self._session_factory = session_factory

    async def save(self, submission: PetitionSubmission) -> None:
        """Save a new petition submission to storage.

        FR-9.4: The submission.id is preserved exactly.

        Args:
            submission: The petition submission to save.

        Raises:
            PetitionSubmissionAlreadyExistsError: If submission.id already exists.
        """
        log = logger.bind(
            petition_id=str(submission.id),
            type=submission.type.value,
            realm=submission.realm,
        )

        async with self._session_factory() as session:
            async with session.begin():
                # Encode content_hash as base64 string for storage
                content_hash_b64 = None
                if submission.content_hash:
                    content_hash_b64 = base64.b64encode(submission.content_hash).decode(
                        "ascii"
                    )

                await session.execute(
                    text("""
                        INSERT INTO petition_submissions (
                            id, type, text, submitter_id, state, content_hash,
                            realm, created_at, updated_at, co_signer_count,
                            escalation_source, escalated_at, escalated_to_realm
                        )
                        VALUES (
                            :id, CAST(:type AS petition_type_enum), :text, :submitter_id,
                            CAST(:state AS petition_state_enum), :content_hash,
                            :realm, :created_at, :updated_at, :co_signer_count,
                            :escalation_source, :escalated_at, :escalated_to_realm
                        )
                    """),
                    {
                        "id": submission.id,
                        "type": submission.type.value,
                        "text": submission.text,
                        "submitter_id": submission.submitter_id,
                        "state": submission.state.value,
                        "content_hash": (
                            submission.content_hash if submission.content_hash else None
                        ),
                        "realm": submission.realm,
                        "created_at": submission.created_at,
                        "updated_at": submission.updated_at,
                        "co_signer_count": submission.co_signer_count,
                        "escalation_source": submission.escalation_source,
                        "escalated_at": submission.escalated_at,
                        "escalated_to_realm": submission.escalated_to_realm,
                    },
                )

        log.info("petition_submission_saved", state=submission.state.value)

    async def get(self, submission_id: UUID) -> PetitionSubmission | None:
        """Retrieve a petition submission by ID.

        Args:
            submission_id: The unique petition submission identifier.

        Returns:
            The petition submission if found, None otherwise.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, type, text, submitter_id, state, content_hash,
                           realm, created_at, updated_at, co_signer_count,
                           escalation_source, escalated_at, escalated_to_realm
                    FROM petition_submissions
                    WHERE id = :id
                """),
                {"id": submission_id},
            )
            row = result.fetchone()

            if row is None:
                return None

            return self._row_to_submission(row)

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
        async with self._session_factory() as session:
            # Get total count
            count_result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM petition_submissions
                    WHERE state = CAST(:state AS petition_state_enum)
                """),
                {"state": state.value},
            )
            total_count = count_result.scalar() or 0

            # Get paginated results
            result = await session.execute(
                text("""
                    SELECT id, type, text, submitter_id, state, content_hash,
                           realm, created_at, updated_at, co_signer_count,
                           escalation_source, escalated_at, escalated_to_realm
                    FROM petition_submissions
                    WHERE state = CAST(:state AS petition_state_enum)
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"state": state.value, "limit": limit, "offset": offset},
            )
            rows = result.fetchall()

            submissions = [self._row_to_submission(row) for row in rows]
            return submissions, total_count

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
        log = logger.bind(
            petition_id=str(submission_id),
            new_state=new_state.value,
        )

        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    text("""
                        UPDATE petition_submissions
                        SET state = CAST(:new_state AS petition_state_enum),
                            updated_at = :updated_at
                        WHERE id = :id
                        RETURNING id
                    """),
                    {
                        "id": submission_id,
                        "new_state": new_state.value,
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
                row = result.fetchone()

                if row is None:
                    raise PetitionSubmissionNotFoundError(submission_id)

        log.info("petition_state_updated")

    async def assign_fate_cas(
        self,
        submission_id: UUID,
        expected_state: PetitionState,
        new_state: PetitionState,
        escalation_source: str | None = None,
        escalated_to_realm: str | None = None,
    ) -> PetitionSubmission:
        """Atomic fate assignment using compare-and-swap (Story 1.6, FR-2.4).

        This method ensures exactly-once fate assignment using optimistic
        concurrency control. The state is only updated if the current state
        matches the expected state.

        Constitutional Constraints:
        - FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate)
        - NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
        - FR-5.4: Escalation metadata populated atomically (Story 6.1)

        Args:
            submission_id: The petition submission to update.
            expected_state: The state the petition must be in for update to succeed.
            new_state: The new terminal fate state (ACKNOWLEDGED, REFERRED, ESCALATED, DEFERRED, NO_RESPONSE).
            escalation_source: What triggered escalation (for ESCALATED state).
            escalated_to_realm: Target King's realm (for ESCALATED state).

        Returns:
            The updated PetitionSubmission with new state.

        Raises:
            ConcurrentModificationError: If expected_state doesn't match current state.
            PetitionSubmissionNotFoundError: If submission doesn't exist.
            InvalidStateTransitionError: If new_state is not valid from expected_state.
            PetitionAlreadyFatedError: If petition is already in terminal state.
        """
        log = logger.bind(
            petition_id=str(submission_id),
            expected_state=expected_state.value,
            new_state=new_state.value,
        )

        # Validate transition is allowed by state machine
        valid_transitions = expected_state.valid_transitions()
        if new_state not in valid_transitions:
            raise InvalidStateTransitionError(
                from_state=expected_state,
                to_state=new_state,
                allowed_transitions=list(valid_transitions),
            )

        now = datetime.now(timezone.utc)
        escalated_at = now if new_state == PetitionState.ESCALATED else None

        async with self._session_factory() as session:
            async with session.begin():
                # First check if petition exists and get current state
                check_result = await session.execute(
                    text("""
                        SELECT state FROM petition_submissions WHERE id = :id
                    """),
                    {"id": submission_id},
                )
                check_row = check_result.fetchone()

                if check_row is None:
                    raise PetitionSubmissionNotFoundError(submission_id)

                current_state = PetitionState(check_row[0])

                # Check if already in terminal state
                if current_state in TERMINAL_STATES:
                    raise PetitionAlreadyFatedError(
                        petition_id=str(submission_id),
                        terminal_state=current_state,
                    )

                # Atomic CAS update
                result = await session.execute(
                    text("""
                        UPDATE petition_submissions
                        SET state = CAST(:new_state AS petition_state_enum),
                            updated_at = :updated_at,
                            escalation_source = COALESCE(:escalation_source, escalation_source),
                            escalated_at = COALESCE(:escalated_at, escalated_at),
                            escalated_to_realm = COALESCE(:escalated_to_realm, escalated_to_realm)
                        WHERE id = :id AND state = CAST(:expected_state AS petition_state_enum)
                        RETURNING id, type, text, submitter_id, state, content_hash,
                                  realm, created_at, updated_at, co_signer_count,
                                  escalation_source, escalated_at, escalated_to_realm
                    """),
                    {
                        "id": submission_id,
                        "expected_state": expected_state.value,
                        "new_state": new_state.value,
                        "updated_at": now,
                        "escalation_source": escalation_source,
                        "escalated_at": escalated_at,
                        "escalated_to_realm": escalated_to_realm,
                    },
                )
                row = result.fetchone()

                if row is None:
                    # CAS failed - state was modified concurrently
                    log.warning(
                        "cas_failed",
                        current_state=current_state.value,
                        message="LEGIT-1: Concurrent modification detected",
                    )
                    raise ConcurrentModificationError(
                        resource_type="PetitionSubmission",
                        resource_id=str(submission_id),
                        expected_state=expected_state.value,
                        actual_state=current_state.value,
                    )

                log.info(
                    "fate_assigned",
                    fate=new_state.value,
                    escalation_source=escalation_source,
                )
                return self._row_to_submission(row)

    async def mark_adopted(
        self,
        submission_id: UUID,
        motion_id: UUID,
        king_id: UUID,
    ) -> PetitionSubmission:
        """Mark petition as adopted by King with immutable provenance (Story 6.3, FR-5.7).

        Note: This method requires migration 027 to be applied for adoption fields.
        Currently returns the petition unchanged if adoption fields don't exist.

        Args:
            submission_id: UUID of the petition to mark as adopted
            motion_id: UUID of the created Motion (back-reference)
            king_id: UUID of the King who adopted the petition

        Returns:
            The updated PetitionSubmission with adoption fields set

        Raises:
            PetitionSubmissionNotFoundError: If submission doesn't exist
        """
        log = logger.bind(
            petition_id=str(submission_id),
            motion_id=str(motion_id),
            king_id=str(king_id),
        )

        # For now, just return the petition since adoption fields aren't in schema yet
        # TODO: Implement once migration 027 is applied
        submission = await self.get(submission_id)
        if submission is None:
            raise PetitionSubmissionNotFoundError(submission_id)

        log.info("mark_adopted_stub", message="Adoption fields not yet in schema")
        return submission

    async def get_queue_depth(self, state: PetitionState | None = None) -> int:
        """Get count of petitions in queue (for capacity checks).

        Args:
            state: Optional state filter. If None, counts non-terminal petitions.

        Returns:
            Count of petitions matching criteria.
        """
        async with self._session_factory() as session:
            if state is not None:
                result = await session.execute(
                    text("""
                        SELECT COUNT(*) FROM petition_submissions
                        WHERE state = CAST(:state AS petition_state_enum)
                    """),
                    {"state": state.value},
                )
            else:
                # Count non-terminal (active) petitions
                result = await session.execute(
                    text("""
                        SELECT COUNT(*) FROM petition_submissions
                        WHERE state NOT IN (
                            'ACKNOWLEDGED',
                            'REFERRED',
                            'ESCALATED',
                            'DEFERRED',
                            'NO_RESPONSE'
                        )
                    """),
                )
            return result.scalar() or 0

    def _row_to_submission(self, row) -> PetitionSubmission:
        """Convert database row to PetitionSubmission domain model.

        Args:
            row: SQLAlchemy row with petition data.

        Returns:
            PetitionSubmission domain object.
        """
        # Handle content_hash - it's stored as bytea
        content_hash = row[5]
        if content_hash is not None and isinstance(content_hash, memoryview):
            content_hash = bytes(content_hash)

        return PetitionSubmission(
            id=row[0],
            type=PetitionType(row[1]),
            text=row[2],
            submitter_id=row[3],
            state=PetitionState(row[4]),
            content_hash=content_hash,
            realm=row[6],
            created_at=row[7],
            updated_at=row[8],
            co_signer_count=row[9],
            escalation_source=row[10],
            escalated_at=row[11],
            escalated_to_realm=row[12],
        )
