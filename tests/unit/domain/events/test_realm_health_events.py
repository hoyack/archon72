"""Unit tests for realm health event payloads (Story 8.7).

Tests the event payload models for realm health computation events.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.realm_health import (
    AllRealmsHealthComputedEventPayload,
    RealmHealthComputedEventPayload,
    RealmHealthStatusChangedEventPayload,
)


class TestRealmHealthComputedEventPayload:
    """Tests for RealmHealthComputedEventPayload."""

    def test_create_event_payload(self) -> None:
        """Test creating a RealmHealthComputed event payload."""
        health_id = uuid4()
        computed_at = datetime.now(timezone.utc)

        event = RealmHealthComputedEventPayload.create(
            health_id=health_id,
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=42,
            petitions_fated=38,
            referrals_pending=3,
            escalations_pending=2,
            health_status="HEALTHY",
            computed_at=computed_at,
        )

        assert event.event_id is not None
        assert event.health_id == health_id
        assert event.realm_id == "realm_privacy_discretion_services"
        assert event.cycle_id == "2026-W04"
        assert event.petitions_received == 42
        assert event.petitions_fated == 38
        assert event.referrals_pending == 3
        assert event.escalations_pending == 2
        assert event.health_status == "HEALTHY"
        assert event.computed_at == computed_at

    def test_to_dict_serialization(self) -> None:
        """Test to_dict() produces valid JSON-serializable dict."""
        health_id = uuid4()
        computed_at = datetime.now(timezone.utc)

        event = RealmHealthComputedEventPayload.create(
            health_id=health_id,
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=42,
            petitions_fated=38,
            referrals_pending=3,
            escalations_pending=2,
            health_status="HEALTHY",
            computed_at=computed_at,
        )

        data = event.to_dict()

        assert data["schema_version"] == "1.0.0"
        assert data["event_id"] == str(event.event_id)
        assert data["health_id"] == str(health_id)
        assert data["realm_id"] == "realm_privacy_discretion_services"
        assert data["cycle_id"] == "2026-W04"
        assert data["petitions_received"] == 42
        assert data["petitions_fated"] == 38
        assert data["referrals_pending"] == 3
        assert data["escalations_pending"] == 2
        assert data["health_status"] == "HEALTHY"
        assert data["computed_at"] == computed_at.isoformat()

    def test_is_frozen_dataclass(self) -> None:
        """Test that event payload is immutable."""
        event = RealmHealthComputedEventPayload.create(
            health_id=uuid4(),
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=42,
            petitions_fated=38,
            referrals_pending=3,
            escalations_pending=2,
            health_status="HEALTHY",
            computed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            event.health_status = "CRITICAL"  # type: ignore


class TestRealmHealthStatusChangedEventPayload:
    """Tests for RealmHealthStatusChangedEventPayload."""

    def test_create_event_payload(self) -> None:
        """Test creating a RealmHealthStatusChanged event payload."""
        changed_at = datetime.now(timezone.utc)

        event = RealmHealthStatusChangedEventPayload.create(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            previous_status="HEALTHY",
            new_status="ATTENTION",
            changed_at=changed_at,
        )

        assert event.event_id is not None
        assert event.realm_id == "realm_privacy_discretion_services"
        assert event.cycle_id == "2026-W04"
        assert event.previous_status == "HEALTHY"
        assert event.new_status == "ATTENTION"
        assert event.changed_at == changed_at

    def test_to_dict_serialization(self) -> None:
        """Test to_dict() produces valid JSON-serializable dict."""
        changed_at = datetime.now(timezone.utc)

        event = RealmHealthStatusChangedEventPayload.create(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            previous_status="HEALTHY",
            new_status="CRITICAL",
            changed_at=changed_at,
        )

        data = event.to_dict()

        assert data["schema_version"] == "1.0.0"
        assert data["event_id"] == str(event.event_id)
        assert data["realm_id"] == "realm_privacy_discretion_services"
        assert data["cycle_id"] == "2026-W04"
        assert data["previous_status"] == "HEALTHY"
        assert data["new_status"] == "CRITICAL"
        assert data["changed_at"] == changed_at.isoformat()


class TestAllRealmsHealthComputedEventPayload:
    """Tests for AllRealmsHealthComputedEventPayload."""

    def test_create_event_payload(self) -> None:
        """Test creating an AllRealmsHealthComputed event payload."""
        computed_at = datetime.now(timezone.utc)

        event = AllRealmsHealthComputedEventPayload.create(
            cycle_id="2026-W04",
            realm_count=9,
            healthy_count=6,
            attention_count=2,
            degraded_count=1,
            critical_count=0,
            computed_at=computed_at,
        )

        assert event.event_id is not None
        assert event.cycle_id == "2026-W04"
        assert event.realm_count == 9
        assert event.healthy_count == 6
        assert event.attention_count == 2
        assert event.degraded_count == 1
        assert event.critical_count == 0
        assert event.computed_at == computed_at

    def test_to_dict_serialization(self) -> None:
        """Test to_dict() produces valid JSON-serializable dict."""
        computed_at = datetime.now(timezone.utc)

        event = AllRealmsHealthComputedEventPayload.create(
            cycle_id="2026-W04",
            realm_count=9,
            healthy_count=6,
            attention_count=2,
            degraded_count=1,
            critical_count=0,
            computed_at=computed_at,
        )

        data = event.to_dict()

        assert data["schema_version"] == "1.0.0"
        assert data["event_id"] == str(event.event_id)
        assert data["cycle_id"] == "2026-W04"
        assert data["realm_count"] == 9
        assert data["healthy_count"] == 6
        assert data["attention_count"] == 2
        assert data["degraded_count"] == 1
        assert data["critical_count"] == 0
        assert data["computed_at"] == computed_at.isoformat()

    def test_counts_sum_to_realm_count(self) -> None:
        """Test that status counts should sum to realm_count."""
        computed_at = datetime.now(timezone.utc)

        event = AllRealmsHealthComputedEventPayload.create(
            cycle_id="2026-W04",
            realm_count=9,
            healthy_count=6,
            attention_count=2,
            degraded_count=1,
            critical_count=0,
            computed_at=computed_at,
        )

        total = (
            event.healthy_count
            + event.attention_count
            + event.degraded_count
            + event.critical_count
        )
        assert total == event.realm_count
