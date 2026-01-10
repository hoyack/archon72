"""Unit tests for configuration health endpoint (Story 6.10, NFR39, AC6).

Tests for the GET /v1/configuration/health endpoint.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
- AC6: Health endpoint should report floor status
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


class TestConfigurationHealthEndpoint:
    """Tests for GET /v1/configuration/health endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app, raise_server_exceptions=False)

    def test_endpoint_exists(self, client: TestClient) -> None:
        """Endpoint should exist at /v1/configuration/health."""
        response = client.get("/v1/configuration/health")
        # Should not be 404
        assert response.status_code != 404

    def test_returns_200_when_healthy(self, client: TestClient) -> None:
        """Should return 200 OK when all configurations are valid."""
        response = client.get("/v1/configuration/health")
        assert response.status_code == 200

    def test_response_includes_is_healthy(self, client: TestClient) -> None:
        """Response should include is_healthy field."""
        response = client.get("/v1/configuration/health")
        data = response.json()
        assert "is_healthy" in data
        assert isinstance(data["is_healthy"], bool)

    def test_response_includes_threshold_statuses(self, client: TestClient) -> None:
        """Response should include threshold_statuses list."""
        response = client.get("/v1/configuration/health")
        data = response.json()
        assert "threshold_statuses" in data
        assert isinstance(data["threshold_statuses"], list)

    def test_threshold_status_includes_required_fields(self, client: TestClient) -> None:
        """Each threshold status should include required fields."""
        response = client.get("/v1/configuration/health")
        data = response.json()

        assert len(data["threshold_statuses"]) > 0
        first_status = data["threshold_statuses"][0]

        assert "threshold_name" in first_status
        assert "floor_value" in first_status
        assert "current_value" in first_status
        assert "is_valid" in first_status

    def test_all_thresholds_are_valid_by_default(self, client: TestClient) -> None:
        """All thresholds should be valid with default configuration."""
        response = client.get("/v1/configuration/health")
        data = response.json()

        assert data["is_healthy"] is True
        for status in data["threshold_statuses"]:
            assert status["is_valid"] is True

    def test_response_includes_checked_at_timestamp(self, client: TestClient) -> None:
        """Response should include checked_at timestamp."""
        response = client.get("/v1/configuration/health")
        data = response.json()
        assert "checked_at" in data
        # Should be ISO format timestamp
        assert isinstance(data["checked_at"], str)
        assert "T" in data["checked_at"]  # ISO format

    def test_known_thresholds_present(self, client: TestClient) -> None:
        """Should include known constitutional thresholds."""
        response = client.get("/v1/configuration/health")
        data = response.json()

        threshold_names = {s["threshold_name"] for s in data["threshold_statuses"]}

        # Should include at least these known thresholds
        assert "cessation_breach_count" in threshold_names
        assert "recovery_waiting_hours" in threshold_names
        assert "minimum_keeper_quorum" in threshold_names
