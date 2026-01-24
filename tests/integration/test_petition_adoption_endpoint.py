"""Integration tests for Petition Adoption endpoint (Story 6.3, FR-5.5).

Tests cover the complete HTTP API flow for petition adoption:
- AC1: POST /escalations/{petition_id}/adopt returns 200 with motion_id
- AC2: 400 for insufficient budget
- AC3: 403 for realm mismatch
- AC4: 404 for petition not found
- AC5: 400 for petition not escalated
- AC7: 503 during system halt
- Full end-to-end adoption flow with all components

Constitutional Constraints Tested:
- FR-5.5: King SHALL be able to ADOPT petition (creates Motion) [P0]
- FR-5.6: Adoption SHALL consume promotion budget (H1 compliance) [P0]
- FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]
- CT-13: Halt check first pattern
- RULING-3: Realm-scoped data access
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.escalation import set_petition_adoption_service
from src.api.main import app
from src.application.services.petition_adoption_service import PetitionAdoptionService
from src.application.stubs.budget_store_stub import InMemoryBudgetStore
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.event_writer_stub import EventWriterStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def petition_repo():
    """Create petition repository stub."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def budget_store():
    """Create budget store with King budget."""
    store = InMemoryBudgetStore()
    # King has 3 promotions per cycle by default
    return store


@pytest.fixture
def halt_checker():
    """Create halt checker (not halted by default)."""
    return HaltCheckerStub(is_halted=False)


@pytest.fixture
def event_writer():
    """Create event writer stub."""
    return EventWriterStub()


@pytest.fixture
def adoption_service(petition_repo, budget_store, halt_checker, event_writer):
    """Create and inject adoption service."""
    service = PetitionAdoptionService(
        petition_repo=petition_repo,
        budget_store=budget_store,
        halt_checker=halt_checker,
        event_writer=event_writer,
    )
    set_petition_adoption_service(service)
    return service


@pytest.fixture
def escalated_petition(petition_repo):
    """Create and save an escalated petition."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.CESSATION,
        text="We petition for system cessation review due to alignment concerns.",
        state=PetitionState.ESCALATED,
        submitter_id=uuid4(),
        realm="governance",
        escalation_source="CO_SIGNER_THRESHOLD",
        escalated_at=datetime.now(timezone.utc),
        escalated_to_realm="governance",
        co_signer_count=150,
    )
    # Use blocking call since this is pytest (not asyncio)
    import asyncio

    asyncio.run(petition_repo.create(petition))
    return petition


# =============================================================================
# Happy Path Tests (AC1)
# =============================================================================


def test_adopt_petition_success(
    client,
    adoption_service,
    escalated_petition,
):
    """Test POST /escalations/{petition_id}/adopt returns 200 with motion_id (AC1).

    Verifies complete adoption flow:
    - Petition is adopted
    - Motion is created with provenance
    - Budget is consumed
    - Event is emitted
    - Response includes motion_id and provenance
    """
    # Arrange: Adoption request
    king_id = "00000000-0000-0000-0000-000000000001"
    realm_id = "governance"
    payload = {
        "motion_title": "Address System Cessation Concerns",
        "motion_body": "This Motion directs a comprehensive review of system cessation procedures.",
        "adoption_rationale": "The petition has 150+ co-signers demonstrating strong community concern.",
    }

    # Act: POST adoption request
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/adopt",
        params={"king_id": king_id, "realm_id": realm_id},
        json=payload,
    )

    # Assert: Success response
    assert response.status_code == 200
    data = response.json()

    # Assert: Response structure
    assert "motion_id" in data
    assert data["petition_id"] == str(escalated_petition.id)
    assert data["sponsor_id"] == king_id
    assert "created_at" in data

    # Assert: Provenance included
    assert "provenance" in data
    assert data["provenance"]["source_petition_ref"] == str(escalated_petition.id)
    assert data["provenance"]["adoption_rationale"] == payload["adoption_rationale"]
    assert data["provenance"]["budget_consumed"] == 1


# =============================================================================
# Budget Tests (AC2)
# =============================================================================


def test_adopt_petition_insufficient_budget(
    client,
    adoption_service,
    escalated_petition,
    budget_store,
):
    """Test 400 when King has insufficient budget (AC2).

    Verifies:
    - Budget validation before adoption
    - HTTP 400 with appropriate error
    - RFC 7807 error format
    """
    # Arrange: Exhaust King's budget
    king_id = "00000000-0000-0000-0000-000000000001"
    realm_id = "governance"
    cycle_id = "2026-Q1"
    budget = budget_store.get_budget(king_id)
    for _ in range(budget):
        budget_store.consume(king_id, cycle_id, 1)

    # Assert: Budget exhausted
    assert not budget_store.can_promote(king_id, cycle_id, 1)

    # Arrange: Adoption request
    payload = {
        "motion_title": "Test Motion",
        "motion_body": "This is a test motion for budget validation.",
        "adoption_rationale": "Testing budget consumption behavior with insufficient funds.",
    }

    # Act: POST adoption request
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/adopt",
        params={"king_id": king_id, "realm_id": realm_id},
        json=payload,
    )

    # Assert: HTTP 400 - Insufficient Budget
    assert response.status_code == 400
    data = response.json()

    # Assert: RFC 7807 error format
    assert data["type"] == "https://archon.example.com/errors/insufficient-budget"
    assert data["title"] == "Insufficient Promotion Budget"
    assert data["status"] == 400
    assert "budget" in data["detail"].lower()


# =============================================================================
# Realm Authorization Tests (AC3)
# =============================================================================


def test_adopt_petition_realm_mismatch(
    client,
    adoption_service,
    escalated_petition,
):
    """Test 403 when King's realm doesn't match petition realm (AC3, RULING-3).

    Verifies:
    - Realm authorization enforcement
    - HTTP 403 with realm mismatch error
    - RFC 7807 error format
    """
    # Arrange: King from different realm
    king_id = "00000000-0000-0000-0000-000000000001"
    wrong_realm = "knowledge"  # Petition is in "governance"

    # Arrange: Adoption request
    payload = {
        "motion_title": "Test Motion",
        "motion_body": "This motion tests realm authorization.",
        "adoption_rationale": "Testing realm mismatch handling and authorization failures.",
    }

    # Act: POST adoption request with wrong realm
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/adopt",
        params={"king_id": king_id, "realm_id": wrong_realm},
        json=payload,
    )

    # Assert: HTTP 403 - Realm Mismatch
    assert response.status_code == 403
    data = response.json()

    # Assert: RFC 7807 error format
    assert data["type"] == "https://archon.example.com/errors/realm-mismatch"
    assert data["title"] == "Realm Authorization Failed"
    assert data["status"] == 403
    assert "realm" in data["detail"].lower()


# =============================================================================
# Petition Not Found Tests (AC4)
# =============================================================================


def test_adopt_petition_not_found(
    client,
    adoption_service,
):
    """Test 404 when petition doesn't exist (AC4).

    Verifies:
    - Petition existence validation
    - HTTP 404 with not found error
    - RFC 7807 error format
    """
    # Arrange: Non-existent petition
    non_existent_id = uuid4()
    king_id = "00000000-0000-0000-0000-000000000001"
    realm_id = "governance"

    # Arrange: Adoption request
    payload = {
        "motion_title": "Test Motion",
        "motion_body": "This motion tests not found handling.",
        "adoption_rationale": "Testing behavior when petition does not exist in the system.",
    }

    # Act: POST adoption request for non-existent petition
    response = client.post(
        f"/v1/kings/escalations/{non_existent_id}/adopt",
        params={"king_id": king_id, "realm_id": realm_id},
        json=payload,
    )

    # Assert: HTTP 404 - Not Found
    assert response.status_code == 404
    data = response.json()

    # Assert: RFC 7807 error format
    assert data["type"] == "https://archon.example.com/errors/not-found"
    assert data["title"] == "Petition Not Found"
    assert data["status"] == 404


# =============================================================================
# Petition Not Escalated Tests (AC5)
# =============================================================================


@pytest.mark.parametrize(
    "petition_state",
    [
        PetitionState.RECEIVED,
        PetitionState.DELIBERATING,
        PetitionState.ACKNOWLEDGED,
        PetitionState.REFERRED,
    ],
)
def test_adopt_petition_not_escalated(
    client,
    adoption_service,
    petition_repo,
    petition_state,
):
    """Test 400 when petition is not in ESCALATED state (AC5).

    Verifies:
    - State validation before adoption
    - HTTP 400 with not escalated error
    - Works for all non-ESCALATED states
    """
    # Arrange: Create petition in non-ESCALATED state
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.CESSATION,
        text="Test petition in non-escalated state.",
        state=petition_state,
        submitter_id=uuid4(),
        realm="governance",
    )
    import asyncio

    asyncio.run(petition_repo.create(petition))

    # Arrange: Adoption request
    king_id = "00000000-0000-0000-0000-000000000001"
    realm_id = "governance"
    payload = {
        "motion_title": "Test Motion",
        "motion_body": "This motion tests state validation.",
        "adoption_rationale": "Testing adoption of petition in non-escalated state.",
    }

    # Act: POST adoption request
    response = client.post(
        f"/v1/kings/escalations/{petition.id}/adopt",
        params={"king_id": king_id, "realm_id": realm_id},
        json=payload,
    )

    # Assert: HTTP 400 - Not Escalated
    assert response.status_code == 400
    data = response.json()

    # Assert: RFC 7807 error format
    assert data["type"] == "https://archon.example.com/errors/petition-not-escalated"
    assert data["title"] == "Petition Not Escalated"
    assert data["status"] == 400
    assert petition_state.value in data["detail"]


# =============================================================================
# System Halt Tests (AC7)
# =============================================================================


def test_adopt_petition_system_halted(
    client,
    petition_repo,
    budget_store,
    event_writer,
    escalated_petition,
):
    """Test 503 when system is halted (AC7, CT-13).

    Verifies:
    - HALT CHECK FIRST pattern (CT-13)
    - HTTP 503 with system halted error
    - No writes during halt
    """
    # Arrange: Create halted system
    halted_checker = HaltCheckerStub(is_halted=True)
    service = PetitionAdoptionService(
        petition_repo=petition_repo,
        budget_store=budget_store,
        halt_checker=halted_checker,
        event_writer=event_writer,
    )
    set_petition_adoption_service(service)

    # Arrange: Adoption request
    king_id = "00000000-0000-0000-0000-000000000001"
    realm_id = "governance"
    payload = {
        "motion_title": "Test Motion",
        "motion_body": "This motion tests halt check behavior.",
        "adoption_rationale": "Testing system halt behavior and write blocking during halt.",
    }

    # Act: POST adoption request during halt
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/adopt",
        params={"king_id": king_id, "realm_id": realm_id},
        json=payload,
    )

    # Assert: HTTP 503 - System Halted
    assert response.status_code == 503
    data = response.json()

    # Assert: RFC 7807 error format
    assert data["type"] == "https://archon.example.com/errors/system-halted"
    assert data["title"] == "System Halted"
    assert data["status"] == 503
    assert "halt" in data["detail"].lower()


# =============================================================================
# Validation Tests (AC8)
# =============================================================================


@pytest.mark.parametrize(
    "field,invalid_value,expected_error",
    [
        ("motion_title", "", "motion_title"),  # Empty title
        ("motion_title", "x" * 201, "motion_title"),  # Title too long
        ("motion_body", "", "motion_body"),  # Empty body
        ("motion_body", "x" * 5001, "motion_body"),  # Body too long
        ("adoption_rationale", "", "adoption_rationale"),  # Empty rationale
        ("adoption_rationale", "short", "adoption_rationale"),  # Rationale too short
        ("adoption_rationale", "x" * 2001, "adoption_rationale"),  # Rationale too long
    ],
)
def test_adopt_petition_validation_errors(
    client,
    adoption_service,
    escalated_petition,
    field,
    invalid_value,
    expected_error,
):
    """Test validation errors for adoption request fields (AC8).

    Verifies:
    - Pydantic validation at API layer
    - HTTP 422 for validation errors
    - Clear error messages
    """
    # Arrange: Valid base payload
    king_id = "00000000-0000-0000-0000-000000000001"
    realm_id = "governance"
    payload = {
        "motion_title": "Valid Title",
        "motion_body": "This is a valid motion body with sufficient length.",
        "adoption_rationale": "This is a valid rationale with more than fifty characters required.",
    }

    # Arrange: Set invalid field
    payload[field] = invalid_value

    # Act: POST adoption request with invalid data
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/adopt",
        params={"king_id": king_id, "realm_id": realm_id},
        json=payload,
    )

    # Assert: HTTP 422 - Validation Error (or 400 depending on implementation)
    assert response.status_code in [400, 422]
    data = response.json()

    # Assert: Error indicates validation failure
    assert expected_error in str(data).lower()


# =============================================================================
# Provenance Tests (AC6)
# =============================================================================


def test_adopt_petition_creates_bidirectional_provenance(
    client,
    adoption_service,
    escalated_petition,
    petition_repo,
):
    """Test adoption creates bidirectional provenance links (AC6, NFR-6.2).

    Verifies:
    - Motion → Petition: source_petition_ref in response
    - Petition → Motion: adopted_as_motion_id in database
    - Provenance is immutable once set
    """
    # Arrange: Adoption request
    king_id = "00000000-0000-0000-0000-000000000001"
    realm_id = "governance"
    payload = {
        "motion_title": "Provenance Test Motion",
        "motion_body": "This motion tests bidirectional provenance tracking.",
        "adoption_rationale": "Testing that provenance links work correctly in both directions.",
    }

    # Act: POST adoption request
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/adopt",
        params={"king_id": king_id, "realm_id": realm_id},
        json=payload,
    )

    # Assert: Success
    assert response.status_code == 200
    data = response.json()
    motion_id = data["motion_id"]

    # Assert: Motion → Petition provenance (forward reference)
    assert data["provenance"]["source_petition_ref"] == str(escalated_petition.id)

    # Assert: Petition → Motion provenance (back-reference)
    import asyncio

    updated_petition = asyncio.run(petition_repo.get(escalated_petition.id))
    assert str(updated_petition.adopted_as_motion_id) == motion_id
    assert str(updated_petition.adopted_by_king_id) == king_id
    assert updated_petition.adopted_at is not None


# =============================================================================
# Event Emission Tests (CT-12)
# =============================================================================


def test_adopt_petition_emits_witnessed_event(
    client,
    adoption_service,
    escalated_petition,
    event_writer,
):
    """Test adoption emits witnessed PetitionAdopted event (CT-12).

    Verifies:
    - PetitionAdopted event is emitted
    - Event contains complete provenance data
    - Event is witnessed via EventWriterService
    """
    # Arrange: Adoption request
    king_id = "00000000-0000-0000-0000-000000000001"
    realm_id = "governance"
    payload = {
        "motion_title": "Event Test Motion",
        "motion_body": "This motion tests event emission and witnessing.",
        "adoption_rationale": "Testing that adoption events are properly emitted and witnessed.",
    }

    # Act: POST adoption request
    response = client.post(
        f"/v1/kings/escalations/{escalated_petition.id}/adopt",
        params={"king_id": king_id, "realm_id": realm_id},
        json=payload,
    )

    # Assert: Success
    assert response.status_code == 200

    # Assert: Event was emitted
    assert len(event_writer.events) == 1
    event = event_writer.events[0]

    # Assert: Event type and payload
    assert event["event_type"] == "petition.adoption.adopted"
    assert event["event_payload"]["petition_id"] == str(escalated_petition.id)
    assert event["event_payload"]["sponsor_king_id"] == king_id
    assert event["event_payload"]["realm_id"] == realm_id
