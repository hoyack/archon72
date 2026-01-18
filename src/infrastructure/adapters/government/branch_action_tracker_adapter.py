"""Branch Action Tracker Adapter (Epic 8, Story 8.4).

This adapter implements the BranchActionTrackerProtocol for tracking
branch actions to enable role collapse detection.

Per Government PRD FR-GOV-23: No role may be collapsed.
Per PRD §2.1: No entity may define intent, execute it, AND judge it.

Per HARDENING-1: Uses TimeAuthorityProtocol for all timestamps.
"""

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from structlog import get_logger

from src.application.ports.branch_action_tracker import (
    ArchonBranchHistory,
    BranchAction,
    BranchActionTrackerProtocol,
    GovernanceBranch,
    RecordActionRequest,
    RecordActionResult,
    get_branch_for_action,
)
from src.application.ports.time_authority import TimeAuthorityProtocol

logger = get_logger(__name__)


class BranchActionTrackerAdapter(BranchActionTrackerProtocol):
    """In-memory implementation of branch action tracking.

    This adapter tracks all branch actions per motion to enable
    role collapse detection.

    Per AC3: Records archon_id, motion_id, branch, action_type, timestamp.
    Per HARDENING-1: Timestamps provided via TimeAuthorityProtocol.

    Note: This is an in-memory implementation suitable for testing and
    single-process deployments. For production, this should be backed
    by a persistent store.
    """

    def __init__(
        self,
        time_authority: TimeAuthorityProtocol | None = None,
    ) -> None:
        """Initialize the branch action tracker.

        Per HARDENING-1: TimeAuthorityProtocol injection for timestamps.

        Args:
            time_authority: Time authority for timestamps (defaults to system time)
        """
        # Primary storage: motion_id -> list of BranchAction
        self._actions_by_motion: dict[UUID, list[BranchAction]] = defaultdict(list)

        # Index: (archon_id, motion_id) -> list of branches
        self._branches_by_archon_motion: dict[
            tuple[str, UUID], list[GovernanceBranch]
        ] = defaultdict(list)

        # Per HARDENING-1: Use injected time authority or fallback
        self._time_authority = time_authority

        logger.info("branch_action_tracker_initialized")

    def _get_current_time(self) -> datetime:
        """Get current time from time authority or fallback.

        Per HARDENING-1: Prefer TimeAuthorityProtocol.now()
        """
        if self._time_authority is not None:
            return self._time_authority.now()
        # Fallback for backwards compatibility during tests
        return datetime.now(timezone.utc)

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
        try:
            # Derive branch from action if not provided
            branch = request.branch
            if branch is None:
                branch = get_branch_for_action(request.action_type)

            # Create the action record with timestamp from time authority
            action = BranchAction.create(
                archon_id=request.archon_id,
                motion_id=request.motion_id,
                branch=branch,
                action_type=request.action_type,
                timestamp=self._get_current_time(),
            )

            # Store in primary storage
            self._actions_by_motion[request.motion_id].append(action)

            # Update index
            key = (request.archon_id, request.motion_id)
            if branch not in self._branches_by_archon_motion[key]:
                self._branches_by_archon_motion[key].append(branch)

            logger.info(
                "branch_action_recorded",
                action_id=str(action.action_id),
                archon_id=request.archon_id,
                motion_id=str(request.motion_id),
                branch=branch.value,
                action_type=request.action_type.value,
            )

            return RecordActionResult(success=True, action=action)

        except Exception as e:
            logger.error(
                "branch_action_record_failed",
                archon_id=request.archon_id,
                motion_id=str(request.motion_id),
                error=str(e),
            )
            return RecordActionResult(success=False, error=str(e))

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
        key = (archon_id, motion_id)
        return list(self._branches_by_archon_motion.get(key, []))

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
        # Get all actions for this motion
        all_actions = self._actions_by_motion.get(motion_id, [])

        # Filter to this Archon
        archon_actions = [a for a in all_actions if a.archon_id == archon_id]

        if not archon_actions:
            return None

        return ArchonBranchHistory.create(
            archon_id=archon_id,
            motion_id=motion_id,
            actions=archon_actions,
            timestamp=self._get_current_time(),  # Per HARDENING-1
        )

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
        return list(self._actions_by_motion.get(motion_id, []))

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
        all_actions = self._actions_by_motion.get(motion_id, [])
        actors = set(a.archon_id for a in all_actions if a.branch == branch)
        return list(actors)

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
        key = (archon_id, motion_id)
        branches = self._branches_by_archon_motion.get(key, [])
        return branch in branches

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
        # Count actions to clear
        count = len(self._actions_by_motion.get(motion_id, []))

        # Clear primary storage
        if motion_id in self._actions_by_motion:
            del self._actions_by_motion[motion_id]

        # Clear from index
        keys_to_remove = [
            key for key in self._branches_by_archon_motion if key[1] == motion_id
        ]
        for key in keys_to_remove:
            del self._branches_by_archon_motion[key]

        logger.info(
            "motion_actions_cleared",
            motion_id=str(motion_id),
            actions_cleared=count,
        )

        return count

    def get_statistics(self) -> dict:
        """Get statistics about tracked actions.

        Returns:
            Dictionary with tracking statistics
        """
        total_actions = sum(
            len(actions) for actions in self._actions_by_motion.values()
        )
        total_motions = len(self._actions_by_motion)
        unique_archons = len(set(key[0] for key in self._branches_by_archon_motion))

        return {
            "total_actions": total_actions,
            "total_motions": total_motions,
            "unique_archons": unique_archons,
        }


def create_branch_action_tracker() -> BranchActionTrackerProtocol:
    """Factory function to create a BranchActionTrackerProtocol instance.

    Returns:
        Configured BranchActionTrackerProtocol instance
    """
    return BranchActionTrackerAdapter()
