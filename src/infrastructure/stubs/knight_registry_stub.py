"""In-memory stub implementation of KnightRegistryProtocol (Story 4.7).

This module provides an in-memory implementation for testing purposes.
Not intended for production use.

Constitutional Constraints:
- FR-4.7: System SHALL enforce max concurrent referrals per Knight
- NFR-7.3: Referral load balancing - max concurrent per Knight configurable
"""

from __future__ import annotations

from uuid import UUID


class KnightRegistryStub:
    """In-memory implementation of KnightRegistryProtocol.

    Stores Knight-realm mappings in memory for testing. Provides all
    registry operations needed by KnightConcurrentLimitService.

    Example:
        >>> stub = KnightRegistryStub()
        >>> stub.add_knight(knight_id, realm_id)
        >>> knights = await stub.get_knights_in_realm(realm_id)
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._knights: set[UUID] = set()
        self._knight_realms: dict[UUID, UUID] = {}  # knight_id -> realm_id
        self._realm_knights: dict[UUID, set[UUID]] = {}  # realm_id -> knight_ids

    def add_knight(self, knight_id: UUID, realm_id: UUID) -> None:
        """Register a Knight with a realm.

        Args:
            knight_id: The Knight's archon UUID.
            realm_id: The realm to assign the Knight to.
        """
        self._knights.add(knight_id)
        self._knight_realms[knight_id] = realm_id

        if realm_id not in self._realm_knights:
            self._realm_knights[realm_id] = set()
        self._realm_knights[realm_id].add(knight_id)

    def remove_knight(self, knight_id: UUID) -> None:
        """Remove a Knight from the registry.

        Args:
            knight_id: The Knight's archon UUID.
        """
        if knight_id in self._knights:
            self._knights.discard(knight_id)
            realm_id = self._knight_realms.pop(knight_id, None)
            if realm_id and realm_id in self._realm_knights:
                self._realm_knights[realm_id].discard(knight_id)

    async def get_knights_in_realm(
        self,
        realm_id: UUID,
    ) -> list[UUID]:
        """Get all Knights assigned to a realm.

        Args:
            realm_id: The realm UUID.

        Returns:
            List of Knight archon UUIDs in the realm.
        """
        knights = self._realm_knights.get(realm_id, set())
        return list(knights)

    async def is_knight(
        self,
        archon_id: UUID,
    ) -> bool:
        """Check if an archon is a Knight.

        Args:
            archon_id: The archon UUID.

        Returns:
            True if archon has Knight role, False otherwise.
        """
        return archon_id in self._knights

    async def get_knight_realm(
        self,
        knight_id: UUID,
    ) -> UUID | None:
        """Get the realm a Knight is assigned to.

        Args:
            knight_id: The Knight's archon UUID.

        Returns:
            Realm UUID if Knight is assigned, None otherwise.
        """
        return self._knight_realms.get(knight_id)

    def clear(self) -> None:
        """Clear all stored data. For testing only."""
        self._knights.clear()
        self._knight_realms.clear()
        self._realm_knights.clear()

    def count_knights(self) -> int:
        """Return total number of Knights. For testing only."""
        return len(self._knights)

    def count_knights_in_realm(self, realm_id: UUID) -> int:
        """Return number of Knights in a realm. For testing only."""
        return len(self._realm_knights.get(realm_id, set()))
