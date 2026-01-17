# Story consent-gov-2.3: Task Consent Operations

Status: ready-for-dev

---

## Story

As a **Cluster**,
I want **to accept or decline task activation requests**,
So that **I maintain control over my participation with full dignity and without penalty for refusal**.

---

## Acceptance Criteria

1. **AC1:** Cluster can view pending task activation requests (FR2)
2. **AC2:** Cluster can accept a task activation request (FR3)
3. **AC3:** Cluster can decline a task activation request without providing justification (FR4)
4. **AC4:** Cluster can halt an in-progress task without penalty (FR5)
5. **AC5:** Declining does NOT reduce standing, reputation, or trigger any penalties
6. **AC6:** No standing/reputation tracking schema exists (architectural enforcement)
7. **AC7:** Event `executive.task.accepted` emitted on acceptance
8. **AC8:** Event `executive.task.declined` emitted on decline (explicit or TTL)
9. **AC9:** Event `executive.task.halted` emitted when Cluster halts in-progress task
10. **AC10:** Unit tests for accept, decline, and halt operations

---

## Tasks / Subtasks

- [ ] **Task 1: Create TaskConsentPort interface** (AC: 1, 2, 3, 4)
  - [ ] Create `src/application/ports/governance/task_consent_port.py`
  - [ ] Define `get_pending_requests()` method for Cluster
  - [ ] Define `accept_task()` method
  - [ ] Define `decline_task()` method (no justification required)
  - [ ] Define `halt_task()` method

- [ ] **Task 2: Implement TaskConsentService** (AC: 2, 3, 4)
  - [ ] Create `src/application/services/governance/task_consent_service.py`
  - [ ] Implement `get_pending_requests()` - query routed tasks for Cluster
  - [ ] Implement `accept_task()` - transition routed → accepted
  - [ ] Implement `decline_task()` - transition routed → declined
  - [ ] Implement `halt_task()` - transition in_progress → quarantined (no penalty)

- [ ] **Task 3: Enforce penalty-free refusal** (AC: 5, 6)
  - [ ] Verify NO standing/reputation fields in any schema
  - [ ] Verify NO penalty tracking on decline
  - [ ] Add architectural test: schema has no standing/reputation columns
  - [ ] Document constitutional guarantee in service

- [ ] **Task 4: Implement pending request visibility** (AC: 1)
  - [ ] Query tasks in ROUTED state for Cluster
  - [ ] Include task details, TTL remaining, Earl info
  - [ ] Support pagination for multiple pending requests
  - [ ] Filter out expired requests (already auto-declined)

- [ ] **Task 5: Implement accept operation** (AC: 2, 7)
  - [ ] Validate task is in ROUTED state
  - [ ] Validate Cluster is the intended recipient
  - [ ] Transition task to ACCEPTED state
  - [ ] Emit `executive.task.accepted` event
  - [ ] Use two-phase event emission

- [ ] **Task 6: Implement decline operation** (AC: 3, 8)
  - [ ] Validate task is in ROUTED or ACCEPTED state
  - [ ] NO justification required (FR4 explicit)
  - [ ] Transition task to DECLINED state
  - [ ] Emit `executive.task.declined` event with reason "explicit_decline"
  - [ ] Do NOT record any negative attribution

- [ ] **Task 7: Implement halt operation** (AC: 4, 9)
  - [ ] Validate task is in IN_PROGRESS state
  - [ ] Validate Cluster is the worker
  - [ ] Transition task to QUARANTINED state (halt = quarantine, not failure)
  - [ ] Emit `executive.task.halted` event
  - [ ] Do NOT record any penalty or negative attribution

- [ ] **Task 8: Write comprehensive unit tests** (AC: 10)
  - [ ] Test get_pending_requests returns routed tasks
  - [ ] Test accept transitions to ACCEPTED
  - [ ] Test decline transitions to DECLINED without justification
  - [ ] Test halt transitions to QUARANTINED without penalty
  - [ ] Test invalid state transitions rejected
  - [ ] Test unauthorized Cluster operations rejected
  - [ ] Architectural test: no standing/reputation schema

---

## Documentation Checklist

- [ ] Architecture docs updated (consent operations workflow)
- [ ] Inline comments explaining penalty-free guarantee
- [ ] N/A - API docs (service layer)
- [ ] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements consent operations with constitutional guarantees.

**Golden Rules Enforcement:**

| Golden Rule | Enforcement Mechanism |
|-------------|----------------------|
| No silent assignment | Task state machine requires explicit accept/decline transition |
| Refusal is penalty-free | No standing/reputation tracking exists in schema |

**Constitutional Guarantee:**
> "Refusal is penalty-free - No standing/reputation tracking exists in schema"

This is NOT a policy decision - it's an architectural constraint. The schema MUST NOT contain:
- Standing scores
- Reputation metrics
- Decline counts
- Performance ratings
- Any field that could be used to penalize refusal

### TaskConsentService

```python
from typing import Protocol
from uuid import UUID
from datetime import datetime

class TaskConsentService:
    """Service for Cluster consent operations on tasks.

    Constitutional Guarantees:
    - Declining is ALWAYS penalty-free
    - No standing/reputation tracking exists
    - Halting in-progress tasks incurs no penalty
    - Justification is NEVER required for decline
    """

    def __init__(
        self,
        task_state_port: TaskStatePort,
        ledger_port: GovernanceLedgerPort,
        two_phase_emitter: TwoPhaseEventEmitterPort,
        time_authority: TimeAuthority,
    ) -> None:
        self._task_state = task_state_port
        self._ledger = ledger_port
        self._emitter = two_phase_emitter
        self._time = time_authority

    async def get_pending_requests(
        self,
        cluster_id: str,
        limit: int = 100,
    ) -> list[PendingTaskView]:
        """Get pending task activation requests for a Cluster.

        Returns tasks in ROUTED state addressed to this Cluster.
        """
        tasks = await self._task_state.get_tasks_by_state_and_cluster(
            status=TaskStatus.ROUTED,
            cluster_id=cluster_id,
            limit=limit,
        )

        return [
            PendingTaskView(
                task_id=t.task_id,
                earl_id=t.earl_id,
                description_preview=t.description_preview,
                ttl_remaining=self._calculate_ttl_remaining(t),
                routed_at=t.state_entered_at,
            )
            for t in tasks
            if not self._is_expired(t)  # Filter out expired
        ]

    async def accept_task(
        self,
        task_id: UUID,
        cluster_id: str,
    ) -> TaskConsentResult:
        """Accept a task activation request.

        Transitions: ROUTED → ACCEPTED

        Returns:
            TaskConsentResult with new task state
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.accept",
            actor_id=cluster_id,
            target_entity_id=str(task_id),
            intent_payload={},
        ) as execution:
            task = await self._task_state.get_task(task_id)

            # Validate Cluster is the intended recipient
            if task.cluster_id != cluster_id:
                raise UnauthorizedConsentError(
                    f"Cluster {cluster_id} is not the recipient of task {task_id}"
                )

            # Validate task is in ROUTED state
            if task.current_status != TaskStatus.ROUTED:
                raise InvalidTaskStateError(
                    f"Cannot accept task in {task.current_status.value} state"
                )

            # Transition to ACCEPTED
            new_task = task.transition(
                TaskStatus.ACCEPTED,
                self._time.now(),
                cluster_id,
            )
            await self._task_state.save_task(new_task)

            # Emit event
            await self._emit_accepted_event(new_task, cluster_id)

            execution.set_result({"accepted": True})
            return TaskConsentResult(
                success=True,
                task_state=new_task,
                operation="accepted",
            )

    async def decline_task(
        self,
        task_id: UUID,
        cluster_id: str,
        # NOTE: No justification parameter - intentionally omitted (FR4)
    ) -> TaskConsentResult:
        """Decline a task activation request.

        Constitutional Guarantee:
        - NO justification required (FR4 explicit)
        - NO penalty incurred
        - NO standing reduction
        - NO negative attribution recorded

        Transitions: ROUTED → DECLINED or ACCEPTED → DECLINED
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.decline",
            actor_id=cluster_id,
            target_entity_id=str(task_id),
            intent_payload={},
        ) as execution:
            task = await self._task_state.get_task(task_id)

            # Validate Cluster is the intended recipient
            if task.cluster_id != cluster_id:
                raise UnauthorizedConsentError(
                    f"Cluster {cluster_id} is not the recipient of task {task_id}"
                )

            # Validate task is in valid state for decline
            if task.current_status not in {TaskStatus.ROUTED, TaskStatus.ACCEPTED}:
                raise InvalidTaskStateError(
                    f"Cannot decline task in {task.current_status.value} state"
                )

            # Transition to DECLINED
            new_task = task.transition(
                TaskStatus.DECLINED,
                self._time.now(),
                cluster_id,
            )
            await self._task_state.save_task(new_task)

            # Emit event - NO penalty information recorded
            await self._emit_declined_event(
                new_task,
                cluster_id,
                reason="explicit_decline",  # Not "failure" or "penalty"
            )

            execution.set_result({"declined": True})
            return TaskConsentResult(
                success=True,
                task_state=new_task,
                operation="declined",
            )

    async def halt_task(
        self,
        task_id: UUID,
        cluster_id: str,
        # NOTE: No justification required - halting is penalty-free (FR5)
    ) -> TaskConsentResult:
        """Halt an in-progress task.

        Constitutional Guarantee:
        - Halting incurs NO penalty (FR5)
        - Task transitions to QUARANTINED (safe state)
        - NO negative attribution recorded

        Transitions: IN_PROGRESS → QUARANTINED
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.halt",
            actor_id=cluster_id,
            target_entity_id=str(task_id),
            intent_payload={},
        ) as execution:
            task = await self._task_state.get_task(task_id)

            # Validate Cluster is the worker
            if task.cluster_id != cluster_id:
                raise UnauthorizedConsentError(
                    f"Cluster {cluster_id} is not working on task {task_id}"
                )

            # Validate task is in IN_PROGRESS state
            if task.current_status != TaskStatus.IN_PROGRESS:
                raise InvalidTaskStateError(
                    f"Cannot halt task in {task.current_status.value} state"
                )

            # Transition to QUARANTINED (not "failed" - important distinction)
            new_task = task.transition(
                TaskStatus.QUARANTINED,
                self._time.now(),
                cluster_id,
            )
            await self._task_state.save_task(new_task)

            # Emit event - explicitly NO penalty
            await self._emit_halted_event(
                new_task,
                cluster_id,
                reason="cluster_initiated_halt",
                penalty_incurred=False,  # Constitutional guarantee
            )

            execution.set_result({"halted": True})
            return TaskConsentResult(
                success=True,
                task_state=new_task,
                operation="halted",
            )
```

### Event Payloads

**executive.task.accepted:**
```json
{
  "metadata": {
    "event_type": "executive.task.accepted",
    "actor_id": "cluster-xyz"
  },
  "payload": {
    "task_id": "uuid",
    "cluster_id": "cluster-xyz",
    "accepted_at": "2026-01-16T00:00:00Z"
  }
}
```

**executive.task.declined:**
```json
{
  "metadata": {
    "event_type": "executive.task.declined",
    "actor_id": "cluster-xyz"
  },
  "payload": {
    "task_id": "uuid",
    "cluster_id": "cluster-xyz",
    "declined_at": "2026-01-16T00:00:00Z",
    "reason": "explicit_decline",
    "penalty_incurred": false  // ALWAYS false - constitutional
  }
}
```

**executive.task.halted:**
```json
{
  "metadata": {
    "event_type": "executive.task.halted",
    "actor_id": "cluster-xyz"
  },
  "payload": {
    "task_id": "uuid",
    "cluster_id": "cluster-xyz",
    "halted_at": "2026-01-16T00:00:00Z",
    "reason": "cluster_initiated_halt",
    "penalty_incurred": false  // ALWAYS false - FR5
  }
}
```

### PendingTaskView

```python
@dataclass(frozen=True)
class PendingTaskView:
    """View model for pending task activation requests."""
    task_id: UUID
    earl_id: str
    description_preview: str  # First 200 chars
    ttl_remaining: timedelta
    routed_at: datetime

@dataclass(frozen=True)
class TaskConsentResult:
    """Result of a consent operation."""
    success: bool
    task_state: TaskState
    operation: str  # "accepted", "declined", "halted"
    message: str = ""
```

### Architectural Enforcement Test

```python
def test_no_standing_reputation_schema():
    """ARCHITECTURAL TEST: Schema has no standing/reputation columns.

    Constitutional Guarantee:
    - Refusal is penalty-free
    - This is enforced by absence of tracking schema

    If this test fails, it indicates a constitutional violation.
    """
    from sqlalchemy import inspect
    from src.infrastructure.database import engine

    inspector = inspect(engine)

    # Check all tables in all schemas
    for schema in ["ledger", "projections", "public"]:
        for table_name in inspector.get_table_names(schema=schema):
            columns = inspector.get_columns(table_name, schema=schema)
            column_names = [c["name"].lower() for c in columns]

            forbidden_columns = {
                "standing", "reputation", "score", "rating",
                "decline_count", "refusal_count", "penalty",
                "performance_score", "reliability_score",
            }

            violations = forbidden_columns & set(column_names)
            assert not violations, (
                f"CONSTITUTIONAL VIOLATION: Table {schema}.{table_name} "
                f"contains forbidden columns: {violations}. "
                f"Refusal must be penalty-free."
            )
```

### Error Types

```python
class UnauthorizedConsentError(Exception):
    """Raised when Cluster tries to consent on task not addressed to them."""
    pass

class InvalidTaskStateError(Exception):
    """Raised when consent operation attempted on invalid task state."""
    pass
```

### Existing Patterns to Follow

**Reference:** `src/domain/governance/task/task_state.py` (from story 2-1)

Task state machine for transition validation.

**Reference:** `src/application/services/governance/two_phase_event_emitter.py` (from story 1-6)

Two-phase emission ensures intent is recorded before operation.

### Dependency on Previous Stories

This story depends on:
- `consent-gov-1-6`: Two-phase event emission
- `consent-gov-2-1`: Task state machine
- `consent-gov-2-2`: Task activation (creates tasks to consent on)

**Import:**
```python
from src.domain.governance.task.task_state import TaskState, TaskStatus
from src.application.services.governance.two_phase_event_emitter import TwoPhaseExecution
from src.application.ports.time_authority import TimeAuthority
```

### Source Tree Components

**New Files:**
```
src/application/ports/governance/
└── task_consent_port.py          # TaskConsentPort protocol

src/application/services/governance/
└── task_consent_service.py       # TaskConsentService
```

**Test Files:**
```
tests/unit/application/services/governance/
└── test_task_consent_service.py

tests/architectural/
└── test_no_standing_reputation_schema.py  # Constitutional test
```

### Technical Requirements

**Python Patterns (CRITICAL):**
- NO justification parameter on decline (FR4)
- NO penalty tracking anywhere
- `penalty_incurred: false` in all decline/halt events
- Type hints on ALL functions (mypy --strict must pass)

**Constitutional Requirements:**
- Schema MUST NOT contain standing/reputation columns
- Events MUST record `penalty_incurred: false`
- Decline reason MUST be "explicit_decline" (not "failure")

### Testing Standards

**Unit Test Patterns:**
```python
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

class TestTaskConsentService:
    @pytest.mark.asyncio
    async def test_accept_transitions_to_accepted(self):
        """Accepting a routed task transitions to ACCEPTED."""
        task = create_task(status=TaskStatus.ROUTED, cluster_id="cluster-1")
        task_port = AsyncMock()
        task_port.get_task.return_value = task

        service = TaskConsentService(...)

        result = await service.accept_task(
            task_id=task.task_id,
            cluster_id="cluster-1",
        )

        assert result.success is True
        assert result.operation == "accepted"
        assert result.task_state.current_status == TaskStatus.ACCEPTED

    @pytest.mark.asyncio
    async def test_decline_requires_no_justification(self):
        """Declining does NOT require justification (FR4)."""
        task = create_task(status=TaskStatus.ROUTED, cluster_id="cluster-1")
        task_port = AsyncMock()
        task_port.get_task.return_value = task

        service = TaskConsentService(...)

        # NOTE: No justification parameter - this is intentional
        result = await service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-1",
        )

        assert result.success is True
        assert result.operation == "declined"

    @pytest.mark.asyncio
    async def test_decline_incurs_no_penalty(self):
        """Declining MUST NOT incur any penalty."""
        task = create_task(status=TaskStatus.ROUTED, cluster_id="cluster-1")
        ledger_port = AsyncMock()

        service = TaskConsentService(ledger_port=ledger_port, ...)

        await service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-1",
        )

        # Verify event payload
        emitted_event = ledger_port.append_event.call_args[0][0]
        assert emitted_event.payload["penalty_incurred"] is False

    @pytest.mark.asyncio
    async def test_halt_in_progress_no_penalty(self):
        """Halting in-progress task incurs NO penalty (FR5)."""
        task = create_task(status=TaskStatus.IN_PROGRESS, cluster_id="cluster-1")
        ledger_port = AsyncMock()

        service = TaskConsentService(ledger_port=ledger_port, ...)

        result = await service.halt_task(
            task_id=task.task_id,
            cluster_id="cluster-1",
        )

        assert result.success is True
        emitted_event = ledger_port.append_event.call_args[0][0]
        assert emitted_event.payload["penalty_incurred"] is False

    @pytest.mark.asyncio
    async def test_unauthorized_cluster_rejected(self):
        """Cluster cannot consent on task addressed to another."""
        task = create_task(status=TaskStatus.ROUTED, cluster_id="cluster-other")

        service = TaskConsentService(...)

        with pytest.raises(UnauthorizedConsentError):
            await service.accept_task(
                task_id=task.task_id,
                cluster_id="cluster-1",  # Wrong cluster
            )
```

**Coverage Requirement:** 100% for consent service

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Async/await, type hints |
| pytest | latest | Unit testing |
| pytest-asyncio | latest | Async test support |

### Project Structure Notes

**Alignment:** Creates consent service in `src/application/services/governance/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Service imports ports (dependency injection)
- Service imports domain models
- No direct infrastructure imports

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Golden Rules → Architectural Enforcement]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-2-3]
- [Source: consent-gov-2-1-task-state-machine-domain-model.md] - Dependency
- [Source: consent-gov-2-2-task-activation-request.md] - Dependency

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| FR2 | Cluster can view pending requests | get_pending_requests() |
| FR3 | Cluster can accept request | accept_task() |
| FR4 | Cluster can decline without justification | decline_task() - no justification param |
| FR5 | Cluster can halt without penalty | halt_task() - penalty_incurred=false |
| Golden Rule | Refusal is penalty-free | No standing/reputation schema |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-6 | Hard dependency | Two-phase event emission |
| consent-gov-2-1 | Hard dependency | Task state machine |
| consent-gov-2-2 | Soft dependency | Task activation (creates tasks) |

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

