"""Realm health compute service (Story 8.7, HP-7).

This module implements the service for computing realm health metrics
across all canonical realms for governance monitoring.

Constitutional Constraints:
- HP-7: Read model projections for realm health
- CT-11: Track petition flow (speech vs agenda)
- CT-12: Witnessing creates accountability
- FR-8.1: Realm health metrics tracked per governance cycle

Developer Golden Rules:
1. CANONICAL - Compute for all 9 canonical realms
2. IDEMPOTENT - Re-computing same cycle overwrites previous
3. WITNESSED - Emit events for all computations (CT-12)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram

from src.application.ports.realm_health_repository import RealmHealthRepositoryProtocol
from src.application.ports.adoption_ratio_repository import (
    AdoptionRatioRepositoryProtocol,
)
from src.domain.events.realm_health import (
    AllRealmsHealthComputedEventPayload,
    RealmHealthComputedEventPayload,
    RealmHealthStatusChangedEventPayload,
)
from src.domain.models.realm import CANONICAL_REALM_IDS
from src.domain.models.realm_health import RealmHealth, RealmHealthStatus

logger = logging.getLogger(__name__)


# Prometheus metrics
REALM_HEALTH_PETITIONS_RECEIVED = Gauge(
    "realm_health_petitions_received",
    "Petitions received by realm in current cycle",
    ["realm"],
)
REALM_HEALTH_PETITIONS_FATED = Gauge(
    "realm_health_petitions_fated",
    "Petitions completing Three Fates by realm",
    ["realm"],
)
REALM_HEALTH_REFERRALS_PENDING = Gauge(
    "realm_health_referrals_pending",
    "Pending Knight referrals by realm",
    ["realm"],
)
REALM_HEALTH_ESCALATIONS_PENDING = Gauge(
    "realm_health_escalations_pending",
    "Pending King escalations by realm",
    ["realm"],
)
REALM_HEALTH_STATUS = Gauge(
    "realm_health_status",
    "Realm health status (1=current status)",
    ["realm", "status"],
)
REALM_HEALTH_COMPUTATION_DURATION = Histogram(
    "realm_health_computation_duration_seconds",
    "Duration of realm health computation",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
REALM_HEALTH_COMPUTATIONS_TOTAL = Counter(
    "realm_health_computations_total",
    "Total realm health computations",
    ["realm"],
)
REALM_HEALTH_STATUS_CHANGES_TOTAL = Counter(
    "realm_health_status_changes_total",
    "Total realm health status changes",
    ["realm", "from_status", "to_status"],
)


class RealmHealthComputeService:
    """Service for computing realm health metrics (Story 8.7, HP-7).

    Computes health metrics for all canonical realms based on petition
    activity, referral status, and escalation status.

    Constitutional Constraints:
    - HP-7: Read model projections for realm health
    - CT-11: Track petition flow (speech vs agenda)
    - CT-12: Witness all computations via events
    """

    def __init__(
        self,
        realm_health_repo: RealmHealthRepositoryProtocol,
        adoption_ratio_repo: AdoptionRatioRepositoryProtocol,
        event_emitter: RealmHealthEventEmitterProtocol | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            realm_health_repo: Repository for realm health persistence
            adoption_ratio_repo: Repository for adoption ratio data
            event_emitter: Optional event emitter for witnessing (CT-12)
        """
        self._realm_health_repo = realm_health_repo
        self._adoption_ratio_repo = adoption_ratio_repo
        self._event_emitter = event_emitter

    async def compute_for_cycle(
        self,
        cycle_id: str,
        petition_counts: dict[str, dict[str, int]] | None = None,
        referral_counts: dict[str, dict[str, int]] | None = None,
        escalation_counts: dict[str, dict[str, int]] | None = None,
        referral_durations: dict[str, int | None] | None = None,
    ) -> list[RealmHealth]:
        """Compute health for all canonical realms in a cycle.

        Args:
            cycle_id: Governance cycle identifier (YYYY-Wnn)
            petition_counts: Optional pre-computed petition counts by realm
                Format: {realm_id: {"received": N, "fated": N}}
            referral_counts: Optional pre-computed referral counts by realm
                Format: {realm_id: {"pending": N, "expired": N}}
            escalation_counts: Optional pre-computed escalation counts by realm
                Format: {realm_id: {"pending": N}}
            referral_durations: Optional average referral duration by realm
                Format: {realm_id: seconds or None}

        Returns:
            List of RealmHealth records for all canonical realms.
        """
        start_time = time.time()
        logger.info(f"Computing realm health for cycle {cycle_id}")

        # Default empty dicts if not provided
        petition_counts = petition_counts or {}
        referral_counts = referral_counts or {}
        escalation_counts = escalation_counts or {}
        referral_durations = referral_durations or {}

        results: list[RealmHealth] = []
        status_counts: dict[str, int] = {
            RealmHealthStatus.HEALTHY.value: 0,
            RealmHealthStatus.ATTENTION.value: 0,
            RealmHealthStatus.DEGRADED.value: 0,
            RealmHealthStatus.CRITICAL.value: 0,
        }

        for realm_id in CANONICAL_REALM_IDS:
            health = await self.compute_for_realm(
                realm_id=realm_id,
                cycle_id=cycle_id,
                petitions_received=petition_counts.get(realm_id, {}).get("received", 0),
                petitions_fated=petition_counts.get(realm_id, {}).get("fated", 0),
                referrals_pending=referral_counts.get(realm_id, {}).get("pending", 0),
                referrals_expired=referral_counts.get(realm_id, {}).get("expired", 0),
                escalations_pending=escalation_counts.get(realm_id, {}).get(
                    "pending", 0
                ),
                average_referral_duration=referral_durations.get(realm_id),
            )
            results.append(health)

            # Track status counts
            status = health.health_status().value
            status_counts[status] = status_counts.get(status, 0) + 1

        # Emit batch completion event
        duration = time.time() - start_time
        REALM_HEALTH_COMPUTATION_DURATION.observe(duration)

        if self._event_emitter:
            await self._event_emitter.emit_all_realms_computed(
                AllRealmsHealthComputedEventPayload.create(
                    cycle_id=cycle_id,
                    realm_count=len(results),
                    healthy_count=status_counts[RealmHealthStatus.HEALTHY.value],
                    attention_count=status_counts[RealmHealthStatus.ATTENTION.value],
                    degraded_count=status_counts[RealmHealthStatus.DEGRADED.value],
                    critical_count=status_counts[RealmHealthStatus.CRITICAL.value],
                    computed_at=datetime.now(timezone.utc),
                )
            )

        logger.info(
            f"Completed realm health computation for {len(results)} realms "
            f"in {duration:.2f}s. Status: "
            f"HEALTHY={status_counts[RealmHealthStatus.HEALTHY.value]}, "
            f"ATTENTION={status_counts[RealmHealthStatus.ATTENTION.value]}, "
            f"DEGRADED={status_counts[RealmHealthStatus.DEGRADED.value]}, "
            f"CRITICAL={status_counts[RealmHealthStatus.CRITICAL.value]}"
        )

        return results

    async def compute_for_realm(
        self,
        realm_id: str,
        cycle_id: str,
        petitions_received: int = 0,
        petitions_fated: int = 0,
        referrals_pending: int = 0,
        referrals_expired: int = 0,
        escalations_pending: int = 0,
        average_referral_duration: int | None = None,
    ) -> RealmHealth:
        """Compute health for a specific realm.

        Args:
            realm_id: Realm identifier
            cycle_id: Governance cycle identifier
            petitions_received: Petitions received this cycle
            petitions_fated: Petitions completing Three Fates
            referrals_pending: Current pending referrals
            referrals_expired: Referrals that expired
            escalations_pending: Current pending escalations
            average_referral_duration: Average referral processing time (seconds)

        Returns:
            RealmHealth record for the realm.
        """
        # Get adoption rate from Story 8.6 metrics
        adoption_rate: float | None = None
        adoption_metrics = await self._adoption_ratio_repo.get_metrics_by_realm_cycle(
            realm_id, cycle_id
        )
        if adoption_metrics:
            adoption_rate = adoption_metrics.adoption_ratio

        # Get previous health for status change detection
        previous_health = await self._realm_health_repo.get_previous_cycle(
            realm_id, cycle_id
        )

        # Compute health
        health = RealmHealth.compute(
            realm_id=realm_id,
            cycle_id=cycle_id,
            petitions_received=petitions_received,
            petitions_fated=petitions_fated,
            referrals_pending=referrals_pending,
            referrals_expired=referrals_expired,
            escalations_pending=escalations_pending,
            adoption_rate=adoption_rate,
            average_referral_duration_seconds=average_referral_duration,
        )

        # Persist
        await self._realm_health_repo.save_health(health)

        # Update Prometheus metrics
        self._update_prometheus_metrics(health)

        # Emit events (CT-12)
        if self._event_emitter:
            await self._event_emitter.emit_health_computed(
                RealmHealthComputedEventPayload.create(
                    health_id=health.health_id,
                    realm_id=health.realm_id,
                    cycle_id=health.cycle_id,
                    petitions_received=health.petitions_received,
                    petitions_fated=health.petitions_fated,
                    referrals_pending=health.referrals_pending,
                    escalations_pending=health.escalations_pending,
                    health_status=health.health_status().value,
                    computed_at=health.computed_at,
                )
            )

            # Check for status change
            if previous_health:
                previous_status = previous_health.health_status()
                current_status = health.health_status()
                if previous_status != current_status:
                    await self._event_emitter.emit_status_changed(
                        RealmHealthStatusChangedEventPayload.create(
                            realm_id=realm_id,
                            cycle_id=cycle_id,
                            previous_status=previous_status.value,
                            new_status=current_status.value,
                            changed_at=health.computed_at,
                        )
                    )
                    REALM_HEALTH_STATUS_CHANGES_TOTAL.labels(
                        realm=realm_id,
                        from_status=previous_status.value,
                        to_status=current_status.value,
                    ).inc()

        REALM_HEALTH_COMPUTATIONS_TOTAL.labels(realm=realm_id).inc()

        logger.debug(
            f"Computed health for {realm_id} cycle {cycle_id}: "
            f"status={health.health_status().value}, "
            f"received={petitions_received}, fated={petitions_fated}, "
            f"pending_referrals={referrals_pending}, pending_escalations={escalations_pending}"
        )

        return health

    def _update_prometheus_metrics(self, health: RealmHealth) -> None:
        """Update Prometheus metrics for a realm.

        Args:
            health: RealmHealth record
        """
        realm = health.realm_id

        REALM_HEALTH_PETITIONS_RECEIVED.labels(realm=realm).set(
            health.petitions_received
        )
        REALM_HEALTH_PETITIONS_FATED.labels(realm=realm).set(health.petitions_fated)
        REALM_HEALTH_REFERRALS_PENDING.labels(realm=realm).set(health.referrals_pending)
        REALM_HEALTH_ESCALATIONS_PENDING.labels(realm=realm).set(
            health.escalations_pending
        )

        # Set status gauge (only one should be 1)
        current_status = health.health_status()
        for status in RealmHealthStatus:
            REALM_HEALTH_STATUS.labels(realm=realm, status=status.value).set(
                1 if status == current_status else 0
            )


class RealmHealthEventEmitterProtocol:
    """Protocol for realm health event emission (CT-12)."""

    async def emit_health_computed(
        self, event: RealmHealthComputedEventPayload
    ) -> None:
        """Emit event when realm health is computed."""
        ...

    async def emit_status_changed(
        self, event: RealmHealthStatusChangedEventPayload
    ) -> None:
        """Emit event when realm health status changes."""
        ...

    async def emit_all_realms_computed(
        self, event: AllRealmsHealthComputedEventPayload
    ) -> None:
        """Emit event when all realms health computation completes."""
        ...
