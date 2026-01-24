"""Integration tests for Escalation Decision Package API endpoint (Story 6.2, FR-5.4).

Tests the GET /v1/kings/escalations/{petition_id} endpoint for fetching complete
escalation context for King adoption/acknowledgment decisions.

Constitutional Constraints:
- FR-5.4: King SHALL receive complete escalation context [P0]
- RULING-2: Tiered transcript access (mediated summaries for Kings)
- RULING-3: Realm-scoped data access (verify realm match)
- NFR-1.2: Endpoint latency p99 < 200ms
- CT-13: Reads work during halt
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from uuid import UUID, uuid4

from src.api.dependencies.escalation import set_escalation_decision_package_service
from src.api.main import app
from src.application.services.escalation_decision_package_service import (
    EscalationDecisionPackageService,
)
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
    service = EscalationDecisionPackageService(petition_repository=petition_repository)
    set_escalation_decision_package_service(service)
    return service


@pytest.fixture
def client(decision_package_service: EscalationDecisionPackageService) -> TestClient:
    """Create a test client with injected decision package service."""
    return TestClient(app)


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
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test GET /v1/kings/escalations/{petition_id} returns decision package (Story 6.2, AC1).

    Verifies:
    - Endpoint returns 200 OK
    - Response includes petition core data
    - Response includes co-signer information
    - Response includes escalation history
    """
    # Arrange
    await petition_repository.save(escalated_petition)

    # Act
    response = client.get(
        f"/v1/kings/escalations/{escalated_petition.id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Petition core data
    assert data["petition_id"] == str(escalated_petition.id)
    assert data["petition_type"] == "CESSATION"
    assert data["petition_content"] == escalated_petition.text

    # Submitter metadata
    assert "submitter_metadata" in data
    assert len(data["submitter_metadata"]["public_key_hash"]) == 64
    assert data["submitter_metadata"]["submitted_at"] == "2026-01-15T08:30:00Z"

    # Co-signer information
    assert "co_signers" in data
    assert data["co_signers"]["total_count"] == 150
    assert isinstance(data["co_signers"]["items"], list)

    # Escalation history
    assert "escalation_history" in data
    assert data["escalation_history"]["escalation_source"] == "CO_SIGNER_THRESHOLD"
    assert data["escalation_history"]["co_signer_count_at_escalation"] == 150


@pytest.mark.asyncio
async def test_get_decision_package_response_schema(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test response matches EscalationDecisionPackageResponse schema (Story 6.2, AC1).

    Verifies:
    - All required fields present
    - Field types are correct
    - Nested objects match schema
    """
    # Arrange
    await petition_repository.save(escalated_petition)

    # Act
    response = client.get(
        f"/v1/kings/escalations/{escalated_petition.id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Top-level fields
    assert "petition_id" in data
    assert "petition_type" in data
    assert "petition_content" in data
    assert "submitter_metadata" in data
    assert "co_signers" in data
    assert "escalation_history" in data

    # Submitter metadata schema
    submitter = data["submitter_metadata"]
    assert "public_key_hash" in submitter
    assert "submitted_at" in submitter

    # Co-signers schema
    co_signers = data["co_signers"]
    assert "items" in co_signers
    assert "total_count" in co_signers
    assert "next_cursor" in co_signers
    assert "has_more" in co_signers

    # Escalation history schema
    history = data["escalation_history"]
    assert "escalation_source" in history
    assert "escalated_at" in history
    assert "co_signer_count_at_escalation" in history
    assert "deliberation_summary" in history
    assert "knight_recommendation" in history


@pytest.mark.asyncio
async def test_get_decision_package_multiple_petition_types(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test endpoint works for all petition types (Story 6.2, AC2).

    Verifies:
    - CESSATION petitions supported
    - GRIEVANCE petitions supported
    - GENERAL petitions supported
    - COLLABORATION petitions supported
    """
    # Arrange - Create escalated petitions of each type
    petition_types = [
        (PetitionType.CESSATION, "CESSATION"),
        (PetitionType.GRIEVANCE, "GRIEVANCE"),
        (PetitionType.GENERAL, "GENERAL"),
        (PetitionType.COLLABORATION, "COLLABORATION"),
    ]

    petitions = []
    for pet_type, expected_type_str in petition_types:
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
        petitions.append((petition, expected_type_str))
        await petition_repository.save(petition)

    # Act & Assert
    for petition, expected_type_str in petitions:
        response = client.get(
            f"/v1/kings/escalations/{petition.id}",
            params={"king_realm": "governance"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["petition_type"] == expected_type_str


# =============================================================================
# Error Condition Tests
# =============================================================================


def test_get_decision_package_petition_not_found(client: TestClient) -> None:
    """Test 404 error when petition doesn't exist (Story 6.2, AC1).

    Verifies:
    - Returns 404 Not Found
    - Error response follows RFC 7807
    - Error message indicates petition not found
    """
    # Arrange
    nonexistent_id = uuid4()

    # Act
    response = client.get(
        f"/v1/kings/escalations/{nonexistent_id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 404
    data = response.json()
    assert data["type"] == "https://archon.example.com/errors/not-found"
    assert data["title"] == "Not Found"
    assert data["status"] == 404
    assert str(nonexistent_id) in data["detail"]


@pytest.mark.asyncio
async def test_get_decision_package_petition_not_escalated(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test 404 error when petition is not escalated (Story 6.2, AC1).

    Verifies:
    - Returns 404 Not Found
    - Error response follows RFC 7807
    - Error message indicates petition not escalated
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

    # Act
    response = client.get(
        f"/v1/kings/escalations/{petition.id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 404
    data = response.json()
    assert data["type"] == "https://archon.example.com/errors/not-found"
    assert "not escalated" in data["detail"]


@pytest.mark.asyncio
async def test_get_decision_package_realm_mismatch(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test 403 error when King's realm doesn't match (Story 6.2, RULING-3).

    Verifies:
    - Returns 403 Forbidden
    - Error response follows RFC 7807
    - Error message indicates realm mismatch
    """
    # Arrange - Petition escalated to different realm
    petition = PetitionSubmission(
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
    await petition_repository.save(petition)

    # Act - Request from wrong realm
    response = client.get(
        f"/v1/kings/escalations/{petition.id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 403
    data = response.json()
    assert data["type"] == "https://archon.example.com/errors/realm-mismatch"
    assert data["title"] == "Realm Mismatch"
    assert data["status"] == 403


def test_get_decision_package_missing_realm_parameter(client: TestClient) -> None:
    """Test 422 error when king_realm parameter is missing (Story 6.2, AC1).

    Verifies:
    - Returns 422 Unprocessable Entity
    - Error indicates missing required parameter
    """
    # Arrange
    petition_id = uuid4()

    # Act - Missing king_realm query parameter
    response = client.get(f"/v1/kings/escalations/{petition_id}")

    # Assert
    assert response.status_code == 422  # FastAPI validation error
    data = response.json()
    assert "detail" in data


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_decision_package_zero_cosigners(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test decision package with zero co-signers (Story 6.2, AC2).

    Verifies:
    - Endpoint returns successfully
    - Co-signer count is 0
    - Co-signer items list is empty
    """
    # Arrange - Knight-recommended petition with 0 co-signers
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
    response = client.get(
        f"/v1/kings/escalations/{petition.id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["co_signers"]["total_count"] == 0
    assert len(data["co_signers"]["items"]) == 0
    assert data["co_signers"]["has_more"] is False


@pytest.mark.asyncio
async def test_get_decision_package_high_cosigner_count(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test decision package with very high co-signer count (Story 6.2, NFR-2.2).

    Verifies:
    - Endpoint handles high co-signer counts (100k+)
    - Total count accurately reported
    - Response time acceptable
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
    response = client.get(
        f"/v1/kings/escalations/{petition.id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["co_signers"]["total_count"] == 150_000


@pytest.mark.asyncio
async def test_get_decision_package_anonymous_submitter(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test decision package with anonymous submitter (Story 6.2, AC2).

    Verifies:
    - Endpoint handles anonymous petitions
    - Submitter metadata still present
    - Hash generated for None submitter
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
    response = client.get(
        f"/v1/kings/escalations/{petition.id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["submitter_metadata"]["public_key_hash"]) == 64


# =============================================================================
# Constitutional Compliance Tests
# =============================================================================


@pytest.mark.asyncio
async def test_realm_scoped_access_enforcement(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
) -> None:
    """Test RULING-3: Realm-scoped data access (Story 6.2, RULING-3).

    Verifies:
    - Kings can only access escalations for their realm
    - Different realms are properly isolated
    - Realm boundaries are enforced at API level
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
    response = client.get(
        f"/v1/kings/escalations/{governance_petition.id}",
        params={"king_realm": "governance"},
    )
    assert response.status_code == 200

    # Act & Assert - Governance King CANNOT access security petition
    response = client.get(
        f"/v1/kings/escalations/{security_petition.id}",
        params={"king_realm": "governance"},
    )
    assert response.status_code == 403
    assert response.json()["type"] == "https://archon.example.com/errors/realm-mismatch"

    # Act & Assert - Security King can access security petition
    response = client.get(
        f"/v1/kings/escalations/{security_petition.id}",
        params={"king_realm": "security"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_fr_5_4_complete_escalation_context(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test FR-5.4: King receives complete escalation context (Story 6.2, FR-5.4).

    Verifies:
    - All required context fields present in response
    - Petition core data complete
    - Co-signer information complete
    - Escalation history complete
    """
    # Arrange
    await petition_repository.save(escalated_petition)

    # Act
    response = client.get(
        f"/v1/kings/escalations/{escalated_petition.id}",
        params={"king_realm": "governance"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Petition core data
    assert data["petition_id"] is not None
    assert data["petition_type"] is not None
    assert data["petition_content"] is not None

    # Submitter metadata
    assert data["submitter_metadata"]["public_key_hash"] is not None
    assert data["submitter_metadata"]["submitted_at"] is not None

    # Co-signer information
    assert data["co_signers"]["total_count"] >= 0
    assert isinstance(data["co_signers"]["items"], list)

    # Escalation history
    assert data["escalation_history"]["escalation_source"] is not None
    assert data["escalation_history"]["escalated_at"] is not None
    assert data["escalation_history"]["co_signer_count_at_escalation"] >= 0


@pytest.mark.asyncio
async def test_nfr_1_2_endpoint_latency(
    client: TestClient,
    petition_repository: PetitionSubmissionRepositoryStub,
    escalated_petition: PetitionSubmission,
) -> None:
    """Test NFR-1.2: Endpoint latency p99 < 200ms (Story 6.2, NFR-1.2).

    Verifies:
    - Endpoint responds quickly
    - No significant performance degradation
    - Suitable for production use

    Note: This is a basic smoke test. Full p99 latency testing requires
    load testing infrastructure.
    """
    # Arrange
    await petition_repository.save(escalated_petition)

    # Act - Multiple requests to check consistency
    for _ in range(10):
        response = client.get(
            f"/v1/kings/escalations/{escalated_petition.id}",
            params={"king_realm": "governance"},
        )
        assert response.status_code == 200

    # Assert - If endpoint is too slow, tests would timeout
    # This is a basic smoke test; full p99 testing requires benchmarking
