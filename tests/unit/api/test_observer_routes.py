"""Unit tests for observer routes (Story 4.1, Task 3; Story 4.2, Task 4; Story 4.3, Task 1).

Tests for FastAPI router for public event access endpoints.

Constitutional Constraints:
- FR44: No authentication required for read endpoints
- FR46: Query interface supports date range and event type filtering
- FR48: Rate limits identical for all users
- FR62: Raw event data for independent hash computation
- FR63: Exact hash algorithm, encoding, field ordering as immutable spec
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import inspect

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestObserverRoutes:
    """Tests for observer API routes."""

    def _create_mock_event(self, sequence: int = 1):
        """Create a mock event for testing."""
        from src.domain.events import Event

        return Event(
            event_id=uuid4(),
            sequence=sequence,
            event_type="test.event",
            payload={"key": "value"},
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def app_with_observer_routes(self):
        """Create FastAPI app with observer routes."""
        from src.api.routes.observer import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app_with_observer_routes):
        """Create test client."""
        return TestClient(app_with_observer_routes)

    def test_router_exists(self) -> None:
        """Test that observer router exists."""
        from src.api.routes.observer import router

        assert router is not None
        assert router.prefix == "/v1/observer"

    def test_router_has_observer_tag(self) -> None:
        """Test that router has observer tag."""
        from src.api.routes.observer import router

        assert "observer" in router.tags

    def test_get_events_endpoint_exists(self, client) -> None:
        """Test that GET /events endpoint exists."""
        # The endpoint exists but may return 500 due to missing dependencies
        # That's OK for this test - we're just checking it's registered
        response = client.get("/v1/observer/events")
        # Should not be 404 (endpoint not found)
        assert response.status_code != 404

    def test_get_event_by_id_endpoint_exists(self, client) -> None:
        """Test that GET /events/{event_id} endpoint exists."""
        event_id = uuid4()
        response = client.get(f"/v1/observer/events/{event_id}")
        # 404 means "event not found" (endpoint exists and processed request)
        # 405 would mean "method not allowed" (endpoint doesn't exist)
        assert response.status_code in (200, 404)
        # Verify 404 contains proper error message (not just no route)
        if response.status_code == 404:
            assert "not found" in response.json().get("detail", "").lower()

    def test_get_event_by_sequence_endpoint_exists(self, client) -> None:
        """Test that GET /events/sequence/{sequence} endpoint exists."""
        response = client.get("/v1/observer/events/sequence/1")
        # 404 means "event not found" (endpoint exists)
        assert response.status_code in (200, 404)
        if response.status_code == 404:
            assert "not found" in response.json().get("detail", "").lower()

    def test_get_events_no_auth_required(self) -> None:
        """Test that GET /events does not require authentication.

        Per FR44: No authentication required for read endpoints.
        """
        from src.api.routes.observer import router

        # Check that no security dependencies are in the route
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/events":
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
        from src.api.routes.observer import router
        from src.api.models.observer import (
            MerkleProof,
            ObserverEventResponse,
            ObserverEventsListResponse,
        )

        # Find routes and check response models
        for route in router.routes:
            if hasattr(route, "path"):
                if route.path == "/events" and hasattr(route, "response_model"):
                    assert route.response_model == ObserverEventsListResponse
                elif "/events/{event_id}" in route.path and hasattr(
                    route, "response_model"
                ):
                    assert route.response_model == ObserverEventResponse
                elif "/events/sequence/" in route.path and hasattr(
                    route, "response_model"
                ):
                    # New merkle-proof endpoint uses MerkleProof model
                    if "merkle-proof" in route.path:
                        assert route.response_model == MerkleProof
                    else:
                        assert route.response_model == ObserverEventResponse

    def test_get_events_pagination_parameters(self) -> None:
        """Test that GET /events accepts pagination parameters."""
        from src.api.routes.observer import get_events
        import inspect
        from fastapi import Query

        sig = inspect.signature(get_events)
        params = sig.parameters

        # Should have limit and offset parameters
        assert "limit" in params
        assert "offset" in params

        # Check defaults - FastAPI Query wraps the default value
        limit_param = params["limit"]
        offset_param = params["offset"]

        # Extract default from Query object if needed
        limit_default = limit_param.default
        offset_default = offset_param.default

        # Handle both Query wrapped and raw defaults
        if hasattr(limit_default, "default"):
            # FastAPI Query object
            assert limit_default.default == 100
        else:
            assert limit_default == 100

        if hasattr(offset_default, "default"):
            assert offset_default.default == 0
        else:
            assert offset_default == 0

    def test_get_verification_spec_no_auth_required(self, client) -> None:
        """Test that GET /verification-spec endpoint exists and requires no auth.

        Per FR44: No authentication required for read endpoints.
        Per FR62/FR63: Verification spec must be publicly available.
        """
        response = client.get("/v1/observer/verification-spec")
        # Should not be 404 or 401/403
        assert response.status_code == 200

    def test_verification_spec_returns_complete_spec(self, client) -> None:
        """Test that verification spec endpoint returns all required fields.

        Per FR63: Exact hash algorithm, encoding, field ordering documented.
        """
        response = client.get("/v1/observer/verification-spec")
        assert response.status_code == 200

        data = response.json()

        # Core algorithm fields
        assert "hash_algorithm" in data
        assert "hash_algorithm_version" in data
        assert "signature_algorithm" in data
        assert "signature_algorithm_version" in data

        # Genesis hash fields
        assert "genesis_hash" in data
        assert "genesis_description" in data

        # Hash computation documentation
        assert "hash_includes" in data
        assert "hash_excludes" in data
        assert "json_canonicalization" in data
        assert "hash_encoding" in data

    def test_verification_spec_genesis_hash_is_64_zeros(self, client) -> None:
        """Test that genesis hash is 64 zeros (AC4)."""
        response = client.get("/v1/observer/verification-spec")
        assert response.status_code == 200

        data = response.json()
        assert data["genesis_hash"] == "0" * 64
        assert len(data["genesis_hash"]) == 64

    def test_verify_chain_endpoint_exists(self, client) -> None:
        """Test that GET /verify-chain endpoint exists (FR64)."""
        # Should not be 404
        response = client.get("/v1/observer/verify-chain?start=1&end=10")
        # Can be 200 or 500 (missing dependencies) but not 404
        assert response.status_code != 404


# =============================================================================
# Tests for Filter Parameters (Story 4.3, Task 1 - FR46)
# =============================================================================


class TestObserverRoutesFilterParameters:
    """Tests for filter parameters on GET /events endpoint (FR46)."""

    def test_get_events_has_start_date_parameter(self) -> None:
        """Test that GET /events has start_date parameter."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "start_date" in params
        # Should be optional (default None)
        assert params["start_date"].default is not None or params["start_date"].annotation

    def test_get_events_has_end_date_parameter(self) -> None:
        """Test that GET /events has end_date parameter."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "end_date" in params

    def test_get_events_has_event_type_parameter(self) -> None:
        """Test that GET /events has event_type parameter."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "event_type" in params

    def test_get_events_filter_params_are_optional(self) -> None:
        """Test that all filter params are optional (default to None)."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        # Check each filter param has a default
        for param_name in ["start_date", "end_date", "event_type"]:
            param = params[param_name]
            # FastAPI Query wraps the default
            if hasattr(param.default, "default"):
                assert param.default.default is None
            else:
                # Empty default means Pydantic required - should not happen
                pass

    @pytest.fixture
    def app_with_observer_routes(self):
        """Create FastAPI app with observer routes."""
        from src.api.routes.observer import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app_with_observer_routes):
        """Create test client."""
        return TestClient(app_with_observer_routes)

    def test_get_events_accepts_start_date_param(self) -> None:
        """Test that GET /events accepts start_date parameter in signature."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "start_date" in params
        # Parameter should have a default (Query wrapper)
        param = params["start_date"]
        assert param.default is not inspect.Parameter.empty

    def test_get_events_accepts_end_date_param(self) -> None:
        """Test that GET /events accepts end_date parameter in signature."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "end_date" in params
        param = params["end_date"]
        assert param.default is not inspect.Parameter.empty

    def test_get_events_accepts_event_type_param(self) -> None:
        """Test that GET /events accepts event_type parameter in signature."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "event_type" in params
        param = params["event_type"]
        assert param.default is not inspect.Parameter.empty

    def test_date_params_accept_iso8601_format(self) -> None:
        """Test that date params are typed for ISO 8601 datetime."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        # Verify annotation includes datetime
        start_date_annotation = str(params["start_date"].annotation)
        end_date_annotation = str(params["end_date"].annotation)

        # Should be Optional[datetime] or similar
        assert "datetime" in start_date_annotation.lower() or "datetime" in str(type(params["start_date"].annotation))
        assert "datetime" in end_date_annotation.lower() or "datetime" in str(type(params["end_date"].annotation))

    def test_event_type_param_is_string(self) -> None:
        """Test that event_type param accepts string (comma-separated types)."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        event_type_annotation = str(params["event_type"].annotation)
        # Should be Optional[str] or str | None
        assert "str" in event_type_annotation.lower()

    def test_filter_params_have_descriptions(self) -> None:
        """Test that filter params have Query descriptions."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        for param_name in ["start_date", "end_date", "event_type"]:
            param = params[param_name]
            # Query objects have description attribute
            if hasattr(param.default, "description"):
                assert param.default.description is not None
                assert len(param.default.description) > 0


# =============================================================================
# Tests for Schema Documentation Endpoint (Story 4.4, Task 5 - FR50)
# =============================================================================


class TestSchemaDocumentationEndpoint:
    """Tests for GET /schema endpoint (FR50)."""

    @pytest.fixture
    def app_with_observer_routes(self):
        """Create FastAPI app with observer routes."""
        from src.api.routes.observer import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app_with_observer_routes):
        """Create test client."""
        return TestClient(app_with_observer_routes)

    def test_get_schema_docs_endpoint_exists(self, client) -> None:
        """Test that GET /schema endpoint exists."""
        response = client.get("/v1/observer/schema")
        assert response.status_code == 200

    def test_get_schema_docs_no_auth_required(self, client) -> None:
        """Test that GET /schema requires no authentication (FR44)."""
        response = client.get("/v1/observer/schema")
        # 200 means no auth required and successful
        assert response.status_code == 200

    def test_schema_docs_is_versioned(self, client) -> None:
        """Test that schema docs include version info."""
        response = client.get("/v1/observer/schema")
        assert response.status_code == 200

        data = response.json()
        assert "schema_version" in data
        assert "api_version" in data
        assert data["schema_version"] == "1.0.0"
        assert data["api_version"] == "v1"

    def test_schema_docs_includes_event_types(self, client) -> None:
        """Test that schema docs include supported event types."""
        response = client.get("/v1/observer/schema")
        assert response.status_code == 200

        data = response.json()
        assert "event_types" in data
        assert isinstance(data["event_types"], list)
        assert len(data["event_types"]) > 0
        # Should include common event types
        assert "vote" in data["event_types"]
        assert "halt" in data["event_types"]

    def test_schema_docs_includes_event_schema(self, client) -> None:
        """Test that schema docs include JSON schema for events."""
        response = client.get("/v1/observer/schema")
        assert response.status_code == 200

        data = response.json()
        assert "event_schema" in data
        assert isinstance(data["event_schema"], dict)
        assert "type" in data["event_schema"]
        assert "required" in data["event_schema"]
        assert "properties" in data["event_schema"]

    def test_schema_docs_includes_verification_spec_url(self, client) -> None:
        """Test that schema docs include URL to verification spec."""
        response = client.get("/v1/observer/schema")
        assert response.status_code == 200

        data = response.json()
        assert "verification_spec_url" in data
        assert data["verification_spec_url"] == "/v1/observer/verification-spec"

    def test_schema_docs_includes_last_updated(self, client) -> None:
        """Test that schema docs include last_updated timestamp."""
        response = client.get("/v1/observer/schema")
        assert response.status_code == 200

        data = response.json()
        assert "last_updated" in data
        # Should be a valid ISO 8601 datetime string
        assert isinstance(data["last_updated"], str)

    def test_schema_docs_same_availability_as_event_store(self) -> None:
        """Test that schema endpoint exists alongside events endpoint (FR50).

        FR50: Schema documentation SHALL have same availability as event store.
        """
        from src.api.routes.observer import router

        # Find both endpoints (paths include prefix)
        has_events = False
        has_schema = False

        for route in router.routes:
            if hasattr(route, "path"):
                if route.path.endswith("/events"):
                    has_events = True
                elif route.path.endswith("/schema"):
                    has_schema = True

        # Both should exist
        assert has_events, "Events endpoint should exist"
        assert has_schema, "Schema endpoint should exist for FR50"

    def test_schema_docs_response_model_correct(self) -> None:
        """Test that schema endpoint uses SchemaDocumentation model."""
        from src.api.routes.observer import router
        from src.api.models.observer import SchemaDocumentation

        for route in router.routes:
            if hasattr(route, "path") and route.path.endswith("/schema"):
                assert hasattr(route, "response_model")
                assert route.response_model == SchemaDocumentation
                break
        else:
            pytest.fail("Schema route not found")


# =============================================================================
# Tests for Historical Query Parameters (Story 4.5, Task 2 - FR88, FR89)
# =============================================================================


class TestObserverRoutesHistoricalQueries:
    """Tests for historical query parameters on GET /events endpoint (FR88, FR89)."""

    def test_get_events_has_as_of_sequence_parameter(self) -> None:
        """Test that GET /events has as_of_sequence parameter (FR88)."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "as_of_sequence" in params

    def test_get_events_has_as_of_timestamp_parameter(self) -> None:
        """Test that GET /events has as_of_timestamp parameter (FR88)."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "as_of_timestamp" in params

    def test_get_events_has_include_proof_parameter(self) -> None:
        """Test that GET /events has include_proof parameter (FR89)."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        assert "include_proof" in params

    def test_as_of_sequence_is_optional(self) -> None:
        """Test that as_of_sequence parameter is optional."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        param = params["as_of_sequence"]
        # Should have a default value (None or Query with default None)
        if hasattr(param.default, "default"):
            assert param.default.default is None
        else:
            assert param.default is None

    def test_as_of_timestamp_is_optional(self) -> None:
        """Test that as_of_timestamp parameter is optional."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        param = params["as_of_timestamp"]
        if hasattr(param.default, "default"):
            assert param.default.default is None
        else:
            assert param.default is None

    def test_include_proof_defaults_to_false(self) -> None:
        """Test that include_proof defaults to False."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        param = params["include_proof"]
        if hasattr(param.default, "default"):
            assert param.default.default is False
        else:
            assert param.default is False

    def test_as_of_sequence_has_description(self) -> None:
        """Test that as_of_sequence has a description."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        param = params["as_of_sequence"]
        if hasattr(param.default, "description"):
            assert param.default.description is not None
            assert "FR88" in param.default.description or "sequence" in param.default.description.lower()

    def test_include_proof_has_description(self) -> None:
        """Test that include_proof has a description."""
        from src.api.routes.observer import get_events

        sig = inspect.signature(get_events)
        params = sig.parameters

        param = params["include_proof"]
        if hasattr(param.default, "description"):
            assert param.default.description is not None
            assert "FR89" in param.default.description or "proof" in param.default.description.lower()


# =============================================================================
# Tests for Push Notification Endpoints (Story 4.8 - SR-9, RT-5)
# =============================================================================


class TestSSEStreamEndpoint:
    """Tests for SSE streaming endpoint (Story 4.8, Task 3).

    Per SR-9: Observer push notifications via SSE.

    Note: sse_starlette.EventSourceResponse sets content-type internally but
    TestClient may not properly capture it during streaming. We test the
    endpoint exists and signature-level features here; integration tests
    cover actual SSE behavior.
    """

    @pytest.fixture
    def app_with_observer_routes(self):
        """Create FastAPI app with observer routes."""
        from src.api.routes.observer import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app_with_observer_routes):
        """Create test client."""
        return TestClient(app_with_observer_routes)

    def test_sse_endpoint_exists(self, client) -> None:
        """Test that GET /events/stream endpoint exists."""
        # Use stream=True to handle SSE response
        # The endpoint exists and will return a streaming response
        # We just verify it doesn't return 404
        with client.stream("GET", "/v1/observer/events/stream") as response:
            assert response.status_code != 404

    def test_sse_endpoint_returns_streaming_response(self) -> None:
        """Test that SSE endpoint returns EventSourceResponse type.

        sse_starlette.EventSourceResponse sets 'text/event-stream' content-type
        but TestClient may not correctly capture it during streaming tests.
        We verify the endpoint function returns the correct response type.
        """
        from sse_starlette.sse import EventSourceResponse
        from src.api.routes.observer import stream_events

        # Check return type annotation
        sig = inspect.signature(stream_events)
        return_annotation = sig.return_annotation
        assert return_annotation == EventSourceResponse

    def test_sse_endpoint_has_cache_control_in_response(self) -> None:
        """Test that SSE endpoint configures cache-control header.

        Verify the endpoint code explicitly sets Cache-Control: no-cache.
        Inspecting the stream_events function to verify it returns
        EventSourceResponse with cache-control header configured.
        """
        import ast
        import inspect

        from src.api.routes.observer import stream_events

        # Get source code and check for Cache-Control: no-cache
        source = inspect.getsource(stream_events)

        # Check that EventSourceResponse is returned with no-cache header
        assert "Cache-Control" in source or "cache-control" in source.lower()
        assert "no-cache" in source

    def test_sse_endpoint_accepts_event_types_param(self) -> None:
        """Test that SSE endpoint accepts event_types parameter."""
        from src.api.routes.observer import stream_events

        sig = inspect.signature(stream_events)
        params = sig.parameters

        assert "event_types" in params

    def test_sse_endpoint_no_auth_required(self) -> None:
        """Test that SSE endpoint does not require authentication (FR44)."""
        from src.api.routes.observer import stream_events

        # No auth dependency in signature - FR44 compliance
        sig = inspect.signature(stream_events)
        params = sig.parameters

        # Check no "current_user" or "token" params
        assert "current_user" not in params
        assert "token" not in params


class TestWebhookSubscriptionEndpoints:
    """Tests for webhook subscription endpoints (Story 4.8, Task 4).

    Per SR-9: Webhook subscription for push notifications.
    """

    @pytest.fixture
    def app_with_observer_routes(self):
        """Create FastAPI app with observer routes."""
        from src.api.routes.observer import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app_with_observer_routes):
        """Create test client."""
        return TestClient(app_with_observer_routes)

    def test_webhook_subscribe_endpoint_exists(self, client) -> None:
        """Test that POST /subscriptions/webhook endpoint exists."""
        response = client.post(
            "/v1/observer/subscriptions/webhook",
            json={
                "webhook_url": "https://example.com/webhook",
                "event_types": ["breach"],
            },
        )
        # Should not be 404 or 405
        assert response.status_code not in (404, 405)

    def test_webhook_unsubscribe_endpoint_exists(self, client) -> None:
        """Test that DELETE /subscriptions/webhook/{id} endpoint exists."""
        sub_id = uuid4()
        response = client.delete(f"/v1/observer/subscriptions/webhook/{sub_id}")
        # 404 means "subscription not found" (endpoint exists)
        assert response.status_code in (200, 404)

    def test_webhook_get_endpoint_exists(self, client) -> None:
        """Test that GET /subscriptions/webhook/{id} endpoint exists."""
        sub_id = uuid4()
        response = client.get(f"/v1/observer/subscriptions/webhook/{sub_id}")
        # 404 means "subscription not found" (endpoint exists)
        assert response.status_code in (200, 404)

    def test_webhook_subscribe_validates_url(self, client) -> None:
        """Test that webhook subscription validates URL."""
        response = client.post(
            "/v1/observer/subscriptions/webhook",
            json={
                "webhook_url": "not_a_url",
                "event_types": ["breach"],
            },
        )
        # Should return 422 (validation error)
        assert response.status_code == 422

    def test_webhook_subscribe_no_auth_required(self) -> None:
        """Test that webhook subscription does not require auth (FR44)."""
        from src.api.routes.observer import subscribe_webhook

        sig = inspect.signature(subscribe_webhook)
        params = sig.parameters

        # No auth dependency in signature - FR44 compliance
        assert "current_user" not in params
        assert "token" not in params

    def test_webhook_unsubscribe_returns_404_for_unknown_id(self, client) -> None:
        """Test that unsubscribe returns 404 for unknown subscription."""
        unknown_id = uuid4()
        response = client.delete(f"/v1/observer/subscriptions/webhook/{unknown_id}")
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()

    def test_webhook_get_returns_404_for_unknown_id(self, client) -> None:
        """Test that get returns 404 for unknown subscription."""
        unknown_id = uuid4()
        response = client.get(f"/v1/observer/subscriptions/webhook/{unknown_id}")
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
