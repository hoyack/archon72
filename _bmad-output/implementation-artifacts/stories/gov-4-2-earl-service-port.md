# Story GOV-4.2: Define Earl Service Port (Administrative Branch)

Status: pending

## Story

As a **developer**,
I want **an abstract port defining Earl capabilities**,
So that **task execution has clear boundaries**.

## Acceptance Criteria

### AC1: Protocol Implements PermissionEnforcerProtocol

**Given** an `EarlServiceProtocol` is defined in `src/application/ports/earl_service.py`
**When** the protocol is instantiated
**Then** it enforces permission checks via the PermissionEnforcerProtocol
**And** only Archons with `original_rank: Earl` can invoke Earl methods

### AC2: Task Execution Methods

**Given** the Earl's administrative role (FR-GOV-12)
**When** methods are specified
**Then** it includes:
  - `execute_task(task: AegisTaskSpec)` - Execute task within Duke's domain
  - `coordinate_agents(task_id: UUID, agent_ids: list[str])` - Coordinate agents for task
  - `optimize_within_constraints(task_id: UUID)` - Optimize execution within approved constraints
  - `report_execution_result(task_id: UUID, result: ExecutionResult)` - Report task completion

### AC3: Explicitly Excluded Methods

**Given** the Earl's constraints (FR-GOV-13)
**When** the protocol is reviewed
**Then** it explicitly EXCLUDES (documented as comments):
  - `introduce_motion()` - PROHIBITED (King function)
  - `define_execution()` - PROHIBITED (President function)
  - `reinterpret_intent()` - PROHIBITED (FR-GOV-13)
  - `judge_compliance()` - PROHIBITED (Prince function)
  - `own_domain()` - PROHIBITED (Duke function)

### AC4: Domain Model Types

**Given** Earl operations require specific data types
**When** domain models are created
**Then** they include:
  - `ExecutionResult` - Result of task execution with outputs
  - `AgentCoordination` - Agent coordination specification
  - `OptimizationReport` - Report of optimization actions
  - `ExecutionStatus` - Current status of task execution

### AC5: AegisTaskSpec Integration

**Given** Earls execute tasks from President-defined plans
**When** `execute_task()` is called
**Then** it accepts `AegisTaskSpec` (from Epic 9) as input
**And** validates the task spec matches approved plan

### AC6: Duke-Earl Relationship

**Given** Earls operate within Duke-assigned domains
**When** an Earl executes a task
**Then** the task must be within a domain owned by a Duke
**And** constraints from Duke's allocation are enforced

## Tasks / Subtasks

- [ ] Task 1: Create Earl Service Port (AC: 1, 2, 3, 5, 6)
  - [ ] 1.1 Create `src/application/ports/earl_service.py`
  - [ ] 1.2 Define `EarlServiceProtocol` abstract base class
  - [ ] 1.3 Add `execute_task()` abstract method accepting AegisTaskSpec
  - [ ] 1.4 Add `coordinate_agents()` abstract method
  - [ ] 1.5 Add `optimize_within_constraints()` abstract method
  - [ ] 1.6 Add `report_execution_result()` abstract method
  - [ ] 1.7 Add explicitly excluded methods as comments (per FR-GOV-13)
  - [ ] 1.8 Add Duke-Earl relationship validation

- [ ] Task 2: Create Domain Models (AC: 4)
  - [ ] 2.1 Create `ExecutionResult` frozen dataclass with task_id, outputs, metrics, success
  - [ ] 2.2 Create `AgentCoordination` frozen dataclass with agent_ids, roles, task_allocation
  - [ ] 2.3 Create `OptimizationReport` frozen dataclass with actions_taken, improvements
  - [ ] 2.4 Create `ExecutionStatus` Enum (PENDING, EXECUTING, COMPLETED, FAILED)
  - [ ] 2.5 Add `to_dict()` serialization methods to all models

- [ ] Task 3: Unit Tests (AC: 1-6)
  - [ ] 3.1 Create `tests/unit/application/ports/test_earl_service.py`
  - [ ] 3.2 Test domain model creation and immutability
  - [ ] 3.3 Test serialization methods
  - [ ] 3.4 Test permission context construction

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All Earl actions must be witnessed

**Government PRD Requirements:**
- **FR-GOV-12:** Earl Authority - Execute tasks, coordinate agents, optimize within constraints
- **FR-GOV-13:** Earl Constraints - No reinterpretation of intent, no suppression of failure signals

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Port | `src/application/ports/earl_service.py` | Earl Service Protocol |
| Tests | `tests/unit/application/ports/test_earl_service.py` | Unit tests |

**Import Rules (CRITICAL):**
```python
# ALLOWED in application/ports/earl_service.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

# Import permission enforcer and AegisTaskSpec
from src.application.ports.permission_enforcer import (
    PermissionContext,
    PermissionEnforcerProtocol,
)

# FORBIDDEN
from src.infrastructure import ...  # VIOLATION!
from src.api import ...             # VIOLATION!
```

### Permission Matrix Integration

Per `config/permissions/rank-matrix.yaml` v2.0:
```yaml
Earl:
  original_rank: "Earl"
  aegis_rank: "strategic_director"
  branch: "administrative"
  allowed_actions:
    - execute
    - deliberate
    - ratify
  prohibited_actions:
    - introduce_motion
    - define_execution
    - judge
    - witness
  constraints:
    - "Cannot reinterpret intent"
    - "Cannot suppress failure signals"
    - "Execute within Duke-assigned constraints"
```

### Domain Model Design

```python
class ExecutionStatus(Enum):
    """Status of task execution by Earl."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

@dataclass(frozen=True)
class ExecutionResult:
    """Result of task execution by an Earl.

    Per FR-GOV-12: Earls execute tasks and report results.
    Immutable to ensure execution integrity.
    """
    result_id: UUID
    task_id: UUID
    status: ExecutionStatus
    outputs: dict[str, Any]  # Task outputs mapped to success criteria
    metrics: dict[str, float]  # Execution metrics
    success: bool
    executed_by: str  # Earl's Archon ID
    executed_at: datetime
    error: str | None = None

@dataclass(frozen=True)
class AgentCoordination:
    """Coordination specification for agents in task execution."""
    coordination_id: UUID
    task_id: UUID
    agent_ids: tuple[str, ...]  # Aegis agents involved
    roles: dict[str, str]  # agent_id -> role
    task_allocation: dict[str, list[str]]  # agent_id -> subtasks
```

### Duke-Earl Hierarchy

```
Duke (Domain Owner)
├── ExecutionDomain
│   ├── assigned_tasks[]
│   └── constraints[]
└── Earl (Task Executor)
    ├── execute_task()
    ├── coordinate_agents()
    └── optimize_within_constraints()
```

The Earl MUST operate within the Duke's domain constraints:
- Tasks must be from the Duke's assigned_tasks
- Resource usage must fit within Duke's allocation
- Any constraint violation must be reported (per FR-GOV-13: no suppression)

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Epic 4: Duke/Earl Services]
- [Source: config/permissions/rank-matrix.yaml#Earl]
- [Source: docs/archons-base.json#Earl Archons (6)]
- [Source: src/application/ports/permission_enforcer.py#PermissionEnforcerProtocol]
- [Source: Story GOV-4.1#Duke Service Port]
