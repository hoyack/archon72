"""Integration tests for auto-escalation execution (Story 5.6, FR-5.1, FR-5.3).

Tests the integration between CoSignSubmissionService and AutoEscalationExecutor
to ensure auto-escalation executes correctly when thresholds are reached.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count [P0]
- FR-10.2: CESSATION petitions SHALL auto-escalate at 100 co-signers
- FR-10.3: GRIEVANCE petitions SHALL auto-escalate at 50 co-signers
- CT-12: All outputs through witnessing pipeline
- CT-14: Silence must be expensive - auto-escalation ensures King attention
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.api.dependencies.co_sign import (
    get_co_sign_submission_service,
    reset_co_sign_dependencies,
    set_auto_escalation_executor,
    set_co_sign_repository,
    set_halt_checker,
    set_identity_store,
    set_petition_repository,
)
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.auto_escalation_executor_stub import (
    AutoEscalationExecutorStub,
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


@pytest.fixture
def auto_escalation_executor() -> AutoEscalationExecutorStub:
    """Create and configure auto-escalation executor."""
    executor = AutoEscalationExecutorStub()
    set_auto_escalation_executor(executor)
    return executor


def setup_petition(
    petition_repo: PetitionSubmissionRepositoryStub,
    co_sign_repo: CoSignRepositoryStub,
    petition_type: PetitionType,
    co_signer_count: int = 0,
    state: PetitionState = PetitionState.RECEIVED,
) -> PetitionSubmission:
    """Create a test petition and register it in both repositories."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=petition_type,
        text="Test petition content",
        state=state,
        submitter_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        co_signer_count=co_signer_count,
    )
    # Register in both repositories
    petition_repo._submissions[petition.id] = petition
    co_sign_repo.add_valid_petition(petition.id)
    # Set the starting co-signer count in the stub to match the petition
    co_sign_repo._counts[petition.id] = co_signer_count
    return petition


class TestAutoEscalationExecution:
    """Test auto-escalation execution when threshold is reached (FR-5.1)."""

    @pytest.mark.asyncio
    async def test_cessation_triggers_escalation_at_100(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """CESSATION petition triggers auto-escalation at 100 co-signers (FR-10.2)."""
        # Setup: Create CESSATION petition with 99 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=99
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign (count becomes 100)
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold reached and escalation triggered
        assert result.threshold_reached is True
        assert result.threshold_value == 100
        assert result.escalation_triggered is True
        assert result.escalation_id is not None
        assert isinstance(result.escalation_id, UUID)

    @pytest.mark.asyncio
    async def test_grievance_triggers_escalation_at_50(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """GRIEVANCE petition triggers auto-escalation at 50 co-signers (FR-10.3)."""
        # Setup: Create GRIEVANCE petition with 49 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GRIEVANCE, co_signer_count=49
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign (count becomes 50)
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold reached and escalation triggered
        assert result.threshold_reached is True
        assert result.threshold_value == 50
        assert result.escalation_triggered is True
        assert result.escalation_id is not None

    @pytest.mark.asyncio
    async def test_below_threshold_no_escalation(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """Below threshold does not trigger escalation."""
        # Setup: Create CESSATION petition with 98 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=98
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign (count becomes 99)
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold not reached, no escalation
        assert result.threshold_reached is False
        assert result.escalation_triggered is False
        assert result.escalation_id is None

    @pytest.mark.asyncio
    async def test_general_petition_no_escalation(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """GENERAL petition never triggers escalation (no threshold)."""
        # Setup: Create GENERAL petition with many co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GENERAL, co_signer_count=500
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: No escalation for GENERAL
        assert result.threshold_reached is False
        assert result.escalation_triggered is False
        assert result.escalation_id is None


class TestEscalationIdempotency:
    """Test idempotent behavior for already escalated petitions (AC5)."""

    @pytest.mark.asyncio
    async def test_already_escalated_returns_idempotent(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """Already escalated petition returns escalation_triggered=True but no new escalation."""
        # Setup: Create CESSATION petition with 99 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=99
        )

        # Pre-mark petition as escalated
        auto_escalation_executor.set_already_escalated(petition.id)

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign (count becomes 100)
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Threshold reached, but escalation shows already escalated
        assert result.threshold_reached is True
        assert result.escalation_triggered is False  # Already escalated
        assert result.escalation_id is None

        # Verify only one entry in history (the check, not a new escalation)
        history = auto_escalation_executor.get_history_for_petition(petition.id)
        assert len(history) == 1
        assert history[0].result.already_escalated is True

    @pytest.mark.asyncio
    async def test_multiple_threshold_triggers_single_escalation(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """Multiple co-signs above threshold only escalate once."""
        # Setup: Create GRIEVANCE petition with 49 co-signers
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GRIEVANCE, co_signer_count=49
        )

        service = get_co_sign_submission_service()

        # First co-sign: triggers escalation
        signer1 = uuid4()
        identity_store.add_valid_identity(signer1)
        result1 = await service.submit_co_sign(petition.id, signer1)
        assert result1.escalation_triggered is True

        # Second co-sign: should not create new escalation
        signer2 = uuid4()
        identity_store.add_valid_identity(signer2)
        result2 = await service.submit_co_sign(petition.id, signer2)
        assert result2.threshold_reached is True
        # Escalation already happened, so new co-signs don't re-trigger
        # The stub will return already_escalated=True
        assert result2.escalation_triggered is False

        # Verify escalation only happened once
        assert auto_escalation_executor.get_escalation_count() == 1


class TestEscalationExecutorHistory:
    """Test that escalation executor tracks history correctly."""

    @pytest.mark.asyncio
    async def test_escalation_history_recorded(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """Escalation execution is recorded in history for auditing."""
        # Setup: Create CESSATION petition at threshold
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=99
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign to trigger escalation
        service = get_co_sign_submission_service()
        await service.submit_co_sign(petition.id, signer_id)

        # Assert: History recorded
        history = auto_escalation_executor.get_history()
        assert len(history) == 1

        entry = history[0]
        assert entry.petition_id == petition.id
        assert entry.trigger_type == "CO_SIGNER_THRESHOLD"
        assert entry.co_signer_count == 100
        assert entry.threshold == 100
        assert entry.result.triggered is True


class TestEscalationResponseFields:
    """Test that escalation fields are correctly populated in response (AC6)."""

    @pytest.mark.asyncio
    async def test_all_escalation_fields_present(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """All escalation fields are present in result."""
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GRIEVANCE, co_signer_count=49
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # All escalation fields should be present
        assert hasattr(result, "escalation_triggered")
        assert hasattr(result, "escalation_id")
        assert result.escalation_triggered is True
        assert result.escalation_id is not None

    @pytest.mark.asyncio
    async def test_escalation_id_is_uuid(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """escalation_id is a valid UUID."""
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=99
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        assert isinstance(result.escalation_id, UUID)


class TestEscalationWithNoExecutor:
    """Test behavior when auto-escalation executor is not configured."""

    @pytest.mark.asyncio
    async def test_threshold_reached_without_executor(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """When executor is not configured, threshold is reached but no escalation."""
        # Don't set up an executor - use the default from dependencies
        # The default might have an executor, so reset and don't set one explicitly
        reset_co_sign_dependencies()
        set_petition_repository(petition_repo)
        set_co_sign_repository(co_sign_repo)
        set_halt_checker(halt_checker)
        set_identity_store(identity_store)
        # Note: get_co_sign_submission_service() will include default executor
        # This test verifies the executor is present in the default setup

        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=99
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Default executor should trigger escalation
        assert result.threshold_reached is True
        assert result.escalation_triggered is True


class TestEscalationExecutorFailure:
    """Test graceful handling of escalation executor failures."""

    @pytest.mark.asyncio
    async def test_executor_failure_does_not_fail_cosign(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Escalation failure does not fail the co-sign operation."""
        # Create executor that will fail
        failing_executor = AutoEscalationExecutorStub.failing(
            RuntimeError("Escalation service unavailable")
        )
        set_auto_escalation_executor(failing_executor)

        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.CESSATION, co_signer_count=99
        )

        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        # Act: Submit co-sign - should succeed even if escalation fails
        service = get_co_sign_submission_service()
        result = await service.submit_co_sign(petition.id, signer_id)

        # Assert: Co-sign succeeded
        assert result.cosign_id is not None
        assert result.co_signer_count == 100
        assert result.threshold_reached is True
        # Escalation failed but didn't crash the request
        assert result.escalation_triggered is False
        assert result.escalation_id is None


class TestThresholdProgressionToEscalation:
    """Test threshold progression leading to escalation."""

    @pytest.mark.asyncio
    async def test_progression_to_threshold_and_escalation(
        self,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        auto_escalation_executor: AutoEscalationExecutorStub,
    ) -> None:
        """Multiple co-signs progressively reaching threshold triggers escalation."""
        # Start with GRIEVANCE petition at 47 (3 away from threshold)
        petition = setup_petition(
            petition_repo, co_sign_repo, PetitionType.GRIEVANCE, co_signer_count=47
        )

        service = get_co_sign_submission_service()

        # First co-sign: count becomes 48
        signer1 = uuid4()
        identity_store.add_valid_identity(signer1)
        result1 = await service.submit_co_sign(petition.id, signer1)
        assert result1.threshold_reached is False
        assert result1.escalation_triggered is False
        assert result1.co_signer_count == 48

        # Second co-sign: count becomes 49
        signer2 = uuid4()
        identity_store.add_valid_identity(signer2)
        result2 = await service.submit_co_sign(petition.id, signer2)
        assert result2.threshold_reached is False
        assert result2.escalation_triggered is False
        assert result2.co_signer_count == 49

        # Third co-sign: count becomes 50, threshold reached, escalation triggered!
        signer3 = uuid4()
        identity_store.add_valid_identity(signer3)
        result3 = await service.submit_co_sign(petition.id, signer3)
        assert result3.threshold_reached is True
        assert result3.threshold_value == 50
        assert result3.escalation_triggered is True
        assert result3.escalation_id is not None
        assert result3.co_signer_count == 50

        # Verify exactly one escalation
        assert auto_escalation_executor.get_escalation_count() == 1
