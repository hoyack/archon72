# Story 5.9: Override Abuse Detection (FR86-FR87, FP-3)

Status: done

## Story

As a **system operator**,
I want override commands validated against constitutional constraints,
So that abusive overrides are rejected and logged.

## Acceptance Criteria

### AC1: Constitutional Constraint Validation (FR86)
**Given** an override command
**When** it violates a constitutional constraint
**Then** it is rejected
**And** an `OverrideAbuseRejectedEvent` is created with details

### AC2: Statistical Anomaly Detection (FP-3)
**Given** override pattern analysis (FP-3)
**When** statistical anomalies are detected across Keeper behavior
**Then** `AnomalyDetectedEvent` is created
**And** anomaly details are included

### AC3: Long-Term Pattern Analysis (ADR-7)
**Given** ADR-7 Aggregate Anomaly Detection
**When** long-term patterns are analyzed
**Then** slow-burn attacks are detected
**And** coordinated override patterns trigger alerts

## Tasks / Subtasks

- [x] Task 1: Create Override Abuse Domain Events (AC: #1)
  - [x] 1.1 Create `src/domain/events/override_abuse.py`:
    - `OverrideAbuseRejectedPayload` dataclass with: `keeper_id`, `scope`, `violation_type`, `violation_details`, `rejected_at`
    - Event type constant: `OVERRIDE_ABUSE_REJECTED_EVENT_TYPE = "override.abuse_rejected"`
    - `signable_content()` method for witnessing (CT-12)
  - [x] 1.2 Create `AnomalyDetectedPayload` dataclass with: `anomaly_type`, `keeper_ids`, `detection_method`, `confidence_score`, `time_window_days`, `details`, `detected_at`
    - Event type constant: `ANOMALY_DETECTED_EVENT_TYPE = "override.anomaly_detected"`
    - `signable_content()` method for witnessing (CT-12)
  - [x] 1.3 Define `ViolationType` enum: `WITNESS_SUPPRESSION`, `HISTORY_EDIT`, `EVIDENCE_DESTRUCTION`, `FORBIDDEN_SCOPE`, `CONSTITUTIONAL_CONSTRAINT`
  - [x] 1.4 Define `AnomalyType` enum: `COORDINATED_OVERRIDES`, `FREQUENCY_SPIKE`, `PATTERN_CORRELATION`, `SLOW_BURN_EROSION`
  - [x] 1.5 Export from `src/domain/events/__init__.py`

- [x] Task 2: Create Override Abuse Domain Errors (AC: #1)
  - [x] 2.1 Create `src/domain/errors/override_abuse.py`:
    - `OverrideAbuseError(ConstitutionalViolationError)` - base for abuse errors
    - `HistoryEditAttemptError(OverrideAbuseError)` - FR87: override attempts history edit
    - `EvidenceDestructionAttemptError(OverrideAbuseError)` - FR87: override attempts evidence destruction
    - `ConstitutionalConstraintViolationError(OverrideAbuseError)` - FR86: general constitutional violation
  - [x] 2.2 Export from `src/domain/errors/__init__.py`

- [x] Task 3: Create Override Abuse Validator Port (AC: #1)
  - [x] 3.1 Create `src/application/ports/override_abuse_validator.py`:
    - `OverrideAbuseValidatorProtocol` with methods:
      - `async def validate_constitutional_constraints(override_scope: str, action_type: str) -> ValidationResult`
      - `async def is_history_edit_attempt(override_scope: str) -> bool`
      - `async def is_evidence_destruction_attempt(override_scope: str) -> bool`
  - [x] 3.2 Create `ValidationResult` dataclass with: `is_valid`, `violation_type`, `violation_details`
  - [x] 3.3 Export from `src/application/ports/__init__.py`

- [x] Task 4: Create Anomaly Detector Port (AC: #2, #3)
  - [x] 4.1 Create `src/application/ports/anomaly_detector.py`:
    - `AnomalyDetectorProtocol` with methods:
      - `async def detect_keeper_anomalies(time_window_days: int) -> list[AnomalyResult]`
      - `async def detect_coordinated_patterns(keeper_ids: list[str], time_window_days: int) -> list[AnomalyResult]`
      - `async def get_keeper_override_frequency(keeper_id: str, time_window_days: int) -> FrequencyData`
      - `async def detect_slow_burn_erosion(time_window_days: int, threshold: float) -> list[AnomalyResult]`
  - [x] 4.2 Create `AnomalyResult` dataclass with: `anomaly_type`, `confidence_score`, `affected_keepers`, `details`
  - [x] 4.3 Create `FrequencyData` dataclass with: `override_count`, `time_window_days`, `daily_rate`, `deviation_from_baseline`
  - [x] 4.4 Export from `src/application/ports/__init__.py`

- [x] Task 5: Create Override Abuse Detection Service (AC: #1, #2, #3)
  - [x] 5.1 Create `src/application/services/override_abuse_detection_service.py`
  - [x] 5.2 Implement `OverrideAbuseDetectionService`:
    - Inject: `OverrideAbuseValidatorProtocol`, `AnomalyDetectorProtocol`, `EventWriterService`, `HaltChecker`
    - Constants:
      - `ANOMALY_DETECTION_WINDOW_DAYS = 90` (FP-3 statistical analysis window)
      - `SLOW_BURN_WINDOW_DAYS = 365` (RT-3/ADR-7 long-term pattern detection)
      - `ANOMALY_CONFIDENCE_THRESHOLD = 0.7` (minimum confidence for alerts)
  - [x] 5.3 Implement `validate_override_command(scope: str, action_type: str, keeper_id: str) -> ValidationResult`:
    - HALT CHECK FIRST (CT-11)
    - Check for forbidden scopes (delegate to ConstitutionValidatorProtocol)
    - Check for history edit attempt (FR87)
    - Check for evidence destruction attempt (FR87)
    - If invalid: write `OverrideAbuseRejectedEvent` and return violation details
    - If valid: return success
  - [x] 5.4 Implement `detect_anomalies() -> list[AnomalyResult]`:
    - HALT CHECK FIRST (CT-11)
    - Run frequency spike detection
    - Run coordinated pattern detection
    - Run slow-burn erosion detection (ADR-7)
    - For each detected anomaly: write `AnomalyDetectedEvent`
    - Return all anomalies
  - [x] 5.5 Implement `analyze_keeper_behavior(keeper_id: str) -> KeeperBehaviorReport`:
    - Get override frequency data
    - Compare to baseline
    - Flag statistical outliers
  - [x] 5.6 Implement `run_weekly_anomaly_review() -> AnomalyReviewReport` (ADR-7):
    - HALT CHECK FIRST (CT-11)
    - Run all anomaly detectors
    - Aggregate results into review report
    - Write summary event
  - [x] 5.7 Export from `src/application/services/__init__.py`

- [x] Task 6: Create Override Abuse Validator Stub (AC: #1)
  - [x] 6.1 Create `src/infrastructure/stubs/override_abuse_validator_stub.py`
  - [x] 6.2 Implement `OverrideAbuseValidatorStub`:
    - Configurable forbidden scope patterns
    - History edit scope detection (`history`, `event_store.delete`, `event_store.modify`)
    - Evidence destruction scope detection (`evidence`, `audit_log.delete`, `witness.remove`)
    - `add_forbidden_scope(scope: str)` for test setup
    - `clear()` for test cleanup
  - [x] 6.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 7: Create Anomaly Detector Stub (AC: #2, #3)
  - [x] 7.1 Create `src/infrastructure/stubs/anomaly_detector_stub.py`
  - [x] 7.2 Implement `AnomalyDetectorStub`:
    - Configurable anomaly injection for testing
    - `set_detected_anomalies(anomalies: list[AnomalyResult])` for test setup
    - `set_keeper_frequency(keeper_id: str, frequency: FrequencyData)` for test setup
    - `clear()` for test cleanup
  - [x] 7.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 8: Write Unit Tests (AC: #1, #2, #3)
  - [x] 8.1 Create `tests/unit/domain/test_override_abuse_events.py` (23 tests):
    - Test `OverrideAbuseRejectedPayload` creation with required fields
    - Test `AnomalyDetectedPayload` creation with required fields
    - Test `signable_content()` determinism for both payloads
    - Test `ViolationType` enum values
    - Test `AnomalyType` enum values
  - [x] 8.2 Create `tests/unit/domain/test_override_abuse_errors.py` (14 tests):
    - Test `HistoryEditAttemptError` creation with FR87 reference
    - Test `EvidenceDestructionAttemptError` creation with FR87 reference
    - Test `ConstitutionalConstraintViolationError` creation with FR86 reference
  - [x] 8.3 Create `tests/unit/application/test_override_abuse_validator_port.py` (12 tests):
    - Test protocol compliance with stub
    - Test `ValidationResult` dataclass
  - [x] 8.4 Create `tests/unit/application/test_anomaly_detector_port.py` (14 tests):
    - Test protocol compliance with stub
    - Test `AnomalyResult` dataclass
    - Test `FrequencyData` dataclass
  - [x] 8.5 Create `tests/unit/application/test_override_abuse_detection_service.py` (20 tests):
    - Test `validate_override_command()` rejects history edit (AC1)
    - Test `validate_override_command()` rejects evidence destruction (AC1)
    - Test `validate_override_command()` allows valid overrides
    - Test `validate_override_command()` with HALT CHECK
    - Test `detect_anomalies()` detects frequency spikes (AC2)
    - Test `detect_anomalies()` detects coordinated patterns (AC2)
    - Test `detect_anomalies()` detects slow-burn erosion (AC3)
    - Test `detect_anomalies()` writes events for detected anomalies
    - Test `detect_anomalies()` with HALT CHECK
    - Test `run_weekly_anomaly_review()` aggregates all detections (ADR-7)
  - [x] 8.6 Create `tests/unit/infrastructure/test_override_abuse_validator_stub.py` (32 tests):
    - Test stub implementation of all protocol methods
    - Test configurable forbidden scopes
    - Test history edit detection patterns
    - Test evidence destruction detection patterns
  - [x] 8.7 Create `tests/unit/infrastructure/test_anomaly_detector_stub.py` (24 tests):
    - Test stub implementation of all protocol methods
    - Test configurable anomaly injection
    - Test frequency data configuration

- [x] Task 9: Write Integration Tests (AC: #1, #2, #3)
  - [x] 9.1 Create `tests/integration/test_override_abuse_detection_integration.py` (17 tests):
    - Test: `test_fr86_constitutional_constraint_validation` (AC1)
    - Test: `test_fr87_history_edit_rejected_and_logged` (AC1)
    - Test: `test_fr87_evidence_destruction_rejected_and_logged` (AC1)
    - Test: `test_override_abuse_event_is_witnessed` (CT-12)
    - Test: `test_fp3_statistical_anomaly_detection` (AC2)
    - Test: `test_anomaly_detected_event_is_witnessed` (CT-12)
    - Test: `test_adr7_slow_burn_attack_detection` (AC3)
    - Test: `test_coordinated_override_patterns_detected` (AC3)
    - Test: `test_weekly_anomaly_review_ceremony` (ADR-7)
    - Test: `test_valid_override_passes_validation`
    - Test: `test_halt_check_prevents_validation_during_halt`
    - Test: `test_halt_check_prevents_detection_during_halt`

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR86**: System SHALL validate override commands against constitutional constraints before execution
- **FR87**: Override commands violating constitutional constraints (history edit, evidence destruction) SHALL be rejected and logged as override abuse
- **CT-9**: Attackers are patient - aggregate erosion must be detected
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> All abuse events MUST be witnessed
- **FP-3**: Patient attacker detection needs ADR-7 (Aggregate Anomaly Detection)

### ADR-7 Implementation Context

From the architecture document, ADR-007 defines **hybrid detection with weekly anomaly review ceremony**:

| Layer | Method | Response |
|-------|--------|----------|
| **Rules** | Predefined thresholds | Auto-alert, auto-halt if critical |
| **Statistics** | Baseline deviation detection | Queue for review |
| **Human** | Weekly anomaly review ceremony | Classify, escalate, or dismiss |

**Metrics tracked (relevant to this story):**
- Halt frequency by source
- Ceremony frequency by type
- Witness response times
- **Event rate patterns** <- Override abuse patterns
- **Failed verification attempts** <- Abuse rejections

**ADR-7 Acceptance Criteria:**
- Weekly anomaly review ceremony is scheduled and attended
- Anomaly backlog does not exceed 50 items
- Each anomaly is classified: true positive, false positive, or needs investigation
- True positives trigger documented response

### RT-3 Integration (from Story 5.5)

Story 5.5 already implements the **Rules layer** for override trend detection:
- >50% increase in 30 days -> `AntiSuccessAlert`
- >5 overrides in 30 days -> `AntiSuccessAlert` (30_DAY_THRESHOLD)
- >20 overrides in 365 days -> `GovernanceReviewRequired` (RT-3)

This story (5.9) adds the **Statistics layer** and **constitutional validation**:
- FR86/FR87: Constitutional constraint validation (rejection before execution)
- FP-3: Statistical anomaly detection across Keeper behavior
- ADR-7: Long-term pattern analysis for slow-burn attacks

### Forbidden Override Patterns (FR87)

**History Edit Attempts (MUST REJECT):**
```python
HISTORY_EDIT_PATTERNS: frozenset[str] = frozenset([
    "history",
    "event_store.delete",
    "event_store.modify",
    "event_store.update",
    "audit.delete",
    "audit.modify",
    "log.delete",
    "log.modify",
])
```

**Evidence Destruction Attempts (MUST REJECT):**
```python
EVIDENCE_DESTRUCTION_PATTERNS: frozenset[str] = frozenset([
    "evidence",
    "evidence.delete",
    "audit_log.delete",
    "witness.remove",
    "witness.delete",
    "signature.invalidate",
    "hash_chain.modify",
])
```

### Architecture Pattern: Override Abuse Detection Flow

```
Override Command (from OverrideService)
     |
     v
+---------------------------------------------+
| OverrideAbuseDetectionService               | <- Story 5.9 (NEW)
| - HALT CHECK FIRST                          |
| - validate_constitutional_constraints()     |
| - Check for history edit attempt (FR87)     |
| - Check for evidence destruction (FR87)     |
+---------------------------------------------+
     |                                   |
     | (if abuse detected)               | (if valid)
     v                                   v
+---------------------------------------------+
| EventWriterService                          |
| - Write OverrideAbuseRejectedEvent         |
| - Event is witnessed (CT-12)               |
+---------------------------------------------+
     |
     v
+---------------------------------------------+
| AnomalyDetectorProtocol                     | <- Story 5.9 (NEW)
| - detect_keeper_anomalies()                 |
| - detect_coordinated_patterns()             |
| - detect_slow_burn_erosion()                |
+---------------------------------------------+
     | (if anomalies detected)
     v
+---------------------------------------------+
| EventWriterService                          |
| - Write AnomalyDetectedEvent               |
| - Event is witnessed (CT-12)               |
+---------------------------------------------+
```

### Integration with Existing Override System

**From Story 5.4 (Constitution Supremacy):**
- `ConstitutionValidatorProtocol` - validates witness suppression (FR26)
- `WitnessSuppressionAttemptError` - raised for forbidden scopes
- This story extends validation to include FR86/FR87 (history edit, evidence destruction)

**From Story 5.1 (Override Immediate Logging):**
- `OverrideService.initiate_override()` - orchestrates override flow
- This story's validation should be called BEFORE `initiate_override()` writes the event

**From Story 5.5 (Override Trend Analysis):**
- `OverrideTrendAnalysisService` - rules-based threshold detection
- This story adds statistical anomaly detection layer

### Previous Story Learnings (from 5.8)

**Service Pattern:**
- HALT CHECK FIRST at every operation boundary
- Bind logger with operation context
- Write constitutional events for all state changes
- Use specific domain errors with FR references

**Testing Pattern:**
- 80 tests in Story 5.8 - maintain similar rigor
- `pytest.mark.asyncio` for all async tests
- Mock dependencies for unit tests
- Use stubs for integration tests

**Event Pattern:**
- All event payloads have `signable_content()` method for witnessing
- Event type constants defined as module-level `str`
- Frozen dataclasses for immutability

### Files to Create

```
src/domain/events/override_abuse.py                         # Event payloads and types
src/domain/errors/override_abuse.py                         # Override abuse errors
src/application/ports/override_abuse_validator.py           # Validator protocol
src/application/ports/anomaly_detector.py                   # Anomaly detector protocol
src/application/services/override_abuse_detection_service.py # Main service
src/infrastructure/stubs/override_abuse_validator_stub.py   # Validator test stub
src/infrastructure/stubs/anomaly_detector_stub.py           # Anomaly detector test stub
tests/unit/domain/test_override_abuse_events.py             # Event tests
tests/unit/domain/test_override_abuse_errors.py             # Error tests
tests/unit/application/test_override_abuse_validator_port.py    # Port tests
tests/unit/application/test_anomaly_detector_port.py        # Port tests
tests/unit/application/test_override_abuse_detection_service.py # Service tests
tests/unit/infrastructure/test_override_abuse_validator_stub.py # Stub tests
tests/unit/infrastructure/test_anomaly_detector_stub.py     # Stub tests
tests/integration/test_override_abuse_detection_integration.py  # Integration tests
```

### Files to Modify

```
src/domain/events/__init__.py                               # Export new events
src/domain/errors/__init__.py                               # Export new errors
src/application/ports/__init__.py                           # Export new ports
src/application/services/__init__.py                        # Export new service
src/infrastructure/stubs/__init__.py                        # Export new stubs
```

### Import Rules (Hexagonal Architecture)

- `domain/events/` imports from `domain/errors/`, `typing`, `json`, `datetime`, `dataclasses`, `enum`
- `domain/errors/` inherits from `ConstitutionalViolationError`
- `application/ports/` imports from `domain/models/`, `typing` (Protocol)
- `application/services/` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR86/FR87 tests MUST verify specific requirements with rejection and logging
- FP-3 tests MUST verify statistical anomaly detection
- ADR-7 tests MUST verify weekly anomaly review aggregation
- Test HALT CHECK at every operation boundary

### Critical Implementation Notes

1. **Validation Before Logging**: FR86/FR87 validation must happen BEFORE the override is logged (integrate with OverrideService)
2. **Abuse Events Are Witnessed**: All `OverrideAbuseRejectedEvent` and `AnomalyDetectedEvent` MUST be witnessed (CT-12)
3. **Statistical Confidence**: Anomaly detection should include confidence scores to distinguish true positives from noise
4. **Weekly Review**: ADR-7 requires weekly ceremony - service should support batch anomaly review
5. **Coordinated Pattern Detection**: FP-3 specifically calls out detecting coordinated behavior across Keepers

### Project Structure Notes

- Events follow existing payload patterns from Stories 5.5, 5.7, 5.8
- Errors inherit from `ConstitutionalViolationError` with FR references
- Service follows HALT CHECK FIRST pattern throughout
- Anomaly detection builds on Story 5.5 trend analysis foundation

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.9] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR86-FR87] - REFUSE_OVERRIDE Control Primitives
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-007] - Aggregate Anomaly Detection
- [Source: _bmad-output/planning-artifacts/epics.md#FP-3] - Patient attacker detection
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-9] - Patient attackers truth
- [Source: src/domain/errors/override.py] - Override error patterns to follow
- [Source: src/application/services/override_service.py] - Integration point
- [Source: src/application/ports/constitution_validator.py] - Validator pattern to extend
- [Source: src/application/services/override_trend_service.py] - Trend analysis to build upon
- [Source: _bmad-output/implementation-artifacts/stories/5-8-keeper-availability-attestation.md] - Previous story patterns
- [Source: _bmad-output/implementation-artifacts/stories/5-5-override-trend-analysis.md] - Trend analysis patterns

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive FR86-FR87, FP-3, ADR-7 context | Create-Story Workflow (Opus 4.5) |

### File List
