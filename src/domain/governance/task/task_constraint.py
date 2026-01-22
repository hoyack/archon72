"""TaskConstraint domain model for role-specific task constraints.

Story: consent-gov-2.7: Role-Specific Task Constraints

This module defines the domain model for task constraints, including:
- ConstraintRule value object
- Role-specific allowed/prohibited operation mappings
- Pure domain functions for constraint validation

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → Invalid operations raise errors
- Golden Rule: No silent assignment → Explicit consent required

Per FR14: Role-specific constraints within each rank.

Earl constraints (AC1, AC5, AC6):
- CAN: Create activation requests, view task state/history
- CANNOT: Compel acceptance, change scope, bypass consent

Cluster constraints (AC2):
- CAN: Accept, decline, halt, submit result/problem
- CANNOT: Be commanded (only activated)

References:
- [Source: rank-matrix.yaml]
- [Source: governance-prd.md FR14]
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
class ConstraintRule:
    """Value object representing a constraint rule.

    Per AC9: Clear error messages indicate which constraint was violated.

    Constraint rules are human-readable descriptions of the constraints
    enforced by the system. They are used for logging and error messages.

    Attributes:
        rule_id: Unique identifier for the rule (snake_case).
        description: Human-readable description of the constraint.
        prd_reference: Reference to PRD requirement (e.g., FR14).
        severity: Severity level (critical, major, minor).
    """

    rule_id: str
    description: str
    prd_reference: str
    severity: str  # "critical", "major", "minor"


# Earl constraints definition (AC1, AC5, AC6)
EARL_CONSTRAINTS: dict = {
    "role": "Earl",
    "branch": "administrative",
    "allowed_operations": frozenset(
        {
            TaskOperation.CREATE_ACTIVATION,
            TaskOperation.VIEW_TASK_STATE,
            TaskOperation.VIEW_TASK_HISTORY,
        }
    ),
    "prohibited_operations": frozenset(
        {
            TaskOperation.ACCEPT,  # Cannot compel Cluster (AC1)
            TaskOperation.DECLINE,  # Cannot decline for Cluster
            TaskOperation.HALT,  # Cannot halt Cluster's work
            TaskOperation.SUBMIT_RESULT,  # Cannot submit for Cluster
            TaskOperation.SUBMIT_PROBLEM,  # Cannot submit for Cluster
        }
    ),
    "rules": [
        ConstraintRule(
            rule_id="earl_no_compel",
            description="Earl cannot compel Cluster to accept task",
            prd_reference="FR14",
            severity="major",
        ),
        ConstraintRule(
            rule_id="earl_no_scope_change",
            description="Earl cannot modify task scope after creation",
            prd_reference="FR14/AC5",
            severity="major",
        ),
        ConstraintRule(
            rule_id="earl_no_bypass",
            description="Earl cannot bypass Cluster consent (must use activation flow)",
            prd_reference="FR14/AC6",
            severity="critical",
        ),
    ],
}

# Cluster constraints definition (AC2)
CLUSTER_CONSTRAINTS: dict = {
    "role": "Cluster",
    "branch": "participant",
    "allowed_operations": frozenset(
        {
            TaskOperation.ACCEPT,
            TaskOperation.DECLINE,
            TaskOperation.HALT,
            TaskOperation.SUBMIT_RESULT,
            TaskOperation.SUBMIT_PROBLEM,
        }
    ),
    "prohibited_operations": frozenset(
        {
            TaskOperation.CREATE_ACTIVATION,  # Cannot self-assign (AC2)
        }
    ),
    "rules": [
        ConstraintRule(
            rule_id="cluster_no_self_assign",
            description="Cluster cannot self-assign tasks (only activated)",
            prd_reference="FR14/AC2",
            severity="major",
        ),
        ConstraintRule(
            rule_id="cluster_consent_required",
            description="Cluster always has consent choice",
            prd_reference="FR14",
            severity="critical",
        ),
    ],
}

# System constraints definition
SYSTEM_CONSTRAINTS: dict = {
    "role": "system",
    "branch": "internal",
    "allowed_operations": frozenset(
        {
            TaskOperation.AUTO_DECLINE,
            TaskOperation.AUTO_START,
            TaskOperation.AUTO_QUARANTINE,
            TaskOperation.SEND_REMINDER,
        }
    ),
    "prohibited_operations": frozenset(),  # System has no prohibited operations
    "rules": [],
}


# Role → Constraints mapping
ROLE_CONSTRAINTS: dict[str, dict] = {
    "Earl": EARL_CONSTRAINTS,
    "Cluster": CLUSTER_CONSTRAINTS,
    "system": SYSTEM_CONSTRAINTS,
}


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


def is_operation_allowed(role: str, operation: TaskOperation) -> bool:
    """Check if an operation is allowed for a role.

    Per AC3: Role constraints validated at operation time.

    This is a pure domain function that checks the allowed_operations
    set for the given role.

    Args:
        role: Role to check (Earl, Cluster, system).
        operation: The TaskOperation to check.

    Returns:
        True if the operation is in the allowed set for the role.
        False otherwise.
    """
    allowed = ROLE_ALLOWED_OPERATIONS.get(role, frozenset())
    return operation in allowed


def is_operation_prohibited(role: str, operation: TaskOperation) -> bool:
    """Check if an operation is explicitly prohibited for a role.

    Per AC3: Role constraints validated at operation time.

    This is a pure domain function that checks the prohibited_operations
    set for the given role.

    Args:
        role: Role to check (Earl, Cluster, system).
        operation: The TaskOperation to check.

    Returns:
        True if the operation is explicitly prohibited.
        False otherwise.
    """
    prohibited = ROLE_PROHIBITED_OPERATIONS.get(role, frozenset())
    return operation in prohibited


def get_constraint_violation_reason(
    role: str,
    operation: TaskOperation,
) -> str | None:
    """Get the reason why an operation is not allowed.

    Per AC9: Clear error messages indicate which constraint was violated.

    This pure domain function returns a human-readable reason why
    the operation is not allowed. Returns None if the operation is allowed.

    Args:
        role: Role attempting the operation.
        operation: The TaskOperation being attempted.

    Returns:
        None if the operation is allowed.
        A string explaining why the operation is not allowed.
    """
    # Check if operation is allowed
    if is_operation_allowed(role, operation):
        return None

    # Check if explicitly prohibited
    if is_operation_prohibited(role, operation):
        return (
            f"{role} is prohibited from performing {operation.value}. "
            f"This operation violates role-specific constraints (FR14)."
        )

    # Not in allowed set
    return (
        f"{role} cannot perform {operation.value}. "
        f"Operation is not in the allowed set for this role (FR14)."
    )


def get_constraint_rules_for_role(role: str) -> list[ConstraintRule]:
    """Get all constraint rules for a role.

    Args:
        role: Role to get rules for.

    Returns:
        List of ConstraintRule objects for the role.
        Empty list if role not found.
    """
    constraints = ROLE_CONSTRAINTS.get(role, {})
    return constraints.get("rules", [])


def get_constraint_severity(role: str, operation: TaskOperation) -> str:
    """Get the severity of violating a constraint.

    Args:
        role: Role attempting the operation.
        operation: The prohibited operation.

    Returns:
        Severity level ("critical", "major", "minor").
        Defaults to "major" if not found.
    """
    constraints = ROLE_CONSTRAINTS.get(role, {})
    rules = constraints.get("rules", [])

    # Find a matching rule
    for rule in rules:
        if operation.value in rule.description.lower():
            return rule.severity

    # Default severity
    return "major"
