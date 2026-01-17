"""Branch Action Tracker Port (Epic 8, Story 8.4).

This module defines the protocol and domain models for tracking branch actions
per Archon and motion to enable role collapse detection.

Per Government PRD FR-GOV-23: No role may be collapsed.
Per PRD §2.1: No entity may define intent, execute it, AND judge it.

This port is the foundation for detecting when an Archon attempts to act
in multiple conflicting branches on the same motion.

HARDENING-1: All timestamps must be provided via TimeAuthorityProtocol injection.
Factory methods require explicit timestamp parameters - no datetime.now() calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class GovernanceBranch(Enum):
    """Branches of the governance system.

    Per Government PRD §3: Each branch has specific responsibilities.
    """

    LEGISLATIVE = "legislative"  # King introduces motions
    DELIBERATIVE = "deliberative"  # Conclave deliberates
    EXECUTIVE = "executive"  # President plans execution
    ADMINISTRATIVE = "administrative"  # Duke/Earl execute
    JUDICIAL = "judicial"  # Prince judges compliance
    WITNESS = "witness"  # Knight witnesses
    ADVISORY = "advisory"  # Marquis advises (non-blocking)


class GovernanceAction(Enum):
    """Actions that can be performed in the governance system.

    Per Government PRD §4.
    """

    INTRODUCE_MOTION = "introduce_motion"
    DELIBERATE = "deliberate"
    RATIFY = "ratify"
    DEFINE_EXECUTION = "define_execution"
    EXECUTE = "execute"
    JUDGE = "judge"
    ADVISE = "advise"
    WITNESS = "witness"


# Map actions to their primary branch
ACTION_BRANCH_MAP: dict[GovernanceAction, GovernanceBranch] = {
    GovernanceAction.INTRODUCE_MOTION: GovernanceBranch.LEGISLATIVE,
    GovernanceAction.DELIBERATE: GovernanceBranch.DELIBERATIVE,
    GovernanceAction.RATIFY: GovernanceBranch.DELIBERATIVE,
    GovernanceAction.DEFINE_EXECUTION: GovernanceBranch.EXECUTIVE,
    GovernanceAction.EXECUTE: GovernanceBranch.ADMINISTRATIVE,
    GovernanceAction.JUDGE: GovernanceBranch.JUDICIAL,
    GovernanceAction.ADVISE: GovernanceBranch.ADVISORY,
    GovernanceAction.WITNESS: GovernanceBranch.WITNESS,
}


def get_branch_for_action(action: GovernanceAction) -> GovernanceBranch:
    """Get the governance branch for an action.

    Args:
        action: The governance action

    Returns:
        The branch responsible for this action
    """
    return ACTION_BRANCH_MAP[action]


@dataclass(frozen=True)
class BranchAction:
    """Record of an Archon acting on a motion in a specific branch.

    Per AC3: Each action is recorded with archon_id, motion_id, branch,
    action_type, and timestamp.

    This is an immutable record that forms the basis for role collapse detection.
    """

    action_id: UUID
    archon_id: str
    motion_id: UUID
    branch: GovernanceBranch
    action_type: GovernanceAction
    acted_at: datetime

    @classmethod
    def create(
        cls,
        archon_id: str,
        motion_id: UUID,
        branch: GovernanceBranch,
        action_type: GovernanceAction,
        timestamp: datetime,
    ) -> "BranchAction":
        """Create a new branch action record.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            archon_id: The Archon who performed the action
            motion_id: The motion being acted upon
            branch: The governance branch
            action_type: The type of action performed
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New immutable BranchAction
        """
        return cls(
            action_id=uuid4(),
            archon_id=archon_id,
            motion_id=motion_id,
            branch=branch,
            action_type=action_type,
            acted_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action_id": str(self.action_id),
            "archon_id": self.archon_id,
            "motion_id": str(self.motion_id),
            "branch": self.branch.value,
            "action_type": self.action_type.value,
            "acted_at": self.acted_at.isoformat(),
        }


@dataclass(frozen=True)
class ArchonBranchHistory:
    """Summary of branches an Archon has acted in for a specific motion.

    Per AC1: Used to detect role collapse by tracking which branches
    an Archon has already participated in.
    """

    archon_id: str
    motion_id: UUID
    branches: tuple[GovernanceBranch, ...]
    actions: tuple[BranchAction, ...]
    first_action_at: datetime
    last_action_at: datetime

    @classmethod
    def create(
        cls,
        archon_id: str,
        motion_id: UUID,
        actions: list[BranchAction],
        timestamp: datetime,
    ) -> "ArchonBranchHistory":
        """Create an Archon branch history from actions.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            archon_id: The Archon
            motion_id: The motion
            actions: List of actions taken
            timestamp: Current time from TimeAuthorityProtocol (used for empty actions)

        Returns:
            New ArchonBranchHistory summary
        """
        if not actions:
            return cls(
                archon_id=archon_id,
                motion_id=motion_id,
                branches=(),
                actions=(),
                first_action_at=timestamp,
                last_action_at=timestamp,
            )

        # Extract unique branches
        branches = tuple(sorted(set(a.branch for a in actions), key=lambda b: b.value))

        # Sort actions by timestamp
        sorted_actions = tuple(sorted(actions, key=lambda a: a.acted_at))

        return cls(
            archon_id=archon_id,
            motion_id=motion_id,
            branches=branches,
            actions=sorted_actions,
            first_action_at=sorted_actions[0].acted_at,
            last_action_at=sorted_actions[-1].acted_at,
        )

    @property
    def branch_count(self) -> int:
        """Number of unique branches acted in."""
        return len(self.branches)

    def has_acted_in_branch(self, branch: GovernanceBranch) -> bool:
        """Check if Archon has acted in a specific branch.

        Args:
            branch: The branch to check

        Returns:
            True if Archon has acted in this branch
        """
        return branch in self.branches

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "archon_id": self.archon_id,
            "motion_id": str(self.motion_id),
            "branches": [b.value for b in self.branches],
            "action_count": len(self.actions),
            "first_action_at": self.first_action_at.isoformat(),
            "last_action_at": self.last_action_at.isoformat(),
        }


@dataclass
class RecordActionRequest:
    """Request to record a branch action."""

    archon_id: str
    motion_id: UUID
    action_type: GovernanceAction
    branch: GovernanceBranch | None = None  # If None, derived from action_type


@dataclass
class RecordActionResult:
    """Result of recording a branch action."""

    success: bool
    action: BranchAction | None = None
    error: str | None = None


class BranchActionTrackerProtocol(ABC):
    """Protocol for tracking branch actions.

    This port provides the foundation for role collapse detection
    by tracking which branches each Archon has acted in per motion.

    Per FR-GOV-23: No role may be collapsed.
    Per PRD §2.1: No entity may define intent, execute it, AND judge it.

    Implementations should:
    1. Record each branch action with full context
    2. Provide efficient lookup of Archon branches per motion
    3. Support querying action history for audit trails
    """

    @abstractmethod
    async def record_branch_action(
        self,
        request: RecordActionRequest,
    ) -> RecordActionResult:
        """Record that an Archon performed an action in a branch.

        Per AC3: Records archon_id, motion_id, branch, action_type, timestamp.

        Args:
            request: Request with action details

        Returns:
            RecordActionResult with success status and recorded action
        """
        ...

    @abstractmethod
    async def get_archon_branches(
        self,
        archon_id: str,
        motion_id: UUID,
    ) -> list[GovernanceBranch]:
        """Get the branches an Archon has acted in for a motion.

        This is the primary method for role collapse detection.

        Args:
            archon_id: The Archon to check
            motion_id: The motion to check

        Returns:
            List of branches the Archon has acted in
        """
        ...

    @abstractmethod
    async def get_archon_history(
        self,
        archon_id: str,
        motion_id: UUID,
    ) -> ArchonBranchHistory | None:
        """Get the full action history for an Archon on a motion.

        Provides detailed history for audit trails and violation reports.

        Args:
            archon_id: The Archon to check
            motion_id: The motion to check

        Returns:
            ArchonBranchHistory if any actions exist, None otherwise
        """
        ...

    @abstractmethod
    async def get_motion_actions(
        self,
        motion_id: UUID,
    ) -> list[BranchAction]:
        """Get all branch actions for a motion.

        Args:
            motion_id: The motion to query

        Returns:
            List of all actions on this motion
        """
        ...

    @abstractmethod
    async def get_branch_actors(
        self,
        motion_id: UUID,
        branch: GovernanceBranch,
    ) -> list[str]:
        """Get all Archons who have acted in a branch for a motion.

        Useful for identifying who has participated in each branch.

        Args:
            motion_id: The motion to query
            branch: The branch to check

        Returns:
            List of archon_ids who have acted in this branch
        """
        ...

    @abstractmethod
    async def has_acted_in_branch(
        self,
        archon_id: str,
        motion_id: UUID,
        branch: GovernanceBranch,
    ) -> bool:
        """Check if an Archon has acted in a specific branch.

        Efficient single-check for role collapse detection.

        Args:
            archon_id: The Archon to check
            motion_id: The motion to check
            branch: The branch to check

        Returns:
            True if Archon has acted in this branch
        """
        ...

    @abstractmethod
    async def clear_motion_actions(
        self,
        motion_id: UUID,
    ) -> int:
        """Clear all actions for a motion.

        Used when a motion is terminated or for testing.

        Args:
            motion_id: The motion to clear

        Returns:
            Number of actions cleared
        """
        ...
