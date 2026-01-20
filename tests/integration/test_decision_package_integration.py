"""Integration tests for DecisionPackageBuilderService.

Story: 4.3 - Knight Decision Package
Tests the full decision package building flow with stubs.
"""

from datetime import datetime, timedelta, timezone
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
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.referral_repository_stub import ReferralRepositoryStub


@pytest.fixture
def referral_repo() -> ReferralRepositoryStub:
    """Create fresh referral repository stub."""
    return ReferralRepositoryStub()


@pytest.fixture
def petition_repo() -> PetitionSubmissionRepositoryStub:
    """Create fresh petition repository stub."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def service(
    referral_repo: ReferralRepositoryStub,
    petition_repo: PetitionSubmissionRepositoryStub,
) -> DecisionPackageBuilderService:
    """Create DecisionPackageBuilderService with all stubs."""
    return DecisionPackageBuilderService(
        referral_repo=referral_repo,
        petition_repo=petition_repo,
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
def referred_petition(
    petition_repo: PetitionSubmissionRepositoryStub,
) -> PetitionSubmission:
    """Create and store a petition in REFERRED state."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="This is a detailed petition about governance concerns. "
             "The petitioner requests a review of current policies.",
        submitter_id=uuid4(),
        realm="GOVERNANCE",
        state=PetitionState.REFERRED,
        co_signer_count=10,
    )
    petition_repo._submissions[petition.id] = petition
    return petition


@pytest.fixture
def assigned_referral(
    referral_repo: ReferralRepositoryStub,
    referred_petition: PetitionSubmission,
    knight_id: uuid4,
    realm_id: uuid4,
) -> Referral:
    """Create and store an ASSIGNED referral."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(weeks=3)

    # Create pending referral first
    pending_referral = Referral(
        referral_id=uuid4(),
        petition_id=referred_petition.id,
        realm_id=realm_id,
        deadline=deadline,
        created_at=now,
        status=ReferralStatus.PENDING,
    )

    # Store the pending referral (since we can't directly create assigned without knight)
    # Then update with assignment
    assigned = pending_referral.with_assignment(knight_id)

    # Store in repository
    referral_repo._referrals[assigned.referral_id] = assigned
    referral_repo._by_petition[assigned.petition_id] = assigned.referral_id

    return assigned


@pytest.fixture
def in_review_referral(
    referral_repo: ReferralRepositoryStub,
    referred_petition: PetitionSubmission,
    knight_id: uuid4,
    realm_id: uuid4,
) -> Referral:
    """Create and store an IN_REVIEW referral with one extension."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(weeks=4)  # Extended deadline

    # Create through state transitions
    pending = Referral(
        referral_id=uuid4(),
        petition_id=referred_petition.id,
        realm_id=realm_id,
        deadline=now + timedelta(weeks=3),
        created_at=now,
        status=ReferralStatus.PENDING,
    )
    assigned = pending.with_assignment(knight_id)
    extended = assigned.with_extension(deadline)
    in_review = extended.with_in_review()

    # Store in repository
    referral_repo._referrals[in_review.referral_id] = in_review
    referral_repo._by_petition[in_review.petition_id] = in_review.referral_id

    return in_review


class TestFullPackageFlow:
    """Integration tests for the full decision package building flow."""

    @pytest.mark.asyncio
    async def test_build_package_for_assigned_referral(
        self,
        service: DecisionPackageBuilderService,
        assigned_referral: Referral,
        referred_petition: PetitionSubmission,
        knight_id: uuid4,
    ) -> None:
        """Test successful package building for ASSIGNED referral."""
        package = await service.build(
            referral_id=assigned_referral.referral_id,
            requester_id=knight_id,
        )

        # Verify referral data
        assert package.referral_id == assigned_referral.referral_id
        assert package.petition_id == assigned_referral.petition_id
        assert package.realm_id == assigned_referral.realm_id
        assert package.assigned_knight_id == knight_id
        assert package.deadline == assigned_referral.deadline
        assert package.status == ReferralStatus.ASSIGNED
        assert package.extensions_granted == 0
        assert package.can_extend is True

        # Verify petition data
        assert package.petition_text == referred_petition.text
        assert package.petition_type == referred_petition.type
        assert package.submitter_id == referred_petition.submitter_id
        assert package.co_signer_count == referred_petition.co_signer_count

        # Verify built_at is set
        assert package.built_at is not None

    @pytest.mark.asyncio
    async def test_build_package_for_in_review_referral(
        self,
        service: DecisionPackageBuilderService,
        in_review_referral: Referral,
        referred_petition: PetitionSubmission,
        knight_id: uuid4,
    ) -> None:
        """Test successful package building for IN_REVIEW referral."""
        package = await service.build(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
        )

        assert package.status == ReferralStatus.IN_REVIEW
        assert package.extensions_granted == 1
        # Can still extend (max is 2)
        assert package.can_extend is True

    @pytest.mark.asyncio
    async def test_package_contains_complete_context(
        self,
        service: DecisionPackageBuilderService,
        assigned_referral: Referral,
        referred_petition: PetitionSubmission,
        knight_id: uuid4,
    ) -> None:
        """Test that package contains all context for Knight review."""
        package = await service.build(
            referral_id=assigned_referral.referral_id,
            requester_id=knight_id,
        )

        # All required FR-4.3 fields should be present
        assert package.referral_id is not None
        assert package.petition_id is not None
        assert package.realm_id is not None
        assert package.deadline is not None
        assert package.petition_text != ""
        assert package.petition_type is not None
        assert package.petition_created_at is not None


class TestAuthorizationFlow:
    """Integration tests for authorization enforcement."""

    @pytest.mark.asyncio
    async def test_authorized_knight_can_access_package(
        self,
        service: DecisionPackageBuilderService,
        assigned_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Test that the assigned Knight can access the package."""
        # Should not raise
        package = await service.build(
            referral_id=assigned_referral.referral_id,
            requester_id=knight_id,
        )
        assert package.assigned_knight_id == knight_id

    @pytest.mark.asyncio
    async def test_unauthorized_knight_cannot_access_package(
        self,
        service: DecisionPackageBuilderService,
        assigned_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Test that a different Knight cannot access the package."""
        wrong_knight = uuid4()

        with pytest.raises(UnauthorizedPackageAccessError) as exc_info:
            await service.build(
                referral_id=assigned_referral.referral_id,
                requester_id=wrong_knight,
            )

        assert exc_info.value.requester_id == wrong_knight
        assert exc_info.value.assigned_knight_id == knight_id


class TestReferralStateRestrictions:
    """Integration tests for referral state restrictions."""

    @pytest.mark.asyncio
    async def test_cannot_access_pending_referral(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_id: uuid4,
    ) -> None:
        """Test that PENDING referrals cannot have packages accessed."""
        # Create petition
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.REFERRED,
        )
        petition_repo._submissions[petition.id] = petition

        # Create pending referral (no Knight assigned)
        now = datetime.now(timezone.utc)
        pending = Referral(
            referral_id=uuid4(),
            petition_id=petition.id,
            realm_id=realm_id,
            deadline=now + timedelta(weeks=3),
            created_at=now,
            status=ReferralStatus.PENDING,
        )
        referral_repo._referrals[pending.referral_id] = pending
        referral_repo._by_petition[pending.petition_id] = pending.referral_id

        with pytest.raises(ReferralNotAssignedError) as exc_info:
            await service.build(
                referral_id=pending.referral_id,
                requester_id=uuid4(),
            )

        assert exc_info.value.current_status == ReferralStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_cannot_access_expired_referral(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        realm_id: uuid4,
    ) -> None:
        """Test that EXPIRED referrals cannot have packages accessed."""
        # Create petition
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition",
            state=PetitionState.REFERRED,
        )
        petition_repo._submissions[petition.id] = petition

        # Create expired referral
        now = datetime.now(timezone.utc)
        expired = Referral(
            referral_id=uuid4(),
            petition_id=petition.id,
            realm_id=realm_id,
            deadline=now - timedelta(days=1),  # Past
            created_at=now - timedelta(weeks=4),
            status=ReferralStatus.EXPIRED,
            completed_at=now,
        )
        referral_repo._referrals[expired.referral_id] = expired
        referral_repo._by_petition[expired.petition_id] = expired.referral_id

        with pytest.raises(ReferralNotAssignedError) as exc_info:
            await service.build(
                referral_id=expired.referral_id,
                requester_id=uuid4(),
            )

        assert exc_info.value.current_status == ReferralStatus.EXPIRED.value


class TestNotFoundScenarios:
    """Integration tests for not found scenarios."""

    @pytest.mark.asyncio
    async def test_referral_not_found(
        self,
        service: DecisionPackageBuilderService,
    ) -> None:
        """Test error when referral doesn't exist."""
        nonexistent_id = uuid4()

        with pytest.raises(DecisionPackageNotFoundError) as exc_info:
            await service.build(
                referral_id=nonexistent_id,
                requester_id=uuid4(),
            )

        assert exc_info.value.referral_id == nonexistent_id

    @pytest.mark.asyncio
    async def test_petition_not_found_data_consistency(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: ReferralRepositoryStub,
        knight_id: uuid4,
        realm_id: uuid4,
    ) -> None:
        """Test error when petition doesn't exist (data consistency issue)."""
        # Create referral pointing to non-existent petition
        now = datetime.now(timezone.utc)
        pending = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),  # This petition doesn't exist
            realm_id=realm_id,
            deadline=now + timedelta(weeks=3),
            created_at=now,
            status=ReferralStatus.PENDING,
        )
        assigned = pending.with_assignment(knight_id)
        referral_repo._referrals[assigned.referral_id] = assigned
        referral_repo._by_petition[assigned.petition_id] = assigned.referral_id

        with pytest.raises(DecisionPackageNotFoundError) as exc_info:
            await service.build(
                referral_id=assigned.referral_id,
                requester_id=knight_id,
            )

        assert exc_info.value.petition_id == assigned.petition_id
        assert "data consistency" in str(exc_info.value).lower()


class TestPackageSerialization:
    """Integration tests for package serialization."""

    @pytest.mark.asyncio
    async def test_package_serializes_to_api_format(
        self,
        service: DecisionPackageBuilderService,
        assigned_referral: Referral,
        referred_petition: PetitionSubmission,
        knight_id: uuid4,
    ) -> None:
        """Test that package serializes correctly for API response."""
        package = await service.build(
            referral_id=assigned_referral.referral_id,
            requester_id=knight_id,
        )

        data = package.to_dict()

        # Verify API structure matches story requirements
        assert "referral_id" in data
        assert "petition_id" in data
        assert "realm_id" in data
        assert "deadline" in data
        assert "extensions_granted" in data
        assert "can_extend" in data
        assert "status" in data
        assert "petition" in data

        # Verify nested petition structure
        petition_data = data["petition"]
        assert "text" in petition_data
        assert "type" in petition_data
        assert "created_at" in petition_data
        assert "submitter_id" in petition_data
        assert "co_signer_count" in petition_data

        # Verify datetime serialization (ISO 8601)
        assert "T" in data["deadline"]  # ISO 8601 format has T separator

        # Verify UUID serialization
        assert isinstance(data["referral_id"], str)
        assert isinstance(data["petition_id"], str)


class TestAnonymousPetitions:
    """Integration tests for anonymous petition handling."""

    @pytest.mark.asyncio
    async def test_package_with_anonymous_petition(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        knight_id: uuid4,
        realm_id: uuid4,
    ) -> None:
        """Test package building for anonymous petition."""
        # Create anonymous petition
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GRIEVANCE,
            text="Anonymous grievance about system behavior",
            submitter_id=None,  # Anonymous
            state=PetitionState.REFERRED,
            co_signer_count=0,
        )
        petition_repo._submissions[petition.id] = petition

        # Create referral
        now = datetime.now(timezone.utc)
        pending = Referral(
            referral_id=uuid4(),
            petition_id=petition.id,
            realm_id=realm_id,
            deadline=now + timedelta(weeks=3),
            created_at=now,
            status=ReferralStatus.PENDING,
        )
        assigned = pending.with_assignment(knight_id)
        referral_repo._referrals[assigned.referral_id] = assigned
        referral_repo._by_petition[assigned.petition_id] = assigned.referral_id

        package = await service.build(
            referral_id=assigned.referral_id,
            requester_id=knight_id,
        )

        assert package.submitter_id is None
        assert package.petition_type == PetitionType.GRIEVANCE
        assert package.co_signer_count == 0

        # Verify serialization handles None
        data = package.to_dict()
        assert data["petition"]["submitter_id"] is None


class TestExtensionStatus:
    """Integration tests for extension status tracking."""

    @pytest.mark.asyncio
    async def test_can_extend_when_under_limit(
        self,
        service: DecisionPackageBuilderService,
        assigned_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Test that can_extend is True when under limit."""
        package = await service.build(
            referral_id=assigned_referral.referral_id,
            requester_id=knight_id,
        )

        assert package.extensions_granted == 0
        assert package.can_extend is True

    @pytest.mark.asyncio
    async def test_can_extend_with_one_extension(
        self,
        service: DecisionPackageBuilderService,
        in_review_referral: Referral,
        knight_id: uuid4,
    ) -> None:
        """Test that can_extend is True with one extension used."""
        package = await service.build(
            referral_id=in_review_referral.referral_id,
            requester_id=knight_id,
        )

        assert package.extensions_granted == 1
        assert package.can_extend is True  # Max is 2

    @pytest.mark.asyncio
    async def test_cannot_extend_at_max(
        self,
        service: DecisionPackageBuilderService,
        referral_repo: ReferralRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        knight_id: uuid4,
        realm_id: uuid4,
    ) -> None:
        """Test that can_extend is False when at max extensions."""
        # Create petition
        petition = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition at max extensions",
            state=PetitionState.REFERRED,
        )
        petition_repo._submissions[petition.id] = petition

        # Create referral with max extensions
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(weeks=5)

        pending = Referral(
            referral_id=uuid4(),
            petition_id=petition.id,
            realm_id=realm_id,
            deadline=now + timedelta(weeks=3),
            created_at=now,
            status=ReferralStatus.PENDING,
        )
        assigned = pending.with_assignment(knight_id)
        # Apply first extension
        ext1 = assigned.with_extension(now + timedelta(weeks=4))
        # Apply second extension (max)
        ext2 = ext1.with_extension(deadline)
        in_review = ext2.with_in_review()

        referral_repo._referrals[in_review.referral_id] = in_review
        referral_repo._by_petition[in_review.petition_id] = in_review.referral_id

        package = await service.build(
            referral_id=in_review.referral_id,
            requester_id=knight_id,
        )

        assert package.extensions_granted == 2
        assert package.can_extend is False  # At max
