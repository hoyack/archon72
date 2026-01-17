# Story GOV-8.3: Implement Skip Prevention (FR-GOV-23)

Status: done

## Story

As a **developer**,
I want **enforcement that no step can be skipped**,
So that **governance flow is complete**.

## Acceptance Criteria

### AC1: Skip Detection

**Given** a motion in state X
**When** an attempt is made to transition to state X+2 (skipping X+1)
**Then** the skip is detected before transition
**And** the detection includes the skipped state(s)

### AC2: Skip Rejection

**Given** a skip attempt is detected
**When** the state machine processes it
**Then** the transition is rejected
**And** the skip attempt is witnessed as violation
**And** the error includes:
  - Current state
  - Attempted state
  - Required intermediate state(s)

### AC3: Violation Recording

**Given** a skip attempt is rejected
**When** the violation is recorded
**Then** it includes:
  - `violation_type: STEP_SKIP_ATTEMPT`
  - `severity: CRITICAL`
  - `archon_id` of who attempted
  - `motion_id` affected
  - `attempted_transition` details

### AC4: Force Skip Prevention

**Given** a privileged user attempts to force skip
**When** the force attempt is detected
**Then** it is rejected regardless of privilege
**And** escalated to Conclave review
**And** documented as `FORCED_SKIP_ATTEMPT`

### AC5: API-Level Enforcement

**Given** skip prevention at state machine level
**When** API endpoints are called
**Then** API validates transitions before calling state machine
**And** API returns appropriate error codes for skip attempts

### AC6: Audit Trail

**Given** skip attempts must be auditable
**When** a skip attempt occurs
**Then** full audit trail is maintained:
  - Timestamp of attempt
  - Archon who attempted
  - Source of attempt (API, service, manual)
  - Current state and attempted state
  - Rejection reason

## Tasks / Subtasks

- [x] Task 1: Enhance State Machine with Skip Detection (AC: 1, 2)
  - [x] 1.1 Add `validate_transition(from_state, to_state)` method
  - [x] 1.2 Implement skip detection algorithm
  - [x] 1.3 Calculate skipped states for error messages
  - [x] 1.4 Add rejection with detailed error

- [x] Task 2: Create Skip Violation Domain Models (AC: 3)
  - [x] 2.1 Create `SkipAttemptViolation` frozen dataclass
  - [x] 2.2 Create `SkipAttemptType` Enum (SIMPLE_SKIP, FORCE_SKIP, BULK_SKIP)
  - [x] 2.3 Add severity classification

- [x] Task 3: Implement Force Skip Prevention (AC: 4)
  - [x] 3.1 Remove any force-skip bypass capabilities
  - [x] 3.2 Implement escalation for force attempts
  - [x] 3.3 Create `ForcedSkipAttempt` event type

- [x] Task 4: API-Level Integration (AC: 5)
  - [x] 4.1 Add transition validation to API endpoints
  - [x] 4.2 Define HTTP 422 response for skip attempts
  - [x] 4.3 Include detailed error in response

- [x] Task 5: Audit Trail Implementation (AC: 6)
  - [x] 5.1 Create `SkipAttemptAudit` event type
  - [x] 5.2 Implement audit logging
  - [x] 5.3 Create `get_skip_attempts(motion_id)` query

- [x] Task 6: Unit Tests (AC: 1-6)
  - [x] 6.1 Create `tests/unit/infrastructure/adapters/governance/test_skip_prevention.py`
  - [x] 6.2 Test skip detection for all invalid transitions
  - [x] 6.3 Test rejection with correct error details
  - [x] 6.4 Test force skip prevention
  - [x] 6.5 Test audit trail creation

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-13:** Integrity outranks availability → Never allow skip even for performance

**Government PRD Requirements:**
- **FR-GOV-23:** Governance Flow - No step may be skipped
- **NFR-GOV-6:** Legitimacy requires visible procedure

### Hexagonal Architecture Compliance

**Files to Modify/Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Infrastructure/Adapter | `src/infrastructure/adapters/governance/governance_state_machine_adapter.py` | Add skip prevention |
| Tests | `tests/unit/infrastructure/adapters/governance/test_skip_prevention.py` | Unit tests |

### Domain Model Design

```python
class SkipAttemptType(Enum):
    """Types of skip attempts."""
    SIMPLE_SKIP = "simple_skip"    # Normal API call attempting skip
    FORCE_SKIP = "force_skip"      # Privileged attempt to bypass
    BULK_SKIP = "bulk_skip"        # Attempting to skip multiple states

@dataclass(frozen=True)
class SkipAttemptViolation:
    """A violation where a step skip was attempted.

    Per FR-GOV-23: No step may be skipped.
    """
    violation_id: UUID
    motion_id: UUID
    current_state: GovernanceState
    attempted_state: GovernanceState
    skipped_states: tuple[GovernanceState, ...]
    attempt_type: SkipAttemptType
    attempted_by: str  # Archon ID
    attempted_at: datetime
    severity: str = "CRITICAL"
    rejected: bool = True
```

### Skip Detection Algorithm

```python
def detect_skip(
    current_state: GovernanceState,
    attempted_state: GovernanceState,
) -> tuple[bool, list[GovernanceState]]:
    """Detect if a transition would skip intermediate states.

    Returns (is_skip, skipped_states).
    """
    # Get valid path from current to attempted
    valid_path = get_valid_path(current_state, attempted_state)

    if valid_path is None:
        # No valid path exists - invalid transition
        return True, []

    if len(valid_path) == 2:
        # Direct transition (current -> attempted) - no skip
        return False, []

    # Skip detected - intermediate states exist
    skipped = valid_path[1:-1]  # Exclude current and attempted
    return True, skipped

def get_valid_path(
    from_state: GovernanceState,
    to_state: GovernanceState,
) -> list[GovernanceState] | None:
    """Get the valid transition path between states.

    Returns None if no valid path exists.
    """
    # BFS or lookup from transition rules
    ...
```

### Invalid Transition Matrix

All transitions NOT in TRANSITION_RULES are invalid:

```
From\To          │ INT │ DEL │ RAT │ REJ │ PLN │ EXE │ JDG │ WIT │ ACK │
─────────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
INTRODUCED       │  -  │  ✓  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │
DELIBERATING     │  ✗  │  -  │  ✓  │  ✓  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │
RATIFIED         │  ✗  │  ✗  │  -  │  ✗  │  ✓  │  ✗  │  ✗  │  ✗  │  ✗  │
REJECTED         │  ✗  │  ✗  │  ✗  │  -  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │
PLANNING         │  ✗  │  ✗  │  ✗  │  ✗  │  -  │  ✓  │  ✗  │  ✗  │  ✗  │
EXECUTING        │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  -  │  ✓  │  ✗  │  ✗  │
JUDGING          │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  -  │  ✓  │  ✗  │
WITNESSING       │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  -  │  ✓  │
ACKNOWLEDGED     │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  ✗  │  -  │

✓ = Valid transition
✗ = Skip attempt (or invalid)
- = Same state (no transition)
```

### Error Response Format

```python
@dataclass
class SkipAttemptError:
    """Error response for skip attempts."""
    error_code: str = "STEP_SKIP_VIOLATION"
    prd_reference: str = "FR-GOV-23"
    message: str
    current_state: str
    attempted_state: str
    required_next_state: str
    skipped_states: list[str]
    motion_id: str
```

### HTTP Error Code

```
HTTP 422 Unprocessable Entity
Content-Type: application/json

{
  "error_code": "STEP_SKIP_VIOLATION",
  "prd_reference": "FR-GOV-23",
  "message": "Cannot skip from INTRODUCED to PLANNING; must pass through DELIBERATING, RATIFIED",
  "current_state": "INTRODUCED",
  "attempted_state": "PLANNING",
  "required_next_state": "DELIBERATING",
  "skipped_states": ["DELIBERATING", "RATIFIED"],
  "motion_id": "..."
}
```

### Event Types

```python
SKIP_ATTEMPT_VIOLATION = "SKIP_ATTEMPT_VIOLATION"
FORCED_SKIP_ATTEMPT = "FORCED_SKIP_ATTEMPT"
```

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Story 8.3]
- [Source: docs/new-requirements.md#FR-GOV-23]
- [Source: Story GOV-8.1#Governance State Machine]
- [Source: Story GOV-8.2#Flow Orchestrator]
