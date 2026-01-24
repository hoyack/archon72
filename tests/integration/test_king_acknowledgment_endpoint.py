"""Integration tests for King Acknowledgment API endpoint (Story 6.5, FR-5.8).

Tests the POST /v1/kings/escalations/{petition_id}/acknowledge endpoint for
Kings to formally acknowledge escalated petitions with rationale.

Constitutional Constraints:
- FR-5.8: King SHALL be able to ACKNOWLEDGE escalation (with rationale) [P0]
- Story 6.5 AC2: Rationale must be >= 100 characters
- Story 6.5 AC3: Petition must be in ESCALATED state
- Story 6.5 AC4: Realm authorization (King's realm must match petition's realm)
- CT-13: Halt check first pattern (handled by service)
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.escalation import set_acknowledgment_execution_service
from src.api.main import app
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.acknowledgment_execution_stub import (
    AcknowledgmentExecutionStub,
)
from src.infrastructure.stubs.content_hash_stub import ContentHashStub
from src.infrastructure.stubs.event_writer_stub import EventWriterStub
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
def event_writer() -> EventWriterStub:
    """Create an event writer stub for testing."""
    return EventWriterStub()


@pytest.fixture
def hash_service() -> ContentHashStub:
    """Create a content hash stub for testing."""
    return ContentHashStub()


@pytest.fixture
def acknowledgment_service(
    petition_repository: PetitionSubmissionRepositoryStub,
    event_writer: EventWriterStub,
    hash_service: ContentHashStub,
) -> AcknowledgmentExecutionStub:
    """Create an acknowledgment execution service stub."""
    stub = AcknowledgmentExecutionStub()
    # Inject the petition repository's storage into the stub
    # This is a bit of a hack for testing, but allows us to use the real repo
    for petition_id, petition in petition_repository._submissions.items():
        stub.add_petition(petition)
    set_acknowledgment_execution_service(stub)
    return stub


@pytest.fixture
def client(acknowledgment_service: AcknowledgmentExecutionStub) -> TestClient:
    """Create a test client with injected acknowledgment service."""
    return TestClient(app)


@pytest.fixture
def king_id() -> UUID:
    """King UUID for tests."""
    return uuid4()


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


@pytest.fixture
def valid_rationale() -> str:
    """Valid King rationale (>= 100 chars)."""
    return (
        "I have carefully reviewed this petition and the concerns raised by "
        "the co-signers. While I appreciate their dedication to system governance, "
        "the specific concerns have been addressed in recent policy updates."
    )


@pytest.fixture
def valid_request(valid_rationale: str) -> dict:
    """Valid King acknowledgment request body."""
    return {
        "reason_code": "NOTED",
        "rationale": valid_rationale,
    }


# =============================================================================
# Happy Path Tests
# =============================================================================


@pytest.mark.asyncio
async def test_acknowledge_escalation_success(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
    valid_request: dict,
) -> None:
    """Test POST /v1/kings/escalations/{petition_id}/acknowledge returns 200 (Story 6.5 AC1).

    Verifies:
    - Endpoint returns 200 OK
    - Response includes acknowledgment_id
    - Response includes king_id
    - Acknowledgment is persisted
    """
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=valid_request,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert "acknowledgment_id" in data
    assert data["petition_id"] == str(escalated_petition.id)
    assert data["king_id"] == str(king_id)
    assert data["reason_code"] == "NOTED"
    assert data["realm_id"] == "governance"
    assert "acknowledged_at" in data

    # Verify acknowledgment was persisted
    assert acknowledgment_service.was_executed(escalated_petition.id)


@pytest.mark.asyncio
async def test_acknowledge_escalation_response_schema(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
    valid_request: dict,
) -> None:
    """Test response matches KingAcknowledgmentResponse schema (Story 6.5 AC1).

    Verifies:
    - All required fields present
    - Field types are correct
    - UUIDs are valid
    - Timestamps are ISO 8601 UTC
    """
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=valid_request,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Required fields
    required_fields = [
        "acknowledgment_id",
        "petition_id",
        "king_id",
        "reason_code",
        "acknowledged_at",
        "realm_id",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    # UUID fields are valid
    UUID(data["acknowledgment_id"])
    UUID(data["petition_id"])
    UUID(data["king_id"])

    # Timestamp is ISO 8601
    datetime.fromisoformat(data["acknowledged_at"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_acknowledge_with_out_of_scope_reason(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
    valid_rationale: str,
) -> None:
    """Test King acknowledgment with OUT_OF_SCOPE reason (Story 6.5 AC1)."""
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)
    request_body = {
        "reason_code": "OUT_OF_SCOPE",
        "rationale": valid_rationale,
    }

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=request_body,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["reason_code"] == "OUT_OF_SCOPE"


# =============================================================================
# Rationale Validation Tests (Story 6.5 AC2)
# =============================================================================


@pytest.mark.asyncio
async def test_rationale_too_short_returns_422(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
) -> None:
    """Test rationale < 100 chars returns 422 (Story 6.5 AC2)."""
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)
    request_body = {
        "reason_code": "NOTED",
        "rationale": "Too short",  # < 100 chars
    }

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=request_body,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 422
    data = response.json()
    assert any(
        "rationale" in ".".join(str(loc) for loc in err.get("loc", []))
        for err in data.get("detail", [])
    )


@pytest.mark.asyncio
async def test_rationale_exactly_100_chars_succeeds(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
) -> None:
    """Test rationale with exactly 100 chars succeeds (Story 6.5 AC2)."""
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)
    rationale_100 = "X" * 100
    request_body = {
        "reason_code": "NOTED",
        "rationale": rationale_100,
    }

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=request_body,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 200


# =============================================================================
# Petition State Validation Tests (Story 6.5 AC3)
# =============================================================================


@pytest.mark.asyncio
async def test_acknowledge_deliberating_petition_returns_400(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    king_id: UUID,
    valid_request: dict,
) -> None:
    """Test cannot acknowledge DELIBERATING petition (Story 6.5 AC3)."""
    # Arrange
    deliberating_petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test deliberating petition",
        submitter_id=uuid4(),
        state=PetitionState.DELIBERATING,
        realm="governance",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    acknowledgment_service.add_petition(deliberating_petition)

    # Act
    response = client.post(
        f"/v1/kings/escalations/{deliberating_petition.id}/acknowledge",
        json=valid_request,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 400
    data = response.json()
    assert "not escalated" in data["detail"].lower()
    assert "DELIBERATING" in data["detail"]


@pytest.mark.asyncio
async def test_acknowledge_received_petition_returns_400(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    king_id: UUID,
    valid_request: dict,
) -> None:
    """Test cannot acknowledge RECEIVED petition (Story 6.5 AC3)."""
    # Arrange
    received_petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test received petition",
        submitter_id=uuid4(),
        state=PetitionState.RECEIVED,
        realm="governance",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    acknowledgment_service.add_petition(received_petition)

    # Act
    response = client.post(
        f"/v1/kings/escalations/{received_petition.id}/acknowledge",
        json=valid_request,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 400
    data = response.json()
    assert "not escalated" in data["detail"].lower()


# =============================================================================
# Realm Authorization Tests (Story 6.5 AC4)
# =============================================================================


@pytest.mark.asyncio
async def test_realm_mismatch_returns_403(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
    valid_request: dict,
) -> None:
    """Test realm mismatch returns 403 (Story 6.5 AC4)."""
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)

    # Act - King from "knowledge" realm trying to acknowledge "governance" petition
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=valid_request,
        params={
            "king_id": str(king_id),
            "realm_id": "knowledge",  # Different realm
        },
    )

    # Assert
    assert response.status_code == 403
    data = response.json()
    assert "realm" in data["detail"].lower()
    assert "governance" in data["detail"].lower()
    assert "knowledge" in data["detail"].lower()


@pytest.mark.asyncio
async def test_matching_realm_succeeds(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    king_id: UUID,
    valid_rationale: str,
) -> None:
    """Test King can acknowledge petition from matching realm (Story 6.5 AC4)."""
    # Arrange
    security_petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.CESSATION,
        text="Test security petition",
        submitter_id=uuid4(),
        state=PetitionState.ESCALATED,
        realm="security",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        escalated_at=datetime.now(timezone.utc),
        escalated_to_realm="security",
    )
    acknowledgment_service.add_petition(security_petition)
    request_body = {
        "reason_code": "NOTED",
        "rationale": valid_rationale,
    }

    # Act
    response = client.post(
        f"/v1/kings/escalations/{security_petition.id}/acknowledge",
        json=request_body,
        params={
            "king_id": str(king_id),
            "realm_id": "security",  # Matching realm
        },
    )

    # Assert
    assert response.status_code == 200


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_petition_not_found_returns_404(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    king_id: UUID,
    valid_request: dict,
) -> None:
    """Test petition not found returns 404."""
    # Arrange
    nonexistent_id = uuid4()

    # Act
    response = client.post(
        f"/v1/kings/escalations/{nonexistent_id}/acknowledge",
        json=valid_request,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_reason_code_returns_400(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
    valid_rationale: str,
) -> None:
    """Test invalid reason code returns 400."""
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)
    request_body = {
        "reason_code": "INVALID_CODE",
        "rationale": valid_rationale,
    }

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=request_body,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 400
    data = response.json()
    assert "reason code" in data["detail"].lower()


@pytest.mark.asyncio
async def test_missing_king_id_returns_422(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    valid_request: dict,
) -> None:
    """Test missing king_id query param returns 422."""
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=valid_request,
        params={
            "realm_id": "governance",
            # king_id missing
        },
    )

    # Assert
    assert response.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_missing_realm_id_returns_422(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
    valid_request: dict,
) -> None:
    """Test missing realm_id query param returns 422."""
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=valid_request,
        params={
            "king_id": str(king_id),
            # realm_id missing
        },
    )

    # Assert
    assert response.status_code == 422  # FastAPI validation error


# =============================================================================
# Event Emission Tests (Story 6.5 AC7)
# =============================================================================


@pytest.mark.asyncio
async def test_king_acknowledged_escalation_event_emitted(
    client: TestClient,
    acknowledgment_service: AcknowledgmentExecutionStub,
    escalated_petition: PetitionSubmission,
    king_id: UUID,
    valid_request: dict,
) -> None:
    """Test KingAcknowledgedEscalation event is emitted (Story 6.5 AC7)."""
    # Arrange
    acknowledgment_service.add_petition(escalated_petition)

    # Act
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/acknowledge",
        json=valid_request,
        params={
            "king_id": str(king_id),
            "realm_id": "governance",
        },
    )

    # Assert
    assert response.status_code == 200

    # Verify event was emitted
    events = acknowledgment_service.get_emitted_events()
    king_ack_events = [
        e
        for e in events
        if "acknowledged_by_king" in e.get("event_type", "").lower()
    ]
    assert len(king_ack_events) == 1

    event = king_ack_events[0]
    assert event["petition_id"] == escalated_petition.id
    assert event["king_id"] == king_id
    assert event["reason_code"] == "NOTED"
    assert event["realm_id"] == "governance"
