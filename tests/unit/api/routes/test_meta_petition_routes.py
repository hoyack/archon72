"""Unit tests for META petition API routes (Story 8.5, FR-10.4).

These tests verify:
1. GET /v1/governance/meta-petitions (list pending)
2. GET /v1/governance/meta-petitions/{id} (get detail)
3. POST /v1/governance/meta-petitions/{id}/resolve (resolve)
4. Authentication requirements
5. Error handling
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.meta_petition import router, set_resolution_service
from src.domain.events.meta_petition import MetaPetitionResolvedEventPayload
from src.domain.models.meta_petition import (
    MetaDisposition,
    MetaPetitionQueueItem,
    MetaPetitionStatus,
)


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_resolution_service() -> AsyncMock:
    """Create mock resolution service."""
    mock = AsyncMock()
    mock.get_pending_queue.return_value = ([], 0)
    mock.get_queue_item.return_value = None
    return mock


@pytest.fixture
def high_archon_headers() -> dict[str, str]:
    """Headers for authenticated High Archon."""
    return {
        "X-Archon-Id": str(uuid4()),
        "X-Archon-Role": "HIGH_ARCHON",
    }


@pytest.fixture
def sample_queue_item() -> MetaPetitionQueueItem:
    """Create sample queue item for testing."""
    return MetaPetitionQueueItem(
        petition_id=uuid4(),
        submitter_id=uuid4(),
        petition_text="Test META petition about system improvements",
        received_at=datetime.now(timezone.utc),
        status=MetaPetitionStatus.PENDING,
    )


class TestListPendingMetaPetitions:
    """Tests for GET /v1/governance/meta-petitions endpoint."""

    def test_list_pending_success(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
        sample_queue_item: MetaPetitionQueueItem,
    ) -> None:
        """Test successful listing of pending META petitions."""
        mock_resolution_service.get_pending_queue.return_value = (
            [sample_queue_item],
            1,
        )
        set_resolution_service(mock_resolution_service)

        response = client.get(
            "/v1/governance/meta-petitions",
            headers=high_archon_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["petition_id"] == str(sample_queue_item.petition_id)
        assert data["items"][0]["status"] == "PENDING"

    def test_list_pending_empty(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test listing when queue is empty."""
        mock_resolution_service.get_pending_queue.return_value = ([], 0)
        set_resolution_service(mock_resolution_service)

        response = client.get(
            "/v1/governance/meta-petitions",
            headers=high_archon_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["items"] == []

    def test_list_pending_pagination(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test pagination parameters are passed to service."""
        mock_resolution_service.get_pending_queue.return_value = ([], 0)
        set_resolution_service(mock_resolution_service)

        client.get(
            "/v1/governance/meta-petitions?limit=25&offset=50",
            headers=high_archon_headers,
        )

        mock_resolution_service.get_pending_queue.assert_called_once_with(
            limit=25, offset=50
        )

    def test_list_pending_requires_auth(self, client: TestClient) -> None:
        """Test that authentication is required."""
        response = client.get("/v1/governance/meta-petitions")

        assert response.status_code == 401

    def test_list_pending_requires_high_archon_role(
        self, client: TestClient
    ) -> None:
        """Test that HIGH_ARCHON role is required."""
        headers = {
            "X-Archon-Id": str(uuid4()),
            "X-Archon-Role": "ARCHON",  # Not HIGH_ARCHON
        }

        response = client.get(
            "/v1/governance/meta-petitions",
            headers=headers,
        )

        assert response.status_code == 403


class TestGetMetaPetition:
    """Tests for GET /v1/governance/meta-petitions/{id} endpoint."""

    def test_get_petition_success(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
        sample_queue_item: MetaPetitionQueueItem,
    ) -> None:
        """Test successful retrieval of META petition."""
        mock_resolution_service.get_queue_item.return_value = sample_queue_item
        set_resolution_service(mock_resolution_service)

        response = client.get(
            f"/v1/governance/meta-petitions/{sample_queue_item.petition_id}",
            headers=high_archon_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["petition_id"] == str(sample_queue_item.petition_id)
        assert data["petition_text"] == sample_queue_item.petition_text

    def test_get_petition_not_found(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test 404 when petition not found."""
        mock_resolution_service.get_queue_item.return_value = None
        set_resolution_service(mock_resolution_service)

        petition_id = uuid4()
        response = client.get(
            f"/v1/governance/meta-petitions/{petition_id}",
            headers=high_archon_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_petition_requires_auth(self, client: TestClient) -> None:
        """Test that authentication is required."""
        petition_id = uuid4()
        response = client.get(f"/v1/governance/meta-petitions/{petition_id}")

        assert response.status_code == 401


class TestResolveMetaPetition:
    """Tests for POST /v1/governance/meta-petitions/{id}/resolve endpoint."""

    def test_resolve_acknowledge_success(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test successful resolution with ACKNOWLEDGE disposition."""
        petition_id = uuid4()
        high_archon_id = uuid4()
        high_archon_headers["X-Archon-Id"] = str(high_archon_id)

        mock_resolution_service.resolve_meta_petition.return_value = (
            MetaPetitionResolvedEventPayload(
                petition_id=petition_id,
                disposition=MetaDisposition.ACKNOWLEDGE,
                rationale="Acknowledged the system feedback concern",
                high_archon_id=high_archon_id,
                resolved_at=datetime.now(timezone.utc),
                forward_target=None,
            )
        )
        set_resolution_service(mock_resolution_service)

        response = client.post(
            f"/v1/governance/meta-petitions/{petition_id}/resolve",
            headers=high_archon_headers,
            json={
                "disposition": "ACKNOWLEDGE",
                "rationale": "Acknowledged the system feedback concern",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["disposition"] == "ACKNOWLEDGE"
        assert data["petition_id"] == str(petition_id)

    def test_resolve_forward_success(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test successful resolution with FORWARD disposition."""
        petition_id = uuid4()
        high_archon_id = uuid4()
        high_archon_headers["X-Archon-Id"] = str(high_archon_id)

        mock_resolution_service.resolve_meta_petition.return_value = (
            MetaPetitionResolvedEventPayload(
                petition_id=petition_id,
                disposition=MetaDisposition.FORWARD,
                rationale="Forwarding to governance council for review",
                high_archon_id=high_archon_id,
                resolved_at=datetime.now(timezone.utc),
                forward_target="governance_council",
            )
        )
        set_resolution_service(mock_resolution_service)

        response = client.post(
            f"/v1/governance/meta-petitions/{petition_id}/resolve",
            headers=high_archon_headers,
            json={
                "disposition": "FORWARD",
                "rationale": "Forwarding to governance council for review",
                "forward_target": "governance_council",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["disposition"] == "FORWARD"
        assert data["forward_target"] == "governance_council"

    def test_resolve_rationale_too_short(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test 400 when rationale is too short."""
        set_resolution_service(mock_resolution_service)

        response = client.post(
            f"/v1/governance/meta-petitions/{uuid4()}/resolve",
            headers=high_archon_headers,
            json={
                "disposition": "ACKNOWLEDGE",
                "rationale": "short",  # Less than 10 characters
            },
        )

        assert response.status_code == 422  # Pydantic validation

    def test_resolve_validation_error_from_service(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test 400 when service raises validation error."""
        mock_resolution_service.resolve_meta_petition.side_effect = ValueError(
            "forward_target required for FORWARD disposition"
        )
        set_resolution_service(mock_resolution_service)

        response = client.post(
            f"/v1/governance/meta-petitions/{uuid4()}/resolve",
            headers=high_archon_headers,
            json={
                "disposition": "FORWARD",
                "rationale": "Forwarding without target",
                # Missing forward_target
            },
        )

        assert response.status_code == 400
        assert "forward_target" in response.json()["detail"]

    def test_resolve_petition_not_found(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test 404 when petition not found."""
        from src.application.ports.meta_petition_queue_repository import (
            MetaPetitionNotFoundError,
        )

        petition_id = uuid4()
        mock_resolution_service.resolve_meta_petition.side_effect = (
            MetaPetitionNotFoundError(petition_id)
        )
        set_resolution_service(mock_resolution_service)

        response = client.post(
            f"/v1/governance/meta-petitions/{petition_id}/resolve",
            headers=high_archon_headers,
            json={
                "disposition": "ACKNOWLEDGE",
                "rationale": "Acknowledged the concern",
            },
        )

        assert response.status_code == 404

    def test_resolve_already_resolved(
        self,
        client: TestClient,
        mock_resolution_service: AsyncMock,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test 409 when petition already resolved."""
        from src.application.ports.meta_petition_queue_repository import (
            MetaPetitionAlreadyResolvedError,
        )

        petition_id = uuid4()
        mock_resolution_service.resolve_meta_petition.side_effect = (
            MetaPetitionAlreadyResolvedError(petition_id)
        )
        set_resolution_service(mock_resolution_service)

        response = client.post(
            f"/v1/governance/meta-petitions/{petition_id}/resolve",
            headers=high_archon_headers,
            json={
                "disposition": "ACKNOWLEDGE",
                "rationale": "Acknowledged the concern",
            },
        )

        assert response.status_code == 409
        assert "already resolved" in response.json()["detail"].lower()

    def test_resolve_requires_auth(self, client: TestClient) -> None:
        """Test that authentication is required."""
        response = client.post(
            f"/v1/governance/meta-petitions/{uuid4()}/resolve",
            json={
                "disposition": "ACKNOWLEDGE",
                "rationale": "Acknowledged the concern",
            },
        )

        assert response.status_code == 401

    def test_resolve_requires_high_archon_role(self, client: TestClient) -> None:
        """Test that HIGH_ARCHON role is required."""
        headers = {
            "X-Archon-Id": str(uuid4()),
            "X-Archon-Role": "ARCHON",  # Not HIGH_ARCHON
        }

        response = client.post(
            f"/v1/governance/meta-petitions/{uuid4()}/resolve",
            headers=headers,
            json={
                "disposition": "ACKNOWLEDGE",
                "rationale": "Acknowledged the concern",
            },
        )

        assert response.status_code == 403


class TestServiceNotConfigured:
    """Tests for when resolution service is not configured."""

    def test_list_without_service(
        self,
        client: TestClient,
        high_archon_headers: dict[str, str],
    ) -> None:
        """Test error when service is not configured."""
        # Reset the service to None
        set_resolution_service(None)  # type: ignore

        # The RuntimeError is raised during dependency resolution, which
        # causes TestClient to raise directly rather than returning 500.
        # We verify the error is raised correctly.
        with pytest.raises(RuntimeError, match="META petition resolution service not configured"):
            client.get(
                "/v1/governance/meta-petitions",
                headers=high_archon_headers,
            )
