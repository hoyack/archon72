"""Realm health repository stub implementation (Story 8.7).

This module provides an in-memory stub implementation of the
RealmHealthRepositoryProtocol for testing and development.

Developer Golden Rules:
1. STUB - In-memory implementation for testing
2. THREAD-SAFE - Use dict copy for iteration
3. PREVIOUS CYCLE - Calculate previous cycle from current
"""

from __future__ import annotations

import re

from src.domain.models.realm_health import RealmHealth, RealmHealthStatus


class RealmHealthRepositoryStub:
    """In-memory stub implementation of RealmHealthRepositoryProtocol.

    Stores realm health records in memory for testing and development.
    Uses a dict keyed by (realm_id, cycle_id) tuple.
    """

    def __init__(self) -> None:
        """Initialize empty repository."""
        self._health_records: dict[tuple[str, str], RealmHealth] = {}

    async def save_health(self, health: RealmHealth) -> None:
        """Save a realm health record.

        Inserts or replaces record for the realm_id/cycle_id combination.

        Args:
            health: RealmHealth instance to save.
        """
        key = (health.realm_id, health.cycle_id)
        self._health_records[key] = health

    async def get_by_realm_cycle(
        self, realm_id: str, cycle_id: str
    ) -> RealmHealth | None:
        """Get health for a specific realm and cycle.

        Args:
            realm_id: Realm identifier
            cycle_id: Governance cycle identifier (YYYY-Wnn)

        Returns:
            RealmHealth if found, None otherwise.
        """
        key = (realm_id, cycle_id)
        return self._health_records.get(key)

    async def get_all_for_cycle(self, cycle_id: str) -> list[RealmHealth]:
        """Get health for all realms in a cycle.

        Args:
            cycle_id: Governance cycle identifier (YYYY-Wnn)

        Returns:
            List of RealmHealth records for the cycle.
        """
        return [
            health
            for health in self._health_records.values()
            if health.cycle_id == cycle_id
        ]

    async def get_previous_cycle(
        self, realm_id: str, current_cycle_id: str
    ) -> RealmHealth | None:
        """Get health for the previous cycle.

        Args:
            realm_id: Realm identifier
            current_cycle_id: Current cycle identifier (YYYY-Wnn)

        Returns:
            RealmHealth for the previous cycle if exists, None otherwise.
        """
        previous_cycle_id = self._calculate_previous_cycle(current_cycle_id)
        if previous_cycle_id is None:
            return None
        return await self.get_by_realm_cycle(realm_id, previous_cycle_id)

    async def get_latest_for_realm(self, realm_id: str) -> RealmHealth | None:
        """Get the most recent health record for a realm.

        Args:
            realm_id: Realm identifier

        Returns:
            Most recent RealmHealth for the realm, None if no records.
        """
        realm_records = [
            health
            for health in self._health_records.values()
            if health.realm_id == realm_id
        ]
        if not realm_records:
            return None

        # Sort by cycle_id descending (YYYY-Wnn format sorts correctly)
        return max(realm_records, key=lambda h: h.cycle_id)

    async def get_all_latest(self) -> list[RealmHealth]:
        """Get the most recent health record for each realm.

        Returns:
            List of the latest RealmHealth for each realm with data.
        """
        # Group by realm_id
        by_realm: dict[str, list[RealmHealth]] = {}
        for health in self._health_records.values():
            if health.realm_id not in by_realm:
                by_realm[health.realm_id] = []
            by_realm[health.realm_id].append(health)

        # Get latest for each realm
        result = []
        for realm_records in by_realm.values():
            latest = max(realm_records, key=lambda h: h.cycle_id)
            result.append(latest)

        return result

    async def count_by_status_for_cycle(
        self, cycle_id: str
    ) -> dict[str, int]:
        """Count realms by health status for a cycle.

        Args:
            cycle_id: Governance cycle identifier

        Returns:
            Dict mapping status string to count.
        """
        counts: dict[str, int] = {
            RealmHealthStatus.HEALTHY.value: 0,
            RealmHealthStatus.ATTENTION.value: 0,
            RealmHealthStatus.DEGRADED.value: 0,
            RealmHealthStatus.CRITICAL.value: 0,
        }

        cycle_records = await self.get_all_for_cycle(cycle_id)
        for health in cycle_records:
            status = health.health_status().value
            counts[status] = counts.get(status, 0) + 1

        return counts

    def _calculate_previous_cycle(self, cycle_id: str) -> str | None:
        """Calculate the previous cycle ID from current.

        Args:
            cycle_id: Current cycle in YYYY-Wnn format

        Returns:
            Previous cycle ID in YYYY-Wnn format, or None if invalid.
        """
        # Parse YYYY-Wnn format
        match = re.match(r"(\d{4})-W(\d{2})", cycle_id)
        if not match:
            return None

        year = int(match.group(1))
        week = int(match.group(2))

        if week > 1:
            # Same year, previous week
            return f"{year}-W{week - 1:02d}"
        else:
            # Previous year, week 52 (simplified - ignores ISO week nuances)
            return f"{year - 1}-W52"

    # Test helper methods

    def clear(self) -> None:
        """Clear all stored health records (for testing)."""
        self._health_records.clear()

    def count(self) -> int:
        """Get count of stored health records (for testing)."""
        return len(self._health_records)

    def add_health(self, health: RealmHealth) -> None:
        """Synchronous add for test setup."""
        key = (health.realm_id, health.cycle_id)
        self._health_records[key] = health
