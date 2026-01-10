"""UnwitnessedHaltRepositoryStub (Story 3.9, Task 3).

In-memory stub implementation of UnwitnessedHaltRepository for testing.
Stores records in a dictionary keyed by halt_id.
"""

from __future__ import annotations

from uuid import UUID

from src.application.ports.unwitnessed_halt_repository import UnwitnessedHaltRepository
from src.domain.models.unwitnessed_halt import UnwitnessedHaltRecord


class UnwitnessedHaltRepositoryStub(UnwitnessedHaltRepository):
    """In-memory stub for UnwitnessedHaltRepository.

    Stores records in memory for testing. Provides reset() method
    to clear state between tests.
    """

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._records: dict[UUID, UnwitnessedHaltRecord] = {}

    async def save(self, record: UnwitnessedHaltRecord) -> None:
        """Save an unwitnessed halt record.

        Args:
            record: The record to save.
        """
        self._records[record.halt_id] = record

    async def get_all(self) -> list[UnwitnessedHaltRecord]:
        """Get all unwitnessed halt records.

        Returns:
            List of all records, ordered by fallback_timestamp.
        """
        return sorted(
            self._records.values(),
            key=lambda r: r.fallback_timestamp,
        )

    async def get_by_id(self, halt_id: UUID) -> UnwitnessedHaltRecord | None:
        """Get a specific record by halt ID.

        Args:
            halt_id: UUID of the record to retrieve.

        Returns:
            The record if found, None otherwise.
        """
        return self._records.get(halt_id)

    def reset(self) -> None:
        """Clear all records (for testing)."""
        self._records.clear()
