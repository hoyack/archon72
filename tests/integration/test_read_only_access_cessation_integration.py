"""Integration tests for read-only access after cessation (Story 7.5).

Tests the complete flow of read-only access after system cessation,
including middleware, dependencies, and API routes.

Constitutional Constraints:
- FR42: Read-only access indefinitely after cessation
- CT-11: Silent failure destroys legitimacy -> status always visible
- CT-13: Reads allowed indefinitely after cessation (GUARANTEED)

Acceptance Criteria:
- AC1: All read endpoints remain fully functional after cessation
- AC2: Write endpoints return 503 Service Unavailable with Retry-After: never
- AC3: Health endpoint indicates reads available, writes blocked
- AC4: Read access works indefinitely (years/decades later)
- AC5: CeasedStatusHeader included in all read responses
- AC6: SSE streams continue functioning with cessation status
- AC7: All write endpoints consistently return 503
- AC8: No mechanism exists to re-enable writes after cessation
"""

from datetime import datetime, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.cessation import get_freeze_checker, require_not_ceased
from src.api.middleware.ceased_response import CeasedResponseMiddleware
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub


@pytest.fixture
def freeze_checker() -> FreezeCheckerStub:
    """Create a freeze checker stub for testing."""
    return FreezeCheckerStub()


@pytest.fixture
def app(freeze_checker: FreezeCheckerStub) -> FastAPI:
    """Create test FastAPI app with full cessation handling."""
    app = FastAPI()

    # Add CeasedResponseMiddleware
    app.add_middleware(CeasedResponseMiddleware, freeze_checker=freeze_checker)

    # Override the freeze_checker dependency
    app.dependency_overrides[get_freeze_checker] = lambda: freeze_checker

    # Read endpoints (no require_not_ceased)
    @app.get("/v1/observer/events")
    async def get_events() -> dict:
        return {"events": [], "pagination": {"total": 0}}

    @app.get("/v1/observer/events/{event_id}")
    async def get_event(event_id: str) -> dict:
        return {"event_id": event_id, "sequence": 1}

    @app.get("/v1/observer/verification-spec")
    async def get_verification_spec() -> dict:
        return {"algorithm": "SHA-256", "version": 1}

    @app.get("/v1/observer/health")
    async def get_health() -> dict:
        return {"status": "healthy", "reads_available": True}

    # Write endpoints (protected by require_not_ceased)
    @app.post("/v1/events", dependencies=[Depends(require_not_ceased)])
    async def create_event() -> dict:
        return {"created": True}

    @app.post("/v1/observer/webhooks", dependencies=[Depends(require_not_ceased)])
    async def register_webhook() -> dict:
        return {"subscription_id": "test"}

    @app.delete(
        "/v1/observer/webhooks/{id}", dependencies=[Depends(require_not_ceased)]
    )
    async def delete_webhook(id: str) -> dict:
        return {"deleted": True}

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client for the app."""
    return TestClient(app)


class TestAC1ReadEndpointsRemainFunctional:
    """AC1: All read endpoints remain fully functional after cessation."""

    def test_get_events_works_after_cessation(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """GET /events returns 200 after cessation."""
        freeze_checker.set_frozen_simple()
        response = client.get("/v1/observer/events")
        assert response.status_code == 200

    def test_get_single_event_works_after_cessation(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """GET /events/{id} returns 200 after cessation."""
        freeze_checker.set_frozen_simple()
        response = client.get("/v1/observer/events/test-event-id")
        assert response.status_code == 200

    def test_verification_spec_works_after_cessation(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """GET /verification-spec returns 200 after cessation."""
        freeze_checker.set_frozen_simple()
        response = client.get("/v1/observer/verification-spec")
        assert response.status_code == 200

    def test_health_endpoint_works_after_cessation(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """GET /health returns 200 after cessation."""
        freeze_checker.set_frozen_simple()
        response = client.get("/v1/observer/health")
        assert response.status_code == 200


class TestAC2WriteEndpointsReturn503:
    """AC2: Write endpoints return 503 with Retry-After: never."""

    def test_create_event_returns_503(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """POST /events returns 503 after cessation."""
        freeze_checker.set_frozen_simple()
        response = client.post("/v1/events")
        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "never"

    def test_register_webhook_returns_503(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """POST /webhooks returns 503 after cessation."""
        freeze_checker.set_frozen_simple()
        response = client.post("/v1/observer/webhooks")
        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "never"

    def test_delete_webhook_returns_503(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """DELETE /webhooks/{id} returns 503 after cessation."""
        freeze_checker.set_frozen_simple()
        response = client.delete("/v1/observer/webhooks/test-id")
        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "never"


class TestAC4IndefiniteReadAccess:
    """AC4: Read access works indefinitely (years/decades later simulation)."""

    def test_reads_work_years_later_simulation(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Simulate years after cessation - reads still work."""
        # Cessation happened 'years ago'
        long_ago = datetime(2010, 1, 1, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=long_ago,
            final_sequence=12345,
            reason="Historical cessation",
        )

        # Multiple reads should all succeed
        for _ in range(10):
            response = client.get("/v1/observer/events")
            assert response.status_code == 200


class TestAC5CeasedStatusHeaderIncluded:
    """AC5: CeasedStatusHeader included in all read responses."""

    def test_cessation_info_in_json_responses(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """JSON responses include cessation_info after cessation."""
        ceased_at = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=ceased_at,
            final_sequence=12345,
            reason="Unanimous vote",
        )

        response = client.get("/v1/observer/events")
        assert response.status_code == 200
        data = response.json()
        assert "cessation_info" in data
        assert data["cessation_info"]["system_status"] == "CEASED"
        assert data["cessation_info"]["final_sequence_number"] == 12345

    def test_cessation_headers_present(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Response headers include X-System-Status, X-Ceased-At, X-Final-Sequence."""
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=999,
            reason="Test",
        )

        response = client.get("/v1/observer/events")
        assert response.headers.get("X-System-Status") == "CEASED"
        assert "X-Ceased-At" in response.headers
        assert response.headers.get("X-Final-Sequence") == "999"


class TestAC7ConsistentWriteRejection:
    """AC7: All write endpoints consistently return 503."""

    def test_all_write_methods_blocked(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """POST, PUT, DELETE all return 503 when protected."""
        freeze_checker.set_frozen_simple()

        # All protected write endpoints return 503
        assert client.post("/v1/events").status_code == 503
        assert client.post("/v1/observer/webhooks").status_code == 503
        assert client.delete("/v1/observer/webhooks/test").status_code == 503


class TestAC8NoWriteReenablement:
    """AC8: No mechanism exists to re-enable writes after cessation."""

    def test_writes_never_succeed_regardless_of_attempts(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Multiple write attempts all fail - no retry logic succeeds."""
        freeze_checker.set_frozen_simple()

        # Try many times - should always fail
        for _ in range(20):
            response = client.post("/v1/events")
            assert response.status_code == 503
            assert response.headers.get("Retry-After") == "never"

    def test_freeze_checker_state_permanent(
        self, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Once frozen, FreezeChecker remains frozen (per NFR40)."""
        freeze_checker.set_frozen_simple()

        # State should remain frozen
        for _ in range(10):
            # Note: In production, is_frozen() would be async
            # but for testing synchronously we can verify the internal state
            assert freeze_checker._frozen is True


class TestIntegrationScenarios:
    """Complex integration scenarios testing end-to-end behavior."""

    def test_pre_cessation_normal_operation(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Before cessation, both reads and writes work normally."""
        freeze_checker.clear_frozen()

        # Reads work
        assert client.get("/v1/observer/events").status_code == 200

        # Writes work (not blocked)
        assert client.post("/v1/events").status_code == 200

    def test_post_cessation_reads_only(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """After cessation, only reads work."""
        freeze_checker.set_frozen_simple()

        # Reads work
        response = client.get("/v1/observer/events")
        assert response.status_code == 200
        assert "cessation_info" in response.json()

        # Writes blocked
        response = client.post("/v1/events")
        assert response.status_code == 503

    def test_cessation_transition_behavior(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Test the transition from operational to ceased state."""
        # Phase 1: Operational
        freeze_checker.clear_frozen()
        assert client.post("/v1/events").status_code == 200
        read_response = client.get("/v1/observer/events")
        assert read_response.status_code == 200
        assert "cessation_info" not in read_response.json()

        # Phase 2: Cessation occurs
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=42,
            reason="Test cessation",
        )

        # Phase 3: After cessation
        # Writes blocked
        write_response = client.post("/v1/events")
        assert write_response.status_code == 503
        assert write_response.headers.get("Retry-After") == "never"

        # Reads still work with cessation info
        read_response = client.get("/v1/observer/events")
        assert read_response.status_code == 200
        assert "cessation_info" in read_response.json()
        assert read_response.json()["cessation_info"]["final_sequence_number"] == 42
