"""ArchonPool protocol for Three Fates deliberation (Story 0.7, HP-11).

This module defines the protocol for selecting Fate Archons for petition
deliberation. The Three Fates system requires exactly 3 Marquis-rank Archons
to be assigned to each petition for supermajority consensus voting.

Constitutional Constraints:
- HP-11: Archon persona definitions (Three Fates pool)
- FR-11.1: System assigns exactly 3 Marquis-rank Archons per petition
- Determinism: Selection must be deterministic given (petition_id + seed)

Developer Golden Rules:
1. DETERMINISM - Same inputs always produce same selection
2. IDEMPOTENT - Repeated assignment returns existing selection
3. EXACTLY_THREE - Never more, never fewer Archons assigned
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.fate_archon import FateArchon


class ArchonPoolProtocol(Protocol):
    """Protocol for selecting Fate Archons for deliberation.

    Implementations must guarantee:
    1. Exactly 3 Archons are selected per petition
    2. Selection is deterministic given (petition_id + seed)
    3. Selected Archons are from the configured Three Fates pool
    4. Assignment is idempotent (same petition_id returns same selection)

    Constitutional Constraints:
    - FR-11.1: Exactly 3 Marquis-rank Archons per petition
    - HP-11: Archon persona definitions required
    """

    def select_archons(
        self,
        petition_id: UUID,
        seed: int | None = None,
    ) -> tuple[FateArchon, FateArchon, FateArchon]:
        """Select exactly 3 Fate Archons for a petition.

        Selection is deterministic: given the same (petition_id, seed),
        the same 3 Archons will always be returned in the same order.

        Args:
            petition_id: UUID of the petition requiring deliberation.
            seed: Optional seed for deterministic selection. If None,
                  uses petition_id bytes as seed.

        Returns:
            Tuple of exactly 3 FateArchon instances.

        Raises:
            ValueError: If pool has fewer than 3 Archons.
        """
        ...

    def get_archon_by_id(self, archon_id: UUID) -> FateArchon | None:
        """Retrieve a Fate Archon by ID.

        Args:
            archon_id: UUID of the Fate Archon.

        Returns:
            FateArchon if found, None otherwise.
        """
        ...

    def get_archon_by_name(self, name: str) -> FateArchon | None:
        """Retrieve a Fate Archon by name.

        Args:
            name: Name of the Fate Archon (e.g., "Amon").

        Returns:
            FateArchon if found, None otherwise.
        """
        ...

    def list_all_archons(self) -> list[FateArchon]:
        """List all Fate Archons in the pool.

        Returns:
            List of all FateArchon instances in the pool.
        """
        ...

    def get_pool_size(self) -> int:
        """Get the number of Archons in the pool.

        Returns:
            Number of Archons available for selection.
        """
        ...

    def is_valid_archon_id(self, archon_id: UUID) -> bool:
        """Check if an ID belongs to a valid Fate Archon.

        Args:
            archon_id: UUID to validate.

        Returns:
            True if ID is in the pool, False otherwise.
        """
        ...
