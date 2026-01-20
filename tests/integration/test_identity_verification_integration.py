"""Integration tests for identity verification in co-sign flow (Story 5.3, NFR-5.2).

Tests the full identity verification integration with the co-sign API endpoint.

Constitutional Constraints:
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- LEGIT-1: Manufactured consent via bot co-signers -> verification required
- CT-12: Witnessing creates accountability
- D7: RFC 7807 error responses with governance extensions
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.co_sign import get_co_sign_submission_service
from src.api.main import app
from src.application.services.co_sign_submission_service import CoSignSubmissionService
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


@pytest.fixture
def co_sign_repo() -> CoSignRepositoryStub:
    """Create fresh co-sign repository for each test."""
    return CoSignRepositoryStub()


@pytest.fixture
def petition_repo() -> PetitionSubmissionRepositoryStub:
    """Create fresh petition repository for each test."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create fresh halt checker for each test."""
    return HaltCheckerStub()


@pytest.fixture
def identity_store() -> IdentityStoreStub:
    """Create fresh identity store for each test (NFR-5.2)."""
    return IdentityStoreStub()


@pytest.fixture
def co_sign_service(
    co_sign_repo: CoSignRepositoryStub,
    petition_repo: PetitionSubmissionRepositoryStub,
    halt_checker: HaltCheckerStub,
    identity_store: IdentityStoreStub,
) -> CoSignSubmissionService:
    """Create co-sign service with test dependencies including identity store."""
    return CoSignSubmissionService(
        co_sign_repo=co_sign_repo,
        petition_repo=petition_repo,
        halt_checker=halt_checker,
        identity_store=identity_store,
    )


@pytest.fixture
def client(co_sign_service: CoSignSubmissionService) -> TestClient:
    """Create test client with dependency overrides."""
    app.dependency_overrides[get_co_sign_submission_service] = lambda: co_sign_service

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def active_petition(
    petition_repo: PetitionSubmissionRepositoryStub,
    co_sign_repo: CoSignRepositoryStub,
) -> PetitionSubmission:
    """Create an active petition for testing."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for identity verification.",
        realm="test_realm",
        state=PetitionState.RECEIVED,
        content_hash=b"a" * 32,
        co_signer_count=0,
    )
    petition_repo._submissions[petition.id] = petition
    co_sign_repo.add_valid_petition(petition.id)
    return petition


class TestIdentityVerificationSuccess:
    """Tests for successful identity verification (AC1)."""

    def test_co_sign_with_valid_identity_succeeds(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Co-sign with valid identity returns 201 and identity_verified=true."""
        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["identity_verified"] is True
        assert data["signer_id"] == str(signer_id)

    def test_identity_verified_included_in_response(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Response includes identity_verified field (AC5)."""
        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        data = response.json()
        assert "identity_verified" in data


class TestIdentityNotFoundRejection:
    """Tests for unknown identity rejection (AC2)."""

    def test_co_sign_with_unknown_identity_returns_403(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Co-sign with unknown identity returns 403 Forbidden."""
        unknown_signer_id = uuid4()
        # Do NOT add to identity store - identity is unknown

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(unknown_signer_id)},
        )

        assert response.status_code == 403

    def test_identity_not_found_error_code(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Error response includes IDENTITY_NOT_FOUND type."""
        unknown_signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(unknown_signer_id)},
        )

        data = response.json()["detail"]
        assert data["type"] == "urn:archon72:identity:not-found"
        assert data["title"] == "Identity Not Found"
        assert data["status"] == 403

    def test_identity_not_found_includes_governance_extensions(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Error response includes NFR and hardening control references (D7)."""
        unknown_signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(unknown_signer_id)},
        )

        data = response.json()["detail"]
        assert data["nfr_reference"] == "NFR-5.2"
        assert data["hardening_control"] == "LEGIT-1"

    def test_no_co_sign_record_created_for_unknown_identity(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """No co-sign record is created when identity is unknown."""
        unknown_signer_id = uuid4()
        initial_count = co_sign_repo.co_sign_count

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(unknown_signer_id)},
        )

        assert response.status_code == 403
        assert co_sign_repo.co_sign_count == initial_count


class TestIdentitySuspendedRejection:
    """Tests for suspended identity rejection (AC3)."""

    def test_co_sign_with_suspended_identity_returns_403(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Co-sign with suspended identity returns 403 Forbidden."""
        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)
        identity_store.suspend_identity(signer_id, reason="Bot activity detected")

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 403

    def test_suspended_identity_error_code(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Error response includes IDENTITY_SUSPENDED type."""
        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)
        identity_store.suspend_identity(signer_id, reason="Fraud pattern")

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        data = response.json()["detail"]
        assert data["type"] == "urn:archon72:identity:suspended"
        assert data["title"] == "Identity Suspended"
        assert data["status"] == 403

    def test_suspended_identity_includes_reason(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Error response includes suspension reason."""
        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)
        identity_store.suspend_identity(signer_id, reason="Multiple bot signatures")

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        data = response.json()["detail"]
        assert data["suspension_reason"] == "Multiple bot signatures"

    def test_no_co_sign_record_created_for_suspended_identity(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """No co-sign record is created when identity is suspended."""
        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)
        identity_store.suspend_identity(signer_id)
        initial_count = co_sign_repo.co_sign_count

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 403
        assert co_sign_repo.co_sign_count == initial_count


class TestIdentityServiceUnavailable:
    """Tests for identity service unavailable handling (AC6)."""

    def test_co_sign_when_service_unavailable_returns_503(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Co-sign when identity service unavailable returns 503."""
        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)
        identity_store.set_available(False)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 503

    def test_service_unavailable_error_code(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Error response includes IDENTITY_SERVICE_UNAVAILABLE type."""
        signer_id = uuid4()
        identity_store.set_available(False)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        data = response.json()["detail"]
        assert data["type"] == "urn:archon72:identity:service-unavailable"
        assert data["title"] == "Identity Service Unavailable"
        assert data["status"] == 503

    def test_service_unavailable_includes_retry_after_header(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Response includes Retry-After header."""
        signer_id = uuid4()
        identity_store.set_available(False)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert "Retry-After" in response.headers

    def test_service_unavailable_includes_retry_after_in_body(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Error response body includes retry_after."""
        signer_id = uuid4()
        identity_store.set_available(False)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        data = response.json()["detail"]
        assert "retry_after" in data
        assert isinstance(data["retry_after"], int)


class TestIdentityVerificationOrder:
    """Tests that identity verification happens before database writes (AC4)."""

    def test_identity_check_before_duplicate_check(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Identity check happens before duplicate check.

        Even if the signer has already co-signed, if identity is invalid,
        we should get identity error, not duplicate error.
        """
        signer_id = uuid4()
        # First, add a valid co-sign
        identity_store.add_valid_identity(signer_id)
        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )
        assert response.status_code == 201

        # Now remove the identity and try again
        identity_store.remove_valid_identity(signer_id)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        # Should get identity error, not duplicate error
        assert response.status_code == 403
        data = response.json()["detail"]
        assert data["type"] == "urn:archon72:identity:not-found"


class TestRFC7807Compliance:
    """Tests for RFC 7807 error response compliance (D7)."""

    def test_identity_not_found_rfc7807_fields(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Identity not found error has all RFC 7807 fields."""
        unknown_signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(unknown_signer_id)},
        )

        data = response.json()["detail"]
        # Required RFC 7807 fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data
        # Governance extensions
        assert "nfr_reference" in data
        assert "hardening_control" in data

    def test_suspended_identity_rfc7807_fields(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Suspended identity error has all RFC 7807 fields."""
        signer_id = uuid4()
        identity_store.add_valid_identity(signer_id)
        identity_store.suspend_identity(signer_id)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        data = response.json()["detail"]
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data

    def test_service_unavailable_rfc7807_fields(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
    ) -> None:
        """Service unavailable error has all RFC 7807 fields."""
        signer_id = uuid4()
        identity_store.set_available(False)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        data = response.json()["detail"]
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data
