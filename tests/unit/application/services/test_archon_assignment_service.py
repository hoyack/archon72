"""Unit tests for ArchonAssignmentService (Story 2A.2, FR-11.1, FR-11.2).

Tests:
- AC-1: Archon selection on RECEIVED state (deterministic)
- AC-2: Deterministic selection (SHA-256 uniform distribution)
- AC-3: Idempotent assignment (returns existing if already assigned)
- AC-4: Session creation (UUIDv7, ASSESS phase, state DELIBERATING)
- AC-5: Event emission (ArchonsAssignedEvent with schema_version)
- AC-6: Concurrent protection (unique constraint handles race)
- AC-7: Protocol + stub for testing

Acceptance Criteria Coverage:
- FR-11.1: Exactly 3 Marquis-rank Archons per petition
- FR-11.2: Initiate mini-Conclave when petition enters RECEIVED state
- NFR-10.3: Consensus determinism (100% reproducible)
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from uuid6 import uuid7

from src.application.ports.archon_assignment import (
    ARCHONS_ASSIGNED_EVENT_TYPE,
    ARCHONS_ASSIGNED_SCHEMA_VERSION,
    ArchonsAssignedEventPayload,
    AssignmentResult,
)
from src.application.services.archon_assignment_service import (
    ARCHON_ASSIGNMENT_SYSTEM_AGENT_ID,
    ArchonAssignmentService,
)
from src.domain.errors.deliberation import (
    ArchonPoolExhaustedError,
    InvalidPetitionStateError,
)
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)
from src.domain.models.fate_archon import (
    FATE_ARCHON_AMON,
    FATE_ARCHON_LERAJE,
    FATE_ARCHON_RONOVE,
    THREE_FATES_POOL,
    DeliberationStyle,
    FateArchon,
)
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.archon_pool_stub import (
    ArchonPoolStub,
    create_test_archon,
)


def _create_test_petition(
    petition_id: UUID | None = None,
    state: PetitionState = PetitionState.RECEIVED,
) -> PetitionSubmission:
    """Create a test petition submission."""
    return PetitionSubmission(
        id=petition_id or uuid7(),
        type=PetitionType.GENERAL,
        text="Test petition content",
        state=state,
        realm="test-realm",
    )


def _create_petition_repository_mock(
    petition: PetitionSubmission | None = None,
) -> MagicMock:
    """Create a mock petition repository."""
    mock = MagicMock()
    mock.get_by_id = AsyncMock(return_value=petition)
    mock.update = AsyncMock()
    return mock


def _create_event_emitter_mock() -> MagicMock:
    """Create a mock event emitter."""
    mock = MagicMock()
    mock.emit = AsyncMock()
    return mock


class TestArchonAssignmentServiceInitialization:
    """Test service initialization."""

    def test_initializes_with_dependencies(self) -> None:
        """Service initializes with required dependencies."""
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock()

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        assert service is not None

    def test_optional_event_emitter(self) -> None:
        """Service works without event emitter."""
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock()

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
            event_emitter=None,
        )

        assert service is not None


class TestAC1_ArchonSelectionOnReceivedState:
    """AC-1: Archon selection on RECEIVED state."""

    @pytest.mark.asyncio
    async def test_selects_exactly_three_archons(self) -> None:
        """FR-11.1: Exactly 3 Marquis-rank Archons selected."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        result = await service.assign_archons(petition.id)

        assert len(result.assigned_archons) == 3
        assert all(isinstance(a, FateArchon) for a in result.assigned_archons)

    @pytest.mark.asyncio
    async def test_rejects_non_received_state(self) -> None:
        """Rejects petition not in RECEIVED state."""
        petition = _create_test_petition(state=PetitionState.DELIBERATING)
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        with pytest.raises(InvalidPetitionStateError) as exc_info:
            await service.assign_archons(petition.id)

        assert exc_info.value.current_state == "DELIBERATING"
        assert exc_info.value.expected_state == "RECEIVED"

    @pytest.mark.asyncio
    async def test_rejects_terminal_state(self) -> None:
        """Rejects petition in terminal state."""
        petition = _create_test_petition(state=PetitionState.ACKNOWLEDGED)
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        with pytest.raises(InvalidPetitionStateError):
            await service.assign_archons(petition.id)


class TestAC2_DeterministicSelection:
    """AC-2: Deterministic selection using SHA-256."""

    @pytest.mark.asyncio
    async def test_same_inputs_same_selection(self) -> None:
        """NFR-10.3: Same (petition_id, seed) produces same selection."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        # First call creates assignment
        result1 = await service.assign_archons(petition.id, seed=12345)

        # Clear session store to force re-selection
        service._session_store.clear()

        # Second call should select same archons
        repo.get_by_id = AsyncMock(return_value=petition)
        result2 = await service.assign_archons(petition.id, seed=12345)

        # Same archons (in same order)
        assert result1.assigned_archons == result2.assigned_archons

    @pytest.mark.asyncio
    async def test_different_seeds_different_selection(self) -> None:
        """Different seeds produce different selections."""
        petition1 = _create_test_petition()
        petition2 = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition1)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        result1 = await service.assign_archons(petition1.id, seed=1)

        # Reset for second petition
        repo.get_by_id = AsyncMock(return_value=petition2)
        result2 = await service.assign_archons(petition2.id, seed=2)

        # Different archons selected (very unlikely to be same)
        assert result1.assigned_archons != result2.assigned_archons


class TestAC3_IdempotentAssignment:
    """AC-3: Idempotent assignment returns existing session."""

    @pytest.mark.asyncio
    async def test_returns_existing_session(self) -> None:
        """Repeated assignment returns existing session."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        # First assignment
        result1 = await service.assign_archons(petition.id)
        assert result1.is_new_assignment is True

        # Second assignment returns existing
        result2 = await service.assign_archons(petition.id)

        assert result2.is_new_assignment is False
        assert result2.session.id == result1.session.id
        assert result2.assigned_archons == result1.assigned_archons

    @pytest.mark.asyncio
    async def test_idempotent_does_not_emit_event(self) -> None:
        """Idempotent return does not emit duplicate event."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)
        emitter = _create_event_emitter_mock()

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
            event_emitter=emitter,
        )

        # First assignment emits event
        await service.assign_archons(petition.id)
        assert emitter.emit.call_count == 1

        # Second assignment does not emit
        await service.assign_archons(petition.id)
        assert emitter.emit.call_count == 1  # Still 1


class TestAC4_SessionCreation:
    """AC-4: Session creation with UUIDv7, ASSESS phase."""

    @pytest.mark.asyncio
    async def test_creates_session_with_uuidv7(self) -> None:
        """Session created with UUIDv7 ID."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        result = await service.assign_archons(petition.id)

        # UUIDv7 has version 7 in bits 48-51
        session_id = result.session.id
        version = (session_id.int >> 76) & 0xF
        assert version == 7

    @pytest.mark.asyncio
    async def test_session_starts_in_assess_phase(self) -> None:
        """Session created in ASSESS phase."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        result = await service.assign_archons(petition.id)

        assert result.session.phase == DeliberationPhase.ASSESS

    @pytest.mark.asyncio
    async def test_petition_transitions_to_deliberating(self) -> None:
        """Petition state transitions to DELIBERATING."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        await service.assign_archons(petition.id)

        # Verify update was called with DELIBERATING state
        repo.update.assert_called_once()
        updated_petition = repo.update.call_args[0][0]
        assert updated_petition.state == PetitionState.DELIBERATING

    @pytest.mark.asyncio
    async def test_session_contains_archon_ids(self) -> None:
        """Session contains exactly 3 archon IDs."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        result = await service.assign_archons(petition.id)

        assert len(result.session.archon_ids) == 3
        expected_ids = tuple(a.id for a in result.assigned_archons)
        assert result.session.archon_ids == expected_ids


class TestAC5_EventEmission:
    """AC-5: ArchonsAssignedEvent emission."""

    @pytest.mark.asyncio
    async def test_emits_event_on_new_assignment(self) -> None:
        """Emits ArchonsAssignedEvent on new assignment."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)
        emitter = _create_event_emitter_mock()

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
            event_emitter=emitter,
        )

        await service.assign_archons(petition.id)

        emitter.emit.assert_called_once()
        call_args = emitter.emit.call_args
        assert call_args.kwargs["event_type"] == ARCHONS_ASSIGNED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_event_payload_structure(self) -> None:
        """Event payload contains required fields."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)
        emitter = _create_event_emitter_mock()

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
            event_emitter=emitter,
        )

        result = await service.assign_archons(petition.id)

        payload = emitter.emit.call_args.kwargs["payload"]
        assert "session_id" in payload
        assert "petition_id" in payload
        assert "archon_ids" in payload
        assert "archon_names" in payload
        assert "assigned_at" in payload
        assert "schema_version" in payload

    @pytest.mark.asyncio
    async def test_event_includes_schema_version(self) -> None:
        """Event includes schema_version for D2 compliance."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)
        emitter = _create_event_emitter_mock()

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
            event_emitter=emitter,
        )

        await service.assign_archons(petition.id)

        payload = emitter.emit.call_args.kwargs["payload"]
        assert payload["schema_version"] == ARCHONS_ASSIGNED_SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_no_event_without_emitter(self) -> None:
        """No error when event emitter is not provided."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
            event_emitter=None,
        )

        # Should not raise
        result = await service.assign_archons(petition.id)
        assert result.is_new_assignment is True


class TestAC6_ConcurrentProtection:
    """AC-6: Concurrent protection via unique constraint."""

    @pytest.mark.asyncio
    async def test_session_store_prevents_duplicates(self) -> None:
        """In-memory store prevents duplicate sessions."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        # Simulate concurrent calls
        result1 = await service.assign_archons(petition.id)
        result2 = await service.assign_archons(petition.id)

        # Both return same session
        assert result1.session.id == result2.session.id
        assert result1.is_new_assignment is True
        assert result2.is_new_assignment is False


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_petition_not_found(self) -> None:
        """Raises PetitionNotFoundError when petition doesn't exist."""
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition=None)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        with pytest.raises(PetitionNotFoundError):
            await service.assign_archons(uuid7())

    @pytest.mark.asyncio
    async def test_pool_exhausted(self) -> None:
        """Raises ArchonPoolExhaustedError when pool too small."""
        petition = _create_test_petition()
        pool = ArchonPoolStub(populate_canonical=False)
        # Add only 2 archons
        pool.add_archon(create_test_archon("One"))
        pool.add_archon(create_test_archon("Two"))
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        with pytest.raises(ArchonPoolExhaustedError) as exc_info:
            await service.assign_archons(petition.id)

        assert exc_info.value.available_count == 2
        assert exc_info.value.required_count == 3


class TestGetSessionByPetition:
    """Test get_session_by_petition method."""

    @pytest.mark.asyncio
    async def test_returns_session_when_exists(self) -> None:
        """Returns session when it exists."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        result = await service.assign_archons(petition.id)
        session = await service.get_session_by_petition(petition.id)

        assert session is not None
        assert session.id == result.session.id

    @pytest.mark.asyncio
    async def test_returns_none_when_not_exists(self) -> None:
        """Returns None when no session exists."""
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock()

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        session = await service.get_session_by_petition(uuid7())

        assert session is None


class TestGetAssignedArchons:
    """Test get_assigned_archons method."""

    @pytest.mark.asyncio
    async def test_returns_archons_when_assigned(self) -> None:
        """Returns archons when assignment exists."""
        petition = _create_test_petition()
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock(petition)

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        result = await service.assign_archons(petition.id)
        archons = await service.get_assigned_archons(petition.id)

        assert archons is not None
        assert len(archons) == 3
        assert archons == result.assigned_archons

    @pytest.mark.asyncio
    async def test_returns_none_when_not_assigned(self) -> None:
        """Returns None when no assignment exists."""
        pool = ArchonPoolStub()
        repo = _create_petition_repository_mock()

        service = ArchonAssignmentService(
            archon_pool=pool,
            petition_repository=repo,
        )

        archons = await service.get_assigned_archons(uuid7())

        assert archons is None


class TestArchonsAssignedEventPayload:
    """Test ArchonsAssignedEventPayload dataclass."""

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content produces deterministic output."""
        session_id = uuid7()
        petition_id = uuid7()
        archon_ids = (uuid4(), uuid4(), uuid4())
        archon_names = ("Amon", "Leraje", "Ronove")
        assigned_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = ArchonsAssignedEventPayload(
            session_id=session_id,
            petition_id=petition_id,
            archon_ids=archon_ids,
            archon_names=archon_names,
            assigned_at=assigned_at,
        )
        payload2 = ArchonsAssignedEventPayload(
            session_id=session_id,
            petition_id=petition_id,
            archon_ids=archon_ids,
            archon_names=archon_names,
            assigned_at=assigned_at,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all required fields."""
        session_id = uuid7()
        petition_id = uuid7()
        archon_ids = (uuid4(), uuid4(), uuid4())
        archon_names = ("Amon", "Leraje", "Ronove")
        assigned_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        payload = ArchonsAssignedEventPayload(
            session_id=session_id,
            petition_id=petition_id,
            archon_ids=archon_ids,
            archon_names=archon_names,
            assigned_at=assigned_at,
        )

        result = payload.to_dict()

        assert result["session_id"] == str(session_id)
        assert result["petition_id"] == str(petition_id)
        assert len(result["archon_ids"]) == 3
        assert len(result["archon_names"]) == 3
        assert "assigned_at" in result
        assert result["schema_version"] == ARCHONS_ASSIGNED_SCHEMA_VERSION


class TestAssignmentResult:
    """Test AssignmentResult dataclass."""

    def test_is_frozen(self) -> None:
        """AssignmentResult is immutable."""
        session = DeliberationSession.create(
            petition_id=uuid7(),
            archon_ids=(uuid4(), uuid4(), uuid4()),
        )
        archons = (
            create_test_archon("A"),
            create_test_archon("B"),
            create_test_archon("C"),
        )

        result = AssignmentResult(
            session=session,
            assigned_archons=archons,
            is_new_assignment=True,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.is_new_assignment = False  # type: ignore

    def test_default_assigned_at(self) -> None:
        """assigned_at defaults to current time."""
        session = DeliberationSession.create(
            petition_id=uuid7(),
            archon_ids=(uuid4(), uuid4(), uuid4()),
        )
        archons = (
            create_test_archon("A"),
            create_test_archon("B"),
            create_test_archon("C"),
        )

        result = AssignmentResult(
            session=session,
            assigned_archons=archons,
            is_new_assignment=True,
        )

        assert result.assigned_at is not None
        assert result.assigned_at.tzinfo is not None  # UTC aware
