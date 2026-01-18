"""Port for cessation record operations.

Story: consent-gov-8.2: Cessation Record Creation

This port defines the interface for cessation record persistence.
Implementation is APPEND-ONLY - no modify/delete methods exist (AC7).

Constitutional Context:
- FR48: System can create immutable Cessation Record on cessation
- NFR-REL-05: Cessation Record creation is atomic
"""

from typing import Protocol

from src.domain.governance.cessation.cessation_record import CessationRecord


class CessationRecordPort(Protocol):
    """Port for cessation record persistence.

    NO modify/delete methods (immutable record per AC7).

    Implementation must ensure:
    - Atomic creation (NFR-REL-05)
    - Only one record allowed
    - No modifications after creation
    """

    async def create_record_atomic(
        self,
        record: CessationRecord,
    ) -> None:
        """Create cessation record atomically.

        All-or-nothing: either complete record is created or fails entirely.

        Args:
            record: The cessation record to create.

        Raises:
            CessationRecordAlreadyExistsError: If record already exists.
            CessationRecordCreationError: If creation fails.
        """
        ...

    async def get_record(self) -> CessationRecord | None:
        """Get cessation record if exists.

        Returns:
            The cessation record if exists, None otherwise.
        """
        ...

    # Intentionally NOT defined:
    # - update_record() - Records are immutable
    # - delete_record() - Records are permanent
    # - modify_record() - Records cannot be changed
