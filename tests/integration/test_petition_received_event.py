"""Integration tests for petition.received event emission (Story 1.2, FR-1.7).

Tests verify the full flow from petition submission through event emission
to governance ledger persistence.

Constitutional Constraints:
- FR-1.7: System SHALL emit PetitionReceived event on successful intake
- CT-12: Witnessing creates accountability - event witnessed via ledger
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.petition_submission_service import (
    PetitionSubmissionService,
)
from src.domain.models.petition_submission import PetitionType
from src.infrastructure.stubs import (
    ContentHashServiceStub,
    HaltCheckerStub,
    PetitionEventEmitterStub,
    PetitionSubmissionRepositoryStub,
    RealmRegistryStub,
)


class FakeTimeAuthority:
    """Fake time authority for integration tests."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._time

    def utcnow(self) -> datetime:
        return self._time

    def monotonic(self) -> float:
        return 12345.0


class TestPetitionSubmissionEmitsEvent:
    """Integration tests for petition submission with event emission."""

    @pytest.fixture
    def repository(self) -> PetitionSubmissionRepositoryStub:
        """Create a petition submission repository stub."""
        return PetitionSubmissionRepositoryStub()

    @pytest.fixture
    def hash_service(self) -> ContentHashServiceStub:
        """Create a content hash service stub."""
        return ContentHashServiceStub()

    @pytest.fixture
    def realm_registry(self) -> RealmRegistryStub:
        """Create a realm registry stub."""
        return RealmRegistryStub()

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a halt checker stub (not halted)."""
        return HaltCheckerStub(is_halted=False)

    @pytest.fixture
    def event_emitter(self) -> PetitionEventEmitterStub:
        """Create a petition event emitter stub."""
        return PetitionEventEmitterStub()

    @pytest.fixture
    def service(
        self,
        repository: PetitionSubmissionRepositoryStub,
        hash_service: ContentHashServiceStub,
        realm_registry: RealmRegistryStub,
        halt_checker: HaltCheckerStub,
        event_emitter: PetitionEventEmitterStub,
    ) -> PetitionSubmissionService:
        """Create a fully wired submission service."""
        return PetitionSubmissionService(
            repository=repository,
            hash_service=hash_service,
            realm_registry=realm_registry,
            halt_checker=halt_checker,
            event_emitter=event_emitter,
        )

    @pytest.mark.asyncio
    async def test_submit_petition_emits_event(
        self,
        service: PetitionSubmissionService,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """Test that submitting a petition emits petition.received event (FR-1.7)."""
        result = await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition for integration testing",
        )

        # Event should be emitted
        assert len(event_emitter.emitted_events) == 1

        # Event should match petition
        event = event_emitter.emitted_events[0]
        assert event.petition_id == result.petition_id
        assert event.petition_type == "GENERAL"
        assert event.realm == result.realm
        assert event.content_hash == result.content_hash

    @pytest.mark.asyncio
    async def test_submit_petition_emits_event_with_submitter(
        self,
        service: PetitionSubmissionService,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """Test event emission includes submitter_id when provided."""
        submitter_id = uuid4()
        await service.submit_petition(
            petition_type=PetitionType.CESSATION,
            text="Cessation petition with submitter",
            submitter_id=submitter_id,
        )

        assert len(event_emitter.emitted_events) == 1
        event = event_emitter.emitted_events[0]
        assert event.submitter_id == submitter_id

    @pytest.mark.asyncio
    async def test_submit_petition_no_event_without_emitter(
        self,
        repository: PetitionSubmissionRepositoryStub,
        hash_service: ContentHashServiceStub,
        realm_registry: RealmRegistryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test submission works without event emitter (backward compatibility)."""
        service = PetitionSubmissionService(
            repository=repository,
            hash_service=hash_service,
            realm_registry=realm_registry,
            halt_checker=halt_checker,
            event_emitter=None,  # No emitter
        )

        result = await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition without event emission",
        )

        # Submission should succeed
        assert result.petition_id is not None
        assert result.state.value == "RECEIVED"

    @pytest.mark.asyncio
    async def test_submission_succeeds_when_event_emission_fails(
        self,
        repository: PetitionSubmissionRepositoryStub,
        hash_service: ContentHashServiceStub,
        realm_registry: RealmRegistryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test submission succeeds even if event emission fails (graceful degradation)."""
        # Configure emitter to fail
        failing_emitter = PetitionEventEmitterStub()
        failing_emitter.should_fail = True

        service = PetitionSubmissionService(
            repository=repository,
            hash_service=hash_service,
            realm_registry=realm_registry,
            halt_checker=halt_checker,
            event_emitter=failing_emitter,
        )

        result = await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition with failing emitter",
        )

        # Submission should still succeed
        assert result.petition_id is not None
        assert result.state.value == "RECEIVED"

        # Petition should be persisted
        saved = await repository.get(result.petition_id)
        assert saved is not None

    @pytest.mark.asyncio
    async def test_no_event_during_halt(
        self,
        repository: PetitionSubmissionRepositoryStub,
        hash_service: ContentHashServiceStub,
        realm_registry: RealmRegistryStub,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """Test no event emission during system halt (CT-13)."""
        halted_checker = HaltCheckerStub(is_halted=True, halt_reason="Test halt")

        service = PetitionSubmissionService(
            repository=repository,
            hash_service=hash_service,
            realm_registry=realm_registry,
            halt_checker=halted_checker,
            event_emitter=event_emitter,
        )

        from src.domain.errors import SystemHaltedError

        with pytest.raises(SystemHaltedError):
            await service.submit_petition(
                petition_type=PetitionType.GENERAL,
                text="Test petition during halt",
            )

        # No event should be emitted since submission was rejected
        assert len(event_emitter.emitted_events) == 0

    @pytest.mark.asyncio
    async def test_multiple_submissions_emit_multiple_events(
        self,
        service: PetitionSubmissionService,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """Test multiple submissions emit separate events."""
        result1 = await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="First petition",
        )
        result2 = await service.submit_petition(
            petition_type=PetitionType.CESSATION,
            text="Second petition",
        )

        assert len(event_emitter.emitted_events) == 2

        # Events should have different petition IDs
        ids = [e.petition_id for e in event_emitter.emitted_events]
        assert result1.petition_id in ids
        assert result2.petition_id in ids
        assert result1.petition_id != result2.petition_id

    @pytest.mark.asyncio
    async def test_event_contains_realm(
        self,
        repository: PetitionSubmissionRepositoryStub,
        hash_service: ContentHashServiceStub,
        halt_checker: HaltCheckerStub,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """Test event includes resolved realm."""
        from src.domain.models.realm import Realm

        # Create realm registry with custom realm
        realm_registry = RealmRegistryStub()
        realm_registry.register_realm(
            Realm(
                name="governance",
                description="Governance realm",
                is_default=False,
            )
        )

        service = PetitionSubmissionService(
            repository=repository,
            hash_service=hash_service,
            realm_registry=realm_registry,
            halt_checker=halt_checker,
            event_emitter=event_emitter,
        )

        await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition",
            realm="governance",
        )

        assert len(event_emitter.emitted_events) == 1
        assert event_emitter.emitted_events[0].realm == "governance"
