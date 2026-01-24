"""Unit tests for petition status long-poll endpoint (Story 7.1, Task 4).

Tests cover:
- Long-poll with valid token
- Immediate return on state change
- Timeout with HTTP 304
- Invalid/expired token handling
- Petition not found handling

Constitutional Constraints:
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99 on state change
- CT-13: Reads allowed during halt
- AC2: 30-second timeout with HTTP 304
- AC3: Efficient connection management (no busy-wait)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
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
from src.domain.models.petition_submission import PetitionState
from src.domain.models.status_token import StatusToken
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.realm_registry_stub import RealmRegistryStub
from src.infrastructure.stubs.status_token_registry_stub import (
    reset_status_token_registry,
)


@pytest.fixture(autouse=True)
def reset_dependencies():
    """Reset all DI singletons before each test."""
    reset_petition_submission_dependencies()
    reset_status_token_registry()
    yield
    reset_petition_submission_dependencies()
    reset_status_token_registry()


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


class TestLongPollEndpointBasic:
    """Basic tests for long-poll endpoint."""

    def test_longpoll_requires_token_parameter(self, client: TestClient) -> None:
        """Long-poll endpoint requires token query parameter."""
        petition_id = uuid4()
        response = client.get(f"/v1/petition-submissions/{petition_id}/status")
        assert response.status_code == 422  # Validation error

    def test_longpoll_invalid_token_returns_400(
        self, client: TestClient, mock_repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Long-poll with invalid token returns 400 (D7)."""
        # First create a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        response = client.get(
            f"/v1/petition-submissions/{petition_id}/status",
            params={"token": "invalid_base64_token!!!"},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["type"] == "https://archon72.io/errors/invalid-status-token"
        assert detail["status"] == 400

    def test_longpoll_wrong_petition_id_returns_400(
        self, client: TestClient, mock_repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Long-poll with token for different petition returns 400."""
        # Create a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Get its token
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        token = get_response.json()["status_token"]

        # Try to use token for a different petition
        different_id = uuid4()
        # First we need to create another petition
        submit_response2 = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Another petition"},
        )
        different_id = submit_response2.json()["petition_id"]

        response = client.get(
            f"/v1/petition-submissions/{different_id}/status",
            params={"token": token},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "mismatch" in detail["detail"].lower()

    def test_longpoll_expired_token_returns_400(
        self, client: TestClient, mock_repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Long-poll with expired token returns 400."""
        # Create a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Create an old token manually
        old_time = datetime.now(timezone.utc) - timedelta(seconds=600)
        old_token = StatusToken(petition_id=petition_id, version=1, created_at=old_time)
        token_str = old_token.encode()

        response = client.get(
            f"/v1/petition-submissions/{petition_id}/status",
            params={"token": token_str},
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["type"] == "https://archon72.io/errors/expired-status-token"
        assert "max_age_seconds" in detail

    def test_longpoll_petition_not_found_returns_404(self, client: TestClient) -> None:
        """Long-poll for nonexistent petition returns 404."""
        fake_id = uuid4()
        # Create a valid token for the fake ID
        token = StatusToken.create(petition_id=fake_id, version=1)
        token_str = token.encode()

        response = client.get(
            f"/v1/petition-submissions/{fake_id}/status",
            params={"token": token_str},
        )
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["type"] == "https://archon72.io/errors/petition-not-found"


class TestLongPollImmediateReturn:
    """Tests for immediate return when state already changed."""

    def test_longpoll_returns_immediately_on_state_change(
        self, client: TestClient, mock_repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Long-poll returns immediately if state changed (AC2, NFR-1.2)."""
        # Create a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert submit_response.status_code == 201
        petition_id = UUID(submit_response.json()["petition_id"])

        # Get initial token
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        initial_token = get_response.json()["status_token"]

        # Change state
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(petition_id, PetitionState.DELIBERATING)
        )

        # Long-poll should return immediately with new status
        longpoll_response = client.get(
            f"/v1/petition-submissions/{petition_id}/status",
            params={"token": initial_token},
        )

        assert longpoll_response.status_code == 200
        data = longpoll_response.json()
        assert data["state"] == "DELIBERATING"
        assert data["status_token"] != initial_token  # New token

    def test_longpoll_immediate_return_includes_all_fields(
        self, client: TestClient, mock_repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Immediate return includes all status response fields."""
        # Create a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        petition_id = UUID(submit_response.json()["petition_id"])

        # Get initial token
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        initial_token = get_response.json()["status_token"]

        # Change state
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(petition_id, PetitionState.DELIBERATING)
        )

        # Long-poll
        longpoll_response = client.get(
            f"/v1/petition-submissions/{petition_id}/status",
            params={"token": initial_token},
        )

        assert longpoll_response.status_code == 200
        data = longpoll_response.json()
        # Verify all required fields
        assert "petition_id" in data
        assert "state" in data
        assert "type" in data
        assert "realm" in data
        assert "co_signer_count" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "status_token" in data


class TestLongPollTimeout:
    """Tests for timeout behavior."""

    def test_longpoll_timeout_returns_304(
        self, client: TestClient, mock_repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Long-poll returns 304 on timeout (AC2)."""
        # Create a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Get token
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        token = get_response.json()["status_token"]

        # Patch timeout to be very short for testing
        with patch("src.api.routes.petition_submission.LONGPOLL_TIMEOUT_SECONDS", 0.1):
            longpoll_response = client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": token},
            )

        assert longpoll_response.status_code == 304

    def test_longpoll_timeout_returns_same_token(
        self, client: TestClient, mock_repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Long-poll timeout includes same token in header (AC2)."""
        # Create a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        petition_id = submit_response.json()["petition_id"]

        # Get token
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        token = get_response.json()["status_token"]

        # Patch timeout
        with patch("src.api.routes.petition_submission.LONGPOLL_TIMEOUT_SECONDS", 0.1):
            longpoll_response = client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": token},
            )

        assert longpoll_response.status_code == 304
        assert longpoll_response.headers.get("X-Status-Token") == token


class TestLongPollHaltBehavior:
    """Tests for halt state behavior (CT-13)."""

    def test_longpoll_works_during_halt(
        self,
        app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
        mock_realm_registry: RealmRegistryStub,
    ) -> None:
        """Long-poll works during system halt - reads allowed (CT-13)."""
        # Create petition while not halted
        not_halted = HaltCheckerStub()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(not_halted)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        petition_id = UUID(submit_response.json()["petition_id"])

        # Get token
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        token = get_response.json()["status_token"]

        # Change state before halt
        asyncio.get_event_loop().run_until_complete(
            mock_repository.update_state(petition_id, PetitionState.DELIBERATING)
        )

        # Now halt system
        halted_checker = HaltCheckerStub()
        halted_checker.set_halted(True, "Test halt")
        reset_petition_submission_dependencies()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(halted_checker)
        set_realm_registry(mock_realm_registry)

        client = TestClient(app)
        # Long-poll should still work (CT-13: reads allowed)
        longpoll_response = client.get(
            f"/v1/petition-submissions/{petition_id}/status",
            params={"token": token},
        )

        assert longpoll_response.status_code == 200
        assert longpoll_response.json()["state"] == "DELIBERATING"


class TestLongPollTokenValidation:
    """Tests for token validation in long-poll endpoint."""

    def test_valid_token_is_accepted(
        self, client: TestClient, mock_repository: PetitionSubmissionRepositoryStub
    ) -> None:
        """Valid fresh token is accepted."""
        # Create petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": "Test petition"},
        )
        petition_id = submit_response.json()["petition_id"]

        # Get token
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        token = get_response.json()["status_token"]

        # Use token immediately (with short timeout for test)
        with patch("src.api.routes.petition_submission.LONGPOLL_TIMEOUT_SECONDS", 0.1):
            response = client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": token},
            )

        # Should get 304 (timeout) not 400 (invalid)
        assert response.status_code == 304
