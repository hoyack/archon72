"""ArchonPool stub for testing Three Fates deliberation (Story 0.7, HP-11).

This module provides an in-memory stub implementation of the ArchonPool
protocol for testing purposes. It supports operation tracking and
configurable selection behavior.

Developer Golden Rules:
1. OPERATION_TRACKING - Records all operations for test assertions
2. CONFIGURABLE - Supports custom pools and fixed selections
3. DETERMINISTIC - Maintains deterministic selection behavior
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.models.fate_archon import (
    THREE_FATES_POOL,
    DeliberationStyle,
    FateArchon,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass
class ArchonPoolOperation:
    """Record of an operation performed on the stub."""

    operation: str
    timestamp: datetime
    petition_id: UUID | None = None
    archon_id: UUID | None = None
    archon_name: str | None = None
    seed: int | None = None
    result: list[str] | None = None


class ArchonPoolStub:
    """In-memory stub for ArchonPool for testing.

    This stub implements the ArchonPoolProtocol interface with:
    - Configurable Archon pool
    - Operation tracking for test assertions
    - Optional fixed selection override
    - Deterministic selection algorithm (matches service)

    Usage:
        stub = ArchonPoolStub()  # Uses canonical pool
        stub = ArchonPoolStub(populate_canonical=False)  # Empty pool

        # Fixed selection for deterministic tests
        stub.set_fixed_selection([archon1, archon2, archon3])

        # Query operations after test
        ops = stub.get_operations_by_type("select_archons")
    """

    REQUIRED_ARCHON_COUNT: int = 3

    def __init__(
        self,
        populate_canonical: bool = True,
    ) -> None:
        """Initialize the stub.

        Args:
            populate_canonical: If True, pre-populate with canonical
                               THREE_FATES_POOL. If False, start empty.
        """
        self._archons: dict[UUID, FateArchon] = {}
        self._by_name: dict[str, FateArchon] = {}
        self._operations: list[ArchonPoolOperation] = []
        self._fixed_selection: tuple[FateArchon, FateArchon, FateArchon] | None = None

        if populate_canonical:
            for archon in THREE_FATES_POOL:
                self._archons[archon.id] = archon
                self._by_name[archon.name] = archon

    def _record_operation(
        self,
        operation: str,
        petition_id: UUID | None = None,
        archon_id: UUID | None = None,
        archon_name: str | None = None,
        seed: int | None = None,
        result: list[str] | None = None,
    ) -> None:
        """Record an operation for test assertions."""
        self._operations.append(
            ArchonPoolOperation(
                operation=operation,
                timestamp=_utc_now(),
                petition_id=petition_id,
                archon_id=archon_id,
                archon_name=archon_name,
                seed=seed,
                result=result,
            )
        )

    def select_archons(
        self,
        petition_id: UUID,
        seed: int | None = None,
    ) -> tuple[FateArchon, FateArchon, FateArchon]:
        """Select exactly 3 Fate Archons for a petition.

        If fixed_selection is set, returns that instead of computing.
        Otherwise uses deterministic selection matching the service.

        Args:
            petition_id: UUID of the petition requiring deliberation.
            seed: Optional seed for deterministic selection.

        Returns:
            Tuple of exactly 3 FateArchon instances.

        Raises:
            ValueError: If pool has fewer than 3 Archons.
        """
        if len(self._archons) < self.REQUIRED_ARCHON_COUNT:
            raise ValueError(
                f"Pool must have at least {self.REQUIRED_ARCHON_COUNT} Archons, "
                f"got {len(self._archons)}"
            )

        # Return fixed selection if set
        if self._fixed_selection is not None:
            selected = self._fixed_selection
            self._record_operation(
                "select_archons",
                petition_id=petition_id,
                seed=seed,
                result=[a.name for a in selected],
            )
            return selected

        # Deterministic selection (matches service algorithm)
        seed_bytes = petition_id.bytes
        if seed is not None:
            seed_bytes += seed.to_bytes(8, byteorder="big", signed=True)

        hash_bytes = hashlib.sha256(seed_bytes).digest()

        scored_archons: list[tuple[bytes, FateArchon]] = []
        for archon in self._archons.values():
            combined = hash_bytes + archon.id.bytes
            score = hashlib.sha256(combined).digest()
            scored_archons.append((score, archon))

        scored_archons.sort(key=lambda x: x[0])

        selected = tuple(a for _, a in scored_archons[: self.REQUIRED_ARCHON_COUNT])

        self._record_operation(
            "select_archons",
            petition_id=petition_id,
            seed=seed,
            result=[a.name for a in selected],
        )

        return (selected[0], selected[1], selected[2])

    def get_archon_by_id(self, archon_id: UUID) -> FateArchon | None:
        """Retrieve a Fate Archon by ID."""
        self._record_operation("get_archon_by_id", archon_id=archon_id)
        return self._archons.get(archon_id)

    def get_archon_by_name(self, name: str) -> FateArchon | None:
        """Retrieve a Fate Archon by name."""
        self._record_operation("get_archon_by_name", archon_name=name)
        return self._by_name.get(name)

    def list_all_archons(self) -> list[FateArchon]:
        """List all Fate Archons in the pool."""
        self._record_operation("list_all_archons")
        return list(self._archons.values())

    def get_pool_size(self) -> int:
        """Get the number of Archons in the pool."""
        self._record_operation("get_pool_size")
        return len(self._archons)

    def is_valid_archon_id(self, archon_id: UUID) -> bool:
        """Check if an ID belongs to a valid Fate Archon."""
        self._record_operation("is_valid_archon_id", archon_id=archon_id)
        return archon_id in self._archons

    # ═══════════════════════════════════════════════════════════════════════════
    # TESTING HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def add_archon(self, archon: FateArchon) -> None:
        """Add an Archon to the pool.

        Args:
            archon: FateArchon to add.
        """
        self._archons[archon.id] = archon
        self._by_name[archon.name] = archon

    def remove_archon(self, archon_id: UUID) -> bool:
        """Remove an Archon from the pool.

        Args:
            archon_id: UUID of Archon to remove.

        Returns:
            True if removed, False if not found.
        """
        archon = self._archons.pop(archon_id, None)
        if archon:
            self._by_name.pop(archon.name, None)
            return True
        return False

    def set_fixed_selection(
        self,
        archons: tuple[FateArchon, FateArchon, FateArchon] | None,
    ) -> None:
        """Set a fixed selection to return from select_archons.

        Args:
            archons: Tuple of exactly 3 Archons to always return,
                     or None to use deterministic selection.
        """
        self._fixed_selection = archons

    def clear(self) -> None:
        """Clear all Archons and operations."""
        self._archons.clear()
        self._by_name.clear()
        self._operations.clear()
        self._fixed_selection = None

    def clear_operations(self) -> None:
        """Clear only operation history, preserve Archons."""
        self._operations.clear()

    def get_archon_count(self) -> int:
        """Get count of Archons in pool."""
        return len(self._archons)

    def get_operation_count(self) -> int:
        """Get total count of recorded operations."""
        return len(self._operations)

    def get_all_operations(self) -> list[ArchonPoolOperation]:
        """Get all recorded operations."""
        return list(self._operations)

    def get_operations_by_type(self, operation_type: str) -> list[ArchonPoolOperation]:
        """Get operations filtered by type.

        Args:
            operation_type: Type of operation to filter for.

        Returns:
            List of operations matching the type.
        """
        return [op for op in self._operations if op.operation == operation_type]

    def was_petition_selected(self, petition_id: UUID) -> bool:
        """Check if selection was made for a petition.

        Args:
            petition_id: UUID of petition to check.

        Returns:
            True if select_archons was called for this petition.
        """
        return any(
            op.operation == "select_archons" and op.petition_id == petition_id
            for op in self._operations
        )

    def get_selection_for_petition(self, petition_id: UUID) -> list[str] | None:
        """Get the names of Archons selected for a petition.

        Args:
            petition_id: UUID of petition.

        Returns:
            List of Archon names if found, None otherwise.
        """
        for op in self._operations:
            if op.operation == "select_archons" and op.petition_id == petition_id:
                return op.result
        return None


def create_test_archon(
    name: str,
    style: DeliberationStyle = DeliberationStyle.PRAGMATIC_MODERATOR,
    archon_id: UUID | None = None,
) -> FateArchon:
    """Factory function to create a test FateArchon.

    Args:
        name: Name for the test Archon.
        style: Deliberation style (default: PRAGMATIC_MODERATOR).
        archon_id: Optional UUID (generates one if not provided).

    Returns:
        FateArchon instance for testing.
    """
    return FateArchon(
        id=archon_id or uuid4(),
        name=name,
        title=f"Test Marquis of {name}",
        deliberation_style=style,
        system_prompt_template=f"You are {name}, a test Archon for deliberation.",
        backstory=f"Test backstory for {name}.",
    )
