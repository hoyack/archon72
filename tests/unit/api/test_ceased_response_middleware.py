"""Unit tests for CeasedResponseMiddleware (Story 7.5, Task 1).

Tests middleware that injects CeasedStatusHeader into all responses
when system is in ceased state.

Constitutional Constraints:
- FR42: Read-only access indefinitely after cessation
- CT-11: Silent failure destroys legitimacy → Cessation status MUST be visible in ALL responses
- CT-13: Integrity outranks availability → Read access is GUARANTEED indefinitely
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse, Response

from src.api.middleware.ceased_response import CeasedResponseMiddleware
from src.domain.models.ceased_status_header import CeasedStatusHeader, CessationDetails
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub


@pytest.fixture
def freeze_checker() -> FreezeCheckerStub:
    """Create a freeze checker stub for testing."""
    return FreezeCheckerStub()


@pytest.fixture
def app(freeze_checker: FreezeCheckerStub) -> FastAPI:
    """Create test FastAPI app with CeasedResponseMiddleware."""
    app = FastAPI()

    # Add middleware with the freeze checker
    app.add_middleware(CeasedResponseMiddleware, freeze_checker=freeze_checker)

    @app.get("/test")
    async def test_endpoint() -> dict:
        return {"status": "ok"}

    @app.get("/test/empty")
    async def test_empty_endpoint() -> dict:
        return {}

    @app.post("/test/write")
    async def test_write_endpoint() -> dict:
        return {"written": True}

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client for the app."""
    return TestClient(app)


class TestCeasedResponseMiddlewareNotCeased:
    """Tests when system is NOT ceased (normal operation)."""

    def test_response_unchanged_when_not_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When not ceased, responses should not include cessation info."""
        # Given: System is not ceased
        freeze_checker.clear_frozen()

        # When: Request is made
        response = client.get("/test")

        # Then: Response is normal (no cessation_info)
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}
        assert "cessation_info" not in data

    def test_no_cessation_header_when_not_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When not ceased, response headers should not include X-System-Status."""
        # Given: System is not ceased
        freeze_checker.clear_frozen()

        # When: Request is made
        response = client.get("/test")

        # Then: No X-System-Status header
        assert response.status_code == 200
        assert "X-System-Status" not in response.headers


class TestCeasedResponseMiddlewareCeased:
    """Tests when system IS ceased (FR42)."""

    def test_json_response_includes_cessation_info(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When ceased, JSON responses should include cessation_info (AC5)."""
        # Given: System is ceased
        ceased_at = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=ceased_at,
            final_sequence=12345,
            reason="Unanimous vote for cessation",
        )

        # When: GET request is made
        response = client.get("/test")

        # Then: Response includes cessation_info
        assert response.status_code == 200
        data = response.json()
        assert "cessation_info" in data
        cessation_info = data["cessation_info"]
        assert cessation_info["system_status"] == "CEASED"
        assert cessation_info["final_sequence_number"] == 12345
        assert cessation_info["cessation_reason"] == "Unanimous vote for cessation"
        assert "ceased_at" in cessation_info

    def test_response_header_includes_ceased_status(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When ceased, response headers should include X-System-Status: CEASED (AC1)."""
        # Given: System is ceased
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=999,
            reason="Test",
        )

        # When: Request is made
        response = client.get("/test")

        # Then: X-System-Status header is CEASED
        assert response.status_code == 200
        assert response.headers.get("X-System-Status") == "CEASED"

    def test_response_header_includes_ceased_at(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When ceased, response headers should include X-Ceased-At timestamp (AC1)."""
        # Given: System is ceased at specific time
        ceased_at = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=ceased_at,
            final_sequence=999,
            reason="Test",
        )

        # When: Request is made
        response = client.get("/test")

        # Then: X-Ceased-At header contains ISO timestamp
        assert response.status_code == 200
        assert "X-Ceased-At" in response.headers
        assert "2024-06-15" in response.headers["X-Ceased-At"]

    def test_response_header_includes_final_sequence(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When ceased, response headers should include X-Final-Sequence (AC1)."""
        # Given: System is ceased with final sequence
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=12345,
            reason="Test",
        )

        # When: Request is made
        response = client.get("/test")

        # Then: X-Final-Sequence header contains the sequence number
        assert response.status_code == 200
        assert response.headers.get("X-Final-Sequence") == "12345"

    def test_original_response_data_preserved(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When ceased, original response data is preserved alongside cessation_info."""
        # Given: System is ceased
        freeze_checker.set_frozen_simple()

        # When: Request is made
        response = client.get("/test")

        # Then: Original data is still present
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "cessation_info" in data

    def test_empty_response_gets_cessation_info(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When ceased, even empty responses get cessation_info."""
        # Given: System is ceased
        freeze_checker.set_frozen_simple()

        # When: Request to empty endpoint is made
        response = client.get("/test/empty")

        # Then: Response includes cessation_info
        assert response.status_code == 200
        data = response.json()
        assert "cessation_info" in data

    def test_post_request_still_gets_cessation_info(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """When ceased, POST responses also include cessation_info.

        Note: The middleware adds cessation info to ALL responses.
        Blocking writes is handled by a separate dependency (Task 2).
        """
        # Given: System is ceased
        freeze_checker.set_frozen_simple()

        # When: POST request is made
        response = client.post("/test/write")

        # Then: Response includes cessation_info (middleware doesn't block)
        assert response.status_code == 200
        data = response.json()
        assert "cessation_info" in data


class TestCeasedResponseMiddlewareNonJsonResponses:
    """Tests for non-JSON response handling."""

    def test_non_json_response_headers_still_set(
        self, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Non-JSON responses should still get cessation headers."""
        # Given: App with non-JSON endpoint
        app = FastAPI()
        app.add_middleware(CeasedResponseMiddleware, freeze_checker=freeze_checker)

        @app.get("/plain")
        async def plain_text() -> Response:
            return Response(content="Hello", media_type="text/plain")

        freeze_checker.set_frozen_simple()

        # When: Request is made
        client = TestClient(app)
        response = client.get("/plain")

        # Then: Headers are set even for non-JSON
        assert response.status_code == 200
        assert response.headers.get("X-System-Status") == "CEASED"
        # Body is unchanged (not JSON, can't inject)
        assert response.text == "Hello"


class TestCeasedResponseMiddlewareReadOnly:
    """Tests ensuring read operations remain functional (CT-13, FR42)."""

    def test_read_operations_always_succeed(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Read operations must ALWAYS succeed after cessation (FR42, CT-13)."""
        # Given: System is ceased
        freeze_checker.set_frozen_simple()

        # When: Multiple read requests are made
        for _ in range(5):
            response = client.get("/test")
            # Then: Each request succeeds
            assert response.status_code == 200

    def test_reads_allowed_indefinitely_simulation(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Simulate 'years after cessation' - reads still work (AC4).

        We can't actually wait years, but we verify the middleware
        doesn't have any time-based blocking logic.
        """
        # Given: System was ceased 'long ago' (simulated via past timestamp)
        long_ago = datetime(2010, 1, 1, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=long_ago,
            final_sequence=12345,
            reason="Historical cessation",
        )

        # When: Request is made 'years later'
        response = client.get("/test")

        # Then: Read still works
        assert response.status_code == 200
        data = response.json()
        assert "cessation_info" in data
        # Cessation info shows the old date
        assert "2010-01-01" in data["cessation_info"]["ceased_at"]
