# Story 8.5: Pre-Operational Verification (FR146, NFR35)

Status: done

## Story

As a **system operator**,
I want a pre-operational verification checklist on startup,
So that the system doesn't start in a bad state.

## Acceptance Criteria

### AC1: Verification Checklist Execution
**Given** application startup
**When** the application begins
**Then** a verification checklist runs
**And** startup is blocked if any check fails
**And** the checklist completes before ready state

### AC2: Checklist Components (FR146)
**Given** the verification checklist
**When** I examine it
**Then** it includes:
- Hash chain integrity verification
- Witness pool availability
- Keeper key availability
- Checkpoint anchors existence
- Halt state check
- Replica sync status (if replicas configured)

### AC3: Verification Failure Blocking
**Given** a verification failure
**When** it occurs
**Then** specific failure is logged with details
**And** system does not proceed to ready state
**And** failure reason is clear for operator remediation
**And** partial startup does not occur

### AC4: Bypass for Continuous Restarts (FR146 MVP Note)
**Given** continuous restarts scenario
**When** system restarts multiple times rapidly
**Then** verification can be bypassed with logged bypass event
**And** bypass reason is recorded
**And** bypass is limited (not indefinite)
**Note:** MVP: applies to initial startup and post-halt; continuous restarts may bypass with logged bypass.

### AC5: Post-Halt Verification
**Given** system recovering from halt state
**When** startup occurs after halt
**Then** full verification checklist runs
**And** no bypass allowed post-halt
**And** verification is more stringent than normal startup

## Tasks / Subtasks

- [x] **Task 1: Create Pre-Operational Verification Service** (AC: 1,2,3)
  - [x] Create `src/application/services/pre_operational_verification_service.py`
    - [x] `PreOperationalVerificationService` class
    - [x] `run_verification_checklist() -> VerificationResult`
    - [x] Inject all required port dependencies
    - [x] Log each verification step and result
  - [x] Create `src/domain/models/verification_result.py`
    - [x] `VerificationResult` dataclass
    - [x] `VerificationCheck` dataclass (name, passed, details, duration_ms)
    - [x] `VerificationStatus` enum (PASSED, FAILED, BYPASSED)
  - [x] Export from `src/application/services/__init__.py`
  - [x] Export from `src/domain/models/__init__.py`

- [x] **Task 2: Implement Hash Chain Verification Check** (AC: 2)
  - [x] Add `verify_hash_chain() -> VerificationCheck` method
  - [x] Use `HashVerifierProtocol` to verify chain integrity
  - [x] Verify last N events (configurable, default 1000)
  - [x] Fail if any hash mismatch found
  - [x] Log verification stats (events checked, duration)

- [x] **Task 3: Implement Witness Pool Check** (AC: 2)
  - [x] Add `verify_witness_pool() -> VerificationCheck` method
  - [x] Use `WitnessPoolMonitorProtocol` to check availability
  - [x] Verify minimum witness count (6 for standard, 12 for high-stakes)
  - [x] Log pool status (available count, degraded status)
  - [x] Fail if pool is below minimum threshold

- [x] **Task 4: Implement Keeper Key Check** (AC: 2)
  - [x] Add `verify_keeper_keys() -> VerificationCheck` method
  - [x] Use `KeeperKeyRegistryPort` to check key availability
  - [x] Verify at least one active Keeper key exists
  - [x] Check key validity (not expired, not revoked)
  - [x] Log key status (count, validity)

- [x] **Task 5: Implement Checkpoint Anchors Check** (AC: 2)
  - [x] Add `verify_checkpoint_anchors() -> VerificationCheck` method
  - [x] Use `CheckpointRepository` to check for anchors
  - [x] Verify at least one checkpoint exists (for non-fresh start)
  - [x] Check checkpoint freshness (within configured threshold)
  - [x] Log checkpoint status (count, most recent)

- [x] **Task 6: Implement Halt State Check** (AC: 2)
  - [x] Add `verify_halt_state() -> VerificationCheck` method
  - [x] Use `HaltChecker` to check current halt status
  - [x] If halted, include halt reason in verification result
  - [x] Log halt state and reason if applicable
  - [x] Note: Halt state doesn't fail verification, but flags it

- [x] **Task 7: Implement Replica Sync Check** (AC: 2)
  - [x] Add `verify_replica_sync() -> VerificationCheck` method
  - [x] Use `EventReplicatorPort` to check sync status
  - [x] If replicas configured, verify they are in sync
  - [x] Log sync lag and replica count
  - [x] Skip if no replicas configured (pass by default)

- [x] **Task 8: Integrate with Startup Flow** (AC: 1,3)
  - [x] Modify `src/api/startup.py`
    - [x] Add `run_pre_operational_verification()` function
    - [x] Call after `validate_configuration_floors_at_startup()`
    - [x] Raise `PreOperationalVerificationError` on failure
  - [x] Modify `src/api/main.py` lifespan
    - [x] Add verification step to lifespan startup
    - [x] Ensure startup blocks on failure
  - [x] Create `src/domain/errors/pre_operational.py`
    - [x] `PreOperationalVerificationError` with failure details
  - [x] Export from `src/domain/errors/__init__.py`

- [x] **Task 9: Implement Bypass Logic** (AC: 4)
  - [x] Add bypass configuration to verification service
    - [x] `VERIFICATION_BYPASS_ENABLED` environment variable
    - [x] `VERIFICATION_BYPASS_MAX_COUNT` (default 3)
    - [x] `VERIFICATION_BYPASS_WINDOW_SECONDS` (default 300)
  - [x] Track bypass count in transient storage
  - [x] Log bypass events with justification
  - [x] Create `VerificationBypassedEvent` for witnessing
  - [x] Never allow bypass post-halt

- [x] **Task 10: Post-Halt Stringent Verification** (AC: 5)
  - [x] Add `is_post_halt_recovery` parameter to verification
  - [x] When post-halt, enable additional checks:
    - [x] Full hash chain verification (not just last N)
    - [x] All checkpoints verified (not just existence)
    - [x] No bypass allowed
  - [x] Log post-halt verification mode
  - [x] Create `PostHaltVerificationStarted` event

- [x] **Task 11: Unit Tests** (AC: 1,2,3,4,5)
  - [x] Create `tests/unit/application/test_pre_operational_verification_service.py`
    - [x] Test all verification checks pass returns PASSED
    - [x] Test single failure returns FAILED with details
    - [x] Test multiple failures all captured
    - [x] Test bypass logic respects limits
    - [x] Test post-halt prevents bypass
    - [x] Test each individual check method
  - [x] Create `tests/unit/domain/test_verification_result.py`
    - [x] Test VerificationResult construction
    - [x] Test VerificationCheck construction
    - [x] Test status enum values

- [x] **Task 12: Integration Tests** (AC: 1,2,3,5)
  - [x] Create `tests/integration/test_pre_operational_verification_integration.py`
    - [x] Test full checklist execution
    - [x] Test startup blocked on hash chain failure
    - [x] Test startup blocked on witness pool failure
    - [x] Test startup proceeds when all checks pass
    - [x] Test post-halt verification mode
    - [x] Test verification results are logged correctly
    - [x] Test timing (verification should complete in reasonable time)

## Dev Notes

### Relevant Architecture Patterns and Constraints

**FR146 (Pre-Operational Verification) - CRITICAL:**
- Startup SHALL execute verification checklist:
  - Hash chain integrity
  - Witness pool availability
  - Keeper key availability
  - Checkpoint anchors existence
- Blocked until pass
- MVP: applies to initial startup and post-halt; continuous restarts may bypass with logged bypass

**NFR35 (Startup Verification):**
- System startup SHALL complete verification checklist before operation
- No traffic until verification passes

**CT-13 (Integrity > Availability):**
- Startup failure is preferable to operating with unverified state
- Post-halt verification must be more stringent

### Source Tree Components to Touch

**Files to Create:**
```
src/application/services/pre_operational_verification_service.py
src/domain/models/verification_result.py
src/domain/errors/pre_operational.py
tests/unit/application/test_pre_operational_verification_service.py
tests/unit/domain/test_verification_result.py
tests/integration/test_pre_operational_verification_integration.py
```

**Files to Modify:**
```
src/api/startup.py                              # Add verification step
src/api/main.py                                 # Update lifespan
src/application/services/__init__.py            # Export service
src/domain/models/__init__.py                   # Export models
src/domain/errors/__init__.py                   # Export error
```

### Related Existing Code (MUST Review)

**Startup Flow (Current Implementation):**
- `src/api/startup.py` - Configuration floor validation at startup
- `src/api/main.py` - Lifespan manager with startup hooks
- Story 6.10 established the startup validation pattern

**Hash Verification (MUST Use):**
- `src/application/ports/hash_verifier.py` - HashVerifierProtocol
- `src/infrastructure/stubs/hash_verifier_stub.py` - Stub implementation
- Story 1.2, 3.7 established hash chain patterns

**Witness Pool (MUST Use):**
- `src/application/ports/witness_pool.py` - WitnessPoolProtocol
- `src/application/ports/witness_pool_monitor.py` - WitnessPoolMonitorProtocol
- `src/infrastructure/stubs/witness_pool_monitor_stub.py` - Stub implementation
- Story 6.6 established witness pool monitoring

**Keeper Key Registry (MUST Use):**
- `src/application/ports/keeper_key_registry.py` - KeeperKeyRegistryPort
- `src/infrastructure/stubs/keeper_key_registry_stub.py` - Stub implementation
- Story 5.6 established Keeper key patterns

**Checkpoint Repository (MUST Use):**
- `src/application/ports/checkpoint_repository.py` - CheckpointRepository
- `src/infrastructure/stubs/checkpoint_repository_stub.py` - Stub implementation
- Story 3.10 established checkpoint patterns

**Halt Checker (MUST Use):**
- `src/application/ports/halt_checker.py` - HaltChecker
- `src/infrastructure/stubs/halt_checker_stub.py` - Stub implementation
- Story 3.4 established halt state checking

**Event Replicator (MUST Use):**
- `src/application/ports/event_replicator.py` - EventReplicatorPort
- `src/infrastructure/stubs/event_replicator_stub.py` - Stub implementation
- Story 1.10 established replica patterns

### Design Decisions

**Verification Order:**
```python
# Order matters - fail fast on most critical checks
checks = [
    self.verify_halt_state,           # Know state first
    self.verify_hash_chain,           # Integrity is paramount
    self.verify_checkpoint_anchors,   # Recovery capability
    self.verify_keeper_keys,          # Signing capability
    self.verify_witness_pool,         # Witnessing capability
    self.verify_replica_sync,         # Replication health
]
```

**Result Aggregation:**
```python
@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus  # PASSED, FAILED, BYPASSED
    checks: tuple[VerificationCheck, ...]
    started_at: datetime
    completed_at: datetime
    is_post_halt: bool = False
    bypass_reason: str | None = None

    @property
    def failed_checks(self) -> tuple[VerificationCheck, ...]:
        return tuple(c for c in self.checks if not c.passed)

    @property
    def duration_ms(self) -> float:
        return (self.completed_at - self.started_at).total_seconds() * 1000
```

**Bypass Logic:**
```python
# Bypass is NEVER allowed when:
# 1. Post-halt recovery
# 2. Bypass limit exceeded
# 3. Bypass disabled by config

def can_bypass(self) -> bool:
    if self.is_post_halt:
        return False
    if not self.bypass_enabled:
        return False
    if self.bypass_count >= self.bypass_max_count:
        return False
    return True
```

**Startup Integration:**
```python
# In startup.py
async def run_pre_operational_verification(is_post_halt: bool = False) -> None:
    """Run pre-operational verification checklist.

    Args:
        is_post_halt: True if recovering from halt state.

    Raises:
        PreOperationalVerificationError: If verification fails.
    """
    service = PreOperationalVerificationService(
        hash_verifier=get_hash_verifier(),
        witness_pool_monitor=get_witness_pool_monitor(),
        keeper_key_registry=get_keeper_key_registry(),
        checkpoint_repository=get_checkpoint_repository(),
        halt_checker=get_halt_checker(),
        event_replicator=get_event_replicator(),
    )

    result = await service.run_verification_checklist(is_post_halt=is_post_halt)

    if result.status == VerificationStatus.FAILED:
        raise PreOperationalVerificationError(
            failed_checks=result.failed_checks,
            result=result,
        )
```

### Testing Standards Summary

- **Unit Tests Location**: `tests/unit/application/`, `tests/unit/domain/`
- **Integration Tests Location**: `tests/integration/`
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Mock all port dependencies (hash verifier, witness pool, etc.)
- **Coverage**: All verification checks, bypass logic, post-halt mode

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Service: `src/application/services/pre_operational_verification_service.py`
- Models: `src/domain/models/verification_result.py`
- Errors: `src/domain/errors/pre_operational.py`
- Uses ports: hash_verifier, witness_pool_monitor, keeper_key_registry, checkpoint_repository, halt_checker, event_replicator

**Import Rules:**
- Service imports ports and domain
- Models import nothing (pure data)
- Errors import nothing (pure exceptions)
- Startup imports service and domain errors

### Previous Story Intelligence (8-4)

**Learnings from Story 8-4 (Incident Reporting):**
1. **Status workflow pattern** - DRAFT → PENDING_PUBLICATION → PUBLISHED
2. **Event payloads** - Include `signable_content()` for CT-12 witnessing
3. **Configuration values** - 7-day delays, >3 thresholds work well
4. **Repository stub pattern** - In-memory storage with proper interface

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit patterns:**
- Feature commits use `feat(story-X.Y):` prefix
- Include FR reference in commit message
- Co-Authored-By footer for AI assistance

### Environment Variables

```
# Verification configuration
VERIFICATION_HASH_CHAIN_LIMIT=1000           # Events to verify (default 1000)
VERIFICATION_CHECKPOINT_MAX_AGE_HOURS=168    # Max checkpoint age (default 7 days)
VERIFICATION_BYPASS_ENABLED=false            # Allow bypass (default false)
VERIFICATION_BYPASS_MAX_COUNT=3              # Max bypass count (default 3)
VERIFICATION_BYPASS_WINDOW_SECONDS=300       # Bypass window (default 5 min)
```

### Edge Cases to Test

1. **Fresh install**: No checkpoints exist - should pass with warning
2. **Hash chain corruption**: Single bad hash - must fail
3. **Empty witness pool**: Pool < 6 - must fail
4. **Expired Keeper keys**: All keys expired - must fail
5. **Replica lag**: Replicas out of sync - should warn/fail based on lag
6. **Post-halt recovery**: More stringent verification required
7. **Rapid restarts**: Bypass logic kicks in after threshold
8. **Bypass exhaustion**: No bypass after max count
9. **Concurrent startup**: Multiple instances starting simultaneously
10. **Verification timeout**: Single check takes too long

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.5] - Story requirements
- [Source: _bmad-output/planning-artifacts/prd.md#FR146] - Functional requirements
- [Source: _bmad-output/planning-artifacts/prd.md#NFR35] - NFR requirement
- [Source: src/api/startup.py] - Current startup flow
- [Source: src/api/main.py] - Application lifespan
- [Source: src/application/ports/hash_verifier.py] - Hash verification port
- [Source: src/application/ports/witness_pool_monitor.py] - Witness pool port
- [Source: src/application/ports/checkpoint_repository.py] - Checkpoint port
- [Source: _bmad-output/project-context.md] - Project rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Python 3.10 compatibility fix: Changed `from datetime import UTC` to `from datetime import timezone` with `datetime.now(timezone.utc)`
- Checkpoint model field fix: Changed `created_at` to `timestamp` for age calculation
- KeeperKeyRegistryStub enhancement: Added `with_dev_key=True` parameter for startup verification

### Completion Notes List

1. **PreOperationalVerificationService** - Implements FR146 verification checklist with 6 checks:
   - Halt state (informational, doesn't block)
   - Hash chain integrity (limited scan in normal mode, full scan post-halt)
   - Checkpoint anchors (freshness check with 168-hour threshold)
   - Keeper keys (requires at least one active key)
   - Witness pool (minimum 6 witnesses required)
   - Replica sync (validates if replicas configured)

2. **Verification Result Model** - Immutable dataclass with:
   - `VerificationStatus` enum (PASSED, FAILED, BYPASSED)
   - `VerificationCheck` for individual check results
   - `VerificationResult` aggregating all checks with timing and metadata
   - Helper properties: `failed_checks`, `passed_checks`, `duration_ms`
   - `to_summary()` method for human-readable output

3. **Bypass Logic** - Configurable via environment variables:
   - `VERIFICATION_BYPASS_ENABLED` (default: false)
   - `VERIFICATION_BYPASS_MAX_COUNT` (default: 3)
   - `VERIFICATION_BYPASS_WINDOW_SECONDS` (default: 300)
   - Bypass NEVER allowed post-halt (CT-13 enforcement)

4. **Startup Integration**:
   - `run_pre_operational_verification()` in startup.py
   - Called after configuration floor validation
   - Raises `PreOperationalVerificationError` on failure
   - Supports `is_post_halt` parameter for stringent mode

5. **KeeperKeyRegistryStub Enhancement**:
   - Added `with_dev_key=True` parameter to constructor
   - Dev mode automatically includes a KEEPER:primary key
   - Allows startup verification to pass in development
   - Existing tests updated to use `with_dev_key=False`

### File List

**Created:**
- `src/domain/models/verification_result.py` - Domain models for verification
- `src/domain/errors/pre_operational.py` - Error classes (PreOperationalVerificationError, VerificationCheckError, BypassNotAllowedError, PostHaltVerificationRequiredError)
- `src/application/services/pre_operational_verification_service.py` - Main verification service
- `tests/unit/domain/test_verification_result.py` - 28 unit tests for domain models
- `tests/unit/application/test_pre_operational_verification_service.py` - 27 unit tests for service
- `tests/integration/test_pre_operational_verification_integration.py` - 16 integration tests

**Modified:**
- `src/domain/models/__init__.py` - Export verification models
- `src/domain/errors/__init__.py` - Export pre-operational errors
- `src/application/services/__init__.py` - Export service and constants
- `src/api/startup.py` - Add run_pre_operational_verification() function
- `src/api/main.py` - Add verification to lifespan startup
- `src/infrastructure/stubs/keeper_key_registry_stub.py` - Add with_dev_key parameter
- `tests/unit/application/test_key_generation_ceremony_service.py` - Use with_dev_key=False
- `tests/unit/application/test_keeper_key_registry_port.py` - Use with_dev_key=False
- `tests/integration/test_keeper_key_signature_integration.py` - Use with_dev_key=False
- `tests/integration/test_key_generation_ceremony_integration.py` - Use with_dev_key=False

### Test Results

- **Unit Tests**: 55 passing (28 domain + 27 service)
- **Integration Tests**: 16 passing
- **Regression Tests**: All existing KeeperKeyRegistryStub tests pass (59 tests)
- **Total**: 71 Story 8.5 tests passing

## Change Log

- 2026-01-08: Story created via workflow-status command with comprehensive context
- 2026-01-08: Implementation completed - all 12 tasks done, 71 tests passing
