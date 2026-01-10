"""Unit tests for export routes (Story 4.7, Task 3).

Tests for regulatory export endpoints (FR139, FR140).

Constitutional Constraints:
- FR44: No authentication required
- FR48: Rate limits identical for all users
- FR139: Export SHALL support structured audit format (JSON Lines, CSV)
- FR140: Third-party attestation interface with attestation metadata
"""

import inspect
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestExportEndpointsExist:
    """Tests to verify export endpoints are registered."""

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

    def test_export_endpoint_exists(self, client) -> None:
        """Test that GET /export endpoint exists (FR139)."""
        response = client.get("/v1/observer/export")
        # Should not be 404 (endpoint not found)
        # May be 500 due to missing dependencies or streaming issues
        assert response.status_code != 404

    def test_export_attestation_endpoint_exists(self, client) -> None:
        """Test that GET /export/attestation endpoint exists (FR140)."""
        response = client.get(
            "/v1/observer/export/attestation",
            params={"start_sequence": 1, "end_sequence": 10},
        )
        # Should not be 404 (endpoint not found)
        assert response.status_code != 404


class TestExportEndpointParameters:
    """Tests for export endpoint parameters."""

    def test_export_has_format_parameter(self) -> None:
        """Test that export endpoint has format parameter (FR139)."""
        from src.api.routes.observer import export_events

        sig = inspect.signature(export_events)
        params = sig.parameters

        assert "format" in params
        # Default should be jsonl
        assert params["format"].default.default == "jsonl"

    def test_export_has_include_attestation_parameter(self) -> None:
        """Test that export endpoint has include_attestation parameter (FR140)."""
        from src.api.routes.observer import export_events

        sig = inspect.signature(export_events)
        params = sig.parameters

        assert "include_attestation" in params
        assert params["include_attestation"].default.default is False

    def test_export_has_sequence_filter_parameters(self) -> None:
        """Test that export endpoint has sequence filter parameters."""
        from src.api.routes.observer import export_events

        sig = inspect.signature(export_events)
        params = sig.parameters

        assert "start_sequence" in params
        assert "end_sequence" in params

    def test_export_has_date_filter_parameters(self) -> None:
        """Test that export endpoint has date filter parameters."""
        from src.api.routes.observer import export_events

        sig = inspect.signature(export_events)
        params = sig.parameters

        assert "start_date" in params
        assert "end_date" in params

    def test_export_has_event_type_parameter(self) -> None:
        """Test that export endpoint has event type filter parameter."""
        from src.api.routes.observer import export_events

        sig = inspect.signature(export_events)
        params = sig.parameters

        assert "event_type" in params


class TestExportAttestationParameters:
    """Tests for attestation endpoint parameters."""

    def test_attestation_endpoint_requires_sequence_range(self) -> None:
        """Test that attestation endpoint requires start/end sequence."""
        from src.api.routes.observer import get_attestation_for_range

        sig = inspect.signature(get_attestation_for_range)
        params = sig.parameters

        assert "start_sequence" in params
        assert "end_sequence" in params


class TestExportEndpointNoAuth:
    """Tests for authentication requirements (FR44)."""

    def test_export_endpoint_no_auth_dependency(self) -> None:
        """Test that export endpoint has no auth dependency (FR44)."""
        from src.api.routes.observer import export_events

        sig = inspect.signature(export_events)
        params = sig.parameters

        # Should not have any auth-related parameters
        param_names = [p.lower() for p in params.keys()]
        assert "authorization" not in param_names
        assert "token" not in param_names
        assert "api_key" not in param_names

    def test_attestation_endpoint_no_auth_dependency(self) -> None:
        """Test that attestation endpoint has no auth dependency (FR44)."""
        from src.api.routes.observer import get_attestation_for_range

        sig = inspect.signature(get_attestation_for_range)
        params = sig.parameters

        param_names = [p.lower() for p in params.keys()]
        assert "authorization" not in param_names
        assert "token" not in param_names


class TestExportEndpointRateLimiter:
    """Tests for rate limiter dependency (FR48)."""

    def test_export_endpoint_has_rate_limiter(self) -> None:
        """Test that export endpoint has rate limiter dependency."""
        from src.api.routes.observer import export_events

        sig = inspect.signature(export_events)
        params = sig.parameters

        assert "rate_limiter" in params

    def test_attestation_endpoint_has_rate_limiter(self) -> None:
        """Test that attestation endpoint has rate limiter dependency."""
        from src.api.routes.observer import get_attestation_for_range

        sig = inspect.signature(get_attestation_for_range)
        params = sig.parameters

        assert "rate_limiter" in params


class TestExportFormatParameter:
    """Tests for export format parameter values."""

    def test_format_accepts_jsonl(self) -> None:
        """Test that format parameter accepts 'jsonl' value."""
        from src.api.models.observer import ExportFormat

        assert ExportFormat.JSONL.value == "jsonl"

    def test_format_accepts_csv(self) -> None:
        """Test that format parameter accepts 'csv' value."""
        from src.api.models.observer import ExportFormat

        assert ExportFormat.CSV.value == "csv"


class TestExportResponseHeaders:
    """Tests for export response characteristics."""

    def test_export_uses_streaming_response(self) -> None:
        """Test that export endpoint uses StreamingResponse for large exports."""
        from src.api.routes.observer import export_events

        # Check the return type annotation
        # The function should return a StreamingResponse
        source = inspect.getsource(export_events)
        assert "StreamingResponse" in source
