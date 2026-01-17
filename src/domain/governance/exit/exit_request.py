"""Exit request domain model for consent-based governance.

Story: consent-gov-7.1: Exit Request Processing

This module defines the ExitRequest frozen dataclass for capturing
exit request information at the time of initiation.

Design Principles:
- Immutable value object (frozen dataclass)
- Captures point-in-time snapshot of Cluster's tasks
- No reason required (unconditional right)
- No confirmation required
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ExitRequest:
    """Request to exit the system.

    Per FR42: Cluster can initiate exit request.
    Per Golden Rule: Exit is an unconditional right.

    This model captures the exit request at the moment it's made,
    including a snapshot of the Cluster's active tasks at that time.

    Immutability Guarantee:
    - Frozen dataclass ensures request cannot be modified
    - tasks_at_request is a tuple (immutable sequence)

    No Justification Required:
    - There is no 'reason' field
    - Exit does not require explanation
    - Consent can be withdrawn at any time

    Attributes:
        request_id: Unique identifier for this exit request.
        cluster_id: ID of the Cluster requesting exit.
        requested_at: Timestamp when exit was requested.
        tasks_at_request: Tuple of task IDs active at time of request.
    """

    request_id: UUID
    cluster_id: UUID
    requested_at: datetime
    tasks_at_request: tuple[UUID, ...]  # Immutable tuple, not list

    def __post_init__(self) -> None:
        """Validate all ExitRequest fields."""
        self._validate_request_id()
        self._validate_cluster_id()
        self._validate_requested_at()
        self._validate_tasks_at_request()

    def _validate_request_id(self) -> None:
        """Validate request_id is UUID."""
        if not isinstance(self.request_id, UUID):
            raise ValueError(
                f"ExitRequest validation failed - "
                f"request_id must be UUID, got {type(self.request_id).__name__}"
            )

    def _validate_cluster_id(self) -> None:
        """Validate cluster_id is UUID."""
        if not isinstance(self.cluster_id, UUID):
            raise ValueError(
                f"ExitRequest validation failed - "
                f"cluster_id must be UUID, got {type(self.cluster_id).__name__}"
            )

    def _validate_requested_at(self) -> None:
        """Validate requested_at is datetime."""
        if not isinstance(self.requested_at, datetime):
            raise ValueError(
                f"ExitRequest validation failed - "
                f"requested_at must be datetime, got {type(self.requested_at).__name__}"
            )

    def _validate_tasks_at_request(self) -> None:
        """Validate tasks_at_request is tuple of UUIDs."""
        if not isinstance(self.tasks_at_request, tuple):
            raise ValueError(
                f"ExitRequest validation failed - "
                f"tasks_at_request must be tuple, got {type(self.tasks_at_request).__name__}"
            )
        for i, task_id in enumerate(self.tasks_at_request):
            if not isinstance(task_id, UUID):
                raise ValueError(
                    f"ExitRequest validation failed - "
                    f"tasks_at_request[{i}] must be UUID, got {type(task_id).__name__}"
                )

    @property
    def active_task_count(self) -> int:
        """Get count of active tasks at time of request."""
        return len(self.tasks_at_request)

    @property
    def has_active_tasks(self) -> bool:
        """Check if Cluster had active tasks at time of request."""
        return len(self.tasks_at_request) > 0
