"""Realm health event payloads (Story 8.7, CT-12).

This module defines the event payloads for realm health computation
and status changes in the petition system.

Constitutional Constraints:
- CT-12: Witnessing creates accountability - All events witnessed
- HP-7: Read model projections for realm health

Developer Golden Rules:
1. IMMUTABILITY - Event payloads are frozen dataclasses
2. SERIALIZATION - All payloads have to_dict() for event store
3. SCHEMA VERSION - Include schema_version for evolution
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class RealmHealthComputedEventPayload:
    """Event when realm health is computed (Story 8.7, CT-12).

    Emitted when realm health metrics are computed for a cycle.

    Attributes:
        event_id: Unique event identifier
        health_id: Health record identifier
        realm_id: Realm identifier
        cycle_id: Governance cycle identifier
        petitions_received: Petitions received this cycle
        petitions_fated: Petitions completing Three Fates
        referrals_pending: Current pending referrals
        escalations_pending: Current pending escalations
        health_status: Derived health status
        computed_at: When health was computed
    """

    event_id: UUID
    health_id: UUID
    realm_id: str
    cycle_id: str
    petitions_received: int
    petitions_fated: int
    referrals_pending: int
    escalations_pending: int
    health_status: str
    computed_at: datetime

    @classmethod
    def create(
        cls,
        health_id: UUID,
        realm_id: str,
        cycle_id: str,
        petitions_received: int,
        petitions_fated: int,
        referrals_pending: int,
        escalations_pending: int,
        health_status: str,
        computed_at: datetime,
    ) -> RealmHealthComputedEventPayload:
        """Create a RealmHealthComputed event payload.

        Args:
            health_id: Health record identifier
            realm_id: Realm identifier
            cycle_id: Governance cycle identifier
            petitions_received: Petitions received this cycle
            petitions_fated: Petitions completing Three Fates
            referrals_pending: Current pending referrals
            escalations_pending: Current pending escalations
            health_status: Derived health status string
            computed_at: When health was computed

        Returns:
            RealmHealthComputedEventPayload instance.
        """
        return cls(
            event_id=uuid4(),
            health_id=health_id,
            realm_id=realm_id,
            cycle_id=cycle_id,
            petitions_received=petitions_received,
            petitions_fated=petitions_fated,
            referrals_pending=referrals_pending,
            escalations_pending=escalations_pending,
            health_status=health_status,
            computed_at=computed_at,
        )

    def to_dict(self) -> dict:
        """Serialize for event store (CT-12 witnessing)."""
        return {
            "schema_version": "1.0.0",
            "event_id": str(self.event_id),
            "health_id": str(self.health_id),
            "realm_id": self.realm_id,
            "cycle_id": self.cycle_id,
            "petitions_received": self.petitions_received,
            "petitions_fated": self.petitions_fated,
            "referrals_pending": self.referrals_pending,
            "escalations_pending": self.escalations_pending,
            "health_status": self.health_status,
            "computed_at": self.computed_at.isoformat(),
        }


@dataclass(frozen=True)
class RealmHealthStatusChangedEventPayload:
    """Event when realm health status changes (Story 8.7, CT-12).

    Emitted when a realm transitions between health statuses.

    Attributes:
        event_id: Unique event identifier
        realm_id: Realm identifier
        cycle_id: Governance cycle identifier
        previous_status: Previous health status
        new_status: New health status
        changed_at: When status changed
    """

    event_id: UUID
    realm_id: str
    cycle_id: str
    previous_status: str
    new_status: str
    changed_at: datetime

    @classmethod
    def create(
        cls,
        realm_id: str,
        cycle_id: str,
        previous_status: str,
        new_status: str,
        changed_at: datetime,
    ) -> RealmHealthStatusChangedEventPayload:
        """Create a RealmHealthStatusChanged event payload.

        Args:
            realm_id: Realm identifier
            cycle_id: Governance cycle identifier
            previous_status: Previous health status string
            new_status: New health status string
            changed_at: When status changed

        Returns:
            RealmHealthStatusChangedEventPayload instance.
        """
        return cls(
            event_id=uuid4(),
            realm_id=realm_id,
            cycle_id=cycle_id,
            previous_status=previous_status,
            new_status=new_status,
            changed_at=changed_at,
        )

    def to_dict(self) -> dict:
        """Serialize for event store (CT-12 witnessing)."""
        return {
            "schema_version": "1.0.0",
            "event_id": str(self.event_id),
            "realm_id": self.realm_id,
            "cycle_id": self.cycle_id,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "changed_at": self.changed_at.isoformat(),
        }


@dataclass(frozen=True)
class AllRealmsHealthComputedEventPayload:
    """Event when health is computed for all realms (Story 8.7, CT-12).

    Emitted at the end of a cycle computation batch.

    Attributes:
        event_id: Unique event identifier
        cycle_id: Governance cycle identifier
        realm_count: Number of realms computed
        healthy_count: Number of realms in HEALTHY status
        attention_count: Number of realms in ATTENTION status
        degraded_count: Number of realms in DEGRADED status
        critical_count: Number of realms in CRITICAL status
        computed_at: When batch computation completed
    """

    event_id: UUID
    cycle_id: str
    realm_count: int
    healthy_count: int
    attention_count: int
    degraded_count: int
    critical_count: int
    computed_at: datetime

    @classmethod
    def create(
        cls,
        cycle_id: str,
        realm_count: int,
        healthy_count: int,
        attention_count: int,
        degraded_count: int,
        critical_count: int,
        computed_at: datetime,
    ) -> AllRealmsHealthComputedEventPayload:
        """Create an AllRealmsHealthComputed event payload.

        Args:
            cycle_id: Governance cycle identifier
            realm_count: Total realms computed
            healthy_count: Realms in HEALTHY status
            attention_count: Realms in ATTENTION status
            degraded_count: Realms in DEGRADED status
            critical_count: Realms in CRITICAL status
            computed_at: When computation completed

        Returns:
            AllRealmsHealthComputedEventPayload instance.
        """
        return cls(
            event_id=uuid4(),
            cycle_id=cycle_id,
            realm_count=realm_count,
            healthy_count=healthy_count,
            attention_count=attention_count,
            degraded_count=degraded_count,
            critical_count=critical_count,
            computed_at=computed_at,
        )

    def to_dict(self) -> dict:
        """Serialize for event store (CT-12 witnessing)."""
        return {
            "schema_version": "1.0.0",
            "event_id": str(self.event_id),
            "cycle_id": self.cycle_id,
            "realm_count": self.realm_count,
            "healthy_count": self.healthy_count,
            "attention_count": self.attention_count,
            "degraded_count": self.degraded_count,
            "critical_count": self.critical_count,
            "computed_at": self.computed_at.isoformat(),
        }
