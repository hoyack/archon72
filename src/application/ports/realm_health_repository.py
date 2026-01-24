"""Realm health repository port (Story 8.7, HP-7).

This module defines the repository protocol for realm health persistence.

Constitutional Constraints:
- HP-7: Read model projections for realm health
- CT-12: Witnessing creates accountability

Developer Golden Rules:
1. PROTOCOL - Repository is a Protocol for dependency inversion
2. ASYNC - All methods are async for non-blocking I/O
3. OPTIONAL - Return None for missing records, not exceptions
"""

from __future__ import annotations

from typing import Protocol

from src.domain.models.realm_health import RealmHealth


class RealmHealthRepositoryProtocol(Protocol):
    """Repository protocol for realm health data (Story 8.7).

    Provides persistence operations for RealmHealth aggregates.

    Constitutional Constraints:
    - HP-7: Read model projections for realm health
    - CT-12: Data must be witnessable
    """

    async def save_health(self, health: RealmHealth) -> None:
        """Save a realm health record.

        Inserts a new record or updates existing record for the same
        realm_id/cycle_id combination.

        Args:
            health: RealmHealth instance to save.

        Raises:
            RepositoryError: If persistence fails.
        """
        ...

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
        ...

    async def get_all_for_cycle(self, cycle_id: str) -> list[RealmHealth]:
        """Get health for all realms in a cycle.

        Args:
            cycle_id: Governance cycle identifier (YYYY-Wnn)

        Returns:
            List of RealmHealth records for the cycle, may be empty.
        """
        ...

    async def get_previous_cycle(
        self, realm_id: str, current_cycle_id: str
    ) -> RealmHealth | None:
        """Get health for the previous cycle (for trend comparison).

        Args:
            realm_id: Realm identifier
            current_cycle_id: Current cycle identifier

        Returns:
            RealmHealth for the previous cycle if exists, None otherwise.
        """
        ...

    async def get_latest_for_realm(self, realm_id: str) -> RealmHealth | None:
        """Get the most recent health record for a realm.

        Args:
            realm_id: Realm identifier

        Returns:
            Most recent RealmHealth for the realm, None if no records.
        """
        ...

    async def get_all_latest(self) -> list[RealmHealth]:
        """Get the most recent health record for each realm.

        Returns:
            List of the latest RealmHealth for each realm with data.
        """
        ...

    async def count_by_status_for_cycle(
        self, cycle_id: str
    ) -> dict[str, int]:
        """Count realms by health status for a cycle.

        Args:
            cycle_id: Governance cycle identifier

        Returns:
            Dict mapping status string to count (e.g., {"HEALTHY": 5, "ATTENTION": 2})
        """
        ...
