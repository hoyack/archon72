# Story GOV-4.1: Define Duke Service Port (Administrative Branch)

Status: pending

## Story

As a **developer**,
I want **an abstract port defining Duke capabilities**,
So that **domain ownership has clear boundaries**.

## Acceptance Criteria

### AC1: Protocol Implements PermissionEnforcerProtocol

**Given** a `DukeServiceProtocol` is defined in `src/application/ports/duke_service.py`
**When** the protocol is instantiated
**Then** it enforces permission checks via the PermissionEnforcerProtocol
**And** only Archons with `original_rank: Duke` can invoke Duke methods

### AC2: Domain Ownership Methods

**Given** the Duke's administrative role (FR-GOV-11)
**When** methods are specified
**Then** it includes:
  - `own_domain(domain_id: str)` - Take ownership of execution domain
  - `allocate_resources(task_id: UUID, resources: ResourceAllocation)` - Allocate resources within domain
  - `track_progress(task_id: UUID)` - Track task execution progress
  - `report_status(task_id: UUID)` - Report execution status to governance pipeline

### AC3: Explicitly Excluded Methods

**Given** the Duke's constraints (FR-GOV-13)
**When** the protocol is reviewed
**Then** it explicitly EXCLUDES (documented as comments):
  - `introduce_motion()` - PROHIBITED (King function)
  - `define_execution()` - PROHIBITED (President function)
  - `reinterpret_intent()` - PROHIBITED (FR-GOV-13)
  - `judge_compliance()` - PROHIBITED (Prince function)

### AC4: Domain Model Types

**Given** Duke operations require specific data types
**When** domain models are created
**Then** they include:
  - `ExecutionDomain` - Domain owned by Duke with boundaries
  - `ResourceAllocation` - Resource allocation specification
  - `DomainOwnershipResult` - Result of taking domain ownership
  - `ProgressReport` - Progress tracking data
  - `StatusReport` - Execution status with metrics

### AC5: Permission Context Integration

**Given** the permission enforcer uses `original_rank` for lookups
**When** a Duke method is called
**Then** the context includes `original_rank: "Duke"` from archons-base.json
**And** allowed actions are validated against rank-matrix.yaml

## Tasks / Subtasks

- [ ] Task 1: Create Duke Service Port (AC: 1, 2, 3, 5)
  - [ ] 1.1 Create `src/application/ports/duke_service.py`
  - [ ] 1.2 Define `DukeServiceProtocol` abstract base class
  - [ ] 1.3 Add `own_domain()` abstract method with docstring
  - [ ] 1.4 Add `allocate_resources()` abstract method
  - [ ] 1.5 Add `track_progress()` abstract method
  - [ ] 1.6 Add `report_status()` abstract method
  - [ ] 1.7 Add explicitly excluded methods as comments (per FR-GOV-13)
  - [ ] 1.8 Add permission context integration with PermissionEnforcerProtocol

- [ ] Task 2: Create Domain Models (AC: 4)
  - [ ] 2.1 Create `ExecutionDomain` frozen dataclass with domain_id, boundaries, assigned_tasks
  - [ ] 2.2 Create `ResourceAllocation` frozen dataclass with resource_type, amount, constraints
  - [ ] 2.3 Create `DomainOwnershipResult` dataclass with success, domain, error
  - [ ] 2.4 Create `ProgressReport` frozen dataclass with task_id, percent_complete, metrics
  - [ ] 2.5 Create `StatusReport` frozen dataclass with task_id, status, updated_at, details
  - [ ] 2.6 Add `to_dict()` serialization methods to all models

- [ ] Task 3: Unit Tests (AC: 1-5)
  - [ ] 3.1 Create `tests/unit/application/ports/test_duke_service.py`
  - [ ] 3.2 Test domain model creation and immutability
  - [ ] 3.3 Test serialization methods
  - [ ] 3.4 Test permission context construction

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All Duke actions must be witnessed

**Government PRD Requirements:**
- **FR-GOV-11:** Duke Authority - Own execution domains, allocate resources, track progress, report status
- **FR-GOV-13:** Duke Constraints - No reinterpretation of intent, no suppression of failure signals

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Port | `src/application/ports/duke_service.py` | Duke Service Protocol |
| Tests | `tests/unit/application/ports/test_duke_service.py` | Unit tests |

**Import Rules (CRITICAL):**
```python
# ALLOWED in application/ports/duke_service.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

# Import permission enforcer for integration
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
Duke:
  original_rank: "Duke"
  aegis_rank: "senior_director"
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
    - "Must report execution status"
```

### Domain Model Design

```python
@dataclass(frozen=True)
class ExecutionDomain:
    """A domain owned by a Duke for task execution.

    Per FR-GOV-11: Dukes own execution domains and allocate resources.
    """
    domain_id: str
    name: str
    description: str
    boundaries: tuple[str, ...]  # Scope constraints
    assigned_tasks: tuple[UUID, ...] = field(default_factory=tuple)
    owner_archon_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass(frozen=True)
class ResourceAllocation:
    """Resource allocation within a Duke's domain.

    Immutable to ensure allocation integrity.
    """
    allocation_id: UUID
    task_id: UUID
    resource_type: str  # e.g., "compute", "memory", "agents"
    amount: int
    constraints: tuple[str, ...] = field(default_factory=tuple)
    allocated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Epic 4: Duke/Earl Services]
- [Source: config/permissions/rank-matrix.yaml#Duke]
- [Source: docs/archons-base.json#Duke Archons (23)]
- [Source: src/application/ports/permission_enforcer.py#PermissionEnforcerProtocol]
- [Source: src/application/ports/king_service.py#Protocol pattern reference]
