"""Unit tests for external health endpoint (Story 8.3, FR54).

Tests the /health/external endpoint for third-party monitoring services.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable
- CT-11: Silent failure destroys legitimacy

Key Test Scenarios:
1. Returns UP when system is healthy
2. Returns HALTED when halt is active
3. Returns FROZEN when system is ceased
4. No authentication required
5. Response format validation
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.models.external_health import ExternalHealthResponse
from src.api.routes.external_health import router
from src.application.ports.external_health import ExternalHealthStatus
from src.application.services.external_health_service import (
    init_external_health_service,
    reset_external_health_service,
)
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a halt checker stub for testing."""
    return HaltCheckerStub()


@pytest.fixture
def freeze_checker() -> FreezeCheckerStub:
    """Create a freeze checker stub for testing."""
    return FreezeCheckerStub()


@pytest.fixture
def app(halt_checker: HaltCheckerStub, freeze_checker: FreezeCheckerStub) -> FastAPI:
    """Create test FastAPI app with external health route."""
    # Initialize the service
    init_external_health_service(
        halt_checker=halt_checker,
        freeze_checker=freeze_checker,
    )

    app = FastAPI()
    app.include_router(router)

    yield app

    # Cleanup
    reset_external_health_service()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestExternalHealthEndpoint:
    """Tests for /health/external endpoint."""

    def test_returns_up_when_healthy(
        self,
        client: TestClient,
        halt_checker: HaltCheckerStub,
        freeze_checker: FreezeCheckerStub,
    ) -> None:
        """Test endpoint returns UP status when system is healthy.

        AC1: Third-party services can ping the system and get clear status.
        """
        # System is healthy by default (not halted, not frozen)
        response = client.get("/health/external")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "up"
        assert "timestamp" in data

    def test_returns_halted_when_halt_active(
        self, client: TestClient, halt_checker: HaltCheckerStub
    ) -> None:
        """Test endpoint returns HALTED status when halt is active.

        AC4: Halt state visible to external monitors.
        """
        # Trigger halt
        halt_checker.set_halted(True, reason="Test halt")

        response = client.get("/health/external")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "halted"
        assert "timestamp" in data

    def test_returns_frozen_when_system_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Test endpoint returns FROZEN status when system is ceased.

        AC5: Frozen state visible to external monitors.
        """
        # Trigger freeze
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Test cessation",
        )

        response = client.get("/health/external")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "frozen"
        assert "timestamp" in data

    def test_halted_takes_precedence_over_frozen(
        self,
        client: TestClient,
        halt_checker: HaltCheckerStub,
        freeze_checker: FreezeCheckerStub,
    ) -> None:
        """Test that HALTED status takes precedence over FROZEN.

        Both conditions can technically be true simultaneously (edge case).
        HALTED is more severe and should be reported.
        """
        # Both halt and freeze are active
        halt_checker.set_halted(True, reason="Test halt")
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Test cessation",
        )

        response = client.get("/health/external")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "halted"  # HALTED takes precedence

    def test_no_authentication_required(self, client: TestClient) -> None:
        """Test that no authentication is required for the endpoint.

        AC1: Endpoint accessible without authentication.
        FR54: External parties can detect unavailability independently.
        """
        # No auth headers provided
        response = client.get("/health/external")

        # Should succeed without authentication
        assert response.status_code == 200

    def test_response_format_matches_model(self, client: TestClient) -> None:
        """Test response format matches ExternalHealthResponse model.

        Validates that the response is parseable by external monitoring services.
        """
        response = client.get("/health/external")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "status" in data
        assert "timestamp" in data
        assert len(data) == 2  # Only status and timestamp

        # Validate types
        assert isinstance(data["status"], str)
        assert data["status"] in ["up", "halted", "frozen"]

        # Timestamp should be ISO format
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_response_content_type_is_json(self, client: TestClient) -> None:
        """Test response content type is application/json.

        External monitoring services expect JSON responses.
        """
        response = client.get("/health/external")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_timestamp_is_utc(self, client: TestClient) -> None:
        """Test that timestamp is in UTC.

        Consistent timezone is important for monitoring.
        """
        response = client.get("/health/external")

        assert response.status_code == 200
        data = response.json()

        # Parse timestamp
        timestamp_str = data["timestamp"]
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Should be close to now
        now = datetime.now(timezone.utc)
        diff = abs((now - timestamp).total_seconds())
        assert diff < 5  # Within 5 seconds

    def test_status_transitions(
        self,
        client: TestClient,
        halt_checker: HaltCheckerStub,
        freeze_checker: FreezeCheckerStub,
    ) -> None:
        """Test status correctly reflects state transitions.

        System can transition between states, endpoint should reflect current state.
        """
        # Start healthy
        response = client.get("/health/external")
        assert response.json()["status"] == "up"

        # Transition to halted
        halt_checker.set_halted(True, reason="Test halt")
        response = client.get("/health/external")
        assert response.json()["status"] == "halted"

        # Clear halt, should return to up
        halt_checker.set_halted(False)
        response = client.get("/health/external")
        assert response.json()["status"] == "up"

        # Transition to frozen
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Test cessation",
        )
        response = client.get("/health/external")
        assert response.json()["status"] == "frozen"


class TestExternalHealthResponseModel:
    """Tests for ExternalHealthResponse Pydantic model."""

    def test_model_serialization(self) -> None:
        """Test model serializes correctly to JSON."""
        response = ExternalHealthResponse(
            status=ExternalHealthStatus.UP,
            timestamp=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
        )

        data = response.model_dump(mode="json")
        assert data["status"] == "up"
        assert "2026-01-08" in data["timestamp"]

    def test_model_with_all_status_values(self) -> None:
        """Test model works with all status values."""
        for status in ExternalHealthStatus:
            response = ExternalHealthResponse(
                status=status,
                timestamp=datetime.now(timezone.utc),
            )
            data = response.model_dump(mode="json")
            assert data["status"] == status.value
