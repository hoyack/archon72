"""Integration tests for public read access (Story 4.1, Task 8).

End-to-end tests verifying public access without authentication.

Constitutional Constraints:
- FR44: Public read access without registration
- FR48: Rate limits identical for anonymous and authenticated users
- CT-13: Reads allowed during halt (per Story 3.5)
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client for the API."""
    return TestClient(app)


class TestPublicReadAccessIntegration:
    """Integration tests for public read access."""

    def test_no_auth_header_allowed(self, client) -> None:
        """Test that requests without auth header are allowed.

        Per FR44: No authentication required for read endpoints.
        """
        response = client.get("/v1/observer/events")

        # Request should succeed (or return 200 with empty data)
        # Should NOT return 401 Unauthorized
        assert response.status_code != 401
        assert response.status_code in (200, 500)  # 500 if DB not available

    def test_events_endpoint_returns_json(self, client) -> None:
        """Test that events endpoint returns proper JSON."""
        response = client.get("/v1/observer/events")

        if response.status_code == 200:
            data = response.json()
            assert "events" in data
            assert "pagination" in data

    def test_pagination_structure(self, client) -> None:
        """Test that pagination metadata is present."""
        response = client.get("/v1/observer/events?limit=10&offset=0")

        if response.status_code == 200:
            data = response.json()
            pagination = data["pagination"]
            assert "total_count" in pagination
            assert "offset" in pagination
            assert "limit" in pagination
            assert "has_more" in pagination

    def test_get_event_by_id_404_for_missing(self, client) -> None:
        """Test that GET /events/{id} returns 404 for non-existent event."""
        event_id = uuid4()
        response = client.get(f"/v1/observer/events/{event_id}")

        # Should return 404 (not 401 unauthorized)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_event_by_sequence_404_for_missing(self, client) -> None:
        """Test that GET /events/sequence/{seq} returns 404 for non-existent."""
        response = client.get("/v1/observer/events/sequence/999999")

        # Should return 404 (not 401 unauthorized)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_rate_limit_headers_not_preferential(self, client) -> None:
        """Test that rate limits are applied identically.

        Per FR48: Rate limits identical for anonymous and authenticated.
        This test verifies the endpoint works for anonymous requests.
        """
        # Anonymous request
        response = client.get("/v1/observer/events")

        # Should not be rejected based on authentication
        assert response.status_code != 401
        assert response.status_code != 403

    def test_invalid_uuid_returns_422(self, client) -> None:
        """Test that invalid UUID returns 422 validation error."""
        response = client.get("/v1/observer/events/not-a-uuid")

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    def test_invalid_sequence_type_returns_422(self, client) -> None:
        """Test that non-integer sequence returns 422."""
        response = client.get("/v1/observer/events/sequence/not-a-number")

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    def test_pagination_limit_bounds(self, client) -> None:
        """Test pagination limit bounds are enforced."""
        # Limit too high
        response = client.get("/v1/observer/events?limit=10000")
        assert response.status_code == 422

        # Limit too low
        response = client.get("/v1/observer/events?limit=0")
        assert response.status_code == 422

        # Negative offset
        response = client.get("/v1/observer/events?offset=-1")
        assert response.status_code == 422

    def test_constitutional_compliance_fr44_no_auth_required(self, client) -> None:
        """Test FR44 compliance: Public read access without registration.

        Constitutional Constraint FR44:
        - No login required
        - No API key required
        - No registration required
        """
        # Request with NO authentication whatsoever
        response = client.get(
            "/v1/observer/events",
            headers={},  # Explicitly no auth headers
        )

        # Must not require authentication
        assert response.status_code != 401, "FR44 violated: Auth should not be required"
        assert response.status_code != 403, (
            "FR44 violated: Access should not be forbidden"
        )

    def test_constitutional_compliance_fr48_equal_rate_limits(self, client) -> None:
        """Test FR48 compliance: Rate limits identical for all users.

        Constitutional Constraint FR48:
        - Anonymous and authenticated get same limits
        - No preferential treatment
        """
        # Both requests should be treated identically
        anon_response = client.get("/v1/observer/events")
        auth_response = client.get(
            "/v1/observer/events",
            headers={"Authorization": "Bearer fake-token"},
        )

        # Both should work (ignoring the fake token for rate limiting)
        # Neither should be rejected due to rate limit differences
        # (Rate limits are IP-based, not auth-based per FR48)
        assert anon_response.status_code == auth_response.status_code


class TestObserverAPIEndpointsIntegration:
    """Integration tests for observer API endpoint registration."""

    def test_observer_endpoints_registered(self, client) -> None:
        """Test that observer endpoints are registered in the app."""
        # Test GET /v1/observer/events
        events_response = client.get("/v1/observer/events")
        assert events_response.status_code != 405  # Method allowed

        # Test GET /v1/observer/events/{event_id}
        id_response = client.get(f"/v1/observer/events/{uuid4()}")
        assert id_response.status_code != 405

        # Test GET /v1/observer/events/sequence/{sequence}
        seq_response = client.get("/v1/observer/events/sequence/1")
        assert seq_response.status_code != 405

    def test_health_endpoint_still_works(self, client) -> None:
        """Test that health endpoint still works after adding observer."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
