# Story consent-gov-2.7: Role-Specific Task Constraints

Status: done

---

## Story

As a **governance system**,
I want **role-specific constraints enforced within each rank**,
So that **task operations respect branch authority and separation of powers**.

---

## Acceptance Criteria

1. **AC1:** Earl can only activate tasks (cannot compel or change scope) (FR14)
2. **AC2:** Cluster can only be activated (not commanded) (FR14)
3. **AC3:** Role constraints validated at operation time
4. **AC4:** Constraint violations logged and rejected
5. **AC5:** Earl cannot modify task scope after creation
6. **AC6:** Earl cannot bypass Cluster consent (must use activation flow)
7. **AC7:** Constraint validation uses rank-matrix.yaml as source of truth
8. **AC8:** Violations emit `executive.task.constraint_violated` event
9. **AC9:** Clear error messages indicate which constraint was violated
10. **AC10:** Unit tests for constraint enforcement

---

## Tasks / Subtasks

- [x] **Task 1: Create TaskConstraintPort interface** (AC: 3, 4)
  - [x] Create `src/application/ports/governance/task_constraint_port.py`
  - [x] Define `validate_operation()` method
  - [x] Define `ConstraintViolation` result type
  - [x] Include actor role and attempted operation

- [x] **Task 2: Create TaskConstraint domain model** (AC: 1, 2, 3)
  - [x] Create `src/domain/governance/task/task_constraint.py`
  - [x] Define `TaskOperation` enum (ACTIVATE, ACCEPT, DECLINE, HALT, REPORT, etc.)
  - [x] Define role → allowed operations mapping
  - [x] Define `ConstraintRule` value object

- [x] **Task 3: Implement TaskConstraintService** (AC: 3, 4, 7, 8, 9)
  - [x] Create `src/application/services/governance/task_constraint_service.py`
  - [x] Implement constraint validation logic
  - [x] Load constraints from rank-matrix.yaml
  - [x] Emit violation events on failure
  - [x] Return detailed error messages

- [x] **Task 4: Implement Earl constraints** (AC: 1, 5, 6)
  - [x] Earl can: create activation request, view task state/history
  - [x] Earl cannot: compel acceptance, change task scope, bypass consent
  - [x] Earl cannot: directly assign tasks (must use activation flow)
  - [x] Validate Earl operations against allowed actions

- [x] **Task 5: Implement Cluster constraints** (AC: 2)
  - [x] Cluster can: accept, decline, halt, report
  - [x] Cluster cannot: be commanded (only activated)
  - [x] Cluster cannot: modify task scope
  - [x] Cluster always has consent choice

- [x] **Task 6: Integrate with task operations** (AC: 3, 4)
  - [x] Validate constraints before task activation
  - [x] Validate constraints before accept/decline
  - [x] Validate constraints before result submission
  - [x] Reject operation if constraint violated

- [x] **Task 7: Implement violation logging** (AC: 4, 8)
  - [x] Emit `executive.task.constraint_violated` event
  - [x] Include: actor_id, actor_role, attempted_operation, constraint_violated
  - [x] Log to ledger for audit trail
  - [x] Knight can observe all violation events

- [x] **Task 8: Write comprehensive unit tests** (AC: 10)
  - [x] Test Earl can activate
  - [x] Test Earl cannot compel
  - [x] Test Earl cannot change scope after creation
  - [x] Test Cluster can accept/decline
  - [x] Test Cluster cannot be commanded
  - [x] Test violation events emitted
  - [x] Test constraint validation uses rank-matrix.yaml

---

## Documentation Checklist

- [x] Architecture docs updated (constraint enforcement)
- [x] Inline comments explaining separation of powers
- [x] N/A - API docs (service layer)
- [x] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Separation of Powers Enforcement:**
```
Earl (Administrative Branch):
  - CAN: Create activation requests
  - CAN: View task state and history
  - CANNOT: Compel Cluster to accept
  - CANNOT: Change task scope after creation
  - CANNOT: Directly assign tasks (bypassing consent)

Cluster (Participant):
  - CAN: Accept activation requests
  - CAN: Decline without justification
  - CAN: Halt in-progress tasks
  - CAN: Submit results/problem reports
  - CANNOT: Be commanded (only activated)
  - ALWAYS: Has consent choice
```

**Constraint Source of Truth:**
```
config/permissions/rank-matrix.yaml
  - Defines allowed_actions per rank
  - Defines prohibited_actions per rank
  - Defines constraints (human-readable rules)

The TaskConstraintService loads from this YAML.
No hardcoded constraints in application code.
```

### Task Operations and Allowed Roles

```python
class TaskOperation(Enum):
    """Operations that can be performed on tasks."""
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


# Role → Allowed Operations mapping
ROLE_ALLOWED_OPERATIONS: dict[str, frozenset[TaskOperation]] = {
    "Earl": frozenset({
        TaskOperation.CREATE_ACTIVATION,
        TaskOperation.VIEW_TASK_STATE,
        TaskOperation.VIEW_TASK_HISTORY,
    }),
    "Cluster": frozenset({
        TaskOperation.ACCEPT,
        TaskOperation.DECLINE,
        TaskOperation.HALT,
        TaskOperation.SUBMIT_RESULT,
        TaskOperation.SUBMIT_PROBLEM,
    }),
    "system": frozenset({
        TaskOperation.AUTO_DECLINE,
        TaskOperation.AUTO_START,
        TaskOperation.AUTO_QUARANTINE,
        TaskOperation.SEND_REMINDER,
    }),
}

# Explicitly prohibited operations
ROLE_PROHIBITED_OPERATIONS: dict[str, frozenset[TaskOperation]] = {
    "Earl": frozenset({
        TaskOperation.ACCEPT,      # Cannot accept on behalf of Cluster
        TaskOperation.DECLINE,     # Cannot decline on behalf of Cluster
        TaskOperation.HALT,        # Cannot halt Cluster's work
        TaskOperation.SUBMIT_RESULT,  # Cannot submit for Cluster
    }),
    "Cluster": frozenset({
        TaskOperation.CREATE_ACTIVATION,  # Cannot self-assign
    }),
}
```

### Service Implementation Sketch

```python
@dataclass(frozen=True)
class ConstraintViolation:
    """Details of a constraint violation."""
    actor_id: UUID
    actor_role: str
    attempted_operation: TaskOperation
    constraint_violated: str
    message: str


class TaskConstraintService:
    """Enforces role-specific task constraints."""

    def __init__(
        self,
        permission_matrix: PermissionMatrixPort,
        event_emitter: EventEmitter,
    ):
        self._permissions = permission_matrix
        self._event_emitter = event_emitter

    async def validate_operation(
        self,
        actor_id: UUID,
        actor_role: str,
        operation: TaskOperation,
        task_id: UUID | None = None,
    ) -> ConstraintViolation | None:
        """Validate operation against role constraints.

        Returns None if valid, ConstraintViolation if invalid.
        """
        # Load role permissions from rank-matrix.yaml
        role_permissions = await self._permissions.get_role_permissions(actor_role)

        # Check if operation is allowed
        if operation not in role_permissions.allowed_operations:
            violation = ConstraintViolation(
                actor_id=actor_id,
                actor_role=actor_role,
                attempted_operation=operation,
                constraint_violated="operation_not_allowed",
                message=f"{actor_role} cannot perform {operation.value}",
            )
            await self._emit_violation(violation, task_id)
            return violation

        # Check if operation is explicitly prohibited
        if operation in role_permissions.prohibited_operations:
            violation = ConstraintViolation(
                actor_id=actor_id,
                actor_role=actor_role,
                attempted_operation=operation,
                constraint_violated="operation_prohibited",
                message=f"{actor_role} is prohibited from {operation.value}",
            )
            await self._emit_violation(violation, task_id)
            return violation

        return None  # Valid

    async def _emit_violation(
        self,
        violation: ConstraintViolation,
        task_id: UUID | None,
    ) -> None:
        """Emit constraint violation event."""
        await self._event_emitter.emit(
            event_type="executive.task.constraint_violated",
            actor=str(violation.actor_id),
            payload={
                "actor_id": str(violation.actor_id),
                "actor_role": violation.actor_role,
                "attempted_operation": violation.attempted_operation.value,
                "constraint_violated": violation.constraint_violated,
                "message": violation.message,
                "task_id": str(task_id) if task_id else None,
            },
        )

    async def require_valid_operation(
        self,
        actor_id: UUID,
        actor_role: str,
        operation: TaskOperation,
        task_id: UUID | None = None,
    ) -> None:
        """Validate operation, raising exception if invalid."""
        violation = await self.validate_operation(
            actor_id=actor_id,
            actor_role=actor_role,
            operation=operation,
            task_id=task_id,
        )
        if violation:
            raise ConstraintViolationError(violation)
```

### Integration with Task Services

```python
class TaskActivationService:
    """Example integration with constraint service."""

    async def create_activation_request(
        self,
        earl_id: UUID,
        cluster_id: UUID,
        task_details: TaskDetails,
    ) -> ActivationRequest:
        # Validate Earl can create activation
        await self._constraints.require_valid_operation(
            actor_id=earl_id,
            actor_role="Earl",
            operation=TaskOperation.CREATE_ACTIVATION,
        )

        # Proceed with activation...


class TaskConsentService:
    """Example integration with constraint service."""

    async def accept_task(
        self,
        task_id: UUID,
        cluster_id: UUID,
    ) -> Task:
        # Validate Cluster can accept
        await self._constraints.require_valid_operation(
            actor_id=cluster_id,
            actor_role="Cluster",
            operation=TaskOperation.ACCEPT,
            task_id=task_id,
        )

        # Proceed with acceptance...
```

### Event Pattern

```python
# Constraint violation event
{
    "event_type": "executive.task.constraint_violated",
    "actor": "uuid-of-actor",
    "payload": {
        "actor_id": "uuid",
        "actor_role": "Earl",
        "attempted_operation": "accept",
        "constraint_violated": "operation_not_allowed",
        "message": "Earl cannot perform accept",
        "task_id": "uuid"  # if applicable
    }
}
```

### Test Patterns

```python
class TestTaskConstraintService:
    """Unit tests for task constraint enforcement."""

    async def test_earl_can_activate(
        self,
        constraint_service: TaskConstraintService,
    ):
        """Earl can create activation requests."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.CREATE_ACTIVATION,
        )
        assert violation is None

    async def test_earl_cannot_compel(
        self,
        constraint_service: TaskConstraintService,
    ):
        """Earl cannot accept on behalf of Cluster."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )
        assert violation is not None
        assert "cannot perform accept" in violation.message

    async def test_earl_cannot_change_scope(
        self,
        constraint_service: TaskConstraintService,
        activated_task: Task,
    ):
        """Earl cannot modify task scope after creation."""
        # This would be enforced by not having a MODIFY_SCOPE operation
        # for Earl, or by checking task state
        pass

    async def test_cluster_can_accept(
        self,
        constraint_service: TaskConstraintService,
    ):
        """Cluster can accept activation requests."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.ACCEPT,
        )
        assert violation is None

    async def test_cluster_cannot_be_commanded(
        self,
        constraint_service: TaskConstraintService,
    ):
        """Cluster cannot self-assign (be commanded)."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.CREATE_ACTIVATION,
        )
        assert violation is not None

    async def test_violation_event_emitted(
        self,
        constraint_service: TaskConstraintService,
        event_capture: EventCapture,
    ):
        """Constraint violation emits event."""
        await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,  # Not allowed
        )

        event = event_capture.get_last("executive.task.constraint_violated")
        assert event.payload["actor_role"] == "Earl"
        assert event.payload["attempted_operation"] == "accept"

    async def test_constraints_loaded_from_rank_matrix(
        self,
        constraint_service: TaskConstraintService,
        mock_permission_matrix: MockPermissionMatrix,
    ):
        """Constraints loaded from rank-matrix.yaml."""
        await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.CREATE_ACTIVATION,
        )

        # Verify permissions were loaded from YAML
        assert mock_permission_matrix.get_role_permissions.called
        assert mock_permission_matrix.get_role_permissions.call_args[0][0] == "Earl"
```

### Dependencies

- **Depends on:** gov-epic-1 (Permission Matrix), hardening-2 (YAML loading)
- **Integrates with:** consent-gov-2-2 (activation), consent-gov-2-3 (consent)

### References

- FR14: Role-specific constraints within each rank
- rank-matrix.yaml: Canonical constraint definitions
- Government PRD §4: Branch authority and separation of powers
