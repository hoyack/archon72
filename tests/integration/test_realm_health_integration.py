"""Integration tests for realm health (Story 8.7).

Tests end-to-end flows for realm health computation and dashboard.
"""

from uuid import uuid4

import pytest

from src.application.services.realm_health_compute_service import (
    RealmHealthComputeService,
)
from src.domain.models.adoption_ratio import AdoptionRatioMetrics
from src.domain.models.realm import CANONICAL_REALM_IDS
from src.domain.models.realm_health import (
    RealmHealth,
    RealmHealthDelta,
    RealmHealthStatus,
)
from src.infrastructure.stubs.adoption_ratio_repository_stub import (
    AdoptionRatioRepositoryStub,
)
from src.infrastructure.stubs.realm_health_repository_stub import (
    RealmHealthRepositoryStub,
)


class MockEventEmitter:
    """Mock event emitter for integration testing."""

    def __init__(self) -> None:
        self.health_computed_events: list = []
        self.status_changed_events: list = []
        self.all_realms_computed_events: list = []

    async def emit_health_computed(self, event) -> None:
        self.health_computed_events.append(event)

    async def emit_status_changed(self, event) -> None:
        self.status_changed_events.append(event)

    async def emit_all_realms_computed(self, event) -> None:
        self.all_realms_computed_events.append(event)


class TestRealmHealthEndToEndFlow:
    """Integration tests for complete realm health flow."""

    @pytest.mark.asyncio
    async def test_full_cycle_computation_flow(self) -> None:
        """Test complete flow: petition activity -> health computation -> persistence."""
        realm_health_repo = RealmHealthRepositoryStub()
        adoption_ratio_repo = AdoptionRatioRepositoryStub()
        event_emitter = MockEventEmitter()

        service = RealmHealthComputeService(
            realm_health_repo=realm_health_repo,
            adoption_ratio_repo=adoption_ratio_repo,
            event_emitter=event_emitter,
        )

        # Simulate petition activity across realms
        petition_counts = {
            "realm_privacy_discretion_services": {"received": 100, "fated": 90},
            "realm_relationship_facilitation": {"received": 80, "fated": 75},
            "realm_knowledge_skill_development": {"received": 60, "fated": 55},
        }

        referral_counts = {
            "realm_privacy_discretion_services": {"pending": 5, "expired": 2},
            "realm_relationship_facilitation": {"pending": 3, "expired": 0},
        }

        escalation_counts = {
            "realm_privacy_discretion_services": {"pending": 3},
        }

        # Compute health for all realms
        results = await service.compute_for_cycle(
            cycle_id="2026-W04",
            petition_counts=petition_counts,
            referral_counts=referral_counts,
            escalation_counts=escalation_counts,
        )

        # Verify all realms processed
        assert len(results) == 9

        # Verify specific realm health
        privacy_realm = next(
            h for h in results if h.realm_id == "realm_privacy_discretion_services"
        )
        assert privacy_realm.petitions_received == 100
        assert privacy_realm.petitions_fated == 90
        assert privacy_realm.referrals_pending == 5
        assert privacy_realm.referrals_expired == 2
        assert privacy_realm.escalations_pending == 3
        assert privacy_realm.health_status() == RealmHealthStatus.ATTENTION

        # Verify events emitted
        assert len(event_emitter.health_computed_events) == 9
        assert len(event_emitter.all_realms_computed_events) == 1

        # Verify persistence
        persisted = await realm_health_repo.get_all_for_cycle("2026-W04")
        assert len(persisted) == 9

    @pytest.mark.asyncio
    async def test_multi_cycle_tracking_and_delta(self) -> None:
        """Test tracking health across multiple cycles with delta computation."""
        realm_health_repo = RealmHealthRepositoryStub()
        adoption_ratio_repo = AdoptionRatioRepositoryStub()
        event_emitter = MockEventEmitter()

        service = RealmHealthComputeService(
            realm_health_repo=realm_health_repo,
            adoption_ratio_repo=adoption_ratio_repo,
            event_emitter=event_emitter,
        )

        realm_id = "realm_privacy_discretion_services"

        # Week 3: Initial state
        await service.compute_for_realm(
            realm_id=realm_id,
            cycle_id="2026-W03",
            petitions_received=100,
            escalations_pending=0,  # HEALTHY
        )

        # Week 4: Degradation
        health_w4 = await service.compute_for_realm(
            realm_id=realm_id,
            cycle_id="2026-W04",
            petitions_received=120,
            escalations_pending=8,  # DEGRADED
        )

        # Verify status change event emitted
        assert len(event_emitter.status_changed_events) == 1
        status_event = event_emitter.status_changed_events[0]
        assert status_event.previous_status == "HEALTHY"
        assert status_event.new_status == "DEGRADED"

        # Verify delta computation
        previous = await realm_health_repo.get_previous_cycle(realm_id, "2026-W04")
        assert previous is not None

        delta = RealmHealthDelta.compute(health_w4, previous)
        assert delta.petitions_received_delta == 20
        assert delta.escalations_pending_delta == 8
        assert delta.status_changed is True
        assert delta.is_degrading is True

    @pytest.mark.asyncio
    async def test_adoption_rate_integration(self) -> None:
        """Test integration with adoption ratio metrics from Story 8.6."""
        realm_health_repo = RealmHealthRepositoryStub()
        adoption_ratio_repo = AdoptionRatioRepositoryStub()
        event_emitter = MockEventEmitter()

        service = RealmHealthComputeService(
            realm_health_repo=realm_health_repo,
            adoption_ratio_repo=adoption_ratio_repo,
            event_emitter=event_emitter,
        )

        realm_id = "realm_privacy_discretion_services"
        cycle_id = "2026-W04"

        # Add adoption ratio data (from Story 8.6)
        adoption_metrics = AdoptionRatioMetrics.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=20,
            adoption_count=15,  # 75% adoption rate -> CRITICAL
            adopting_kings=[uuid4()],
        )
        adoption_ratio_repo.add_metrics(adoption_metrics)

        # Compute health
        health = await service.compute_for_realm(
            realm_id=realm_id,
            cycle_id=cycle_id,
        )

        # Verify adoption rate integrated
        assert health.adoption_rate == pytest.approx(0.75)
        assert health.health_status() == RealmHealthStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_dashboard_data_aggregation(self) -> None:
        """Test dashboard correctly aggregates data across all realms."""
        realm_health_repo = RealmHealthRepositoryStub()
        adoption_ratio_repo = AdoptionRatioRepositoryStub()
        event_emitter = MockEventEmitter()

        service = RealmHealthComputeService(
            realm_health_repo=realm_health_repo,
            adoption_ratio_repo=adoption_ratio_repo,
            event_emitter=event_emitter,
        )

        # Create varied health states
        escalation_counts = {
            "realm_privacy_discretion_services": {"pending": 15},  # CRITICAL
            "realm_relationship_facilitation": {"pending": 8},  # DEGRADED
            "realm_knowledge_skill_development": {"pending": 3},  # ATTENTION
            # Remaining 6 realms will be HEALTHY
        }

        results = await service.compute_for_cycle(
            cycle_id="2026-W04",
            escalation_counts=escalation_counts,
        )

        # Verify status distribution
        status_counts = {
            RealmHealthStatus.HEALTHY: 0,
            RealmHealthStatus.ATTENTION: 0,
            RealmHealthStatus.DEGRADED: 0,
            RealmHealthStatus.CRITICAL: 0,
        }
        for health in results:
            status_counts[health.health_status()] += 1

        assert status_counts[RealmHealthStatus.CRITICAL] == 1
        assert status_counts[RealmHealthStatus.DEGRADED] == 1
        assert status_counts[RealmHealthStatus.ATTENTION] == 1
        assert status_counts[RealmHealthStatus.HEALTHY] == 6

        # Verify batch event contains correct counts
        batch_event = event_emitter.all_realms_computed_events[0]
        assert batch_event.critical_count == 1
        assert batch_event.degraded_count == 1
        assert batch_event.attention_count == 1
        assert batch_event.healthy_count == 6


class TestRealmHealthRepositoryIntegration:
    """Integration tests for realm health repository operations."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_health(self) -> None:
        """Test saving and retrieving health records."""
        repo = RealmHealthRepositoryStub()

        health = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=42,
            petitions_fated=38,
            referrals_pending=3,
            escalations_pending=2,
        )

        await repo.save_health(health)

        retrieved = await repo.get_by_realm_cycle(
            "realm_privacy_discretion_services", "2026-W04"
        )

        assert retrieved is not None
        assert retrieved.health_id == health.health_id
        assert retrieved.petitions_received == 42

    @pytest.mark.asyncio
    async def test_get_all_for_cycle(self) -> None:
        """Test retrieving all health records for a cycle."""
        repo = RealmHealthRepositoryStub()

        # Add health for multiple realms
        for i, realm_id in enumerate(CANONICAL_REALM_IDS[:5]):
            health = RealmHealth.compute(
                realm_id=realm_id,
                cycle_id="2026-W04",
                petitions_received=10 * (i + 1),
            )
            await repo.save_health(health)

        results = await repo.get_all_for_cycle("2026-W04")

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_previous_cycle_lookup(self) -> None:
        """Test looking up previous cycle health."""
        repo = RealmHealthRepositoryStub()

        realm_id = "realm_privacy_discretion_services"

        # Add W03 health
        w03_health = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W03",
            petitions_received=100,
        )
        await repo.save_health(w03_health)

        # Add W04 health
        w04_health = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W04",
            petitions_received=120,
        )
        await repo.save_health(w04_health)

        # Lookup previous from W04
        previous = await repo.get_previous_cycle(realm_id, "2026-W04")

        assert previous is not None
        assert previous.cycle_id == "2026-W03"
        assert previous.petitions_received == 100

    @pytest.mark.asyncio
    async def test_status_count_aggregation(self) -> None:
        """Test counting realms by status for a cycle."""
        repo = RealmHealthRepositoryStub()

        # Add varied health states
        health1 = RealmHealth.compute(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            escalations_pending=15,  # CRITICAL
        )
        await repo.save_health(health1)

        health2 = RealmHealth.compute(
            realm_id="realm_relationship_facilitation",
            cycle_id="2026-W04",
            escalations_pending=3,  # ATTENTION
        )
        await repo.save_health(health2)

        health3 = RealmHealth.compute(
            realm_id="realm_knowledge_skill_development",
            cycle_id="2026-W04",
            escalations_pending=0,  # HEALTHY
        )
        await repo.save_health(health3)

        counts = await repo.count_by_status_for_cycle("2026-W04")

        assert counts["CRITICAL"] == 1
        assert counts["ATTENTION"] == 1
        assert counts["HEALTHY"] == 1


class TestRealmHealthEventWitnessing:
    """Integration tests for event witnessing (CT-12)."""

    @pytest.mark.asyncio
    async def test_all_computations_emit_events(self) -> None:
        """Test that all health computations emit witnessed events."""
        realm_health_repo = RealmHealthRepositoryStub()
        adoption_ratio_repo = AdoptionRatioRepositoryStub()
        event_emitter = MockEventEmitter()

        service = RealmHealthComputeService(
            realm_health_repo=realm_health_repo,
            adoption_ratio_repo=adoption_ratio_repo,
            event_emitter=event_emitter,
        )

        await service.compute_for_cycle(cycle_id="2026-W04")

        # Each realm should have emitted an event
        assert len(event_emitter.health_computed_events) == 9

        # Verify event payload structure
        for event in event_emitter.health_computed_events:
            assert event.event_id is not None
            assert event.health_id is not None
            assert event.realm_id in CANONICAL_REALM_IDS
            assert event.cycle_id == "2026-W04"
            assert event.health_status is not None

    @pytest.mark.asyncio
    async def test_status_changes_emit_events(self) -> None:
        """Test that status changes emit witnessed events."""
        realm_health_repo = RealmHealthRepositoryStub()
        adoption_ratio_repo = AdoptionRatioRepositoryStub()
        event_emitter = MockEventEmitter()

        service = RealmHealthComputeService(
            realm_health_repo=realm_health_repo,
            adoption_ratio_repo=adoption_ratio_repo,
            event_emitter=event_emitter,
        )

        realm_id = "realm_privacy_discretion_services"

        # W03: HEALTHY
        await service.compute_for_realm(
            realm_id=realm_id,
            cycle_id="2026-W03",
            escalations_pending=0,
        )

        # W04: CRITICAL (triggers status change)
        await service.compute_for_realm(
            realm_id=realm_id,
            cycle_id="2026-W04",
            escalations_pending=15,
        )

        # Verify status change event
        assert len(event_emitter.status_changed_events) == 1
        event = event_emitter.status_changed_events[0]

        assert event.realm_id == realm_id
        assert event.previous_status == "HEALTHY"
        assert event.new_status == "CRITICAL"
        assert event.event_id is not None
