"""UnwitnessedHaltRepository port (Story 3.9, Task 2).

Port interface for storing and retrieving unwitnessed halt records.
When a halt cannot be witnessed in the event store, we create an
UnwitnessedHaltRecord and persist it via this repository.

Constitutional Constraints:
- CT-13: Integrity over availability -> halt proceeds even if witnessing fails
- RT-2: Recovery mechanism requires unwitnessed halts to be tracked
- CT-11: Silent failure destroys legitimacy -> all failures must be recoverable
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.unwitnessed_halt import UnwitnessedHaltRecord


@runtime_checkable
class UnwitnessedHaltRepository(Protocol):
    """Repository for unwitnessed halt records.

    When event store write fails during halt, we still proceed with
    halt (CT-13) but create an UnwitnessedHaltRecord. This repository
    provides persistence and recovery access for these records.

    Constitutional Constraints:
    - CT-13: Integrity over availability -> recovery mechanism required
    - RT-2: All halts must be auditable, even unwitnessed ones
    - CT-11: Silent failure destroys legitimacy -> records enable reconciliation

    Implementation Notes:
    - Records should be stored in a separate, highly-available store
    - File-based or Redis-based implementations suitable for recovery
    - This repository is used during recovery ceremony to reconcile halts

    Example:
        >>> # Save unwitnessed halt during crisis
        >>> record = UnwitnessedHaltRecord(...)
        >>> await repository.save(record)
        >>>
        >>> # Later, during recovery
        >>> all_records = await repository.get_all()
        >>> for record in all_records:
        ...     # Reconcile into event store via ceremony
        ...     pass
    """

    async def save(self, record: "UnwitnessedHaltRecord") -> None:
        """Save an unwitnessed halt record.

        Persists the record for later recovery and reconciliation.
        This method should be highly reliable - if this fails too,
        we log at CRITICAL level as last resort.

        Args:
            record: The unwitnessed halt record to save.

        Note:
            Implementations should use synchronous writes (fsync) or
            other durable storage mechanisms to ensure the record
            survives system restart.
        """
        ...

    async def get_all(self) -> list["UnwitnessedHaltRecord"]:
        """Get all unwitnessed halt records.

        Used during recovery to enumerate all halts that need
        to be reconciled into the event store.

        Returns:
            List of all unwitnessed halt records, ordered by
            fallback_timestamp ascending.

        Note:
            Records are returned in order for sequential reconciliation.
        """
        ...

    async def get_by_id(self, halt_id: UUID) -> "UnwitnessedHaltRecord | None":
        """Get a specific record by halt ID.

        Args:
            halt_id: UUID of the halt record to retrieve.

        Returns:
            The record if found, None otherwise.
        """
        ...
