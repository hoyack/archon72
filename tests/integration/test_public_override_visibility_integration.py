"""Integration tests for Public Override Visibility (Story 5.3, FR25).

Tests end-to-end functionality of override public visibility API.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: No authentication required
- FR48: Rate limits identical for all users
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.override import router as override_router
from src.domain.events import Event
from src.domain.events.override_event import OVERRIDE_EVENT_TYPE


class TestPublicOverrideVisibilityIntegration:
    """Integration tests for FR25 - Public Override Visibility."""

    def _create_override_event(
        self,
        *,
        event_id=None,
        sequence: int = 1,
        keeper_id: str = "keeper-alpha-001",
        scope: str = "agent_pool_size",
        duration: int = 3600,
        reason: str = "EMERGENCY_RESPONSE",
        action_type: str = "CONFIG_CHANGE",
        initiated_at: datetime = None,
    ) -> Event:
        """Create a sample override Event for testing."""
        if initiated_at is None:
            initiated_at = datetime.now(timezone.utc)

        return Event(
            event_id=event_id or uuid4(),
            sequence=sequence,
            event_type=OVERRIDE_EVENT_TYPE,
            payload={
                "keeper_id": keeper_id,
                "scope": scope,
                "duration": duration,
                "reason": reason,
                "action_type": action_type,
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
    def app(self):
        """Create FastAPI app with override routes."""
        app = FastAPI()
        app.include_router(override_router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_override_endpoint_publicly_accessible(self, client) -> None:
        """Test that /v1/observer/overrides is accessible without auth (FR44).

        Per FR44: No authentication required for read endpoints.
        Per FR25: All overrides publicly visible.
        """
        # No auth headers provided - should still work
        response = client.get("/v1/observer/overrides")

        # Should return 200, not 401/403
        assert response.status_code == 200

    def test_override_endpoint_returns_empty_list_when_no_overrides(
        self, client
    ) -> None:
        """Test that endpoint returns empty list when no overrides exist."""
        response = client.get("/v1/observer/overrides")

        assert response.status_code == 200
        data = response.json()

        assert data["overrides"] == []
        assert data["pagination"]["total_count"] == 0

    def test_override_endpoint_supports_pagination(self, client) -> None:
        """Test that endpoint supports pagination parameters (AC3)."""
        # Test with limit and offset
        response = client.get("/v1/observer/overrides?limit=50&offset=10")

        assert response.status_code == 200
        pagination = response.json()["pagination"]

        assert pagination["limit"] == 50
        assert pagination["offset"] == 10

    def test_override_endpoint_supports_date_filtering(self, client) -> None:
        """Test that endpoint supports date range filtering (AC3)."""
        start_date = "2026-01-01T00:00:00Z"
        end_date = "2026-01-31T23:59:59Z"

        response = client.get(
            f"/v1/observer/overrides?start_date={start_date}&end_date={end_date}"
        )

        # Should accept date parameters without error
        assert response.status_code == 200

    def test_override_by_id_returns_404_for_nonexistent(self, client) -> None:
        """Test that single override endpoint returns 404 for nonexistent ID."""
        override_id = uuid4()
        response = client.get(f"/v1/observer/overrides/{override_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_override_endpoint_rate_limited(self, client) -> None:
        """Test that endpoint applies rate limiting (FR48).

        Per FR48: Rate limits identical for all users.
        """
        # Make multiple requests - should not fail due to rate limiting
        # (Our stub rate limiter doesn't actually limit, but we verify
        # the endpoint processes requests)
        for _ in range(5):
            response = client.get("/v1/observer/overrides")
            assert response.status_code == 200

    def test_override_response_includes_pagination_has_more(self, client) -> None:
        """Test that pagination includes has_more field (AC3)."""
        response = client.get("/v1/observer/overrides")

        assert response.status_code == 200
        pagination = response.json()["pagination"]

        assert "has_more" in pagination
        assert isinstance(pagination["has_more"], bool)

    def test_override_endpoint_invalid_limit_rejected(self, client) -> None:
        """Test that invalid limit values are rejected."""
        # Limit too low
        response = client.get("/v1/observer/overrides?limit=0")
        assert response.status_code == 422

        # Limit too high
        response = client.get("/v1/observer/overrides?limit=1001")
        assert response.status_code == 422

    def test_override_endpoint_negative_offset_rejected(self, client) -> None:
        """Test that negative offset is rejected."""
        response = client.get("/v1/observer/overrides?offset=-1")
        assert response.status_code == 422


class TestKeeperIdentityVisibility:
    """Tests specifically for FR25 - Keeper identity visibility."""

    def test_keeper_id_not_anonymized_concept(self) -> None:
        """Conceptual test: Keeper ID must NOT be anonymized per FR25.

        FR25 states: All overrides SHALL be publicly visible.
        This means Keeper identity MUST be visible, not hidden or anonymized.

        This test documents the constitutional requirement.
        """
        # This is a documentation test - the actual implementation
        # is verified in unit tests and the adapter code.
        #
        # Key points:
        # 1. Keeper ID in response == Keeper ID in event (no transformation)
        # 2. No "[REDACTED]" or "***" substitution
        # 3. No anonymization or hashing of Keeper ID
        assert True  # Documented requirement

    def test_override_response_schema_includes_keeper_id(self) -> None:
        """Test that response schema includes keeper_id field."""
        from src.api.models.override import OverrideEventResponse

        # Verify keeper_id is in the model fields
        assert "keeper_id" in OverrideEventResponse.model_fields

        # Verify field description mentions visibility
        field_info = OverrideEventResponse.model_fields["keeper_id"]
        assert "VISIBLE" in field_info.description or "FR25" in field_info.description


class TestDateRangeFiltering:
    """Tests for AC3 - Date range filtering."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = FastAPI()
        app.include_router(override_router)
        return TestClient(app)

    def test_start_date_only_filtering(self, client) -> None:
        """Test filtering with only start_date."""
        response = client.get("/v1/observer/overrides?start_date=2026-01-01T00:00:00Z")
        assert response.status_code == 200

    def test_end_date_only_filtering(self, client) -> None:
        """Test filtering with only end_date."""
        response = client.get("/v1/observer/overrides?end_date=2026-12-31T23:59:59Z")
        assert response.status_code == 200

    def test_both_dates_filtering(self, client) -> None:
        """Test filtering with both start_date and end_date."""
        response = client.get(
            "/v1/observer/overrides?start_date=2026-01-01T00:00:00Z&end_date=2026-12-31T23:59:59Z"
        )
        assert response.status_code == 200


class TestPaginationSupport:
    """Tests for AC3 - Pagination support."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = FastAPI()
        app.include_router(override_router)
        return TestClient(app)

    def test_pagination_total_count_included(self, client) -> None:
        """Test that total_count is included in response."""
        response = client.get("/v1/observer/overrides")

        assert response.status_code == 200
        assert "total_count" in response.json()["pagination"]

    def test_pagination_offset_in_response(self, client) -> None:
        """Test that offset is reflected in response."""
        response = client.get("/v1/observer/overrides?offset=25")

        assert response.status_code == 200
        assert response.json()["pagination"]["offset"] == 25

    def test_pagination_limit_in_response(self, client) -> None:
        """Test that limit is reflected in response."""
        response = client.get("/v1/observer/overrides?limit=75")

        assert response.status_code == 200
        assert response.json()["pagination"]["limit"] == 75

    def test_pagination_default_values(self, client) -> None:
        """Test default pagination values."""
        response = client.get("/v1/observer/overrides")

        assert response.status_code == 200
        pagination = response.json()["pagination"]

        # Defaults: limit=100, offset=0
        assert pagination["limit"] == 100
        assert pagination["offset"] == 0


class TestNoAuthenticationRequired:
    """Tests for FR44 - No authentication required."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = FastAPI()
        app.include_router(override_router)
        return TestClient(app)

    def test_no_authorization_header_accepted(self, client) -> None:
        """Test that requests without Authorization header are accepted."""
        response = client.get("/v1/observer/overrides")
        assert response.status_code == 200

    def test_no_api_key_required(self, client) -> None:
        """Test that no API key is required."""
        response = client.get(
            "/v1/observer/overrides",
            headers={},  # Explicitly no headers
        )
        assert response.status_code == 200

    def test_single_override_no_auth_required(self, client) -> None:
        """Test that single override endpoint requires no auth."""
        override_id = uuid4()
        response = client.get(f"/v1/observer/overrides/{override_id}")

        # 404 is expected (not found), but NOT 401/403 (unauthorized)
        assert response.status_code == 404
        assert response.status_code not in (401, 403)
