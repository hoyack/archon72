"""ArchonAssignmentService for Three Fates deliberation (Story 2A.2, FR-11.1).

This module implements archon assignment for petition deliberation:
- Deterministic selection of exactly 3 Marquis-rank Archons
- Idempotent assignment (returns existing session if already assigned)
- DeliberationSession creation with UUIDv7
- ArchonsAssignedEvent emission

Constitutional Constraints:
- FR-11.1: System assigns exactly 3 Marquis-rank Archons per petition
- FR-11.2: Initiate mini-Conclave when petition enters RECEIVED state
- NFR-10.3: Consensus determinism (100% reproducible)
- NFR-10.5: Support 100+ concurrent deliberations
- NFR-10.6: Archon substitution < 10 seconds on failure

Developer Golden Rules:
1. DETERMINISM - Same (petition_id + seed) always produces same selection
2. IDEMPOTENT - Repeated assignment returns existing session
3. EXACTLY_THREE - Never more, never fewer Archons assigned
4. EVENT_EMISSION - Always emit ArchonsAssignedEvent on new assignment
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from uuid6 import uuid7

from src.application.ports.archon_assignment import (
    ARCHONS_ASSIGNED_EVENT_TYPE,
    ArchonsAssignedEventPayload,
    AssignmentResult,
)
from src.domain.errors.deliberation import (
    ArchonPoolExhaustedError,
    InvalidPetitionStateError,
)
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.models.deliberation_session import (
    DeliberationSession,
)
from src.domain.models.petition_submission import PetitionState

if TYPE_CHECKING:
    from src.application.ports.archon_pool import ArchonPoolProtocol
    from src.application.ports.petition_event_emitter import PetitionEventEmitterPort
    from src.application.ports.petition_submission_repository import (
        PetitionSubmissionRepositoryProtocol,
    )
    from src.domain.models.fate_archon import FateArchon

logger = logging.getLogger(__name__)


# System agent ID for event attribution
ARCHON_ASSIGNMENT_SYSTEM_AGENT_ID: str = "archon-assignment-service"


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class ArchonAssignmentService:
    """Service for assigning Archons to petitions for deliberation.

    This service implements:
    1. Deterministic archon selection from the Three Fates pool
    2. Idempotent assignment (returns existing session if already assigned)
    3. DeliberationSession creation with UUIDv7
    4. ArchonsAssignedEvent emission on new assignment

    Constitutional Constraints:
    - FR-11.1: Exactly 3 Marquis-rank Archons per petition
    - FR-11.2: Initiate mini-Conclave when petition enters RECEIVED state
    - NFR-10.3: Consensus determinism (100% reproducible)

    Thread Safety:
    - Relies on unique constraint on (petition_id) in database for idempotency
    - Multiple concurrent calls for same petition_id handled by database
    """

    REQUIRED_ARCHON_COUNT: int = 3

    def __init__(
        self,
        archon_pool: ArchonPoolProtocol,
        petition_repository: PetitionSubmissionRepositoryProtocol,
        event_emitter: PetitionEventEmitterPort | None = None,
        session_store: dict[UUID, DeliberationSession] | None = None,
    ) -> None:
        """Initialize ArchonAssignmentService.

        Args:
            archon_pool: Pool protocol for selecting Fate Archons.
            petition_repository: Repository for petition persistence.
            event_emitter: Optional event emitter for ArchonsAssignedEvent.
            session_store: Optional in-memory session store for testing.
                           In production, use a database-backed store.
        """
        self._archon_pool = archon_pool
        self._petition_repository = petition_repository
        self._event_emitter = event_emitter
        self._session_store: dict[UUID, DeliberationSession] = (
            session_store if session_store is not None else {}
        )
        logger.info("ArchonAssignmentService initialized")

    async def assign_archons(
        self,
        petition_id: UUID,
        seed: int | None = None,
    ) -> AssignmentResult:
        """Assign archons to a petition for deliberation.

        This operation is idempotent: if archons have already been assigned
        to this petition, the existing session is returned.

        Selection is deterministic: given the same (petition_id, seed),
        the same 3 Archons will always be assigned.

        Args:
            petition_id: UUID of the petition requiring deliberation.
            seed: Optional seed for deterministic selection. If None,
                  uses petition_id bytes as seed.

        Returns:
            AssignmentResult containing the session and assigned archons.

        Raises:
            PetitionNotFoundError: If petition does not exist.
            InvalidPetitionStateError: If petition is not in RECEIVED state.
            ArchonPoolExhaustedError: If pool has fewer than 3 Archons.
        """
        logger.debug("Assigning archons for petition %s", petition_id)

        # Check for existing session (idempotency - AC-3)
        existing_session = await self.get_session_by_petition(petition_id)
        if existing_session is not None:
            logger.info(
                "Returning existing session %s for petition %s",
                existing_session.session_id,
                petition_id,
            )
            archons = self._archon_pool.select_archons(petition_id, seed)
            return AssignmentResult(
                session=existing_session,
                assigned_archons=archons,
                is_new_assignment=False,
                assigned_at=existing_session.created_at,
            )

        # Validate petition exists and is in correct state
        petition = await self._petition_repository.get_by_id(petition_id)
        if petition is None:
            raise PetitionNotFoundError(str(petition_id))

        # Check petition state (AC-4: must be RECEIVED)
        if petition.state != PetitionState.RECEIVED:
            raise InvalidPetitionStateError(
                petition_id=str(petition_id),
                current_state=petition.state.value,
                expected_state=PetitionState.RECEIVED.value,
            )

        # Check pool has enough archons (FR-11.1)
        pool_size = self._archon_pool.get_pool_size()
        if pool_size < self.REQUIRED_ARCHON_COUNT:
            raise ArchonPoolExhaustedError(
                available_count=pool_size,
                required_count=self.REQUIRED_ARCHON_COUNT,
            )

        # Select exactly 3 archons deterministically (AC-2)
        archons = self._archon_pool.select_archons(petition_id, seed)
        archon_ids = tuple(a.id for a in archons)

        logger.debug(
            "Selected archons for petition %s: %s",
            petition_id,
            [a.name for a in archons],
        )

        # Create deliberation session with UUIDv7 (AC-4)
        now = _utc_now()
        session = DeliberationSession.create(
            session_id=uuid7(),
            petition_id=petition_id,
            assigned_archons=archon_ids,
        )

        # Store session
        self._session_store[petition_id] = session

        # Transition petition to DELIBERATING state (AC-4)
        updated_petition = petition.with_state(
            PetitionState.DELIBERATING,
            reason="Archons assigned for Three Fates deliberation",
        )
        await self._petition_repository.update(updated_petition)

        # Emit ArchonsAssignedEvent (AC-5)
        if self._event_emitter is not None:
            event_payload = ArchonsAssignedEventPayload(
                session_id=session.session_id,
                petition_id=petition_id,
                archon_ids=archon_ids,
                archon_names=tuple(a.name for a in archons),
                assigned_at=now,
            )
            await self._event_emitter.emit(
                event_type=ARCHONS_ASSIGNED_EVENT_TYPE,
                payload=event_payload.to_dict(),
            )
            logger.debug(
                "Emitted ArchonsAssignedEvent for session %s",
                session.session_id,
            )

        logger.info(
            "Created deliberation session %s for petition %s with archons %s",
            session.session_id,
            petition_id,
            [a.name for a in archons],
        )

        return AssignmentResult(
            session=session,
            assigned_archons=archons,
            is_new_assignment=True,
            assigned_at=now,
        )

    async def get_session_by_petition(
        self,
        petition_id: UUID,
    ) -> DeliberationSession | None:
        """Get existing deliberation session for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            DeliberationSession if exists, None otherwise.
        """
        return self._session_store.get(petition_id)

    async def get_assigned_archons(
        self,
        petition_id: UUID,
    ) -> tuple[FateArchon, FateArchon, FateArchon] | None:
        """Get assigned archons for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            Tuple of 3 FateArchons if assigned, None otherwise.
        """
        session = await self.get_session_by_petition(petition_id)
        if session is None:
            return None

        # Re-select archons using the same deterministic algorithm
        # This ensures consistency with the original assignment
        return self._archon_pool.select_archons(petition_id)
