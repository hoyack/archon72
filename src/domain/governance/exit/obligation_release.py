"""Obligation release domain models.

Story: consent-gov-7.2: Obligation Release

Defines domain models for tracking obligation releases during exit:
- ObligationRelease: Individual task release record
- ReleaseResult: Aggregate result of releasing all obligations

Constitutional Truths Honored:
- Golden Rule: No penalties on exit
- FR44: All obligations released
- Dignity preservation: Work is acknowledged
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.exit.release_type import ReleaseType
from src.domain.governance.task.task_state import TaskStatus


@dataclass(frozen=True)
class ObligationRelease:
    """Record of a single obligation release during exit.

    Per FR44: System can release Cluster from all obligations on exit.

    This is an immutable record capturing:
    - Which task was released
    - What state it was in
    - How it was released (nullified vs released)
    - Whether work was preserved

    Attributes:
        release_id: Unique identifier for this release record.
        cluster_id: ID of the Cluster whose obligation is released.
        task_id: ID of the task being released.
        previous_state: Task state before release.
        release_type: How the task was released (nullified or released).
        released_at: When the release occurred.
        work_preserved: Whether Cluster's work is preserved (post-consent only).
    """

    release_id: UUID
    cluster_id: UUID
    task_id: UUID
    previous_state: TaskStatus
    release_type: ReleaseType
    released_at: datetime
    work_preserved: bool

    def __post_init__(self) -> None:
        """Validate obligation release fields."""
        # Work preservation only applies to post-consent releases
        if self.release_type == ReleaseType.NULLIFIED_ON_EXIT and self.work_preserved:
            # Cannot preserve work that never existed
            raise ValueError(
                "work_preserved must be False for NULLIFIED_ON_EXIT releases"
            )


@dataclass(frozen=True)
class ReleaseResult:
    """Result of releasing all obligations for a Cluster.

    Per FR44: System can release Cluster from all obligations on exit.
    Per Golden Rule: No penalties applied.

    This captures the aggregate result of the obligation release process.

    Attributes:
        cluster_id: ID of the Cluster whose obligations were released.
        nullified_count: Number of pre-consent tasks nullified.
        released_count: Number of post-consent tasks released.
        pending_cancelled: Number of pending requests cancelled.
        total_obligations: Total obligations processed.
        released_at: When the release completed.

    STRUCTURAL ABSENCE (Golden Rule enforcement):
        The following fields do NOT exist and CANNOT be added:
        - penalty_applied: bool  # No penalties
        - reputation_impact: int  # No reputation system
        - standing_reduction: float  # No standing system
        - early_exit_mark: bool  # No early exit marking

        These fields are intentionally absent. Adding them would
        violate the Golden Rule (refusal is penalty-free).
    """

    cluster_id: UUID
    nullified_count: int
    released_count: int
    pending_cancelled: int
    total_obligations: int
    released_at: datetime

    # ========================================================================
    # STRUCTURAL ABSENCE - The following fields DO NOT EXIST
    # ========================================================================
    #
    # These fields are INTENTIONALLY absent (Golden Rule enforcement):
    #
    # penalty_applied: bool
    #     Would track if penalty was applied - VIOLATES Golden Rule
    #
    # reputation_impact: int
    #     Would track reputation change - NO REPUTATION SYSTEM EXISTS
    #
    # standing_reduction: float
    #     Would track standing change - NO STANDING SYSTEM EXISTS
    #
    # early_exit_mark: bool
    #     Would mark early exit - VIOLATES Golden Rule
    #
    # If you see these fields being added in the future, this is a
    # CONSTITUTIONAL VIOLATION. Knight should observe and record.
    # ========================================================================

    def __post_init__(self) -> None:
        """Validate release result fields."""
        # Counts must be non-negative
        if self.nullified_count < 0:
            raise ValueError("nullified_count must be non-negative")
        if self.released_count < 0:
            raise ValueError("released_count must be non-negative")
        if self.pending_cancelled < 0:
            raise ValueError("pending_cancelled must be non-negative")
        if self.total_obligations < 0:
            raise ValueError("total_obligations must be non-negative")

        # Total must match sum
        if self.total_obligations != self.nullified_count + self.released_count:
            raise ValueError(
                f"total_obligations ({self.total_obligations}) must equal "
                f"nullified_count ({self.nullified_count}) + "
                f"released_count ({self.released_count})"
            )
