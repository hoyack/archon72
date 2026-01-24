"""TaskConstraintPort - Interface for role-specific task constraint enforcement.

Story: consent-gov-2.7: Role-Specific Task Constraints

This port defines the contract for validating task operations against
role-specific constraints. Enforces separation of powers at the task level.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → Violations raise clear errors
- CT-12: Witnessing creates accountability → Violations emit events

Per FR14: Role-specific constraints within each rank.

Earl constraints:
- CAN: Create activation requests, view task state/history
- CANNOT: Compel acceptance, change scope, bypass consent

Cluster constraints:
- CAN: Accept, decline, halt, submit result/problem
- CANNOT: Be commanded (only activated)

References:
- [Source: rank-matrix.yaml]
- [Source: governance-prd.md FR14]
- [Source: governance-architecture.md]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.task.task_constraint import (
    TaskOperation,
)


@dataclass(frozen=True)
class ConstraintViolation:
    """Details of a constraint violation.

    Per AC9: Clear error messages indicate which constraint was violated.

    This frozen dataclass captures all information about a constraint
    violation for logging, event emission, and error reporting.

    Attributes:
        actor_id: UUID of the actor who attempted the operation.
        actor_role: Role of the actor (Earl, Cluster, system).
        attempted_operation: The operation that was attempted.
        constraint_violated: Identifier for the constraint (operation_not_allowed, etc.)
        message: Human-readable message explaining the violation.
        task_id: Optional UUID of the task involved.
        timestamp: When the violation occurred.
    """

    actor_id: UUID
    actor_role: str
    attempted_operation: TaskOperation
    constraint_violated: str
    message: str
    task_id: UUID | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_event_payload(self) -> dict:
        """Convert to event payload for emission.

        Per AC8: Violations emit executive.task.constraint_violated event.

        Returns:
            Dictionary suitable for event payload.
        """
        return {
            "actor_id": str(self.actor_id),
            "actor_role": self.actor_role,
            "attempted_operation": self.attempted_operation.value,
            "constraint_violated": self.constraint_violated,
            "message": self.message,
            "task_id": str(self.task_id) if self.task_id else None,
            "timestamp": self.timestamp.isoformat(),
        }


class ConstraintViolationError(Exception):
    """Exception raised when a constraint violation is detected.

    Per AC4: Constraint violations are logged and rejected.

    This exception wraps a ConstraintViolation and provides a clear
    error message for the caller.

    Attributes:
        violation: The ConstraintViolation that triggered this error.
    """

    def __init__(self, violation: ConstraintViolation) -> None:
        self.violation = violation
        super().__init__(violation.message)


@runtime_checkable
class TaskConstraintPort(Protocol):
    """Port interface for task constraint enforcement.

    This protocol defines the contract for validating task operations
    against role-specific constraints. Implementations should:

    1. Load constraints from rank-matrix.yaml (AC7)
    2. Validate operations against allowed actions
    3. Emit violation events on failure (AC8)
    4. Return clear error messages (AC9)

    Per FR14: Role-specific constraints within each rank.

    Example usage:
        constraint_service = TaskConstraintService(...)

        # Check if valid (returns None or ConstraintViolation)
        violation = await constraint_service.validate_operation(
            actor_id=earl_uuid,
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,  # Not allowed for Earl
        )
        if violation:
            # Handle violation - log, notify, etc.
            pass

        # Or require valid (raises ConstraintViolationError)
        await constraint_service.require_valid_operation(
            actor_id=cluster_uuid,
            actor_role="Cluster",
            operation=TaskOperation.ACCEPT,  # Allowed for Cluster
        )
    """

    async def validate_operation(
        self,
        actor_id: UUID,
        actor_role: str,
        operation: TaskOperation,
        task_id: UUID | None = None,
    ) -> ConstraintViolation | None:
        """Validate an operation against role constraints.

        Per AC3: Role constraints validated at operation time.

        This method checks whether the given actor role is allowed
        to perform the specified operation. Returns None if valid,
        or a ConstraintViolation if invalid.

        Args:
            actor_id: UUID of the actor attempting the operation.
            actor_role: Role of the actor (Earl, Cluster, system).
            operation: The TaskOperation being attempted.
            task_id: Optional UUID of the task involved.

        Returns:
            None if the operation is allowed.
            ConstraintViolation if the operation violates constraints.
        """
        ...

    async def require_valid_operation(
        self,
        actor_id: UUID,
        actor_role: str,
        operation: TaskOperation,
        task_id: UUID | None = None,
    ) -> None:
        """Validate an operation and raise if invalid.

        Per AC4: Constraint violations logged and rejected.

        This method is a convenience wrapper that calls validate_operation
        and raises ConstraintViolationError if a violation is detected.

        Args:
            actor_id: UUID of the actor attempting the operation.
            actor_role: Role of the actor (Earl, Cluster, system).
            operation: The TaskOperation being attempted.
            task_id: Optional UUID of the task involved.

        Raises:
            ConstraintViolationError: If the operation violates constraints.
        """
        ...

    async def get_allowed_operations(
        self,
        actor_role: str,
    ) -> frozenset[TaskOperation]:
        """Get the set of allowed operations for a role.

        Per AC7: Constraints loaded from rank-matrix.yaml.

        Args:
            actor_role: Role to check (Earl, Cluster, system).

        Returns:
            Frozenset of TaskOperation values allowed for the role.
        """
        ...

    async def get_prohibited_operations(
        self,
        actor_role: str,
    ) -> frozenset[TaskOperation]:
        """Get the set of prohibited operations for a role.

        Per AC7: Constraints loaded from rank-matrix.yaml.

        Args:
            actor_role: Role to check (Earl, Cluster, system).

        Returns:
            Frozenset of TaskOperation values prohibited for the role.
        """
        ...

