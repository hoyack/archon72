"""Preservation result domain model for consent-based governance.

Story: consent-gov-7.3: Contribution Preservation

Defines the PreservationResult frozen dataclass for capturing
the result of preserving a Cluster's contribution history on exit.

Constitutional Truths Honored:
- FR45: Contribution history preserved on exit
- NFR-INT-02: Public data only, no PII
- Ledger immutability: Contributions cannot be deleted

Key Design Principles:
1. Immutable value object (frozen dataclass)
2. Reports what was preserved, not what was deleted
3. No scrubbing methods exist
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PreservationResult:
    """Result of preserving contributions on exit.

    Per FR45: System can preserve Cluster's contribution history on exit.
    Per AC5: Event `custodial.contributions.preserved` emitted.

    This captures the result of the preservation process:
    - Which Cluster's contributions were preserved
    - How many contributions were preserved
    - Which task IDs had contributions preserved
    - When preservation completed

    STRUCTURAL ABSENCE (immutability enforcement):
        The following fields DO NOT EXIST:
        - contributions_deleted: int  # No deletion allowed
        - contributions_scrubbed: int  # No scrubbing allowed
        - contributions_modified: int  # No modification allowed

        These fields are intentionally absent. Adding them would
        violate ledger immutability principles.

    Attributes:
        cluster_id: ID of the Cluster whose contributions were preserved.
        contributions_preserved: Number of contributions preserved.
        task_ids: List of task IDs with preserved contributions.
        preserved_at: When preservation completed.
    """

    cluster_id: UUID
    contributions_preserved: int
    task_ids: tuple[UUID, ...]  # Immutable tuple
    preserved_at: datetime

    # ========================================================================
    # STRUCTURAL ABSENCE - The following fields DO NOT EXIST
    # ========================================================================
    #
    # These fields are INTENTIONALLY absent (immutability enforcement):
    #
    # contributions_deleted: int
    #     Would track deletions - NO DELETION ALLOWED
    #
    # contributions_scrubbed: int
    #     Would track scrubbing - NO SCRUBBING ALLOWED
    #
    # contributions_modified: int
    #     Would track modifications - NO MODIFICATION ALLOWED
    #
    # If you see these fields being added in the future, this is a
    # CONSTITUTIONAL VIOLATION. Knight should observe and record.
    # ========================================================================

    def __post_init__(self) -> None:
        """Validate preservation result fields."""
        self._validate_cluster_id()
        self._validate_contributions_preserved()
        self._validate_task_ids()
        self._validate_preserved_at()

    def _validate_cluster_id(self) -> None:
        """Validate cluster_id is UUID."""
        if not isinstance(self.cluster_id, UUID):
            raise ValueError(
                f"PreservationResult validation failed - "
                f"cluster_id must be UUID, got {type(self.cluster_id).__name__}"
            )

    def _validate_contributions_preserved(self) -> None:
        """Validate contributions_preserved is non-negative int."""
        if not isinstance(self.contributions_preserved, int):
            raise ValueError(
                f"PreservationResult validation failed - "
                f"contributions_preserved must be int, got {type(self.contributions_preserved).__name__}"
            )
        if self.contributions_preserved < 0:
            raise ValueError(
                "PreservationResult validation failed - "
                "contributions_preserved must be non-negative"
            )

    def _validate_task_ids(self) -> None:
        """Validate task_ids is tuple of UUIDs."""
        if not isinstance(self.task_ids, tuple):
            raise ValueError(
                f"PreservationResult validation failed - "
                f"task_ids must be tuple, got {type(self.task_ids).__name__}"
            )
        for i, task_id in enumerate(self.task_ids):
            if not isinstance(task_id, UUID):
                raise ValueError(
                    f"PreservationResult validation failed - "
                    f"task_ids[{i}] must be UUID, got {type(task_id).__name__}"
                )

    def _validate_preserved_at(self) -> None:
        """Validate preserved_at is datetime."""
        if not isinstance(self.preserved_at, datetime):
            raise ValueError(
                f"PreservationResult validation failed - "
                f"preserved_at must be datetime, got {type(self.preserved_at).__name__}"
            )

    @property
    def has_contributions(self) -> bool:
        """Check if any contributions were preserved."""
        return self.contributions_preserved > 0

    @property
    def unique_tasks(self) -> int:
        """Count of unique tasks with preserved contributions."""
        return len(set(self.task_ids))
