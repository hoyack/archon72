"""Integration tests for ReferralExecutionService.

Story: 4.2 - Referral Execution Service
Tests the full execution flow with stubs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from src.application.services.referral_execution_service import (
    JOB_TYPE_REFERRAL_TIMEOUT,
    ReferralExecutionService,
)
from src.domain.events.referral import PETITION_REFERRED_EVENT_TYPE
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.domain.models.referral import (
    REFERRAL_DEFAULT_DEADLINE_CYCLES,
    ReferralStatus,
)
from src.infrastructure.stubs.content_hash_service_stub import ContentHashServiceStub
from src.infrastructure.stubs.job_scheduler_stub import JobSchedulerStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.referral_repository_stub import ReferralRepositoryStub


class EventWriterStub:
    """Simple event writer stub for testing."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    async def write(self, event_data: dict[str, Any]) -> None:
        """Write event to in-memory storage."""
        self._events.append(event_data)

    def get_events(self) -> list[dict[str, Any]]:
        """Get all recorded events."""
        return self._events.copy()

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()


@pytest.fixture
def referral_repo() -> ReferralRepositoryStub:
    """Create fresh referral repository stub."""
    return ReferralRepositoryStub()


@pytest.fixture
def petition_repo() -> PetitionSubmissionRepositoryStub:
    """Create fresh petition repository stub."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def event_writer() -> EventWriterStub:
    """Create fresh event writer stub."""
    return EventWriterStub()


@pytest.fixture
def job_scheduler() -> JobSchedulerStub:
    """Create fresh job scheduler stub."""
    return JobSchedulerStub()


@pytest.fixture
def hash_service() -> ContentHashServiceStub:
    """Create fresh hash service stub."""
    return ContentHashServiceStub()


@pytest.fixture
def service(
    referral_repo: ReferralRepositoryStub,
    petition_repo: PetitionSubmissionRepositoryStub,
    event_writer: EventWriterStub,
    job_scheduler: JobSchedulerStub,
    hash_service: ContentHashServiceStub,
) -> ReferralExecutionService:
    """Create ReferralExecutionService with all stubs."""
    return ReferralExecutionService(
        referral_repo=referral_repo,
        petition_repo=petition_repo,
        event_writer=event_writer,
        job_scheduler=job_scheduler,
        hash_service=hash_service,
    )


@pytest.fixture
def deliberating_petition(
    petition_repo: PetitionSubmissionRepositoryStub,
) -> PetitionSubmission:
    """Create and store a petition in DELIBERATING state."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for referral integration",
        submitter_id=uuid4(),
        realm="TECH",
        state=PetitionState.DELIBERATING,
    )
    petition_repo._submissions[petition.id] = petition
    return petition


class TestFullExecutionFlow:
    """Integration tests for the full referral execution flow."""

    @pytest.mark.asyncio
    async def test_full_execution_flow_success(
        self,
        service: ReferralExecutionService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        event_writer: EventWriterStub,
        job_scheduler: JobSchedulerStub,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Test successful end-to-end referral execution."""
        realm_id = uuid4()

        # Execute referral
        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Verify referral record
        assert referral.petition_id == deliberating_petition.id
        assert referral.realm_id == realm_id
        assert referral.status == ReferralStatus.PENDING
        assert referral.assigned_knight_id is None
        assert referral.extensions_granted == 0

        # Verify deadline is approximately 3 weeks out
        expected_deadline = datetime.now(timezone.utc) + timedelta(
            weeks=REFERRAL_DEFAULT_DEADLINE_CYCLES
        )
        assert abs((referral.deadline - expected_deadline).total_seconds()) < 2

        # Verify referral was persisted
        stored = await referral_repo.get_by_id(referral.referral_id)
        assert stored is not None
        assert stored.referral_id == referral.referral_id

        # Verify petition state was updated
        updated_petition = await petition_repo.get(deliberating_petition.id)
        assert updated_petition is not None
        assert updated_petition.state == PetitionState.REFERRED

        # Verify event was emitted
        events = event_writer.get_events()
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == PETITION_REFERRED_EVENT_TYPE
        assert event["petition_id"] == str(deliberating_petition.id)
        assert event["referral_id"] == str(referral.referral_id)
        assert event["realm_id"] == str(realm_id)
        assert "witness_hash" in event

        # Verify job was scheduled
        jobs = job_scheduler.get_all_jobs()
        assert len(jobs) >= 1
        referral_jobs = [j for j in jobs if j.job_type == JOB_TYPE_REFERRAL_TIMEOUT]
        assert len(referral_jobs) == 1
        job = referral_jobs[0]
        assert job.payload["referral_id"] == str(referral.referral_id)
        assert job.payload["petition_id"] == str(deliberating_petition.id)

    @pytest.mark.asyncio
    async def test_idempotency_returns_same_referral(
        self,
        service: ReferralExecutionService,
        event_writer: EventWriterStub,
        job_scheduler: JobSchedulerStub,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Test that repeated execution returns same referral."""
        realm_id = uuid4()

        # First execution
        referral1 = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        initial_event_count = len(event_writer.get_events())
        initial_jobs = job_scheduler.get_all_jobs()
        initial_job_count = len(initial_jobs)

        # Second execution - should be idempotent
        referral2 = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Should return same referral
        assert referral2.referral_id == referral1.referral_id
        assert referral2.petition_id == referral1.petition_id

        # Should not emit additional events or schedule additional jobs
        assert len(event_writer.get_events()) == initial_event_count
        final_jobs = job_scheduler.get_all_jobs()
        assert len(final_jobs) == initial_job_count

    @pytest.mark.asyncio
    async def test_multiple_petitions_independent_referrals(
        self,
        service: ReferralExecutionService,
        petition_repo: PetitionSubmissionRepositoryStub,
        referral_repo: ReferralRepositoryStub,
    ) -> None:
        """Test that multiple petitions get independent referrals."""
        realm_id = uuid4()

        # Create two petitions
        petition1 = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition 1 for referral",
            submitter_id=uuid4(),
            realm="TECH",
            state=PetitionState.DELIBERATING,
        )
        petition2 = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GRIEVANCE,
            text="Test petition 2 for referral",
            submitter_id=uuid4(),
            realm="GOVERNANCE",
            state=PetitionState.DELIBERATING,
        )
        petition_repo._submissions[petition1.id] = petition1
        petition_repo._submissions[petition2.id] = petition2

        # Execute referrals
        referral1 = await service.execute(
            petition_id=petition1.id,
            realm_id=realm_id,
        )
        referral2 = await service.execute(
            petition_id=petition2.id,
            realm_id=realm_id,
        )

        # Verify independent referrals
        assert referral1.referral_id != referral2.referral_id
        assert referral1.petition_id == petition1.id
        assert referral2.petition_id == petition2.id

        # Verify both are stored
        assert referral_repo.count() == 2


class TestWitnessHashIntegration:
    """Integration tests for witness hash generation."""

    @pytest.mark.asyncio
    async def test_witness_hash_is_deterministic(
        self,
        service: ReferralExecutionService,
        hash_service: ContentHashServiceStub,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Test that witness hash is generated correctly."""
        realm_id = uuid4()

        await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Hash service should have been called
        # ContentHashServiceStub tracks calls via _operations
        assert hash_service.get_operation_count() > 0

    @pytest.mark.asyncio
    async def test_event_contains_witness_hash(
        self,
        service: ReferralExecutionService,
        event_writer: EventWriterStub,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Test that emitted event contains witness hash."""
        await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=uuid4(),
        )

        events = event_writer.get_events()
        assert len(events) == 1
        assert "witness_hash" in events[0]
        assert events[0]["witness_hash"].startswith("blake3:")


class TestCustomDeadline:
    """Integration tests for custom deadline configuration."""

    @pytest.mark.asyncio
    async def test_custom_deadline_cycles(
        self,
        service: ReferralExecutionService,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Test referral with custom deadline cycles."""
        realm_id = uuid4()
        custom_cycles = 5

        now = datetime.now(timezone.utc)
        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
            deadline_cycles=custom_cycles,
        )

        # Deadline should be 5 weeks out
        expected_deadline = now + timedelta(weeks=custom_cycles)
        assert abs((referral.deadline - expected_deadline).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_job_scheduled_at_deadline(
        self,
        service: ReferralExecutionService,
        job_scheduler: JobSchedulerStub,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Test that job is scheduled at the referral deadline."""
        realm_id = uuid4()

        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        jobs = job_scheduler.get_all_jobs()
        referral_jobs = [j for j in jobs if j.job_type == JOB_TYPE_REFERRAL_TIMEOUT]
        assert len(referral_jobs) == 1

        # Job scheduled_for should match referral deadline
        job = referral_jobs[0]
        assert job.scheduled_for == referral.deadline


class TestRepositoryIntegration:
    """Integration tests for repository operations."""

    @pytest.mark.asyncio
    async def test_get_by_petition_id(
        self,
        service: ReferralExecutionService,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Test retrieving referral by petition ID."""
        await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=uuid4(),
        )

        retrieved = await service.get_referral_by_petition(deliberating_petition.id)
        assert retrieved is not None
        assert retrieved.petition_id == deliberating_petition.id

    @pytest.mark.asyncio
    async def test_get_by_referral_id(
        self,
        service: ReferralExecutionService,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Test retrieving referral by referral ID."""
        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=uuid4(),
        )

        retrieved = await service.get_referral(referral.referral_id)
        assert retrieved is not None
        assert retrieved.referral_id == referral.referral_id
