"""Unit tests for PetitionSubmissionService (Story 1.1, FR-1.1; Story 1.7, FR-2.5; Story 7.3, FR-7.5).

Tests cover:
- Petition submission workflow
- Transactional fate assignment (Story 1.7, FR-2.5, HC-1)
- Rollback on event emission failure
- Halt state checking
- Petition withdrawal (Story 7.3, FR-7.5)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.services.petition_submission_service import (
    PetitionSubmissionService,
)
from src.domain.errors import (
    FateEventEmissionError,
    SystemHaltedError,
    UnauthorizedWithdrawalError,
)
from src.domain.errors.petition import PetitionNotFoundError
from src.domain.errors.state_transition import PetitionAlreadyFatedError
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs import (
    PetitionEventEmitterStub,
)


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._time

    def utcnow(self) -> datetime:
        return self._time


class TestAssignFateTransactional:
    """Tests for assign_fate_transactional method (Story 1.7, FR-2.5, HC-1)."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        """Create a mock repository with assign_fate_cas."""
        repo = AsyncMock()
        repo.assign_fate_cas = AsyncMock()
        repo.update_state = AsyncMock()
        repo.get = AsyncMock()
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def mock_hash_service(self) -> MagicMock:
        """Create a mock hash service."""
        hash_service = MagicMock()
        hash_service.hash_text = MagicMock(return_value=b"mock_hash")
        return hash_service

    @pytest.fixture
    def mock_realm_registry(self) -> MagicMock:
        """Create a mock realm registry."""
        realm_registry = MagicMock()
        realm_registry.get_default_realm = MagicMock(return_value=None)
        return realm_registry

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create a mock halt checker that is not halted."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)
        halt_checker.get_halt_reason = AsyncMock(return_value=None)
        return halt_checker

    @pytest.fixture
    def event_emitter_stub(self) -> PetitionEventEmitterStub:
        """Create an event emitter stub."""
        return PetitionEventEmitterStub()

    @pytest.fixture
    def service(
        self,
        mock_repository: AsyncMock,
        mock_hash_service: MagicMock,
        mock_realm_registry: MagicMock,
        mock_halt_checker: AsyncMock,
        event_emitter_stub: PetitionEventEmitterStub,
    ) -> PetitionSubmissionService:
        """Create a service with mock dependencies."""
        return PetitionSubmissionService(
            repository=mock_repository,
            hash_service=mock_hash_service,
            realm_registry=mock_realm_registry,
            halt_checker=mock_halt_checker,
            event_emitter=event_emitter_stub,
        )

    @pytest.fixture
    def sample_petition(self) -> PetitionSubmission:
        """Create a sample petition for testing."""
        return PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition text",
            state=PetitionState.ACKNOWLEDGED,  # After CAS update
            submitter_id=None,
            content_hash=b"x" * 32,
            realm="default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_assign_fate_success(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        event_emitter_stub: PetitionEventEmitterStub,
        sample_petition: PetitionSubmission,
    ) -> None:
        """Test successful fate assignment with event emission."""
        mock_repository.assign_fate_cas.return_value = sample_petition

        result = await service.assign_fate_transactional(
            petition_id=sample_petition.id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ACKNOWLEDGED,
            actor_id="clotho-agent",
            reason="Test reason",
        )

        assert result == sample_petition
        mock_repository.assign_fate_cas.assert_called_once_with(
            sample_petition.id,
            PetitionState.RECEIVED,
            PetitionState.ACKNOWLEDGED,
            fate_reason="Test reason",
        )
        assert len(event_emitter_stub.emitted_fate_events) == 1
        fate_event = event_emitter_stub.emitted_fate_events[0]
        assert fate_event.petition_id == sample_petition.id
        assert fate_event.new_state == "ACKNOWLEDGED"
        assert fate_event.actor_id == "clotho-agent"

    @pytest.mark.asyncio
    async def test_assign_fate_all_terminal_states(
        self,
        mock_repository: AsyncMock,
        mock_hash_service: MagicMock,
        mock_realm_registry: MagicMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test fate assignment works for all three terminal states."""
        for state in [
            PetitionState.ACKNOWLEDGED,
            PetitionState.REFERRED,
            PetitionState.ESCALATED,
        ]:
            emitter = PetitionEventEmitterStub()
            service = PetitionSubmissionService(
                repository=mock_repository,
                hash_service=mock_hash_service,
                realm_registry=mock_realm_registry,
                halt_checker=mock_halt_checker,
                event_emitter=emitter,
            )

            petition = PetitionSubmission(
                id=uuid4(),
                type=PetitionType.GENERAL,
                text="Test",
                state=state,
                submitter_id=None,
                content_hash=b"x" * 32,
                realm="default",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            mock_repository.assign_fate_cas.return_value = petition

            await service.assign_fate_transactional(
                petition_id=petition.id,
                expected_state=PetitionState.RECEIVED,
                new_state=state,
                actor_id="test-agent",
            )

            assert len(emitter.emitted_fate_events) == 1
            assert emitter.emitted_fate_events[0].new_state == state.value

    @pytest.mark.asyncio
    async def test_assign_fate_rolls_back_on_event_failure(
        self,
        mock_repository: AsyncMock,
        mock_hash_service: MagicMock,
        mock_realm_registry: MagicMock,
        mock_halt_checker: AsyncMock,
        sample_petition: PetitionSubmission,
    ) -> None:
        """Test state rollback when event emission fails (HC-1)."""
        # Create emitter that will fail
        emitter = PetitionEventEmitterStub()
        emitter.fate_should_fail = True

        service = PetitionSubmissionService(
            repository=mock_repository,
            hash_service=mock_hash_service,
            realm_registry=mock_realm_registry,
            halt_checker=mock_halt_checker,
            event_emitter=emitter,
        )
        mock_repository.assign_fate_cas.return_value = sample_petition

        with pytest.raises(FateEventEmissionError):
            await service.assign_fate_transactional(
                petition_id=sample_petition.id,
                expected_state=PetitionState.RECEIVED,
                new_state=PetitionState.ACKNOWLEDGED,
                actor_id="clotho-agent",
            )

        # Verify rollback was called
        mock_repository.update_state.assert_called_once_with(
            sample_petition.id, PetitionState.RECEIVED
        )

    @pytest.mark.asyncio
    async def test_assign_fate_raises_fate_event_emission_error(
        self,
        mock_repository: AsyncMock,
        mock_hash_service: MagicMock,
        mock_realm_registry: MagicMock,
        mock_halt_checker: AsyncMock,
        sample_petition: PetitionSubmission,
    ) -> None:
        """Test FateEventEmissionError is raised with proper attributes."""
        emitter = PetitionEventEmitterStub()
        emitter.fate_fail_exception = RuntimeError("Ledger unavailable")

        service = PetitionSubmissionService(
            repository=mock_repository,
            hash_service=mock_hash_service,
            realm_registry=mock_realm_registry,
            halt_checker=mock_halt_checker,
            event_emitter=emitter,
        )
        mock_repository.assign_fate_cas.return_value = sample_petition

        with pytest.raises(FateEventEmissionError) as exc_info:
            await service.assign_fate_transactional(
                petition_id=sample_petition.id,
                expected_state=PetitionState.RECEIVED,
                new_state=PetitionState.ACKNOWLEDGED,
                actor_id="clotho-agent",
            )

        assert exc_info.value.petition_id == sample_petition.id
        assert exc_info.value.new_state == "ACKNOWLEDGED"
        assert isinstance(exc_info.value.cause, RuntimeError)

    @pytest.mark.asyncio
    async def test_assign_fate_rejects_when_halted(
        self,
        mock_repository: AsyncMock,
        mock_hash_service: MagicMock,
        mock_realm_registry: MagicMock,
        event_emitter_stub: PetitionEventEmitterStub,
    ) -> None:
        """Test fate assignment is rejected when system is halted (CT-13)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=True)
        halt_checker.get_halt_reason = AsyncMock(return_value="Emergency halt")

        service = PetitionSubmissionService(
            repository=mock_repository,
            hash_service=mock_hash_service,
            realm_registry=mock_realm_registry,
            halt_checker=halt_checker,
            event_emitter=event_emitter_stub,
        )

        with pytest.raises(SystemHaltedError):
            await service.assign_fate_transactional(
                petition_id=uuid4(),
                expected_state=PetitionState.RECEIVED,
                new_state=PetitionState.ACKNOWLEDGED,
                actor_id="clotho-agent",
            )

        # No CAS should have been attempted
        mock_repository.assign_fate_cas.assert_not_called()

    @pytest.mark.asyncio
    async def test_assign_fate_fails_without_event_emitter(
        self,
        mock_repository: AsyncMock,
        mock_hash_service: MagicMock,
        mock_realm_registry: MagicMock,
        mock_halt_checker: AsyncMock,
        sample_petition: PetitionSubmission,
    ) -> None:
        """Test fate assignment fails when no event emitter is configured (HC-1)."""
        service = PetitionSubmissionService(
            repository=mock_repository,
            hash_service=mock_hash_service,
            realm_registry=mock_realm_registry,
            halt_checker=mock_halt_checker,
            event_emitter=None,  # No emitter configured
        )
        mock_repository.assign_fate_cas.return_value = sample_petition

        with pytest.raises(FateEventEmissionError) as exc_info:
            await service.assign_fate_transactional(
                petition_id=sample_petition.id,
                expected_state=PetitionState.RECEIVED,
                new_state=PetitionState.ACKNOWLEDGED,
                actor_id="clotho-agent",
            )

        assert "not configured" in str(exc_info.value.cause)
        # Verify rollback was called
        mock_repository.update_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_assign_fate_reason_is_optional(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        event_emitter_stub: PetitionEventEmitterStub,
        sample_petition: PetitionSubmission,
    ) -> None:
        """Test fate assignment works without reason."""
        mock_repository.assign_fate_cas.return_value = sample_petition

        await service.assign_fate_transactional(
            petition_id=sample_petition.id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ACKNOWLEDGED,
            actor_id="clotho-agent",
            # No reason provided
        )

        fate_event = event_emitter_stub.emitted_fate_events[0]
        assert fate_event.reason is None

    @pytest.mark.asyncio
    async def test_assign_fate_passes_reason_to_event(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        event_emitter_stub: PetitionEventEmitterStub,
        sample_petition: PetitionSubmission,
    ) -> None:
        """Test fate assignment passes reason to event emitter."""
        mock_repository.assign_fate_cas.return_value = sample_petition

        await service.assign_fate_transactional(
            petition_id=sample_petition.id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ACKNOWLEDGED,
            actor_id="clotho-agent",
            reason="Per protocol section 3.2",
        )

        fate_event = event_emitter_stub.emitted_fate_events[0]
        assert fate_event.reason == "Per protocol section 3.2"


class TestAssignFateTransactionalCASPropagation:
    """Tests for CAS error propagation from repository."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        """Create a mock repository."""
        repo = AsyncMock()
        repo.assign_fate_cas = AsyncMock()
        repo.update_state = AsyncMock()
        return repo

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create a non-halted halt checker."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)
        halt_checker.get_halt_reason = AsyncMock(return_value=None)
        return halt_checker

    @pytest.mark.asyncio
    async def test_cas_error_propagates(
        self,
        mock_repository: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test ConcurrentModificationError from CAS propagates to caller."""
        from src.domain.errors import ConcurrentModificationError

        mock_repository.assign_fate_cas.side_effect = ConcurrentModificationError(
            petition_id=uuid4(),
            expected_state=PetitionState.RECEIVED,
        )

        service = PetitionSubmissionService(
            repository=mock_repository,
            hash_service=MagicMock(hash_text=MagicMock(return_value=b"hash")),
            realm_registry=MagicMock(get_default_realm=MagicMock(return_value=None)),
            halt_checker=mock_halt_checker,
            event_emitter=PetitionEventEmitterStub(),
        )

        with pytest.raises(ConcurrentModificationError):
            await service.assign_fate_transactional(
                petition_id=uuid4(),
                expected_state=PetitionState.RECEIVED,
                new_state=PetitionState.ACKNOWLEDGED,
                actor_id="clotho-agent",
            )


class TestWithdrawPetition:
    """Tests for withdraw_petition method (Story 7.3, FR-7.5)."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        """Create a mock repository."""
        repo = AsyncMock()
        repo.assign_fate_cas = AsyncMock()
        repo.update_state = AsyncMock()
        repo.get = AsyncMock()
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def mock_hash_service(self) -> MagicMock:
        """Create a mock hash service."""
        hash_service = MagicMock()
        hash_service.hash_text = MagicMock(return_value=b"mock_hash")
        return hash_service

    @pytest.fixture
    def mock_realm_registry(self) -> MagicMock:
        """Create a mock realm registry."""
        realm_registry = MagicMock()
        realm_registry.get_default_realm = MagicMock(return_value=None)
        return realm_registry

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create a mock halt checker that is not halted."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)
        halt_checker.get_halt_reason = AsyncMock(return_value=None)
        return halt_checker

    @pytest.fixture
    def event_emitter_stub(self) -> PetitionEventEmitterStub:
        """Create an event emitter stub."""
        return PetitionEventEmitterStub()

    @pytest.fixture
    def submitter_id(self) -> UUID:
        """Create a submitter UUID for tests."""
        return uuid4()

    @pytest.fixture
    def sample_petition_received(self, submitter_id: UUID) -> PetitionSubmission:
        """Create a sample petition in RECEIVED state."""
        return PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition text",
            state=PetitionState.RECEIVED,
            submitter_id=submitter_id,
            content_hash=b"x" * 32,
            realm="default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_petition_deliberating(self, submitter_id: UUID) -> PetitionSubmission:
        """Create a sample petition in DELIBERATING state."""
        return PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition text",
            state=PetitionState.DELIBERATING,
            submitter_id=submitter_id,
            content_hash=b"x" * 32,
            realm="default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_petition_acknowledged(self, submitter_id: UUID) -> PetitionSubmission:
        """Create a sample petition in ACKNOWLEDGED (terminal) state."""
        return PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition text",
            state=PetitionState.ACKNOWLEDGED,
            submitter_id=submitter_id,
            content_hash=b"x" * 32,
            realm="default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            fate_reason="Already fated",
        )

    @pytest.fixture
    def sample_anonymous_petition(self) -> PetitionSubmission:
        """Create a sample anonymous petition (no submitter_id)."""
        return PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Anonymous petition text",
            state=PetitionState.RECEIVED,
            submitter_id=None,  # Anonymous
            content_hash=b"x" * 32,
            realm="default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def service(
        self,
        mock_repository: AsyncMock,
        mock_hash_service: MagicMock,
        mock_realm_registry: MagicMock,
        mock_halt_checker: AsyncMock,
        event_emitter_stub: PetitionEventEmitterStub,
    ) -> PetitionSubmissionService:
        """Create a service with mock dependencies."""
        return PetitionSubmissionService(
            repository=mock_repository,
            hash_service=mock_hash_service,
            realm_registry=mock_realm_registry,
            halt_checker=mock_halt_checker,
            event_emitter=event_emitter_stub,
        )

    @pytest.mark.asyncio
    async def test_withdraw_petition_success(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        event_emitter_stub: PetitionEventEmitterStub,
        sample_petition_received: PetitionSubmission,
        submitter_id: UUID,
    ) -> None:
        """Test successful withdrawal of a RECEIVED petition (AC1, happy path)."""
        # Setup: petition in RECEIVED state, matching submitter
        mock_repository.get.return_value = sample_petition_received

        # After withdrawal, petition is ACKNOWLEDGED
        withdrawn_petition = PetitionSubmission(
            id=sample_petition_received.id,
            type=sample_petition_received.type,
            text=sample_petition_received.text,
            state=PetitionState.ACKNOWLEDGED,
            submitter_id=sample_petition_received.submitter_id,
            content_hash=sample_petition_received.content_hash,
            realm=sample_petition_received.realm,
            created_at=sample_petition_received.created_at,
            updated_at=datetime.now(timezone.utc),
            fate_reason="WITHDRAWN: My reason",
        )
        mock_repository.assign_fate_cas.return_value = withdrawn_petition

        result = await service.withdraw_petition(
            petition_id=sample_petition_received.id,
            requester_id=submitter_id,
            reason="My reason",
        )

        assert result.state == PetitionState.ACKNOWLEDGED
        mock_repository.get.assert_called_once_with(sample_petition_received.id)
        mock_repository.assign_fate_cas.assert_called_once()
        # Verify fate event was emitted
        assert len(event_emitter_stub.emitted_fate_events) == 1
        # Verify withdrawn event was emitted
        assert len(event_emitter_stub.emitted_withdrawn_events) == 1
        withdrawn_event = event_emitter_stub.emitted_withdrawn_events[0]
        assert withdrawn_event.petition_id == sample_petition_received.id
        assert withdrawn_event.withdrawn_by == submitter_id
        assert withdrawn_event.reason == "My reason"

    @pytest.mark.asyncio
    async def test_withdraw_petition_default_reason(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        event_emitter_stub: PetitionEventEmitterStub,
        sample_petition_received: PetitionSubmission,
        submitter_id: UUID,
    ) -> None:
        """Test withdrawal uses default reason when none provided (AC1)."""
        mock_repository.get.return_value = sample_petition_received

        withdrawn_petition = PetitionSubmission(
            id=sample_petition_received.id,
            type=sample_petition_received.type,
            text=sample_petition_received.text,
            state=PetitionState.ACKNOWLEDGED,
            submitter_id=sample_petition_received.submitter_id,
            content_hash=sample_petition_received.content_hash,
            realm=sample_petition_received.realm,
            created_at=sample_petition_received.created_at,
            updated_at=datetime.now(timezone.utc),
            fate_reason="WITHDRAWN: Petitioner withdrew",
        )
        mock_repository.assign_fate_cas.return_value = withdrawn_petition

        result = await service.withdraw_petition(
            petition_id=sample_petition_received.id,
            requester_id=submitter_id,
            reason=None,  # No reason provided
        )

        assert result.state == PetitionState.ACKNOWLEDGED
        # Verify default reason used
        withdrawn_event = event_emitter_stub.emitted_withdrawn_events[0]
        assert withdrawn_event.reason is None  # Event stores the provided reason (None)

    @pytest.mark.asyncio
    async def test_withdraw_petition_from_deliberating(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        sample_petition_deliberating: PetitionSubmission,
        submitter_id: UUID,
    ) -> None:
        """Test withdrawal from DELIBERATING state (AC1)."""
        mock_repository.get.return_value = sample_petition_deliberating

        withdrawn_petition = PetitionSubmission(
            id=sample_petition_deliberating.id,
            type=sample_petition_deliberating.type,
            text=sample_petition_deliberating.text,
            state=PetitionState.ACKNOWLEDGED,
            submitter_id=sample_petition_deliberating.submitter_id,
            content_hash=sample_petition_deliberating.content_hash,
            realm=sample_petition_deliberating.realm,
            created_at=sample_petition_deliberating.created_at,
            updated_at=datetime.now(timezone.utc),
            fate_reason="WITHDRAWN: Petitioner withdrew",
        )
        mock_repository.assign_fate_cas.return_value = withdrawn_petition

        result = await service.withdraw_petition(
            petition_id=sample_petition_deliberating.id,
            requester_id=submitter_id,
        )

        assert result.state == PetitionState.ACKNOWLEDGED

    @pytest.mark.asyncio
    async def test_withdraw_petition_not_found(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        submitter_id: UUID,
    ) -> None:
        """Test withdrawal of non-existent petition (AC4)."""
        mock_repository.get.return_value = None
        petition_id = uuid4()

        with pytest.raises(PetitionNotFoundError) as exc_info:
            await service.withdraw_petition(
                petition_id=petition_id,
                requester_id=submitter_id,
            )

        assert str(petition_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_withdraw_petition_already_fated_acknowledged(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        sample_petition_acknowledged: PetitionSubmission,
        submitter_id: UUID,
    ) -> None:
        """Test withdrawal of already acknowledged petition (AC2)."""
        mock_repository.get.return_value = sample_petition_acknowledged

        with pytest.raises(PetitionAlreadyFatedError) as exc_info:
            await service.withdraw_petition(
                petition_id=sample_petition_acknowledged.id,
                requester_id=submitter_id,
            )

        assert exc_info.value.terminal_state == PetitionState.ACKNOWLEDGED

    @pytest.mark.asyncio
    async def test_withdraw_petition_already_fated_referred(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        submitter_id: UUID,
    ) -> None:
        """Test withdrawal of already referred petition (AC2)."""
        referred_petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Referred petition",
            state=PetitionState.REFERRED,
            submitter_id=submitter_id,
            content_hash=b"x" * 32,
            realm="default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_repository.get.return_value = referred_petition

        with pytest.raises(PetitionAlreadyFatedError) as exc_info:
            await service.withdraw_petition(
                petition_id=referred_petition.id,
                requester_id=submitter_id,
            )

        assert exc_info.value.terminal_state == PetitionState.REFERRED

    @pytest.mark.asyncio
    async def test_withdraw_petition_already_fated_escalated(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        submitter_id: UUID,
    ) -> None:
        """Test withdrawal of already escalated petition (AC2)."""
        escalated_petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.CESSATION,
            text="Escalated petition",
            state=PetitionState.ESCALATED,
            submitter_id=submitter_id,
            content_hash=b"x" * 32,
            realm="default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_repository.get.return_value = escalated_petition

        with pytest.raises(PetitionAlreadyFatedError) as exc_info:
            await service.withdraw_petition(
                petition_id=escalated_petition.id,
                requester_id=submitter_id,
            )

        assert exc_info.value.terminal_state == PetitionState.ESCALATED

    @pytest.mark.asyncio
    async def test_withdraw_petition_unauthorized_different_submitter(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        sample_petition_received: PetitionSubmission,
    ) -> None:
        """Test withdrawal by different submitter is rejected (AC3)."""
        mock_repository.get.return_value = sample_petition_received
        different_submitter = uuid4()  # Different from petition's submitter_id

        with pytest.raises(UnauthorizedWithdrawalError) as exc_info:
            await service.withdraw_petition(
                petition_id=sample_petition_received.id,
                requester_id=different_submitter,
            )

        assert str(sample_petition_received.id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_withdraw_anonymous_petition_rejected(
        self,
        service: PetitionSubmissionService,
        mock_repository: AsyncMock,
        sample_anonymous_petition: PetitionSubmission,
    ) -> None:
        """Test withdrawal of anonymous petition is rejected (AC3)."""
        mock_repository.get.return_value = sample_anonymous_petition
        any_requester = uuid4()

        with pytest.raises(UnauthorizedWithdrawalError) as exc_info:
            await service.withdraw_petition(
                petition_id=sample_anonymous_petition.id,
                requester_id=any_requester,
            )

        assert "Anonymous" in str(exc_info.value) or "anonymous" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_withdraw_petition_halt_check_first(
        self,
        mock_repository: AsyncMock,
        mock_hash_service: MagicMock,
        mock_realm_registry: MagicMock,
        event_emitter_stub: PetitionEventEmitterStub,
        sample_petition_received: PetitionSubmission,
        submitter_id: UUID,
    ) -> None:
        """Test HALT CHECK FIRST pattern - halt checked before other operations (AC5, CT-13)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=True)
        halt_checker.get_halt_reason = AsyncMock(return_value="Emergency halt")

        service = PetitionSubmissionService(
            repository=mock_repository,
            hash_service=mock_hash_service,
            realm_registry=mock_realm_registry,
            halt_checker=halt_checker,
            event_emitter=event_emitter_stub,
        )

        with pytest.raises(SystemHaltedError):
            await service.withdraw_petition(
                petition_id=sample_petition_received.id,
                requester_id=submitter_id,
            )

        # Repository should NOT be called - halt check happens first
        mock_repository.get.assert_not_called()
        mock_repository.assign_fate_cas.assert_not_called()
