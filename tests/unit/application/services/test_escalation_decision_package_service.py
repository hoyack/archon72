"""Unit tests for EscalationDecisionPackageService (Story 6.2, FR-5.4).

Tests the escalation decision package service's ability to fetch complete
escalation context for King adoption/acknowledgment decisions.

Constitutional Constraints:
- FR-5.4: King SHALL receive complete escalation context [P0]
- RULING-2: Tiered transcript access (mediated summaries for Kings)
- RULING-3: Realm-scoped data access (verify realm match)
- CT-13: Reads work during halt
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.application.services.escalation_decision_package_service import (
    EscalationDecisionPackageService,
    EscalationNotFoundError,
    RealmMismatchError,
)
from src.domain.errors.petition import PetitionSubmissionNotFoundError
from src.domain.models.petition_submission import (
    PetitionSubmission,
    PetitionType,
    PetitionState,
)
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def petition_repository() -> PetitionSubmissionRepositoryStub:
    """Create a petition repository stub for testing."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def decision_package_service(
    petition_repository: PetitionSubmissionRepositoryStub,
) -> EscalationDecisionPackageService:
    """Create a decision package service with stubbed repository."""
    return EscalationDecisionPackageService(petition_repository=petition_repository)


@pytest.fixture
def escalated_petition() -> PetitionSubmission:
    """Create an escalated petition for testing."""
    return PetitionSubmission(
        id=uuid4(),
        type=PetitionType.CESSATION,
        text="Request for cessation review due to governance concerns.",
        submitter_id=uuid4(),
        state=PetitionState.ESCALATED,
        realm="governance",
        created_at=datetime(2026, 1, 15, 8, 30, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
        co_signer_count=150,
        escalation_source="CO_SIGNER_THRESHOLD",
        escalated_at=datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
        escalated_to_realm="governance",
    )


# =============================================================================
# Happy Path Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_decision_package_success(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test fetching decision package for escalated petition (Story 6.2, AC1-AC2).

    Verifies:
    - Service fetches complete decision package
    - Petition core data included (text, type, submitter metadata)
    - Co-signer information included (total count)
    - Escalation history included (source, timestamp, co-signer count)
    """
    # Arrange
    await petition_repository.save(escalated_petition)

    # Act
    package = await decision_package_service.get_decision_package(
        petition_id=escalated_petition.id,
        king_realm="governance",
    )

    # Assert
    assert package.petition_id == escalated_petition.id
    assert package.petition_type == PetitionType.CESSATION.value
    assert package.petition_content == escalated_petition.text
    assert package.submitter_metadata.submitted_at == escalated_petition.created_at
    assert package.co_signers.total_count == 150
    assert package.escalation_history.escalation_source == "CO_SIGNER_THRESHOLD"
    assert package.escalation_history.co_signer_count_at_escalation == 150


@pytest.mark.asyncio
async def test_get_decision_package_anonymized_submitter(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test submitter metadata is anonymized (Story 6.2, AC2).

    Verifies:
    - Submitter public key is hashed (SHA-256)
    - Hash is 64 characters (hex-encoded)
    - Original UUID is not exposed
    """
    # Arrange
    await petition_repository.save(escalated_petition)

    # Act
    package = await decision_package_service.get_decision_package(
        petition_id=escalated_petition.id,
        king_realm="governance",
    )

    # Assert
    assert len(package.submitter_metadata.public_key_hash) == 64
    assert package.submitter_metadata.public_key_hash.isalnum()
    assert str(escalated_petition.submitter_id) not in package.submitter_metadata.public_key_hash


@pytest.mark.asyncio
async def test_get_decision_package_escalation_history(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test escalation history context is included (Story 6.2, AC2).

    Verifies:
    - Escalation source is provided
    - Escalation timestamp is included
    - Co-signer count at escalation is recorded
    """
    # Arrange
    await petition_repository.save(escalated_petition)

    # Act
    package = await decision_package_service.get_decision_package(
        petition_id=escalated_petition.id,
        king_realm="governance",
    )

    # Assert
    history = package.escalation_history
    assert history.escalation_source == "CO_SIGNER_THRESHOLD"
    assert history.escalated_at == escalated_petition.escalated_at
    assert history.co_signer_count_at_escalation == 150
    assert history.deliberation_summary is None  # Not applicable for CO_SIGNER_THRESHOLD
    assert history.knight_recommendation is None  # Not applicable for CO_SIGNER_THRESHOLD


@pytest.mark.asyncio
async def test_get_decision_package_multiple_petition_types(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test decision package works for all petition types (Story 6.2, AC2).

    Verifies:
    - CESSATION petitions supported
    - GRIEVANCE petitions supported
    - GENERAL petitions supported
    - COLLABORATION petitions supported
    """
    # Arrange - Create escalated petitions of each type
    petition_types = [
        PetitionType.CESSATION,
        PetitionType.GRIEVANCE,
        PetitionType.GENERAL,
        PetitionType.COLLABORATION,
    ]

    petitions = []
    for pet_type in petition_types:
        petition = PetitionSubmission(
            id=uuid4(),
            type=pet_type,
            text=f"Test {pet_type.value} petition",
            submitter_id=uuid4(),
            state=PetitionState.ESCALATED,
            realm="governance",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            co_signer_count=120,
            escalation_source="CO_SIGNER_THRESHOLD",
            escalated_at=datetime.utcnow(),
            escalated_to_realm="governance",
        )
        petitions.append(petition)
        await petition_repository.save(petition)

    # Act & Assert
    for petition in petitions:
        package = await decision_package_service.get_decision_package(
            petition_id=petition.id,
            king_realm="governance",
        )
        assert package.petition_type == petition.type.value
        assert package.petition_content == petition.text


# =============================================================================
# Error Condition Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_decision_package_petition_not_found(
    decision_package_service: EscalationDecisionPackageService,
) -> None:
    """Test error when petition doesn't exist (Story 6.2, AC1).

    Verifies:
    - Raises PetitionSubmissionNotFoundError
    - Error includes petition ID
    """
    # Arrange
    nonexistent_id = uuid4()

    # Act & Assert
    with pytest.raises(PetitionSubmissionNotFoundError) as exc_info:
        await decision_package_service.get_decision_package(
            petition_id=nonexistent_id,
            king_realm="governance",
        )

    assert exc_info.value.petition_id == nonexistent_id


@pytest.mark.asyncio
async def test_get_decision_package_petition_not_escalated(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test error when petition is not escalated (Story 6.2, AC1).

    Verifies:
    - Raises EscalationNotFoundError
    - Error message indicates petition is not escalated
    """
    # Arrange - Create non-escalated petition
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Non-escalated petition",
        submitter_id=uuid4(),
        state=PetitionState.RECEIVED,  # Not escalated
        realm="governance",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        co_signer_count=50,
        escalation_source=None,
        escalated_at=None,
        escalated_to_realm=None,
    )
    await petition_repository.save(petition)

    # Act & Assert
    with pytest.raises(EscalationNotFoundError) as exc_info:
        await decision_package_service.get_decision_package(
            petition_id=petition.id,
            king_realm="governance",
        )

    assert exc_info.value.petition_id == petition.id
    assert "not escalated" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_decision_package_realm_mismatch(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test error when King's realm doesn't match escalation realm (Story 6.2, RULING-3).

    Verifies:
    - Raises RealmMismatchError
    - Error includes expected and actual realms
    - Enforces realm-scoped data access
    """
    # Arrange
    escalated_petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.CESSATION,
        text="Escalated to different realm",
        submitter_id=uuid4(),
        state=PetitionState.ESCALATED,
        realm="governance",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        co_signer_count=100,
        escalation_source="CO_SIGNER_THRESHOLD",
        escalated_at=datetime.utcnow(),
        escalated_to_realm="security",  # Different realm
    )
    await petition_repository.save(escalated_petition)

    # Act & Assert
    with pytest.raises(RealmMismatchError) as exc_info:
        await decision_package_service.get_decision_package(
            petition_id=escalated_petition.id,
            king_realm="governance",  # Requesting from wrong realm
        )

    assert exc_info.value.petition_id == escalated_petition.id
    assert exc_info.value.expected_realm == "governance"
    assert exc_info.value.actual_realm == "security"


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_decision_package_zero_cosigners(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test decision package with zero co-signers (Story 6.2, AC2).

    Verifies:
    - Package returns with zero co-signer count
    - Empty co-signer list
    - Service doesn't fail on edge case
    """
    # Arrange - Escalated petition with 0 co-signers (e.g., Knight recommendation)
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Knight-recommended petition",
        submitter_id=uuid4(),
        state=PetitionState.ESCALATED,
        realm="governance",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        co_signer_count=0,
        escalation_source="KNIGHT_RECOMMENDATION",
        escalated_at=datetime.utcnow(),
        escalated_to_realm="governance",
    )
    await petition_repository.save(petition)

    # Act
    package = await decision_package_service.get_decision_package(
        petition_id=petition.id,
        king_realm="governance",
    )

    # Assert
    assert package.co_signers.total_count == 0
    assert len(package.co_signers.items) == 0
    assert package.co_signers.has_more is False
    assert package.escalation_history.co_signer_count_at_escalation == 0


@pytest.mark.asyncio
async def test_get_decision_package_high_cosigner_count(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test decision package with very high co-signer count (Story 6.2, NFR-2.2).

    Verifies:
    - Service handles high co-signer counts (100k+ possible)
    - Total count accurately reported
    - No performance degradation
    """
    # Arrange - Petition with 100k+ co-signers
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.CESSATION,
        text="High-volume petition",
        submitter_id=uuid4(),
        state=PetitionState.ESCALATED,
        realm="governance",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        co_signer_count=150_000,
        escalation_source="CO_SIGNER_THRESHOLD",
        escalated_at=datetime.utcnow(),
        escalated_to_realm="governance",
    )
    await petition_repository.save(petition)

    # Act
    package = await decision_package_service.get_decision_package(
        petition_id=petition.id,
        king_realm="governance",
    )

    # Assert
    assert package.co_signers.total_count == 150_000
    assert package.escalation_history.co_signer_count_at_escalation == 150_000


@pytest.mark.asyncio
async def test_get_decision_package_anonymous_submitter(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test decision package with anonymous submitter (Story 6.2, AC2).

    Verifies:
    - Anonymous petitions supported (submitter_id is None)
    - Hash generated for None submitter
    - No errors on missing submitter
    """
    # Arrange - Anonymous petition
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GRIEVANCE,
        text="Anonymous grievance",
        submitter_id=None,  # Anonymous
        state=PetitionState.ESCALATED,
        realm="governance",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        co_signer_count=75,
        escalation_source="CO_SIGNER_THRESHOLD",
        escalated_at=datetime.utcnow(),
        escalated_to_realm="governance",
    )
    await petition_repository.save(petition)

    # Act
    package = await decision_package_service.get_decision_package(
        petition_id=petition.id,
        king_realm="governance",
    )

    # Assert
    assert len(package.submitter_metadata.public_key_hash) == 64
    assert package.submitter_metadata.public_key_hash.isalnum()


# =============================================================================
# Constitutional Compliance Tests
# =============================================================================


@pytest.mark.asyncio
async def test_realm_scoped_access_enforcement(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test RULING-3: Realm-scoped data access (Story 6.2, RULING-3).

    Verifies:
    - Kings can only access escalations for their realm
    - Different realms are properly isolated
    - Realm boundaries are enforced
    """
    # Arrange - Create petitions in different realms
    governance_petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Governance realm petition",
        submitter_id=uuid4(),
        state=PetitionState.ESCALATED,
        realm="governance",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        co_signer_count=100,
        escalation_source="CO_SIGNER_THRESHOLD",
        escalated_at=datetime.utcnow(),
        escalated_to_realm="governance",
    )

    security_petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Security realm petition",
        submitter_id=uuid4(),
        state=PetitionState.ESCALATED,
        realm="security",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        co_signer_count=100,
        escalation_source="CO_SIGNER_THRESHOLD",
        escalated_at=datetime.utcnow(),
        escalated_to_realm="security",
    )

    await petition_repository.save(governance_petition)
    await petition_repository.save(security_petition)

    # Act & Assert - Governance King can access governance petition
    governance_package = await decision_package_service.get_decision_package(
        petition_id=governance_petition.id,
        king_realm="governance",
    )
    assert governance_package.petition_id == governance_petition.id

    # Act & Assert - Governance King CANNOT access security petition
    with pytest.raises(RealmMismatchError):
        await decision_package_service.get_decision_package(
            petition_id=security_petition.id,
            king_realm="governance",  # Wrong realm
        )

    # Act & Assert - Security King can access security petition
    security_package = await decision_package_service.get_decision_package(
        petition_id=security_petition.id,
        king_realm="security",
    )
    assert security_package.petition_id == security_petition.id


@pytest.mark.asyncio
async def test_fr_5_4_complete_escalation_context(
    decision_package_service: EscalationDecisionPackageService,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test FR-5.4: King receives complete escalation context (Story 6.2, FR-5.4).

    Verifies:
    - Petition core data included (text, type, submitter)
    - Co-signer information included (count)
    - Escalation history included (source, timestamp, count at escalation)
    - All required fields populated
    """
    # Arrange
    await petition_repository.save(escalated_petition)

    # Act
    package = await decision_package_service.get_decision_package(
        petition_id=escalated_petition.id,
        king_realm="governance",
    )

    # Assert - Petition core data
    assert package.petition_id is not None
    assert package.petition_type is not None
    assert package.petition_content is not None

    # Assert - Submitter metadata
    assert package.submitter_metadata is not None
    assert package.submitter_metadata.public_key_hash is not None
    assert package.submitter_metadata.submitted_at is not None

    # Assert - Co-signer information
    assert package.co_signers is not None
    assert package.co_signers.total_count >= 0
    assert package.co_signers.items is not None

    # Assert - Escalation history
    assert package.escalation_history is not None
    assert package.escalation_history.escalation_source is not None
    assert package.escalation_history.escalated_at is not None
    assert package.escalation_history.co_signer_count_at_escalation >= 0
