"""Integration tests for co-sign rate limiting API (Story 5.4, FR-6.6, SYBIL-1).

These tests verify the complete request/response flow for rate limiting
through the API with all components integrated.

Constitutional Compliance:
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- NFR-5.1: Rate limiting per identity: Configurable per type
- SYBIL-1: Identity verification + rate limiting per verified identity
- CT-11: Silent failure destroys legitimacy - return 429, never silently drop
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
from src.infrastructure.stubs.co_sign_rate_limiter_stub import CoSignRateLimiterStub
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
    """Create fresh identity store for each test."""
    return IdentityStoreStub()


@pytest.fixture
def rate_limiter() -> CoSignRateLimiterStub:
    """Create fresh rate limiter for each test."""
    return CoSignRateLimiterStub()


@pytest.fixture
def co_sign_service(
    co_sign_repo: CoSignRepositoryStub,
    petition_repo: PetitionSubmissionRepositoryStub,
    halt_checker: HaltCheckerStub,
    identity_store: IdentityStoreStub,
    rate_limiter: CoSignRateLimiterStub,
) -> CoSignSubmissionService:
    """Create co-sign service with all dependencies."""
    return CoSignSubmissionService(
        co_sign_repo=co_sign_repo,
        petition_repo=petition_repo,
        halt_checker=halt_checker,
        identity_store=identity_store,
        rate_limiter=rate_limiter,
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
        text="Test petition for rate limit testing.",
        realm="test_realm",
        state=PetitionState.RECEIVED,
        content_hash=b"a" * 32,
        co_signer_count=0,
    )
    petition_repo._submissions[petition.id] = petition
    co_sign_repo.add_valid_petition(petition.id)
    return petition


@pytest.fixture
def signer_id(identity_store: IdentityStoreStub) -> uuid4:
    """Create a valid signer and return its ID."""
    signer = uuid4()
    identity_store.add_valid_identity(signer)
    return signer


class TestRateLimitSuccess:
    """Tests for successful co-sign within rate limit (AC6)."""

    def test_co_sign_succeeds_under_rate_limit(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
    ) -> None:
        """Co-sign succeeds when under rate limit."""
        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["cosign_id"] is not None
        assert data["signer_id"] == str(signer_id)

    def test_rate_limit_remaining_in_success_response(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Success response includes rate_limit_remaining (AC6)."""
        # Set some existing usage
        rate_limiter.set_count(signer_id, 10)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        data = response.json()

        # After increment: count is 11, so remaining is 50 - 11 = 39
        assert data["rate_limit_remaining"] == 39

    def test_rate_limit_reset_at_in_success_response(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
    ) -> None:
        """Success response includes rate_limit_reset_at (AC6)."""
        from datetime import datetime

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 201
        data = response.json()

        assert data["rate_limit_reset_at"] is not None
        # Should be parseable as ISO datetime
        reset_at = datetime.fromisoformat(
            data["rate_limit_reset_at"].replace("Z", "+00:00")
        )
        assert reset_at > datetime.now(reset_at.tzinfo)


class TestRateLimitExceeded:
    """Tests for rate limit exceeded behavior (AC1)."""

    def test_returns_429_when_at_limit(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Returns HTTP 429 when at rate limit (AC1)."""
        # Set at limit
        rate_limiter.set_count(signer_id, 50)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 429

    def test_retry_after_header_present(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Response includes Retry-After header (AC1)."""
        rate_limiter.set_count(signer_id, 50)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0

    def test_rfc_7807_error_format(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Error response follows RFC 7807 format (AC1, D7)."""
        rate_limiter.set_count(signer_id, 50)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 429
        detail = response.json()["detail"]

        # RFC 7807 required fields
        assert detail["type"] == "urn:archon72:co-sign:rate-limit-exceeded"
        assert detail["title"] == "Co-Sign Rate Limit Exceeded"
        assert detail["status"] == 429
        assert "detail" in detail
        assert str(signer_id) in detail["detail"]

    def test_rate_limit_remaining_extension(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Error includes rate_limit_remaining extension (AC1)."""
        rate_limiter.set_count(signer_id, 50)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 429
        detail = response.json()["detail"]

        assert detail["rate_limit_remaining"] == 0

    def test_rate_limit_reset_at_extension(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Error includes rate_limit_reset_at extension (AC1)."""
        from datetime import datetime

        rate_limiter.set_count(signer_id, 50)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 429
        detail = response.json()["detail"]

        assert "rate_limit_reset_at" in detail
        # Should be parseable as ISO datetime
        reset_at = datetime.fromisoformat(
            detail["rate_limit_reset_at"].replace("Z", "+00:00")
        )
        assert reset_at is not None

    def test_governance_extensions(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Error includes governance extensions (nfr_reference, hardening_control)."""
        rate_limiter.set_count(signer_id, 50)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 429
        detail = response.json()["detail"]

        assert detail["nfr_reference"] == "NFR-5.1"
        assert detail["hardening_control"] == "SYBIL-1"

    def test_current_count_and_limit_in_error(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Error includes current_count and limit."""
        rate_limiter.set_count(signer_id, 55)  # Over limit

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )

        assert response.status_code == 429
        detail = response.json()["detail"]

        assert detail["current_count"] == 55
        assert detail["limit"] == 50


class TestRateLimitCounterIncrement:
    """Tests for rate limit counter behavior (AC4)."""

    def test_counter_only_increments_on_success(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        signer_id: uuid4,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Counter increments only after successful co-sign (AC4)."""
        initial_count = rate_limiter.get_count(signer_id)
        assert initial_count == 0

        # First successful co-sign
        response1 = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )
        assert response1.status_code == 201

        # Counter should be 1
        assert rate_limiter.get_count(signer_id) == 1

        # Duplicate co-sign (fails)
        response2 = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(signer_id)},
        )
        assert response2.status_code == 409  # Already signed

        # Counter should still be 1 (not incremented on failure)
        assert rate_limiter.get_count(signer_id) == 1


class TestRateLimitInteractionWithIdentity:
    """Tests for rate limit interaction with identity verification (AC3)."""

    def test_rate_limit_not_checked_for_invalid_identity(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
        rate_limiter: CoSignRateLimiterStub,
    ) -> None:
        """Rate limit is not checked when identity verification fails (AC3)."""
        unknown_signer = uuid4()
        # Not adding to identity store - will fail identity verification

        # Set rate limiter at limit
        rate_limiter.set_count(unknown_signer, 50)

        response = client.post(
            f"/v1/petitions/{active_petition.id}/co-sign",
            json={"signer_id": str(unknown_signer)},
        )

        # Should get identity error (403), not rate limit error (429)
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["type"] == "urn:archon72:identity:not-found"


class TestRateLimitDifferentSigners:
    """Tests for rate limiting with different signers."""

    def test_signers_have_independent_limits(
        self,
        client: TestClient,
        active_petition: PetitionSubmission,
        identity_store: IdentityStoreStub,
        rate_limiter: CoSignRateLimiterStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Different signers have independent rate limits."""
        signer_a = uuid4()
        signer_b = uuid4()
        identity_store.add_valid_identity(signer_a)
        identity_store.add_valid_identity(signer_b)

        # Set signer_a at limit
        rate_limiter.set_count(signer_a, 50)
        # signer_b is under limit

        # Create multiple petitions so each signer can co-sign
        petition_a = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Petition A",
            realm="test",
            state=PetitionState.RECEIVED,
            content_hash=b"x" * 32,
            co_signer_count=0,
        )
        petition_b = PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Petition B",
            realm="test",
            state=PetitionState.RECEIVED,
            content_hash=b"y" * 32,
            co_signer_count=0,
        )
        petition_repo._submissions[petition_a.id] = petition_a
        petition_repo._submissions[petition_b.id] = petition_b
        co_sign_repo.add_valid_petition(petition_a.id)
        co_sign_repo.add_valid_petition(petition_b.id)

        # signer_a should be rate limited
        response_a = client.post(
            f"/v1/petitions/{petition_a.id}/co-sign",
            json={"signer_id": str(signer_a)},
        )
        assert response_a.status_code == 429

        # signer_b should succeed
        response_b = client.post(
            f"/v1/petitions/{petition_b.id}/co-sign",
            json={"signer_id": str(signer_b)},
        )
        assert response_b.status_code == 201
