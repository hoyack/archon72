"""RollbackCoordinator port for rollback operations (Story 3.10, Task 7).

This module defines the port interface for coordinating rollback operations
to checkpoint anchors (FR143).

Constitutional Constraints:
- FR143: Rollback to checkpoint for infrastructure recovery
- FR143: Rollback is logged, does not undo canonical events
- CT-11: Rollback must be witnessed
- CT-13: Integrity outranks availability - halt required
- PREVENT_DELETE: Events are never deleted, only marked orphaned

Usage:
    class RollbackCoordinatorService(RollbackCoordinator):
        async def query_checkpoints(self) -> list[Checkpoint]:
            ...

    # Type checking
    coordinator: RollbackCoordinator = RollbackCoordinatorService(...)
    checkpoints = await coordinator.query_checkpoints()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.rollback_completed import RollbackCompletedPayload
    from src.domain.events.rollback_target_selected import RollbackTargetSelectedPayload
    from src.domain.models.ceremony_evidence import CeremonyEvidence
    from src.domain.models.checkpoint import Checkpoint


@runtime_checkable
class RollbackCoordinator(Protocol):
    """Port for coordinating rollback operations (FR143).

    This port defines the contract for rollback coordination,
    including checkpoint query, target selection, and execution.

    Constitutional Constraints:
    - FR143: Rollback for infrastructure recovery, logged, no event deletion
    - CT-11: Rollback must be witnessed (events recorded)
    - CT-13: Halt required before rollback
    - PREVENT_DELETE: Events marked orphaned, not deleted

    The rollback process has two phases:
    1. Target Selection (AC2): Keepers select checkpoint, event recorded
    2. Execution (AC3): Rollback executed, events orphaned, event recorded
    """

    async def query_checkpoints(self) -> list["Checkpoint"]:
        """Query available checkpoints for rollback (AC1).

        Returns all available checkpoint anchors that can be used
        as rollback targets.

        Returns:
            List of Checkpoint objects ordered by event_sequence (ascending).
            Empty list if no checkpoints exist.
        """
        ...

    async def select_rollback_target(
        self,
        checkpoint_id: UUID,
        selecting_keepers: tuple[str, ...],
        reason: str,
    ) -> "RollbackTargetSelectedPayload":
        """Record Keeper selection of rollback target (AC2).

        Records the Keepers' selection of a checkpoint for rollback.
        Creates a RollbackTargetSelectedEvent for audit trail.

        Constitutional Constraint (CT-11):
        Selection must be witnessed and logged - no silent decisions.

        Args:
            checkpoint_id: UUID of the selected checkpoint.
            selecting_keepers: Tuple of Keeper IDs who selected this target.
            reason: Human-readable reason for rollback.

        Returns:
            RollbackTargetSelectedPayload for event creation.

        Raises:
            RollbackNotPermittedError: If system is not halted.
            CheckpointNotFoundError: If checkpoint doesn't exist.
            RollbackAlreadyInProgressError: If rollback already in progress.
        """
        ...

    async def execute_rollback(
        self,
        ceremony_evidence: "CeremonyEvidence",
    ) -> "RollbackCompletedPayload":
        """Execute rollback to selected checkpoint (AC3).

        Executes the rollback operation:
        1. Marks events after checkpoint as orphaned (PREVENT_DELETE)
        2. Moves HEAD pointer to checkpoint sequence
        3. Creates RollbackCompletedEvent for audit trail

        Constitutional Constraints:
        - PREVENT_DELETE: Events are orphaned, not deleted
        - CT-11: Rollback must be witnessed
        - FR143: Rollback is logged

        Args:
            ceremony_evidence: CeremonyEvidence proving Keeper authorization.

        Returns:
            RollbackCompletedPayload for event creation.

        Raises:
            RollbackNotPermittedError: If system is not halted.
            InvalidRollbackTargetError: If no target was selected.
            InvalidCeremonyError: If ceremony evidence is invalid.
        """
        ...

    async def get_rollback_status(self) -> dict[str, Any]:
        """Get current rollback operation status.

        Returns status information for monitoring and display.

        Returns:
            Dictionary with:
            - in_progress: Whether a rollback is in progress
            - selected_checkpoint_id: UUID of selected target, or None
            - selected_checkpoint_sequence: Sequence of selected target, or None
            - current_head_sequence: Current HEAD sequence
        """
        ...
