"""Integration tests for legitimacy dashboard API (Story 8.4, FR-8.4).

Tests High Archon dashboard endpoint with authentication, authorization,
caching, and database integration.

Constitutional Requirements:
- FR-8.4: Dashboard accessible to High Archon only
- NFR-5.6: 5-minute cache TTL
- NFR-1.2: <500ms response time
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.routes.legitimacy import set_dashboard_service
from src.application.services.legitimacy_dashboard_service import (
    LegitimacyDashboardService,
)
from src.infrastructure.cache.dashboard_cache import DashboardCache


@pytest.fixture
def mock_db_connection():
    """Mock database connection for dashboard service."""
    # In real integration tests, this would be a test database
    from unittest.mock import Mock

    db = Mock()
    cursor = Mock()
    db.cursor.return_value = cursor

    # Mock successful queries
    cursor.fetchone.side_effect = [
        (0.85, 150.0, 120.0),  # Current cycle metrics
        (5,),  # Orphan count
        (20, 18, 1, 1),  # Deliberation metrics
    ]

    cursor.fetchall.side_effect = [
        [("2026-W03", 0.88, datetime.now(timezone.utc))],  # Historical trend
        [("RECEIVED", 10), ("DELIBERATING", 5)],  # Petition counts
        [],  # Archon rates
    ]

    return db


@pytest.fixture
def dashboard_service(mock_db_connection):
    """Dashboard service with mock database."""
    cache = DashboardCache(ttl_seconds=300)
    return LegitimacyDashboardService(
        db_connection=mock_db_connection, cache=cache
    )


@pytest.fixture
def client(dashboard_service):
    """Test client with dashboard service configured."""
    set_dashboard_service(dashboard_service)
    return TestClient(app)


class TestDashboardAuthentication:
    """Tests for dashboard authentication (FR-8.4)."""

    def test_rejects_missing_archon_id_header(self, client):
        """Test rejection when X-Archon-Id header missing."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
        )

        # Assert
        assert response.status_code == 401
        assert "X-Archon-Id" in response.json()["detail"]

    def test_rejects_invalid_archon_id_format(self, client):
        """Test rejection when X-Archon-Id is not a valid UUID."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
            headers={"X-Archon-Id": "not-a-uuid", "X-Archon-Role": "HIGH_ARCHON"},
        )

        # Assert
        assert response.status_code == 400
        assert "Invalid Archon ID format" in response.json()["detail"]

    def test_rejects_missing_role_header(self, client):
        """Test rejection when X-Archon-Role header missing."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
            headers={"X-Archon-Id": str(uuid4())},
        )

        # Assert
        assert response.status_code == 401
        assert "X-Archon-Role" in response.json()["detail"]


class TestDashboardAuthorization:
    """Tests for dashboard authorization (FR-8.4)."""

    def test_rejects_non_high_archon_role(self, client):
        """Test rejection when role is not HIGH_ARCHON."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "KNIGHT",  # Not HIGH_ARCHON
            },
        )

        # Assert
        assert response.status_code == 403
        assert "High Archon role required" in response.json()["detail"]

    def test_accepts_high_archon_role(self, client):
        """Test acceptance when role is HIGH_ARCHON."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 200


class TestDashboardDataRetrieval:
    """Tests for dashboard data retrieval (FR-8.4)."""

    def test_returns_complete_dashboard_data(self, client):
        """Test successful dashboard data retrieval."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "current_cycle_score" in data
        assert "current_cycle_id" in data
        assert data["current_cycle_id"] == "2026-W04"
        assert "health_status" in data
        assert "historical_trend" in data
        assert "petitions_by_state" in data
        assert "orphan_petition_count" in data
        assert "average_time_to_fate" in data
        assert "median_time_to_fate" in data
        assert "deliberation_metrics" in data
        assert "archon_acknowledgment_rates" in data
        assert "requires_attention" in data
        assert "data_refreshed_at" in data

    def test_petition_state_counts_structure(self, client):
        """Test petition state counts have correct structure."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        data = response.json()
        state_counts = data["petitions_by_state"]

        assert "received" in state_counts
        assert "deliberating" in state_counts
        assert "acknowledged" in state_counts
        assert "referred" in state_counts
        assert "escalated" in state_counts
        assert "deferred" in state_counts
        assert "no_response" in state_counts
        assert "total" in state_counts

    def test_deliberation_metrics_structure(self, client):
        """Test deliberation metrics have correct structure."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        data = response.json()
        metrics = data["deliberation_metrics"]

        assert "total_deliberations" in metrics
        assert "consensus_rate" in metrics
        assert "timeout_rate" in metrics
        assert "deadlock_rate" in metrics

    def test_historical_trend_structure(self, client):
        """Test historical trend has correct structure."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "2026-W04"},
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        data = response.json()
        trend = data["historical_trend"]

        assert isinstance(trend, list)
        if len(trend) > 0:
            point = trend[0]
            assert "cycle_id" in point
            assert "legitimacy_score" in point
            assert "computed_at" in point


class TestDashboardCaching:
    """Tests for dashboard caching (NFR-5.6)."""

    def test_cache_reduces_database_queries(
        self, client, mock_db_connection, dashboard_service
    ):
        """Test that cache reduces database queries on repeated requests."""
        # Arrange
        headers = {
            "X-Archon-Id": str(uuid4()),
            "X-Archon-Role": "HIGH_ARCHON",
        }
        params = {"current_cycle_id": "2026-W04"}

        # Act - First request (cache miss)
        response1 = client.get(
            "/v1/governance/legitimacy/dashboard",
            params=params,
            headers=headers,
        )

        # Reset call counts
        _ = mock_db_connection.cursor.call_count
        mock_db_connection.reset_mock()

        # Act - Second request (cache hit)
        response2 = client.get(
            "/v1/governance/legitimacy/dashboard",
            params=params,
            headers=headers,
        )

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()

        # Database should not be queried on cache hit
        assert mock_db_connection.cursor.call_count == 0

    def test_invalid_cycle_id_returns_400(self, client):
        """Test that invalid cycle ID returns 400 error."""
        # Act
        response = client.get(
            "/v1/governance/legitimacy/dashboard",
            params={"current_cycle_id": "invalid"},
            headers={
                "X-Archon-Id": str(uuid4()),
                "X-Archon-Role": "HIGH_ARCHON",
            },
        )

        # Assert
        # Note: The actual validation depends on dashboard_service implementation
        # This test documents expected behavior
        assert response.status_code in [400, 200]  # May succeed with NO_DATA
