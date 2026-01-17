"""Exit result domain model for consent-based governance.

Story: consent-gov-7.1: Exit Request Processing

This module defines the ExitResult frozen dataclass for capturing
the outcome of exit processing.

Design Principles:
- Immutable value object (frozen dataclass)
- Tracks round-trips to enforce NFR-EXIT-01
- Captures metrics for auditing (tasks affected, obligations released)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.exit.exit_status import ExitStatus


# Maximum allowed round-trips per NFR-EXIT-01
MAX_ROUND_TRIPS = 2


@dataclass(frozen=True)
class ExitResult:
    """Result of exit processing.

    Per FR43: System can process exit request.
    Per NFR-EXIT-01: Exit completes in ≤2 message round-trips.

    This model captures the outcome of exit processing, including
    metrics for auditing purposes.

    Round-Trip Enforcement:
    - round_trips must be ≤2 (enforced in __post_init__)
    - Violation raises ValueError (code smell detector)

    Attributes:
        request_id: ID of the original exit request.
        cluster_id: ID of the Cluster that exited.
        status: Current status of the exit (should be COMPLETED).
        initiated_at: When exit was initiated.
        completed_at: When exit was completed (None if not complete).
        tasks_affected: Number of tasks affected by exit.
        obligations_released: Number of obligations released.
        round_trips: Number of round-trips used (must be ≤2).
    """

    request_id: UUID
    cluster_id: UUID
    status: ExitStatus
    initiated_at: datetime
    completed_at: datetime | None
    tasks_affected: int
    obligations_released: int
    round_trips: int

    def __post_init__(self) -> None:
        """Validate all ExitResult fields."""
        self._validate_request_id()
        self._validate_cluster_id()
        self._validate_status()
        self._validate_timestamps()
        self._validate_counts()
        self._validate_round_trips()

    def _validate_request_id(self) -> None:
        """Validate request_id is UUID."""
        if not isinstance(self.request_id, UUID):
            raise ValueError(
                f"ExitResult validation failed - "
                f"request_id must be UUID, got {type(self.request_id).__name__}"
            )

    def _validate_cluster_id(self) -> None:
        """Validate cluster_id is UUID."""
        if not isinstance(self.cluster_id, UUID):
            raise ValueError(
                f"ExitResult validation failed - "
                f"cluster_id must be UUID, got {type(self.cluster_id).__name__}"
            )

    def _validate_status(self) -> None:
        """Validate status is ExitStatus."""
        if not isinstance(self.status, ExitStatus):
            raise ValueError(
                f"ExitResult validation failed - "
                f"status must be ExitStatus, got {type(self.status).__name__}"
            )

    def _validate_timestamps(self) -> None:
        """Validate timestamps."""
        if not isinstance(self.initiated_at, datetime):
            raise ValueError(
                f"ExitResult validation failed - "
                f"initiated_at must be datetime, got {type(self.initiated_at).__name__}"
            )
        if self.completed_at is not None and not isinstance(self.completed_at, datetime):
            raise ValueError(
                f"ExitResult validation failed - "
                f"completed_at must be datetime or None, got {type(self.completed_at).__name__}"
            )
        # If completed, completion must be after initiation
        if self.completed_at is not None and self.completed_at < self.initiated_at:
            raise ValueError(
                "ExitResult validation failed - "
                "completed_at cannot be before initiated_at"
            )

    def _validate_counts(self) -> None:
        """Validate count fields are non-negative."""
        if not isinstance(self.tasks_affected, int) or self.tasks_affected < 0:
            raise ValueError(
                "ExitResult validation failed - "
                "tasks_affected must be non-negative integer"
            )
        if not isinstance(self.obligations_released, int) or self.obligations_released < 0:
            raise ValueError(
                "ExitResult validation failed - "
                "obligations_released must be non-negative integer"
            )

    def _validate_round_trips(self) -> None:
        """Validate round_trips is within allowed limit.

        Per NFR-EXIT-01: Exit completes in ≤2 message round-trips.
        If this validation fails, it indicates a code smell - the
        exit implementation is violating the constitutional requirement.
        """
        if not isinstance(self.round_trips, int) or self.round_trips < 0:
            raise ValueError(
                "ExitResult validation failed - "
                "round_trips must be non-negative integer"
            )
        if self.round_trips > MAX_ROUND_TRIPS:
            raise ValueError(
                f"NFR-EXIT-01 VIOLATION: Exit exceeded {MAX_ROUND_TRIPS} round-trips. "
                f"Actual: {self.round_trips}. Exit must complete in ≤2 round-trips."
            )

    @property
    def is_complete(self) -> bool:
        """Check if exit is complete."""
        return self.status == ExitStatus.COMPLETED

    @property
    def duration_ms(self) -> float | None:
        """Get exit duration in milliseconds.

        Returns None if exit is not complete.
        """
        if self.completed_at is None:
            return None
        delta = self.completed_at - self.initiated_at
        return delta.total_seconds() * 1000
