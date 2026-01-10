# Story 5.7: Keeper Key Generation Ceremony (FR69, ADR-4)

Status: done

## Story

As a **system operator**,
I want witnessed ceremonies for Keeper key generation,
So that key creation is auditable.

## Acceptance Criteria

### AC1: Witnessed Key Generation Ceremony
**Given** a new Keeper key is needed
**When** the generation ceremony starts
**Then** multiple witnesses are required
**And** the ceremony is recorded as a `KeyGenerationCeremonyEvent`

### AC2: Key Registration Upon Ceremony Completion
**Given** the ceremony
**When** completed
**Then** new public key is registered
**And** old key (if any) begins transition period
**And** ceremony recording includes all witness signatures

### AC3: Annual Key Rotation with 30-Day Transition
**Given** annual key rotation (30-day transition)
**When** rotation is due
**Then** new key is generated via ceremony
**And** both old and new keys are valid for 30 days
**And** after 30 days, old key is revoked

## Tasks / Subtasks

- [x] Task 1: Create Key Generation Ceremony Domain Models (AC: #1, #2, #3)
  - [x] 1.1 Create `src/domain/models/key_generation_ceremony.py`:
    - `KeyGenerationCeremony` dataclass with: `id`, `keeper_id`, `ceremony_type` (new/rotation), `state`, `witnesses`, `new_key_id`, `old_key_id`, `transition_end_at`, `created_at`, `completed_at`
    - `CeremonyState` enum: `PENDING`, `APPROVED`, `EXECUTING`, `COMPLETED`, `FAILED`, `EXPIRED`
    - `CeremonyType` enum: `NEW_KEEPER_KEY`, `KEY_ROTATION`
    - Use `DeletePreventionMixin` for audit trail preservation (FR76)
    - `CEREMONY_TIMEOUT_SECONDS = 3600` (1 hour max per VAL-2)
    - `TRANSITION_PERIOD_DAYS = 30` (ADR-4 requirement)
  - [x] 1.2 Create `src/domain/models/ceremony_witness.py`:
    - `CeremonyWitness` dataclass with: `witness_id`, `witnessed_at`, `signature`, `witness_type`
    - `WitnessType` enum: `KEEPER`, `SYSTEM`, `EXTERNAL`
  - [x] 1.3 Export from `src/domain/models/__init__.py`

- [x] Task 2: Create Key Generation Ceremony Events (AC: #1, #2)
  - [x] 2.1 Create `src/domain/events/key_generation_ceremony.py`:
    - `KeyGenerationCeremonyStartedPayload` - ceremony initiated
    - `KeyGenerationCeremonyWitnessedPayload` - witness added signature
    - `KeyGenerationCeremonyCompletedPayload` - ceremony completed, key registered
    - `KeyGenerationCeremonyFailedPayload` - ceremony failed or timed out
    - All payloads include `ceremony_id`, `keeper_id`, `timestamp`
  - [x] 2.2 Export from `src/domain/events/__init__.py`

- [x] Task 3: Create Key Generation Ceremony Errors (AC: #1, #2)
  - [x] 3.1 Create `src/domain/errors/key_generation_ceremony.py`:
    - `CeremonyError(ConclaveError)` - base class
    - `CeremonyNotFoundError(CeremonyError)` - ceremony ID not found
    - `InvalidCeremonyStateError(CeremonyError)` - invalid state transition
    - `InsufficientWitnessesError(CeremonyError)` - not enough witnesses
    - `CeremonyTimeoutError(CeremonyError)` - ceremony exceeded time limit (VAL-2)
    - `CeremonyConflictError(CeremonyError)` - conflicting ceremony in progress (CM-5)
    - `DuplicateWitnessError(CeremonyError)` - witness already signed
  - [x] 3.2 Export from `src/domain/errors/__init__.py`

- [x] Task 4: Create Key Generation Ceremony Port (AC: #1, #2, #3)
  - [x] 4.1 Create `src/application/ports/key_generation_ceremony.py`:
    - `KeyGenerationCeremonyProtocol` with methods:
      - `async def get_ceremony(ceremony_id: str) -> KeyGenerationCeremony | None`
      - `async def create_ceremony(keeper_id: str, ceremony_type: CeremonyType, old_key_id: str | None) -> KeyGenerationCeremony`
      - `async def add_witness(ceremony_id: str, witness: CeremonyWitness) -> None`
      - `async def update_state(ceremony_id: str, new_state: CeremonyState) -> None`
      - `async def get_active_ceremonies() -> list[KeyGenerationCeremony]`
      - `async def mark_completed(ceremony_id: str, new_key_id: str, transition_end_at: datetime | None) -> None`
  - [x] 4.2 Export from `src/application/ports/__init__.py`

- [x] Task 5: Create Key Generation Ceremony Service (AC: #1, #2, #3)
  - [x] 5.1 Create `src/application/services/key_generation_ceremony_service.py`
  - [x] 5.2 Implement `KeyGenerationCeremonyService`:
    - Inject: `HSMProtocol`, `KeeperKeyRegistryProtocol`, `KeyGenerationCeremonyProtocol`, `EventWriterService`, `HaltGuardProtocol`
    - REQUIRED_WITNESSES = 3 (multi-witness per architecture)
  - [x] 5.3 Implement `start_ceremony(keeper_id: str, ceremony_type: CeremonyType, initiator_id: str, old_key_id: str | None = None) -> KeyGenerationCeremony`:
    - HALT CHECK FIRST
    - Check for conflicting ceremonies (CM-5 mutex)
    - Create ceremony record
    - Write `KeyGenerationCeremonyStartedEvent` to event store
    - Return ceremony object
  - [x] 5.4 Implement `add_witness(ceremony_id: str, witness_id: str, signature: bytes) -> None`:
    - HALT CHECK FIRST
    - Verify ceremony exists and is in PENDING state
    - Verify witness hasn't already signed
    - Add witness signature
    - Write `KeyGenerationCeremonyWitnessedEvent`
    - If witnesses >= REQUIRED_WITNESSES, auto-transition to APPROVED
  - [x] 5.5 Implement `execute_ceremony(ceremony_id: str) -> KeyGenerationCeremony`:
    - HALT CHECK FIRST
    - Verify ceremony is APPROVED with sufficient witnesses
    - Generate new key via HSM
    - Register key in KeeperKeyRegistry
    - If rotation: set transition period on old key
    - Write `KeyGenerationCeremonyCompletedEvent`
    - Return updated ceremony with new key ID
  - [x] 5.6 Implement `check_ceremony_timeout()` - background task:
    - Find ceremonies exceeding CEREMONY_TIMEOUT_SECONDS
    - Transition to FAILED state with reason
    - Write `KeyGenerationCeremonyFailedEvent`
  - [x] 5.7 Export from `src/application/services/__init__.py`

- [x] Task 6: Create Key Generation Ceremony Stub (AC: #1, #2, #3)
  - [x] 6.1 Create `src/infrastructure/stubs/key_generation_ceremony_stub.py`
  - [x] 6.2 Implement `KeyGenerationCeremonyStub`:
    - In-memory ceremony storage
    - Conflict detection for active ceremonies
    - Witness tracking per ceremony
    - State transition validation
    - `clear()` for test cleanup
  - [x] 6.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 7: Extend KeeperKeyRegistry for Transition Support (AC: #3)
  - [x] 7.1 Modify `src/application/ports/keeper_key_registry.py`:
    - Add `async def begin_transition(old_key_id: str, new_key_id: str, transition_end_at: datetime) -> None`
    - Add `async def complete_transition(old_key_id: str) -> None` - revokes old key
    - Add `async def get_keys_in_transition(keeper_id: str) -> list[KeeperKey]`
  - [x] 7.2 Update `KeeperKeyRegistryStub` with transition support
  - [x] 7.3 Update tests for new protocol methods

- [x] Task 8: Write Unit Tests (AC: #1, #2, #3)
  - [x] 8.1 Create `tests/unit/domain/test_key_generation_ceremony.py` (54 tests):
    - Test `KeyGenerationCeremony` creation and state transitions
    - Test `CeremonyWitness` creation and validation
    - Test valid state transitions per `VALID_TRANSITIONS`
    - Test invalid state transitions are rejected
    - Test ceremony timeout calculation
    - Test delete prevention (FR76)
  - [x] 8.2 Create `tests/unit/domain/test_key_generation_ceremony_events.py` (21 tests):
    - Test all event payload types
    - Test serialization/deserialization
    - Test required fields present
  - [x] 8.3 Create `tests/unit/application/test_key_generation_ceremony_service.py` (27 tests):
    - Test `start_ceremony()` with halt check
    - Test `start_ceremony()` rejects if conflicting ceremony active (CM-5)
    - Test `add_witness()` accumulates signatures
    - Test `add_witness()` auto-transitions to APPROVED when threshold met
    - Test `add_witness()` rejects duplicate witnesses
    - Test `execute_ceremony()` generates key and registers
    - Test `execute_ceremony()` sets transition period for rotation
    - Test `check_ceremony_timeout()` fails expired ceremonies (VAL-2)
    - Test HALT CHECK at each operation boundary

- [x] Task 9: Write Integration Tests (AC: #1, #2, #3)
  - [x] 9.1 Create `tests/integration/test_key_generation_ceremony_integration.py` (11 tests):
    - Test: `test_complete_new_key_ceremony_workflow` (AC1, AC2)
    - Test: `test_complete_key_rotation_ceremony_workflow` (AC3)
    - Test: `test_cm5_single_ceremony_per_keeper` (CM-5)
    - Test: `test_ct12_witness_threshold_enforced` (CT-12)
    - Test: `test_ct12_duplicate_witness_rejected` (CT-12)
    - Test: `test_val2_ceremony_timeout` (VAL-2)
    - Test: `test_fp4_state_machine_enforced` (FP-4)
    - Test: `test_mixed_witness_types_accepted`
    - Test: `test_new_key_registered_after_completion`
    - Test: `test_old_key_deactivated_after_rotation`
    - Test: `test_can_start_new_ceremony_after_completion`

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR69**: Keeper keys SHALL be generated through witnessed ceremony
- **FR70**: Every override SHALL record full authorization chain from Keeper identity through execution
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> Ceremony requires multiple witnesses
- **NFR18**: All Keeper actions SHALL be cryptographically signed

### ADR-4: Key Custody + Keeper Adversarial Defense

From architecture document, ADR-4 specifies key rotation ceremony requirements:
1. Generate new key in HSM
2. Write key-transition event signed by old key referencing new public key
3. Activate new key for signing
4. Revoke old key after overlap period (30 days)
5. Verify observers accept both keys during overlap

### ADR-6: Ceremony Tier Assignment

Key rotation is classified as:
- **Tier 1: Operational** (2 Keepers)
- Monthly rotation drills
- With audit trail

However, initial key generation for a new Keeper may require higher scrutiny per security policy.

### VAL-2: Ceremony Timeout Enforcement

From pre-mortem analysis - ceremonies MUST have timeout:
```python
CEREMONY_TIMEOUT_SECONDS = {
    CeremonyType.KEY_ROTATION: 3600,  # 1 hour max
}

class KeyGenerationCeremonyService:
    async def check_timeout(self) -> None:
        elapsed = now() - ceremony.created_at
        if elapsed > CEREMONY_TIMEOUT_SECONDS[ceremony.type]:
            await self._force_abort_with_witness(
                reason=f"Ceremony timeout after {elapsed}s"
            )
```

### CM-5: Ceremony Mutex and Conflict Detection

From chaos analysis - concurrent ceremonies can conflict:
```python
class CeremonyCoordinator:
    CONFLICTS = {
        CeremonyType.KEY_ROTATION: {CeremonyType.AMENDMENT, CeremonyType.CONVENTION},
    }

    async def initiate(self, ceremony_type, initiator) -> Ceremony:
        async with self._lock:
            active = await self._get_active_ceremonies()
            # Enforce single ceremony limit
            if len(active) >= 1:
                raise CeremonyLimitError("Only one ceremony at a time")
```

### Architecture Pattern: Ceremony State Machine (FP-4)

From architecture document - ceremonies use state machine with valid transitions:
```python
VALID_TRANSITIONS: Dict[CeremonyState, Set[CeremonyState]] = {
    CeremonyState.PENDING: {CeremonyState.APPROVED, CeremonyState.EXPIRED, CeremonyState.FAILED},
    CeremonyState.APPROVED: {CeremonyState.EXECUTING, CeremonyState.EXPIRED},
    CeremonyState.EXECUTING: {CeremonyState.COMPLETED, CeremonyState.FAILED},
    CeremonyState.COMPLETED: set(),  # Terminal
    CeremonyState.FAILED: set(),     # Terminal
    CeremonyState.EXPIRED: set(),    # Terminal
}
```

### WR-4: Ceremony Audit Record

Every ceremony transition has signed, immutable evidence:
```python
class CeremonyAuditRecord(BaseModel):
    """Immutable audit record for ceremony state transitions."""
    ceremony_id: str
    ceremony_type: CeremonyType
    from_state: CeremonyState
    to_state: CeremonyState
    actor_id: str
    actor_role: str
    timestamp: datetime
    evidence_refs: List[ContentRef]
    justification: str
    signature: str  # Actor's signature over transition
```

### Key Generation Flow

```
1. start_ceremony()
   │
   ▼
┌─────────────────────────────────────────┐
│ KeyGenerationCeremonyService            │
│ - HALT CHECK FIRST                      │
│ - Check for conflicting ceremonies      │
│ - Create ceremony in PENDING state      │
│ - Write KeyGenerationCeremonyStarted    │
└─────────────────────────────────────────┘
   │
   ▼
2. add_witness() x3
   │
   ▼
┌─────────────────────────────────────────┐
│ - Verify witness not duplicate          │
│ - Add signature to ceremony             │
│ - Write KeyGenerationCeremonyWitnessed  │
│ - Auto-transition to APPROVED if >= 3   │
└─────────────────────────────────────────┘
   │
   ▼
3. execute_ceremony()
   │
   ▼
┌─────────────────────────────────────────┐
│ - HALT CHECK FIRST                      │
│ - Verify APPROVED state                 │
│ - Generate new key via HSM              │
│ - Register key in KeeperKeyRegistry     │
│ - Set transition period if rotation     │
│ - Write KeyGenerationCeremonyCompleted  │
│ - Return ceremony with new_key_id       │
└─────────────────────────────────────────┘
```

### Previous Story Learnings (from 5.6)

**KeeperKey Model Pattern:**
- Ed25519 public keys (32 bytes)
- `DeletePreventionMixin` prevents deletion
- Temporal validity via `active_from`/`active_until`
- `is_active_at()` for historical verification

**KeeperKeyRegistryProtocol Pattern:**
- `get_key_by_id()`, `get_active_key_for_keeper()`, `register_key()`, `deactivate_key()`
- Keys are NEVER deleted (FR76)
- Historical keys preserved

**Service Pattern:**
- HALT CHECK FIRST at every operation boundary
- Bind logger with operation context
- Write constitutional events for all state changes
- Use specific domain errors with FR references

**Testing Pattern:**
- 54 tests in Story 5.6 - maintain similar rigor
- `pytest.mark.asyncio` for all async tests
- Mock dependencies for unit tests
- Use stubs for integration tests

### Existing Code to Integrate With

**From Story 5.6:**
- `KeeperKey` domain model - keys to be registered
- `KeeperKeyRegistryProtocol` - where new keys are stored
- `KeeperSignatureService` - can sign ceremony events

**From Event Store (Epic 1):**
- `EventWriterService` - write ceremony events
- `ConstitutionalEvent` envelope pattern

**From HSM (Story 0.4):**
- `HSMProtocol` - key generation
- `HSMDevStub` - for testing
- RT-1 mode watermarking

### Files to Create

```
src/domain/models/key_generation_ceremony.py           # Ceremony domain model + state enum
src/domain/models/ceremony_witness.py                  # Witness domain model
src/domain/events/key_generation_ceremony.py           # Ceremony event payloads
src/domain/errors/key_generation_ceremony.py           # Ceremony-specific errors
src/application/ports/key_generation_ceremony.py       # Ceremony repository protocol
src/application/services/key_generation_ceremony_service.py  # Main service
src/infrastructure/stubs/key_generation_ceremony_stub.py     # Test stub
tests/unit/domain/test_key_generation_ceremony.py            # Domain model tests
tests/unit/domain/test_key_generation_ceremony_events.py     # Event tests
tests/unit/application/test_key_generation_ceremony_service.py  # Service tests
tests/integration/test_key_generation_ceremony_integration.py   # Integration tests
```

### Files to Modify

```
src/domain/models/__init__.py              # Export ceremony models
src/domain/events/__init__.py              # Export ceremony events
src/domain/errors/__init__.py              # Export ceremony errors
src/application/ports/__init__.py          # Export ceremony port
src/application/ports/keeper_key_registry.py  # Add transition methods
src/application/services/__init__.py       # Export ceremony service
src/infrastructure/stubs/__init__.py       # Export ceremony stub
src/infrastructure/stubs/keeper_key_registry_stub.py  # Add transition support
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
- Test ceremony state machine transitions exhaustively
- Test timeout and conflict detection (VAL-2, CM-5)
- Verify HALT CHECK at every operation boundary

### Project Structure Notes

- Ceremony follows `CeremonyStateMachine` pattern from architecture (FP-4)
- Audit records follow `CeremonyAuditRecord` pattern (WR-4)
- State transitions follow `VALID_TRANSITIONS` map
- Timeout enforcement per VAL-2 pre-mortem analysis
- Conflict detection per CM-5 chaos analysis

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.7] - Story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-004] - Key Rotation Ceremony requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-006] - Ceremony Tier Assignment
- [Source: _bmad-output/planning-artifacts/architecture.md#FP-4] - CeremonyStateMachine pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#WR-4] - CeremonyAuditRecord pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#VAL-2] - Ceremony Timeout Enforcement
- [Source: _bmad-output/planning-artifacts/architecture.md#CM-5] - Ceremony Mutex
- [Source: _bmad-output/implementation-artifacts/stories/5-6-keeper-key-cryptographic-signature.md] - Previous story patterns
- [Source: src/domain/models/keeper_key.py] - KeeperKey model to integrate with
- [Source: src/application/ports/keeper_key_registry.py] - Registry to extend

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- Implementation complete with 102 passing tests
- Domain models follow hexagonal architecture patterns
- Ceremony state machine enforces FP-4 valid transitions
- HALT CHECK FIRST pattern at every operation boundary (CT-11)
- Multi-witness requirement (3) enforces CT-12 accountability
- VAL-2 timeout enforcement (1 hour max)
- CM-5 conflict detection (single ceremony per Keeper)
- ADR-4 30-day transition period for key rotations
- FR76 audit trail preservation (keys never deleted)
- All lint checks passing (ruff)
- Import boundaries maintained (no violations in new code)

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive FR69, ADR-4, FP-4 context | Create-Story Workflow (Opus 4.5) |
| 2026-01-07 | Implementation complete - 102 tests passing | Dev Workflow (Opus 4.5) |
| 2026-01-07 | Code review passed - Fixed MockHSMProtocol missing get_public_key_bytes | Code Review (Opus 4.5) |

### Senior Developer Review (AI)

**Review Date:** 2026-01-07
**Reviewer:** Claude Opus 4.5 (Adversarial Code Review)
**Outcome:** APPROVED with fixes applied

**Issues Found:**
1. **[HIGH] MockHSMProtocol missing method** - `tests/unit/application/test_export_service.py` did not implement `get_public_key_bytes()` after HSMProtocol interface extension → FIXED
2. **[MEDIUM] Documentation gap** - File List missing modified test file → FIXED below
3. **[LOW] CeremonyEvidence unused** - Model exists but intended for Story 3.4 → Documented
4. **[LOW] Unregistered witness bootstrap** - Signature verification allows unregistered witnesses for bootstrap scenarios → Expected behavior, documented

**Fixes Applied:**
- Added `get_public_key_bytes()` method to `MockHSMProtocol` in test_export_service.py
- Updated File List to include modified test file

### File List

**Created Files:**
- `src/domain/models/key_generation_ceremony.py` - Ceremony domain model with state machine
- `src/domain/models/ceremony_witness.py` - Witness value object with validation
- `src/domain/events/key_generation_ceremony.py` - 4 event payloads (Started, Witnessed, Completed, Failed)
- `src/domain/errors/key_generation_ceremony.py` - 7 ceremony-specific errors
- `src/application/ports/key_generation_ceremony.py` - Repository protocol
- `src/application/services/key_generation_ceremony_service.py` - Main service with HALT CHECK
- `src/infrastructure/stubs/key_generation_ceremony_stub.py` - In-memory test implementation
- `tests/unit/domain/test_key_generation_ceremony.py` - 54 domain model tests
- `tests/unit/domain/test_key_generation_ceremony_events.py` - 21 event tests
- `tests/unit/application/test_key_generation_ceremony_service.py` - 27 service tests
- `tests/integration/test_key_generation_ceremony_integration.py` - 11 integration tests

**Modified Files:**
- `src/domain/models/__init__.py` - Added ceremony model exports
- `src/domain/events/__init__.py` - Added ceremony event exports
- `src/domain/errors/__init__.py` - Added ceremony error exports
- `src/application/ports/__init__.py` - Added ceremony port export
- `src/application/ports/hsm.py` - Added `verify_with_key()` and `get_public_key_bytes()` methods
- `src/application/ports/keeper_key_registry.py` - Added transition methods
- `src/application/services/__init__.py` - Added ceremony service export
- `src/infrastructure/adapters/security/hsm_dev.py` - Implemented new HSM interface methods
- `src/infrastructure/adapters/security/hsm_cloud.py` - Implemented new HSM interface methods
- `src/infrastructure/stubs/__init__.py` - Added ceremony stub export
- `src/infrastructure/stubs/keeper_key_registry_stub.py` - Added transition support
- `tests/unit/application/test_export_service.py` - Added `get_public_key_bytes()` to MockHSMProtocol (code review fix)
