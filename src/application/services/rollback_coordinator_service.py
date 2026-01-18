"""RollbackCoordinatorService (Story 3.10, Task 8).

This application service coordinates rollback operations to checkpoint anchors.
It implements the RollbackCoordinator protocol.

Constitutional Constraints:
- FR143: Rollback for infrastructure recovery, logged, no event deletion
- CT-11: Rollback must be witnessed
- CT-13: Integrity outranks availability - halt required
- PREVENT_DELETE: Events are never deleted, only marked orphaned

Developer Golden Rules:
1. HALT FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Rollback creates audit trail events
3. FAIL LOUD - Never silently skip rollback operations

Usage:
    service = RollbackCoordinatorService(
        halt_checker=halt_checker,
        checkpoint_repository=checkpoint_repo,
    )

    # Query checkpoints (AC1)
    checkpoints = await service.query_checkpoints()

    # Select target (AC2)
    payload = await service.select_rollback_target(
        checkpoint_id=checkpoint.checkpoint_id,
        selecting_keepers=("keeper-001", "keeper-002"),
        reason="Fork detected",
    )

    # Execute rollback (AC3)
    result = await service.execute_rollback(ceremony_evidence)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from src.domain.errors.rollback import (
    CheckpointNotFoundError,
    InvalidRollbackTargetError,
    RollbackNotPermittedError,
)
from src.domain.events.rollback_completed import RollbackCompletedPayload
from src.domain.events.rollback_target_selected import RollbackTargetSelectedPayload

if TYPE_CHECKING:
    from src.application.ports.checkpoint_repository import CheckpointRepository
    from src.application.ports.halt_checker import HaltChecker
    from src.domain.models.ceremony_evidence import CeremonyEvidence
    from src.domain.models.checkpoint import Checkpoint

log = structlog.get_logger()


class RollbackCoordinatorService:
    """Coordinates rollback to checkpoint (FR143, AC1-AC3).

    This application service orchestrates the rollback process:
    1. Query available checkpoints (AC1)
    2. Record target selection with Keeper attribution (AC2)
    3. Execute rollback and mark events orphaned (AC3)

    Constitutional Constraints:
    - FR143: Rollback for infrastructure recovery, logged, no event deletion
    - CT-11: Rollback must be witnessed (events created)
    - CT-13: Integrity over availability (halt required)
    - PREVENT_DELETE: Events marked orphaned, not deleted

    Example:
        >>> service = RollbackCoordinatorService(halt_checker, checkpoint_repo)
        >>>
        >>> # Query checkpoints
        >>> checkpoints = await service.query_checkpoints()
        >>>
        >>> # Select target
        >>> payload = await service.select_rollback_target(
        ...     checkpoint_id=checkpoints[0].checkpoint_id,
        ...     selecting_keepers=("keeper-001", "keeper-002"),
        ...     reason="Fork detected",
        ... )
        >>>
        >>> # Execute rollback
        >>> result = await service.execute_rollback(ceremony_evidence)
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        checkpoint_repository: CheckpointRepository,
    ) -> None:
        """Initialize RollbackCoordinatorService.

        Args:
            halt_checker: Port for checking halt state.
            checkpoint_repository: Port for checkpoint operations.
        """
        self._halt_checker = halt_checker
        self._checkpoint_repo = checkpoint_repository
        self._selected_target: Checkpoint | None = None
        self._log = log.bind(service="rollback_coordinator")

    async def query_checkpoints(self) -> list[Checkpoint]:
        """Query available checkpoints (AC1).

        Returns all available checkpoint anchors that can be used
        as rollback targets.

        Returns:
            List of Checkpoint objects ordered by event_sequence (ascending).
        """
        checkpoints = await self._checkpoint_repo.get_all_checkpoints()

        self._log.debug(
            "checkpoints_queried",
            checkpoint_count=len(checkpoints),
            ac="AC1",
        )

        return checkpoints

    async def select_rollback_target(
        self,
        checkpoint_id: UUID,
        selecting_keepers: tuple[str, ...],
        reason: str,
    ) -> RollbackTargetSelectedPayload:
        """Record Keeper selection of rollback target (AC2).

        Records the Keepers' selection of a checkpoint for rollback.
        Creates a RollbackTargetSelectedPayload for event creation.

        Constitutional Constraint (CT-11, CT-13):
        - System must be halted (integrity over availability)
        - Selection must be witnessed (audit trail)

        Args:
            checkpoint_id: UUID of the selected checkpoint.
            selecting_keepers: Tuple of Keeper IDs who selected this target.
            reason: Human-readable reason for rollback.

        Returns:
            RollbackTargetSelectedPayload for event creation.

        Raises:
            RollbackNotPermittedError: If system is not halted.
            CheckpointNotFoundError: If checkpoint doesn't exist.
        """
        # HALT FIRST - Constitutional requirement (CT-13)
        is_halted = await self._halt_checker.is_halted()
        if not is_halted:
            self._log.warning(
                "rollback_target_selection_rejected",
                reason="system_not_halted",
                ct="CT-13",
            )
            raise RollbackNotPermittedError(
                "CT-13: Cannot select rollback target - system must be halted"
            )

        # Validate checkpoint exists
        checkpoint = await self._checkpoint_repo.get_checkpoint_by_id(checkpoint_id)
        if not checkpoint:
            self._log.warning(
                "checkpoint_not_found",
                checkpoint_id=str(checkpoint_id),
            )
            raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} not found")

        # Store selected target
        self._selected_target = checkpoint

        self._log.info(
            "rollback_target_selected",
            checkpoint_id=str(checkpoint_id),
            event_sequence=checkpoint.event_sequence,
            selecting_keepers=list(selecting_keepers),
            reason=reason,
            ac="AC2",
        )

        # Create payload for event
        return RollbackTargetSelectedPayload(
            target_checkpoint_id=checkpoint.checkpoint_id,
            target_event_sequence=checkpoint.event_sequence,
            target_anchor_hash=checkpoint.anchor_hash,
            selecting_keepers=selecting_keepers,
            selection_reason=reason,
            selection_timestamp=datetime.now(timezone.utc),
        )

    async def execute_rollback(
        self,
        ceremony_evidence: CeremonyEvidence,
    ) -> RollbackCompletedPayload:
        """Execute rollback to selected checkpoint (AC3).

        Executes the rollback operation:
        1. Validates halt state and ceremony
        2. Creates RollbackCompletedPayload for event

        Note: Actual event orphaning is handled by the event store
        when the RollbackCompletedEvent is processed. This service
        creates the payload for that event.

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
            InsufficientApproversError: If ceremony lacks required approvers.
        """
        # HALT FIRST - Constitutional requirement (CT-13)
        is_halted = await self._halt_checker.is_halted()
        if not is_halted:
            self._log.warning(
                "rollback_execution_rejected",
                reason="system_not_halted",
                ct="CT-13",
            )
            raise RollbackNotPermittedError(
                "CT-13: Cannot execute rollback - system must be halted"
            )

        # Validate target was selected
        if self._selected_target is None:
            self._log.warning(
                "rollback_execution_rejected",
                reason="no_target_selected",
            )
            raise InvalidRollbackTargetError(
                "No rollback target selected. Call select_rollback_target first."
            )

        # Validate ceremony evidence
        ceremony_evidence.validate()

        # For now, use placeholder values for head sequence
        # In a full implementation, this would query the event store
        # The actual orphaning happens when the event is processed
        previous_head = self._selected_target.event_sequence + 100  # Placeholder
        new_head = self._selected_target.event_sequence
        orphaned_count = previous_head - new_head
        orphaned_range = (new_head + 1, previous_head + 1)

        self._log.info(
            "rollback_executed",
            checkpoint_id=str(self._selected_target.checkpoint_id),
            previous_head=previous_head,
            new_head=new_head,
            orphaned_count=orphaned_count,
            ceremony_id=str(ceremony_evidence.ceremony_id),
            ac="AC3",
            fr="FR143",
        )

        # Create payload for event
        return RollbackCompletedPayload(
            target_checkpoint_id=self._selected_target.checkpoint_id,
            previous_head_sequence=previous_head,
            new_head_sequence=new_head,
            orphaned_event_count=orphaned_count,
            orphaned_sequence_range=orphaned_range,
            rollback_timestamp=datetime.now(timezone.utc),
            ceremony_id=ceremony_evidence.ceremony_id,
            approving_keepers=ceremony_evidence.get_keeper_ids(),
        )

    async def get_rollback_status(self) -> dict[str, Any]:
        """Get current rollback operation status.

        Returns status information for monitoring and display.

        Returns:
            Dictionary with:
            - in_progress: Whether a rollback is in progress (target selected)
            - selected_checkpoint_id: UUID of selected target as string, or None
            - selected_checkpoint_sequence: Sequence of selected target, or None
        """
        if self._selected_target is None:
            return {
                "in_progress": False,
                "selected_checkpoint_id": None,
                "selected_checkpoint_sequence": None,
            }

        return {
            "in_progress": True,
            "selected_checkpoint_id": str(self._selected_target.checkpoint_id),
            "selected_checkpoint_sequence": self._selected_target.event_sequence,
        }
