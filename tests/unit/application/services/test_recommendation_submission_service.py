"""Unit tests for RecommendationSubmissionService.

Story: 4.4 - Knight Recommendation Submission
FR-4.6: Knight SHALL submit recommendation with mandatory rationale [P0]
NFR-5.2: Authorization: Only assigned Knight can submit recommendation
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
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


@pytest.fixture
def referral_repo() -> AsyncMock:
    """Create a mock referral repository."""
    return AsyncMock()


@pytest.fixture
def event_writer() -> AsyncMock:
    """Create a mock event writer."""
    return AsyncMock()


@pytest.fixture
def hash_service() -> AsyncMock:
    """Create a mock hash service."""
    mock = AsyncMock()
    mock.compute_hash.return_value = "blake3:testwitnesshash123"
    return mock


@pytest.fixture
def job_scheduler() -> AsyncMock:
    """Create a mock job scheduler."""
    return AsyncMock()


@pytest.fixture
def acknowledgment_service() -> AsyncMock:
    """Create a mock acknowledgment service."""
    return AsyncMock()


@pytest.fixture
def service(
    referral_repo: AsyncMock,
    event_writer: AsyncMock,
    hash_service: AsyncMock,
    job_scheduler: AsyncMock,
    acknowledgment_service: AsyncMock,
) -> RecommendationSubmissionService:
    """Create a RecommendationSubmissionService with all dependencies."""
    return RecommendationSubmissionService(
        referral_repo=referral_repo,
        event_writer=event_writer,
        hash_service=hash_service,
        job_scheduler=job_scheduler,
        acknowledgment_service=acknowledgment_service,
    )


@pytest.fixture
def knight_id() -> uuid4:
    """Create a Knight UUID."""
    return uuid4()


@pytest.fixture
def in_review_referral(knight_id: uuid4) -> Referral:
    """Create a referral in IN_REVIEW state."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(weeks=3)
    return Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        deadline=deadline,
        created_at=now,
        assigned_knight_id=knight_id,
        status=ReferralStatus.IN_REVIEW,
        extensions_granted=0,
    )


@pytest.fixture
def assigned_referral(knight_id: uuid4) -> Referral:
    """Create a referral in ASSIGNED state."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(weeks=3)
    return Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        deadline=deadline,
        created_at=now,
        assigned_knight_id=knight_id,
        status=ReferralStatus.ASSIGNED,
        extensions_granted=0,
    )


@pytest.fixture
def valid_rationale() -> str:
    """Create a valid rationale string."""
    return "This petition addresses a legitimate concern and warrants acknowledgment."


class TestSubmitHappyPath:
    """Tests for successful recommendation submission."""

    @pytest.mark.asyncio
    async def test_submit_acknowledge_success(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        event_writer: AsyncMock,
        hash_service: AsyncMock,
        job_scheduler: AsyncMock,
        acknowledgment_service: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Successfully submit ACKNOWLEDGE recommendation."""
        referral_repo.get_by_id.return_value = in_review_referral

        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        # Verify referral was updated
        assert result.status == ReferralStatus.COMPLETED
        assert result.recommendation == ReferralRecommendation.ACKNOWLEDGE
        assert result.rationale == valid_rationale
        assert result.completed_at is not None

        # Verify referral was updated
        referral_repo.update.assert_called_once()
        updated_referral = referral_repo.update.call_args[0][0]
        assert updated_referral.status == ReferralStatus.COMPLETED

        # Verify event was emitted
        event_writer.write.assert_called_once()
        event_data = event_writer.write.call_args[0][0]
        assert event_data["event_type"] == "petition.referral.completed"
        assert event_data["recommendation"] == "acknowledge"

        # Verify witness hash was generated
        hash_service.compute_hash.assert_called_once()

        # Verify deadline job was cancelled
        job_scheduler.cancel.assert_called_once()
        job_id = job_scheduler.cancel.call_args[0][0]
        assert f"referral-deadline-{in_review_referral.referral_id}" == job_id

        # Verify acknowledgment routing was called
        acknowledgment_service.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_escalate_success(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        event_writer: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Successfully submit ESCALATE recommendation."""
        referral_repo.get_by_id.return_value = in_review_referral

        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ESCALATE,
            rationale=valid_rationale,
        )

        # Verify referral was updated
        assert result.status == ReferralStatus.COMPLETED
        assert result.recommendation == ReferralRecommendation.ESCALATE
        assert result.rationale == valid_rationale

        # Verify event was emitted
        event_writer.write.assert_called_once()
        event_data = event_writer.write.call_args[0][0]
        assert event_data["recommendation"] == "escalate"


class TestRationaleValidation:
    """Tests for rationale validation (FR-4.6)."""

    @pytest.mark.asyncio
    async def test_submit_fails_empty_rationale(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
    ) -> None:
        """Should reject empty rationale."""
        with pytest.raises(RationaleRequiredError) as exc_info:
            await service.submit(
                referral_id=uuid4(),
                requester_id=uuid4(),
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale="",
            )

        assert exc_info.value.provided_length == 0
        assert exc_info.value.min_length == MIN_RATIONALE_LENGTH

        # Referral should not have been queried
        referral_repo.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_fails_whitespace_only_rationale(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
    ) -> None:
        """Should reject whitespace-only rationale."""
        with pytest.raises(RationaleRequiredError) as exc_info:
            await service.submit(
                referral_id=uuid4(),
                requester_id=uuid4(),
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale="   \t\n   ",
            )

        assert exc_info.value.provided_length == 0

    @pytest.mark.asyncio
    async def test_submit_fails_rationale_too_short(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
    ) -> None:
        """Should reject rationale shorter than minimum length."""
        short_rationale = "too short"  # 9 characters
        assert len(short_rationale) < MIN_RATIONALE_LENGTH

        with pytest.raises(RationaleRequiredError) as exc_info:
            await service.submit(
                referral_id=uuid4(),
                requester_id=uuid4(),
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=short_rationale,
            )

        assert exc_info.value.provided_length == len(short_rationale)

    @pytest.mark.asyncio
    async def test_submit_accepts_minimum_rationale(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Should accept rationale at exactly minimum length."""
        min_rationale = "a" * MIN_RATIONALE_LENGTH  # Exactly 10 characters
        referral_repo.get_by_id.return_value = in_review_referral

        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=min_rationale,
        )

        assert result.rationale == min_rationale

    @pytest.mark.asyncio
    async def test_submit_trims_rationale_whitespace(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Should trim leading/trailing whitespace from rationale."""
        padded_rationale = "  Valid rationale text here  "
        referral_repo.get_by_id.return_value = in_review_referral

        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=padded_rationale,
        )

        assert result.rationale == padded_rationale.strip()


class TestAuthorizationEnforcement:
    """Tests for authorization enforcement (NFR-5.2)."""

    @pytest.mark.asyncio
    async def test_submit_fails_wrong_knight(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should reject when requester is not the assigned Knight."""
        referral_repo.get_by_id.return_value = in_review_referral
        wrong_knight_id = uuid4()

        with pytest.raises(UnauthorizedRecommendationError) as exc_info:
            await service.submit(
                referral_id=in_review_referral.referral_id,
                requester_id=wrong_knight_id,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        assert exc_info.value.referral_id == in_review_referral.referral_id
        assert exc_info.value.requester_id == wrong_knight_id
        assert exc_info.value.assigned_knight_id == knight_id

    @pytest.mark.asyncio
    async def test_submit_fails_no_assigned_knight(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        valid_rationale: str,
    ) -> None:
        """Should reject when referral has no assigned Knight."""
        now = datetime.now(timezone.utc)
        # Create a mock referral in IN_REVIEW state but with no knight
        mock_referral = AsyncMock()
        mock_referral.referral_id = uuid4()
        mock_referral.status = ReferralStatus.IN_REVIEW
        mock_referral.assigned_knight_id = None

        referral_repo.get_by_id.return_value = mock_referral
        requester_id = uuid4()

        with pytest.raises(UnauthorizedRecommendationError) as exc_info:
            await service.submit(
                referral_id=mock_referral.referral_id,
                requester_id=requester_id,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        assert exc_info.value.referral_id == mock_referral.referral_id


class TestReferralStateValidation:
    """Tests for referral state validation."""

    @pytest.mark.asyncio
    async def test_submit_fails_assigned_status(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        assigned_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should reject when referral is in ASSIGNED state."""
        referral_repo.get_by_id.return_value = assigned_referral

        with pytest.raises(ReferralNotInReviewError) as exc_info:
            await service.submit(
                referral_id=assigned_referral.referral_id,
                requester_id=knight_id,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        assert exc_info.value.referral_id == assigned_referral.referral_id
        assert exc_info.value.current_status == ReferralStatus.ASSIGNED.value

    @pytest.mark.asyncio
    async def test_submit_fails_completed_status(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should reject when referral is already COMPLETED."""
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(weeks=3)

        completed_referral = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=deadline,
            created_at=now,
            assigned_knight_id=knight_id,
            status=ReferralStatus.COMPLETED,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale="Existing rationale",
            completed_at=now,
        )

        referral_repo.get_by_id.return_value = completed_referral

        with pytest.raises(RecommendationAlreadySubmittedError) as exc_info:
            await service.submit(
                referral_id=completed_referral.referral_id,
                requester_id=knight_id,
                recommendation=ReferralRecommendation.ESCALATE,
                rationale=valid_rationale,
            )

        assert exc_info.value.referral_id == completed_referral.referral_id
        assert exc_info.value.existing_recommendation == "acknowledge"

    @pytest.mark.asyncio
    async def test_submit_fails_expired_status(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        valid_rationale: str,
    ) -> None:
        """Should reject when referral is EXPIRED."""
        now = datetime.now(timezone.utc)
        deadline = now - timedelta(days=1)

        expired_referral = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=deadline,
            created_at=now - timedelta(weeks=4),
            status=ReferralStatus.EXPIRED,
            completed_at=now,
        )

        referral_repo.get_by_id.return_value = expired_referral

        with pytest.raises(ReferralNotInReviewError) as exc_info:
            await service.submit(
                referral_id=expired_referral.referral_id,
                requester_id=uuid4(),
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        assert exc_info.value.current_status == ReferralStatus.EXPIRED.value


class TestNotFoundErrors:
    """Tests for not found error handling."""

    @pytest.mark.asyncio
    async def test_submit_fails_referral_not_found(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        valid_rationale: str,
    ) -> None:
        """Should raise ReferralNotFoundError when referral doesn't exist."""
        referral_repo.get_by_id.return_value = None
        referral_id = uuid4()

        with pytest.raises(ReferralNotFoundError) as exc_info:
            await service.submit(
                referral_id=referral_id,
                requester_id=uuid4(),
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=valid_rationale,
            )

        assert exc_info.value.referral_id == referral_id


class TestWitnessing:
    """Tests for witness hash generation (CT-12)."""

    @pytest.mark.asyncio
    async def test_submit_generates_witness_hash(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        hash_service: AsyncMock,
        event_writer: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should generate witness hash for the recommendation."""
        referral_repo.get_by_id.return_value = in_review_referral

        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        # Verify hash was computed
        hash_service.compute_hash.assert_called_once()
        witness_content = hash_service.compute_hash.call_args[0][0]

        # Verify content includes all required fields
        assert f"referral_id:{in_review_referral.referral_id}" in witness_content
        assert f"petition_id:{in_review_referral.petition_id}" in witness_content
        assert f"knight_id:{knight_id}" in witness_content
        assert "recommendation:acknowledge" in witness_content
        assert f"rationale:{valid_rationale}" in witness_content
        assert "completed_at:" in witness_content
        assert "schema_version:" in witness_content

    @pytest.mark.asyncio
    async def test_submit_includes_witness_hash_in_event(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        hash_service: AsyncMock,
        event_writer: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should include witness hash in the emitted event."""
        referral_repo.get_by_id.return_value = in_review_referral

        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        # Verify event includes witness hash
        event_data = event_writer.write.call_args[0][0]
        assert event_data["witness_hash"] == "blake3:testwitnesshash123"


class TestDeadlineJobCancellation:
    """Tests for deadline job cancellation."""

    @pytest.mark.asyncio
    async def test_submit_cancels_deadline_job(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        job_scheduler: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should cancel the deadline job after submission."""
        referral_repo.get_by_id.return_value = in_review_referral

        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        job_scheduler.cancel.assert_called_once()
        job_id = job_scheduler.cancel.call_args[0][0]
        assert job_id == f"referral-deadline-{in_review_referral.referral_id}"

    @pytest.mark.asyncio
    async def test_submit_handles_job_cancellation_failure(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        job_scheduler: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should gracefully handle job cancellation failure."""
        referral_repo.get_by_id.return_value = in_review_referral
        job_scheduler.cancel.side_effect = Exception("Job not found")

        # Should not raise - job may have already executed
        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        assert result.status == ReferralStatus.COMPLETED


class TestRouting:
    """Tests for petition routing based on recommendation."""

    @pytest.mark.asyncio
    async def test_acknowledge_routes_to_acknowledgment_service(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        acknowledgment_service: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """ACKNOWLEDGE recommendation should route to acknowledgment service."""
        from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode

        referral_repo.get_by_id.return_value = in_review_referral

        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        acknowledgment_service.execute.assert_called_once()
        call_kwargs = acknowledgment_service.execute.call_args.kwargs
        assert call_kwargs["petition_id"] == in_review_referral.petition_id
        assert call_kwargs["reason_code"] == AcknowledgmentReasonCode.KNIGHT_REFERRAL
        assert call_kwargs["rationale"] == valid_rationale

    @pytest.mark.asyncio
    async def test_escalate_does_not_call_acknowledgment_service(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        acknowledgment_service: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """ESCALATE recommendation should not call acknowledgment service."""
        referral_repo.get_by_id.return_value = in_review_referral

        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ESCALATE,
            rationale=valid_rationale,
        )

        acknowledgment_service.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_without_acknowledgment_service(
        self,
        referral_repo: AsyncMock,
        event_writer: AsyncMock,
        hash_service: AsyncMock,
        job_scheduler: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should handle missing acknowledgment service gracefully."""
        service = RecommendationSubmissionService(
            referral_repo=referral_repo,
            event_writer=event_writer,
            hash_service=hash_service,
            job_scheduler=job_scheduler,
            acknowledgment_service=None,  # No service configured
        )
        referral_repo.get_by_id.return_value = in_review_referral

        # Should not raise
        result = await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        assert result.status == ReferralStatus.COMPLETED


class TestEventEmission:
    """Tests for ReferralCompletedEvent emission."""

    @pytest.mark.asyncio
    async def test_submit_emits_completed_event(
        self,
        service: RecommendationSubmissionService,
        referral_repo: AsyncMock,
        event_writer: AsyncMock,
        in_review_referral: Referral,
        knight_id: uuid4,
        valid_rationale: str,
    ) -> None:
        """Should emit ReferralCompletedEvent with correct data."""
        referral_repo.get_by_id.return_value = in_review_referral

        await service.submit(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale=valid_rationale,
        )

        event_writer.write.assert_called_once()
        event_data = event_writer.write.call_args[0][0]

        assert event_data["event_type"] == "petition.referral.completed"
        assert event_data["referral_id"] == str(in_review_referral.referral_id)
        assert event_data["petition_id"] == str(in_review_referral.petition_id)
        assert event_data["knight_id"] == str(knight_id)
        assert event_data["recommendation"] == "acknowledge"
        assert event_data["rationale"] == valid_rationale
        assert "completed_at" in event_data
        assert "witness_hash" in event_data
        assert event_data["schema_version"] == "1.0.0"
