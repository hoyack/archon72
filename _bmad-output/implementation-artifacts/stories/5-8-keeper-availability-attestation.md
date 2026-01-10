# Story 5.8: Keeper Availability Attestation (FR77-FR79)

Status: done

## Story

As a **system operator**,
I want Keeper availability tracked with replacement triggers,
So that unresponsive Keepers are replaced.

## Acceptance Criteria

### AC1: Weekly Attestation Requirement
**Given** weekly attestation requirement
**When** a Keeper attests availability
**Then** a `KeeperAttestationEvent` is created
**And** the event includes: `keeper_id`, `attested_at`, `attestation_period_start`, `attestation_period_end`

### AC2: Missed Attestation Triggers Replacement
**Given** a Keeper misses 2 consecutive attestations
**When** the second deadline passes
**Then** replacement process is triggered
**And** a `KeeperReplacementInitiatedEvent` is created
**And** the event includes: `keeper_id`, `missed_periods`, `initiated_at`, `reason`

### AC3: Keeper Quorum Below Minimum Halts System
**Given** Keeper quorum (minimum 3)
**When** quorum drops below 3
**Then** system halts
**And** error includes "FR79: Keeper quorum below minimum"
**And** a `SystemHaltedError` is raised with appropriate context

### AC4: Keeper Quorum Warning at Threshold (SR-7)
**Given** quorum drops to exactly 3
**When** this threshold is reached
**Then** health alert is triggered
**And** `KeeperQuorumWarningEvent` is created
**And** the event includes: `current_count`, `minimum_required`, `alert_severity`

## Tasks / Subtasks

- [x] Task 1: Create Keeper Attestation Domain Models (AC: #1)
  - [x] 1.1 Create `src/domain/models/keeper_attestation.py`:
    - `KeeperAttestation` dataclass with: `id`, `keeper_id`, `attested_at`, `period_start`, `period_end`, `signature`
    - `ATTESTATION_PERIOD_DAYS = 7` (weekly requirement)
    - `MISSED_ATTESTATIONS_THRESHOLD = 2` (trigger replacement after 2 missed)
    - Use `DeletePreventionMixin` for audit trail preservation (FR76)
    - `is_valid_for_period(period_start, period_end)` method
  - [x] 1.2 Export from `src/domain/models/__init__.py`

- [x] Task 2: Create Keeper Availability Events (AC: #1, #2, #4)
  - [x] 2.1 Create `src/domain/events/keeper_availability.py`:
    - `KeeperAttestationPayload` - weekly attestation submitted
    - `KeeperMissedAttestationPayload` - attestation deadline passed without submission
    - `KeeperReplacementInitiatedPayload` - replacement process started
    - `KeeperQuorumWarningPayload` - quorum at minimum threshold (SR-7)
    - All payloads include `keeper_id`, `timestamp`
  - [x] 2.2 Export from `src/domain/events/__init__.py`

- [x] Task 3: Create Keeper Availability Errors (AC: #2, #3)
  - [x] 3.1 Create `src/domain/errors/keeper_availability.py`:
    - `KeeperAvailabilityError(ConclaveError)` - base class
    - `KeeperAttestationExpiredError(KeeperAvailabilityError)` - attestation period passed
    - `DuplicateAttestationError(KeeperAvailabilityError)` - already attested for period
    - `KeeperQuorumViolationError(KeeperAvailabilityError)` - FR79: quorum below 3
    - `KeeperReplacementRequiredError(KeeperAvailabilityError)` - 2 missed attestations
    - `InvalidAttestationSignatureError(KeeperAvailabilityError)` - signature verification failed
  - [x] 3.2 Export from `src/domain/errors/__init__.py`

- [x] Task 4: Create Keeper Availability Port (AC: #1, #2, #3, #4)
  - [x] 4.1 Create `src/application/ports/keeper_availability.py`:
    - `KeeperAvailabilityProtocol` with methods:
      - `async def get_attestation(keeper_id: str, period_start: datetime) -> KeeperAttestation | None`
      - `async def record_attestation(attestation: KeeperAttestation) -> None`
      - `async def get_missed_attestations_count(keeper_id: str) -> int`
      - `async def get_all_active_keepers() -> list[str]`
      - `async def get_keepers_pending_replacement() -> list[str]`
      - `async def mark_keeper_for_replacement(keeper_id: str, reason: str) -> None`
      - `async def get_current_keeper_count() -> int`
  - [x] 4.2 Export from `src/application/ports/__init__.py`

- [x] Task 5: Create Keeper Availability Service (AC: #1, #2, #3, #4)
  - [x] 5.1 Create `src/application/services/keeper_availability_service.py`
  - [x] 5.2 Implement `KeeperAvailabilityService`:
    - Inject: `KeeperAvailabilityProtocol`, `KeeperSignatureService`, `EventWriterService`, `HaltGuardProtocol`, `HaltTriggerProtocol`
    - MINIMUM_KEEPER_QUORUM = 3 (FR79)
    - MISSED_ATTESTATIONS_THRESHOLD = 2
    - ATTESTATION_PERIOD_DAYS = 7
  - [x] 5.3 Implement `submit_attestation(keeper_id: str, signature: bytes) -> KeeperAttestation`:
    - HALT CHECK FIRST (CT-11)
    - Verify Keeper signature using KeeperSignatureService
    - Calculate current attestation period
    - Check for duplicate attestation
    - Record attestation
    - Write `KeeperAttestationEvent` to event store
    - Return attestation record
  - [x] 5.4 Implement `check_attestation_deadlines() -> list[str]` - background task:
    - HALT CHECK FIRST
    - Find all Keepers missing attestation for current period
    - For each missing Keeper:
      - Increment missed attestation count
      - Write `KeeperMissedAttestationEvent`
      - If count >= MISSED_ATTESTATIONS_THRESHOLD:
        - Mark for replacement
        - Write `KeeperReplacementInitiatedEvent`
    - Return list of Keepers marked for replacement
  - [x] 5.5 Implement `check_keeper_quorum() -> None`:
    - Get current active Keeper count
    - If count < MINIMUM_KEEPER_QUORUM:
      - Trigger halt via HaltTriggerProtocol
      - Raise `KeeperQuorumViolationError("FR79: Keeper quorum below minimum")`
    - If count == MINIMUM_KEEPER_QUORUM (SR-7):
      - Write `KeeperQuorumWarningEvent`
      - Log health alert
  - [x] 5.6 Implement `get_keeper_attestation_status(keeper_id: str) -> dict`:
    - Return: last_attestation, missed_count, next_deadline, status
  - [x] 5.7 Export from `src/application/services/__init__.py`

- [x] Task 6: Create Keeper Availability Stub (AC: #1, #2, #3, #4)
  - [x] 6.1 Create `src/infrastructure/stubs/keeper_availability_stub.py`
  - [x] 6.2 Implement `KeeperAvailabilityStub`:
    - In-memory attestation storage
    - Missed attestation tracking per Keeper
    - Active Keeper list management
    - Replacement pending list
    - `clear()` for test cleanup
    - `add_keeper(keeper_id: str)` for test setup
    - `remove_keeper(keeper_id: str)` for quorum testing
  - [x] 6.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 7: Write Unit Tests (AC: #1, #2, #3, #4)
  - [x] 7.1 Create `tests/unit/domain/test_keeper_attestation.py` (21 tests):
    - Test `KeeperAttestation` creation and validation
    - Test `is_valid_for_period()` temporal checks
    - Test period calculation (7-day intervals)
    - Test delete prevention (FR76)
    - Test signature requirement
  - [x] 7.2 Create `tests/unit/domain/test_keeper_availability_events.py` (18 tests):
    - Test all event payload types
    - Test serialization/deserialization
    - Test required fields present
    - Test FR reference in error messages
  - [x] 7.3 Create `tests/unit/application/test_keeper_availability_service.py` (17 tests):
    - Test `submit_attestation()` with valid signature (AC1)
    - Test `submit_attestation()` rejects invalid signature
    - Test `submit_attestation()` rejects duplicate for period
    - Test `submit_attestation()` with HALT CHECK
    - Test `check_attestation_deadlines()` detects missing (AC2)
    - Test `check_attestation_deadlines()` triggers replacement after 2 missed
    - Test `check_attestation_deadlines()` writes events correctly
    - Test `check_keeper_quorum()` halts when < 3 Keepers (AC3)
    - Test `check_keeper_quorum()` raises FR79 error (AC3)
    - Test `check_keeper_quorum()` warns at exactly 3 Keepers (AC4)
    - Test `get_keeper_attestation_status()` returns correct status
    - Test HALT CHECK at every operation boundary
  - [x] 7.4 Create `tests/unit/infrastructure/test_keeper_availability_stub.py` (12 tests)

- [x] Task 8: Write Integration Tests (AC: #1, #2, #3, #4)
  - [x] 8.1 Create `tests/integration/test_keeper_availability_integration.py` (12 tests):
    - Test: `test_submit_valid_attestation_creates_event` (AC1)
    - Test: `test_attestation_includes_all_required_fields` (AC1)
    - Test: `test_missed_attestation_detected_after_deadline` (AC2)
    - Test: `test_two_missed_attestations_triggers_replacement` (AC2)
    - Test: `test_replacement_event_includes_required_fields` (AC2)
    - Test: `test_fr79_quorum_below_3_halts_system` (AC3)
    - Test: `test_fr79_error_message_included` (AC3)
    - Test: `test_sr7_quorum_at_3_triggers_warning` (AC4)
    - Test: `test_quorum_warning_event_includes_severity` (AC4)
    - Test: `test_signature_verification_required_for_attestation`
    - Test: `test_duplicate_attestation_rejected`
    - Test: `test_attestation_period_calculation`

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR77**: If unanimous Keeper agreement not achieved within 72 hours of recovery, cessation evaluation SHALL begin
- **FR78**: Keepers SHALL attest availability weekly; 2 missed attestations trigger replacement process
- **FR79**: If registered Keeper count falls below 3, system SHALL halt until complement restored
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> Attestations are witnessed events
- **NFR42**: Keeper count SHALL never fall below 3 without halt

### SR-7: Keeper Health Alerting

From Stakeholder Round Table findings:
- Alert when quorum drops to exactly 3 (critical threshold)
- Proactive warning before quorum violation
- Health dashboard integration

### Architecture Pattern: Keeper Availability Flow

```
1. submit_attestation()
   │
   ▼
┌─────────────────────────────────────────┐
│ KeeperAvailabilityService               │
│ - HALT CHECK FIRST                      │
│ - Verify Keeper signature               │
│ - Calculate attestation period          │
│ - Check for duplicate                   │
│ - Record attestation                    │
│ - Write KeeperAttestationEvent          │
└─────────────────────────────────────────┘
   │
   ▼
2. check_attestation_deadlines() [Background Task]
   │
   ▼
┌─────────────────────────────────────────┐
│ - HALT CHECK FIRST                      │
│ - Scan all active Keepers               │
│ - Detect missing attestations           │
│ - Increment missed counts               │
│ - Write KeeperMissedAttestationEvent    │
│ - If count >= 2:                        │
│   - Mark for replacement                │
│   - Write KeeperReplacementInitiated    │
└─────────────────────────────────────────┘
   │
   ▼
3. check_keeper_quorum()
   │
   ▼
┌─────────────────────────────────────────┐
│ - Get active Keeper count               │
│ - If count < 3:                         │
│   - HALT SYSTEM (FR79)                  │
│   - Raise KeeperQuorumViolationError    │
│ - If count == 3:                        │
│   - Write KeeperQuorumWarningEvent      │
│   - Log MEDIUM severity alert           │
└─────────────────────────────────────────┘
```

### Attestation Period Calculation

```python
def get_current_period() -> tuple[datetime, datetime]:
    """Calculate current 7-day attestation period.

    Periods start at midnight UTC on Mondays.
    """
    now = datetime.now(timezone.utc)
    # Find Monday of current week
    days_since_monday = now.weekday()
    period_start = now.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days_since_monday)
    period_end = period_start + timedelta(days=7)
    return period_start, period_end
```

### Previous Story Learnings (from 5.7)

**Key Generation Ceremony Patterns:**
- Ceremony state machine with valid transitions
- Multi-witness requirement enforcement
- VAL-2 timeout enforcement
- CM-5 conflict detection

**Service Pattern:**
- HALT CHECK FIRST at every operation boundary
- Bind logger with operation context
- Write constitutional events for all state changes
- Use specific domain errors with FR references

**Testing Pattern:**
- 102 tests in Story 5.7 - maintain similar rigor
- `pytest.mark.asyncio` for all async tests
- Mock dependencies for unit tests
- Use stubs for integration tests

### Existing Code to Integrate With

**From Story 5.6:**
- `KeeperKey` domain model - keys for signature verification
- `KeeperKeyRegistryProtocol` - key lookup
- `KeeperSignatureService` - verify attestation signatures

**From Story 5.7:**
- `KeyGenerationCeremonyService` - key management patterns
- `CEREMONY_TIMEOUT_SECONDS` pattern for deadline management

**From Event Store (Epic 1):**
- `EventWriterService` - write attestation events
- `ConstitutionalEvent` envelope pattern

**From Halt System (Epic 3):**
- `HaltGuardProtocol` - check halt status
- `HaltTriggerProtocol` - trigger halt on quorum violation

### Files to Create

```
src/domain/models/keeper_attestation.py                    # Attestation domain model
src/domain/events/keeper_availability.py                   # Availability event payloads
src/domain/errors/keeper_availability.py                   # Availability-specific errors
src/application/ports/keeper_availability.py               # Availability repository protocol
src/application/services/keeper_availability_service.py    # Main service
src/infrastructure/stubs/keeper_availability_stub.py       # Test stub
tests/unit/domain/test_keeper_attestation.py               # Domain model tests
tests/unit/domain/test_keeper_availability_events.py       # Event tests
tests/unit/application/test_keeper_availability_service.py # Service tests
tests/integration/test_keeper_availability_integration.py  # Integration tests
```

### Files to Modify

```
src/domain/models/__init__.py              # Export attestation models
src/domain/events/__init__.py              # Export availability events
src/domain/errors/__init__.py              # Export availability errors
src/application/ports/__init__.py          # Export availability port
src/application/services/__init__.py       # Export availability service
src/infrastructure/stubs/__init__.py       # Export availability stub
```

### Import Rules (Hexagonal Architecture)

- `domain/models/` imports from `domain/errors/`, `domain/primitives/`, `typing`, `datetime`, `dataclasses`, `uuid`
- `domain/events/` imports from `domain/models/`, `typing`, `datetime`
- `domain/errors/` inherits from base `ConclaveError`
- `application/ports/` imports from `domain/models/`, `typing` (Protocol)
- `application/services/` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR79 test MUST verify halt is triggered with correct error message
- SR-7 test MUST verify warning event at exactly 3 Keepers
- Test missed attestation counting carefully (boundary conditions)

### Critical Implementation Notes

1. **Attestation Period Alignment**: Periods must align to Monday 00:00 UTC for consistency
2. **Signature Verification**: Every attestation MUST be cryptographically signed (use KeeperSignatureService)
3. **Quorum Check Timing**: Check quorum AFTER any operation that could reduce Keeper count
4. **Background Task Design**: `check_attestation_deadlines()` should be idempotent (safe to run multiple times)
5. **Race Conditions**: Handle concurrent attestation submissions for same period

### Project Structure Notes

- Attestation follows similar patterns to `AgentKey` temporal validity
- Events follow existing payload patterns from Story 5.7
- Errors inherit from `ConclaveError` with FR references
- Service follows HALT CHECK FIRST pattern throughout

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.8] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR77-FR79] - Recovery Deadlock Prevention requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-004] - Key Custody patterns
- [Source: _bmad-output/planning-artifacts/epics.md#SR-7] - Keeper health alerting requirement
- [Source: src/domain/models/keeper_key.py] - KeeperKey model to integrate with
- [Source: src/application/ports/keeper_key_registry.py] - Registry pattern to follow
- [Source: src/application/services/keeper_signature_service.py] - Signature verification service
- [Source: _bmad-output/implementation-artifacts/stories/5-7-keeper-key-generation-ceremony.md] - Previous story patterns
- [Source: _bmad-output/implementation-artifacts/stories/5-6-keeper-key-cryptographic-signature.md] - Keeper signature patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

- Implementation follows TDD approach (RED-GREEN-REFACTOR)
- All 80 tests pass (68 unit + 12 integration)
- Domain model uses frozen dataclasses for immutability
- DeletePreventionMixin applied for audit trail preservation (FR76)
- HALT CHECK FIRST pattern implemented at all operation boundaries (CT-11)
- Weekly attestation periods align to Monday 00:00 UTC
- Quorum check triggers halt for count < 3 (FR79) and warning for count == 3 (SR-7)
- Signature verification via KeeperSignatureService integration
- Background task `check_attestation_deadlines()` is idempotent

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive FR77-FR79, SR-7 context | Create-Story Workflow (Opus 4.5) |
| 2026-01-07 | Implementation completed - all 8 tasks done, 80 tests passing | Dev Agent (Opus 4.5) |

### File List

**Created:**
- `src/domain/models/keeper_attestation.py` - KeeperAttestation domain model with constants
- `src/domain/events/keeper_availability.py` - Event payloads for attestation tracking
- `src/domain/errors/keeper_availability.py` - Keeper availability error classes
- `src/application/ports/keeper_availability.py` - KeeperAvailabilityProtocol ABC
- `src/application/services/keeper_availability_service.py` - Main service (FR77-FR79)
- `src/infrastructure/stubs/keeper_availability_stub.py` - In-memory test stub
- `tests/unit/domain/test_keeper_attestation.py` - 21 tests
- `tests/unit/domain/test_keeper_availability_events.py` - 18 tests
- `tests/unit/application/test_keeper_availability_service.py` - 17 tests
- `tests/unit/infrastructure/test_keeper_availability_stub.py` - 12 tests
- `tests/integration/test_keeper_availability_integration.py` - 12 tests

**Modified:**
- `src/domain/models/__init__.py` - Export KeeperAttestation and constants
- `src/domain/events/__init__.py` - Export event payloads and constants
- `src/domain/errors/__init__.py` - Export error classes
- `src/application/ports/__init__.py` - Export KeeperAvailabilityProtocol
- `src/application/services/__init__.py` - Export service and status dataclass
- `src/infrastructure/stubs/__init__.py` - Export KeeperAvailabilityStub
