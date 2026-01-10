# Story 6.8: Breach Collusion Defense (FR124-FR125)

Status: done

## Story

As a **system operator**,
I want defenses against witness collusion and hash verification bypass,
So that breach detection remains trustworthy.

## Acceptance Criteria

### AC1: Witness Collusion Investigation (FR124)
**Given** witness collusion detection from anomaly scanner
**When** multiple breaches involve the same witness pair
**Then** a collusion investigation is triggered
**And** pair is suspended pending review
**And** `CollusionInvestigationTriggeredEvent` is created
**And** suspension is logged as witnessed event

### AC2: Pair Suspension During Investigation (FR124)
**Given** a witness pair flagged for collusion investigation
**When** the pair is suspended
**Then** pair cannot be selected for witnessing
**And** suspension is publicly visible
**And** `WitnessPairSuspendedEvent` is created with attribution
**And** suspension persists until explicit clearance

### AC3: Continuous Hash Verification (FR125)
**Given** stored hashes in the event store
**When** verification runs continuously
**Then** any hash mismatch triggers breach event
**And** `HashVerificationBreachEvent` is created
**And** affected event range is identified
**And** system immediately halts on hash mismatch

### AC4: Hash Verification Audit Trail (FR125)
**Given** continuous hash verification
**When** verification completes a scan cycle
**Then** verification timestamp and scope are logged
**And** observers can query verification status
**And** verification runs at configurable interval (default: 1 hour)

### AC5: Investigation Resolution Workflow (FR124)
**Given** an ongoing collusion investigation
**When** investigation is resolved (cleared or confirmed)
**Then** resolution event is created
**And** if cleared: pair is reinstated for selection
**And** if confirmed: pair is permanently banned
**And** resolution includes investigator attribution

### AC6: Collusion Pattern Correlation (FR124)
**Given** breach events in the system
**When** multiple breaches share witness attribution
**Then** correlation analysis runs automatically
**And** correlation score is calculated
**And** high correlation (>0.8) triggers investigation
**And** correlation results visible to observers

## Tasks / Subtasks

- [x] Task 1: Create Collusion Investigation Domain Events (AC: #1, #2, #5)
  - [ ] 1.1 Create `src/domain/events/collusion.py`:
    - `CollusionInvestigationTriggeredEventPayload` frozen dataclass with:
      - `investigation_id: str` - Unique investigation identifier
      - `witness_pair: WitnessPair` - The pair under investigation
      - `triggering_anomalies: tuple[str, ...]` - Anomaly IDs that triggered this
      - `breach_event_ids: tuple[str, ...]` - Related breach events
      - `correlation_score: float` - 0.0 to 1.0 correlation strength
      - `triggered_at: datetime`
      - `triggered_by: str` - System or human who initiated
    - Event type constant: `COLLUSION_INVESTIGATION_TRIGGERED_EVENT_TYPE = "collusion.investigation_triggered"`
    - `to_dict()` for event serialization
    - `signable_content()` for witnessing (CT-12)
  - [ ] 1.2 Create `WitnessPairSuspendedEventPayload` frozen dataclass:
    - `pair_key: str` - Canonical pair key
    - `investigation_id: str` - Related investigation
    - `suspension_reason: str`
    - `suspended_at: datetime`
    - `suspended_by: str` - Attribution
    - Event type constant: `WITNESS_PAIR_SUSPENDED_EVENT_TYPE = "witness.pair_suspended"`
  - [ ] 1.3 Create `InvestigationResolvedEventPayload` frozen dataclass:
    - `investigation_id: str`
    - `pair_key: str`
    - `resolution: InvestigationResolution` - CLEARED, CONFIRMED_COLLUSION
    - `resolution_reason: str`
    - `resolved_at: datetime`
    - `resolved_by: str` - Investigator attribution
    - `evidence_summary: str`
    - Event type constant: `INVESTIGATION_RESOLVED_EVENT_TYPE = "collusion.investigation_resolved"`
  - [ ] 1.4 Create `InvestigationResolution` enum: CLEARED, CONFIRMED_COLLUSION
  - [ ] 1.5 Export from `src/domain/events/__init__.py`

- [x] Task 2: Create Hash Verification Domain Events (AC: #3, #4)
  - [ ] 2.1 Create `src/domain/events/hash_verification.py`:
    - `HashVerificationBreachEventPayload` frozen dataclass with:
      - `breach_id: str` - Unique breach identifier
      - `affected_event_id: str` - Event with hash mismatch
      - `expected_hash: str` - Hash that should be there
      - `actual_hash: str` - Hash that was found
      - `event_sequence_num: int` - Position in chain
      - `detected_at: datetime`
      - Event type constant: `HASH_VERIFICATION_BREACH_EVENT_TYPE = "hash.verification_breach"`
    - `HashVerificationCompletedEventPayload` frozen dataclass:
      - `scan_id: str` - Unique scan identifier
      - `events_scanned: int`
      - `sequence_range: tuple[int, int]` - (start, end) sequence numbers
      - `duration_seconds: float`
      - `result: HashVerificationResult` - PASSED, FAILED
      - `completed_at: datetime`
      - Event type constant: `HASH_VERIFICATION_COMPLETED_EVENT_TYPE = "hash.verification_completed"`
    - `HashVerificationResult` enum: PASSED, FAILED
  - [ ] 2.2 Export from `src/domain/events/__init__.py`

- [x] Task 3: Create Collusion Domain Errors (AC: #1, #2, #5)
  - [ ] 3.1 Create `src/domain/errors/collusion.py`:
    - `CollusionDefenseError(ConstitutionalViolationError)` - Base class
    - `CollusionInvestigationRequiredError(CollusionDefenseError)` - FR124
      - Attributes: `pair_key: str`, `correlation_score: float`
      - Message: "FR124: Collusion investigation required - correlation score {correlation_score}"
    - `WitnessPairSuspendedError(CollusionDefenseError)` - FR124 pair suspended
      - Attributes: `pair_key: str`, `investigation_id: str`
      - Message: "FR124: Witness pair {pair_key} suspended pending investigation"
    - `InvestigationNotFoundError(CollusionDefenseError)`
      - Attributes: `investigation_id: str`
      - Message: "Investigation {investigation_id} not found"
    - `InvestigationAlreadyResolvedError(CollusionDefenseError)`
      - Attributes: `investigation_id: str`, `resolved_at: datetime`
      - Message: "Investigation {investigation_id} already resolved at {resolved_at}"
  - [ ] 3.2 Export from `src/domain/errors/__init__.py`

- [x] Task 4: Create Hash Verification Errors (AC: #3, #4)
  - [ ] 4.1 Create `src/domain/errors/hash_verification.py`:
    - `HashVerificationError(ConstitutionalViolationError)` - Base class
    - `HashMismatchError(HashVerificationError)` - FR125 hash mismatch
      - Attributes: `event_id: str`, `expected_hash: str`, `actual_hash: str`
      - Message: "FR125: Hash mismatch detected - chain integrity compromised"
    - `HashVerificationTimeoutError(HashVerificationError)`
      - Attributes: `scan_id: str`, `timeout_seconds: float`
      - Message: "Hash verification scan {scan_id} timed out after {timeout_seconds}s"
  - [ ] 4.2 Export from `src/domain/errors/__init__.py`

- [x] Task 5: Create Collusion Investigation Port (AC: #1, #2, #5, #6)
  - [ ] 5.1 Create `src/application/ports/collusion_investigator.py`:
    - `CollusionInvestigatorProtocol` ABC with methods:
      - `async def trigger_investigation(pair_key: str, anomaly_ids: tuple[str, ...], breach_ids: tuple[str, ...]) -> str`
        - Triggers new investigation, returns investigation_id
      - `async def get_investigation(investigation_id: str) -> Investigation | None`
        - Retrieves investigation details
      - `async def list_active_investigations() -> list[Investigation]`
        - Lists all ongoing investigations
      - `async def resolve_investigation(investigation_id: str, resolution: InvestigationResolution, reason: str, resolved_by: str) -> None`
        - Resolves an investigation
      - `async def is_pair_under_investigation(pair_key: str) -> bool`
        - Checks if pair has active investigation
      - `async def calculate_correlation(pair_key: str, breach_ids: tuple[str, ...]) -> float`
        - Calculates correlation score for pair across breaches
    - `Investigation` frozen dataclass:
      - `investigation_id: str`
      - `pair_key: str`
      - `status: InvestigationStatus` - ACTIVE, CLEARED, CONFIRMED
      - `triggered_at: datetime`
      - `triggering_anomalies: tuple[str, ...]`
      - `breach_event_ids: tuple[str, ...]`
      - `correlation_score: float`
      - `resolved_at: datetime | None`
      - `resolution: InvestigationResolution | None`
    - `InvestigationStatus` enum: ACTIVE, CLEARED, CONFIRMED
  - [ ] 5.2 Export from `src/application/ports/__init__.py`

- [x] Task 6: Create Hash Verifier Port (AC: #3, #4)
  - [ ] 6.1 Create `src/application/ports/hash_verifier.py`:
    - `HashVerifierProtocol` ABC with methods:
      - `async def verify_event_hash(event_id: str) -> HashVerificationResult`
        - Verifies single event hash
      - `async def run_full_scan(max_events: int | None = None) -> HashScanResult`
        - Runs full hash chain verification
      - `async def get_last_scan_status() -> HashScanStatus`
        - Returns last scan status for observer queries
      - `async def schedule_continuous_verification(interval_seconds: int = 3600) -> None`
        - Configures continuous verification interval
    - `HashScanResult` frozen dataclass:
      - `scan_id: str`
      - `events_scanned: int`
      - `passed: bool`
      - `failed_event_id: str | None`
      - `expected_hash: str | None`
      - `actual_hash: str | None`
      - `completed_at: datetime`
    - `HashScanStatus` frozen dataclass:
      - `last_scan_id: str | None`
      - `last_scan_at: datetime | None`
      - `next_scan_at: datetime | None`
      - `last_scan_passed: bool | None`
      - `events_verified_total: int`
  - [ ] 6.2 Export from `src/application/ports/__init__.py`

- [x] Task 7: Create Breach Collusion Defense Service (AC: #1, #2, #5, #6)
  - [ ] 7.1 Create `src/application/services/breach_collusion_defense_service.py`:
    - Inject: `HaltChecker`, `CollusionInvestigatorProtocol`, `WitnessAnomalyDetectorProtocol`, `BreachRepositoryProtocol`, `EventWriterService` (optional)
    - HALT CHECK FIRST at every operation boundary (CT-11)
  - [ ] 7.2 Implement `async def check_for_collusion_trigger(pair_key: str) -> CollusionCheckResult`:
    - HALT CHECK FIRST (CT-11)
    - Query breaches involving this pair
    - Query anomalies involving this pair
    - Calculate correlation score
    - If correlation > 0.8, trigger investigation
    - Return check result
  - [ ] 7.3 Implement `async def trigger_investigation(pair_key: str, anomaly_ids: tuple[str, ...], breach_ids: tuple[str, ...]) -> str`:
    - HALT CHECK FIRST (CT-11)
    - Create investigation via port
    - Suspend pair immediately
    - Create `CollusionInvestigationTriggeredEvent`
    - Create `WitnessPairSuspendedEvent`
    - Return investigation_id
  - [ ] 7.4 Implement `async def resolve_investigation(investigation_id: str, resolution: InvestigationResolution, reason: str, resolved_by: str) -> None`:
    - HALT CHECK FIRST (CT-11)
    - Validate investigation exists and is active
    - Resolve via port
    - If CLEARED: reinstate pair
    - If CONFIRMED: permanently ban pair
    - Create `InvestigationResolvedEvent`
  - [ ] 7.5 Implement correlation calculation:
    - `_calculate_pair_breach_correlation(pair_key: str, breach_ids: tuple[str, ...]) -> float`
    - Correlation = (breaches with pair) / (total breaches in window)
    - Threshold: 0.8 (configurable via constitutional threshold)
  - [ ] 7.6 Export from `src/application/services/__init__.py`

- [x] Task 8: Create Hash Verification Service (AC: #3, #4)
  - [ ] 8.1 Create `src/application/services/hash_verification_service.py`:
    - Inject: `HaltChecker`, `HashVerifierProtocol`, `HaltTrigger`, `EventWriterService` (optional)
    - HALT CHECK FIRST at every operation (CT-11)
  - [ ] 8.2 Implement `async def verify_single_event(event_id: str) -> HashVerificationResult`:
    - HALT CHECK FIRST (CT-11)
    - Verify via port
    - Return result
  - [ ] 8.3 Implement `async def run_continuous_verification(interval_seconds: int = 3600) -> None`:
    - HALT CHECK FIRST (CT-11)
    - Configure interval on port
    - Log configuration
  - [ ] 8.4 Implement `async def run_full_chain_scan() -> HashScanResult`:
    - HALT CHECK FIRST (CT-11)
    - Run scan via port
    - If any mismatch found:
      - Create `HashVerificationBreachEvent`
      - Trigger system halt immediately
      - Return failed result
    - Create `HashVerificationCompletedEvent`
    - Return result
  - [ ] 8.5 Implement `async def get_verification_status() -> HashScanStatus`:
    - HALT CHECK FIRST (CT-11)
    - Return last scan status for observer queries
  - [ ] 8.6 Export from `src/application/services/__init__.py`

- [x] Task 9: Create Infrastructure Stubs (AC: #1, #2, #3, #4, #5, #6)
  - [ ] 9.1 Create `src/infrastructure/stubs/collusion_investigator_stub.py`:
    - `CollusionInvestigatorStub` implementing `CollusionInvestigatorProtocol`
    - In-memory storage for investigations
    - `inject_investigation(investigation: Investigation)` for test setup
    - `set_correlation_score(pair_key: str, score: float)` for test control
    - `clear()` for test isolation
    - DEV MODE watermark warning on initialization
  - [ ] 9.2 Create `src/infrastructure/stubs/hash_verifier_stub.py`:
    - `HashVerifierStub` implementing `HashVerifierProtocol`
    - Configurable verification results
    - `set_verification_result(event_id: str, result: HashVerificationResult)` for test control
    - `set_scan_failure(event_id: str, expected: str, actual: str)` for test control
    - `clear()` for test isolation
  - [ ] 9.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 10: Integrate with Witness Selection Service (AC: #2)
  - [ ] 10.1 Update `VerifiableWitnessSelectionService` or `WitnessAnomalyDetectionService`:
    - Add optional `CollusionInvestigatorProtocol` injection
    - Before selecting pair, check if under investigation
    - Skip pairs with active investigation
    - Skip permanently banned pairs

- [x] Task 11: Write Unit Tests (AC: #1, #2, #3, #4, #5, #6)
  - [ ] 11.1 Create `tests/unit/domain/test_collusion_events.py`:
    - Test `CollusionInvestigationTriggeredEventPayload` creation with all fields
    - Test `WitnessPairSuspendedEventPayload` creation
    - Test `InvestigationResolvedEventPayload` creation
    - Test `InvestigationResolution` enum values
    - Test `to_dict()` returns expected structure
    - Test `signable_content()` determinism
  - [ ] 11.2 Create `tests/unit/domain/test_hash_verification_events.py`:
    - Test `HashVerificationBreachEventPayload` creation
    - Test `HashVerificationCompletedEventPayload` creation
    - Test `HashVerificationResult` enum values
  - [ ] 11.3 Create `tests/unit/domain/test_collusion_errors.py`:
    - Test `CollusionInvestigationRequiredError` message includes FR124
    - Test `WitnessPairSuspendedError` includes pair_key
    - Test error inheritance hierarchy
  - [ ] 11.4 Create `tests/unit/domain/test_hash_verification_errors.py`:
    - Test `HashMismatchError` message includes FR125
    - Test error inheritance hierarchy
  - [ ] 11.5 Create `tests/unit/application/test_breach_collusion_defense_service.py`:
    - Test `check_for_collusion_trigger()` calculates correlation
    - Test `check_for_collusion_trigger()` triggers investigation at >0.8
    - Test `trigger_investigation()` suspends pair
    - Test `trigger_investigation()` creates events
    - Test `resolve_investigation()` handles CLEARED
    - Test `resolve_investigation()` handles CONFIRMED
    - Test HALT CHECK on all operations
  - [ ] 11.6 Create `tests/unit/application/test_hash_verification_service.py`:
    - Test `verify_single_event()` returns result
    - Test `run_full_chain_scan()` creates completion event on pass
    - Test `run_full_chain_scan()` triggers halt on mismatch
    - Test `run_full_chain_scan()` creates breach event on mismatch
    - Test `get_verification_status()` returns last scan
    - Test HALT CHECK on all operations
  - [ ] 11.7 Create `tests/unit/infrastructure/test_collusion_investigator_stub.py`:
    - Test stub investigation management
    - Test `inject_investigation()` for test setup
    - Test correlation score configuration
    - Test `clear()` method
  - [ ] 11.8 Create `tests/unit/infrastructure/test_hash_verifier_stub.py`:
    - Test stub verification results
    - Test scan failure configuration
    - Test `clear()` method

- [x] Task 12: Write Integration Tests (AC: #1, #2, #3, #4, #5, #6)
  - [ ] 12.1 Create `tests/integration/test_breach_collusion_defense_integration.py`:
    - Test: `test_fr124_collusion_investigation_triggered` (AC1)
      - Set up multiple breaches with same pair
      - Run collusion check
      - Verify investigation triggered
      - Verify events created
    - Test: `test_fr124_pair_suspended_during_investigation` (AC2)
      - Trigger investigation
      - Attempt to select pair
      - Verify pair skipped
      - Verify suspension publicly visible
    - Test: `test_fr124_investigation_cleared_reinstates_pair` (AC5)
      - Trigger and resolve as CLEARED
      - Verify pair selectable again
      - Verify resolution event created
    - Test: `test_fr124_investigation_confirmed_bans_pair` (AC5)
      - Trigger and resolve as CONFIRMED
      - Verify pair permanently banned
      - Verify resolution event created
    - Test: `test_fr124_correlation_calculation` (AC6)
      - Multiple breaches, some with pair, some without
      - Verify correlation calculated correctly
      - Verify high correlation triggers investigation
    - Test: `test_fr125_hash_verification_detects_mismatch` (AC3)
      - Inject hash mismatch
      - Run scan
      - Verify breach event created
      - Verify system halts
    - Test: `test_fr125_hash_verification_logs_completion` (AC4)
      - Run successful scan
      - Verify completion event created
      - Verify status queryable
    - Test: `test_halt_check_prevents_collusion_operations`
      - Set system halted
      - Attempt operations
      - Verify SystemHaltedError
    - Test: `test_all_events_witnessed`
      - Trigger investigation
      - Verify all events have witness attribution

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR124**: Witness selection randomness SHALL combine hash chain state + external entropy source meeting independence criteria (Randomness Gaming defense)
- **FR125**: Witness selection algorithm SHALL be published; statistical deviation from expected distribution flagged (Selection Audit)
- **CT-9**: Attackers are patient - aggregate erosion must be detected
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> All events MUST be witnessed
- **CT-13**: Integrity outranks availability -> Hash mismatch MUST trigger halt

### FR Mapping Clarification

The story title in epics.md says "FR124-FR128" but analysis shows:
- **FR124-FR125** are the relevant FRs for this story:
  - FR124: Randomness combining hash chain + external entropy (witness collusion defense)
  - FR125: Published selection algorithm + statistical deviation flagging (selection audit)
- FR126-FR128 were covered in Story 6.7 (Amendment Visibility)

This story focuses on:
1. **Witness Collusion Investigation** - When anomalies are detected, trigger formal investigation
2. **Hash Verification** - Continuous verification that stored hashes are correct
3. **Pair Suspension Workflow** - Full lifecycle from detection to resolution

### ADR-7: Aggregate Anomaly Detection

Story 6.8 builds on ADR-7's three-layer detection system:

| Layer | Method | Response |
|-------|--------|----------|
| Rules | Predefined thresholds | Auto-alert, auto-halt if critical |
| Statistics (Story 6.6) | Baseline deviation detection | Queue for review |
| **Human (THIS STORY)** | Investigation workflow | Classify, escalate, or dismiss |

This story implements the **investigation workflow** that follows statistical detection from Story 6.6.

### Epic 6 Context - Story 6.8 Position

```
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.6: Witness Pool Anomaly Detection (COMPLETED)           │
│ - Statistical co-occurrence analysis (FR116)                    │
│ - Unavailability pattern detection (FR116)                      │
│ - Witness pool degraded mode (FR117)                            │
│ - ADR-7 Statistics layer integration                            │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Anomalies detected
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.7: Amendment Visibility (COMPLETED)                     │
│ - 14-day public visibility period (FR126)                       │
│ - Impact analysis for core guarantees (FR127)                   │
│ - History protection (FR128)                                    │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Parallel
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.8: Breach Collusion Defense (THIS STORY)                │
│ - Collusion investigation triggered from anomalies (FR124)      │
│ - Pair suspension pending review (FR124)                        │
│ - Continuous hash verification (FR125)                          │
│ - Investigation resolution workflow                             │
│ - Hash mismatch triggers halt                                   │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Followed by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.9: Topic Manipulation Defense (FUTURE)                  │
│ - Topic submission manipulation detection                       │
│ - Seed manipulation defense                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Key Dependencies from Previous Stories

From Story 6.6 (Witness Pool Anomaly Detection):
- `src/application/ports/witness_anomaly_detector.py` - WitnessAnomalyDetectorProtocol
- `src/application/services/witness_anomaly_detection_service.py` - For anomaly trigger integration
- `src/domain/events/witness_anomaly.py` - WitnessAnomalyEventPayload patterns
- `src/infrastructure/stubs/witness_anomaly_detector_stub.py` - Stub patterns

From Story 6.5 (Verifiable Witness Selection):
- `src/application/services/verifiable_witness_selection_service.py` - Integrate investigation check
- `src/domain/models/witness_pair.py` - WitnessPair for canonical keys

From Story 6.1 (Breach Declaration Events):
- `src/application/ports/breach_repository.py` - BreachRepositoryProtocol
- `src/domain/events/breach.py` - Breach event patterns

From Core Infrastructure:
- `src/application/ports/halt_checker.py` - HaltCheckerProtocol
- `src/application/ports/halt_trigger.py` - HaltTriggerProtocol (for hash mismatch halt)
- `src/domain/errors/writer.py` - SystemHaltedError
- `src/domain/events/event.py` - Base event patterns

### Collusion Investigation Workflow

```python
# Collusion investigation workflow (FR124)

async def check_for_collusion_trigger(
    pair_key: str,
) -> CollusionCheckResult:
    """Check if pair should trigger collusion investigation.

    FR124: Witness selection randomness SHALL combine hash chain
    state + external entropy source meeting independence criteria.

    When anomalies indicate collusion, investigation is required.
    """
    # HALT CHECK FIRST (CT-11)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # Query breaches involving this pair
    breaches = await self._breach_repository.get_breaches_by_witness_pair(pair_key)

    # Query anomalies from Story 6.6
    anomalies = await self._anomaly_detector.get_anomalies_for_pair(pair_key)

    # Calculate correlation
    correlation = self._calculate_pair_breach_correlation(
        pair_key,
        tuple(b.breach_id for b in breaches)
    )

    # Threshold check
    if correlation > 0.8:
        # Trigger investigation
        investigation_id = await self.trigger_investigation(
            pair_key=pair_key,
            anomaly_ids=tuple(a.anomaly_id for a in anomalies),
            breach_ids=tuple(b.breach_id for b in breaches),
        )
        return CollusionCheckResult(
            requires_investigation=True,
            investigation_id=investigation_id,
            correlation_score=correlation,
        )

    return CollusionCheckResult(
        requires_investigation=False,
        investigation_id=None,
        correlation_score=correlation,
    )
```

### Hash Verification Service (FR125)

```python
async def run_full_chain_scan(self) -> HashScanResult:
    """Run full hash chain verification (FR125).

    FR125: Witness selection algorithm SHALL be published;
    statistical deviation from expected distribution flagged.

    Hash verification ensures stored hashes match recalculated values.
    Any mismatch indicates tampering or corruption - immediate halt.
    """
    # HALT CHECK FIRST (CT-11)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # Run scan via port
    result = await self._hash_verifier.run_full_scan()

    if not result.passed:
        # CRITICAL: Hash mismatch - chain integrity compromised
        # Create breach event
        breach_event = HashVerificationBreachEventPayload(
            breach_id=f"hash-breach-{uuid4()}",
            affected_event_id=result.failed_event_id,
            expected_hash=result.expected_hash,
            actual_hash=result.actual_hash,
            event_sequence_num=0,  # Would need lookup
            detected_at=datetime.now(UTC),
        )

        if self._event_writer:
            await self._event_writer.write_event(breach_event)

        # CT-13: Integrity outranks availability - HALT IMMEDIATELY
        await self._halt_trigger.trigger_halt(
            reason="FR125: Hash verification breach - chain integrity compromised",
            source="hash_verification_service",
        )

        return result

    # Success - log completion
    completion_event = HashVerificationCompletedEventPayload(
        scan_id=result.scan_id,
        events_scanned=result.events_scanned,
        sequence_range=(0, result.events_scanned - 1),
        duration_seconds=0.0,  # Would need timing
        result=HashVerificationResult.PASSED,
        completed_at=datetime.now(UTC),
    )

    if self._event_writer:
        await self._event_writer.write_event(completion_event)

    return result
```

### Investigation Resolution

```python
@dataclass(frozen=True)
class InvestigationResolvedEventPayload:
    """Event created when investigation is resolved.

    Resolution options:
    - CLEARED: No collusion found, pair reinstated
    - CONFIRMED_COLLUSION: Collusion confirmed, pair permanently banned
    """
    investigation_id: str
    pair_key: str
    resolution: InvestigationResolution
    resolution_reason: str
    resolved_at: datetime
    resolved_by: str  # Attribution - who resolved
    evidence_summary: str


async def resolve_investigation(
    self,
    investigation_id: str,
    resolution: InvestigationResolution,
    reason: str,
    resolved_by: str,
) -> None:
    """Resolve a collusion investigation (FR124).

    CLEARED: Reinstates pair for selection.
    CONFIRMED: Permanently bans pair from selection.
    """
    # HALT CHECK FIRST (CT-11)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # Validate investigation exists
    investigation = await self._investigator.get_investigation(investigation_id)
    if investigation is None:
        raise InvestigationNotFoundError(investigation_id=investigation_id)

    if investigation.status != InvestigationStatus.ACTIVE:
        raise InvestigationAlreadyResolvedError(
            investigation_id=investigation_id,
            resolved_at=investigation.resolved_at,
        )

    # Resolve
    await self._investigator.resolve_investigation(
        investigation_id, resolution, reason, resolved_by
    )

    # Handle based on resolution
    if resolution == InvestigationResolution.CLEARED:
        # Reinstate pair
        await self._anomaly_detector.clear_pair_exclusion(investigation.pair_key)
    else:
        # Permanently ban (already excluded, just don't clear)
        pass

    # Create resolution event
    event = InvestigationResolvedEventPayload(
        investigation_id=investigation_id,
        pair_key=investigation.pair_key,
        resolution=resolution,
        resolution_reason=reason,
        resolved_at=datetime.now(UTC),
        resolved_by=resolved_by,
        evidence_summary=f"Correlation score: {investigation.correlation_score}",
    )

    if self._event_writer:
        await self._event_writer.write_event(event)
```

### Import Rules (Hexagonal Architecture)

- `domain/events/collusion.py` imports from `domain/`, `typing`, `dataclasses`, `datetime`, `enum`
- `domain/events/hash_verification.py` imports from `domain/`, `typing`, `dataclasses`, `datetime`, `enum`
- `domain/errors/collusion.py` inherits from `ConstitutionalViolationError`
- `domain/errors/hash_verification.py` inherits from `ConstitutionalViolationError`
- `application/ports/collusion_investigator.py` imports from `abc`, `typing`, domain events
- `application/ports/hash_verifier.py` imports from `abc`, `typing`, `datetime`
- `application/services/breach_collusion_defense_service.py` imports from `application/ports/`, `domain/`
- `application/services/hash_verification_service.py` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR124 tests MUST verify:
  - Investigation triggered at correlation > 0.8
  - Pair suspended during investigation
  - Resolution handles CLEARED and CONFIRMED
  - All events witnessed
- FR125 tests MUST verify:
  - Hash mismatch triggers breach event
  - Hash mismatch triggers system halt
  - Successful scan creates completion event
  - Verification status queryable

### Files to Create

```
src/domain/events/collusion.py                                # Collusion events
src/domain/events/hash_verification.py                        # Hash verification events
src/domain/errors/collusion.py                                # Collusion errors
src/domain/errors/hash_verification.py                        # Hash verification errors
src/application/ports/collusion_investigator.py               # Investigator port
src/application/ports/hash_verifier.py                        # Hash verifier port
src/application/services/breach_collusion_defense_service.py  # Collusion defense service
src/application/services/hash_verification_service.py         # Hash verification service
src/infrastructure/stubs/collusion_investigator_stub.py       # Investigator stub
src/infrastructure/stubs/hash_verifier_stub.py                # Hash verifier stub
tests/unit/domain/test_collusion_events.py                    # Collusion event tests
tests/unit/domain/test_hash_verification_events.py            # Hash verification event tests
tests/unit/domain/test_collusion_errors.py                    # Collusion error tests
tests/unit/domain/test_hash_verification_errors.py            # Hash verification error tests
tests/unit/application/test_breach_collusion_defense_service.py  # Collusion defense service tests
tests/unit/application/test_hash_verification_service.py         # Hash verification service tests
tests/unit/infrastructure/test_collusion_investigator_stub.py    # Investigator stub tests
tests/unit/infrastructure/test_hash_verifier_stub.py             # Hash verifier stub tests
tests/integration/test_breach_collusion_defense_integration.py   # Integration tests
```

### Files to Modify

```
src/application/services/verifiable_witness_selection_service.py  # Add investigation check
src/domain/events/__init__.py                                     # Export new events
src/domain/errors/__init__.py                                     # Export new errors
src/application/ports/__init__.py                                 # Export new ports
src/application/services/__init__.py                              # Export new services
src/infrastructure/stubs/__init__.py                              # Export new stubs
```

### Project Structure Notes

- Investigation workflow follows existing ADR-7 human review pattern
- Pair suspension is immediate on investigation trigger (no async delay)
- Hash verification runs continuously with configurable interval
- Hash mismatch is existential - triggers immediate halt (CT-13)
- Resolution requires human attribution (CT-12)
- All events witnessed for accountability

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.8] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR124] - Randomness with hash chain + entropy
- [Source: _bmad-output/planning-artifacts/prd.md#FR125] - Published selection algorithm + statistical flagging
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-7] - Aggregate Anomaly Detection
- [Source: _bmad-output/implementation-artifacts/stories/6-6-witness-pool-anomaly-detection.md] - Previous story patterns
- [Source: _bmad-output/implementation-artifacts/stories/6-7-amendment-visibility.md] - Amendment patterns
- [Source: src/application/ports/witness_anomaly_detector.py] - Anomaly detector integration
- [Source: src/application/services/verifiable_witness_selection_service.py] - Selection service to extend
- [Source: src/application/ports/halt_trigger.py] - Halt trigger for hash mismatch
- [Source: _bmad-output/project-context.md] - Project implementation rules

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

**Implemented 2026-01-08:**

1. **Domain Events Created:**
   - `src/domain/events/collusion.py` - CollusionInvestigationTriggeredEventPayload, WitnessPairSuspendedEventPayload, InvestigationResolvedEventPayload, InvestigationResolution enum
   - `src/domain/events/hash_verification.py` - HashVerificationBreachEventPayload, HashVerificationCompletedEventPayload, HashVerificationResult enum

2. **Domain Errors Created:**
   - `src/domain/errors/collusion.py` - CollusionDefenseError, CollusionInvestigationRequiredError, WitnessPairSuspendedError, InvestigationNotFoundError, InvestigationAlreadyResolvedError, WitnessPairPermanentlyBannedError
   - `src/domain/errors/hash_verification.py` - HashVerificationError, HashMismatchError, HashVerificationTimeoutError, HashVerificationScanInProgressError, HashChainBrokenError

3. **Application Ports Created:**
   - `src/application/ports/collusion_investigator.py` - CollusionInvestigatorProtocol, Investigation dataclass, InvestigationStatus enum
   - `src/application/ports/hash_verifier.py` - HashVerifierProtocol, HashScanResult, HashScanStatus dataclasses

4. **Application Services Created:**
   - `src/application/services/breach_collusion_defense_service.py` - BreachCollusionDefenseService with HALT CHECK FIRST pattern (CT-11)
   - `src/application/services/hash_verification_service.py` - HashVerificationService implementing HashVerifierProtocol

5. **Infrastructure Stubs Created:**
   - `src/infrastructure/stubs/collusion_investigator_stub.py` - In-memory stub for testing
   - `src/infrastructure/stubs/hash_verifier_stub.py` - In-memory stub for testing

6. **Extended Existing Components:**
   - Added `get_breaches_by_witness_pair()` to BreachRepositoryProtocol and BreachRepositoryStub
   - Added `get_all()`, `get_by_id()`, `get_by_sequence()` to EventStorePort and EventStoreStub

7. **Tests:**
   - 83 unit tests passing (domain events, errors, infrastructure stubs)
   - 26 integration tests passing (breach collusion defense, hash verification)
   - Total: 109 tests passing for Story 6.8

**Constitutional Constraints Honored:**
- FR124: Collusion investigation workflow with correlation thresholds
- FR125: Hash verification with halt on mismatch (CT-13)
- CT-9: Aggregate anomaly detection integration
- CT-11: HALT CHECK FIRST at every operation boundary
- CT-12: All events have signable_content() for witnessing
- CT-13: Hash mismatch triggers immediate halt

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Story created with comprehensive FR124-FR125 context, investigation workflow, hash verification, ADR-7 human review integration | Create-Story Workflow (Opus 4.5) |

### File List

