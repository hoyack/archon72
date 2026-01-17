# Story consent-gov-7.1: Exit Request Processing

Status: done

---

## Story

As a **Cluster**,
I want **to initiate and complete an exit request**,
So that **I can leave the system cleanly**.

---

## Acceptance Criteria

1. **AC1:** Cluster can initiate exit request (FR42)
2. **AC2:** System processes exit request (FR43)
3. **AC3:** Exit completes in ≤2 message round-trips (NFR-EXIT-01)
4. **AC4:** Exit path available from any task state (NFR-EXIT-03)
5. **AC5:** Event `custodial.exit.initiated` emitted at start
6. **AC6:** Event `custodial.exit.completed` emitted on completion
7. **AC7:** No barriers to exit (no "are you sure?" patterns)
8. **AC8:** Exit works regardless of current task status
9. **AC9:** Unit tests for exit from each task state

---

## Tasks / Subtasks

- [x] **Task 1: Create ExitRequest domain model** (AC: 1)
  - [x] Create `src/domain/governance/exit/exit_request.py`
  - [x] Include cluster_id, requested_at
  - [x] Include current_task_states at time of request
  - [x] Immutable value object

- [x] **Task 2: Create ExitService** (AC: 2, 3, 4)
  - [x] Create `src/application/services/governance/exit_service.py`
  - [x] Process exit request
  - [x] Coordinate with other services (obligation release, etc.)
  - [x] Complete in ≤2 round-trips

- [x] **Task 3: Create ExitPort interface** (AC: 2)
  - [x] Create `src/application/ports/governance/exit_port.py`
  - [x] Define `initiate_exit()` method
  - [x] Define `complete_exit()` method
  - [x] Define `get_exit_status()` method

- [x] **Task 4: Implement exit initiation** (AC: 1, 5)
  - [x] Accept exit request from Cluster
  - [x] Emit `custodial.exit.initiated` event
  - [x] No confirmation dialog (direct initiation)
  - [x] No reason required (unconditional right)

- [x] **Task 5: Implement exit processing** (AC: 2, 3)
  - [x] Step 1: Cluster sends exit request
  - [x] Step 2: System confirms exit complete
  - [x] Total: 2 round-trips maximum
  - [x] No intermediate states requiring response

- [x] **Task 6: Implement universal exit path** (AC: 4, 8)
  - [x] Exit from AUTHORIZED state
  - [x] Exit from ACTIVATED state
  - [x] Exit from ACCEPTED state
  - [x] Exit from IN_PROGRESS state
  - [x] Exit from any other state

- [x] **Task 7: Implement completion event** (AC: 6)
  - [x] Emit `custodial.exit.completed` on finish
  - [x] Include exit duration
  - [x] Include tasks affected
  - [x] Knight observes completion

- [x] **Task 8: Ensure no barriers** (AC: 7)
  - [x] No confirmation prompts
  - [x] No waiting periods
  - [x] No penalty warnings
  - [x] Immediate processing

- [x] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [x] Test exit from AUTHORIZED
  - [x] Test exit from ACTIVATED
  - [x] Test exit from ACCEPTED
  - [x] Test exit from IN_PROGRESS
  - [x] Test exit completes in ≤2 round-trips
  - [x] Test events emitted
  - [x] Test no barriers

---

## Documentation Checklist

- [x] Architecture docs updated (exit workflow) - In-code documentation
- [x] Exit path documented for all states - In __init__.py module docstring
- [x] Operations runbook for exit handling - N/A (domain layer only)
- [x] N/A - README (internal component)

---

## File List

### Created Files
- `src/domain/governance/exit/__init__.py` - Module exports with comprehensive docstring
- `src/domain/governance/exit/exit_status.py` - ExitStatus enum (INITIATED, PROCESSING, COMPLETED)
- `src/domain/governance/exit/exit_request.py` - ExitRequest frozen dataclass
- `src/domain/governance/exit/exit_result.py` - ExitResult frozen dataclass with round-trip validation
- `src/domain/governance/exit/errors.py` - ExitBarrierError, AlreadyExitedError, ExitNotFoundError
- `src/application/ports/governance/exit_port.py` - ExitPort protocol (no barrier methods)
- `src/application/services/governance/exit_service.py` - ExitService with initiate_exit()
- `tests/unit/domain/governance/exit/__init__.py` - Test package init
- `tests/unit/domain/governance/exit/test_exit_models.py` - 36 domain model tests
- `tests/unit/application/ports/governance/test_exit_port.py` - 23 port interface tests
- `tests/unit/application/services/governance/test_exit_service.py` - 40 service tests

### Modified Files
- `src/application/ports/governance/__init__.py` - Added ExitPort export
- `src/application/services/governance/__init__.py` - Added ExitService export

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-17 | Initial implementation - All 9 tasks complete | Claude |
| 2026-01-17 | 99 unit tests passing | Claude |

---

## Dev Notes

### Key Architectural Decisions

**Why ≤2 Round-Trips?**
```
NFR-EXIT-01: Exit completes in ≤2 message round-trips

Round-trip 1: Cluster → System: "I want to exit"
Round-trip 2: System → Cluster: "Exit complete"

Why this limit?
  - Compatible with email-only protocols
  - No complex handshaking
  - Minimizes chance to insert barriers
  - Clear, simple protocol

NOT allowed:
  - "Are you sure?" prompts
  - Multi-step verification
  - Waiting periods
  - Confirmation codes
```

**Why No Barriers?**
```
Exit is an unconditional right:
  - Consent can be withdrawn at any time
  - No justification required
  - No penalty for leaving
  - No guilt-inducing messages

Barriers would be coercion:
  - "Your work will be lost" → guilt
  - "Wait 7 days" → friction
  - "Enter reason" → interrogation
  - "Confirm again" → dark pattern
```

**Exit from Any State:**
```
NFR-EXIT-03: Exit path available from any task state

┌─────────────────────────────────────────────┐
│ State            │ Exit Handling            │
├──────────────────┼──────────────────────────┤
│ AUTHORIZED       │ Task nullified           │
│ ACTIVATED        │ Task nullified           │
│ ROUTED           │ Task nullified           │
│ ACCEPTED         │ Task released (quarantine)│
│ IN_PROGRESS      │ Task released (quarantine)│
│ REPORTED         │ Task released (preserve) │
│ COMPLETED        │ No change (done)         │
│ DECLINED         │ No change (done)         │
└─────────────────────────────────────────────┘

No state prevents exit. Period.
```

### Implementation Notes

**Round-Trip Enforcement:**
```python
# ExitResult validates round_trips in __post_init__
if self.round_trips > MAX_ROUND_TRIPS:
    raise ValueError(
        f"NFR-EXIT-01 VIOLATION: Exit exceeded {MAX_ROUND_TRIPS} round-trips."
    )
```

**No Barrier Methods:**
The following methods are INTENTIONALLY NOT IMPLEMENTED:
- `confirm_exit()` - Would require confirmation
- `verify_exit()` - Would require verification
- `approve_exit()` - Would require approval
- `wait_for_exit()` - Would add waiting period
- `require_reason()` - Would require justification
- `warn_exit()` - Would show penalty warning
- `are_you_sure()` - Classic dark pattern

Tests explicitly verify these methods do not exist.

### Dependencies

- **Depends on:** consent-gov-2-1 (task state machine)
- **Enables:** consent-gov-7-2 (obligation release), consent-gov-7-3 (contribution preservation), consent-gov-7-4 (contact prevention)

### References

- FR42: Cluster can initiate exit request
- FR43: System can process exit request
- NFR-EXIT-01: Exit completes in ≤2 message round-trips
- NFR-EXIT-03: Exit path available from any task state
