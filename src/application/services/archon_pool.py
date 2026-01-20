"""ArchonPool service for Three Fates deliberation (Story 0.7, HP-11).

This module implements the ArchonPool service for selecting Fate Archons
for petition deliberation. Selection is deterministic and repeatable.

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

import hashlib
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.models.fate_archon import (
    THREE_FATES_POOL,
    FateArchon,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ArchonPoolService:
    """Service for selecting Fate Archons for Three Fates deliberation.

    This service implements deterministic selection of exactly 3 Archons
    from the Three Fates pool for each petition. Given the same
    (petition_id, seed) combination, the same 3 Archons will always
    be selected in the same order.

    Constitutional Constraints:
    - FR-11.1: Exactly 3 Marquis-rank Archons per petition
    - HP-11: Uses canonical Archon persona definitions

    Selection Algorithm:
    1. Combine petition_id bytes with optional seed
    2. Hash with SHA-256 for uniform distribution
    3. Use hash bytes to deterministically shuffle pool
    4. Return first 3 from shuffled pool
    """

    REQUIRED_ARCHON_COUNT: int = 3

    def __init__(
        self,
        pool: tuple[FateArchon, ...] | None = None,
    ) -> None:
        """Initialize ArchonPoolService.

        Args:
            pool: Optional custom pool of FateArchons. If None, uses
                  the canonical THREE_FATES_POOL.

        Raises:
            ValueError: If pool has fewer than 3 Archons.
        """
        self._pool = pool if pool is not None else THREE_FATES_POOL
        if len(self._pool) < self.REQUIRED_ARCHON_COUNT:
            raise ValueError(
                f"Pool must have at least {self.REQUIRED_ARCHON_COUNT} Archons, "
                f"got {len(self._pool)}"
            )
        # Build lookup tables
        self._by_id: dict[UUID, FateArchon] = {a.id: a for a in self._pool}
        self._by_name: dict[str, FateArchon] = {a.name: a for a in self._pool}
        logger.info(
            "ArchonPoolService initialized with %d Archons",
            len(self._pool),
        )

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
        # Create deterministic seed from petition_id and optional seed
        seed_bytes = petition_id.bytes
        if seed is not None:
            seed_bytes += seed.to_bytes(8, byteorder="big", signed=True)

        # Hash for uniform distribution
        hash_bytes = hashlib.sha256(seed_bytes).digest()

        # Create deterministic ordering using hash bytes
        # Each Archon gets a score based on combining their ID with hash
        scored_archons: list[tuple[bytes, FateArchon]] = []
        for archon in self._pool:
            combined = hash_bytes + archon.id.bytes
            score = hashlib.sha256(combined).digest()
            scored_archons.append((score, archon))

        # Sort by score for deterministic ordering
        scored_archons.sort(key=lambda x: x[0])

        # Take first 3
        selected = tuple(a for _, a in scored_archons[: self.REQUIRED_ARCHON_COUNT])

        logger.debug(
            "Selected Archons for petition %s: %s",
            petition_id,
            [a.name for a in selected],
        )

        # Type assertion for tuple[FateArchon, FateArchon, FateArchon]
        return (selected[0], selected[1], selected[2])

    def get_archon_by_id(self, archon_id: UUID) -> FateArchon | None:
        """Retrieve a Fate Archon by ID.

        Args:
            archon_id: UUID of the Fate Archon.

        Returns:
            FateArchon if found, None otherwise.
        """
        return self._by_id.get(archon_id)

    def get_archon_by_name(self, name: str) -> FateArchon | None:
        """Retrieve a Fate Archon by name.

        Args:
            name: Name of the Fate Archon (e.g., "Amon").

        Returns:
            FateArchon if found, None otherwise.
        """
        return self._by_name.get(name)

    def list_all_archons(self) -> list[FateArchon]:
        """List all Fate Archons in the pool.

        Returns:
            List of all FateArchon instances in the pool.
        """
        return list(self._pool)

    def get_pool_size(self) -> int:
        """Get the number of Archons in the pool.

        Returns:
            Number of Archons available for selection.
        """
        return len(self._pool)

    def is_valid_archon_id(self, archon_id: UUID) -> bool:
        """Check if an ID belongs to a valid Fate Archon.

        Args:
            archon_id: UUID to validate.

        Returns:
            True if ID is in the pool, False otherwise.
        """
        return archon_id in self._by_id

    def select_substitute(
        self,
        excluded_archon_ids: set[UUID],
    ) -> FateArchon | None:
        """Select a substitute Archon not in the excluded set (Story 2B.4, AC-2).

        Used for Archon substitution when one fails during deliberation.
        Selects the first available Archon not in the excluded set.

        Args:
            excluded_archon_ids: Set of Archon IDs to exclude from selection.

        Returns:
            FateArchon if one is available, None if pool exhausted.
        """
        for archon in self._pool:
            if archon.id not in excluded_archon_ids:
                logger.debug(
                    "Selected substitute Archon: %s (excluded %d archons)",
                    archon.name,
                    len(excluded_archon_ids),
                )
                return archon

        logger.warning(
            "No substitute available: all %d archons excluded",
            len(self._pool),
        )
        return None

    def get_available_archons(
        self,
        excluded_archon_ids: set[UUID],
    ) -> list[FateArchon]:
        """Get all Archons not in the excluded set (Story 2B.4, AC-2).

        Args:
            excluded_archon_ids: Set of Archon IDs to exclude.

        Returns:
            List of available FateArchon instances.
        """
        return [archon for archon in self._pool if archon.id not in excluded_archon_ids]


# Default singleton using canonical pool
_default_archon_pool: ArchonPoolService | None = None


def get_archon_pool_service() -> ArchonPoolService:
    """Get the default ArchonPoolService singleton.

    Returns:
        Default ArchonPoolService with canonical Three Fates pool.
    """
    global _default_archon_pool
    if _default_archon_pool is None:
        _default_archon_pool = ArchonPoolService()
    return _default_archon_pool
