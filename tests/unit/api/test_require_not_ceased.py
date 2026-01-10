"""Unit tests for require_not_ceased dependency (Story 7.5, Task 2).

Tests the dependency that blocks write endpoints when system is ceased.

Constitutional Constraints:
- FR42: Read-only access indefinitely after cessation
- AC2: Write endpoints return 503 with Retry-After: never
- CT-11: Silent failure destroys legitimacy -> Clear error messages
"""

from datetime import datetime, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.cessation import get_freeze_checker, require_not_ceased
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub


@pytest.fixture
def freeze_checker() -> FreezeCheckerStub:
    """Create a freeze checker stub for testing."""
    return FreezeCheckerStub()


@pytest.fixture
def app(freeze_checker: FreezeCheckerStub) -> FastAPI:
    """Create test FastAPI app with write endpoints protected by require_not_ceased."""
    app = FastAPI()

    # Override the freeze_checker dependency
    app.dependency_overrides[get_freeze_checker] = lambda: freeze_checker

    @app.get("/read")
    async def read_endpoint() -> dict:
        """Read endpoint - no dependency (always allowed)."""
        return {"data": "readable"}

    @app.post("/write", dependencies=[Depends(require_not_ceased)])
    async def write_endpoint() -> dict:
        """Write endpoint - protected by require_not_ceased."""
        return {"written": True}

    @app.put("/update", dependencies=[Depends(require_not_ceased)])
    async def update_endpoint() -> dict:
        """Update endpoint - protected by require_not_ceased."""
        return {"updated": True}

    @app.delete("/delete", dependencies=[Depends(require_not_ceased)])
    async def delete_endpoint() -> dict:
        """Delete endpoint - protected by require_not_ceased."""
        return {"deleted": True}

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client for the app."""
    return TestClient(app)


class TestWriteEndpointsNotCeased:
    """Tests when system is NOT ceased (normal operation)."""

    def test_post_succeeds_when_not_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """POST succeeds when system is not ceased."""
        freeze_checker.clear_frozen()
        response = client.post("/write")
        assert response.status_code == 200
        assert response.json() == {"written": True}

    def test_put_succeeds_when_not_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """PUT succeeds when system is not ceased."""
        freeze_checker.clear_frozen()
        response = client.put("/update")
        assert response.status_code == 200
        assert response.json() == {"updated": True}

    def test_delete_succeeds_when_not_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """DELETE succeeds when system is not ceased."""
        freeze_checker.clear_frozen()
        response = client.delete("/delete")
        assert response.status_code == 200
        assert response.json() == {"deleted": True}

    def test_read_always_succeeds(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Read endpoints (without dependency) always succeed."""
        freeze_checker.clear_frozen()
        response = client.get("/read")
        assert response.status_code == 200
        assert response.json() == {"data": "readable"}


class TestWriteEndpointsCeased:
    """Tests when system IS ceased (FR42, AC2)."""

    def test_post_returns_503_when_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """POST returns 503 Service Unavailable when system is ceased (AC2)."""
        freeze_checker.set_frozen_simple()
        response = client.post("/write")
        assert response.status_code == 503

    def test_put_returns_503_when_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """PUT returns 503 when system is ceased."""
        freeze_checker.set_frozen_simple()
        response = client.put("/update")
        assert response.status_code == 503

    def test_delete_returns_503_when_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """DELETE returns 503 when system is ceased."""
        freeze_checker.set_frozen_simple()
        response = client.delete("/delete")
        assert response.status_code == 503

    def test_retry_after_never_header(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """503 response includes Retry-After: never header (AC2)."""
        freeze_checker.set_frozen_simple()
        response = client.post("/write")
        assert response.status_code == 503
        # "never" indicates permanent unavailability
        assert response.headers.get("Retry-After") == "never"

    def test_error_includes_cessation_reason(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """503 response body explains the cessation (CT-11)."""
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=12345,
            reason="Unanimous vote for cessation",
        )
        response = client.post("/write")
        assert response.status_code == 503
        data = response.json()
        assert "error" in data or "detail" in data
        # Check for "ceased" anywhere in the response
        data_str = str(data).lower()
        assert "ceased" in data_str

    def test_error_includes_final_sequence(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """503 response includes final sequence number for verification."""
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=12345,
            reason="Test cessation",
        )
        response = client.post("/write")
        assert response.status_code == 503
        # Final sequence in header
        assert response.headers.get("X-Final-Sequence") == "12345"

    def test_error_includes_ceased_at(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """503 response includes cessation timestamp."""
        ceased_at = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=ceased_at,
            final_sequence=12345,
            reason="Test cessation",
        )
        response = client.post("/write")
        assert response.status_code == 503
        # Ceased-at in header
        assert "X-Ceased-At" in response.headers
        assert "2024-06-15" in response.headers["X-Ceased-At"]

    def test_read_still_works_when_ceased(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Read endpoints still succeed when system is ceased (CT-13)."""
        freeze_checker.set_frozen_simple()
        response = client.get("/read")
        # Read is NOT protected by require_not_ceased
        assert response.status_code == 200
        assert response.json() == {"data": "readable"}


class TestWriteEndpointsPermanence:
    """Tests ensuring write rejection is permanent (AC2, AC4)."""

    def test_writes_never_succeed_after_cessation(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Once ceased, writes NEVER succeed - no timeout, no recovery."""
        # Given: System is ceased
        freeze_checker.set_frozen_simple()

        # When: Multiple write attempts over time
        for _ in range(10):
            response = client.post("/write")
            # Then: Each attempt fails with 503
            assert response.status_code == 503
            assert response.headers.get("Retry-After") == "never"

    def test_simulated_years_later_writes_still_blocked(
        self, client: TestClient, freeze_checker: FreezeCheckerStub
    ) -> None:
        """Simulate 'years after cessation' - writes still blocked (AC4).

        We can't actually wait years, but we verify the dependency
        doesn't have any time-based recovery logic.
        """
        # Given: System was ceased 'long ago' (simulated via past timestamp)
        long_ago = datetime(2010, 1, 1, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=long_ago,
            final_sequence=12345,
            reason="Historical cessation",
        )

        # When: Write attempt 'years later'
        response = client.post("/write")

        # Then: Still blocked
        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "never"
