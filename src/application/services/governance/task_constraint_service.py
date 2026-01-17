"""TaskConstraintService - Service for role-specific task constraint enforcement.

Story: consent-gov-2.7: Role-Specific Task Constraints

This service implements the TaskConstraintPort interface, providing
constraint validation, violation event emission, and error handling.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → Violations logged and rejected
- CT-12: Witnessing creates accountability → Events emitted for violations

Per FR14: Role-specific constraints within each rank.

Implements:
- AC3: Role constraints validated at operation time
- AC4: Constraint violations logged and rejected
- AC7: Constraint validation uses rank-matrix.yaml (via domain mappings)
- AC8: Violations emit executive.task.constraint_violated event
- AC9: Clear error messages indicate which constraint was violated

References:
- [Source: governance-prd.md FR14]
- [Source: rank-matrix.yaml]
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Protocol
from uuid import UUID

from src.application.ports.governance.task_constraint_port import (
    ConstraintViolation,
    ConstraintViolationError,
    ROLE_ALLOWED_OPERATIONS,
    ROLE_PROHIBITED_OPERATIONS,
    TaskConstraintPort,
    TaskOperation,
)
from src.domain.governance.task.task_constraint import (
    get_constraint_violation_reason,
    is_operation_allowed,
    is_operation_prohibited,
)


class EventEmitter(Protocol):
    """Protocol for event emission.

    This protocol defines the interface for emitting governance events.
    Implementations may use the two-phase event system.
    """

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit an event to the governance ledger.

        Args:
            event_type: Type of event (e.g., executive.task.constraint_violated).
            actor: ID of the actor who triggered the event.
            payload: Event payload containing details.
        """
        ...


class TaskConstraintService(TaskConstraintPort):
    """Service for enforcing role-specific task constraints.

    This service validates task operations against role-specific constraints,
    emits violation events, and provides clear error messages.

    Per FR14: Role-specific constraints within each rank.

    Example usage:
        service = TaskConstraintService(event_emitter=emitter)

        # Check if valid
        violation = await service.validate_operation(
            actor_id=earl_uuid,
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,  # Not allowed
        )
        if violation:
            # Handle violation
            pass

        # Or require valid (raises ConstraintViolationError)
        await service.require_valid_operation(
            actor_id=cluster_uuid,
            actor_role="Cluster",
            operation=TaskOperation.ACCEPT,
        )
    """

    def __init__(
        self,
        event_emitter: EventEmitter,
        permission_matrix: Any = None,  # Optional for YAML loading
    ) -> None:
        """Initialize the task constraint service.

        Args:
            event_emitter: Event emitter for violation events.
            permission_matrix: Optional permission matrix port for YAML loading.
        """
        self._event_emitter = event_emitter
        self._permission_matrix = permission_matrix

    async def validate_operation(
        self,
        actor_id: UUID,
        actor_role: str,
        operation: TaskOperation,
        task_id: Optional[UUID] = None,
    ) -> Optional[ConstraintViolation]:
        """Validate an operation against role constraints.

        Per AC3: Role constraints validated at operation time.

        Checks whether the given actor role is allowed to perform the
        specified operation. Returns None if valid, or a ConstraintViolation
        if invalid. Emits a violation event if the operation is not allowed.

        Args:
            actor_id: UUID of the actor attempting the operation.
            actor_role: Role of the actor (Earl, Cluster, system).
            operation: The TaskOperation being attempted.
            task_id: Optional UUID of the task involved.

        Returns:
            None if the operation is allowed.
            ConstraintViolation if the operation violates constraints.
        """
        # Check if operation is allowed using domain function
        if is_operation_allowed(actor_role, operation):
            return None

        # Get the violation reason
        reason = get_constraint_violation_reason(actor_role, operation)
        if reason is None:
            reason = f"{actor_role} cannot perform {operation.value}"

        # Determine constraint type
        if is_operation_prohibited(actor_role, operation):
            constraint_violated = "operation_prohibited"
        else:
            constraint_violated = "operation_not_allowed"

        # Create violation
        violation = ConstraintViolation(
            actor_id=actor_id,
            actor_role=actor_role,
            attempted_operation=operation,
            constraint_violated=constraint_violated,
            message=reason,
            task_id=task_id,
        )

        # Emit violation event (AC8)
        await self._emit_violation_event(violation)

        return violation

    async def require_valid_operation(
        self,
        actor_id: UUID,
        actor_role: str,
        operation: TaskOperation,
        task_id: Optional[UUID] = None,
    ) -> None:
        """Validate an operation and raise if invalid.

        Per AC4: Constraint violations logged and rejected.

        Convenience wrapper that calls validate_operation and raises
        ConstraintViolationError if a violation is detected.

        Args:
            actor_id: UUID of the actor attempting the operation.
            actor_role: Role of the actor (Earl, Cluster, system).
            operation: The TaskOperation being attempted.
            task_id: Optional UUID of the task involved.

        Raises:
            ConstraintViolationError: If the operation violates constraints.
        """
        violation = await self.validate_operation(
            actor_id=actor_id,
            actor_role=actor_role,
            operation=operation,
            task_id=task_id,
        )
        if violation:
            raise ConstraintViolationError(violation)

    async def get_allowed_operations(
        self,
        actor_role: str,
    ) -> frozenset[TaskOperation]:
        """Get the set of allowed operations for a role.

        Per AC7: Constraints loaded from rank-matrix.yaml (via domain mappings).

        Args:
            actor_role: Role to check (Earl, Cluster, system).

        Returns:
            Frozenset of TaskOperation values allowed for the role.
        """
        return ROLE_ALLOWED_OPERATIONS.get(actor_role, frozenset())

    async def get_prohibited_operations(
        self,
        actor_role: str,
    ) -> frozenset[TaskOperation]:
        """Get the set of prohibited operations for a role.

        Per AC7: Constraints loaded from rank-matrix.yaml (via domain mappings).

        Args:
            actor_role: Role to check (Earl, Cluster, system).

        Returns:
            Frozenset of TaskOperation values prohibited for the role.
        """
        return ROLE_PROHIBITED_OPERATIONS.get(actor_role, frozenset())

    async def _emit_violation_event(
        self,
        violation: ConstraintViolation,
    ) -> None:
        """Emit a constraint violation event.

        Per AC8: Violations emit executive.task.constraint_violated event.

        Args:
            violation: The ConstraintViolation to emit.
        """
        await self._event_emitter.emit(
            event_type="executive.task.constraint_violated",
            actor=str(violation.actor_id),
            payload=violation.to_event_payload(),
        )
