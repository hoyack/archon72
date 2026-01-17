"""Unit tests for legitimacy API routes.

Tests the API endpoints for legitimacy restoration and status.

Constitutional Compliance:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- AC5: Operator must be authenticated and authorized
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.legitimacy import (
    router,
    set_restoration_service,
)
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.restoration_acknowledgment import (
    RestorationAcknowledgment,
    RestorationResult,
)
from src.domain.governance.legitimacy.transition_type import TransitionType


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_service() -> MagicMock:
    """Create mock restoration service."""
    service = MagicMock()
    service.request_restoration = AsyncMock()
    service.get_restoration_history = AsyncMock(return_value=[])
    service.get_acknowledgment = AsyncMock(return_value=None)
    service.get_restoration_count = AsyncMock(return_value=0)

    # Mock legitimacy port
    service._legitimacy = MagicMock()
    service._legitimacy.get_legitimacy_state = AsyncMock(
        return_value=LegitimacyState(
            current_band=LegitimacyBand.STABLE,
            entered_at=datetime.now(timezone.utc),
            violation_count=0,
            last_triggering_event_id=None,
            last_transition_type=None,
        )
    )

    return service


@pytest.fixture
def client(app: FastAPI, mock_service: MagicMock) -> TestClient:
    """Create test client with mock service."""
    set_restoration_service(mock_service)
    return TestClient(app)


class TestRestoreEndpoint:
    """Tests for POST /v1/governance/legitimacy/restore."""

    def test_restore_requires_operator_header(self, client: TestClient) -> None:
        """Restore endpoint requires X-Operator-Id header."""
        response = client.post(
            "/v1/governance/legitimacy/restore",
            json={
                "target_band": "stable",
                "reason": "Issues resolved",
                "evidence": "Audit ID: 123",
            },
        )

        assert response.status_code == 401
        assert "X-Operator-Id" in response.json()["detail"]

    def test_restore_validates_operator_uuid(self, client: TestClient) -> None:
        """Operator ID must be valid UUID."""
        response = client.post(
            "/v1/governance/legitimacy/restore",
            headers={"X-Operator-Id": "invalid-uuid"},
            json={
                "target_band": "stable",
                "reason": "Issues resolved",
                "evidence": "Audit ID: 123",
            },
        )

        assert response.status_code == 400
        assert "Invalid operator ID" in response.json()["detail"]

    def test_restore_validates_target_band(self, client: TestClient) -> None:
        """Target band must be valid."""
        response = client.post(
            "/v1/governance/legitimacy/restore",
            headers={"X-Operator-Id": str(uuid4())},
            json={
                "target_band": "invalid_band",
                "reason": "Issues resolved",
                "evidence": "Audit ID: 123",
            },
        )

        assert response.status_code == 422

    def test_restore_validates_reason_required(self, client: TestClient) -> None:
        """Reason is required and cannot be empty."""
        response = client.post(
            "/v1/governance/legitimacy/restore",
            headers={"X-Operator-Id": str(uuid4())},
            json={
                "target_band": "stable",
                "reason": "",
                "evidence": "Audit ID: 123",
            },
        )

        assert response.status_code == 422

    def test_restore_validates_evidence_required(self, client: TestClient) -> None:
        """Evidence is required and cannot be empty."""
        response = client.post(
            "/v1/governance/legitimacy/restore",
            headers={"X-Operator-Id": str(uuid4())},
            json={
                "target_band": "stable",
                "reason": "Issues resolved",
                "evidence": "",
            },
        )

        assert response.status_code == 422

    def test_restore_success(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Successful restoration returns acknowledgment details."""
        operator_id = uuid4()
        ack_id = uuid4()
        now = datetime.now(timezone.utc)

        ack = RestorationAcknowledgment(
            acknowledgment_id=ack_id,
            operator_id=operator_id,
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            reason="Issues resolved",
            evidence="Audit ID: 123",
            acknowledged_at=now,
        )

        mock_service.request_restoration.return_value = RestorationResult.succeeded(
            new_state=LegitimacyState(
                current_band=LegitimacyBand.STABLE,
                entered_at=now,
                violation_count=5,
                last_triggering_event_id=None,
                last_transition_type=TransitionType.ACKNOWLEDGED,
            ),
            acknowledgment=ack,
        )

        response = client.post(
            "/v1/governance/legitimacy/restore",
            headers={"X-Operator-Id": str(operator_id)},
            json={
                "target_band": "stable",
                "reason": "Issues resolved",
                "evidence": "Audit ID: 123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["acknowledgment_id"] == str(ack_id)
        assert data["from_band"] == "strained"
        assert data["to_band"] == "stable"
        assert data["reason"] == "Issues resolved"
        assert data["evidence"] == "Audit ID: 123"

    def test_restore_unauthorized(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Unauthorized operator returns 403."""
        mock_service.request_restoration.return_value = RestorationResult.failed(
            "Operator not authorized to restore legitimacy"
        )

        response = client.post(
            "/v1/governance/legitimacy/restore",
            headers={"X-Operator-Id": str(uuid4())},
            json={
                "target_band": "stable",
                "reason": "Issues resolved",
                "evidence": "Audit ID: 123",
            },
        )

        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    def test_restore_failed_state_terminal(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """FAILED state returns 422 with terminal message."""
        mock_service.request_restoration.return_value = RestorationResult.failed(
            "FAILED is terminal - reconstitution required"
        )

        response = client.post(
            "/v1/governance/legitimacy/restore",
            headers={"X-Operator-Id": str(uuid4())},
            json={
                "target_band": "compromised",
                "reason": "Trying to restore",
                "evidence": "Evidence",
            },
        )

        assert response.status_code == 422
        assert "terminal" in response.json()["detail"].lower()

    def test_restore_one_step_violated(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Multi-step restoration returns 422."""
        mock_service.request_restoration.return_value = RestorationResult.failed(
            "Restoration must be one step at a time."
        )

        response = client.post(
            "/v1/governance/legitimacy/restore",
            headers={"X-Operator-Id": str(uuid4())},
            json={
                "target_band": "stable",
                "reason": "Trying to skip",
                "evidence": "Evidence",
            },
        )

        assert response.status_code == 422
        assert "one step" in response.json()["detail"].lower()


class TestStatusEndpoint:
    """Tests for GET /v1/governance/legitimacy/status."""

    def test_status_no_auth_required(self, client: TestClient) -> None:
        """Status endpoint does not require authentication."""
        response = client.get("/v1/governance/legitimacy/status")

        assert response.status_code == 200

    def test_status_returns_current_band(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Status returns current legitimacy band."""
        now = datetime.now(timezone.utc)
        mock_service._legitimacy.get_legitimacy_state.return_value = LegitimacyState(
            current_band=LegitimacyBand.STRAINED,
            entered_at=now,
            violation_count=3,
            last_triggering_event_id=uuid4(),
            last_transition_type=TransitionType.AUTOMATIC,
        )
        mock_service.get_restoration_count.return_value = 2

        response = client.get("/v1/governance/legitimacy/status")

        assert response.status_code == 200
        data = response.json()
        assert data["current_band"] == "strained"
        assert data["violation_count"] == 3
        assert data["restoration_count"] == 2
        assert data["last_transition_type"] == "automatic"


class TestHistoryEndpoint:
    """Tests for GET /v1/governance/legitimacy/history."""

    def test_history_no_auth_required(self, client: TestClient) -> None:
        """History endpoint does not require authentication."""
        response = client.get("/v1/governance/legitimacy/history")

        assert response.status_code == 200

    def test_history_returns_acknowledgments(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """History returns list of acknowledgments."""
        ack_id = uuid4()
        operator_id = uuid4()
        now = datetime.now(timezone.utc)

        ack = RestorationAcknowledgment(
            acknowledgment_id=ack_id,
            operator_id=operator_id,
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            reason="Resolved",
            evidence="Evidence",
            acknowledged_at=now,
        )

        mock_service.get_restoration_history.return_value = [ack]
        mock_service.get_restoration_count.return_value = 1

        response = client.get("/v1/governance/legitimacy/history")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["acknowledgment_id"] == str(ack_id)

    def test_history_supports_limit_param(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """History endpoint supports limit parameter."""
        mock_service.get_restoration_history.return_value = []
        mock_service.get_restoration_count.return_value = 0

        response = client.get("/v1/governance/legitimacy/history?limit=10")

        assert response.status_code == 200
        mock_service.get_restoration_history.assert_called_once()
        call_args = mock_service.get_restoration_history.call_args
        assert call_args.kwargs["limit"] == 10


class TestAcknowledgmentEndpoint:
    """Tests for GET /v1/governance/legitimacy/acknowledgment/{id}."""

    def test_acknowledgment_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Returns 404 when acknowledgment not found."""
        mock_service.get_acknowledgment.return_value = None

        ack_id = uuid4()
        response = client.get(
            f"/v1/governance/legitimacy/acknowledgment/{ack_id}"
        )

        assert response.status_code == 404

    def test_acknowledgment_invalid_uuid(self, client: TestClient) -> None:
        """Returns 400 for invalid UUID."""
        response = client.get(
            "/v1/governance/legitimacy/acknowledgment/invalid-uuid"
        )

        assert response.status_code == 400

    def test_acknowledgment_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Returns acknowledgment details when found."""
        ack_id = uuid4()
        operator_id = uuid4()
        now = datetime.now(timezone.utc)

        ack = RestorationAcknowledgment(
            acknowledgment_id=ack_id,
            operator_id=operator_id,
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.STABLE,
            reason="Resolved",
            evidence="Evidence",
            acknowledged_at=now,
        )

        mock_service.get_acknowledgment.return_value = ack

        response = client.get(
            f"/v1/governance/legitimacy/acknowledgment/{ack_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["acknowledgment_id"] == str(ack_id)
        assert data["operator_id"] == str(operator_id)
        assert data["from_band"] == "strained"
        assert data["to_band"] == "stable"
