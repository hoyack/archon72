"""Integration tests for co-sign submission API (Story 5.2, FR-6.1).

These tests verify the complete request/response flow through the API
with all components integrated (but using stub repositories).

Constitutional Compliance:
- FR-6.1: Seeker SHALL be able to co-sign active petition
- FR-6.2: System SHALL reject duplicate co-signature (NFR-3.5)
- FR-6.3: System SHALL reject co-sign after fate assignment
- FR-6.4: System SHALL increment co-signer count atomically
- CT-12: Witnessing creates accountability
- CT-13: Halt rejects writes, allows reads
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-1.3: Response latency < 150ms p99
- D7: RFC 7807 error responses with governance extensions
"""

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
def co_sign_service(
    co_sign_repo: CoSignRepositoryStub,
    petition_repo: PetitionSubmissionRepositoryStub,
    halt_checker: HaltCheckerStub,
) -> CoSignSubmissionService:
    """Create co-sign service with test dependencies."""
    return CoSignSubmissionService(
        co_sign_repo=co_sign_repo,
        petition_repo=petition_repo,
        halt_checker=halt_checker,
    )


@pytest.fixture
def client(co_sign_service: CoSignSubmissionService) -> TestClient:
    """Create test client with dependency overrides."""
    # Override the dependency to use our test service
    app.dependency_overrides[get_co_sign_submission_service] = lambda: co_sign_service

    client = TestClient(app, raise_server_exceptions=False)
    yield client

    # Clean up overrides after test
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
        text="Test petition for co-signing.",
        realm="test_realm",
        state=PetitionState.RECEIVED,
        content_hash=b"a" * 32,  # Blake3 hash is exactly 32 bytes
        co_signer_count=0,
    )
    # Add to petition repository via internal dict (stub testing pattern)
    petition_repo._submissions[petition.id] = petition
    # Register as valid petition in co-sign repo (simulates FK constraint)
    co_sign_repo.add_valid_petition(petition.id)
    return petition


@pytest.fixture
def fated_petition(
    petition_repo: PetitionSubmissionRepositoryStub,
    co_sign_repo: CoSignRepositoryStub,
) -> PetitionSubmission:
    """Create a fated (terminal state) petition for testing."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.CESSATION,
        text="Test petition that has been acknowledged.",
        realm="test_realm",
        state=PetitionState.ACKNOWLEDGED,
        content_hash=b"b" * 32,  # Blake3 hash is exactly 32 bytes
        co_signer_count=5,
    )
    # Add to petition repository via internal dict (stub testing pattern)
    petition_repo._submissions[petition.id] = petition
    # Register as valid petition in co-sign repo (simulates FK constraint)
    co_sign_repo.add_valid_petition(petition.id)
    return petition


class TestCoSignSubmissionIntegration:
    """Integration tests for co-sign submission flow."""

    def test_successful_co_sign(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Test successful co-sign submission (FR-6.1, FR-6.4)."""
        signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response fields
        assert "cosign_id" in data
        assert data["petition_id"] == str(active_petition.id)
        assert data["signer_id"] == str(signer_id)
        assert "signed_at" in data
        assert "content_hash" in data
        assert data["co_signer_count"] == 1  # First co-signer

    def test_co_sign_count_increments_atomically(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Co-signer count increments atomically (FR-6.4)."""
        signers = [uuid4() for _ in range(5)]
        counts = []

        for signer_id in signers:
            response = client.post(
                f"/v1/petitions/{active_petition.id}/co-sign",
                json={"signer_id": str(signer_id)},
            )
            assert response.status_code == 201
            counts.append(response.json()["co_signer_count"])

        # Counts should be 1, 2, 3, 4, 5
        assert counts == [1, 2, 3, 4, 5]


class TestCoSignDuplicatePrevention:
    """Integration tests for duplicate co-sign prevention (FR-6.2, NFR-3.5)."""

    def test_duplicate_co_sign_rejected(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Duplicate co-sign is rejected with 409 (FR-6.2, NFR-3.5)."""
        signer_id = uuid4()

        # First co-sign should succeed
        response1 = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )
        assert response1.status_code == 201

        # Second co-sign should fail
        response2 = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )
        assert response2.status_code == 409

        # Verify RFC 7807 error format
        detail = response2.json()["detail"]
        assert detail["type"] == "urn:archon72:co-sign:already-signed"
        assert detail["title"] == "Already Signed"
        assert detail["status"] == 409
        assert str(active_petition.id) in detail["detail"]
        assert str(signer_id) in detail["detail"]

    def test_different_signers_can_co_sign(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Different signers can co-sign the same petition."""
        signer1 = uuid4()
        signer2 = uuid4()

        response1 = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer1)},
        )
        response2 = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer2)},
        )

        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response2.json()["co_signer_count"] == 2


class TestCoSignPetitionNotFound:
    """Integration tests for petition not found errors (FR-6.1)."""

    def test_nonexistent_petition_returns_404(self, client: TestClient) -> None:
        """Co-sign on non-existent petition returns 404."""
        fake_petition_id = uuid4()
        signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{fake_petition_id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:co-sign:petition-not-found"
        assert detail["title"] == "Petition Not Found"
        assert detail["status"] == 404
        assert str(fake_petition_id) in detail["detail"]

    def test_invalid_uuid_format_returns_422(self, client: TestClient) -> None:
        """Invalid UUID format returns 422 validation error."""
        response = client.post(
            "/v1/petitions/not-a-valid-uuid/co-sign",
            json={"signer_id": str(uuid4())},
        )
        assert response.status_code == 422


class TestCoSignPetitionFated:
    """Integration tests for fated petition rejection (FR-6.3)."""

    def test_co_sign_on_fated_petition_rejected(
        self, client: TestClient, fated_petition: PetitionSubmission
    ) -> None:
        """Co-sign on fated petition returns 409 (FR-6.3)."""
        signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{fated_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:co-sign:petition-fated"
        assert detail["title"] == "Petition Already Fated"
        assert detail["status"] == 409
        assert str(fated_petition.id) in detail["detail"]
        assert detail["terminal_state"] == "ACKNOWLEDGED"


class TestCoSignSystemHalt:
    """Integration tests for system halt behavior (CT-13)."""

    def test_co_sign_rejected_during_halt(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Co-sign is rejected during system halt (CT-13)."""
        # Enable halt
        halt_checker.set_halted(True)

        signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:co-sign:system-halted"
        assert detail["title"] == "System Halted"
        assert detail["status"] == 503
        assert "Retry-After" in response.headers

    def test_co_sign_succeeds_after_halt_cleared(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Co-sign succeeds after halt is cleared."""
        # Enable then disable halt
        halt_checker.set_halted(True)
        halt_checker.set_halted(False)

        signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201


class TestCoSignResponseFormat:
    """Integration tests for response format compliance."""

    def test_response_contains_all_required_fields(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Response contains all required fields (CT-12)."""
        signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        data = response.json()

        # All required fields must be present
        assert "cosign_id" in data
        assert "petition_id" in data
        assert "signer_id" in data
        assert "signed_at" in data
        assert "content_hash" in data
        assert "co_signer_count" in data

    def test_content_hash_is_hex_encoded(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Content hash is BLAKE3 hex-encoded."""
        signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        content_hash = response.json()["content_hash"]

        # Should be valid hex (64 chars = 32 bytes)
        assert len(content_hash) == 64
        int(content_hash, 16)  # Should not raise

    def test_signed_at_is_iso_format(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """signed_at is in ISO 8601 format."""
        from datetime import datetime

        signer_id = uuid4()

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        signed_at = response.json()["signed_at"]

        # Should be parseable as ISO datetime
        datetime.fromisoformat(signed_at.replace("Z", "+00:00"))

    def test_basic_latency_check(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Basic latency check for co-sign response (NFR-1.3).

        Note: Comprehensive p99 < 150ms testing requires load testing.
        This is a basic sanity check.
        """
        import time

        signer_id = uuid4()

        start = time.monotonic()
        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        assert response.status_code == 201
        # Basic sanity check - should complete well under 1 second
        assert elapsed_ms < 1000, f"Response took {elapsed_ms}ms (expected < 1000ms)"


class TestCoSignValidation:
    """Integration tests for request validation."""

    def test_missing_signer_id_returns_422(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Missing signer_id returns 422 validation error."""
        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={},
        )
        assert response.status_code == 422

    def test_invalid_signer_id_format_returns_422(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Invalid signer_id UUID format returns 422."""
        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": "not-a-uuid"},
        )
        assert response.status_code == 422

    def test_null_signer_id_returns_422(
        self, client: TestClient, active_petition: PetitionSubmission
    ) -> None:
        """Null signer_id returns 422 validation error."""
        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": None},
        )
        assert response.status_code == 422
