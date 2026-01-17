# Story consent-gov-2.4: Task Result Submission

Status: ready-for-dev

---

## Story

As a **Cluster**,
I want **to submit task results and problem reports**,
So that **my work is recorded and issues are surfaced through proper channels**.

---

## Acceptance Criteria

1. **AC1:** Cluster can submit task result report for completed work (FR6)
2. **AC2:** Cluster can submit problem report for an in-progress task (FR7)
3. **AC3:** Result submission transitions task from `in_progress` to `reported`
4. **AC4:** Problem report records issue without state transition (task remains `in_progress`)
5. **AC5:** Event `executive.task.reported` emitted on result submission
6. **AC6:** Event `executive.task.problem_reported` emitted on problem report
7. **AC7:** Result includes structured output matching task spec expectations
8. **AC8:** Problem report includes categorized issue type and description
9. **AC9:** Only assigned Cluster can submit results for a task
10. **AC10:** Unit tests for result and problem submissions

---

## Tasks / Subtasks

- [ ] **Task 1: Create TaskResultPort interface** (AC: 1, 2, 9)
  - [ ] Create `src/application/ports/governance/task_result_port.py`
  - [ ] Define `submit_result()` method for completed work
  - [ ] Define `submit_problem_report()` method for issues
  - [ ] Include Cluster authorization validation

- [ ] **Task 2: Create TaskResult domain model** (AC: 7)
  - [ ] Create `src/domain/governance/task_result.py`
  - [ ] Define `TaskResult` value object with structured output
  - [ ] Define result validation against task spec
  - [ ] Include timestamp and Cluster attribution

- [ ] **Task 3: Create ProblemReport domain model** (AC: 8)
  - [ ] Define `ProblemReport` value object
  - [ ] Define `ProblemCategory` enum (e.g., BLOCKED, UNCLEAR_SPEC, RESOURCE_UNAVAILABLE)
  - [ ] Include description field and timestamp
  - [ ] Include Cluster attribution

- [ ] **Task 4: Implement TaskResultService** (AC: 1, 2, 3, 4)
  - [ ] Create `src/application/services/governance/task_result_service.py`
  - [ ] Implement `submit_result()` - validate in_progress, transition to reported
  - [ ] Implement `submit_problem_report()` - record problem, keep in_progress
  - [ ] Validate Cluster is assigned worker

- [ ] **Task 5: Implement result submission** (AC: 1, 3, 5, 7)
  - [ ] Validate task is in IN_PROGRESS state
  - [ ] Validate Cluster is the assigned worker
  - [ ] Validate result structure matches task spec expectations
  - [ ] Transition task to REPORTED state
  - [ ] Emit `executive.task.reported` event with result payload
  - [ ] Use two-phase event emission

- [ ] **Task 6: Implement problem report submission** (AC: 2, 4, 6, 8)
  - [ ] Validate task is in IN_PROGRESS state
  - [ ] Validate Cluster is the assigned worker
  - [ ] Create ProblemReport with category and description
  - [ ] Do NOT transition state (task remains IN_PROGRESS)
  - [ ] Emit `executive.task.problem_reported` event
  - [ ] Use two-phase event emission
  - [ ] Problem report may trigger escalation to Duke (future story)

- [ ] **Task 7: Integrate with Task State Machine** (AC: 3, 4)
  - [ ] Add REPORTED to TaskStatus enum if not present
  - [ ] Add valid transition: IN_PROGRESS → REPORTED
  - [ ] Verify problem reports don't affect state

- [ ] **Task 8: Write comprehensive unit tests** (AC: 10)
  - [ ] Test submit_result transitions to REPORTED
  - [ ] Test submit_problem_report keeps IN_PROGRESS
  - [ ] Test result validation against task spec
  - [ ] Test problem report captures category and description
  - [ ] Test unauthorized Cluster submission rejected
  - [ ] Test submission from wrong state rejected
  - [ ] Test events emitted correctly

---

## Documentation Checklist

- [ ] Architecture docs updated (result submission workflow)
- [ ] Inline comments explaining result vs problem report distinction
- [ ] N/A - API docs (service layer)
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Result vs Problem Report:**
```
Result Submission:
  - IN_PROGRESS → REPORTED (state transition)
  - Task is considered "done" from Cluster perspective
  - Awaits aggregation/completion by Earl/Duke

Problem Report:
  - IN_PROGRESS → IN_PROGRESS (no state change)
  - Task continues, but issue is recorded
  - May trigger Duke escalation (FR not in this story)
```

**Event Patterns:**
```python
# Result submission event
{
    "event_type": "executive.task.reported",
    "payload": {
        "task_id": "uuid",
        "cluster_id": "uuid",
        "result": { ... },  # Structured output
        "submitted_at": "timestamp"
    }
}

# Problem report event
{
    "event_type": "executive.task.problem_reported",
    "payload": {
        "task_id": "uuid",
        "cluster_id": "uuid",
        "problem": {
            "category": "BLOCKED",
            "description": "...",
            "reported_at": "timestamp"
        }
    }
}
```

### Task State Transitions (Updated)

```
IN_PROGRESS → REPORTED (via submit_result)
IN_PROGRESS → IN_PROGRESS (via submit_problem_report - no change)
IN_PROGRESS → QUARANTINED (via halt - from story 2-3)
```

### Domain Model Sketch

```python
@dataclass(frozen=True)
class TaskResult:
    """Immutable result of completed task work."""
    task_id: UUID
    cluster_id: UUID
    output: dict[str, Any]  # Structured output per task spec
    submitted_at: datetime

    def validate_against_spec(self, task_spec: TaskSpec) -> None:
        """Validates result structure matches spec expectations."""
        ...


class ProblemCategory(Enum):
    BLOCKED = "blocked"              # External blocker
    UNCLEAR_SPEC = "unclear_spec"    # Task spec ambiguous
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    TECHNICAL_ISSUE = "technical_issue"
    OTHER = "other"


@dataclass(frozen=True)
class ProblemReport:
    """Immutable problem report for in-progress task."""
    task_id: UUID
    cluster_id: UUID
    category: ProblemCategory
    description: str
    reported_at: datetime
```

### Service Implementation Sketch

```python
class TaskResultService:
    """Handles task result and problem report submissions."""

    def __init__(
        self,
        task_state_port: TaskStatePort,
        event_emitter: TwoPhaseEventEmitter,
        time_authority: TimeAuthority,
    ):
        self._task_state = task_state_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def submit_result(
        self,
        task_id: UUID,
        cluster_id: UUID,
        output: dict[str, Any],
    ) -> TaskResult:
        """Submit completed task result."""
        # 1. Get task and validate state
        task = await self._task_state.get_task(task_id)
        if task.status != TaskStatus.IN_PROGRESS:
            raise IllegalStateTransitionError(
                f"Cannot submit result: task is {task.status}"
            )

        # 2. Validate Cluster is assigned worker
        if task.assigned_cluster_id != cluster_id:
            raise UnauthorizedError("Only assigned Cluster can submit")

        # 3. Create result
        result = TaskResult(
            task_id=task_id,
            cluster_id=cluster_id,
            output=output,
            submitted_at=self._time.now(),
        )

        # 4. Two-phase event emission
        async with self._event_emitter.two_phase(
            event_type="executive.task.reported",
            payload={"task_id": str(task_id), "result": output},
        ):
            # 5. Transition state
            await self._task_state.transition(
                task_id=task_id,
                to_status=TaskStatus.REPORTED,
            )

        return result

    async def submit_problem_report(
        self,
        task_id: UUID,
        cluster_id: UUID,
        category: ProblemCategory,
        description: str,
    ) -> ProblemReport:
        """Submit problem report without state change."""
        # 1. Validate task and Cluster
        task = await self._task_state.get_task(task_id)
        if task.status != TaskStatus.IN_PROGRESS:
            raise IllegalStateTransitionError(
                f"Cannot report problem: task is {task.status}"
            )
        if task.assigned_cluster_id != cluster_id:
            raise UnauthorizedError("Only assigned Cluster can report")

        # 2. Create problem report
        report = ProblemReport(
            task_id=task_id,
            cluster_id=cluster_id,
            category=category,
            description=description,
            reported_at=self._time.now(),
        )

        # 3. Emit event (NO state transition)
        await self._event_emitter.emit(
            event_type="executive.task.problem_reported",
            payload={
                "task_id": str(task_id),
                "category": category.value,
                "description": description,
            },
        )

        return report
```

### Test Patterns

```python
class TestTaskResultService:
    """Unit tests for task result submission."""

    async def test_submit_result_transitions_to_reported(
        self,
        result_service: TaskResultService,
        in_progress_task: Task,
    ):
        """Result submission transitions task to REPORTED."""
        result = await result_service.submit_result(
            task_id=in_progress_task.id,
            cluster_id=in_progress_task.assigned_cluster_id,
            output={"completion": "done"},
        )

        task = await result_service._task_state.get_task(in_progress_task.id)
        assert task.status == TaskStatus.REPORTED
        assert result.task_id == in_progress_task.id

    async def test_problem_report_keeps_in_progress(
        self,
        result_service: TaskResultService,
        in_progress_task: Task,
    ):
        """Problem report does NOT change task state."""
        report = await result_service.submit_problem_report(
            task_id=in_progress_task.id,
            cluster_id=in_progress_task.assigned_cluster_id,
            category=ProblemCategory.BLOCKED,
            description="External API unavailable",
        )

        task = await result_service._task_state.get_task(in_progress_task.id)
        assert task.status == TaskStatus.IN_PROGRESS  # Unchanged!
        assert report.category == ProblemCategory.BLOCKED

    async def test_unauthorized_cluster_rejected(
        self,
        result_service: TaskResultService,
        in_progress_task: Task,
    ):
        """Only assigned Cluster can submit results."""
        wrong_cluster_id = uuid4()

        with pytest.raises(UnauthorizedError):
            await result_service.submit_result(
                task_id=in_progress_task.id,
                cluster_id=wrong_cluster_id,
                output={"result": "data"},
            )

    async def test_submit_from_wrong_state_rejected(
        self,
        result_service: TaskResultService,
        accepted_task: Task,  # Not IN_PROGRESS
    ):
        """Cannot submit result if task not IN_PROGRESS."""
        with pytest.raises(IllegalStateTransitionError):
            await result_service.submit_result(
                task_id=accepted_task.id,
                cluster_id=accepted_task.assigned_cluster_id,
                output={"result": "data"},
            )
```

### Dependencies

- **Depends on:** consent-gov-2-1 (TaskStatus enum), consent-gov-1-6 (TwoPhaseEventEmitter)
- **Enables:** consent-gov-2-5 (TTL auto-transitions may reference REPORTED state)

### References

- FR6: Cluster can submit a task result report
- FR7: Cluster can submit a problem report for an in-progress task
- governance-architecture.md: Task State Machine, Event vocabulary
