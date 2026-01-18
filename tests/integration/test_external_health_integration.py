"""Integration tests for external health endpoint (Story 8.3, FR54).

Tests the full /health/external flow including HTTP layer.

Constitutional Constraints:
- FR54: System unavailability SHALL be independently detectable
- CT-11: Silent failure destroys legitimacy

Key Integration Scenarios:
1. HTTP request returns valid JSON
2. Response time is fast (<100ms with margin)
3. Endpoint accessible without authentication
4. Halt state properly reflected in response
5. Frozen state properly reflected in response
6. Status transitions work correctly
"""

import time
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.api.routes.external_health import router
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


class TestExternalHealthIntegration:
    """Integration tests for external health endpoint."""

    def test_http_request_returns_valid_json(self, client: TestClient) -> None:
        """Test HTTP request returns valid JSON response.

        AC1: Third-party services can ping and get valid response.
        """
        response = client.get("/health/external")

        # Should return 200 OK
        assert response.status_code == 200

        # Should be valid JSON
        data = response.json()
        assert isinstance(data, dict)

        # Should have required fields
        assert "status" in data
        assert "timestamp" in data

    def test_response_time_is_fast(self, client: TestClient) -> None:
        """Test response time is fast (<100ms with margin).

        External health must be fast for monitoring services.
        Target is <50ms, but we allow 100ms for test stability.
        """
        # Warm up
        client.get("/health/external")

        # Measure response time
        start = time.perf_counter()
        response = client.get("/health/external")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 100, f"Response took {elapsed_ms:.2f}ms, expected <100ms"

    def test_endpoint_accessible_without_authentication(
        self, client: TestClient
    ) -> None:
        """Test endpoint is accessible without any authentication.

        AC1: No authentication required.
        FR54: External parties can detect unavailability independently.
        """
        # Make request with no auth headers
        response = client.get("/health/external")

        # Should succeed
        assert response.status_code == 200

    def test_halt_state_reflected_in_response(
        self, client: TestClient, halt_checker: HaltCheckerStub
    ) -> None:
        """Test halt state is properly reflected in response.

        AC4: Halt state visible to external monitors.
        """
        # Initially healthy
        response = client.get("/health/external")
        assert response.json()["status"] == "up"

        # Trigger halt
        halt_checker.set_halted(True, reason="Integration test halt")

        # Should now return halted
        response = client.get("/health/external")
        assert response.json()["status"] == "halted"

    def test_frozen_state_reflected_in_response(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Test frozen state is properly reflected in response.

        AC5: Frozen state visible to external monitors.
        """
        # Initially healthy
        response = client.get("/health/external")
        assert response.json()["status"] == "up"

        # Trigger freeze
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Integration test cessation",
        )

        # Should now return frozen
        response = client.get("/health/external")
        assert response.json()["status"] == "frozen"

    def test_status_transitions_work(
        self,
        client: TestClient,
        halt_checker: HaltCheckerStub,
        freeze_checker: FreezeCheckerStub,
    ) -> None:
        """Test status correctly reflects state transitions.

        Verifies the endpoint tracks state changes correctly.
        """
        # Start healthy
        assert client.get("/health/external").json()["status"] == "up"

        # Transition to halted
        halt_checker.set_halted(True, reason="Test")
        assert client.get("/health/external").json()["status"] == "halted"

        # Clear halt
        halt_checker.set_halted(False)
        assert client.get("/health/external").json()["status"] == "up"

        # Transition to frozen
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Test",
        )
        assert client.get("/health/external").json()["status"] == "frozen"

        # Halt takes precedence over frozen
        halt_checker.set_halted(True, reason="Test")
        assert client.get("/health/external").json()["status"] == "halted"

    def test_content_type_is_json(self, client: TestClient) -> None:
        """Test Content-Type header is application/json."""
        response = client.get("/health/external")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_response_has_correct_structure(self, client: TestClient) -> None:
        """Test response structure matches expected format.

        External monitoring services expect consistent format.
        """
        response = client.get("/health/external")
        data = response.json()

        # Only status and timestamp
        assert set(data.keys()) == {"status", "timestamp"}

        # Status is a valid enum value
        assert data["status"] in ["up", "halted", "frozen"]

        # Timestamp is parseable
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_timestamp_is_recent(self, client: TestClient) -> None:
        """Test timestamp is recent (within a few seconds)."""
        before = datetime.now(timezone.utc)
        response = client.get("/health/external")
        after = datetime.now(timezone.utc)

        data = response.json()
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

        # Timestamp should be between before and after
        # Allow 1 second buffer for test stability
        assert timestamp >= before.replace(microsecond=0)
        assert timestamp <= after.replace(microsecond=999999)

    def test_multiple_concurrent_requests(self, client: TestClient) -> None:
        """Test endpoint handles multiple concurrent requests.

        External monitors may poll frequently.
        """
        import concurrent.futures

        def make_request():
            return client.get("/health/external")

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [f.result() for f in futures]

        # All should succeed
        for response in responses:
            assert response.status_code == 200
            assert response.json()["status"] == "up"


class TestExternalHealthAsyncIntegration:
    """Async integration tests for external health endpoint."""

    @pytest.mark.asyncio
    async def test_async_request_returns_valid_json(
        self, halt_checker: HaltCheckerStub, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Test async HTTP request returns valid JSON response."""
        # Initialize service
        init_external_health_service(
            halt_checker=halt_checker,
            freeze_checker=freeze_checker,
        )

        app = FastAPI()
        app.include_router(router)

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health/external")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "up"
            assert "timestamp" in data
        finally:
            reset_external_health_service()

    @pytest.mark.asyncio
    async def test_async_status_changes(
        self, halt_checker: HaltCheckerStub, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Test async status changes correctly."""
        # Initialize service
        init_external_health_service(
            halt_checker=halt_checker,
            freeze_checker=freeze_checker,
        )

        app = FastAPI()
        app.include_router(router)

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # Initially up
                response = await client.get("/health/external")
                assert response.json()["status"] == "up"

                # Trigger halt
                halt_checker.set_halted(True, reason="Test")
                response = await client.get("/health/external")
                assert response.json()["status"] == "halted"
        finally:
            reset_external_health_service()


class TestExternalHealthEdgeCases:
    """Edge case tests for external health endpoint."""

    def test_empty_halt_reason_still_returns_halted(
        self, client: TestClient, halt_checker: HaltCheckerStub
    ) -> None:
        """Test halt without reason still returns halted status."""
        halt_checker.set_halted(True, reason=None)

        response = client.get("/health/external")
        assert response.json()["status"] == "halted"

    def test_rapid_state_changes(
        self,
        client: TestClient,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test rapid state changes are handled correctly."""
        for _ in range(100):
            halt_checker.set_halted(True)
            response = client.get("/health/external")
            assert response.json()["status"] == "halted"

            halt_checker.set_halted(False)
            response = client.get("/health/external")
            assert response.json()["status"] == "up"

    def test_no_internal_state_exposed(self, client: TestClient) -> None:
        """Test no internal state details are exposed.

        Security: External monitors should only see status, not internals.
        """
        response = client.get("/health/external")
        data = response.json()

        # Should not contain internal fields
        assert "halt_reason" not in data
        assert "freeze_details" not in data
        assert "internal" not in data
        assert "error" not in data

        # Only expected fields
        assert set(data.keys()) == {"status", "timestamp"}

    def test_response_is_minimal(self, client: TestClient) -> None:
        """Test response size is minimal.

        Important for fast parsing by monitoring services.
        """
        response = client.get("/health/external")

        # Response should be small (less than 200 bytes)
        content_length = len(response.content)
        assert content_length < 200, f"Response too large: {content_length} bytes"
