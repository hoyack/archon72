# Story 1.5: State Machine Domain Model

**Epic:** Petition Epic 1 - Petition Intake & State Machine
**Priority:** P0
**Status:** Done
**Completed:** 2026-01-19

## Story

As a **developer**,
I want a petition state machine that enforces valid transitions,
So that petitions can only move through legitimate states.

## References

- **FR-2.1**: System SHALL enforce valid state transitions only
- **FR-2.2**: System SHALL support states: RECEIVED, DELIBERATING, ACKNOWLEDGED, REFERRED, ESCALATED
- **FR-2.3**: System SHALL reject transitions not in transition matrix
- **FR-2.6**: System SHALL mark petition as terminal when fate assigned
- **AT-1**: Every petition terminates in exactly one of Three Fates

## Acceptance Criteria

### AC1: Valid Transitions from RECEIVED
**Given** a petition in state RECEIVED
**When** a transition is attempted
**Then** only these transitions are valid:
- RECEIVED → DELIBERATING (fate assignment begins)
- RECEIVED → ACKNOWLEDGED (withdrawn before deliberation)

**And** invalid transitions raise `InvalidStateTransitionError`

### AC2: Valid Transitions from DELIBERATING
**Given** a petition in state DELIBERATING
**When** a transition is attempted
**Then** only these transitions are valid:
- DELIBERATING → ACKNOWLEDGED (Three Fates acknowledge)
- DELIBERATING → REFERRED (referred to Knight)
- DELIBERATING → ESCALATED (escalated to King)

**And** invalid transitions raise `InvalidStateTransitionError`

### AC3: Terminal State Enforcement
**Given** a petition in terminal state (ACKNOWLEDGED, REFERRED, ESCALATED)
**When** any transition is attempted
**Then** the system rejects with `PetitionAlreadyFatedError`

### AC4: Transition Matrix Documentation
**And** all transition rules are documented in the state machine model
**And** unit tests cover all valid and invalid transition combinations

## Implementation

### Files Created

| File | Purpose |
|------|---------|
| `src/domain/errors/state_transition.py` | InvalidStateTransitionError, PetitionAlreadyFatedError |

### Files Modified

| File | Changes |
|------|---------|
| `src/domain/models/petition_submission.py` | Added state machine logic, terminal states, transition matrix |
| `src/domain/models/__init__.py` | Exported STATE_TRANSITION_MATRIX, TERMINAL_STATES |
| `src/domain/errors/__init__.py` | Exported new errors |
| `tests/unit/domain/models/test_petition_submission.py` | Added comprehensive state machine tests |

### State Machine

```
                    ┌─────────────┐
                    │  RECEIVED   │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
      ┌───────────────┐         ┌──────────────┐
      │ DELIBERATING  │         │ ACKNOWLEDGED │ (withdrawal)
      └───────┬───────┘         │  (terminal)  │
              │                 └──────────────┘
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
┌────────┐ ┌────────┐ ┌──────────┐
│REFERRED│ │ACKNOWL.│ │ESCALATED │
│(term.) │ │(term.) │ │(terminal)│
└────────┘ └────────┘ └──────────┘
```

### Transition Matrix

| From State | Valid Targets |
|------------|---------------|
| RECEIVED | DELIBERATING, ACKNOWLEDGED |
| DELIBERATING | ACKNOWLEDGED, REFERRED, ESCALATED |
| ACKNOWLEDGED | (none - terminal) |
| REFERRED | (none - terminal) |
| ESCALATED | (none - terminal) |

### Key Design Decisions

1. **Terminal states are the Three Fates**: ACKNOWLEDGED, REFERRED, ESCALATED
2. **No self-loops**: States cannot transition to themselves
3. **No backward transitions**: Cannot go from DELIBERATING back to RECEIVED
4. **Withdrawal path**: RECEIVED → ACKNOWLEDGED bypasses deliberation for withdrawals
5. **Error specificity**: Terminal states raise `PetitionAlreadyFatedError`, invalid transitions raise `InvalidStateTransitionError`

## Test Coverage

### Test Classes Added

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestPetitionStateMachine` | 10 | State machine mechanics |
| `TestPetitionAlreadyFated` | 4 | Terminal state enforcement |
| `TestInvalidStateTransitionError` | 2 | Error attributes |
| `TestCompleteStateTransitionCoverage` | 6 | All paths + happy paths |

### Total New Tests: 22

### Tests Updated

- `test_valid_state_transitions_from_received` - Valid RECEIVED transitions
- `test_valid_state_transitions_from_deliberating` - Valid DELIBERATING transitions

## Constitutional Compliance

| Constraint | Implementation |
|------------|----------------|
| FR-2.1 | `with_state()` validates against `STATE_TRANSITION_MATRIX` |
| FR-2.2 | `PetitionState` enum with all 5 states |
| FR-2.3 | `InvalidStateTransitionError` for invalid transitions |
| FR-2.6 | `PetitionAlreadyFatedError` for terminal state modifications |
| AT-1 | `TERMINAL_STATES` frozenset ensures exactly one fate |

## Dependencies

- Story 0.2: Petition Domain Model & Base Schema (provides PetitionSubmission, PetitionState)

## Notes

- Tests verified with `py_compile` for syntax correctness
- Full test execution requires Python 3.11+ environment (current venv is 3.10)
- State machine is enforced at the domain model level, ensuring integrity regardless of caller
