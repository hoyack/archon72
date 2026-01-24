"""Unit tests for RealmHealth domain model (Story 8.7).

Tests the RealmHealth aggregate and RealmHealthDelta models.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.realm_health import (
    RealmHealth,
    RealmHealthDelta,
    RealmHealthStatus,
)


class TestRealmHealth:
    """Tests for RealmHealth domain model."""

    def test_compute_creates_valid_instance(self) -> None:
        """Test that compute() creates a valid RealmHealth instance."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=42,
            petitions_fated=38,
            referrals_pending=3,
            referrals_expired=1,
            escalations_pending=2,
            adoption_rate=0.35,
            average_referral_duration_seconds=86400,
        )

        assert health.realm_id == "realm_privacy_discretion_services"
        assert health.cycle_id == "2026-W04"
        assert health.petitions_received == 42
        assert health.petitions_fated == 38
        assert health.referrals_pending == 3
        assert health.referrals_expired == 1
        assert health.escalations_pending == 2
        assert health.adoption_rate == 0.35
        assert health.average_referral_duration_seconds == 86400
        assert health.health_id is not None
        assert health.computed_at is not None

    def test_compute_defaults_to_zeros(self) -> None:
        """Test that compute() defaults numeric fields to zero."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
        )

        assert health.petitions_received == 0
        assert health.petitions_fated == 0
        assert health.referrals_pending == 0
        assert health.referrals_expired == 0
        assert health.escalations_pending == 0
        assert health.adoption_rate is None
        assert health.average_referral_duration_seconds is None

    def test_is_frozen_dataclass(self) -> None:
        """Test that RealmHealth is immutable (frozen dataclass)."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
        )

        with pytest.raises(AttributeError):
            health.petitions_received = 100  # type: ignore

    def test_health_status_healthy_no_issues(self) -> None:
        """Test HEALTHY status when no issues detected."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=100,
            petitions_fated=95,
            referrals_pending=0,
            referrals_expired=0,
            escalations_pending=0,
            adoption_rate=0.30,
        )

        assert health.health_status() == RealmHealthStatus.HEALTHY
        assert health.is_healthy is True
        assert health.is_critical is False

    def test_health_status_attention_pending_escalations(self) -> None:
        """Test ATTENTION status with 1-5 pending escalations."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            escalations_pending=3,
        )

        assert health.health_status() == RealmHealthStatus.ATTENTION

    def test_health_status_attention_expiry_rate(self) -> None:
        """Test ATTENTION status with 10-20% expiry rate."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_fated=80,  # Used as proxy for completed referrals
            referrals_expired=12,  # 12/(80+12) = ~13% expiry rate
        )

        assert health.health_status() == RealmHealthStatus.ATTENTION

    def test_health_status_degraded_pending_escalations(self) -> None:
        """Test DEGRADED status with 6-10 pending escalations."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            escalations_pending=8,
        )

        assert health.health_status() == RealmHealthStatus.DEGRADED

    def test_health_status_degraded_expiry_rate(self) -> None:
        """Test DEGRADED status with >20% expiry rate."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_fated=70,
            referrals_expired=30,  # 30/(70+30) = 30% expiry rate
        )

        assert health.health_status() == RealmHealthStatus.DEGRADED

    def test_health_status_critical_pending_escalations(self) -> None:
        """Test CRITICAL status with >10 pending escalations."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            escalations_pending=15,
        )

        assert health.health_status() == RealmHealthStatus.CRITICAL
        assert health.is_critical is True

    def test_health_status_critical_adoption_rate(self) -> None:
        """Test CRITICAL status with adoption rate >70%."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            adoption_rate=0.75,
        )

        assert health.health_status() == RealmHealthStatus.CRITICAL

    def test_referral_expiry_rate_calculation(self) -> None:
        """Test referral expiry rate calculation."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_fated=80,
            referrals_pending=10,
            referrals_expired=10,
        )

        # total = 80 + 10 + 10 = 100, expired = 10, rate = 0.10
        assert health.referral_expiry_rate == pytest.approx(0.10)

    def test_referral_expiry_rate_none_when_no_activity(self) -> None:
        """Test expiry rate is None when no referral activity."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
        )

        assert health.referral_expiry_rate is None

    def test_has_activity_true_when_petitions_received(self) -> None:
        """Test has_activity is True when petitions received."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=1,
        )

        assert health.has_activity is True

    def test_has_activity_false_when_no_activity(self) -> None:
        """Test has_activity is False when no petition activity."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
        )

        assert health.has_activity is False

    def test_fate_completion_rate_calculation(self) -> None:
        """Test fate completion rate calculation."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=100,
            petitions_fated=90,
        )

        assert health.fate_completion_rate() == pytest.approx(0.90)

    def test_fate_completion_rate_none_when_no_petitions(self) -> None:
        """Test fate completion rate is None when no petitions."""
        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
        )

        assert health.fate_completion_rate() is None


class TestRealmHealthDelta:
    """Tests for RealmHealthDelta model."""

    def test_compute_delta_basic(self) -> None:
        """Test computing delta between two health records."""
        previous = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W03",
            petitions_received=100,
            petitions_fated=90,
            referrals_pending=5,
            escalations_pending=2,
            adoption_rate=0.30,
        )

        current = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=120,
            petitions_fated=110,
            referrals_pending=3,
            escalations_pending=4,
            adoption_rate=0.35,
        )

        delta = RealmHealthDelta.compute(current, previous)

        assert delta.realm_id == "realm_privacy_discretion_services"
        assert delta.current_cycle_id == "2026-W04"
        assert delta.previous_cycle_id == "2026-W03"
        assert delta.petitions_received_delta == 20
        assert delta.petitions_fated_delta == 20
        assert delta.referrals_pending_delta == -2
        assert delta.escalations_pending_delta == 2
        assert delta.adoption_rate_delta == pytest.approx(0.05)

    def test_status_changed_detection(self) -> None:
        """Test detection of status changes."""
        previous = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W03",
            escalations_pending=0,  # HEALTHY
        )

        current = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            escalations_pending=5,  # ATTENTION
        )

        delta = RealmHealthDelta.compute(current, previous)

        assert delta.status_changed is True
        assert delta.previous_status == RealmHealthStatus.HEALTHY
        assert delta.current_status == RealmHealthStatus.ATTENTION

    def test_is_improving_status_upgrade(self) -> None:
        """Test is_improving when status improves."""
        previous = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W03",
            escalations_pending=5,  # ATTENTION
        )

        current = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            escalations_pending=0,  # HEALTHY
        )

        delta = RealmHealthDelta.compute(current, previous)

        assert delta.is_improving is True
        assert delta.is_degrading is False

    def test_is_degrading_status_downgrade(self) -> None:
        """Test is_degrading when status degrades."""
        previous = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W03",
            escalations_pending=0,  # HEALTHY
        )

        current = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            escalations_pending=15,  # CRITICAL
        )

        delta = RealmHealthDelta.compute(current, previous)

        assert delta.is_degrading is True
        assert delta.is_improving is False

    def test_adoption_rate_delta_none_when_missing(self) -> None:
        """Test adoption rate delta is None when previous has no rate."""
        previous = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W03",
            adoption_rate=None,
        )

        current = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            adoption_rate=0.35,
        )

        delta = RealmHealthDelta.compute(current, previous)

        assert delta.adoption_rate_delta is None


class TestRealmHealthStatus:
    """Tests for RealmHealthStatus enum."""

    def test_all_statuses_defined(self) -> None:
        """Test all expected statuses are defined."""
        assert RealmHealthStatus.HEALTHY.value == "HEALTHY"
        assert RealmHealthStatus.ATTENTION.value == "ATTENTION"
        assert RealmHealthStatus.DEGRADED.value == "DEGRADED"
        assert RealmHealthStatus.CRITICAL.value == "CRITICAL"

    def test_status_count(self) -> None:
        """Test there are exactly 4 status levels."""
        assert len(RealmHealthStatus) == 4
