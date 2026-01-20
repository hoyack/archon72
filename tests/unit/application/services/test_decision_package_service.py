"""Unit tests for DecisionPackageBuilderService.

Story: 4.3 - Knight Decision Package
FR-4.3: Knight SHALL receive decision package (petition + context) [P0]
NFR-5.2: Authorization: Only assigned Knight can access package
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.decision_package_service import (
    DecisionPackageBuilderService,
)
from src.domain.errors.decision_package import (
    DecisionPackageNotFoundError,
    ReferralNotAssignedError,
    UnauthorizedPackageAccessError,
)
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.domain.models.referral import Referral, ReferralStatus


@pytest.fixture
def referral_repo() -> AsyncMock:
    """Create a mock referral repository."""
    return AsyncMock()


@pytest.fixture
def petition_repo() -> AsyncMock:
    """Create a mock petition repository."""
    return AsyncMock()


@pytest.fixture
def service(
    referral_repo: AsyncMock,
    petition_repo: AsyncMock,
) -> DecisionPackageBuilderService:
    """Create a DecisionPackageBuilderService with all dependencies."""
    return DecisionPackageBuilderService(
        referral_repo=referral_repo,
        petition_repo=petition_repo,
    )


@pytest.fixture
def knight_id() -> uuid4:
    """Create a Knight UUID."""
    return uuid4()


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
        extensions_granted=1,
    )


@pytest.fixture
def pending_referral() -> Referral:
    """Create a referral in PENDING state (no Knight assigned)."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(weeks=3)
    return Referral(
        referral_id=uuid4(),
        petition_id=uuid4(),
        realm_id=uuid4(),
        deadline=deadline,
        created_at=now,
        status=ReferralStatus.PENDING,
    )


@pytest.fixture
def test_petition() -> PetitionSubmission:
    """Create a test petition in REFERRED state."""
    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for Knight review. This is a detailed description of the issue.",
        submitter_id=uuid4(),
        realm="TECH",
        state=PetitionState.REFERRED,
        co_signer_count=5,
    )


class TestBuildHappyPath:
    """Tests for successful decision package building."""

    @pytest.mark.asyncio
    async def test_build_success_assigned_status(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
        assigned_referral: Referral,
        test_petition: PetitionSubmission,
        knight_id: uuid4,
    ) -> None:
        """Successfully build a decision package for ASSIGNED referral."""
        # Update petition to use the referral's petition_id
        test_petition = PetitionSubmission(
            id=assigned_referral.petition_id,
            type=test_petition.type,
            text=test_petition.text,
            submitter_id=test_petition.submitter_id,
            realm=test_petition.realm,
            state=test_petition.state,
            co_signer_count=test_petition.co_signer_count,
        )

        referral_repo.get_by_id.return_value = assigned_referral
        petition_repo.get.return_value = test_petition

        package = await service.build(
            referral_id=assigned_referral.referral_id,
            requester_id=knight_id,
        )

        # Verify package contents
        assert package.referral_id == assigned_referral.referral_id
        assert package.petition_id == assigned_referral.petition_id
        assert package.realm_id == assigned_referral.realm_id
        assert package.assigned_knight_id == knight_id
        assert package.deadline == assigned_referral.deadline
        assert package.status == ReferralStatus.ASSIGNED
        assert package.extensions_granted == 0
        assert package.can_extend is True

        # Verify petition contents
        assert package.petition_text == test_petition.text
        assert package.petition_type == test_petition.type
        assert package.submitter_id == test_petition.submitter_id
        assert package.co_signer_count == test_petition.co_signer_count

        # Verify built_at is set
        assert package.built_at is not None

    @pytest.mark.asyncio
    async def test_build_success_in_review_status(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
        in_review_referral: Referral,
        test_petition: PetitionSubmission,
        knight_id: uuid4,
    ) -> None:
        """Successfully build a decision package for IN_REVIEW referral."""
        test_petition = PetitionSubmission(
            id=in_review_referral.petition_id,
            type=test_petition.type,
            text=test_petition.text,
            submitter_id=test_petition.submitter_id,
            realm=test_petition.realm,
            state=test_petition.state,
            co_signer_count=test_petition.co_signer_count,
        )

        referral_repo.get_by_id.return_value = in_review_referral
        petition_repo.get.return_value = test_petition

        package = await service.build(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
        )

        assert package.status == ReferralStatus.IN_REVIEW
        assert package.extensions_granted == 1
        # With 1 extension used, can still extend (max is 2)
        assert package.can_extend is True


class TestAuthorizationEnforcement:
    """Tests for authorization enforcement (NFR-5.2)."""

    @pytest.mark.asyncio
    async def test_build_fails_wrong_knight(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
        assigned_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Should reject access when requester is not the assigned Knight."""
        referral_repo.get_by_id.return_value = assigned_referral
        wrong_knight_id = uuid4()

        with pytest.raises(UnauthorizedPackageAccessError) as exc_info:
            await service.build(
                referral_id=assigned_referral.referral_id,
                requester_id=wrong_knight_id,
            )

        assert exc_info.value.referral_id == assigned_referral.referral_id
        assert exc_info.value.requester_id == wrong_knight_id
        assert exc_info.value.assigned_knight_id == knight_id

        # Petition should not have been queried
        petition_repo.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_fails_no_assigned_knight(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
    ) -> None:
        """Should reject access when referral has no assigned Knight."""
        # Create a referral that's in ASSIGNED state but has None for knight
        # This is an invalid state but we need to test the error handling
        # We can't actually create this via Referral constructor due to validation
        # So we use a mock that returns a referral-like object
        mock_referral = AsyncMock()
        mock_referral.referral_id = uuid4()
        mock_referral.status = ReferralStatus.ASSIGNED
        mock_referral.assigned_knight_id = None

        referral_repo.get_by_id.return_value = mock_referral
        requester_id = uuid4()

        with pytest.raises(UnauthorizedPackageAccessError) as exc_info:
            await service.build(
                referral_id=mock_referral.referral_id,
                requester_id=requester_id,
            )

        assert "no assigned Knight" in str(exc_info.value)


class TestReferralStateValidation:
    """Tests for referral state validation."""

    @pytest.mark.asyncio
    async def test_build_fails_pending_referral(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
        pending_referral: Referral,
    ) -> None:
        """Should reject access for PENDING referral."""
        referral_repo.get_by_id.return_value = pending_referral

        with pytest.raises(ReferralNotAssignedError) as exc_info:
            await service.build(
                referral_id=pending_referral.referral_id,
                requester_id=uuid4(),
            )

        assert exc_info.value.referral_id == pending_referral.referral_id
        assert exc_info.value.current_status == ReferralStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_build_fails_completed_referral(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
        knight_id: uuid4,
    ) -> None:
        """Should reject access for COMPLETED referral."""
        from src.domain.models.referral import ReferralRecommendation

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
            rationale="Test rationale",
            completed_at=now,
        )

        referral_repo.get_by_id.return_value = completed_referral

        with pytest.raises(ReferralNotAssignedError) as exc_info:
            await service.build(
                referral_id=completed_referral.referral_id,
                requester_id=knight_id,
            )

        assert exc_info.value.current_status == ReferralStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_build_fails_expired_referral(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
    ) -> None:
        """Should reject access for EXPIRED referral."""
        now = datetime.now(timezone.utc)
        deadline = now - timedelta(days=1)  # Past deadline

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

        with pytest.raises(ReferralNotAssignedError) as exc_info:
            await service.build(
                referral_id=expired_referral.referral_id,
                requester_id=uuid4(),
            )

        assert exc_info.value.current_status == ReferralStatus.EXPIRED.value


class TestNotFoundErrors:
    """Tests for not found error handling."""

    @pytest.mark.asyncio
    async def test_build_fails_referral_not_found(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
    ) -> None:
        """Should raise DecisionPackageNotFoundError when referral doesn't exist."""
        referral_repo.get_by_id.return_value = None
        referral_id = uuid4()

        with pytest.raises(DecisionPackageNotFoundError) as exc_info:
            await service.build(
                referral_id=referral_id,
                requester_id=uuid4(),
            )

        assert exc_info.value.referral_id == referral_id

    @pytest.mark.asyncio
    async def test_build_fails_petition_not_found(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
        assigned_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Should raise DecisionPackageNotFoundError when petition doesn't exist."""
        referral_repo.get_by_id.return_value = assigned_referral
        petition_repo.get.return_value = None

        with pytest.raises(DecisionPackageNotFoundError) as exc_info:
            await service.build(
                referral_id=assigned_referral.referral_id,
                requester_id=knight_id,
            )

        assert exc_info.value.referral_id == assigned_referral.referral_id
        assert exc_info.value.petition_id == assigned_referral.petition_id
        assert "data consistency" in str(exc_info.value).lower()


class TestPackageSerialization:
    """Tests for decision package serialization."""

    @pytest.mark.asyncio
    async def test_package_to_dict(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
        assigned_referral: Referral,
        test_petition: PetitionSubmission,
        knight_id: uuid4,
    ) -> None:
        """Package should serialize correctly to dict."""
        test_petition = PetitionSubmission(
            id=assigned_referral.petition_id,
            type=test_petition.type,
            text=test_petition.text,
            submitter_id=test_petition.submitter_id,
            realm=test_petition.realm,
            state=test_petition.state,
            co_signer_count=test_petition.co_signer_count,
        )

        referral_repo.get_by_id.return_value = assigned_referral
        petition_repo.get.return_value = test_petition

        package = await service.build(
            referral_id=assigned_referral.referral_id,
            requester_id=knight_id,
        )

        # Serialize to dict
        data = package.to_dict()

        # Verify structure
        assert data["referral_id"] == str(assigned_referral.referral_id)
        assert data["petition_id"] == str(assigned_referral.petition_id)
        assert data["realm_id"] == str(assigned_referral.realm_id)
        assert data["status"] == "assigned"
        assert data["extensions_granted"] == 0
        assert data["can_extend"] is True

        # Verify nested petition structure
        assert "petition" in data
        assert data["petition"]["text"] == test_petition.text
        assert data["petition"]["type"] == "GENERAL"
        assert data["petition"]["co_signer_count"] == 5


class TestAnonymousPetitions:
    """Tests for handling anonymous petitions."""

    @pytest.mark.asyncio
    async def test_build_with_anonymous_petition(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: AsyncMock,
        petition_repo: AsyncMock,
        assigned_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Should handle petitions without submitter_id."""
        anonymous_petition = PetitionSubmission(
            id=assigned_referral.petition_id,
            type=PetitionType.GRIEVANCE,
            text="Anonymous grievance petition",
            submitter_id=None,  # Anonymous
            realm="LEGAL",
            state=PetitionState.REFERRED,
            co_signer_count=0,
        )

        referral_repo.get_by_id.return_value = assigned_referral
        petition_repo.get.return_value = anonymous_petition

        package = await service.build(
            referral_id=assigned_referral.referral_id,
            requester_id=knight_id,
        )

        assert package.submitter_id is None
        assert package.petition_type == PetitionType.GRIEVANCE

        # Verify serialization handles None submitter_id
        data = package.to_dict()
        assert data["petition"]["submitter_id"] is None
