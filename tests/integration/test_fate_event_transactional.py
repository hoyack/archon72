"""Integration tests for transactional fate event emission (Story 1.7, FR-2.5, HC-1).

These tests verify that the transactional fate assignment mechanism correctly
combines CAS state update with event emission, including proper rollback on failure.

Constitutional Constraints:
- FR-2.5: System SHALL emit fate event in same transaction as state update
- HC-1: Fate transition requires witness event - NO silent fate assignment
- NFR-3.3: Event witnessing: 100% fate events persisted [CRITICAL]

Test Strategy:
- Verify state and event are atomically committed together
- Verify state rollback when event emission fails
- Test concurrent fate assignment with event emission
- Verify no fate is assigned without corresponding event
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.petition_submission_service import PetitionSubmissionService
from src.domain.errors import ConcurrentModificationError, FateEventEmissionError
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs import (
    ContentHashServiceStub,
    HaltCheckerStub,
    PetitionEventEmitterStub,
    PetitionSubmissionRepositoryStub,
    RealmRegistryStub,
)


def _make_received_petition() -> PetitionSubmission:
    """Create a petition in RECEIVED state for fate assignment tests."""
    return PetitionSubmission(
        id=uuid.uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for transactional fate assignment",
        state=PetitionState.RECEIVED,
        realm="test-realm",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_deliberating_petition() -> PetitionSubmission:
    """Create a petition in DELIBERATING state for fate assignment tests."""
    return PetitionSubmission(
        id=uuid.uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for transactional fate assignment",
        state=PetitionState.DELIBERATING,
        realm="test-realm",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestTransactionalFateAssignmentIntegration:
    """Integration tests for transactional fate assignment with event emission."""

    @pytest.fixture
    def repository(self) -> PetitionSubmissionRepositoryStub:
        """Create a fresh repository for each test."""
        return PetitionSubmissionRepositoryStub()

    @pytest.fixture
    def event_emitter(self) -> PetitionEventEmitterStub:
        """Create a fresh event emitter for each test."""
        return PetitionEventEmitterStub()

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a halt checker that is not halted."""
        return HaltCheckerStub(initial_halted=False)

    @pytest.fixture
    def service(
        self,
        repository: PetitionSubmissionRepositoryStub,
        event_emitter: PetitionEventEmitterStub,
        halt_checker: HaltCheckerStub,
    ) -> PetitionSubmissionService:
        """Create a service with real stubs for integration testing."""
        return PetitionSubmissionService(
            repository=repository,
            hash_service=ContentHashServiceStub(),
            realm_registry=RealmRegistryStub(),
            halt_checker=halt_checker,
            event_emitter=event_emitter,
        )

    @pytest.mark.asyncio
    async def test_fr25_state_and_event_committed_together(
        self,
        service: PetitionSubmissionService,
        repository: PetitionSubmissionRepositoryStub,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """FR-2.5: State update and event emission happen atomically."""
        petition = _make_received_petition()
        await repository.save(petition)

        # Assign fate transactionally
        result = await service.assign_fate_transactional(
            petition_id=petition.id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ACKNOWLEDGED,
            actor_id="clotho-agent",
            reason="Test reason",
        )

        # Verify state is updated
        stored = await repository.get(petition.id)
        assert stored is not None
        assert stored.state == PetitionState.ACKNOWLEDGED

        # Verify event was emitted
        assert len(event_emitter.emitted_fate_events) == 1
        fate_event = event_emitter.emitted_fate_events[0]
        assert fate_event.petition_id == petition.id
        assert fate_event.previous_state == "RECEIVED"
        assert fate_event.new_state == "ACKNOWLEDGED"
        assert fate_event.actor_id == "clotho-agent"
        assert fate_event.reason == "Test reason"

    @pytest.mark.asyncio
    async def test_hc1_no_fate_without_event_rollback(
        self,
        repository: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """HC-1: If event emission fails, state is rolled back - no silent fate."""
        # Create emitter that will fail
        failing_emitter = PetitionEventEmitterStub()
        failing_emitter.fate_should_fail = True

        service = PetitionSubmissionService(
            repository=repository,
            hash_service=ContentHashServiceStub(),
            realm_registry=RealmRegistryStub(),
            halt_checker=halt_checker,
            event_emitter=failing_emitter,
        )

        petition = _make_received_petition()
        await repository.save(petition)

        # Attempt fate assignment - should fail and rollback
        with pytest.raises(FateEventEmissionError):
            await service.assign_fate_transactional(
                petition_id=petition.id,
                expected_state=PetitionState.RECEIVED,
                new_state=PetitionState.ACKNOWLEDGED,
                actor_id="clotho-agent",
            )

        # Verify state was rolled back to RECEIVED
        stored = await repository.get(petition.id)
        assert stored is not None
        assert stored.state == PetitionState.RECEIVED

        # Verify no fate event was persisted
        assert len(failing_emitter.emitted_fate_events) == 0

    @pytest.mark.asyncio
    async def test_nfr33_all_fates_have_events(
        self,
        repository: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """NFR-3.3: 100% fate events persisted - every fate has event."""
        event_emitter = PetitionEventEmitterStub()
        service = PetitionSubmissionService(
            repository=repository,
            hash_service=ContentHashServiceStub(),
            realm_registry=RealmRegistryStub(),
            halt_checker=halt_checker,
            event_emitter=event_emitter,
        )

        # Create petitions and assign all three fates
        for fate in [PetitionState.ACKNOWLEDGED, PetitionState.REFERRED, PetitionState.ESCALATED]:
            petition = _make_received_petition()
            await repository.save(petition)

            await service.assign_fate_transactional(
                petition_id=petition.id,
                expected_state=PetitionState.RECEIVED,
                new_state=fate,
                actor_id="test-agent",
            )

        # Verify we have exactly 3 fate events
        assert len(event_emitter.emitted_fate_events) == 3

        # Verify each fate type has an event
        emitted_states = {e.new_state for e in event_emitter.emitted_fate_events}
        assert emitted_states == {"ACKNOWLEDGED", "REFERRED", "ESCALATED"}

    @pytest.mark.asyncio
    async def test_concurrent_fate_with_event_exactly_one(
        self,
        repository: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Concurrent fate assignments - exactly one wins with event."""
        event_emitter = PetitionEventEmitterStub()
        service = PetitionSubmissionService(
            repository=repository,
            hash_service=ContentHashServiceStub(),
            realm_registry=RealmRegistryStub(),
            halt_checker=halt_checker,
            event_emitter=event_emitter,
        )

        petition = _make_received_petition()
        await repository.save(petition)

        successes = []
        failures = []

        async def attempt_fate(fate: PetitionState) -> None:
            try:
                result = await service.assign_fate_transactional(
                    petition_id=petition.id,
                    expected_state=PetitionState.RECEIVED,
                    new_state=fate,
                    actor_id=f"{fate.value.lower()}-agent",
                )
                successes.append(result.state)
            except (ConcurrentModificationError, FateEventEmissionError) as e:
                failures.append((fate, type(e).__name__))

        # Race three fates
        await asyncio.gather(
            attempt_fate(PetitionState.ACKNOWLEDGED),
            attempt_fate(PetitionState.REFERRED),
            attempt_fate(PetitionState.ESCALATED),
        )

        # Exactly one success
        assert len(successes) == 1
        assert len(failures) == 2

        # Exactly one event
        assert len(event_emitter.emitted_fate_events) == 1
        event = event_emitter.emitted_fate_events[0]
        assert event.petition_id == petition.id
        assert event.new_state == successes[0].value

    @pytest.mark.asyncio
    async def test_rollback_on_event_failure_high_concurrency(
        self,
        repository: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """High concurrency with event failures - all fates rolled back."""
        # Create emitter that always fails
        failing_emitter = PetitionEventEmitterStub()
        failing_emitter.fate_should_fail = True

        service = PetitionSubmissionService(
            repository=repository,
            hash_service=ContentHashServiceStub(),
            realm_registry=RealmRegistryStub(),
            halt_checker=halt_checker,
            event_emitter=failing_emitter,
        )

        # Create 10 petitions
        petitions = [_make_received_petition() for _ in range(10)]
        for p in petitions:
            await repository.save(p)

        errors = []

        async def attempt_fate(petition: PetitionSubmission) -> None:
            try:
                await service.assign_fate_transactional(
                    petition_id=petition.id,
                    expected_state=PetitionState.RECEIVED,
                    new_state=PetitionState.ACKNOWLEDGED,
                    actor_id="test-agent",
                )
            except FateEventEmissionError:
                errors.append(petition.id)

        # Attempt all fate assignments
        await asyncio.gather(*[attempt_fate(p) for p in petitions])

        # All should have failed
        assert len(errors) == 10

        # All states should be rolled back to RECEIVED
        for petition in petitions:
            stored = await repository.get(petition.id)
            assert stored is not None
            assert stored.state == PetitionState.RECEIVED, (
                f"Petition {petition.id} should be RECEIVED, got {stored.state}"
            )

        # No events should have been emitted
        assert len(failing_emitter.emitted_fate_events) == 0

    @pytest.mark.asyncio
    async def test_event_contains_all_required_fields(
        self,
        service: PetitionSubmissionService,
        repository: PetitionSubmissionRepositoryStub,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """Verify emitted fate event contains all required fields."""
        petition = _make_received_petition()
        await repository.save(petition)

        await service.assign_fate_transactional(
            petition_id=petition.id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.REFERRED,
            actor_id="lachesis-agent",
            reason="Requires knight intervention",
        )

        event = event_emitter.emitted_fate_events[0]

        # Verify all required fields are present
        assert event.petition_id == petition.id
        assert event.previous_state == "RECEIVED"
        assert event.new_state == "REFERRED"
        assert event.actor_id == "lachesis-agent"
        assert event.reason == "Requires knight intervention"
        assert event.emitted_at is not None

    @pytest.mark.asyncio
    async def test_fate_event_emission_after_cas_success_only(
        self,
        repository: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Event emission only happens after successful CAS."""
        event_emitter = PetitionEventEmitterStub()
        service = PetitionSubmissionService(
            repository=repository,
            hash_service=ContentHashServiceStub(),
            realm_registry=RealmRegistryStub(),
            halt_checker=halt_checker,
            event_emitter=event_emitter,
        )

        petition = _make_received_petition()
        await repository.save(petition)

        # First successful fate
        await service.assign_fate_transactional(
            petition_id=petition.id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ACKNOWLEDGED,
            actor_id="clotho-agent",
        )

        initial_event_count = len(event_emitter.emitted_fate_events)
        assert initial_event_count == 1

        # Attempt second fate with wrong expected state
        # CAS should fail before event emission
        with pytest.raises(ConcurrentModificationError):
            await service.assign_fate_transactional(
                petition_id=petition.id,
                expected_state=PetitionState.RECEIVED,  # Wrong - already ACKNOWLEDGED
                new_state=PetitionState.ESCALATED,
                actor_id="atropos-agent",
            )

        # No new event should have been emitted
        assert len(event_emitter.emitted_fate_events) == initial_event_count


class TestTransactionalFateCorrelation:
    """Tests for event-to-state correlation."""

    @pytest.fixture
    def repository(self) -> PetitionSubmissionRepositoryStub:
        """Create a fresh repository for each test."""
        return PetitionSubmissionRepositoryStub()

    @pytest.fixture
    def event_emitter(self) -> PetitionEventEmitterStub:
        """Create a fresh event emitter for each test."""
        return PetitionEventEmitterStub()

    @pytest.fixture
    def service(
        self,
        repository: PetitionSubmissionRepositoryStub,
        event_emitter: PetitionEventEmitterStub,
    ) -> PetitionSubmissionService:
        """Create a service for testing."""
        return PetitionSubmissionService(
            repository=repository,
            hash_service=ContentHashServiceStub(),
            realm_registry=RealmRegistryStub(),
            halt_checker=HaltCheckerStub(initial_halted=False),
            event_emitter=event_emitter,
        )

    @pytest.mark.asyncio
    async def test_event_matches_final_state(
        self,
        service: PetitionSubmissionService,
        repository: PetitionSubmissionRepositoryStub,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """Event's new_state matches petition's final state."""
        petition = _make_received_petition()
        await repository.save(petition)

        await service.assign_fate_transactional(
            petition_id=petition.id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ESCALATED,
            actor_id="atropos-agent",
        )

        stored = await repository.get(petition.id)
        event = event_emitter.get_fate_event_by_petition_id(petition.id)

        assert stored is not None
        assert event is not None
        assert event.new_state == stored.state.value

    @pytest.mark.asyncio
    async def test_multiple_petitions_event_correlation(
        self,
        service: PetitionSubmissionService,
        repository: PetitionSubmissionRepositoryStub,
        event_emitter: PetitionEventEmitterStub,
    ) -> None:
        """Each petition's event correlates to correct petition."""
        petitions = [_make_received_petition() for _ in range(5)]
        for p in petitions:
            await repository.save(p)

        # Assign different fates
        fates = [
            PetitionState.ACKNOWLEDGED,
            PetitionState.REFERRED,
            PetitionState.ESCALATED,
            PetitionState.ACKNOWLEDGED,
            PetitionState.REFERRED,
        ]

        for petition, fate in zip(petitions, fates):
            await service.assign_fate_transactional(
                petition_id=petition.id,
                expected_state=PetitionState.RECEIVED,
                new_state=fate,
                actor_id=f"{fate.value.lower()}-agent",
            )

        # Verify each petition has matching event
        for petition, fate in zip(petitions, fates):
            stored = await repository.get(petition.id)
            event = event_emitter.get_fate_event_by_petition_id(petition.id)

            assert stored is not None
            assert event is not None
            assert stored.state == fate
            assert event.new_state == fate.value
            assert event.petition_id == petition.id
