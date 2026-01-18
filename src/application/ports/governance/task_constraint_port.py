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
from enum import Enum
from typing import Protocol, runtime_checkable
from uuid import UUID


class TaskOperation(str, Enum):
    """Operations that can be performed on tasks.

    Per FR14 and Dev Notes, operations are categorized by actor role.

    Earl operations:
    - CREATE_ACTIVATION: Create a task activation request
    - VIEW_TASK_STATE: View current task state
    - VIEW_TASK_HISTORY: View task event history

    Cluster operations:
    - ACCEPT: Accept an activation request
    - DECLINE: Decline an activation request
    - HALT: Stop in-progress work
    - SUBMIT_RESULT: Submit task result
    - SUBMIT_PROBLEM: Report a problem with the task

    System operations (automatic):
    - AUTO_DECLINE: System declines on TTL expiry
    - AUTO_START: System starts work after acceptance
    - AUTO_QUARANTINE: System quarantines on halt
    - SEND_REMINDER: System sends reminder notification
    """

    # Earl operations
    CREATE_ACTIVATION = "create_activation"
    VIEW_TASK_STATE = "view_task_state"
    VIEW_TASK_HISTORY = "view_task_history"

    # Cluster operations
    ACCEPT = "accept"
    DECLINE = "decline"
    HALT = "halt"
    SUBMIT_RESULT = "submit_result"
    SUBMIT_PROBLEM = "submit_problem"

    # System operations
    AUTO_DECLINE = "auto_decline"
    AUTO_START = "auto_start"
    AUTO_QUARANTINE = "auto_quarantine"
    SEND_REMINDER = "send_reminder"


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


# Role → Allowed Operations mapping (per Dev Notes)
ROLE_ALLOWED_OPERATIONS: dict[str, frozenset[TaskOperation]] = {
    "Earl": frozenset(
        {
            TaskOperation.CREATE_ACTIVATION,
            TaskOperation.VIEW_TASK_STATE,
            TaskOperation.VIEW_TASK_HISTORY,
        }
    ),
    "Cluster": frozenset(
        {
            TaskOperation.ACCEPT,
            TaskOperation.DECLINE,
            TaskOperation.HALT,
            TaskOperation.SUBMIT_RESULT,
            TaskOperation.SUBMIT_PROBLEM,
        }
    ),
    "system": frozenset(
        {
            TaskOperation.AUTO_DECLINE,
            TaskOperation.AUTO_START,
            TaskOperation.AUTO_QUARANTINE,
            TaskOperation.SEND_REMINDER,
        }
    ),
}

# Role → Prohibited Operations mapping (per Dev Notes)
# Explicitly prohibited operations (beyond just "not allowed")
ROLE_PROHIBITED_OPERATIONS: dict[str, frozenset[TaskOperation]] = {
    "Earl": frozenset(
        {
            TaskOperation.ACCEPT,  # Cannot accept on behalf of Cluster (AC1)
            TaskOperation.DECLINE,  # Cannot decline on behalf of Cluster
            TaskOperation.HALT,  # Cannot halt Cluster's work
            TaskOperation.SUBMIT_RESULT,  # Cannot submit for Cluster
            TaskOperation.SUBMIT_PROBLEM,  # Cannot submit for Cluster
        }
    ),
    "Cluster": frozenset(
        {
            TaskOperation.CREATE_ACTIVATION,  # Cannot self-assign (AC2)
        }
    ),
    "system": frozenset(),  # System has no prohibited operations
}
