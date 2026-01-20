"""Integration tests for escalation threshold checking (Story 5.5, FR-6.5).

Tests the integration between CoSignSubmissionService and EscalationThresholdService
to ensure threshold checking is correctly performed on each co-sign.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached
- FR-5.2: Escalation thresholds: CESSATION=100, GRIEVANCE=50
- FR-6.5: System SHALL check escalation threshold on each co-sign
- FR-10.2: CESSATION petitions SHALL auto-escalate at 100 co-signers
- FR-10.3: GRIEVANCE petitions SHALL auto-escalate at 50 co-signers
- CON-5: CESSATION auto-escalation threshold is immutable (100)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.api.dependencies.co_sign import (
    get_co_sign_submission_service,
    reset_co_sign_dependencies,
    set_co_sign_repository,
    set_halt_checker,
    set_identity_store,
    set_petition_repository,
)
from src.application.services.escalation_threshold_service import (
    EscalationThresholdService,
)
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.co_sign_repository_stub import CoSignRepositoryStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.identity_store_stub import IdentityStoreStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


@pytest.fixture(autouse=True)
def reset_dependencies() -> None:
    """Reset all singleton dependencies before each test."""
    reset_co_sign_dependencies()


@pytest.fixture
def petition_repo() -> PetitionSubmissionRepositoryStub:
    """Create and configure petition repository."""
    repo = PetitionSubmissionRepositoryStub()
    set_petition_repository(repo)
    return repo


@pytest.fixture
def co_sign_repo() -> CoSignRepositoryStub:
    """Create and configure co-sign repository."""
    repo = CoSignRepositoryStub()
    set_co_sign_repository(repo)
    return repo


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create and configure halt checker."""
    checker = HaltCheckerStub()
    set_halt_checker(checker)
    return checker


@pytest.fixture
def identity_store() -> IdentityStoreStub:
    """Create and configure identity store with verified identities."""
    store = IdentityStoreStub()
    set_identity_store(store)
    return store


def setup_petition(
    petition_repo: PetitionSubmissionRepositoryStub,
    co_sign_repo: CoSignRepositoryStub,
    petition_type: PetitionType,
    co_signer_count: int = 0,
) -> PetitionSubmission:
    """Create a test petition and register it in both repositories."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=petition_type,
        text="Test petition content",
        state=PetitionState.RECEIVED,
        submitter_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        co_signer_count=co_signer_count,
    )
    # Register in both repositories
    petition_repo._submissions[petition.id] = petition
    co_sign_repo.add_valid_petition(petition.id)
    # Set the starting co-signer count in the stub to match the petition
    # The stub's add_valid_petition initializes to 0, so we override here
    co_sign_repo._counts[petition.id] = co_signer_count
    return petition


class TestThresholdCheckingIntegration:
    """Test threshold checking integration in co-sign workflow."""

    @pytest.mark.asyncio
    async def test_cessation_below_threshold(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """CESSATION petition with count < 100 returns threshold_reached=False."""
        # Setup: Create CESSATION petition with 98 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=98
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign (count becomes 99)
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold not reached
        assert result.threshold_reached is False
        assert result.threshold_value == 100
        assert result.petition_type == "CESSATION"
        assert result.co_signer_count == 99

    @pytest.mark.asyncio
    async def test_cessation_at_threshold(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """CESSATION petition reaching 100 returns threshold_reached=True (FR-10.2)."""
        # Setup: Create CESSATION petition with 99 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=99
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign (count becomes 100)
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold reached
        assert result.threshold_reached is True
        assert result.threshold_value == 100
        assert result.petition_type == "CESSATION"
        assert result.co_signer_count == 100

    @pytest.mark.asyncio
    async def test_cessation_above_threshold(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """CESSATION petition above threshold still returns threshold_reached=True."""
        # Setup: Create CESSATION petition already above threshold
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=150
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold still reached
        assert result.threshold_reached is True
        assert result.threshold_value == 100
        assert result.co_signer_count == 151

    @pytest.mark.asyncio
    async def test_grievance_below_threshold(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """GRIEVANCE petition with count < 50 returns threshold_reached=False."""
        # Setup: Create GRIEVANCE petition with 48 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GRIEVANCE, co_signer_count=48
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign (count becomes 49)
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold not reached
        assert result.threshold_reached is False
        assert result.threshold_value == 50
        assert result.petition_type == "GRIEVANCE"
        assert result.co_signer_count == 49

    @pytest.mark.asyncio
    async def test_grievance_at_threshold(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """GRIEVANCE petition reaching 50 returns threshold_reached=True (FR-10.3)."""
        # Setup: Create GRIEVANCE petition with 49 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GRIEVANCE, co_signer_count=49
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign (count becomes 50)
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold reached
        assert result.threshold_reached is True
        assert result.threshold_value == 50
        assert result.petition_type == "GRIEVANCE"
        assert result.co_signer_count == 50

    @pytest.mark.asyncio
    async def test_general_no_threshold(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """GENERAL petition never triggers threshold (no auto-escalation)."""
        # Setup: Create GENERAL petition with high co-signer count
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GENERAL, co_signer_count=500
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: No threshold for GENERAL
        assert result.threshold_reached is False
        assert result.threshold_value is None
        assert result.petition_type == "GENERAL"
        assert result.co_signer_count == 501

    @pytest.mark.asyncio
    async def test_collaboration_no_threshold(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """COLLABORATION petition never triggers threshold (no auto-escalation)."""
        # Setup: Create COLLABORATION petition with high co-signer count
        petition = setup_petition(
            petition_repo,
            co_sign_repo,
            PetitionType.COLLABORATION,
            co_signer_count=1000,
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: No threshold for COLLABORATION
        assert result.threshold_reached is False
        assert result.threshold_value is None
        assert result.petition_type == "COLLABORATION"
        assert result.co_signer_count == 1001


class TestThresholdResponseFieldsIntegration:
    """Test that threshold fields are correctly populated in response."""

    @pytest.mark.asyncio
    async def test_all_threshold_fields_present(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """All threshold fields are present in result."""
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=0
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # All threshold fields should be present
        assert hasattr(result, "threshold_reached")
        assert hasattr(result, "threshold_value")
        assert hasattr(result, "petition_type")
        assert result.threshold_reached is False
        assert result.threshold_value == 100
        assert result.petition_type == "CESSATION"

    @pytest.mark.asyncio
    async def test_threshold_fields_correct_types(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Threshold fields have correct types."""
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GRIEVANCE, co_signer_count=49
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        assert isinstance(result.threshold_reached, bool)
        assert isinstance(result.threshold_value, int)
        assert isinstance(result.petition_type, str)


class TestMultipleCoSignsThresholdProgression:
    """Test threshold progression across multiple co-signs."""

    @pytest.mark.asyncio
    async def test_threshold_progression_to_reached(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Threshold progresses from False to True as co-signs accumulate."""
        # Start with GRIEVANCE petition at 47 (2 away from threshold)
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GRIEVANCE, co_signer_count=47
        )

        service = get_co_sign_submission_service()

        # First co-sign: count becomes 48
        signer1 = uuid4()
        identity_store.add_valid_identity(signer1)
        result1 = await service.submit_co_sign(petition.id, signer1)
        assert result1.threshold_reached is False
        assert result1.co_signer_count == 48

        # Second co-sign: count becomes 49
        signer2 = uuid4()
        identity_store.add_valid_identity(signer2)
        result2 = await service.submit_co_sign(petition.id, signer2)
        assert result2.threshold_reached is False
        assert result2.co_signer_count == 49

        # Third co-sign: count becomes 50, threshold reached!
        signer3 = uuid4()
        identity_store.add_valid_identity(signer3)
        result3 = await service.submit_co_sign(petition.id, signer3)
        assert result3.threshold_reached is True
        assert result3.co_signer_count == 50
        assert result3.threshold_value == 50


class TestThresholdCheckerServiceIntegration:
    """Test direct EscalationThresholdService integration."""

    def test_service_creates_correct_results(self) -> None:
        """EscalationThresholdService creates correct results for all types."""
        service = EscalationThresholdService()

        # CESSATION at threshold
        result = service.check_threshold(PetitionType.CESSATION, 100)
        assert result.threshold_reached is True
        assert result.threshold_value == 100

        # GRIEVANCE at threshold
        result = service.check_threshold(PetitionType.GRIEVANCE, 50)
        assert result.threshold_reached is True
        assert result.threshold_value == 50

        # GENERAL never reaches threshold
        result = service.check_threshold(PetitionType.GENERAL, 10000)
        assert result.threshold_reached is False
        assert result.threshold_value is None

    def test_service_boundary_conditions(self) -> None:
        """Test boundary conditions at threshold edges."""
        service = EscalationThresholdService()

        # Just below CESSATION threshold
        result = service.check_threshold(PetitionType.CESSATION, 99)
        assert result.threshold_reached is False

        # Exactly at CESSATION threshold
        result = service.check_threshold(PetitionType.CESSATION, 100)
        assert result.threshold_reached is True

        # Just below GRIEVANCE threshold
        result = service.check_threshold(PetitionType.GRIEVANCE, 49)
        assert result.threshold_reached is False

        # Exactly at GRIEVANCE threshold
        result = service.check_threshold(PetitionType.GRIEVANCE, 50)
        assert result.threshold_reached is True
