"""Unit tests for realm health API routes (Story 8.7).

Tests the API endpoints for realm health dashboard.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.realm_health import router, get_realm_health_repo
from src.domain.models.realm import CANONICAL_REALM_IDS
from src.domain.models.realm_health import RealmHealth
from src.infrastructure.stubs.realm_health_repository_stub import (
    RealmHealthRepositoryStub,
)


@pytest.fixture
def realm_health_repo() -> RealmHealthRepositoryStub:
    """Create realm health repository stub."""
    return RealmHealthRepositoryStub()


@pytest.fixture
def app(realm_health_repo: RealmHealthRepositoryStub) -> FastAPI:
    """Create test FastAPI app with realm health router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # Override the dependency to use our test stub
    async def override_get_repo():
        return realm_health_repo

    app.dependency_overrides[get_realm_health_repo] = override_get_repo
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestRealmHealthDashboardEndpoint:
    """Tests for GET /api/v1/governance/dashboard/realm-health."""

    def test_get_realm_health_success(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test successful retrieval of realm health dashboard."""
        # Add some health data
        for realm_id in CANONICAL_REALM_IDS[:3]:
            health = RealmHealth.compute(
                realm_id=realm_id,
                cycle_id="2026-W04",
                petitions_received=10,
                petitions_fated=8,
            )
            realm_health_repo.add_health(health)

        response = client.get("/api/v1/governance/dashboard/realm-health?cycle_id=2026-W04")

        assert response.status_code == 200
        data = response.json()

        assert data["total_realms"] == 9
        assert len(data["realms"]) == 9

    def test_get_realm_health_with_cycle_parameter(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test retrieval with specific cycle_id parameter."""
        # Add health for specific cycle
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W03",
            petitions_received=50,
        )
        realm_health_repo.add_health(health)

        response = client.get(
            "/api/v1/governance/dashboard/realm-health?cycle_id=2026-W03"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["cycle_id"] == "2026-W03"

    def test_get_realm_health_includes_all_canonical_realms(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test that response includes all 9 canonical realms."""
        response = client.get("/api/v1/governance/dashboard/realm-health")

        assert response.status_code == 200
        data = response.json()

        realm_ids = {r["health"]["realm_id"] for r in data["realms"]}
        assert realm_ids == set(CANONICAL_REALM_IDS)

    def test_get_realm_health_includes_delta_when_previous_exists(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test that delta is included when previous cycle data exists."""
        realm_id = "realm_privacy_discretion_services"

        # Add previous cycle health
        previous = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W03",
            petitions_received=100,
        )
        realm_health_repo.add_health(previous)

        # Add current cycle health
        current = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W04",
            petitions_received=120,
        )
        realm_health_repo.add_health(current)

        response = client.get(
            "/api/v1/governance/dashboard/realm-health?cycle_id=2026-W04"
        )

        assert response.status_code == 200
        data = response.json()

        # Find the realm we configured
        realm_data = next(
            r for r in data["realms"] if r["health"]["realm_id"] == realm_id
        )

        assert realm_data["delta"] is not None
        assert realm_data["delta"]["petitions_received_delta"] == 20

    def test_get_realm_health_empty_data_handling(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test handling when no health data exists."""
        response = client.get("/api/v1/governance/dashboard/realm-health")

        assert response.status_code == 200
        data = response.json()

        # Should still return all realms with empty health
        assert data["total_realms"] == 9
        assert data["healthy_count"] == 9  # All empty = HEALTHY
        assert data["total_petitions_received"] == 0

    def test_get_realm_health_status_counts(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test that status counts are calculated correctly."""
        # Add health with different statuses
        # CRITICAL: >10 escalations
        critical_health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            escalations_pending=15,
        )
        realm_health_repo.add_health(critical_health)

        # ATTENTION: 1-5 escalations
        attention_health = RealmHealth.compute(
            realm_id="realm_relationship_facilitation",
            cycle_id="2026-W04",
            escalations_pending=3,
        )
        realm_health_repo.add_health(attention_health)

        response = client.get(
            "/api/v1/governance/dashboard/realm-health?cycle_id=2026-W04"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["critical_count"] == 1
        assert data["attention_count"] == 1
        assert data["healthy_count"] == 7  # Remaining 7 realms


class TestRealmHealthByIdEndpoint:
    """Tests for GET /api/v1/governance/dashboard/realm-health/{realm_id}."""

    def test_get_realm_health_by_id_success(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test successful retrieval of specific realm health."""
        realm_id = "realm_privacy_discretion_services"

        health = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W04",
            petitions_received=42,
            petitions_fated=38,
        )
        realm_health_repo.add_health(health)

        response = client.get(
            f"/api/v1/governance/dashboard/realm-health/{realm_id}?cycle_id=2026-W04"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["health"]["realm_id"] == realm_id
        assert data["health"]["petitions_received"] == 42
        assert data["health"]["petitions_fated"] == 38

    def test_get_realm_health_by_id_unknown_realm(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test 404 for unknown realm ID."""
        response = client.get(
            "/api/v1/governance/dashboard/realm-health/unknown_realm"
        )

        assert response.status_code == 404
        assert "Unknown realm" in response.json()["detail"]

    def test_get_realm_health_by_id_with_cycle_parameter(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test retrieval with specific cycle_id parameter."""
        realm_id = "realm_privacy_discretion_services"

        health = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W03",
            petitions_received=100,
        )
        realm_health_repo.add_health(health)

        response = client.get(
            f"/api/v1/governance/dashboard/realm-health/{realm_id}?cycle_id=2026-W03"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["health"]["cycle_id"] == "2026-W03"
        assert data["health"]["petitions_received"] == 100

    def test_get_realm_health_by_id_empty_returns_default_health(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test that empty realm returns default health record."""
        realm_id = "realm_privacy_discretion_services"

        response = client.get(
            f"/api/v1/governance/dashboard/realm-health/{realm_id}"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["health"]["realm_id"] == realm_id
        assert data["health"]["petitions_received"] == 0
        assert data["health"]["health_status"] == "HEALTHY"

    def test_get_realm_health_by_id_includes_delta(
        self,
        client: TestClient,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test that delta is included when previous cycle exists."""
        realm_id = "realm_privacy_discretion_services"

        # Add previous cycle
        previous = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W03",
            petitions_received=50,
        )
        realm_health_repo.add_health(previous)

        # Add current cycle
        current = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W04",
            petitions_received=75,
        )
        realm_health_repo.add_health(current)

        response = client.get(
            f"/api/v1/governance/dashboard/realm-health/{realm_id}?cycle_id=2026-W04"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["delta"] is not None
        assert data["delta"]["petitions_received_delta"] == 25
