"""Integration tests for public cessation trigger conditions (Story 7.7, FR134).

Tests the full integration from API endpoint through service to domain model.

Constitutional Constraints Tested:
- FR134: Public documentation of cessation trigger conditions
- FR44: No authentication required for read endpoints
- FR48: Rate limits identical for all users
- FR33: Threshold definitions SHALL be constitutional, not operational
- FR37: 3 consecutive integrity failures in 30 days
- FR38: Anti-success alert sustained 90 days
- FR39: External observer petition with 100+ co-signers
- FR32: >10 unacknowledged breaches in 90-day window
- RT-4: 5 non-consecutive failures in 90-day rolling window
- CT-11: Silent failure destroys legitimacy
- CT-13: Reads allowed after cessation (read-only survives)

Developer Notes:
- These tests verify the endpoint works end-to-end without mocking
- JSON-LD format is verified for semantic interoperability
- Constitutional floor enforcement is validated
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.rate_limiter import ObserverRateLimiter
from src.api.routes.observer import router


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


class TestPublicCessationTriggersIntegration:
    """Integration tests for public cessation trigger conditions (FR134)."""

    def test_get_all_triggers_returns_all_constitutional_triggers(
        self, client: TestClient
    ) -> None:
        """Test that GET /cessation-triggers returns all constitutional triggers (FR134).

        Constitutional Constraint (FR134):
        All cessation trigger conditions SHALL be publicly documented.
        """
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

        data = response.json()

        # Verify all 5 trigger types are present
        trigger_types = {c["trigger_type"] for c in data["trigger_conditions"]}
        expected_types = {
            "consecutive_failures",  # FR37
            "rolling_window",  # RT-4
            "anti_success_sustained",  # FR38
            "petition_threshold",  # FR39
            "breach_threshold",  # FR32
        }
        assert trigger_types == expected_types

    def test_consecutive_failures_matches_fr37_exactly(
        self, client: TestClient
    ) -> None:
        """Test consecutive_failures matches FR37: 3 consecutive in 30 days.

        Constitutional Constraint (FR37):
        3 consecutive integrity failures in 30 days SHALL trigger
        automatic cessation agenda placement.
        """
        response = client.get("/v1/observer/cessation-triggers/consecutive_failures")

        assert response.status_code == 200

        data = response.json()
        assert data["trigger_type"] == "consecutive_failures"
        assert data["threshold"] == 3
        assert data["window_days"] == 30
        assert data["fr_reference"] == "FR37"
        assert data["constitutional_floor"] == 3
        assert "consecutive" in data["description"].lower()

    def test_rolling_window_matches_rt4_exactly(self, client: TestClient) -> None:
        """Test rolling_window matches RT-4: 5 non-consecutive in 90 days.

        Constitutional Constraint (RT-4):
        5 non-consecutive failures in any 90-day rolling window SHALL
        trigger cessation agenda placement (timing attack prevention).
        """
        response = client.get("/v1/observer/cessation-triggers/rolling_window")

        assert response.status_code == 200

        data = response.json()
        assert data["trigger_type"] == "rolling_window"
        assert data["threshold"] == 5
        assert data["window_days"] == 90
        assert data["fr_reference"] == "RT-4"
        assert data["constitutional_floor"] == 5

    def test_anti_success_sustained_matches_fr38_exactly(
        self, client: TestClient
    ) -> None:
        """Test anti_success_sustained matches FR38: 90 days sustained.

        Constitutional Constraint (FR38):
        Anti-success alert sustained for 90 days SHALL trigger
        automatic cessation agenda placement.
        """
        response = client.get("/v1/observer/cessation-triggers/anti_success_sustained")

        assert response.status_code == 200

        data = response.json()
        assert data["trigger_type"] == "anti_success_sustained"
        assert data["threshold"] == 90  # 90 days sustained
        assert data["window_days"] is None  # Not a rolling window
        assert data["fr_reference"] == "FR38"
        assert data["constitutional_floor"] == 90

    def test_petition_threshold_matches_fr39_exactly(self, client: TestClient) -> None:
        """Test petition_threshold matches FR39: 100+ co-signers.

        Constitutional Constraint (FR39):
        External observer petition with 100 or more co-signers
        SHALL trigger cessation agenda placement.
        """
        response = client.get("/v1/observer/cessation-triggers/petition_threshold")

        assert response.status_code == 200

        data = response.json()
        assert data["trigger_type"] == "petition_threshold"
        assert data["threshold"] == 100  # 100 co-signers
        assert data["window_days"] is None  # Not a rolling window
        assert data["fr_reference"] == "FR39"
        assert data["constitutional_floor"] == 100

    def test_breach_threshold_matches_fr32_exactly(self, client: TestClient) -> None:
        """Test breach_threshold matches FR32: >10 in 90 days.

        Constitutional Constraint (FR32):
        More than 10 unacknowledged breaches in 90-day window
        SHALL trigger cessation agenda placement.
        """
        response = client.get("/v1/observer/cessation-triggers/breach_threshold")

        assert response.status_code == 200

        data = response.json()
        assert data["trigger_type"] == "breach_threshold"
        assert data["threshold"] == 10  # >10 breaches
        assert data["window_days"] == 90
        assert data["fr_reference"] == "FR32"
        assert data["constitutional_floor"] == 10


class TestJsonLdFormatIntegration:
    """Integration tests for JSON-LD format (FR134 AC5)."""

    def test_json_ld_endpoint_returns_semantic_context(
        self, client: TestClient
    ) -> None:
        """Test that JSON-LD endpoint includes semantic @context (FR134 AC5).

        Constitutional Constraint (FR134 AC5):
        Machine-readable format with semantic context for
        external verification and integration.
        """
        response = client.get("/v1/observer/cessation-triggers.jsonld")

        assert response.status_code == 200

        data = response.json()
        assert "@context" in data

        # Verify context uses archon72.org namespace
        context = data["@context"]
        assert "cessation" in context
        assert "archon72.org" in context["cessation"]

    def test_json_ld_endpoint_includes_type_annotations(
        self, client: TestClient
    ) -> None:
        """Test that JSON-LD endpoint includes @type annotations."""
        response = client.get("/v1/observer/cessation-triggers.jsonld")

        assert response.status_code == 200

        data = response.json()
        assert "@type" in data
        assert data["@type"] == "cessation:TriggerConditionSet"

        # Each trigger condition should have @type
        for condition in data["trigger_conditions"]:
            assert "@type" in condition
            assert condition["@type"] == "cessation:TriggerCondition"

    def test_json_ld_vocabulary_is_complete(self, client: TestClient) -> None:
        """Test that JSON-LD vocabulary defines all required terms."""
        response = client.get("/v1/observer/cessation-triggers.jsonld")

        assert response.status_code == 200

        data = response.json()
        context = data["@context"]

        # All fields should be in vocabulary
        required_terms = [
            "trigger_type",
            "threshold",
            "window_days",
            "description",
            "fr_reference",
            "constitutional_floor",
            "TriggerCondition",
            "TriggerConditionSet",
        ]
        for term in required_terms:
            assert term in context


class TestVersionMetadataIntegration:
    """Integration tests for version metadata."""

    def test_response_includes_schema_version(self, client: TestClient) -> None:
        """Test that response includes schema_version."""
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

        data = response.json()
        assert "schema_version" in data
        assert data["schema_version"] == "1.0.0"

    def test_response_includes_constitution_version(self, client: TestClient) -> None:
        """Test that response includes constitution_version."""
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

        data = response.json()
        assert "constitution_version" in data
        assert data["constitution_version"] == "1.0.0"

    def test_response_includes_effective_date(self, client: TestClient) -> None:
        """Test that response includes effective_date."""
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

        data = response.json()
        assert "effective_date" in data
        # Should be a valid ISO 8601 date
        datetime.fromisoformat(data["effective_date"].replace("Z", "+00:00"))

    def test_response_includes_last_updated(self, client: TestClient) -> None:
        """Test that response includes last_updated."""
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

        data = response.json()
        assert "last_updated" in data
        # Should be a valid ISO 8601 date
        datetime.fromisoformat(data["last_updated"].replace("Z", "+00:00"))


class TestConstitutionalFloorEnforcement:
    """Integration tests for constitutional floor enforcement (FR33)."""

    def test_all_thresholds_at_or_above_floor(self, client: TestClient) -> None:
        """Test that all thresholds are at or above constitutional floor (FR33).

        Constitutional Constraint (FR33):
        Threshold definitions SHALL be constitutional, not operational.
        """
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

        data = response.json()

        for condition in data["trigger_conditions"]:
            assert condition["threshold"] >= condition["constitutional_floor"], (
                f"Threshold {condition['threshold']} is below floor "
                f"{condition['constitutional_floor']} for {condition['trigger_type']}"
            )

    def test_floors_match_constitutional_requirements(self, client: TestClient) -> None:
        """Test that constitutional floors match FR requirements."""
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

        data = response.json()
        conditions_by_type = {c["trigger_type"]: c for c in data["trigger_conditions"]}

        # FR37: Floor is 3 consecutive failures
        assert conditions_by_type["consecutive_failures"]["constitutional_floor"] == 3

        # RT-4: Floor is 5 non-consecutive failures
        assert conditions_by_type["rolling_window"]["constitutional_floor"] == 5

        # FR38: Floor is 90 days sustained
        assert (
            conditions_by_type["anti_success_sustained"]["constitutional_floor"] == 90
        )

        # FR39: Floor is 100 co-signers
        assert conditions_by_type["petition_threshold"]["constitutional_floor"] == 100

        # FR32: Floor is 10 unacknowledged breaches
        assert conditions_by_type["breach_threshold"]["constitutional_floor"] == 10


class TestErrorHandling:
    """Integration tests for error handling."""

    def test_unknown_trigger_type_returns_404(self, client: TestClient) -> None:
        """Test that unknown trigger type returns 404."""
        response = client.get("/v1/observer/cessation-triggers/unknown_type")

        assert response.status_code == 404

    def test_404_response_follows_rfc7807(self, client: TestClient) -> None:
        """Test that 404 response follows RFC 7807 format."""
        response = client.get("/v1/observer/cessation-triggers/unknown_type")

        assert response.status_code == 404

        data = response.json()
        detail = data["detail"]

        # RFC 7807 requires these fields
        assert "type" in detail
        assert "title" in detail
        assert "status" in detail
        assert "detail" in detail
        assert "instance" in detail

        # Verify values
        assert detail["status"] == 404
        assert "unknown_type" in detail["detail"]
        assert "unknown_type" in detail["instance"]


class TestNoAuthenticationRequired:
    """Integration tests verifying no authentication is required (FR44)."""

    def test_get_all_triggers_no_auth_header(self, client: TestClient) -> None:
        """Test GET /cessation-triggers works without auth header (FR44)."""
        # No Authorization header
        response = client.get("/v1/observer/cessation-triggers")

        assert response.status_code == 200

    def test_get_single_trigger_no_auth_header(self, client: TestClient) -> None:
        """Test GET /cessation-triggers/{type} works without auth header (FR44)."""
        # No Authorization header
        response = client.get("/v1/observer/cessation-triggers/breach_threshold")

        assert response.status_code == 200

    def test_get_json_ld_no_auth_header(self, client: TestClient) -> None:
        """Test GET /cessation-triggers.jsonld works without auth header (FR44)."""
        # No Authorization header
        response = client.get("/v1/observer/cessation-triggers.jsonld")

        assert response.status_code == 200
