# Story consent-gov-2.2: Task Activation Request

Status: ready-for-dev

---

## Story

As an **Earl**,
I want **to create task activation requests for Clusters**,
So that **work can be offered to human participants with full transparency and consent-based acceptance**.

---

## Acceptance Criteria

1. **AC1:** Earl can create activation request with task details (description, requirements, expected outcomes)
2. **AC2:** Activation request includes configurable TTL (default 72h)
3. **AC3:** Activation request transitions task from `authorized` → `activated` → `routed`
4. **AC4:** Request content MUST pass through Coercion Filter before routing (FR21)
5. **AC5:** Request routed to Cluster via async protocol (email) per NFR-INT-01
6. **AC6:** Event `executive.task.activated` emitted to ledger on activation
7. **AC7:** Event `executive.task.routed` emitted to ledger on routing
8. **AC8:** Earl can view task state and history (FR12)
9. **AC9:** `TaskActivationService` encapsulates the activation workflow
10. **AC10:** Unit tests for activation request creation, filtering, and routing

---

## Tasks / Subtasks

- [ ] **Task 1: Create task activation domain models** (AC: 1, 2)
  - [ ] Create `src/domain/governance/task/task_activation_request.py`
  - [ ] Define `TaskActivationRequest` dataclass
  - [ ] Include task details: description, requirements, expected_outcomes
  - [ ] Include TTL configuration with default 72h
  - [ ] Add validation for required fields

- [ ] **Task 2: Create TaskActivationPort interface** (AC: 5, 9)
  - [ ] Create `src/application/ports/governance/task_activation_port.py`
  - [ ] Define `create_activation()` method
  - [ ] Define `route_to_cluster()` method
  - [ ] Define `get_task_state()` method for Earl visibility

- [ ] **Task 3: Implement TaskActivationService** (AC: 3, 4, 9)
  - [ ] Create `src/application/services/governance/task_activation_service.py`
  - [ ] Implement `create_activation_request()` method
  - [ ] Integrate with `CoercionFilterService` for content validation
  - [ ] Implement state transitions (authorized → activated → routed)
  - [ ] Use two-phase event emission (from Epic 1)

- [ ] **Task 4: Implement Coercion Filter integration** (AC: 4)
  - [ ] Create filter request for activation content
  - [ ] Handle `accept`, `reject`, `block` outcomes
  - [ ] Return filter result to Earl for review (FR19)
  - [ ] Block routing if filter rejects/blocks

- [ ] **Task 5: Implement async routing** (AC: 5)
  - [ ] Create `ParticipantMessagePort` integration
  - [ ] Route via email (async protocol)
  - [ ] Use `FilteredContent` type (not raw strings)
  - [ ] Log routing attempt to ledger

- [ ] **Task 6: Implement event emission** (AC: 6, 7)
  - [ ] Emit `executive.task.activated` on activation
  - [ ] Emit `executive.task.routed` on successful routing
  - [ ] Include activation details in event payload
  - [ ] Use two-phase emission pattern

- [ ] **Task 7: Implement Earl task visibility** (AC: 8)
  - [ ] Create `get_task_state()` method
  - [ ] Create `get_task_history()` method
  - [ ] Query from task_states projection
  - [ ] Return complete state and event history

- [ ] **Task 8: Write comprehensive unit tests** (AC: 10)
  - [ ] Test activation request creation with valid data
  - [ ] Test TTL configuration (default and custom)
  - [ ] Test Coercion Filter integration (accept, reject, block)
  - [ ] Test state transitions
  - [ ] Test event emission
  - [ ] Test Earl task visibility

---

## Documentation Checklist

- [ ] Architecture docs updated (task activation workflow)
- [ ] Inline comments explaining filter integration
- [ ] N/A - API docs (service layer)
- [ ] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements task activation with mandatory Coercion Filter routing.

**Filter Pipeline Placement (Locked):**
```
Earl drafts activation request
        ↓
   [Coercion Filter] ← MANDATORY (no bypass path exists)
        ↓
Filter decision logged → Ledger
        ↓
Request sent to Cluster (if accepted/transformed)
```

**What Goes Through Filter:**

| Content Type | Filtered | Rationale |
|--------------|----------|-----------|
| Task activation requests | Yes | Primary coercion vector |

**Async Protocol (NFR-INT-01):**
> Async protocol (email) handles all Earl→Cluster communication

### TaskActivationRequest Domain Model

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

@dataclass(frozen=True)
class TaskActivationRequest:
    """Request to activate a task for a Cluster.

    Constitutional Guarantee:
    - Content MUST pass through Coercion Filter
    - Cannot be sent without FilteredContent wrapper
    """
    request_id: UUID
    task_id: UUID
    earl_id: str
    cluster_id: str
    description: str
    requirements: list[str]
    expected_outcomes: list[str]
    ttl: timedelta = timedelta(hours=72)
    created_at: datetime

    # Filter-related fields (set after filtering)
    filtered_content: "FilteredContent | None" = None
    filter_decision_id: UUID | None = None

@dataclass(frozen=True)
class TaskActivationResult:
    """Result of task activation attempt."""
    success: bool
    task_state: "TaskState"
    filter_outcome: str  # "accepted", "transformed", "rejected", "blocked"
    filter_decision_id: UUID
    routing_status: str  # "routed", "pending_rewrite", "blocked"
    message: str
```

### TaskActivationService

```python
from typing import Protocol
from uuid import UUID

class TaskActivationService:
    """Service for creating and routing task activation requests.

    Constitutional Guarantees:
    - All content passes through Coercion Filter
    - No bypass path exists for participant messages
    - Events emitted via two-phase pattern
    """

    def __init__(
        self,
        task_state_port: TaskStatePort,
        coercion_filter: CoercionFilterPort,
        participant_message_port: ParticipantMessagePort,
        ledger_port: GovernanceLedgerPort,
        two_phase_emitter: TwoPhaseEventEmitterPort,
    ) -> None:
        self._task_state = task_state_port
        self._filter = coercion_filter
        self._messenger = participant_message_port
        self._ledger = ledger_port
        self._emitter = two_phase_emitter

    async def create_activation_request(
        self,
        earl_id: str,
        cluster_id: str,
        description: str,
        requirements: list[str],
        expected_outcomes: list[str],
        ttl: timedelta = timedelta(hours=72),
    ) -> TaskActivationResult:
        """Create and process a task activation request.

        Flow:
        1. Create task in AUTHORIZED state
        2. Transition to ACTIVATED
        3. Filter content through Coercion Filter
        4. If accepted/transformed: route to Cluster
        5. If rejected: return to Earl for rewrite
        6. If blocked: log violation, do not route

        Returns:
            TaskActivationResult with filter outcome and routing status
        """
        async with TwoPhaseExecution(
            emitter=self._emitter,
            operation_type="task.activate",
            actor_id=earl_id,
            target_entity_id=str(task_id),
            intent_payload={"cluster_id": cluster_id},
        ) as execution:
            # Create task
            task = await self._create_task(earl_id, cluster_id, ttl)

            # Transition to ACTIVATED
            task = await self._transition_task(
                task, TaskStatus.ACTIVATED, earl_id
            )

            # Filter content
            filter_result = await self._filter.filter_content(
                content_type="task_activation_request",
                originator_id=earl_id,
                content={
                    "description": description,
                    "requirements": requirements,
                    "expected_outcomes": expected_outcomes,
                },
            )

            # Handle filter outcome
            if filter_result.outcome in ("accepted", "transformed"):
                # Route to Cluster
                await self._route_to_cluster(
                    task, cluster_id, filter_result.filtered_content
                )
                execution.set_result({"routed": True})
                return TaskActivationResult(
                    success=True,
                    task_state=task,
                    filter_outcome=filter_result.outcome,
                    filter_decision_id=filter_result.decision_id,
                    routing_status="routed",
                    message="Task activation routed to Cluster",
                )
            elif filter_result.outcome == "rejected":
                execution.set_result({"routed": False, "reason": "rejected"})
                return TaskActivationResult(
                    success=False,
                    task_state=task,
                    filter_outcome="rejected",
                    filter_decision_id=filter_result.decision_id,
                    routing_status="pending_rewrite",
                    message="Content rejected by filter. Please revise.",
                )
            else:  # blocked
                execution.set_result({"routed": False, "reason": "blocked"})
                return TaskActivationResult(
                    success=False,
                    task_state=task,
                    filter_outcome="blocked",
                    filter_decision_id=filter_result.decision_id,
                    routing_status="blocked",
                    message="Content blocked due to violation.",
                )

    async def _route_to_cluster(
        self,
        task: TaskState,
        cluster_id: str,
        content: FilteredContent,
    ) -> None:
        """Route activation request to Cluster via async protocol."""
        # Transition to ROUTED
        task = await self._transition_task(
            task, TaskStatus.ROUTED, "system"
        )

        # Send via participant message port (email)
        await self._messenger.send_to_participant(
            participant_id=cluster_id,
            content=content,  # MUST be FilteredContent
            message_type="task_activation",
            metadata={"task_id": str(task.task_id)},
        )

        # Emit routed event
        await self._emit_event(
            "executive.task.routed",
            task,
            {"cluster_id": cluster_id},
        )
```

### ParticipantMessagePort Integration

```python
class ParticipantMessagePort(Protocol):
    """All participant-facing messages go through this port.

    Constitutional Guarantee:
    - Only accepts FilteredContent (not raw strings)
    - Type system prevents bypass
    """

    async def send_to_participant(
        self,
        participant_id: str,
        content: FilteredContent,  # MUST be FilteredContent, not raw
        message_type: str,
        metadata: dict,
    ) -> None:
        """Send filtered content to participant via async protocol."""
        ...
```

### Event Payloads

**executive.task.activated:**
```json
{
  "metadata": {
    "event_id": "uuid",
    "event_type": "executive.task.activated",
    "schema_version": "1.0.0",
    "timestamp": "2026-01-16T00:00:00Z",
    "actor_id": "earl-agares"
  },
  "payload": {
    "task_id": "uuid",
    "earl_id": "earl-agares",
    "cluster_id": "cluster-xyz",
    "ttl_hours": 72,
    "description_hash": "blake3:...",  // Not raw content
    "filter_decision_id": "uuid"
  }
}
```

**executive.task.routed:**
```json
{
  "metadata": {
    "event_id": "uuid",
    "event_type": "executive.task.routed",
    "schema_version": "1.0.0",
    "timestamp": "2026-01-16T00:00:00Z",
    "actor_id": "system"
  },
  "payload": {
    "task_id": "uuid",
    "cluster_id": "cluster-xyz",
    "routing_protocol": "email",
    "filter_outcome": "accepted"
  }
}
```

### Earl Task Visibility (FR12)

```python
async def get_task_state(self, task_id: UUID, earl_id: str) -> TaskStateView:
    """Get current task state for Earl.

    Returns:
        TaskStateView with current state and metadata
    """
    task = await self._task_state.get_task(task_id)

    # Verify Earl owns this task
    if task.earl_id != earl_id:
        raise UnauthorizedAccessError(f"Earl {earl_id} does not own task {task_id}")

    return TaskStateView(
        task_id=task.task_id,
        current_status=task.current_status,
        cluster_id=task.cluster_id,
        created_at=task.created_at,
        state_entered_at=task.state_entered_at,
        ttl=task.ttl,
        ttl_remaining=self._calculate_ttl_remaining(task),
    )

async def get_task_history(self, task_id: UUID, earl_id: str) -> list[TaskEvent]:
    """Get task event history for Earl.

    Returns:
        List of events related to this task
    """
    # Verify ownership first
    task = await self._task_state.get_task(task_id)
    if task.earl_id != earl_id:
        raise UnauthorizedAccessError(f"Earl {earl_id} does not own task {task_id}")

    return await self._ledger.read_events(
        event_type_pattern="executive.task.*",
        payload_filter={"task_id": str(task_id)},
    )
```

### Existing Patterns to Follow

**Reference:** `src/application/services/governance/two_phase_event_emitter.py` (from story 1-6)

Two-phase emission ensures intent is recorded before operation.

**Reference:** `src/domain/governance/task/task_state.py` (from story 2-1)

Task state machine for transition validation.

### Dependency on Previous Stories

This story depends on:
- `consent-gov-1-1`: Event infrastructure
- `consent-gov-1-2`: Ledger port for events
- `consent-gov-1-6`: Two-phase event emission
- `consent-gov-2-1`: Task state machine

**Import:**
```python
from src.domain.governance.task.task_state import TaskState, TaskStatus
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.application.services.governance.two_phase_event_emitter import TwoPhaseExecution
```

### Source Tree Components

**New Files:**
```
src/domain/governance/task/
└── task_activation_request.py    # TaskActivationRequest, TaskActivationResult

src/application/ports/governance/
├── task_activation_port.py       # TaskActivationPort protocol
└── participant_message_port.py   # ParticipantMessagePort protocol

src/application/services/governance/
└── task_activation_service.py    # TaskActivationService
```

**Test Files:**
```
tests/unit/domain/governance/task/
└── test_task_activation_request.py

tests/unit/application/services/governance/
└── test_task_activation_service.py
```

### Technical Requirements

**Python Patterns (CRITICAL):**
- Frozen dataclasses for domain models
- `FilteredContent` type enforced (no raw strings)
- Two-phase event emission for all operations
- Type hints on ALL functions (mypy --strict must pass)

**Security Requirements:**
- Content MUST pass through Coercion Filter
- No bypass path exists
- Filter decision logged to ledger
- Raw content hashed, not stored in events

### Testing Standards

**Unit Test Patterns:**
```python
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import timedelta

class TestTaskActivationService:
    @pytest.mark.asyncio
    async def test_successful_activation_routes_to_cluster(self):
        """Accepted content is routed to Cluster."""
        filter_port = AsyncMock()
        filter_port.filter_content.return_value = FilterResult(
            outcome="accepted",
            filtered_content=FilteredContent("Test task"),
            decision_id=uuid4(),
        )

        messenger = AsyncMock()
        service = TaskActivationService(
            task_state_port=AsyncMock(),
            coercion_filter=filter_port,
            participant_message_port=messenger,
            ledger_port=AsyncMock(),
            two_phase_emitter=AsyncMock(),
        )

        result = await service.create_activation_request(
            earl_id="earl-1",
            cluster_id="cluster-1",
            description="Test task",
            requirements=["Req 1"],
            expected_outcomes=["Outcome 1"],
        )

        assert result.success is True
        assert result.routing_status == "routed"
        messenger.send_to_participant.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejected_content_not_routed(self):
        """Rejected content returns to Earl for rewrite."""
        filter_port = AsyncMock()
        filter_port.filter_content.return_value = FilterResult(
            outcome="rejected",
            filtered_content=None,
            decision_id=uuid4(),
            rejection_reason="Contains urgency language",
        )

        messenger = AsyncMock()
        service = TaskActivationService(...)

        result = await service.create_activation_request(...)

        assert result.success is False
        assert result.routing_status == "pending_rewrite"
        messenger.send_to_participant.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocked_content_not_routed(self):
        """Blocked content logs violation, does not route."""
        filter_port = AsyncMock()
        filter_port.filter_content.return_value = FilterResult(
            outcome="blocked",
            filtered_content=None,
            decision_id=uuid4(),
            violations=["coercion.threat"],
        )

        messenger = AsyncMock()
        service = TaskActivationService(...)

        result = await service.create_activation_request(...)

        assert result.success is False
        assert result.routing_status == "blocked"
        messenger.send_to_participant.assert_not_called()
```

**Coverage Requirement:** 90%+ for service layer

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Async/await, type hints |
| pytest | latest | Unit testing |
| pytest-asyncio | latest | Async test support |

### Project Structure Notes

**Alignment:** Creates task activation service in `src/application/services/governance/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Service imports ports (dependency injection)
- Service imports domain models
- No direct infrastructure imports

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Filter Pipeline Placement (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Routing Architecture (Locked)]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-2-2]
- [Source: consent-gov-2-1-task-state-machine-domain-model.md] - Dependency
- [Source: consent-gov-1-6-two-phase-event-emission.md] - Dependency

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| FR1 | Earl can create task activation requests | TaskActivationService |
| FR12 | Earl can view task state and history | get_task_state(), get_task_history() |
| FR21 | All messages through Coercion Filter | Mandatory filter integration |
| NFR-INT-01 | Async protocol for Earl→Cluster | ParticipantMessagePort (email) |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-1 | Hard dependency | Event infrastructure |
| consent-gov-1-2 | Hard dependency | Ledger port |
| consent-gov-1-6 | Hard dependency | Two-phase event emission |
| consent-gov-2-1 | Hard dependency | Task state machine |
| consent-gov-3-2 | Soft dependency | Coercion Filter service (can mock) |

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

