"""Unit tests for petition submission API routes (Story 1.1, FR-1.1).

Tests the API endpoints for Three Fates petition submission.

Constitutional Compliance:
- FR-1.1: Accept petition submissions via REST API
- FR-1.2: Generate UUID petition_id
- FR-1.3: Validate petition schema
- FR-1.6: Set initial state to RECEIVED
- FR-10.1: Support GENERAL, CESSATION, GRIEVANCE, COLLABORATION types
- CT-11: Silent failure destroys legitimacy - fail loud on errors
- CT-13: Halt rejects writes, allows reads
"""

import base64
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.petition_submission import (
    reset_petition_submission_dependencies,
    set_halt_checker,
    set_petition_submission_repository,
    set_realm_registry,
)
from src.api.routes.petition_submission import router
from src.domain.models.petition_submission import (
    PetitionState,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.realm_registry_stub import RealmRegistryStub


@pytest.fixture(autouse=True)
def reset_dependencies():
    """Reset all DI singletons before each test."""
    reset_petition_submission_dependencies()
    yield
    reset_petition_submission_dependencies()


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_repository() -> PetitionSubmissionRepositoryStub:
    """Create mock petition submission repository."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def mock_halt_checker() -> HaltCheckerStub:
    """Create mock halt checker (not halted)."""
    return HaltCheckerStub()


@pytest.fixture
def mock_realm_registry() -> RealmRegistryStub:
    """Create mock realm registry with canonical realms."""
    return RealmRegistryStub(populate_canonical=True)


@pytest.fixture
def client(
    app: FastAPI,
    mock_repository: PetitionSubmissionRepositoryStub,
    mock_halt_checker: HaltCheckerStub,
    mock_realm_registry: RealmRegistryStub,
) -> TestClient:
    """Create test client with mock services."""
    set_petition_submission_repository(mock_repository)
    set_halt_checker(mock_halt_checker)
    set_realm_registry(mock_realm_registry)
    return TestClient(app)


class TestSubmitPetition:
    """Tests for POST /v1/petition-submissions."""

    def test_submit_general_petition_success(self, client: TestClient) -> None:
        """Submit a GENERAL petition successfully (FR-1.1, FR-1.6)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "This is a general petition about system behavior.",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "petition_id" in data
        assert data["state"] == "RECEIVED"
        assert data["type"] == "GENERAL"
        assert "content_hash" in data
        assert "realm" in data
        assert "created_at" in data
        # Validate UUID format
        UUID(data["petition_id"])
        # Validate content hash is base64
        base64.b64decode(data["content_hash"])

    def test_submit_cessation_petition_success(self, client: TestClient) -> None:
        """Submit a CESSATION petition successfully (FR-10.1)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "CESSATION",
                "text": "Request for system cessation review based on observed patterns.",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["state"] == "RECEIVED"
        assert data["type"] == "CESSATION"

    def test_submit_grievance_petition_success(self, client: TestClient) -> None:
        """Submit a GRIEVANCE petition successfully (FR-10.1)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GRIEVANCE",
                "text": "Complaint about system behavior in specific context.",
            },
        )

        assert response.status_code == 201
        assert response.json()["type"] == "GRIEVANCE"

    def test_submit_collaboration_petition_success(self, client: TestClient) -> None:
        """Submit a COLLABORATION petition successfully (FR-10.1)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "COLLABORATION",
                "text": "Request for inter-realm collaboration on shared concern.",
            },
        )

        assert response.status_code == 201
        assert response.json()["type"] == "COLLABORATION"

    def test_submit_with_realm_success(
        self, client: TestClient, mock_realm_registry: RealmRegistryStub
    ) -> None:
        """Submit petition with explicit realm (HP-3)."""
        # Get a valid realm name from the registry
        realms = mock_realm_registry.list_active_realms()
        assert len(realms) > 0
        realm_name = realms[0].name

        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for specific realm routing.",
                "realm": realm_name,
            },
        )

        assert response.status_code == 201
        assert response.json()["realm"] == realm_name

    def test_submit_invalid_type_rejected(self, client: TestClient) -> None:
        """Invalid petition type is rejected (FR-1.3)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "INVALID_TYPE",
                "text": "This should be rejected.",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_submit_empty_text_rejected(self, client: TestClient) -> None:
        """Empty text is rejected (FR-1.3)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_submit_whitespace_only_text_rejected(self, client: TestClient) -> None:
        """Whitespace-only text is rejected (FR-1.3)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "   \n\t   ",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_submit_text_too_long_rejected(self, client: TestClient) -> None:
        """Text > 10,000 chars is rejected (FR-1.3)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "x" * 10001,
            },
        )

        assert response.status_code == 422  # Validation error

    def test_submit_missing_type_rejected(self, client: TestClient) -> None:
        """Missing type field is rejected (FR-1.3)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "text": "This should be rejected.",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_submit_missing_text_rejected(self, client: TestClient) -> None:
        """Missing text field is rejected (FR-1.3)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_submit_invalid_realm_rejected(self, client: TestClient) -> None:
        """Invalid realm is rejected (HP-3)."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for unknown realm.",
                "realm": "nonexistent_realm_xyz",
            },
        )

        assert response.status_code == 400
        data = response.json()["detail"]
        assert data["type"] == "https://archon72.io/errors/invalid-realm"
        assert "nonexistent_realm_xyz" in data["detail"]


class TestSubmitPetitionHaltBehavior:
    """Tests for halt state behavior (CT-13)."""

    def test_submit_rejected_when_halted(
        self,
        app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
        mock_realm_registry: RealmRegistryStub,
    ) -> None:
        """Petition submission is rejected when system is halted (CT-13)."""
        # Create halted halt checker
        halted_checker = HaltCheckerStub()
        halted_checker.set_halted(True, "Emergency maintenance")

        set_petition_submission_repository(mock_repository)
        set_halt_checker(halted_checker)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "This should be rejected due to halt.",
            },
        )

        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["type"] == "https://archon72.io/errors/system-halted"
        assert "Retry-After" in response.headers


class TestGetPetitionStatus:
    """Tests for GET /v1/petition-submissions/{petition_id}."""

    def test_get_petition_success(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Get petition status successfully (FR-7.1)."""
        # First submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to retrieve later.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Then retrieve it
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["petition_id"] == petition_id
        assert data["state"] == "RECEIVED"
        assert data["type"] == "GENERAL"
        assert "content_hash" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_petition_not_found(self, client: TestClient) -> None:
        """Get nonexistent petition returns 404."""
        fake_id = str(uuid4())
        response = client.get(f"/v1/petition-submissions/{fake_id}")

        assert response.status_code == 404
        data = response.json()["detail"]
        assert data["type"] == "https://archon72.io/errors/petition-not-found"
        assert fake_id in data["detail"]

    def test_get_petition_invalid_uuid(self, client: TestClient) -> None:
        """Get with invalid UUID returns 422."""
        response = client.get("/v1/petition-submissions/not-a-uuid")

        assert response.status_code == 422  # Validation error

    def test_get_petition_works_during_halt(
        self,
        app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
        mock_realm_registry: RealmRegistryStub,
    ) -> None:
        """GET petition works even when system is halted (CT-13)."""
        # First set up without halt to create a petition
        not_halted = HaltCheckerStub()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(not_halted)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to retrieve during halt.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Now set halted state - reads should still work
        halted_checker = HaltCheckerStub()
        halted_checker.set_halted(True, "Emergency maintenance")
        set_halt_checker(halted_checker)

        # Force service recreation
        reset_petition_submission_dependencies()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(halted_checker)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        # GET should succeed even during halt (CT-13: reads allowed)
        assert get_response.status_code == 200


class TestContentHashComputation:
    """Tests for content hash computation (HP-2)."""

    def test_content_hash_deterministic(self, client: TestClient) -> None:
        """Same content produces same hash (HP-2)."""
        text = "Identical petition content for hash test."

        response1 = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": text},
        )
        response2 = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": text},
        )

        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["content_hash"] == response2.json()["content_hash"]

    def test_content_hash_differs_for_different_content(
        self, client: TestClient
    ) -> None:
        """Different content produces different hash (HP-2)."""
        response1 = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "First petition content."},
        )
        response2 = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Second petition content."},
        )

        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["content_hash"] != response2.json()["content_hash"]

    def test_content_hash_is_32_bytes_base64(self, client: TestClient) -> None:
        """Content hash is 32 bytes encoded as base64 (Blake3)."""
        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition for hash length."},
        )

        assert response.status_code == 201
        hash_bytes = base64.b64decode(response.json()["content_hash"])
        assert len(hash_bytes) == 32  # Blake3 produces 32-byte hashes


class TestRFC7807ErrorResponses:
    """Tests for RFC 7807 compliant error responses."""

    def test_error_response_has_required_fields(self, client: TestClient) -> None:
        """Error responses include all RFC 7807 fields."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for unknown realm.",
                "realm": "nonexistent_realm",
            },
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "type" in detail
        assert "title" in detail
        assert "status" in detail
        assert "detail" in detail
        assert "instance" in detail
        assert detail["type"].startswith("https://")
        assert detail["status"] == 400


class TestPetitionStatusQueryEndpoint:
    """Tests for petition status query endpoint (Story 1.8, FR-7.1, FR-7.4)."""

    def test_status_response_includes_all_required_fields(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Response includes petition_id, type, state, co_signer_count, created_at, updated_at (AC2, AC7)."""
        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to verify response fields.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        # Verify all required fields present (AC2, AC7)
        assert "petition_id" in data
        assert "type" in data
        assert "state" in data
        assert "co_signer_count" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "realm" in data
        # Verify field values
        assert data["petition_id"] == petition_id
        assert data["type"] == "GENERAL"
        assert data["state"] == "RECEIVED"
        assert data["co_signer_count"] == 0  # Default until Epic 5

    def test_status_response_includes_fate_reason_for_acknowledged(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Response includes fate_reason when state is ACKNOWLEDGED (AC3, AC7)."""
        import asyncio

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to acknowledge.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # First transition to DELIBERATING, then to ACKNOWLEDGED with reason
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(
                petition_id,
                PetitionState.DELIBERATING,
            )
        )
        asyncio.get_event_loop().run_until_complete(
            mock_repository.assign_fate_cas(
                petition_id,
                PetitionState.DELIBERATING,
                PetitionState.ACKNOWLEDGED,
                fate_reason="Duplicate of existing petition #123",
            )
        )

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["state"] == "ACKNOWLEDGED"
        assert data["fate_reason"] == "Duplicate of existing petition #123"

    def test_status_response_includes_fate_reason_for_referred(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Response includes fate_reason when state is REFERRED (AC3)."""
        import asyncio

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GRIEVANCE",
                "text": "Petition to refer to Knight.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Transition to DELIBERATING then REFERRED with reason
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(
                petition_id,
                PetitionState.DELIBERATING,
            )
        )
        asyncio.get_event_loop().run_until_complete(
            mock_repository.assign_fate_cas(
                petition_id,
                PetitionState.DELIBERATING,
                PetitionState.REFERRED,
                fate_reason="Requires Knight investigation",
            )
        )

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["state"] == "REFERRED"
        assert data["fate_reason"] == "Requires Knight investigation"

    def test_status_response_includes_fate_reason_for_escalated(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Response includes fate_reason when state is ESCALATED (AC3)."""
        import asyncio

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "CESSATION",
                "text": "Petition to escalate to King.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Transition to DELIBERATING then ESCALATED with reason
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(
                petition_id,
                PetitionState.DELIBERATING,
            )
        )
        asyncio.get_event_loop().run_until_complete(
            mock_repository.assign_fate_cas(
                petition_id,
                PetitionState.DELIBERATING,
                PetitionState.ESCALATED,
                fate_reason="Unanimous agreement for King adoption",
            )
        )

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["state"] == "ESCALATED"
        assert data["fate_reason"] == "Unanimous agreement for King adoption"

    def test_status_response_no_fate_reason_for_non_terminal(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Response fate_reason is None for non-terminal states (AC3)."""
        import asyncio

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition in non-terminal state.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Transition to DELIBERATING (non-terminal)
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(
                petition_id,
                PetitionState.DELIBERATING,
            )
        )

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["state"] == "DELIBERATING"
        assert data["fate_reason"] is None

    def test_404_error_format_compliance(self, client: TestClient) -> None:
        """404 response format includes type, title, status, detail, instance (AC4, AC8)."""
        fake_id = str(uuid4())
        response = client.get(f"/v1/petition-submissions/{fake_id}")

        assert response.status_code == 404
        detail = response.json()["detail"]
        # Verify all RFC 7807 fields present (AC8)
        assert "type" in detail
        assert "title" in detail
        assert "status" in detail
        assert "detail" in detail
        assert "instance" in detail
        # Verify field values
        assert detail["type"] == "https://archon72.io/errors/petition-not-found"
        assert detail["title"] == "Petition Not Found"
        assert detail["status"] == 404
        assert fake_id in detail["detail"]

    def test_endpoint_works_during_halt(
        self,
        app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
        mock_realm_registry: RealmRegistryStub,
    ) -> None:
        """Status query works during system halt - reads allowed (AC6, CT-13)."""
        # Create petition while system is not halted
        not_halted = HaltCheckerStub()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(not_halted)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to query during halt.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Now set halted state
        halted_checker = HaltCheckerStub()
        halted_checker.set_halted(True, "Emergency maintenance")
        reset_petition_submission_dependencies()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(halted_checker)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        # GET should succeed during halt (AC6, CT-13)
        assert get_response.status_code == 200
        assert get_response.json()["petition_id"] == petition_id


class TestPetitionStatusTokenResponse:
    """Tests for status_token in petition status response (Story 7.1, FR-7.2)."""

    def test_status_response_includes_status_token(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Response includes status_token for long-polling (FR-7.2, AC1)."""
        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to verify status token.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        # Verify status_token is present and non-empty (AC1)
        assert "status_token" in data
        assert data["status_token"] is not None
        assert isinstance(data["status_token"], str)
        assert len(data["status_token"]) > 0

    def test_status_token_is_valid_base64url(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """status_token is valid base64url encoding (AC1)."""
        import base64

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for base64url token test.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        assert get_response.status_code == 200

        token = get_response.json()["status_token"]
        # Should be URL-safe (no + or /)
        assert "+" not in token
        assert "/" not in token
        # Should decode successfully
        try:
            decoded = base64.urlsafe_b64decode(token)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"Failed to decode status_token: {e}")

    def test_status_token_encodes_petition_id(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """status_token encodes the petition_id for verification (AC1)."""
        from src.domain.models.status_token import StatusToken

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for token encoding test.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        assert get_response.status_code == 200

        token_str = get_response.json()["status_token"]
        # Decode and verify petition_id
        token = StatusToken.decode(token_str)
        assert token.petition_id == petition_id

    def test_status_token_encodes_state_version(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """status_token encodes state version for change detection (AC1)."""
        from src.domain.models.status_token import StatusToken

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for version encoding test.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        assert get_response.status_code == 200

        token_str = get_response.json()["status_token"]
        # Decode and verify version is set
        token = StatusToken.decode(token_str)
        assert token.version is not None
        assert isinstance(token.version, int)

    def test_status_token_changes_on_state_change(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """status_token version changes when petition state changes (AC1)."""
        import asyncio

        from src.domain.models.status_token import StatusToken

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for state change detection test.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Get initial token
        get_response1 = client.get(f"/v1/petition-submissions/{petition_id}")
        token1 = StatusToken.decode(get_response1.json()["status_token"])
        initial_version = token1.version

        # Change state to DELIBERATING
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(
                petition_id,
                PetitionState.DELIBERATING,
            )
        )

        # Get new token
        get_response2 = client.get(f"/v1/petition-submissions/{petition_id}")
        token2 = StatusToken.decode(get_response2.json()["status_token"])

        # Version should change when state changes
        assert token2.version != initial_version

    def test_status_token_consistent_for_same_state(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """status_token has consistent version for same state (AC1)."""
        from src.domain.models.status_token import StatusToken

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for consistency test.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Get tokens from two requests without state change
        get_response1 = client.get(f"/v1/petition-submissions/{petition_id}")
        get_response2 = client.get(f"/v1/petition-submissions/{petition_id}")

        token1 = StatusToken.decode(get_response1.json()["status_token"])
        token2 = StatusToken.decode(get_response2.json()["status_token"])

        # Version should be same (state hasn't changed)
        assert token1.version == token2.version
        # But timestamps will differ
        assert token1.petition_id == token2.petition_id


class TestWithdrawPetitionEndpoint:
    """Tests for POST /v1/petition-submissions/{petition_id}/withdraw (Story 7.3, FR-7.5)."""

    def test_withdraw_petition_success(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Successful withdrawal returns 200 with ACKNOWLEDGED state (AC1)."""
        submitter_id = uuid4()

        # Submit a petition with submitter_id
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to withdraw.",
                "submitter_id": str(submitter_id),
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Withdraw the petition
        withdraw_response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": str(submitter_id),
                "reason": "Changed my mind",
            },
        )

        assert withdraw_response.status_code == 200
        data = withdraw_response.json()
        assert data["petition_id"] == petition_id
        assert data["state"] == "ACKNOWLEDGED"
        assert "WITHDRAWN" in data["fate_reason"]
        assert "updated_at" in data

    def test_withdraw_petition_without_reason(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Withdrawal without reason uses default (AC1)."""
        submitter_id = uuid4()

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to withdraw without reason.",
                "submitter_id": str(submitter_id),
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Withdraw without reason
        withdraw_response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": str(submitter_id),
            },
        )

        assert withdraw_response.status_code == 200
        data = withdraw_response.json()
        assert "WITHDRAWN" in data["fate_reason"]

    def test_withdraw_petition_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Withdrawal of non-existent petition returns 404 (AC4)."""
        fake_petition_id = str(uuid4())
        requester_id = str(uuid4())

        response = client.post(
            f"/v1/petition-submissions/{fake_petition_id}/withdraw",
            json={
                "requester_id": requester_id,
            },
        )

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:petition:not-found"
        assert detail["title"] == "Petition Not Found"
        assert fake_petition_id in detail["detail"]
        assert detail["status"] == 404

    def test_withdraw_petition_unauthorized(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Withdrawal by different submitter returns 403 (AC3)."""
        original_submitter = uuid4()
        different_requester = uuid4()

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to test unauthorized withdrawal.",
                "submitter_id": str(original_submitter),
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Try to withdraw with different requester
        response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": str(different_requester),
            },
        )

        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:petition:unauthorized-withdrawal"
        assert detail["title"] == "Unauthorized Withdrawal"
        assert detail["status"] == 403
        assert f"submitter:{different_requester}" in detail["actor"]

    def test_withdraw_anonymous_petition_rejected(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Withdrawal of anonymous petition returns 403 (AC3)."""
        # Submit an anonymous petition (no submitter_id)
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Anonymous petition that cannot be withdrawn.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Try to withdraw
        any_requester = uuid4()
        response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": str(any_requester),
            },
        )

        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:petition:unauthorized-withdrawal"

    def test_withdraw_already_fated_petition(
        self,
        client: TestClient,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Withdrawal of already-fated petition returns 400 (AC2)."""
        import asyncio

        submitter_id = uuid4()

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition that will be fated before withdrawal.",
                "submitter_id": str(submitter_id),
            },
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Fate the petition (RECEIVED -> DELIBERATING -> ACKNOWLEDGED)
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(
                petition_id,
                PetitionState.DELIBERATING,
            )
        )
        asyncio.get_event_loop().run_until_complete(
            mock_repository.assign_fate_cas(
                petition_id,
                PetitionState.DELIBERATING,
                PetitionState.ACKNOWLEDGED,
                fate_reason="Already processed",
            )
        )

        # Try to withdraw
        response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": str(submitter_id),
            },
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:petition:already-fated"
        assert detail["title"] == "Petition Already Fated"
        assert "ACKNOWLEDGED" in detail["detail"]
        assert detail["status"] == 400

    def test_withdraw_petition_halted(
        self,
        app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
        mock_realm_registry: RealmRegistryStub,
    ) -> None:
        """Withdrawal during system halt returns 503 (AC5, CT-13)."""
        submitter_id = uuid4()

        # First create petition while not halted
        not_halted = HaltCheckerStub()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(not_halted)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to withdraw during halt.",
                "submitter_id": str(submitter_id),
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Now halt the system
        halted_checker = HaltCheckerStub()
        halted_checker.set_halted(True, "Emergency maintenance")
        reset_petition_submission_dependencies()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(halted_checker)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": str(submitter_id),
            },
        )

        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:system:halted"
        assert detail["title"] == "System Halted"
        assert "Retry-After" in response.headers

    def test_withdraw_petition_invalid_uuid(
        self,
        client: TestClient,
    ) -> None:
        """Invalid petition_id UUID returns 422."""
        response = client.post(
            "/v1/petition-submissions/not-a-uuid/withdraw",
            json={
                "requester_id": str(uuid4()),
            },
        )

        assert response.status_code == 422

    def test_withdraw_petition_missing_requester_id(
        self,
        client: TestClient,
    ) -> None:
        """Missing requester_id returns 422."""
        petition_id = str(uuid4())

        response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={},
        )

        assert response.status_code == 422

    def test_withdraw_petition_rfc7807_format(
        self,
        client: TestClient,
    ) -> None:
        """Error responses follow RFC 7807 format with governance extensions (D7)."""
        fake_petition_id = str(uuid4())

        response = client.post(
            f"/v1/petition-submissions/{fake_petition_id}/withdraw",
            json={
                "requester_id": str(uuid4()),
            },
        )

        assert response.status_code == 404
        detail = response.json()["detail"]

        # RFC 7807 required fields
        assert "type" in detail
        assert "title" in detail
        assert "status" in detail
        assert "detail" in detail
        assert "instance" in detail

        # Governance extension
        assert "petition_id" in detail
