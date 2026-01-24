"""Unit tests for adoption ratio API routes (Story 8.6, PREVENT-7).

Tests adoption ratio dashboard and alert endpoints.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- FR-8.4: High Archon SHALL have access to legitimacy dashboard
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.adoption_ratio import (
    router,
    set_alerting_service,
    set_repository,
)
from src.domain.models.adoption_ratio import AdoptionRatioAlert, AdoptionRatioMetrics


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    return AsyncMock()


@pytest.fixture
def mock_alerting_service():
    """Create a mock alerting service."""
    return AsyncMock()


@pytest.fixture
def app(mock_repository, mock_alerting_service):
    """Create test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    # Inject mocks
    set_repository(mock_repository)
    set_alerting_service(mock_alerting_service)

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def high_archon_headers():
    """Standard High Archon authentication headers."""
    return {
        "X-Archon-Id": str(uuid4()),
        "X-Archon-Role": "HIGH_ARCHON",
    }


@pytest.fixture
def sample_metrics():
    """Create sample adoption ratio metrics."""
    return AdoptionRatioMetrics.compute(
        realm_id="governance",
        cycle_id="2026-W04",
        escalation_count=20,
        adoption_count=12,  # 60%
        adopting_kings=[uuid4(), uuid4()],
    )


@pytest.fixture
def sample_alert():
    """Create sample adoption ratio alert."""
    return AdoptionRatioAlert(
        alert_id=uuid4(),
        realm_id="governance",
        cycle_id="2026-W04",
        adoption_count=12,
        escalation_count=20,
        adoption_ratio=0.60,
        threshold=0.50,
        adopting_kings=(uuid4(),),
        severity="WARN",
        trend_delta=0.05,
        created_at=datetime.now(timezone.utc),
        resolved_at=None,
        status="ACTIVE",
    )


class TestAdoptionRatioDashboard:
    """Test dashboard endpoint."""

    def test_get_dashboard_requires_authentication(self, client, mock_repository):
        """Dashboard endpoint requires High Archon authentication."""
        # Given: No authentication headers
        mock_repository.get_all_realms_current_cycle.return_value = []

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios",
            params={"cycle_id": "2026-W04"},
        )

        # Then
        assert response.status_code == 401

    def test_get_dashboard_returns_empty_when_no_data(
        self, client, high_archon_headers, mock_repository, mock_alerting_service
    ):
        """Dashboard returns empty lists when no data."""
        # Given
        mock_repository.get_all_realms_current_cycle.return_value = []
        mock_alerting_service.get_active_alerts.return_value = []

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios",
            params={"cycle_id": "2026-W04"},
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["cycle_id"] == "2026-W04"
        assert data["total_realms_with_data"] == 0
        assert data["realms_exceeding_threshold"] == 0
        assert data["active_alerts_count"] == 0
        assert data["realm_metrics"] == []
        assert data["active_alerts"] == []

    def test_get_dashboard_returns_metrics_and_alerts(
        self,
        client,
        high_archon_headers,
        mock_repository,
        mock_alerting_service,
        sample_metrics,
        sample_alert,
    ):
        """Dashboard returns metrics and alerts for realms."""
        # Given
        mock_repository.get_all_realms_current_cycle.return_value = [sample_metrics]
        mock_alerting_service.get_active_alerts.return_value = [sample_alert]

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios",
            params={"cycle_id": "2026-W04"},
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["cycle_id"] == "2026-W04"
        assert data["total_realms_with_data"] == 1
        assert data["realms_exceeding_threshold"] == 1  # 60% > 50%
        assert data["active_alerts_count"] == 1
        assert len(data["realm_metrics"]) == 1
        assert data["realm_metrics"][0]["realm_id"] == "governance"
        assert data["realm_metrics"][0]["metrics"]["adoption_ratio"] == 0.6
        assert len(data["active_alerts"]) == 1

    def test_get_dashboard_counts_critical_realms(
        self, client, high_archon_headers, mock_repository, mock_alerting_service
    ):
        """Dashboard correctly counts critical realms (>70%)."""
        # Given
        critical_metrics = AdoptionRatioMetrics.compute(
            realm_id="council",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=16,  # 80% - critical
            adopting_kings=[uuid4()],
        )
        mock_repository.get_all_realms_current_cycle.return_value = [critical_metrics]
        mock_alerting_service.get_active_alerts.return_value = []

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios",
            params={"cycle_id": "2026-W04"},
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["realms_critical"] == 1


class TestAdoptionRatioRealmStatus:
    """Test realm-specific endpoint."""

    def test_get_realm_status_requires_authentication(self, client, mock_repository):
        """Realm status endpoint requires High Archon authentication."""
        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios/realm/governance",
            params={"cycle_id": "2026-W04"},
        )

        # Then
        assert response.status_code == 401

    def test_get_realm_status_returns_metrics_and_alert(
        self, client, high_archon_headers, mock_repository, sample_metrics, sample_alert
    ):
        """Realm status returns metrics and active alert."""
        # Given
        mock_repository.get_metrics_by_realm_cycle.return_value = sample_metrics
        mock_repository.get_active_alert.return_value = sample_alert

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios/realm/governance",
            params={"cycle_id": "2026-W04"},
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["realm_id"] == "governance"
        assert data["metrics"] is not None
        assert data["metrics"]["adoption_ratio"] == 0.6
        assert data["active_alert"] is not None
        assert data["active_alert"]["severity"] == "WARN"

    def test_get_realm_status_returns_null_for_no_data(
        self, client, high_archon_headers, mock_repository
    ):
        """Realm status returns null metrics when no data."""
        # Given
        mock_repository.get_metrics_by_realm_cycle.return_value = None
        mock_repository.get_active_alert.return_value = None

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios/realm/new-realm",
            params={"cycle_id": "2026-W04"},
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["realm_id"] == "new-realm"
        assert data["metrics"] is None
        assert data["active_alert"] is None


class TestAdoptionRatioAlerts:
    """Test alerts endpoints."""

    def test_get_active_alerts_requires_authentication(
        self, client, mock_alerting_service
    ):
        """Active alerts endpoint requires High Archon authentication."""
        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios/alerts",
        )

        # Then
        assert response.status_code == 401

    def test_get_active_alerts_returns_list(
        self, client, high_archon_headers, mock_alerting_service, sample_alert
    ):
        """Active alerts endpoint returns list of alerts."""
        # Given
        mock_alerting_service.get_active_alerts.return_value = [sample_alert]

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios/alerts",
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["realm_id"] == "governance"
        assert data[0]["severity"] == "WARN"
        assert data[0]["status"] == "ACTIVE"

    def test_get_specific_alert_returns_alert(
        self, client, high_archon_headers, mock_repository, sample_alert
    ):
        """Get specific alert by ID."""
        # Given
        mock_repository.get_alert_by_id.return_value = sample_alert

        # When
        response = client.get(
            f"/v1/governance/dashboard/adoption-ratios/alert/{sample_alert.alert_id}",
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["alert_id"] == str(sample_alert.alert_id)
        assert data["realm_id"] == "governance"

    def test_get_specific_alert_not_found(
        self, client, high_archon_headers, mock_repository
    ):
        """Get specific alert returns 404 when not found."""
        # Given
        mock_repository.get_alert_by_id.return_value = None
        alert_id = uuid4()

        # When
        response = client.get(
            f"/v1/governance/dashboard/adoption-ratios/alert/{alert_id}",
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 404

    def test_get_specific_alert_invalid_uuid(self, client, high_archon_headers):
        """Get specific alert returns 400 for invalid UUID."""
        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios/alert/not-a-uuid",
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 400


class TestAdoptionRatioResponseModels:
    """Test response model structure."""

    def test_metrics_response_includes_health_status(
        self, client, high_archon_headers, mock_repository, mock_alerting_service
    ):
        """Metrics response includes health_status field."""
        # Given
        warn_metrics = AdoptionRatioMetrics.compute(
            realm_id="governance",
            cycle_id="2026-W04",
            escalation_count=20,
            adoption_count=11,  # 55% - WARN
            adopting_kings=[uuid4()],
        )
        mock_repository.get_all_realms_current_cycle.return_value = [warn_metrics]
        mock_alerting_service.get_active_alerts.return_value = []

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios",
            params={"cycle_id": "2026-W04"},
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["realm_metrics"][0]["metrics"]["health_status"] == "WARN"

    def test_alert_response_includes_all_fields(
        self, client, high_archon_headers, mock_alerting_service, sample_alert
    ):
        """Alert response includes all required fields."""
        # Given
        mock_alerting_service.get_active_alerts.return_value = [sample_alert]

        # When
        response = client.get(
            "/v1/governance/dashboard/adoption-ratios/alerts",
            headers=high_archon_headers,
        )

        # Then
        assert response.status_code == 200
        data = response.json()[0]

        # Verify all fields present
        assert "alert_id" in data
        assert "realm_id" in data
        assert "cycle_id" in data
        assert "adoption_count" in data
        assert "escalation_count" in data
        assert "adoption_ratio" in data
        assert "threshold" in data
        assert "severity" in data
        assert "trend_delta" in data
        assert "adopting_kings" in data
        assert "created_at" in data
        assert "resolved_at" in data
        assert "status" in data
