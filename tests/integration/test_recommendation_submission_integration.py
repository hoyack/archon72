"""Integration tests for RecommendationSubmissionService.

Story: 4.4 - Knight Recommendation Submission
Tests the full recommendation submission flow with stubs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from src.application.services.recommendation_submission_service import (
    MIN_RATIONALE_LENGTH,
    RecommendationSubmissionService,
)
from src.domain.errors.recommendation import (
    RationaleRequiredError,
    RecommendationAlreadySubmittedError,
    ReferralNotInReviewError,
    UnauthorizedRecommendationError,
)
from src.domain.errors.referral import ReferralNotFoundError
from src.domain.models.referral import Referral, ReferralRecommendation, ReferralStatus
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


class HashServiceStub:
    """Simple hash service stub for testing with compute_hash method."""

    def __init__(self) -> None:
        self._compute_calls: list[str] = []
        self._counter: int = 0

    async def compute_hash(self, content: str) -> str:
        """Compute a deterministic hash for content."""
        self._compute_calls.append(content)
        self._counter += 1
        # Return deterministic hash based on content
        import hashlib

        hash_bytes = hashlib.sha256(content.encode()).hexdigest()[:32]
        return f"blake3:{hash_bytes}"

    def get_compute_calls(self) -> list[str]:
        """Get all content that was hashed."""
        return self._compute_calls.copy()

    def clear(self) -> None:
        """Clear all calls."""
        self._compute_calls.clear()
        self._counter = 0


class JobSchedulerStub:
    """Simple job scheduler stub for testing with string-based job IDs."""

    def __init__(self) -> None:
        self._cancelled_jobs: list[str] = []

    async def cancel(self, job_id: str) -> bool:
        """Cancel a job by ID."""
        self._cancelled_jobs.append(job_id)
        return True

    def get_cancelled_jobs(self) -> list[str]:
        """Get list of cancelled job IDs."""
        return self._cancelled_jobs.copy()

    def clear(self) -> None:
        """Clear all cancelled jobs."""
        self._cancelled_jobs.clear()


@pytest.fixture
def referral_repo() -> ReferralRepositoryStub:
    """Create fresh referral repository stub."""
    return ReferralRepositoryStub()


@pytest.fixture
def event_writer() -> EventWriterStub:
    """Create fresh event writer stub."""
    return EventWriterStub()


@pytest.fixture
def hash_service() -> HashServiceStub:
    """Create fresh hash service stub."""
    return HashServiceStub()


@pytest.fixture
def job_scheduler() -> JobSchedulerStub:
    """Create fresh job scheduler stub."""
    return JobSchedulerStub()


@pytest.fixture
def service(
    referral_repo: ReferralRepositoryStub,
    event_writer: EventWriterStub,
    hash_service: HashServiceStub,
    job_scheduler: JobSchedulerStub,
) -> RecommendationSubmissionService:
    """Create RecommendationSubmissionService with all stubs."""
    return RecommendationSubmissionService(
        referral_repo=referral_repo,
        event_writer=event_writer,
        hash_service=hash_service,
        job_scheduler=job_scheduler,
        acknowledgment_service=None,  # No routing in integration tests
    )


@pytest.fixture
def knight_id() -> uuid4:
    """Create a Knight UUID."""
    return uuid4()


@pytest.fixture
def realm_id() -> uuid4:
    """Create a realm UUID."""
    return uuid4()


@pytest.fixture
def valid_rationale() -> str:
    """Create a valid rationale string."""
    return "This petition addresses a legitimate governance concern and warrants acknowledgment."


@pytest.fixture
def in_review_referral(
    referral_repo: ReferralRepositoryStub,
    knight_id: uuid4,
    realm_id: uuid4,
) -> Referral:
    """Create and store an IN_REVIEW referral."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(weeks=3)

    # Create through state transitions
    pending = Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=realm_id,
        deadline=deadline,
        created_at=now,
        status=ReferralStatus.PENDING,
    )
    assigned = pending.with_assignment(knight_id)
    in_review = assigned.with_in_review()

    # Store in repository
    referral_repo._referrals[in_review.referral_id] = in_review
    referral_repo._by_petition[in_review.petition_id] = in_review.referral_id

    return in_review


@pytest.fixture
def assigned_referral(
    referral_repo: ReferralRepositoryStub,
    knight_id: uuid4,
    realm_id: uuid4,
) -> Referral:
    """Create and store an ASSIGNED referral."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(weeks=3)

    pending = Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=realm_id,
        deadline=deadline,
        created_at=now,
        status=ReferralStatus.PENDING,
    )
    assigned = pending.with_assignment(knight_id)

    # Store in repository
    referral_repo._referrals[assigned.referral_id] = assigned
    referral_repo._by_petition[assigned.petition_id] = assigned.referral_id

    return assigned


class TestFullSubmissionFlow:
    """Integration tests for the full recommendation submission flow."""

    @pytest.mark.asyncio
    async def test_submit_acknowledge_recommendation(
        self,
        service: RecommendationSubmissionService,
        referral_repo: ReferralRepositoryStub,
        event_writer: EventWriterStub,
        hash_service: HashServiceStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test successful ACKNOWLEDGE recommendation submission."""
        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        # Verify result
        assert result.status == ReferralStatus.COMPLETED
        assert result.recommendation == ReferralRecommendation.ACKNOWLEDGE
        assert result.rationale == valid_rationale
        assert result.completed_at is not None

        # Verify repository was updated
        stored = await referral_repo.get_by_id(in_review_referral.referral_id)
        assert stored is not None
        assert stored.status == ReferralStatus.COMPLETED
        assert stored.recommendation == ReferralRecommendation.ACKNOWLEDGE

        # Verify event was emitted
        events = event_writer.get_events()
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "petition.referral.completed"
        assert event["recommendation"] == "acknowledge"

    @pytest.mark.asyncio
    async def test_submit_escalate_recommendation(
        self,
        service: RecommendationSubmissionService,
        referral_repo: ReferralRepositoryStub,
        event_writer: EventWriterStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test successful ESCALATE recommendation submission."""
        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ESCALATE,
            rationale=valid_rationale,
        )

        # Verify result
        assert result.status == ReferralStatus.COMPLETED
        assert result.recommendation == ReferralRecommendation.ESCALATE

        # Verify repository was updated
        stored = await referral_repo.get_by_id(in_review_referral.referral_id)
        assert stored is not None
        assert stored.recommendation == ReferralRecommendation.ESCALATE

        # Verify event
        events = event_writer.get_events()
        assert len(events) == 1
        assert events[0]["recommendation"] == "escalate"


class TestRationaleValidationFlow:
    """Integration tests for rationale validation."""

    @pytest.mark.asyncio
    async def test_reject_empty_rationale(
        self,
        service: RecommendationSubmissionService,
        referral_repo: ReferralRepositoryStub,
        event_writer: EventWriterStub,
        in_review_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Test that empty rationale is rejected."""
        with pytest.raises(RationaleRequiredError) as exc_info:
            await service.submit(
                referral_id=in_review_referral.referral_id,
                requester_id=knight_id,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale="",
            )

        assert exc_info.value.provided_length == 0

        # Verify referral was not modified
        stored = await referral_repo.get_by_id(in_review_referral.referral_id)
        assert stored.status == ReferralStatus.IN_REVIEW

        # Verify no event was emitted
        events = event_writer.get_events()
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_reject_short_rationale(
        self,
        service: RecommendationSubmissionService,
        in_review_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Test that short rationale is rejected."""
        short_rationale = "too short"  # 9 characters

        with pytest.raises(RationaleRequiredError) as exc_info:
            await service.submit(
                referral_id=in_review_referral.referral_id,
                requester_id=knight_id,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=short_rationale,
            )

        assert exc_info.value.provided_length == len(short_rationale)

    @pytest.mark.asyncio
    async def test_accept_minimum_rationale(
        self,
        service: RecommendationSubmissionService,
        in_review_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Test that minimum length rationale is accepted."""
        min_rationale = "a" * MIN_RATIONALE_LENGTH

        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=min_rationale,
        )

        assert result.rationale == min_rationale


class TestAuthorizationFlow:
    """Integration tests for authorization enforcement."""

    @pytest.mark.asyncio
    async def test_authorized_knight_can_submit(
        self,
        service: RecommendationSubmissionService,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that the assigned Knight can submit recommendation."""
        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        assert result.status == ReferralStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_unauthorized_knight_cannot_submit(
        self,
        service: RecommendationSubmissionService,
        referral_repo: ReferralRepositoryStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that a different Knight cannot submit."""
        wrong_knight = uuid4()

        with pytest.raises(UnauthorizedRecommendationError) as exc_info:
            await service.submit(
                referral_id=in_review_referral.referral_id,
                requester_id=wrong_knight,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        assert exc_info.value.requester_id == wrong_knight
        assert exc_info.value.assigned_knight_id == knight_id

        # Verify referral was not modified
        stored = await referral_repo.get_by_id(in_review_referral.referral_id)
        assert stored.status == ReferralStatus.IN_REVIEW


class TestReferralStateRestrictions:
    """Integration tests for referral state restrictions."""

    @pytest.mark.asyncio
    async def test_cannot_submit_for_assigned_referral(
        self,
        service: RecommendationSubmissionService,
        assigned_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that ASSIGNED referrals cannot have recommendations submitted."""
        with pytest.raises(ReferralNotInReviewError) as exc_info:
            await service.submit(
                referral_id=assigned_referral.referral_id,
                requester_id=knight_id,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        assert exc_info.value.current_status == ReferralStatus.ASSIGNED.value

    @pytest.mark.asyncio
    async def test_cannot_submit_twice(
        self,
        service: RecommendationSubmissionService,
        referral_repo: ReferralRepositoryStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that recommendation cannot be submitted twice."""
        # First submission
        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        # Second submission should fail
        with pytest.raises(RecommendationAlreadySubmittedError) as exc_info:
            await service.submit(
                referral_id=in_review_referral.referral_id,
                requester_id=knight_id,
                recommendation=ReferralRecommendation.ESCALATE,
                rationale="Different rationale",
            )

        assert exc_info.value.existing_recommendation == "acknowledge"


class TestNotFoundScenarios:
    """Integration tests for not found scenarios."""

    @pytest.mark.asyncio
    async def test_referral_not_found(
        self,
        service: RecommendationSubmissionService,
        valid_rationale: str,
    ) -> None:
        """Test error when referral doesn't exist."""
        nonexistent_id = uuid4()

        with pytest.raises(ReferralNotFoundError) as exc_info:
            await service.submit(
                referral_id=nonexistent_id,
                requester_id=uuid4(),
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        assert exc_info.value.referral_id == nonexistent_id


class TestWitnessing:
    """Integration tests for witness hash generation."""

    @pytest.mark.asyncio
    async def test_witness_hash_in_event(
        self,
        service: RecommendationSubmissionService,
        event_writer: EventWriterStub,
        hash_service: HashServiceStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that witness hash is included in the event."""
        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        events = event_writer.get_events()
        assert len(events) == 1
        assert "witness_hash" in events[0]
        assert events[0]["witness_hash"].startswith("blake3:")

    @pytest.mark.asyncio
    async def test_hash_computed_with_all_fields(
        self,
        service: RecommendationSubmissionService,
        hash_service: HashServiceStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that hash includes all required fields."""
        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        # Verify hash was computed
        calls = hash_service.get_compute_calls()
        assert len(calls) == 1
        content = calls[0]

        # Verify all required fields in witness content
        assert f"referral_id:{in_review_referral.referral_id}" in content
        assert f"petition_id:{in_review_referral.petition_id}" in content
        assert f"knight_id:{knight_id}" in content
        assert "recommendation:acknowledge" in content
        assert f"rationale:{valid_rationale}" in content


class TestDeadlineJobCancellation:
    """Integration tests for deadline job cancellation."""

    @pytest.mark.asyncio
    async def test_deadline_job_cancelled_on_submit(
        self,
        service: RecommendationSubmissionService,
        job_scheduler: JobSchedulerStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that deadline job is cancelled after submission."""
        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        # Verify cancel was called
        cancelled = job_scheduler.get_cancelled_jobs()
        assert len(cancelled) == 1
        assert cancelled[0] == f"referral-deadline-{in_review_referral.referral_id}"


class TestEventEmission:
    """Integration tests for event emission."""

    @pytest.mark.asyncio
    async def test_event_contains_all_fields(
        self,
        service: RecommendationSubmissionService,
        event_writer: EventWriterStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that emitted event contains all required fields."""
        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        events = event_writer.get_events()
        assert len(events) == 1
        event = events[0]

        # Verify all required fields
        assert event["event_type"] == "petition.referral.completed"
        assert event["referral_id"] == str(in_review_referral.referral_id)
        assert event["petition_id"] == str(in_review_referral.petition_id)
        assert event["knight_id"] == str(knight_id)
        assert event["recommendation"] == "acknowledge"
        assert event["rationale"] == valid_rationale
        assert "completed_at" in event
        assert "witness_hash" in event
        assert event["schema_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_event_completed_at_is_recent(
        self,
        service: RecommendationSubmissionService,
        event_writer: EventWriterStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that completed_at is set to a recent time."""
        before = datetime.now(timezone.utc)

        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        after = datetime.now(timezone.utc)

        events = event_writer.get_events()
        completed_at = datetime.fromisoformat(events[0]["completed_at"])

        assert before <= completed_at <= after


class TestIdempotency:
    """Integration tests for idempotency behavior."""

    @pytest.mark.asyncio
    async def test_second_submit_fails_gracefully(
        self,
        service: RecommendationSubmissionService,
        event_writer: EventWriterStub,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Test that second submission returns clear error."""
        # First submission succeeds
        first_result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        assert first_result.status == ReferralStatus.COMPLETED

        # Second submission fails with clear error
        with pytest.raises(RecommendationAlreadySubmittedError) as exc_info:
            await service.submit(
                referral_id=in_review_referral.referral_id,
                requester_id=knight_id,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        # Verify error contains useful info
        assert exc_info.value.referral_id == in_review_referral.referral_id
        assert exc_info.value.existing_recommendation == "acknowledge"

        # Verify only one event was emitted (from first submission)
        events = event_writer.get_events()
        assert len(events) == 1
