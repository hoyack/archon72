# Story GOV-8.2: Implement Flow Orchestrator (FR-GOV-23)

Status: pending

## Story

As a **developer**,
I want **a flow orchestrator that coordinates all branch services**,
So that **the governance pipeline is automated**.

## Acceptance Criteria

### AC1: Motion Routing

**Given** a motion enters the pipeline
**When** the orchestrator processes it
**Then** it routes to the correct branch service based on current state:
  - `INTRODUCED` → Conclave Service
  - `RATIFIED` → President Service
  - `PLANNING` → Duke Service
  - `EXECUTING` → Prince Service
  - `JUDGING` → Knight Service
  - `WITNESSING` → Conclave Service (for acknowledgment)

### AC2: State Transition Triggering

**Given** a branch service completes its work
**When** the orchestrator receives completion notification
**Then** it triggers the state machine transition
**And** routes to the next branch service

### AC3: Witnessed Transitions

**Given** all state transitions must be witnessed
**When** the orchestrator triggers a transition
**Then** Knight Witness is notified
**And** the transition includes witness statement

### AC4: Error Handling and Escalation

**Given** a branch service fails or returns error
**When** the orchestrator receives the error
**Then** it does NOT silently ignore the error
**And** escalates to appropriate handler based on error type:
  - Validation error → Return to previous step
  - Permission error → Conclave review
  - System error → Halt and alert

### AC5: Pipeline Visibility

**Given** multiple motions in the pipeline
**When** the pipeline status is queried
**Then** it returns:
  - All active motions with current state
  - Motions blocked or waiting
  - Expected next actions
  - Time in current state

### AC6: Concurrent Motion Handling

**Given** multiple motions can be active simultaneously
**When** the orchestrator processes motions
**Then** each motion has independent state
**And** concurrency is handled safely
**And** no race conditions occur

## Tasks / Subtasks

- [ ] Task 1: Create Flow Orchestrator Port (AC: 1, 2)
  - [ ] 1.1 Create `src/application/ports/flow_orchestrator.py`
  - [ ] 1.2 Define `FlowOrchestratorProtocol` abstract class
  - [ ] 1.3 Add `process_motion(motion_id)` method
  - [ ] 1.4 Add `route_to_branch(motion_id, state)` method
  - [ ] 1.5 Add `handle_completion(motion_id, result)` method

- [ ] Task 2: Create Flow Orchestrator Service (AC: 1, 2, 3, 4)
  - [ ] 2.1 Create `src/application/services/flow_orchestrator_service.py`
  - [ ] 2.2 Implement state-to-service routing
  - [ ] 2.3 Implement completion handling
  - [ ] 2.4 Implement Knight witness integration
  - [ ] 2.5 Implement error escalation

- [ ] Task 3: Branch Service Integration (AC: 1)
  - [ ] 3.1 Integrate King Service (motion introduction)
  - [ ] 3.2 Integrate Conclave Service (deliberation)
  - [ ] 3.3 Integrate President Service (planning)
  - [ ] 3.4 Integrate Duke/Earl Services (execution)
  - [ ] 3.5 Integrate Prince Service (judgment)
  - [ ] 3.6 Integrate Knight Witness Service

- [ ] Task 4: Pipeline Status Tracking (AC: 5)
  - [ ] 4.1 Create `PipelineStatus` domain model
  - [ ] 4.2 Implement `get_pipeline_status()` method
  - [ ] 4.3 Implement `get_motion_status(motion_id)` method
  - [ ] 4.4 Add metrics collection for pipeline health

- [ ] Task 5: Concurrency Handling (AC: 6)
  - [ ] 5.1 Implement motion-level locking
  - [ ] 5.2 Add concurrency tests
  - [ ] 5.3 Handle race conditions in state transitions

- [ ] Task 6: Unit Tests (AC: 1-6)
  - [ ] 6.1 Create `tests/unit/application/services/test_flow_orchestrator.py`
  - [ ] 6.2 Test motion routing
  - [ ] 6.3 Test state transitions
  - [ ] 6.4 Test error handling
  - [ ] 6.5 Test concurrent motions

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All transitions witnessed

**Government PRD Requirements:**
- **FR-GOV-23:** Governance Flow - 7 canonical steps coordinated
- **NFR-GOV-7:** Halt over degrade - Silent failure destroys legitimacy

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Port | `src/application/ports/flow_orchestrator.py` | Orchestrator protocol |
| Application/Service | `src/application/services/flow_orchestrator_service.py` | Implementation |
| Tests | `tests/unit/application/services/test_flow_orchestrator.py` | Unit tests |

### Domain Model Design

```python
@dataclass(frozen=True)
class BranchResult:
    """Result from a branch service completing work."""
    motion_id: UUID
    branch: GovernanceBranch
    success: bool
    output: dict[str, Any]
    next_state: GovernanceState | None
    error: str | None = None

@dataclass(frozen=True)
class PipelineStatus:
    """Current status of the governance pipeline."""
    active_motions: int
    motions_by_state: dict[GovernanceState, int]
    blocked_motions: list[UUID]
    oldest_motion_age: timedelta
    recent_completions: int  # Last 24h
    recent_failures: int  # Last 24h

@dataclass
class MotionPipelineState:
    """Pipeline state for a single motion."""
    motion_id: UUID
    current_state: GovernanceState
    entered_state_at: datetime
    expected_completion: datetime | None
    blocking_issues: list[str]
    next_action: str
```

### State-to-Service Routing Map

```python
STATE_SERVICE_MAP = {
    GovernanceState.INTRODUCED: "conclave_service",  # For deliberation
    GovernanceState.DELIBERATING: "conclave_service",  # Continue deliberation
    GovernanceState.RATIFIED: "president_service",  # For planning
    GovernanceState.PLANNING: "president_service",  # Continue planning
    GovernanceState.EXECUTING: "duke_service",  # For execution
    GovernanceState.JUDGING: "prince_service",  # For compliance
    GovernanceState.WITNESSING: "knight_witness_service",  # For recording
}
```

### Flow Orchestrator Architecture

```
              ┌────────────────────┐
              │  Flow Orchestrator │
              │     Service        │
              └─────────┬──────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────┐   ┌───────────┐   ┌───────────┐
│   State   │   │  Branch   │   │  Knight   │
│  Machine  │   │ Services  │   │ Witness   │
└───────────┘   └───────────┘   └───────────┘
        │               │               │
        │       ┌───────┴───────┐       │
        │       │               │       │
        │       ▼               ▼       │
        │ ┌──────────┐   ┌──────────┐   │
        │ │  King    │   │President │   │
        │ │ Service  │   │ Service  │   │
        │ └──────────┘   └──────────┘   │
        │                               │
        │ ┌──────────┐   ┌──────────┐   │
        │ │  Duke/   │   │ Prince   │   │
        │ │ Earl     │   │ Service  │   │
        │ └──────────┘   └──────────┘   │
        │                               │
        └───────────────────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │  Event Store  │
                └───────────────┘
```

### Error Escalation Strategy

```python
class ErrorEscalationStrategy(Enum):
    """Strategies for handling branch service errors."""
    RETURN_TO_PREVIOUS = "return_to_previous"  # Validation errors
    CONCLAVE_REVIEW = "conclave_review"        # Permission/compliance errors
    HALT_AND_ALERT = "halt_and_alert"          # System errors
    RETRY_WITH_BACKOFF = "retry_with_backoff"  # Transient errors

ERROR_TYPE_MAP = {
    "validation_error": ErrorEscalationStrategy.RETURN_TO_PREVIOUS,
    "permission_error": ErrorEscalationStrategy.CONCLAVE_REVIEW,
    "compliance_error": ErrorEscalationStrategy.CONCLAVE_REVIEW,
    "system_error": ErrorEscalationStrategy.HALT_AND_ALERT,
    "timeout_error": ErrorEscalationStrategy.RETRY_WITH_BACKOFF,
}
```

### Configuration

```yaml
# config/flow-orchestrator.yaml
flow_orchestrator:
  max_concurrent_motions: 100
  state_timeout_hours:
    deliberating: 168  # 7 days
    planning: 72       # 3 days
    executing: 168     # 7 days
    judging: 48        # 2 days
    witnessing: 24     # 1 day
  retry:
    max_attempts: 3
    backoff_seconds: [5, 30, 300]
```

### Event Types

```python
# Event types for orchestrator
MOTION_ROUTED = "MOTION_ROUTED"
BRANCH_COMPLETED = "BRANCH_COMPLETED"
ORCHESTRATOR_ERROR = "ORCHESTRATOR_ERROR"
```

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Story 8.2]
- [Source: docs/new-requirements.md#FR-GOV-23]
- [Source: Story GOV-8.1#Governance State Machine]
- [Source: src/application/ports/king_service.py#KingServiceProtocol]
- [Source: src/application/ports/president_service.py#PresidentServiceProtocol]
- [Source: src/application/ports/prince_service.py#PrinceServiceProtocol]
- [Source: src/application/ports/knight_witness.py#KnightWitnessProtocol]
