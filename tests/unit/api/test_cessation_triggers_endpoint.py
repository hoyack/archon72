"""Unit tests for cessation triggers API endpoints (Story 7.7, FR134).

Tests the API endpoints for public access to cessation trigger conditions.

Constitutional Constraints Tested:
- FR134: Public documentation of cessation trigger conditions
- FR44: No authentication required for read endpoints
- FR48: Rate limits identical for all users
- CT-11: Silent failure destroys legitimacy
- CT-13: Reads allowed after cessation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.observer import router
from src.api.middleware.rate_limiter import ObserverRateLimiter
from src.domain.models.cessation_trigger_condition import (
    CessationTriggerCondition,
    CessationTriggerConditionSet,
)


# Create test FastAPI app
def create_test_app() -> FastAPI:
    """Create a test FastAPI app with the observer router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client() -> TestClient:
    """Create a test client with mocked rate limiter."""
    app = create_test_app()

    # Override the rate limiter dependency
    async def mock_rate_limiter() -> ObserverRateLimiter:
        limiter = MagicMock(spec=ObserverRateLimiter)
        limiter.check_rate_limit = AsyncMock()
        return limiter

    # Import and override the dependency
    from src.api.dependencies.observer import get_rate_limiter
    app.dependency_overrides[get_rate_limiter] = mock_rate_limiter

    return TestClient(app)


class TestGetCessationTriggersEndpoint:
    """Tests for GET /v1/observer/cessation-triggers endpoint."""

    def test_endpoint_returns_200(self, client: TestClient) -> None:
        """Test that endpoint returns 200 status."""
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

    def test_endpoint_returns_trigger_conditions(self, client: TestClient) -> None:
        """Test that endpoint returns trigger conditions (FR134)."""
        response = client.get("/v1/observer/cessation-triggers")
        data = response.json()

        assert "trigger_conditions" in data
        assert len(data["trigger_conditions"]) == 5

    def test_endpoint_returns_version_metadata(self, client: TestClient) -> None:
        """Test that endpoint returns version metadata."""
        response = client.get("/v1/observer/cessation-triggers")
        data = response.json()

        assert "schema_version" in data
        assert "constitution_version" in data
        assert "effective_date" in data
        assert "last_updated" in data

    def test_endpoint_returns_all_trigger_types(self, client: TestClient) -> None:
        """Test that endpoint returns all expected trigger types."""
        response = client.get("/v1/observer/cessation-triggers")
        data = response.json()

        trigger_types = {c["trigger_type"] for c in data["trigger_conditions"]}
        expected = {
            "consecutive_failures",
            "rolling_window",
            "anti_success_sustained",
            "petition_threshold",
            "breach_threshold",
        }
        assert trigger_types == expected

    def test_trigger_condition_has_required_fields(self, client: TestClient) -> None:
        """Test that each trigger condition has required fields."""
        response = client.get("/v1/observer/cessation-triggers")
        data = response.json()

        for condition in data["trigger_conditions"]:
            assert "trigger_type" in condition
            assert "threshold" in condition
            assert "description" in condition
            assert "fr_reference" in condition
            assert "constitutional_floor" in condition


class TestGetCessationTriggersJsonLdEndpoint:
    """Tests for GET /v1/observer/cessation-triggers.jsonld endpoint."""

    def test_endpoint_returns_200(self, client: TestClient) -> None:
        """Test that endpoint returns 200 status."""
        response = client.get("/v1/observer/cessation-triggers.jsonld")

        assert response.status_code == 200

    def test_endpoint_returns_json_ld_context(self, client: TestClient) -> None:
        """Test that endpoint returns JSON-LD @context (FR134 AC5)."""
        response = client.get("/v1/observer/cessation-triggers.jsonld")
        data = response.json()

        assert "@context" in data
        assert "cessation" in data["@context"]

    def test_endpoint_returns_json_ld_type(self, client: TestClient) -> None:
        """Test that endpoint returns JSON-LD @type."""
        response = client.get("/v1/observer/cessation-triggers.jsonld")
        data = response.json()

        assert "@type" in data
        assert data["@type"] == "cessation:TriggerConditionSet"

    def test_trigger_conditions_have_type_annotation(self, client: TestClient) -> None:
        """Test that trigger conditions have @type annotation."""
        response = client.get("/v1/observer/cessation-triggers.jsonld")
        data = response.json()

        for condition in data["trigger_conditions"]:
            assert "@type" in condition
            assert condition["@type"] == "cessation:TriggerCondition"


class TestGetCessationTriggerByTypeEndpoint:
    """Tests for GET /v1/observer/cessation-triggers/{trigger_type} endpoint."""

    def test_endpoint_returns_200_for_valid_type(self, client: TestClient) -> None:
        """Test that endpoint returns 200 for valid trigger type."""
        response = client.get("/v1/observer/cessation-triggers/breach_threshold")

        assert response.status_code == 200

    def test_endpoint_returns_correct_trigger(self, client: TestClient) -> None:
        """Test that endpoint returns the correct trigger condition."""
        response = client.get("/v1/observer/cessation-triggers/breach_threshold")
        data = response.json()

        assert data["trigger_type"] == "breach_threshold"
        assert data["threshold"] == 10
        assert data["fr_reference"] == "FR32"

    def test_endpoint_returns_404_for_unknown_type(self, client: TestClient) -> None:
        """Test that endpoint returns 404 for unknown trigger type."""
        response = client.get("/v1/observer/cessation-triggers/nonexistent_type")

        assert response.status_code == 404

    def test_endpoint_returns_rfc7807_error_format(self, client: TestClient) -> None:
        """Test that 404 response follows RFC 7807 format."""
        response = client.get("/v1/observer/cessation-triggers/nonexistent_type")
        data = response.json()

        # RFC 7807 requires these fields
        assert "detail" in data
        assert "type" in data["detail"]
        assert "title" in data["detail"]
        assert "status" in data["detail"]
        assert "detail" in data["detail"]
        assert "instance" in data["detail"]

    def test_consecutive_failures_trigger(self, client: TestClient) -> None:
        """Test retrieving consecutive_failures trigger (FR37)."""
        response = client.get("/v1/observer/cessation-triggers/consecutive_failures")
        data = response.json()

        assert data["trigger_type"] == "consecutive_failures"
        assert data["threshold"] == 3
        assert data["window_days"] == 30
        assert data["fr_reference"] == "FR37"

    def test_rolling_window_trigger(self, client: TestClient) -> None:
        """Test retrieving rolling_window trigger (RT-4)."""
        response = client.get("/v1/observer/cessation-triggers/rolling_window")
        data = response.json()

        assert data["trigger_type"] == "rolling_window"
        assert data["threshold"] == 5
        assert data["window_days"] == 90
        assert data["fr_reference"] == "RT-4"

    def test_anti_success_sustained_trigger(self, client: TestClient) -> None:
        """Test retrieving anti_success_sustained trigger (FR38)."""
        response = client.get("/v1/observer/cessation-triggers/anti_success_sustained")
        data = response.json()

        assert data["trigger_type"] == "anti_success_sustained"
        assert data["threshold"] == 90
        assert data["window_days"] is None
        assert data["fr_reference"] == "FR38"

    def test_petition_threshold_trigger(self, client: TestClient) -> None:
        """Test retrieving petition_threshold trigger (FR39)."""
        response = client.get("/v1/observer/cessation-triggers/petition_threshold")
        data = response.json()

        assert data["trigger_type"] == "petition_threshold"
        assert data["threshold"] == 100
        assert data["window_days"] is None
        assert data["fr_reference"] == "FR39"
