"""Realm health domain model (Story 8.7, HP-7).

This module defines the RealmHealth aggregate for tracking per-realm
petition metrics in the Three Fates petition system.

Constitutional Constraints:
- HP-7: Read model projections for realm-level health monitoring
- CT-11: "Speech is unlimited. Agenda is scarce." - Track petition flow
- CT-12: Witnessing creates accountability -> Frozen dataclass
- FR-8.1: Realm health metrics tracked per governance cycle

Developer Golden Rules:
1. IMMUTABILITY - RealmHealth is a frozen dataclass (CT-12)
2. CANONICAL - Only track canonical realms from CANONICAL_REALM_IDS
3. COMPUTE - Use compute() factory for creating instances
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


class RealmHealthStatus(Enum):
    """Health status for a realm (Story 8.7).

    Derived from realm metrics to provide quick health assessment.

    Statuses:
        HEALTHY: Normal operation, no significant issues
        ATTENTION: Minor issues requiring monitoring
        DEGRADED: Significant issues affecting operation
        CRITICAL: Severe issues requiring immediate attention
    """

    HEALTHY = "HEALTHY"
    ATTENTION = "ATTENTION"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RealmHealth:
    """Realm health aggregate (Story 8.7, HP-7).

    Tracks per-realm petition metrics for governance monitoring.
    Provides the read model projection for realm-level health.

    Constitutional Constraints:
    - HP-7: Read model projections for realm health
    - CT-11: Track petition flow (speech vs agenda)
    - CT-12: Witnessing creates accountability (frozen)

    Attributes:
        health_id: Unique identifier for this health record
        realm_id: Realm identifier (from CANONICAL_REALM_IDS)
        cycle_id: Governance cycle identifier (YYYY-Wnn)
        petitions_received: Petitions received in this realm this cycle
        petitions_fated: Petitions that completed Three Fates deliberation
        referrals_pending: Current pending Knight referrals
        referrals_expired: Referrals that expired without recommendation
        escalations_pending: Petitions awaiting King decision
        adoption_rate: adoptions / escalations (None if no escalations)
        average_referral_duration_seconds: Mean referral processing time
        computed_at: When health was computed (UTC)
    """

    health_id: UUID
    realm_id: str
    cycle_id: str
    petitions_received: int
    petitions_fated: int
    referrals_pending: int
    referrals_expired: int
    escalations_pending: int
    adoption_rate: float | None
    average_referral_duration_seconds: int | None
    computed_at: datetime

    # Health status thresholds
    ESCALATION_ATTENTION_THRESHOLD: int = 1
    ESCALATION_DEGRADED_THRESHOLD: int = 6
    ESCALATION_CRITICAL_THRESHOLD: int = 10
    EXPIRY_RATE_ATTENTION_THRESHOLD: float = 0.10
    EXPIRY_RATE_DEGRADED_THRESHOLD: float = 0.20
    ADOPTION_RATE_CRITICAL_THRESHOLD: float = 0.70

    @classmethod
    def compute(
        cls,
        realm_id: str,
        cycle_id: str,
        petitions_received: int = 0,
        petitions_fated: int = 0,
        referrals_pending: int = 0,
        referrals_expired: int = 0,
        escalations_pending: int = 0,
        adoption_rate: float | None = None,
        average_referral_duration_seconds: int | None = None,
    ) -> RealmHealth:
        """Compute realm health for a realm/cycle (HP-7).

        Args:
            realm_id: Realm identifier (canonical name)
            cycle_id: Governance cycle identifier (e.g., "2026-W04")
            petitions_received: Count of petitions received this cycle
            petitions_fated: Count of petitions completing Three Fates
            referrals_pending: Current pending Knight referrals
            referrals_expired: Referrals that expired without recommendation
            escalations_pending: Petitions awaiting King decision
            adoption_rate: Adoption ratio from Story 8.6 (None if no escalations)
            average_referral_duration_seconds: Mean referral processing time

        Returns:
            RealmHealth instance with computed health.
        """
        return cls(
            health_id=uuid4(),
            realm_id=realm_id,
            cycle_id=cycle_id,
            petitions_received=petitions_received,
            petitions_fated=petitions_fated,
            referrals_pending=referrals_pending,
            referrals_expired=referrals_expired,
            escalations_pending=escalations_pending,
            adoption_rate=adoption_rate,
            average_referral_duration_seconds=average_referral_duration_seconds,
            computed_at=datetime.now(timezone.utc),
        )

    @property
    def referral_expiry_rate(self) -> float | None:
        """Calculate referral expiry rate.

        Returns:
            Ratio of expired referrals to total referrals (resolved + expired + pending),
            or None if no referral activity.
        """
        total_referrals = (
            self.referrals_pending
            + self.referrals_expired
            + self.petitions_fated  # Approximates completed referrals
        )
        if total_referrals == 0:
            return None
        return self.referrals_expired / total_referrals

    def health_status(self) -> RealmHealthStatus:
        """Derive health status from realm metrics (Story 8.7).

        Status is derived based on:
        - HEALTHY: No pending escalations, referral expiry rate < 10%
        - ATTENTION: 1-5 pending escalations OR expiry rate 10-20%
        - DEGRADED: 6-10 pending escalations OR expiry rate > 20%
        - CRITICAL: > 10 pending escalations OR adoption rate > 70%

        Returns:
            RealmHealthStatus enum value.
        """
        # Check critical conditions first
        if self.escalations_pending > self.ESCALATION_CRITICAL_THRESHOLD:
            return RealmHealthStatus.CRITICAL

        if (
            self.adoption_rate is not None
            and self.adoption_rate > self.ADOPTION_RATE_CRITICAL_THRESHOLD
        ):
            return RealmHealthStatus.CRITICAL

        # Check degraded conditions
        expiry_rate = self.referral_expiry_rate
        if self.escalations_pending >= self.ESCALATION_DEGRADED_THRESHOLD:
            return RealmHealthStatus.DEGRADED

        if (
            expiry_rate is not None
            and expiry_rate > self.EXPIRY_RATE_DEGRADED_THRESHOLD
        ):
            return RealmHealthStatus.DEGRADED

        # Check attention conditions
        if self.escalations_pending >= self.ESCALATION_ATTENTION_THRESHOLD:
            return RealmHealthStatus.ATTENTION

        if (
            expiry_rate is not None
            and expiry_rate > self.EXPIRY_RATE_ATTENTION_THRESHOLD
        ):
            return RealmHealthStatus.ATTENTION

        # Otherwise healthy
        return RealmHealthStatus.HEALTHY

    @property
    def is_healthy(self) -> bool:
        """Check if realm is in healthy state."""
        return self.health_status() == RealmHealthStatus.HEALTHY

    @property
    def is_critical(self) -> bool:
        """Check if realm is in critical state."""
        return self.health_status() == RealmHealthStatus.CRITICAL

    @property
    def has_activity(self) -> bool:
        """Check if realm has any petition activity this cycle."""
        return (
            self.petitions_received > 0
            or self.petitions_fated > 0
            or self.referrals_pending > 0
            or self.escalations_pending > 0
        )

    def fate_completion_rate(self) -> float | None:
        """Calculate the rate of petitions completing Three Fates.

        Returns:
            Ratio of fated petitions to received petitions,
            or None if no petitions received.
        """
        if self.petitions_received == 0:
            return None
        return self.petitions_fated / self.petitions_received


@dataclass(frozen=True)
class RealmHealthDelta:
    """Change in realm health between cycles (Story 8.7).

    Used for trend comparison in the dashboard.

    Attributes:
        realm_id: Realm identifier
        current_cycle_id: Current cycle identifier
        previous_cycle_id: Previous cycle identifier
        petitions_received_delta: Change in petitions received
        petitions_fated_delta: Change in petitions fated
        referrals_pending_delta: Change in pending referrals
        escalations_pending_delta: Change in pending escalations
        adoption_rate_delta: Change in adoption rate (None if unavailable)
        status_changed: Whether health status changed
        previous_status: Previous health status
        current_status: Current health status
    """

    realm_id: str
    current_cycle_id: str
    previous_cycle_id: str
    petitions_received_delta: int
    petitions_fated_delta: int
    referrals_pending_delta: int
    escalations_pending_delta: int
    adoption_rate_delta: float | None
    status_changed: bool
    previous_status: RealmHealthStatus
    current_status: RealmHealthStatus

    @classmethod
    def compute(
        cls,
        current: RealmHealth,
        previous: RealmHealth,
    ) -> RealmHealthDelta:
        """Compute delta between two health records.

        Args:
            current: Current cycle health
            previous: Previous cycle health

        Returns:
            RealmHealthDelta with computed differences.
        """
        current_status = current.health_status()
        previous_status = previous.health_status()

        # Calculate adoption rate delta if both have data
        adoption_delta = None
        if current.adoption_rate is not None and previous.adoption_rate is not None:
            adoption_delta = current.adoption_rate - previous.adoption_rate

        return cls(
            realm_id=current.realm_id,
            current_cycle_id=current.cycle_id,
            previous_cycle_id=previous.cycle_id,
            petitions_received_delta=(
                current.petitions_received - previous.petitions_received
            ),
            petitions_fated_delta=current.petitions_fated - previous.petitions_fated,
            referrals_pending_delta=(
                current.referrals_pending - previous.referrals_pending
            ),
            escalations_pending_delta=(
                current.escalations_pending - previous.escalations_pending
            ),
            adoption_rate_delta=adoption_delta,
            status_changed=current_status != previous_status,
            previous_status=previous_status,
            current_status=current_status,
        )

    @property
    def is_improving(self) -> bool:
        """Check if realm health is improving.

        Returns True if status improved or stayed healthy with decreasing
        pending work.
        """
        if self.status_changed:
            # Status hierarchy: HEALTHY > ATTENTION > DEGRADED > CRITICAL
            status_order = {
                RealmHealthStatus.HEALTHY: 0,
                RealmHealthStatus.ATTENTION: 1,
                RealmHealthStatus.DEGRADED: 2,
                RealmHealthStatus.CRITICAL: 3,
            }
            return status_order[self.current_status] < status_order[self.previous_status]

        # Same status - check if work is decreasing
        return (
            self.referrals_pending_delta <= 0
            and self.escalations_pending_delta <= 0
        )

    @property
    def is_degrading(self) -> bool:
        """Check if realm health is degrading.

        Returns True if status degraded or stayed non-healthy with increasing
        pending work.
        """
        if self.status_changed:
            status_order = {
                RealmHealthStatus.HEALTHY: 0,
                RealmHealthStatus.ATTENTION: 1,
                RealmHealthStatus.DEGRADED: 2,
                RealmHealthStatus.CRITICAL: 3,
            }
            return status_order[self.current_status] > status_order[self.previous_status]

        # Same status - check if work is increasing
        if self.current_status != RealmHealthStatus.HEALTHY:
            return (
                self.referrals_pending_delta > 0
                or self.escalations_pending_delta > 0
            )

        return False
