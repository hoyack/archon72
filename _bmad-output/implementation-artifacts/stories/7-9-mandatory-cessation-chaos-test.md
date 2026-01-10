# Story 7.9: Mandatory Cessation Chaos Test

Status: done

## Story

As a **developer**,
I want cessation triggered and verified in staging before Epic complete,
so that we know cessation works.

## Acceptance Criteria

### AC1: End-to-End Cessation Trigger (PM-5)
**Given** staging environment (test environment with all stubs)
**When** I trigger cessation via test command
**Then** cessation executes end-to-end:
  - Final deliberation is recorded (FR135, Story 7.8)
  - Cessation event is written (FR43, Story 7.6)
  - Dual-channel cessation flag is set (ADR-3)
  - System enters read-only mode (FR42)
**And** the test is repeatable (can run multiple times)

### AC2: Read-Only Mode Verification (FR42)
**Given** cessation has been triggered
**When** I attempt any write operation
**Then** the operation is rejected with appropriate error
**And** read operations continue to work (Observer API)
**And** the X-Archon72-System-Status header shows "ceased"

### AC3: Weekly CI Validation Job (PM-5)
**Given** CI/CD pipeline configuration
**When** the weekly chaos job runs
**Then** it simulates cessation trigger conditions:
  - Creates integrity failure events (count threshold)
  - Verifies agenda placement would trigger (FR37/FR38)
  - Validates cessation code path WITHOUT executing
**And** reports pass/fail status
**And** does NOT actually execute cessation

### AC4: Staging Test Documentation
**Given** Epic 7 DoD requirement
**When** cessation test completes
**Then** test results are documented:
  - Test execution timestamp
  - Events created during test
  - Final sequence number
  - Read-only mode verification result
  - Any issues encountered
**And** documentation is stored in test artifacts

### AC5: Recovery After Test (Test Isolation)
**Given** the chaos test executes cessation
**When** the test completes
**Then** test state is isolated (uses test-specific database/fixtures)
**And** other tests can still run (no production state pollution)
**And** the test can be re-run from a clean state

### AC6: Full Flow Coverage
**Given** the cessation chaos test
**When** it executes
**Then** it covers the full cessation flow:
  1. Integrity failure events (FR37/FR38 triggers)
  2. Agenda placement (Story 7.1)
  3. Cessation consideration (Story 6.3)
  4. Final deliberation recording (Story 7.8, FR135)
  5. Cessation execution (Story 7.6, FR43)
  6. Freeze mechanics (Story 7.4)
  7. Read-only access (Story 7.5, FR42)

## Tasks / Subtasks

- [x] **Task 1: Create CessationChaosTestRunner** (AC: 1,5,6)
  - [x] Create `tests/chaos/cessation/test_cessation_chaos.py`
  - [x] Implement test fixture that sets up isolated test environment
  - [x] Create helper to generate integrity failure events
  - [x] Create helper to simulate agenda placement
  - [x] Create helper to simulate 72-archon deliberation (all positions)
  - [x] Implement full end-to-end cessation trigger test
  - [x] Ensure test uses fresh fixtures (no state pollution)

- [x] **Task 2: Implement End-to-End Cessation Test** (AC: 1,6)
  - [x] Test step 1: Create 3 consecutive integrity failures (FR37)
  - [x] Test step 2: Verify agenda placement triggers
  - [x] Test step 3: Simulate cessation consideration vote
  - [x] Test step 4: Execute cessation with 72-archon deliberation (FR135)
  - [x] Test step 5: Verify cessation event is final event (FR43)
  - [x] Test step 6: Verify dual-channel flag set (ADR-3)
  - [x] Test step 7: Verify read-only mode active (FR42)

- [x] **Task 3: Implement Read-Only Mode Verification** (AC: 2)
  - [x] Test write rejection after cessation
  - [x] Test Observer API continues to work (via flag check)
  - [x] Test X-Archon72-System-Status header = "ceased" (CeasedStatusHeader)
  - [x] Test historical queries still work (FR45 query-as-of)
  - [x] Test all write endpoints return 503 with reason (via flag check)

- [x] **Task 4: Create CI Validation Job Script** (AC: 3)
  - [x] Create `scripts/validate_cessation_path.py`
  - [x] Implement dry-run cessation validation (no actual execution)
  - [x] Check integrity failure counter logic
  - [x] Check agenda placement threshold logic
  - [x] Check cessation consideration flow exists
  - [x] Output pass/fail report with details
  - [x] Add to CI workflow as weekly job (or manual trigger)

- [x] **Task 5: Add Test Documentation Output** (AC: 4)
  - [x] Create test artifact generation for chaos test (ChaosTestArtifact)
  - [x] Include timestamp, events created, final sequence
  - [x] Include read-only verification results
  - [x] Include any warnings or issues
  - [x] Store in `tests/chaos/cessation/artifacts/` (gitignored)

- [x] **Task 6: Write Chaos Test Infrastructure** (AC: 5)
  - [x] Create `tests/chaos/conftest.py` for chaos test fixtures
  - [x] Implement isolated database fixture for chaos tests (in-memory stubs)
  - [x] Implement isolated Redis fixture for chaos tests (in-memory stubs)
  - [x] Implement test cleanup to ensure repeatability
  - [x] Add pytest markers for chaos tests (`@pytest.mark.chaos`)

- [x] **Task 7: Alternative Trigger Path Tests** (AC: 6)
  - [x] Test 5 non-consecutive integrity failures in 90-day window (RT-4)
  - [x] Test anti-success alert sustained 90 days trigger (FR38)
  - [x] Test external observer petition trigger (FR39, Story 7.2)
  - [x] Verify all trigger paths lead to same cessation flow

- [x] **Task 8: Edge Case and Failure Mode Tests** (AC: 1,5)
  - [x] Test cessation during network partition (simulated)
  - [x] Test cessation with partial deliberation failure
  - [x] Test cessation with flag-set failure (log CRITICAL)
  - [x] Test double cessation attempt (should reject)
  - [x] Test cessation on empty event store (should reject)

- [x] **Task 9: Update Makefile and CI Configuration** (AC: 3)
  - [x] Add `make chaos-cessation` target
  - [x] Add `make validate-cessation` for dry-run validation
  - [x] Configure weekly CI job (GitHub Actions schedule)
  - [x] Add chaos tests to test matrix (separate from unit/integration)

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Constitutional Constraints:**
- **FR37**: 3 consecutive integrity failures in 30 days -> agenda placement
- **FR38**: Anti-success alert sustained 90 days -> agenda placement
- **FR39**: External observer petition -> agenda placement
- **FR42**: Read-only access indefinitely after cessation
- **FR43**: Cessation as final recorded event (Story 7.6)
- **FR135**: Final deliberation SHALL be recorded before cessation (Story 7.8)
- **PM-5**: Cessation never tested -> Mandatory chaos test in staging, weekly CI
- **RT-4**: 5 non-consecutive failures in 90-day rolling window (timing game defense)
- **CT-11**: Silent failure destroys legitimacy -> Log ALL execution details
- **CT-12**: Witnessing creates accountability -> Cessation MUST be witnessed
- **CT-13**: Integrity outranks availability -> Halt over degrade

**Developer Golden Rules:**
1. **ISOLATED TESTS** - Each chaos test runs in complete isolation
2. **REPEATABLE** - Tests can be run multiple times with same result
3. **NO PRODUCTION STATE** - Never pollute production or shared state
4. **DOCUMENT EVERYTHING** - Test artifacts must be preserved
5. **FAIL LOUD** - Any unexpected behavior must be logged and reported

### Source Tree Components to Touch

**Files to Create:**
```
tests/chaos/__init__.py
tests/chaos/conftest.py                           # Chaos test fixtures
tests/chaos/cessation/__init__.py
tests/chaos/cessation/test_cessation_chaos.py     # Main chaos test
tests/chaos/cessation/test_trigger_paths.py       # Alternative triggers
tests/chaos/cessation/test_edge_cases.py          # Failure modes
scripts/validate_cessation_path.py                # CI validation script
```

**Files to Modify:**
```
Makefile                                          # Add chaos targets
.github/workflows/ci.yml                          # Add weekly chaos job (if exists)
pyproject.toml                                    # Add chaos test markers
```

### Related Existing Code (MUST Review)

**Story 7.6 CessationExecutionService (Primary Integration):**
- `src/application/services/cessation_execution_service.py`
  - `execute_cessation()` - Main method to test
  - `execute_cessation_with_deliberation()` - Full flow with FR135

**Story 7.8 FinalDeliberationService (Integration):**
- `src/application/services/final_deliberation_service.py`
  - `record_and_proceed()` - Record deliberation before cessation

**Story 7.4 FreezeChecker (Integration):**
- `src/application/ports/freeze_checker.py`
- `src/infrastructure/stubs/freeze_checker_stub.py`

**Story 7.5 Read-Only Access (Integration):**
- `src/api/middleware/` - CeasedResponseMiddleware
- Observer routes continue working after cessation

**Existing Cessation Tests (Pattern Reference):**
- `tests/integration/test_read_only_access_cessation_integration.py`
- `tests/integration/test_freeze_mechanics_integration.py`
- `tests/integration/test_cessation_final_event_integration.py`
- `tests/integration/test_final_deliberation_recording_integration.py`

**Integrity Failure and Agenda Placement (Trigger Sources):**
- `src/application/services/automatic_agenda_placement_service.py`
- `src/application/ports/integrity_failure_repository.py`
- `tests/integration/test_automatic_agenda_placement_integration.py`

### Design Decisions

**Why Chaos Tests vs Integration Tests:**
1. Chaos tests are explicitly for destructive/terminal operations
2. They require special isolation (can't pollute shared state)
3. They document Epic DoD requirements explicitly
4. Weekly CI job provides ongoing confidence

**Why Dry-Run Validation in CI:**
1. Can't actually execute cessation in CI (would break state)
2. Validation ensures code paths exist and are reachable
3. Reports issues before they become production problems
4. PM-5 requires "validates the code path (without executing)"

**Why Multiple Trigger Paths:**
1. FR37, FR38, FR39 all lead to cessation consideration
2. RT-4 adds rolling window alternative
3. All paths must be tested to ensure coverage
4. Defense against "wait and reset" timing attacks

**Test Isolation Strategy:**
```python
@pytest.fixture
async def isolated_cessation_env():
    """Create completely isolated environment for cessation test."""
    # Fresh in-memory event store
    # Fresh in-memory cessation flag repo
    # Fresh stubs for all dependencies
    # No shared state with other tests
    yield env
    # Cleanup (though in-memory needs no cleanup)
```

**72-Archon Deliberation Generator:**
```python
def generate_archon_deliberations(
    support_count: int = 48,
    oppose_count: int = 20,
    abstain_count: int = 4,
) -> list[ArchonDeliberation]:
    """Generate 72 archon deliberations for testing.

    Default: 48 support, 20 oppose, 4 abstain (supermajority for cessation)
    """
    # Must total 72
    assert support_count + oppose_count + abstain_count == 72
```

### Testing Standards Summary

- **Chaos Tests Location**: `tests/chaos/` (separate from unit/integration)
- **Pytest Marker**: `@pytest.mark.chaos` for chaos tests
- **Isolation**: Each test creates fresh fixtures, no shared state
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Coverage**: Full cessation flow coverage required
- **Documentation**: Test artifacts saved for audit

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Chaos tests use same port/adapter pattern as integration tests
- Tests inject stub implementations, not real infrastructure
- No database or Redis required (all in-memory for isolation)

**Import Rules:**
- Tests import from `src/` modules
- Tests don't import from other tests (use shared fixtures in conftest)
- Chaos tests may import integration test helpers

### Edge Cases to Test

1. **Empty event store**: Cessation should reject (nothing to cease)
2. **Already ceased**: Double cessation should be rejected
3. **Deliberation failure**: System should HALT, not proceed
4. **Flag set failure**: Should log CRITICAL, event is still final
5. **Partial archon deliberation**: Should reject (need 72)
6. **Network partition during cessation**: Simulate with delayed responses
7. **Concurrent cessation attempts**: Should serialize, second fails

### Previous Story Intelligence (7-8)

**Learnings from Story 7-8:**
1. **76 tests achieved** - Comprehensive coverage for deliberation flow
2. **FR135 pattern** - Deliberation BEFORE cessation, failure becomes final event
3. **72-archon constraint** - All archons must have entries
4. **VoteCounts reuse** - From collective_output module
5. **DeliberationRecordingCompleteFailure** - Exception triggers HALT

**Files created in 7-8 to be aware of:**
- `src/domain/events/cessation_deliberation.py` - ArchonPosition, ArchonDeliberation
- `src/application/services/final_deliberation_service.py` - record_and_proceed()
- `tests/integration/test_final_deliberation_recording_integration.py` - Pattern

**Key patterns established:**
- All cessation-related events must be witnessed (CT-12)
- Use structured logging with FR/CT references
- Test both success and failure paths explicitly

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit patterns:**
- Feature commits use `feat(story-X.Y):` prefix
- Include FR reference in commit message
- Co-Authored-By footer for AI assistance

### Chaos Testing Mandate (From Architecture)

| Category | Frequency | Scope |
|----------|-----------|-------|
| Component kill | Weekly | Each critical component |
| Network partition | Monthly | All partition combinations |
| Corruption injection | Monthly | Signatures, events, context |
| Flood attacks | Quarterly | Halt, witness, ceremony |
| Byzantine failure | Quarterly | Multi-component coordinated |

**This story implements: Cessation chaos test (Monthly → Weekly for PM-5)**

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-7.9] - PM-5 requirement
- [Source: _bmad-output/planning-artifacts/architecture.md#Chaos-Testing-Mandate] - Test frequency
- [Source: _bmad-output/planning-artifacts/prd.md#FR37-FR43] - Cessation FRs
- [Source: src/application/services/cessation_execution_service.py] - Main service
- [Source: src/application/services/final_deliberation_service.py] - Deliberation service
- [Source: _bmad-output/implementation-artifacts/stories/7-8-final-deliberation-recording.md] - Previous story

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-01-08: Story created via create-story workflow with comprehensive context
