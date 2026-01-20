"""Integration tests for ArchonAssignmentService (Story 2A.2).

Tests:
- Service with real ArchonPoolService
- Concurrent assignment handling (unique constraint on petition_id)
- Petition state transition from RECEIVED to DELIBERATING
- Event emission verification

Requires Docker for testcontainers PostgreSQL.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.archon_assignment import (
    ARCHONS_ASSIGNED_EVENT_TYPE,
    ArchonsAssignedEventPayload,
    AssignmentResult,
)
from src.application.services.archon_assignment_service import (
    ARCHON_ASSIGNMENT_SYSTEM_AGENT_ID,
    ArchonAssignmentService,
)
from src.application.services.archon_pool import ArchonPoolService, get_archon_pool_service
from src.domain.errors.deliberation import (
    ArchonPoolExhaustedError,
    InvalidPetitionStateError,
)
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.models.deliberation_session import DeliberationPhase, DeliberationSession
from src.domain.models.petition_submission import PetitionState


# Path to migration files
PETITION_MIGRATION_FILE = Path(__file__).parent.parent.parent / "migrations" / "012_create_petition_submissions.sql"
DELIBERATION_MIGRATION_FILE = Path(__file__).parent.parent.parent / "migrations" / "017_create_deliberation_sessions.sql"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def assignment_schema(db_session: AsyncSession) -> AsyncSession:
    """Apply migrations required for archon assignment tests.

    Applies both petition_submissions and deliberation_sessions migrations
    since deliberation_sessions has a foreign key to petition_submissions.
    """
    # Apply petition_submissions migration (required for FK)
    petition_sql = PETITION_MIGRATION_FILE.read_text()
    for statement in petition_sql.split(";"):
        cleaned = statement.strip()
        if cleaned and not cleaned.startswith("--"):
            await db_session.execute(text(cleaned))

    # Apply deliberation_sessions migration
    deliberation_sql = DELIBERATION_MIGRATION_FILE.read_text()
    for statement in deliberation_sql.split(";"):
        cleaned = statement.strip()
        if cleaned and not cleaned.startswith("--"):
            await db_session.execute(text(cleaned))

    await db_session.flush()
    return db_session


@pytest.fixture
def archon_pool() -> ArchonPoolService:
    """Return the real archon pool service."""
    return get_archon_pool_service()


@pytest.fixture
async def received_petition(assignment_schema: AsyncSession) -> str:
    """Insert a petition in RECEIVED state and return its ID."""
    petition_id = str(uuid4())
    await assignment_schema.execute(
        text("""
            INSERT INTO petition_submissions (id, type, text, state, realm)
            VALUES (:id, 'GENERAL', 'Test petition for deliberation', 'RECEIVED', 'default')
        """),
        {"id": petition_id},
    )
    await assignment_schema.flush()
    return petition_id


@pytest.fixture
async def deliberating_petition(assignment_schema: AsyncSession) -> str:
    """Insert a petition in DELIBERATING state and return its ID."""
    petition_id = str(uuid4())
    await assignment_schema.execute(
        text("""
            INSERT INTO petition_submissions (id, type, text, state, realm)
            VALUES (:id, 'GENERAL', 'Already deliberating petition', 'DELIBERATING', 'default')
        """),
        {"id": petition_id},
    )
    await assignment_schema.flush()
    return petition_id


class MockPetitionRepository:
    """In-memory mock petition repository for integration tests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, petition_id):
        """Get petition by ID from database."""
        from uuid import UUID as UUIDType

        from src.domain.models.petition_submission import PetitionSubmission, PetitionType

        result = await self._session.execute(
            text("SELECT id, type, text, state, realm FROM petition_submissions WHERE id = :id"),
            {"id": str(petition_id)},
        )
        row = result.fetchone()
        if row is None:
            return None

        return PetitionSubmission(
            id=UUIDType(row[0]) if isinstance(row[0], str) else row[0],
            type=PetitionType(row[1]),
            text=row[2],
            state=PetitionState(row[3]),
            realm=row[4],
        )

    async def update(self, petition):
        """Update petition in database."""
        await self._session.execute(
            text("UPDATE petition_submissions SET state = :state WHERE id = :id"),
            {"id": str(petition.id), "state": petition.state.value},
        )
        await self._session.flush()


class MockEventEmitter:
    """Mock event emitter that records emitted events."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(self, event_type: str, payload: dict) -> None:
        """Record emitted event."""
        self.events.append({"event_type": event_type, "payload": payload})


# =============================================================================
# Service Integration Tests (FR-11.1, FR-11.2)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestArchonAssignmentServiceIntegration:
    """Integration tests for ArchonAssignmentService."""

    async def test_assigns_exactly_3_archons_from_pool(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """FR-11.1: System assigns exactly 3 Marquis-rank Archons from pool."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        result = await service.assign_archons(UUIDType(received_petition))

        # Exactly 3 archons assigned
        assert len(result.assigned_archons) == 3
        # All archons are from the pool
        pool_ids = {a.id for a in archon_pool.get_all_archons()}
        assert all(a.id in pool_ids for a in result.assigned_archons)
        # All archons are distinct
        archon_ids = [a.id for a in result.assigned_archons]
        assert len(set(archon_ids)) == 3
        # Is a new assignment
        assert result.is_new_assignment is True

    async def test_deterministic_selection_same_petition(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """NFR-10.3: Same petition_id always selects same archons."""
        from uuid import UUID as UUIDType

        petition_id = UUIDType(received_petition)
        seed = 42

        # Select archons multiple times
        archons1 = archon_pool.select_archons(petition_id, seed)
        archons2 = archon_pool.select_archons(petition_id, seed)
        archons3 = archon_pool.select_archons(petition_id, seed)

        # Same archons in same order every time
        assert archons1 == archons2 == archons3
        assert len(archons1) == 3

    async def test_different_petitions_can_select_different_archons(
        self,
        archon_pool: ArchonPoolService,
    ) -> None:
        """NFR-10.3: Different petition_ids produce distributed selection."""
        from uuid import UUID as UUIDType

        # Generate many petition IDs and check distribution
        selections = []
        for i in range(20):
            petition_id = UUIDType(str(uuid4()))
            archons = archon_pool.select_archons(petition_id, seed=i)
            archon_names = tuple(a.name for a in archons)
            selections.append(archon_names)

        # Not all selections are identical (statistical check)
        unique_selections = set(selections)
        # With 7 archons choose 3 = 35 combinations, 20 draws should have some variety
        assert len(unique_selections) > 1, "All 20 petition selections were identical - suspect non-random"


# =============================================================================
# Concurrent Assignment Tests (AC-6, NFR-10.5)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentAssignmentProtection:
    """Test concurrent assignment handling (AC-6)."""

    async def test_unique_constraint_prevents_duplicate_sessions(
        self,
        assignment_schema: AsyncSession,
        received_petition: str,
    ) -> None:
        """AC-6: Unique constraint on petition_id prevents duplicate sessions."""
        archons = [str(uuid4()) for _ in range(3)]
        session1_id = str(uuid4())
        session2_id = str(uuid4())

        # Insert first session
        await assignment_schema.execute(
            text("""
                INSERT INTO deliberation_sessions
                    (session_id, petition_id, assigned_archons)
                VALUES
                    (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[])
            """),
            {
                "session_id": session1_id,
                "petition_id": received_petition,
                "a1": archons[0],
                "a2": archons[1],
                "a3": archons[2],
            },
        )
        await assignment_schema.flush()

        # Attempt second session for same petition
        with pytest.raises(Exception) as exc_info:
            await assignment_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[])
                """),
                {
                    "session_id": session2_id,
                    "petition_id": received_petition,
                    "a1": archons[0],
                    "a2": archons[1],
                    "a3": archons[2],
                },
            )
            await assignment_schema.flush()

        # Unique constraint violation
        error_msg = str(exc_info.value).lower()
        assert "unique" in error_msg or "duplicate" in error_msg


# =============================================================================
# Petition State Transition Tests (AC-4)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestPetitionStateTransition:
    """Test petition state transitions during assignment (AC-4)."""

    async def test_petition_transitions_to_deliberating(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """AC-4: Petition state transitions from RECEIVED to DELIBERATING."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        # Verify initial state
        petition_before = await petition_repo.get_by_id(UUIDType(received_petition))
        assert petition_before.state == PetitionState.RECEIVED

        # Assign archons
        await service.assign_archons(UUIDType(received_petition))

        # Verify state changed
        petition_after = await petition_repo.get_by_id(UUIDType(received_petition))
        assert petition_after.state == PetitionState.DELIBERATING

    async def test_rejects_non_received_petition(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        deliberating_petition: str,
    ) -> None:
        """AC-4: Rejects assignment for petition not in RECEIVED state."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        with pytest.raises(InvalidPetitionStateError) as exc_info:
            await service.assign_archons(UUIDType(deliberating_petition))

        assert exc_info.value.current_state == "DELIBERATING"


# =============================================================================
# Event Emission Tests (AC-5)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestEventEmission:
    """Test event emission during assignment (AC-5)."""

    async def test_emits_archons_assigned_event(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """AC-5: ArchonsAssignedEvent emitted on successful assignment."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        result = await service.assign_archons(UUIDType(received_petition))

        # Event was emitted
        assert len(event_emitter.events) == 1
        event = event_emitter.events[0]

        # Event type is correct
        assert event["event_type"] == ARCHONS_ASSIGNED_EVENT_TYPE

        # Payload contains required fields
        payload = event["payload"]
        assert str(payload["petition_id"]) == received_petition
        assert payload["session_id"] == str(result.session.id)
        assert len(payload["archon_ids"]) == 3
        assert len(payload["archon_names"]) == 3
        assert "assigned_at" in payload
        assert "schema_version" in payload

    async def test_no_event_on_idempotent_return(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """AC-3: No event emitted when returning existing assignment."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        # First assignment - emits event
        result1 = await service.assign_archons(UUIDType(received_petition))
        assert result1.is_new_assignment is True
        assert len(event_emitter.events) == 1

        # Second assignment - no new event
        result2 = await service.assign_archons(UUIDType(received_petition))
        assert result2.is_new_assignment is False
        assert len(event_emitter.events) == 1  # Still just 1


# =============================================================================
# Idempotency Tests (AC-3)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestIdempotentAssignment:
    """Test idempotent assignment behavior (AC-3)."""

    async def test_returns_existing_session_on_repeat_call(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """AC-3: Second assignment returns existing session."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        # First assignment
        result1 = await service.assign_archons(UUIDType(received_petition))
        assert result1.is_new_assignment is True

        # Second assignment
        result2 = await service.assign_archons(UUIDType(received_petition))

        # Returns existing
        assert result2.is_new_assignment is False
        assert result2.session.id == result1.session.id
        assert result2.assigned_archons == result1.assigned_archons


# =============================================================================
# Session Creation Tests (AC-4)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestSessionCreation:
    """Test DeliberationSession creation (AC-4)."""

    async def test_session_created_with_uuidv7(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """AC-4: Session uses UUIDv7 for session_id."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        result = await service.assign_archons(UUIDType(received_petition))

        # UUIDv7 has version 7 in position 6 (bits 12-15)
        version = (result.session.id.int >> 76) & 0xF
        assert version == 7, f"Expected UUIDv7 (version 7), got version {version}"

    async def test_session_starts_in_assess_phase(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """AC-4: New session starts in ASSESS phase."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        result = await service.assign_archons(UUIDType(received_petition))

        assert result.session.phase == DeliberationPhase.ASSESS

    async def test_session_has_correct_petition_id(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
        received_petition: str,
    ) -> None:
        """AC-4: Session links to correct petition_id."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        result = await service.assign_archons(UUIDType(received_petition))

        assert str(result.session.petition_id) == received_petition


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling during assignment."""

    async def test_petition_not_found_error(
        self,
        assignment_schema: AsyncSession,
        archon_pool: ArchonPoolService,
    ) -> None:
        """Raises PetitionNotFoundError for non-existent petition."""
        from uuid import UUID as UUIDType

        petition_repo = MockPetitionRepository(assignment_schema)
        event_emitter = MockEventEmitter()

        service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
            event_emitter=event_emitter,
        )

        fake_petition_id = UUIDType(str(uuid4()))

        with pytest.raises(PetitionNotFoundError):
            await service.assign_archons(fake_petition_id)
