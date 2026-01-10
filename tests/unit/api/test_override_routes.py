"""Unit tests for override routes (Story 5.3, FR25).

Tests for FastAPI router for public override visibility endpoints.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: No authentication required for read endpoints
- FR48: Rate limits identical for all users
- CT-12: Witnessing creates accountability
"""

import inspect
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestOverrideRoutes:
    """Tests for override API routes."""

    def _create_mock_override_event(self, sequence: int = 1):
        """Create a mock override event for testing."""
        from src.domain.events import Event

        initiated_at = datetime.now(timezone.utc)

        return Event(
            event_id=uuid4(),
            sequence=sequence,
            event_type="override.initiated",
            payload={
                "keeper_id": "keeper-alpha-001",
                "scope": "agent_pool_size",
                "duration": 3600,
                "reason": "EMERGENCY_RESPONSE",
                "action_type": "CONFIG_CHANGE",
                "initiated_at": initiated_at.isoformat(),
            },
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=initiated_at,
        )

    @pytest.fixture
    def app_with_override_routes(self):
        """Create FastAPI app with override routes."""
        from src.api.routes.override import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app_with_override_routes):
        """Create test client."""
        return TestClient(app_with_override_routes)

    def test_router_exists(self) -> None:
        """Test that override router exists."""
        from src.api.routes.override import router

        assert router is not None
        assert router.prefix == "/v1/observer/overrides"

    def test_router_has_overrides_tag(self) -> None:
        """Test that router has overrides tag."""
        from src.api.routes.override import router

        assert "overrides" in router.tags

    def test_get_overrides_endpoint_exists(self, client) -> None:
        """Test that GET /v1/observer/overrides endpoint exists."""
        # The endpoint exists but may return empty list due to stub
        response = client.get("/v1/observer/overrides")
        # Should not be 404 (endpoint not found)
        assert response.status_code != 404

    def test_get_override_by_id_endpoint_exists(self, client) -> None:
        """Test that GET /v1/observer/overrides/{override_id} endpoint exists."""
        override_id = uuid4()
        response = client.get(f"/v1/observer/overrides/{override_id}")
        # 404 means "override not found" (endpoint exists and processed request)
        assert response.status_code in (200, 404)
        if response.status_code == 404:
            assert "not found" in response.json().get("detail", "").lower()

    def test_get_overrides_no_auth_required(self) -> None:
        """Test that GET /overrides does not require authentication.

        Per FR44: No authentication required for read endpoints.
        Per FR25: All overrides publicly visible.
        """
        from src.api.routes.override import router

        # Check that no security dependencies are in the route
        for route in router.routes:
            if hasattr(route, "path") and route.path == "":
                # Verify no auth dependencies
                if hasattr(route, "dependencies"):
                    for dep in route.dependencies:
                        dep_str = str(dep).lower()
                        assert "auth" not in dep_str
                        assert "security" not in dep_str
                        assert "bearer" not in dep_str
                break

    def test_endpoints_use_correct_response_models(self) -> None:
        """Test that endpoints use correct response models."""
        from src.api.routes.override import router
        from src.api.models.override import (
            OverrideEventResponse,
            OverrideEventsListResponse,
        )

        # Find routes and check response models
        for route in router.routes:
            if hasattr(route, "path"):
                if route.path == "" and hasattr(route, "response_model"):
                    assert route.response_model == OverrideEventsListResponse
                elif "/{override_id}" in route.path and hasattr(route, "response_model"):
                    assert route.response_model == OverrideEventResponse

    def test_get_overrides_pagination_parameters(self) -> None:
        """Test that GET /overrides accepts pagination parameters."""
        from src.api.routes.override import get_overrides

        sig = inspect.signature(get_overrides)
        params = sig.parameters

        # Should have limit and offset parameters
        assert "limit" in params
        assert "offset" in params

    def test_get_overrides_date_filter_parameters(self) -> None:
        """Test that GET /overrides accepts date filter parameters (AC3)."""
        from src.api.routes.override import get_overrides

        sig = inspect.signature(get_overrides)
        params = sig.parameters

        # Should have start_date and end_date parameters
        assert "start_date" in params
        assert "end_date" in params

    def test_get_overrides_rate_limiter_dependency(self) -> None:
        """Test that GET /overrides has rate limiter dependency (FR48)."""
        from src.api.routes.override import get_overrides

        sig = inspect.signature(get_overrides)
        params = sig.parameters

        # Should have rate_limiter parameter
        assert "rate_limiter" in params

    def test_get_overrides_returns_list_response(self, client) -> None:
        """Test that GET /overrides returns list response format."""
        response = client.get("/v1/observer/overrides")

        assert response.status_code == 200
        data = response.json()

        # Response should have overrides list and pagination
        assert "overrides" in data
        assert "pagination" in data
        assert isinstance(data["overrides"], list)
        assert isinstance(data["pagination"], dict)

    def test_get_overrides_pagination_metadata(self, client) -> None:
        """Test that pagination metadata is included in response (AC3)."""
        response = client.get("/v1/observer/overrides")

        assert response.status_code == 200
        pagination = response.json()["pagination"]

        # Pagination should have required fields
        assert "total_count" in pagination
        assert "offset" in pagination
        assert "limit" in pagination
        assert "has_more" in pagination

    def test_get_overrides_accepts_limit_parameter(self, client) -> None:
        """Test that limit parameter is accepted."""
        response = client.get("/v1/observer/overrides?limit=50")

        assert response.status_code == 200
        pagination = response.json()["pagination"]
        assert pagination["limit"] == 50

    def test_get_overrides_accepts_offset_parameter(self, client) -> None:
        """Test that offset parameter is accepted."""
        response = client.get("/v1/observer/overrides?offset=10")

        assert response.status_code == 200
        pagination = response.json()["pagination"]
        assert pagination["offset"] == 10

    def test_get_overrides_rejects_invalid_limit(self, client) -> None:
        """Test that invalid limit is rejected."""
        # Limit must be >= 1
        response = client.get("/v1/observer/overrides?limit=0")
        assert response.status_code == 422

        # Limit must be <= 1000
        response = client.get("/v1/observer/overrides?limit=1001")
        assert response.status_code == 422

    def test_get_overrides_rejects_negative_offset(self, client) -> None:
        """Test that negative offset is rejected."""
        response = client.get("/v1/observer/overrides?offset=-1")
        assert response.status_code == 422

    def test_get_override_by_id_returns_404_for_nonexistent(self, client) -> None:
        """Test that GET /overrides/{id} returns 404 for nonexistent override."""
        override_id = uuid4()
        response = client.get(f"/v1/observer/overrides/{override_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_override_by_id_rejects_invalid_uuid(self, client) -> None:
        """Test that GET /overrides/{id} rejects invalid UUID."""
        response = client.get("/v1/observer/overrides/invalid-uuid")

        assert response.status_code == 422
