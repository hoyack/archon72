"""Unit tests for RealmHealthComputeService (Story 8.7).

Tests the service for computing realm health metrics.
"""

from uuid import uuid4

import pytest

from src.application.services.realm_health_compute_service import (
    RealmHealthComputeService,
)
from src.domain.models.adoption_ratio import AdoptionRatioMetrics
from src.domain.models.realm import CANONICAL_REALM_IDS
from src.domain.models.realm_health import RealmHealth
from src.infrastructure.stubs.adoption_ratio_repository_stub import (
    AdoptionRatioRepositoryStub,
)
from src.infrastructure.stubs.realm_health_repository_stub import (
    RealmHealthRepositoryStub,
)


class MockEventEmitter:
    """Mock event emitter for testing."""

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


@pytest.fixture
def realm_health_repo() -> RealmHealthRepositoryStub:
    """Create a fresh realm health repository stub."""
    return RealmHealthRepositoryStub()


@pytest.fixture
def adoption_ratio_repo() -> AdoptionRatioRepositoryStub:
    """Create a fresh adoption ratio repository stub."""
    return AdoptionRatioRepositoryStub()


@pytest.fixture
def event_emitter() -> MockEventEmitter:
    """Create a mock event emitter."""
    return MockEventEmitter()


@pytest.fixture
def service(
    realm_health_repo: RealmHealthRepositoryStub,
    adoption_ratio_repo: AdoptionRatioRepositoryStub,
    event_emitter: MockEventEmitter,
) -> RealmHealthComputeService:
    """Create service with all dependencies."""
    return RealmHealthComputeService(
        realm_health_repo=realm_health_repo,
        adoption_ratio_repo=adoption_ratio_repo,
        event_emitter=event_emitter,
    )


class TestRealmHealthComputeService:
    """Tests for RealmHealthComputeService."""

    @pytest.mark.asyncio
    async def test_compute_for_cycle_creates_health_for_all_realms(
        self,
        service: RealmHealthComputeService,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test that compute_for_cycle creates health for all 9 canonical realms."""
        results = await service.compute_for_cycle(cycle_id="2026-W04")

        assert len(results) == 9
        assert len(results) == len(CANONICAL_REALM_IDS)

        # Verify all canonical realms are covered
        result_realm_ids = {h.realm_id for h in results}
        assert result_realm_ids == set(CANONICAL_REALM_IDS)

    @pytest.mark.asyncio
    async def test_compute_for_cycle_persists_all_health_records(
        self,
        service: RealmHealthComputeService,
        realm_health_repo: RealmHealthRepositoryStub,
    ) -> None:
        """Test that compute_for_cycle persists health for all realms."""
        await service.compute_for_cycle(cycle_id="2026-W04")

        # Verify all records were persisted
        persisted = await realm_health_repo.get_all_for_cycle("2026-W04")
        assert len(persisted) == 9

    @pytest.mark.asyncio
    async def test_compute_for_cycle_uses_provided_metrics(
        self,
        service: RealmHealthComputeService,
    ) -> None:
        """Test that compute_for_cycle uses provided petition/referral counts."""
        realm_id = "realm_privacy_discretion_services"

        results = await service.compute_for_cycle(
            cycle_id="2026-W04",
            petition_counts={realm_id: {"received": 42, "fated": 38}},
            referral_counts={realm_id: {"pending": 3, "expired": 1}},
            escalation_counts={realm_id: {"pending": 2}},
            referral_durations={realm_id: 86400},
        )

        # Find the realm we configured
        health = next(h for h in results if h.realm_id == realm_id)

        assert health.petitions_received == 42
        assert health.petitions_fated == 38
        assert health.referrals_pending == 3
        assert health.referrals_expired == 1
        assert health.escalations_pending == 2
        assert health.average_referral_duration_seconds == 86400

    @pytest.mark.asyncio
    async def test_compute_for_cycle_emits_all_realms_computed_event(
        self,
        service: RealmHealthComputeService,
        event_emitter: MockEventEmitter,
    ) -> None:
        """Test that compute_for_cycle emits AllRealmsHealthComputed event."""
        await service.compute_for_cycle(cycle_id="2026-W04")

        assert len(event_emitter.all_realms_computed_events) == 1
        event = event_emitter.all_realms_computed_events[0]

        assert event.cycle_id == "2026-W04"
        assert event.realm_count == 9

    @pytest.mark.asyncio
    async def test_compute_for_realm_creates_valid_health(
        self,
        service: RealmHealthComputeService,
    ) -> None:
        """Test that compute_for_realm creates a valid health record."""
        health = await service.compute_for_realm(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
            petitions_received=42,
            petitions_fated=38,
            referrals_pending=3,
            referrals_expired=1,
            escalations_pending=2,
            average_referral_duration=86400,
        )

        assert health.realm_id == "realm_privacy_discretion_services"
        assert health.cycle_id == "2026-W04"
        assert health.petitions_received == 42
        assert health.petitions_fated == 38
        assert health.referrals_pending == 3
        assert health.referrals_expired == 1
        assert health.escalations_pending == 2
        assert health.average_referral_duration_seconds == 86400

    @pytest.mark.asyncio
    async def test_compute_for_realm_integrates_adoption_rate(
        self,
        service: RealmHealthComputeService,
        adoption_ratio_repo: AdoptionRatioRepositoryStub,
    ) -> None:
        """Test that compute_for_realm gets adoption rate from Story 8.6."""
        realm_id = "realm_privacy_discretion_services"
        cycle_id = "2026-W04"

        # Add adoption ratio data
        adoption_metrics = AdoptionRatioMetrics.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=10,
            adoption_count=4,
            adopting_kings=[uuid4()],
        )
        adoption_ratio_repo.add_metrics(adoption_metrics)

        health = await service.compute_for_realm(
            realm_id=realm_id,
            cycle_id=cycle_id,
        )

        assert health.adoption_rate == pytest.approx(0.4)

    @pytest.mark.asyncio
    async def test_compute_for_realm_emits_health_computed_event(
        self,
        service: RealmHealthComputeService,
        event_emitter: MockEventEmitter,
    ) -> None:
        """Test that compute_for_realm emits RealmHealthComputed event."""
        await service.compute_for_realm(
            realm_id="realm_privacy_discretion_services",
            cycle_id="2026-W04",
        )

        assert len(event_emitter.health_computed_events) == 1
        event = event_emitter.health_computed_events[0]

        assert event.realm_id == "realm_privacy_discretion_services"
        assert event.cycle_id == "2026-W04"

    @pytest.mark.asyncio
    async def test_compute_for_realm_emits_status_changed_event(
        self,
        service: RealmHealthComputeService,
        realm_health_repo: RealmHealthRepositoryStub,
        event_emitter: MockEventEmitter,
    ) -> None:
        """Test that compute_for_realm emits status change event when status changes."""
        realm_id = "realm_privacy_discretion_services"

        # Add previous cycle health (HEALTHY)
        previous_health = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W03",
            escalations_pending=0,
        )
        realm_health_repo.add_health(previous_health)

        # Compute current cycle (CRITICAL)
        await service.compute_for_realm(
            realm_id=realm_id,
            cycle_id="2026-W04",
            escalations_pending=15,  # Triggers CRITICAL
        )

        assert len(event_emitter.status_changed_events) == 1
        event = event_emitter.status_changed_events[0]

        assert event.realm_id == realm_id
        assert event.previous_status == "HEALTHY"
        assert event.new_status == "CRITICAL"

    @pytest.mark.asyncio
    async def test_compute_for_realm_no_status_change_event_when_same(
        self,
        service: RealmHealthComputeService,
        realm_health_repo: RealmHealthRepositoryStub,
        event_emitter: MockEventEmitter,
    ) -> None:
        """Test no status change event when status remains the same."""
        realm_id = "realm_privacy_discretion_services"

        # Add previous cycle health (HEALTHY)
        previous_health = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id="2026-W03",
            escalations_pending=0,
        )
        realm_health_repo.add_health(previous_health)

        # Compute current cycle (also HEALTHY)
        await service.compute_for_realm(
            realm_id=realm_id,
            cycle_id="2026-W04",
            escalations_pending=0,
        )

        assert len(event_emitter.status_changed_events) == 0

    @pytest.mark.asyncio
    async def test_compute_for_cycle_counts_status_correctly(
        self,
        service: RealmHealthComputeService,
        event_emitter: MockEventEmitter,
    ) -> None:
        """Test that status counts are calculated correctly."""
        # Configure different statuses for different realms
        _ = {}
        escalation_counts = {}

        # First realm: CRITICAL (>10 escalations)
        escalation_counts["realm_privacy_discretion_services"] = {"pending": 15}

        # Second realm: ATTENTION (1-5 escalations)
        escalation_counts["realm_relationship_facilitation"] = {"pending": 3}

        _ = await service.compute_for_cycle(
            cycle_id="2026-W04",
            escalation_counts=escalation_counts,
        )

        event = event_emitter.all_realms_computed_events[0]

        # Verify counts
        assert event.critical_count == 1
        assert event.attention_count == 1
        # Remaining 7 realms should be HEALTHY
        assert event.healthy_count == 7
        assert event.realm_count == 9

    @pytest.mark.asyncio
    async def test_service_without_event_emitter(
        self,
        realm_health_repo: RealmHealthRepositoryStub,
        adoption_ratio_repo: AdoptionRatioRepositoryStub,
    ) -> None:
        """Test service works without event emitter (optional dependency)."""
        service = RealmHealthComputeService(
            realm_health_repo=realm_health_repo,
            adoption_ratio_repo=adoption_ratio_repo,
            event_emitter=None,
        )

        # Should not raise even without event emitter
        results = await service.compute_for_cycle(cycle_id="2026-W04")
        assert len(results) == 9
