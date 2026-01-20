"""Unit tests for ReferralExecutionService.

Story: 4.2 - Referral Execution Service
FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
FR-4.2: System SHALL assign referral deadline (3 cycles default)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.referral_execution_service import (
    JOB_TYPE_REFERRAL_TIMEOUT,
    ReferralExecutionService,
)
from src.domain.errors.referral import (
    PetitionNotReferrableError,
    ReferralJobSchedulingError,
    ReferralWitnessHashError,
)
from src.domain.models.petition_submission import PetitionState, PetitionSubmission
from src.domain.models.referral import (
    REFERRAL_DEFAULT_DEADLINE_CYCLES,
    ReferralStatus,
)
from src.infrastructure.stubs.referral_repository_stub import ReferralRepositoryStub


@pytest.fixture
def referral_repo() -> ReferralRepositoryStub:
    """Create a fresh referral repository stub."""
    return ReferralRepositoryStub()


@pytest.fixture
def petition_repo() -> AsyncMock:
    """Create a mock petition repository."""
    return AsyncMock()


@pytest.fixture
def event_writer() -> AsyncMock:
    """Create a mock event writer."""
    mock = AsyncMock()
    mock.write = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def job_scheduler() -> AsyncMock:
    """Create a mock job scheduler."""
    mock = AsyncMock()
    mock.schedule = AsyncMock(return_value=uuid4())
    return mock


@pytest.fixture
def hash_service() -> MagicMock:
    """Create a mock hash service."""
    mock = MagicMock()
    # hash_text is synchronous and returns bytes
    mock.hash_text = MagicMock(return_value=b"\xab\xcd\xef" * 10 + b"\x12\x34")
    return mock


@pytest.fixture
def deliberating_petition() -> PetitionSubmission:
    """Create a petition in DELIBERATING state."""
    from src.domain.models.petition_submission import PetitionType

    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for referral",
        submitter_id=uuid4(),
        realm="TECH",
        state=PetitionState.DELIBERATING,
    )


@pytest.fixture
def received_petition() -> PetitionSubmission:
    """Create a petition in RECEIVED state (not ready for referral)."""
    from src.domain.models.petition_submission import PetitionType

    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition in received state",
        submitter_id=uuid4(),
        realm="TECH",
        state=PetitionState.RECEIVED,
    )


@pytest.fixture
def service(
    referral_repo: ReferralRepositoryStub,
    petition_repo: AsyncMock,
    event_writer: AsyncMock,
    job_scheduler: AsyncMock,
    hash_service: AsyncMock,
) -> ReferralExecutionService:
    """Create a ReferralExecutionService with all dependencies."""
    return ReferralExecutionService(
        referral_repo=referral_repo,
        petition_repo=petition_repo,
        event_writer=event_writer,
        job_scheduler=job_scheduler,
        hash_service=hash_service,
    )


class TestExecuteHappyPath:
    """Tests for successful referral execution."""

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        service: ReferralExecutionService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: AsyncMock,
        event_writer: AsyncMock,
        job_scheduler: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Successfully execute a referral."""
        petition_repo.get.return_value = deliberating_petition
        realm_id = uuid4()

        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Verify referral was created
        assert referral.petition_id == deliberating_petition.id
        assert referral.realm_id == realm_id
        assert referral.status == ReferralStatus.PENDING
        assert referral.assigned_knight_id is None

        # Verify referral was persisted
        stored = await referral_repo.get_by_id(referral.referral_id)
        assert stored is not None
        assert stored.referral_id == referral.referral_id

        # Verify petition state was updated
        petition_repo.update_state.assert_called_once()
        call_args = petition_repo.update_state.call_args
        assert call_args.kwargs["submission_id"] == deliberating_petition.id
        assert call_args.kwargs["new_state"] == PetitionState.REFERRED

        # Verify event was emitted
        event_writer.write.assert_called_once()

        # Verify job was scheduled
        job_scheduler.schedule.assert_called_once()
        call_args = job_scheduler.schedule.call_args
        assert call_args.kwargs["job_type"] == JOB_TYPE_REFERRAL_TIMEOUT

    @pytest.mark.asyncio
    async def test_execute_with_default_deadline(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Referral should use default deadline of 3 cycles."""
        petition_repo.get.return_value = deliberating_petition
        realm_id = uuid4()

        now = datetime.now(timezone.utc)
        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Deadline should be approximately 3 weeks from now
        expected_deadline = now + timedelta(weeks=REFERRAL_DEFAULT_DEADLINE_CYCLES)
        # Allow 1 second tolerance for test execution time
        assert abs((referral.deadline - expected_deadline).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_execute_with_custom_deadline(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Referral should use custom deadline cycles when specified."""
        petition_repo.get.return_value = deliberating_petition
        realm_id = uuid4()

        now = datetime.now(timezone.utc)
        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
            deadline_cycles=5,
        )

        # Deadline should be approximately 5 weeks from now
        expected_deadline = now + timedelta(weeks=5)
        assert abs((referral.deadline - expected_deadline).total_seconds()) < 1


class TestIdempotency:
    """Tests for idempotency behavior."""

    @pytest.mark.asyncio
    async def test_execute_returns_existing_referral(
        self,
        service: ReferralExecutionService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: AsyncMock,
        event_writer: AsyncMock,
        job_scheduler: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Should return existing referral if already created."""
        petition_repo.get.return_value = deliberating_petition
        realm_id = uuid4()

        # First execution
        referral1 = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Reset mocks
        event_writer.write.reset_mock()
        job_scheduler.schedule.reset_mock()

        # Second execution - should return existing
        referral2 = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Should return same referral
        assert referral2.referral_id == referral1.referral_id

        # Should not emit another event or schedule another job
        event_writer.write.assert_not_called()
        job_scheduler.schedule.assert_not_called()


class TestStateValidation:
    """Tests for petition state validation."""

    @pytest.mark.asyncio
    async def test_execute_fails_for_received_petition(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
        received_petition: PetitionSubmission,
    ) -> None:
        """Should reject referral for petition not in DELIBERATING state."""
        petition_repo.get.return_value = received_petition

        with pytest.raises(PetitionNotReferrableError) as exc_info:
            await service.execute(
                petition_id=received_petition.id,
                realm_id=uuid4(),
            )

        assert exc_info.value.petition_id == received_petition.id
        assert exc_info.value.current_state == PetitionState.RECEIVED.value

    @pytest.mark.asyncio
    async def test_execute_fails_for_acknowledged_petition(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
    ) -> None:
        """Should reject referral for already acknowledged petition."""
        from src.domain.models.petition_submission import PetitionType

        acknowledged_petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test acknowledged petition",
            submitter_id=uuid4(),
            realm="TECH",
            state=PetitionState.ACKNOWLEDGED,
        )
        petition_repo.get.return_value = acknowledged_petition

        with pytest.raises(PetitionNotReferrableError) as exc_info:
            await service.execute(
                petition_id=acknowledged_petition.id,
                realm_id=uuid4(),
            )

        assert exc_info.value.current_state == PetitionState.ACKNOWLEDGED.value

    @pytest.mark.asyncio
    async def test_execute_fails_for_nonexistent_petition(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
    ) -> None:
        """Should raise PetitionNotFoundError for nonexistent petition."""
        from src.domain.errors.acknowledgment import PetitionNotFoundError

        petition_repo.get.return_value = None
        petition_id = uuid4()

        with pytest.raises(PetitionNotFoundError) as exc_info:
            await service.execute(
                petition_id=petition_id,
                realm_id=uuid4(),
            )

        assert exc_info.value.petition_id == petition_id


class TestWitnessHashGeneration:
    """Tests for witness hash generation (CT-12)."""

    @pytest.mark.asyncio
    async def test_execute_generates_witness_hash(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
        hash_service: MagicMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Should generate witness hash for referral."""
        petition_repo.get.return_value = deliberating_petition
        hash_service.hash_text.return_value = b"\xab\xcd" * 16  # 32 bytes

        await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=uuid4(),
        )

        # Hash service should have been called
        hash_service.hash_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_fails_on_hash_error(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
        hash_service: MagicMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Should raise ReferralWitnessHashError on hash generation failure."""
        petition_repo.get.return_value = deliberating_petition
        hash_service.hash_text.side_effect = RuntimeError("Hash service error")

        with pytest.raises(ReferralWitnessHashError) as exc_info:
            await service.execute(
                petition_id=deliberating_petition.id,
                realm_id=uuid4(),
            )

        assert exc_info.value.petition_id == deliberating_petition.id
        assert "Hash service error" in exc_info.value.reason


class TestJobScheduling:
    """Tests for deadline job scheduling (NFR-3.4, NFR-4.4)."""

    @pytest.mark.asyncio
    async def test_execute_schedules_timeout_job(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
        job_scheduler: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Should schedule referral timeout job."""
        petition_repo.get.return_value = deliberating_petition
        realm_id = uuid4()

        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Verify job was scheduled
        job_scheduler.schedule.assert_called_once()
        call_args = job_scheduler.schedule.call_args

        assert call_args.kwargs["job_type"] == JOB_TYPE_REFERRAL_TIMEOUT
        assert call_args.kwargs["run_at"] == referral.deadline

        # Verify payload contents
        payload = call_args.kwargs["payload"]
        assert payload["referral_id"] == str(referral.referral_id)
        assert payload["petition_id"] == str(deliberating_petition.id)
        assert payload["realm_id"] == str(realm_id)

    @pytest.mark.asyncio
    async def test_execute_fails_on_job_scheduling_error(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
        job_scheduler: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Should raise ReferralJobSchedulingError on job scheduling failure."""
        petition_repo.get.return_value = deliberating_petition
        job_scheduler.schedule.side_effect = RuntimeError("Scheduler unavailable")

        with pytest.raises(ReferralJobSchedulingError) as exc_info:
            await service.execute(
                petition_id=deliberating_petition.id,
                realm_id=uuid4(),
            )

        assert "Scheduler unavailable" in exc_info.value.reason


class TestEventEmission:
    """Tests for event emission (CT-12)."""

    @pytest.mark.asyncio
    async def test_execute_emits_petition_referred_event(
        self,
        service: ReferralExecutionService,
        petition_repo: AsyncMock,
        event_writer: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Should emit PetitionReferred event."""
        petition_repo.get.return_value = deliberating_petition
        realm_id = uuid4()

        referral = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=realm_id,
        )

        # Verify event was emitted
        event_writer.write.assert_called_once()
        event_data = event_writer.write.call_args[0][0]

        assert event_data["event_type"] == "petition.referral.created"
        assert event_data["petition_id"] == str(deliberating_petition.id)
        assert event_data["referral_id"] == str(referral.referral_id)
        assert event_data["realm_id"] == str(realm_id)
        assert "witness_hash" in event_data


class TestGetMethods:
    """Tests for retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_referral_returns_existing(
        self,
        service: ReferralExecutionService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Should retrieve existing referral by ID."""
        petition_repo.get.return_value = deliberating_petition

        # Create referral
        created = await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=uuid4(),
        )

        # Retrieve it
        retrieved = await service.get_referral(created.referral_id)

        assert retrieved is not None
        assert retrieved.referral_id == created.referral_id

    @pytest.mark.asyncio
    async def test_get_referral_returns_none_for_nonexistent(
        self,
        service: ReferralExecutionService,
    ) -> None:
        """Should return None for nonexistent referral ID."""
        result = await service.get_referral(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_referral_by_petition_returns_existing(
        self,
        service: ReferralExecutionService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: AsyncMock,
        deliberating_petition: PetitionSubmission,
    ) -> None:
        """Should retrieve referral by petition ID."""
        petition_repo.get.return_value = deliberating_petition

        # Create referral
        await service.execute(
            petition_id=deliberating_petition.id,
            realm_id=uuid4(),
        )

        # Retrieve by petition
        retrieved = await service.get_referral_by_petition(deliberating_petition.id)

        assert retrieved is not None
        assert retrieved.petition_id == deliberating_petition.id

    @pytest.mark.asyncio
    async def test_get_referral_by_petition_returns_none_for_nonexistent(
        self,
        service: ReferralExecutionService,
    ) -> None:
        """Should return None for petition without referral."""
        result = await service.get_referral_by_petition(uuid4())
        assert result is None
