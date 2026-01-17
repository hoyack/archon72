# Story GOV-8.1: Define Governance State Machine (FR-GOV-23)

Status: pending

## Story

As a **developer**,
I want **a state machine enforcing the 7-step flow**,
So that **governance progresses in correct order**.

## Acceptance Criteria

### AC1: State Definition

**Given** the canonical 7-step flow (PRD §6)
**When** states are defined
**Then** they include:
  1. `INTRODUCED` - King introduced motion
  2. `DELIBERATING` - Conclave debating
  3. `RATIFIED` - Conclave approved (or REJECTED)
  4. `PLANNING` - President translating to HOW
  5. `EXECUTING` - Duke/Earl executing
  6. `JUDGING` - Prince evaluating compliance
  7. `WITNESSING` - Knight recording outcome
  8. `ACKNOWLEDGED` - Conclave acknowledged witness statement

### AC2: Transition Rules

**Given** valid state transitions
**When** the state machine is configured
**Then** only these transitions are allowed:
  - `INTRODUCED → DELIBERATING` (King → Conclave)
  - `DELIBERATING → RATIFIED | REJECTED` (Conclave vote)
  - `RATIFIED → PLANNING` (Conclave → President)
  - `PLANNING → EXECUTING` (President → Duke/Earl)
  - `EXECUTING → JUDGING` (Duke/Earl → Prince)
  - `JUDGING → WITNESSING` (Prince → Knight)
  - `WITNESSING → ACKNOWLEDGED` (Knight → Conclave)

### AC3: Invalid Transition Rejection

**Given** an invalid transition is attempted
**When** the state machine processes it
**Then** the transition is rejected
**And** a violation event is triggered
**And** the rejection includes the attempted and expected states

### AC4: State Persistence

**Given** motion state changes
**When** a transition occurs
**Then** the new state is persisted in the event store
**And** the state change is hash-chained
**And** previous state is recorded for audit

### AC5: Motion State Query

**Given** a motion ID
**When** the current state is queried
**Then** it returns:
  - Current state
  - Time in state
  - Previous state history
  - Available transitions

### AC6: Terminal State Handling

**Given** terminal states (REJECTED, ACKNOWLEDGED)
**When** a motion reaches a terminal state
**Then** no further transitions are allowed
**And** the motion is marked as complete

## Tasks / Subtasks

- [ ] Task 1: Create State Machine Domain Models (AC: 1, 2)
  - [ ] 1.1 Create `GovernanceState` Enum with all 8 states
  - [ ] 1.2 Create `StateTransition` frozen dataclass
  - [ ] 1.3 Create `TransitionRule` dataclass with from_state, to_state, guard
  - [ ] 1.4 Create `MotionStateRecord` frozen dataclass

- [ ] Task 2: Create State Machine Port (AC: 2, 3, 5)
  - [ ] 2.1 Create `src/application/ports/governance_state_machine.py`
  - [ ] 2.2 Define `GovernanceStateMachineProtocol` abstract class
  - [ ] 2.3 Add `transition(motion_id, to_state)` method
  - [ ] 2.4 Add `get_current_state(motion_id)` method
  - [ ] 2.5 Add `get_available_transitions(motion_id)` method
  - [ ] 2.6 Add `can_transition(motion_id, to_state)` method

- [ ] Task 3: Create State Machine Adapter (AC: 2, 3, 6)
  - [ ] 3.1 Create `src/infrastructure/adapters/governance/governance_state_machine_adapter.py`
  - [ ] 3.2 Implement transition rule validation
  - [ ] 3.3 Implement invalid transition rejection
  - [ ] 3.4 Implement terminal state handling

- [ ] Task 4: Event Store Integration (AC: 4)
  - [ ] 4.1 Define `STATE_TRANSITION` event type
  - [ ] 4.2 Implement state transition event creation
  - [ ] 4.3 Ensure hash chain inclusion
  - [ ] 4.4 Add Knight witnessing for transitions

- [ ] Task 5: Unit Tests (AC: 1-6)
  - [ ] 5.1 Create `tests/unit/infrastructure/adapters/governance/test_governance_state_machine.py`
  - [ ] 5.2 Test valid transitions
  - [ ] 5.3 Test invalid transition rejection
  - [ ] 5.4 Test terminal state handling
  - [ ] 5.5 Test state query methods

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All state changes witnessed

**Government PRD Requirements:**
- **FR-GOV-23:** Governance Flow - 7 canonical steps; No step may be skipped, no role may be collapsed
- **NFR-GOV-6:** Legitimacy requires visible procedure and recorded consequence

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Port | `src/application/ports/governance_state_machine.py` | State machine protocol |
| Infrastructure/Adapter | `src/infrastructure/adapters/governance/governance_state_machine_adapter.py` | Implementation |
| Tests | `tests/unit/infrastructure/adapters/governance/test_governance_state_machine.py` | Unit tests |

### Domain Model Design

```python
class GovernanceState(Enum):
    """States in the 7-step governance flow.

    Per PRD §6: No step may be skipped.
    """
    # Step 1: King introduces motion
    INTRODUCED = "introduced"

    # Step 2: Conclave deliberates
    DELIBERATING = "deliberating"

    # Step 2b: Conclave outcome
    RATIFIED = "ratified"
    REJECTED = "rejected"  # Terminal

    # Step 3: President plans
    PLANNING = "planning"

    # Step 4: Duke/Earl execute
    EXECUTING = "executing"

    # Step 5: Prince judges
    JUDGING = "judging"

    # Step 6: Knight witnesses
    WITNESSING = "witnessing"

    # Step 7: Conclave acknowledges
    ACKNOWLEDGED = "acknowledged"  # Terminal

@dataclass(frozen=True)
class StateTransition:
    """Record of a state transition."""
    transition_id: UUID
    motion_id: UUID
    from_state: GovernanceState
    to_state: GovernanceState
    triggered_by: str  # Archon ID
    transitioned_at: datetime
    witnessed_by: str | None = None

@dataclass(frozen=True)
class MotionStateRecord:
    """Complete state history for a motion."""
    motion_id: UUID
    current_state: GovernanceState
    history: tuple[StateTransition, ...]
    time_in_state: timedelta
    is_terminal: bool
```

### State Transition Graph

```
                    ┌──────────┐
                    │INTRODUCED│ ← King
                    └────┬─────┘
                         │
                         ▼
                    ┌──────────┐
                    │DELIBERATING│ ← Conclave
                    └────┬─────┘
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             ▼             ▼
      ┌────────┐   ┌─────────┐   ┌────────┐
      │REJECTED│   │RATIFIED │   │TABLED  │
      │(Terminal)│  └────┬────┘   │(Pause) │
      └────────┘        │        └────────┘
                        │
                        ▼
                   ┌─────────┐
                   │PLANNING │ ← President
                   └────┬────┘
                        │
                        ▼
                   ┌──────────┐
                   │EXECUTING │ ← Duke/Earl
                   └────┬─────┘
                        │
                        ▼
                   ┌─────────┐
                   │JUDGING  │ ← Prince
                   └────┬────┘
                        │
                        ▼
                   ┌──────────┐
                   │WITNESSING│ ← Knight
                   └────┬─────┘
                        │
                        ▼
                   ┌────────────┐
                   │ACKNOWLEDGED│ ← Conclave (Terminal)
                   └────────────┘
```

### Transition Rules Configuration

```python
TRANSITION_RULES = [
    TransitionRule(from_state=GovernanceState.INTRODUCED, to_state=GovernanceState.DELIBERATING),
    TransitionRule(from_state=GovernanceState.DELIBERATING, to_state=GovernanceState.RATIFIED),
    TransitionRule(from_state=GovernanceState.DELIBERATING, to_state=GovernanceState.REJECTED),
    TransitionRule(from_state=GovernanceState.RATIFIED, to_state=GovernanceState.PLANNING),
    TransitionRule(from_state=GovernanceState.PLANNING, to_state=GovernanceState.EXECUTING),
    TransitionRule(from_state=GovernanceState.EXECUTING, to_state=GovernanceState.JUDGING),
    TransitionRule(from_state=GovernanceState.JUDGING, to_state=GovernanceState.WITNESSING),
    TransitionRule(from_state=GovernanceState.WITNESSING, to_state=GovernanceState.ACKNOWLEDGED),
]

TERMINAL_STATES = {GovernanceState.REJECTED, GovernanceState.ACKNOWLEDGED}
```

### Event Type

```python
# New event type for state transitions
STATE_TRANSITION = "STATE_TRANSITION"
```

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Story 8.1]
- [Source: docs/new-requirements.md#FR-GOV-23]
- [Source: docs/new-requirements.md#PRD §6 Governance Flow]
- [Source: src/application/ports/king_service.py#MotionStatus Enum (partial reference)]
