# Story 6.9: Topic Manipulation Defense (FR118-FR119)

Status: complete

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **system operator**,
I want defenses against topic manipulation and seed manipulation,
So that agenda cannot be gamed.

## Acceptance Criteria

### AC1: Topic Manipulation Pattern Detection (FR118)
**Given** topic submissions from external sources
**When** coordinated manipulation patterns are detected (timing, content similarity, source collusion)
**Then** a `TopicManipulationSuspectedEvent` is created
**And** suspicious topics are flagged for review
**And** pattern details are logged for investigation
**And** detection continues operating (does not reject topics)

### AC2: External Topic Rate Limiting (FR118)
**Given** external topic sources (non-autonomous)
**When** rate limit of 10 topics/day per source is exceeded
**Then** excess topics are rejected with clear error message
**And** `TopicRateLimitDailyEvent` is created
**And** rate limit status is publicly visible

### AC3: Autonomous Topic Priority (FR119)
**Given** autonomous constitutional self-examination topics
**When** topics are prioritized for deliberation
**Then** autonomous topics have priority over external submissions
**And** priority is enforced at queue processing time
**And** external topics can never starve autonomous topics
**And** topic drowning attack is prevented

### AC4: Seed Source Independence Verification (FR124 extension)
**Given** random seeds generated for any system operation
**When** seeds are generated from entropy sources
**Then** source independence is verified before use
**And** predictable seeds are rejected with error
**And** `SeedValidationEvent` is created for audit trail
**And** failed validation triggers alert (not halt)

### AC5: Topic Submission Coordination Detection
**Given** multiple topic submissions in short window
**When** submissions exhibit coordination signals:
  - Same content with minor variations
  - Timing pattern (burst within minutes)
  - Same network origin or session patterns
**Then** coordination score is calculated
**And** if score > 0.7, `CoordinatedSubmissionSuspectedEvent` is created
**And** submissions are flagged for human review

### AC6: Manipulation Defense Audit Trail
**Given** any topic manipulation defense action
**When** detection, flagging, or rate limiting occurs
**Then** full audit trail is created
**And** trail includes: source_id, action_type, evidence_hash, timestamp
**And** audit events are witnessed (CT-12)
**And** trail is queryable by observers

## Tasks / Subtasks

- [ ] Task 1: Create Topic Manipulation Domain Events (AC: #1, #5, #6)
  - [ ] 1.1 Create `src/domain/events/topic_manipulation.py`:
    - `TopicManipulationSuspectedEventPayload` frozen dataclass with:
      - `detection_id: str` - Unique detection identifier
      - `suspected_topics: tuple[str, ...]` - Topic IDs flagged
      - `pattern_type: ManipulationPatternType` - COORDINATED_TIMING, CONTENT_SIMILARITY, SOURCE_COLLUSION
      - `confidence_score: float` - 0.0 to 1.0
      - `evidence_summary: str` - Human-readable evidence description
      - `detected_at: datetime`
      - `detection_window_hours: int` - Analysis window used
      - Event type constant: `TOPIC_MANIPULATION_SUSPECTED_EVENT_TYPE = "topic.manipulation_suspected"`
      - `to_dict()` for event serialization
      - `signable_content()` for witnessing (CT-12)
    - `ManipulationPatternType` enum: COORDINATED_TIMING, CONTENT_SIMILARITY, SOURCE_COLLUSION, BURST_SUBMISSION, UNKNOWN
  - [ ] 1.2 Create `CoordinatedSubmissionSuspectedEventPayload` frozen dataclass:
    - `detection_id: str`
    - `submission_ids: tuple[str, ...]` - Related submission IDs
    - `coordination_score: float` - 0.0 to 1.0
    - `coordination_signals: tuple[str, ...]` - Detected signals
    - `source_ids: tuple[str, ...]` - Sources involved
    - `detected_at: datetime`
    - Event type constant: `COORDINATED_SUBMISSION_SUSPECTED_EVENT_TYPE = "topic.coordinated_submission_suspected"`
  - [ ] 1.3 Create `TopicRateLimitDailyEventPayload` frozen dataclass:
    - `source_id: str`
    - `topics_today: int`
    - `daily_limit: int` (default 10)
    - `rejected_topic_ids: tuple[str, ...]`
    - `limit_start: datetime`
    - `limit_reset_at: datetime`
    - Event type constant: `TOPIC_RATE_LIMIT_DAILY_EVENT_TYPE = "topic.rate_limit_daily"`
  - [ ] 1.4 Export from `src/domain/events/__init__.py`

- [ ] Task 2: Create Seed Validation Domain Events (AC: #4)
  - [ ] 2.1 Create `src/domain/events/seed_validation.py`:
    - `SeedValidationEventPayload` frozen dataclass with:
      - `validation_id: str`
      - `seed_purpose: str` - What the seed is for
      - `entropy_source_id: str` - Source that provided entropy
      - `independence_verified: bool`
      - `validation_result: SeedValidationResult` - VALID, PREDICTABLE_REJECTED, SOURCE_DEPENDENT
      - `validated_at: datetime`
      - Event type constant: `SEED_VALIDATION_EVENT_TYPE = "seed.validation"`
    - `SeedValidationResult` enum: VALID, PREDICTABLE_REJECTED, SOURCE_DEPENDENT, ENTROPY_UNAVAILABLE
    - `SeedRejectedEventPayload` frozen dataclass:
      - `rejection_id: str`
      - `seed_purpose: str`
      - `rejection_reason: str`
      - `attempted_source: str`
      - `rejected_at: datetime`
      - Event type constant: `SEED_REJECTED_EVENT_TYPE = "seed.rejected"`
  - [ ] 2.2 Export from `src/domain/events/__init__.py`

- [ ] Task 3: Create Topic Manipulation Domain Errors (AC: #1, #2, #4)
  - [ ] 3.1 Create `src/domain/errors/topic_manipulation.py`:
    - `TopicManipulationDefenseError(ConclaveError)` - Base class (NOT constitutional violation)
    - `DailyRateLimitExceededError(TopicManipulationDefenseError)` - FR118 daily limit
      - Attributes: `source_id: str`, `topics_today: int`, `daily_limit: int`
      - Message: "FR118: Daily topic limit exceeded - {source_id} submitted {topics_today} topics (limit: {daily_limit})"
    - `PredictableSeedError(ConstitutionalViolationError)` - Seed manipulation detected
      - Attributes: `seed_purpose: str`, `predictability_reason: str`
      - Message: "FR124: Predictable seed rejected - {seed_purpose}: {predictability_reason}"
    - `SeedSourceDependenceError(ConstitutionalViolationError)` - Source independence failed
      - Attributes: `seed_purpose: str`, `failed_source: str`
      - Message: "FR124: Seed source independence verification failed for {seed_purpose}"
  - [ ] 3.2 Export from `src/domain/errors/__init__.py`

- [ ] Task 4: Create Topic Manipulation Detector Port (AC: #1, #5)
  - [ ] 4.1 Create `src/application/ports/topic_manipulation_detector.py`:
    - `TopicManipulationDetectorProtocol` ABC with methods:
      - `async def analyze_submissions(topic_ids: tuple[str, ...], window_hours: int = 24) -> ManipulationAnalysisResult`
        - Analyzes topics for manipulation patterns
      - `async def calculate_coordination_score(submission_ids: tuple[str, ...]) -> float`
        - Returns coordination score 0.0 to 1.0
      - `async def get_content_similarity(topic_id_a: str, topic_id_b: str) -> float`
        - Returns content similarity score
      - `async def get_timing_pattern(source_id: str, window_hours: int) -> TimingPatternResult`
        - Analyzes submission timing for burst detection
      - `async def flag_for_review(topic_id: str, reason: str) -> None`
        - Flags topic for human review
      - `async def get_flagged_topics(limit: int = 100) -> list[FlaggedTopic]`
        - Gets topics flagged for review
    - `ManipulationAnalysisResult` frozen dataclass:
      - `manipulation_suspected: bool`
      - `pattern_type: ManipulationPatternType | None`
      - `confidence_score: float`
      - `evidence_summary: str`
      - `topic_ids_affected: tuple[str, ...]`
    - `TimingPatternResult` frozen dataclass:
      - `is_burst: bool`
      - `submissions_in_window: int`
      - `burst_threshold: int`
      - `window_hours: int`
    - `FlaggedTopic` frozen dataclass:
      - `topic_id: str`
      - `flag_reason: str`
      - `flagged_at: datetime`
      - `reviewed: bool`
  - [ ] 4.2 Export from `src/application/ports/__init__.py`

- [ ] Task 5: Create Seed Validator Port (AC: #4)
  - [ ] 5.1 Create `src/application/ports/seed_validator.py`:
    - `SeedValidatorProtocol` ABC with methods:
      - `async def validate_seed_source(source_id: str, purpose: str) -> SeedSourceValidation`
        - Validates entropy source independence
      - `async def check_predictability(seed_bytes: bytes, context: str) -> PredictabilityCheck`
        - Checks if seed appears predictable
      - `async def record_seed_usage(seed_hash: str, purpose: str, source_id: str) -> None`
        - Records seed usage for audit trail
      - `async def get_seed_audit_trail(purpose: str, limit: int = 100) -> list[SeedUsageRecord]`
        - Gets seed usage audit trail
    - `SeedSourceValidation` frozen dataclass:
      - `source_id: str`
      - `is_independent: bool`
      - `validation_reason: str`
      - `last_verified_at: datetime | None`
    - `PredictabilityCheck` frozen dataclass:
      - `is_predictable: bool`
      - `predictability_indicators: tuple[str, ...]`
      - `recommendation: str`
    - `SeedUsageRecord` frozen dataclass:
      - `seed_hash: str`
      - `purpose: str`
      - `source_id: str`
      - `used_at: datetime`
      - `validation_result: SeedValidationResult`
  - [ ] 5.2 Export from `src/application/ports/__init__.py`

- [ ] Task 6: Create Daily Rate Limiter Port Extension (AC: #2)
  - [ ] 6.1 Extend or create `src/application/ports/topic_daily_limiter.py`:
    - `TopicDailyLimiterProtocol` ABC with methods:
      - `async def check_daily_limit(source_id: str) -> bool`
        - Returns True if within daily limit
      - `async def get_daily_count(source_id: str) -> int`
        - Returns topics submitted today by source
      - `async def record_daily_submission(source_id: str) -> int`
        - Records submission and returns new count
      - `async def get_daily_limit() -> int`
        - Returns current daily limit (default 10)
      - `async def get_limit_reset_time(source_id: str) -> datetime`
        - Returns when limit resets for source
      - `async def is_external_source(source_id: str) -> bool`
        - Returns True if source is external (non-autonomous)
    - Note: This is separate from hourly rate limiter in TopicRateLimiterPort
  - [ ] 6.2 Export from `src/application/ports/__init__.py`

- [ ] Task 7: Create Topic Priority Port (AC: #3)
  - [ ] 7.1 Create `src/application/ports/topic_priority.py`:
    - `TopicPriorityProtocol` ABC with methods:
      - `async def get_topic_priority(topic_id: str) -> TopicPriorityLevel`
        - Returns priority level for topic
      - `async def set_topic_priority(topic_id: str, priority: TopicPriorityLevel) -> None`
        - Sets priority level for topic
      - `async def get_next_topic_for_deliberation() -> str | None`
        - Returns highest priority topic not yet deliberated
      - `async def get_queued_topics_by_priority() -> dict[TopicPriorityLevel, list[str]]`
        - Returns topics grouped by priority
      - `async def ensure_autonomous_priority() -> None`
        - Enforces autonomous topics always have higher priority
    - `TopicPriorityLevel` enum:
      - CONSTITUTIONAL_EXAMINATION (highest - autonomous self-examination)
      - AUTONOMOUS (agent-initiated)
      - SCHEDULED (pre-scheduled)
      - PETITION (external - lowest)
  - [ ] 7.2 Export from `src/application/ports/__init__.py`

- [ ] Task 8: Create Topic Manipulation Defense Service (AC: #1, #2, #3, #5, #6)
  - [ ] 8.1 Create `src/application/services/topic_manipulation_defense_service.py`:
    - Inject: `HaltChecker`, `TopicManipulationDetectorProtocol`, `TopicDailyLimiterProtocol`, `TopicPriorityProtocol`, `EventWriterService` (optional)
    - HALT CHECK FIRST at every operation boundary (CT-11)
  - [ ] 8.2 Implement `async def check_for_manipulation(topic_ids: tuple[str, ...], window_hours: int = 24) -> ManipulationCheckResult`:
    - HALT CHECK FIRST (CT-11)
    - Call detector to analyze submissions
    - If manipulation suspected:
      - Create `TopicManipulationSuspectedEvent`
      - Flag topics for review
    - Return check result
  - [ ] 8.3 Implement `async def submit_external_topic(topic_id: str, source_id: str) -> ExternalTopicResult`:
    - HALT CHECK FIRST (CT-11)
    - Check if source is external
    - Check daily rate limit (FR118)
    - If exceeded:
      - Create `TopicRateLimitDailyEvent`
      - Raise `DailyRateLimitExceededError`
    - Record submission
    - Return success result
  - [ ] 8.4 Implement `async def get_next_topic_with_priority() -> str | None`:
    - HALT CHECK FIRST (CT-11)
    - Ensure autonomous priority (FR119)
    - Return highest priority topic
    - Log selection for audit trail
  - [ ] 8.5 Implement `async def check_coordination(submission_ids: tuple[str, ...]) -> CoordinationCheckResult`:
    - HALT CHECK FIRST (CT-11)
    - Calculate coordination score
    - If score > 0.7:
      - Create `CoordinatedSubmissionSuspectedEvent`
      - Flag submissions for review
    - Return check result
  - [ ] 8.6 Export from `src/application/services/__init__.py`

- [ ] Task 9: Create Seed Validation Service (AC: #4)
  - [ ] 9.1 Create `src/application/services/seed_validation_service.py`:
    - Inject: `HaltChecker`, `SeedValidatorProtocol`, `EntropySourceProtocol`, `EventWriterService` (optional)
    - HALT CHECK FIRST at every operation (CT-11)
  - [ ] 9.2 Implement `async def validate_and_get_seed(purpose: str) -> ValidatedSeed`:
    - HALT CHECK FIRST (CT-11)
    - Get entropy from source
    - Validate source independence
    - Check for predictability
    - If any validation fails:
      - Create `SeedRejectedEvent`
      - Raise appropriate error
    - Create `SeedValidationEvent`
    - Record usage for audit
    - Return validated seed
  - [ ] 9.3 Implement `async def get_seed_audit_trail(purpose: str, limit: int = 100) -> list[SeedUsageRecord]`:
    - HALT CHECK FIRST (CT-11)
    - Return audit trail for observers
  - [ ] 9.4 Export from `src/application/services/__init__.py`

- [ ] Task 10: Create Infrastructure Stubs (AC: #1, #2, #3, #4, #5)
  - [ ] 10.1 Create `src/infrastructure/stubs/topic_manipulation_detector_stub.py`:
    - `TopicManipulationDetectorStub` implementing `TopicManipulationDetectorProtocol`
    - In-memory storage for submissions and analysis
    - `inject_manipulation_pattern(pattern: ManipulationPatternType, topic_ids: tuple[str, ...])` for test setup
    - `set_coordination_score(submission_ids: tuple[str, ...], score: float)` for test control
    - `clear()` for test isolation
    - DEV MODE watermark warning on initialization
  - [ ] 10.2 Create `src/infrastructure/stubs/seed_validator_stub.py`:
    - `SeedValidatorStub` implementing `SeedValidatorProtocol`
    - Configurable validation results
    - `set_source_independence(source_id: str, is_independent: bool)` for test control
    - `set_predictable(seed_bytes: bytes, is_predictable: bool)` for test control
    - `clear()` for test isolation
  - [ ] 10.3 Create `src/infrastructure/stubs/topic_daily_limiter_stub.py`:
    - `TopicDailyLimiterStub` implementing `TopicDailyLimiterProtocol`
    - In-memory tracking of daily submissions
    - `set_daily_count(source_id: str, count: int)` for test setup
    - `set_external_source(source_id: str, is_external: bool)` for test control
    - `clear()` for test isolation
  - [ ] 10.4 Create `src/infrastructure/stubs/topic_priority_stub.py`:
    - `TopicPriorityStub` implementing `TopicPriorityProtocol`
    - In-memory priority tracking
    - `inject_topic_priority(topic_id: str, priority: TopicPriorityLevel)` for test setup
    - `clear()` for test isolation
  - [ ] 10.5 Export from `src/infrastructure/stubs/__init__.py`

- [ ] Task 11: Write Unit Tests (AC: #1, #2, #3, #4, #5, #6)
  - [ ] 11.1 Create `tests/unit/domain/test_topic_manipulation_events.py`:
    - Test `TopicManipulationSuspectedEventPayload` creation with all fields
    - Test `CoordinatedSubmissionSuspectedEventPayload` creation
    - Test `TopicRateLimitDailyEventPayload` creation
    - Test `ManipulationPatternType` enum values
    - Test `to_dict()` returns expected structure
    - Test `signable_content()` determinism (CT-12)
  - [ ] 11.2 Create `tests/unit/domain/test_seed_validation_events.py`:
    - Test `SeedValidationEventPayload` creation
    - Test `SeedRejectedEventPayload` creation
    - Test `SeedValidationResult` enum values
  - [ ] 11.3 Create `tests/unit/domain/test_topic_manipulation_errors.py`:
    - Test `DailyRateLimitExceededError` message includes FR118
    - Test `PredictableSeedError` message includes FR124
    - Test `SeedSourceDependenceError` message includes FR124
    - Test error inheritance hierarchy
  - [ ] 11.4 Create `tests/unit/application/test_topic_manipulation_detector_port.py`:
    - Test protocol method signatures
    - Test result dataclass field validation
  - [ ] 11.5 Create `tests/unit/application/test_topic_manipulation_defense_service.py`:
    - Test `check_for_manipulation()` detects patterns
    - Test `check_for_manipulation()` creates events when suspected
    - Test `submit_external_topic()` enforces daily limit (FR118)
    - Test `submit_external_topic()` rejects excess topics
    - Test `get_next_topic_with_priority()` prioritizes autonomous (FR119)
    - Test `check_coordination()` calculates score correctly
    - Test `check_coordination()` flags at > 0.7
    - Test HALT CHECK on all operations
  - [ ] 11.6 Create `tests/unit/application/test_seed_validation_service.py`:
    - Test `validate_and_get_seed()` validates independence
    - Test `validate_and_get_seed()` checks predictability
    - Test `validate_and_get_seed()` creates events
    - Test `validate_and_get_seed()` raises on predictable seed
    - Test `get_seed_audit_trail()` returns records
    - Test HALT CHECK on all operations
  - [ ] 11.7 Create `tests/unit/infrastructure/test_topic_manipulation_detector_stub.py`:
    - Test stub pattern injection
    - Test coordination score configuration
    - Test `clear()` method
  - [ ] 11.8 Create `tests/unit/infrastructure/test_seed_validator_stub.py`:
    - Test stub independence configuration
    - Test predictability configuration
    - Test `clear()` method

- [ ] Task 12: Write Integration Tests (AC: #1, #2, #3, #4, #5, #6)
  - [ ] 12.1 Create `tests/integration/test_topic_manipulation_defense_integration.py`:
    - Test: `test_fr118_daily_rate_limit_enforced` (AC2)
      - Submit 10 topics from external source
      - 11th topic rejected with DailyRateLimitExceededError
      - Verify TopicRateLimitDailyEvent created
    - Test: `test_fr119_autonomous_priority_over_external` (AC3)
      - Queue external and autonomous topics
      - Verify autonomous returned first
      - Verify external never starves autonomous
    - Test: `test_manipulation_pattern_detected` (AC1)
      - Inject coordinated timing pattern
      - Run analysis
      - Verify TopicManipulationSuspectedEvent created
      - Verify topics flagged for review
    - Test: `test_coordination_score_threshold` (AC5)
      - Submit coordinated submissions
      - Verify score calculated correctly
      - Verify event created at > 0.7
    - Test: `test_audit_trail_created` (AC6)
      - Perform various defense actions
      - Verify audit trail queryable
      - Verify all events witnessed
    - Test: `test_halt_check_prevents_operations`
      - Set system halted
      - Attempt operations
      - Verify SystemHaltedError
  - [ ] 12.2 Create `tests/integration/test_seed_validation_integration.py`:
    - Test: `test_seed_source_independence_verified` (AC4)
      - Configure independent source
      - Validate seed
      - Verify SeedValidationEvent created
    - Test: `test_predictable_seed_rejected` (AC4)
      - Configure predictable seed
      - Attempt validation
      - Verify PredictableSeedError raised
      - Verify SeedRejectedEvent created
    - Test: `test_seed_audit_trail_queryable` (AC4)
      - Generate several seeds
      - Query audit trail
      - Verify complete history returned

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR118**: External topic sources (non-autonomous) SHALL be rate-limited to 10 topics/day per source (Agenda Hijack defense)
- **FR119**: Autonomous constitutional self-examination topics SHALL have priority over external submissions (Topic Drowning defense)
- **FR124**: Witness selection randomness SHALL combine hash chain state + external entropy source meeting independence criteria (Randomness Gaming defense)
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> All events MUST be witnessed
- **CT-13**: Integrity outranks availability -> Queue topics rather than drop them

### FR Clarification

The epics.md lists Story 6.9 as covering "FR127-FR128" but the actual requirements from the PRD show:
- **FR127-FR128** are Amendment Erosion Defense (covered in Story 6.7)
- This story should cover **FR118-FR119** (Topic Flooding Defense) + **seed validation extensions**

The story title "Topic Manipulation Defense" aligns with:
1. **Topic Flooding Defense** (FR118-FR119 from Red Team analysis)
2. **Seed Manipulation Defense** (FR124 extension - source independence verification)

### Relationship to Story 2.7 (Topic Origin Tracking)

Story 2.7 implemented the **foundation** for topic manipulation defense:
- `TopicOrigin` model with origin types (AUTONOMOUS, PETITION, SCHEDULED)
- `TopicRateLimiterPort` for **hourly** rate limiting
- `TopicOriginTrackerPort` for origin tracking
- `TopicOriginService` orchestrating FR71-73

**This story (6.9) extends with:**
- **Daily** rate limiting (FR118) - separate from hourly
- **Priority** enforcement (FR119) - autonomous > external
- **Pattern detection** - coordinated, timing, content similarity
- **Seed validation** - independence verification

### ADR-7: Aggregate Anomaly Detection

Story 6.9 builds on ADR-7's detection approach for topic manipulation:

| Detection Type | Method | Response |
|----------------|--------|----------|
| Rate Limit (FR118) | Daily submission count | Reject excess |
| Priority (FR119) | Queue ordering | Enforce autonomous first |
| Pattern Detection | Statistical analysis | Flag for review |
| Seed Validation | Independence check | Alert on failure |

### Epic 6 Context - Story 6.9 Position

```
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.8: Breach Collusion Defense (COMPLETED)                 │
│ - Collusion investigation triggered from anomalies (FR124)      │
│ - Continuous hash verification (FR125)                          │
│ - Investigation resolution workflow                             │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Followed by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.9: Topic Manipulation Defense (THIS STORY)              │
│ - Daily rate limiting for external sources (FR118)              │
│ - Autonomous topic priority (FR119)                             │
│ - Manipulation pattern detection                                │
│ - Seed source independence verification                         │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Followed by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.10: Configuration Floor Enforcement (NFR39)             │
│ - Constitutional floors enforced in all environments            │
│ - Runtime configuration validation                              │
└─────────────────────────────────────────────────────────────────┘
```

### Key Dependencies from Previous Stories

From Story 2.7 (Topic Origin Tracking):
- `src/domain/models/topic_origin.py` - TopicOrigin, TopicOriginType, TopicOriginMetadata
- `src/domain/errors/topic.py` - TopicDiversityViolationError, TopicRateLimitError
- `src/application/ports/topic_origin_tracker.py` - TopicOriginTrackerPort
- `src/application/ports/topic_rate_limiter.py` - TopicRateLimiterPort (hourly)
- `src/application/services/topic_origin_service.py` - TopicOriginService
- `src/domain/events/topic_rate_limit.py` - TopicRateLimitPayload

From Story 6.5 (Verifiable Witness Selection):
- `src/application/ports/entropy_source.py` - EntropySourceProtocol
- `src/infrastructure/stubs/entropy_source_stub.py` - EntropySourceStub

From Core Infrastructure:
- `src/application/ports/halt_checker.py` - HaltCheckerProtocol
- `src/domain/errors/writer.py` - SystemHaltedError
- `src/domain/events/event.py` - Base event patterns

### Pattern Detection Logic

```python
# Coordination score calculation
async def calculate_coordination_score(
    submissions: list[TopicSubmission],
) -> float:
    """Calculate coordination score for submissions.

    Signals considered:
    - Timing: submissions within 5-minute window
    - Content: >70% content similarity (TF-IDF or hash comparison)
    - Source: same IP range or session pattern
    - Sequence: alternating sources suggesting coordination

    Returns score 0.0 to 1.0 where > 0.7 triggers investigation.
    """
    timing_score = _calculate_timing_correlation(submissions)
    content_score = _calculate_content_similarity(submissions)
    source_score = _calculate_source_pattern(submissions)

    # Weighted average
    return (
        timing_score * 0.4 +
        content_score * 0.4 +
        source_score * 0.2
    )
```

### Priority Enforcement Logic

```python
# Autonomous topic priority (FR119)
class TopicPriorityLevel(str, Enum):
    """Priority levels for topic deliberation.

    FR119: Autonomous constitutional self-examination topics
    SHALL have priority over external submissions.

    Priority order (highest to lowest):
    1. CONSTITUTIONAL_EXAMINATION - system self-examination
    2. AUTONOMOUS - agent-initiated topics
    3. SCHEDULED - pre-scheduled topics
    4. PETITION - external submissions (lowest)
    """
    CONSTITUTIONAL_EXAMINATION = "constitutional_examination"
    AUTONOMOUS = "autonomous"
    SCHEDULED = "scheduled"
    PETITION = "petition"

async def get_next_topic_for_deliberation(self) -> str | None:
    """Get highest priority topic for deliberation (FR119).

    Always returns autonomous/constitutional topics before
    external submissions to prevent topic drowning attack.
    """
    # HALT CHECK FIRST (CT-11)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # Priority order ensures autonomous first
    for priority in TopicPriorityLevel:
        topics = await self._priority.get_queued_topics_by_priority()
        if topics.get(priority):
            return topics[priority][0]

    return None
```

### Seed Independence Verification

```python
# Seed source independence (FR124 extension)
async def validate_seed_source(
    source_id: str,
    purpose: str,
) -> SeedSourceValidation:
    """Validate entropy source is independent (FR124).

    Independence criteria:
    - Source not controlled by system operator
    - Source provides cryptographically secure randomness
    - Source has verifiable public reputation
    - Source freshness can be verified

    Predictability checks:
    - No repeating patterns in recent seeds
    - No correlation with system time
    - No correlation with other system state
    """
    # Check source identity
    if not await self._is_known_independent_source(source_id):
        return SeedSourceValidation(
            source_id=source_id,
            is_independent=False,
            validation_reason="Source not in approved list",
            last_verified_at=None,
        )

    # Check source freshness
    last_verified = await self._get_last_verification(source_id)
    if _is_stale(last_verified):
        # Re-verify source
        await self._verify_source_freshness(source_id)

    return SeedSourceValidation(
        source_id=source_id,
        is_independent=True,
        validation_reason="Source verified and fresh",
        last_verified_at=datetime.now(UTC),
    )
```

### Import Rules (Hexagonal Architecture)

- `domain/events/topic_manipulation.py` imports from `domain/`, `typing`, `dataclasses`, `datetime`, `enum`
- `domain/events/seed_validation.py` imports from `domain/`, `typing`, `dataclasses`, `datetime`, `enum`
- `domain/errors/topic_manipulation.py` inherits from `ConclaveError` and `ConstitutionalViolationError`
- `application/ports/topic_manipulation_detector.py` imports from `abc`, `typing`, domain events
- `application/ports/seed_validator.py` imports from `abc`, `typing`, `datetime`
- `application/services/topic_manipulation_defense_service.py` imports from `application/ports/`, `domain/`
- `application/services/seed_validation_service.py` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR118 tests MUST verify:
  - Daily rate limit enforced (10/day per source)
  - Excess topics rejected
  - Event created on rejection
- FR119 tests MUST verify:
  - Autonomous topics returned before external
  - External can never starve autonomous
- Pattern detection tests MUST verify:
  - Score calculation is deterministic
  - Threshold (0.7) is enforced
  - Events created when threshold exceeded
- Seed validation tests MUST verify:
  - Independence check runs
  - Predictable seeds rejected
  - Audit trail created

### Files to Create

```
src/domain/events/topic_manipulation.py                           # Manipulation events
src/domain/events/seed_validation.py                              # Seed validation events
src/domain/errors/topic_manipulation.py                           # Manipulation errors
src/application/ports/topic_manipulation_detector.py              # Detector port
src/application/ports/seed_validator.py                           # Seed validator port
src/application/ports/topic_daily_limiter.py                      # Daily limiter port
src/application/ports/topic_priority.py                           # Priority port
src/application/services/topic_manipulation_defense_service.py    # Defense service
src/application/services/seed_validation_service.py               # Seed validation service
src/infrastructure/stubs/topic_manipulation_detector_stub.py      # Detector stub
src/infrastructure/stubs/seed_validator_stub.py                   # Seed validator stub
src/infrastructure/stubs/topic_daily_limiter_stub.py              # Daily limiter stub
src/infrastructure/stubs/topic_priority_stub.py                   # Priority stub
tests/unit/domain/test_topic_manipulation_events.py               # Event tests
tests/unit/domain/test_seed_validation_events.py                  # Seed event tests
tests/unit/domain/test_topic_manipulation_errors.py               # Error tests
tests/unit/application/test_topic_manipulation_detector_port.py   # Port tests
tests/unit/application/test_topic_manipulation_defense_service.py # Service tests
tests/unit/application/test_seed_validation_service.py            # Seed service tests
tests/unit/infrastructure/test_topic_manipulation_detector_stub.py # Stub tests
tests/unit/infrastructure/test_seed_validator_stub.py             # Seed stub tests
tests/integration/test_topic_manipulation_defense_integration.py  # Integration tests
tests/integration/test_seed_validation_integration.py             # Seed integration tests
```

### Files to Modify

```
src/domain/events/__init__.py                                     # Export new events
src/domain/errors/__init__.py                                     # Export new errors
src/application/ports/__init__.py                                 # Export new ports
src/application/services/__init__.py                              # Export new services
src/infrastructure/stubs/__init__.py                              # Export new stubs
```

### Project Structure Notes

- Daily rate limiting is SEPARATE from hourly rate limiting (Story 2.7)
- Priority enforcement is at queue-processing time, not submission time
- Pattern detection is advisory (flags for review), not enforcement
- Seed validation creates events but does NOT halt on failure (just alerts)
- All events must be witnessed (CT-12)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.9] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR118] - External topic rate limit (10/day)
- [Source: _bmad-output/planning-artifacts/prd.md#FR119] - Autonomous topic priority
- [Source: _bmad-output/planning-artifacts/prd.md#FR124] - Seed independence
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-7] - Aggregate Anomaly Detection
- [Source: _bmad-output/implementation-artifacts/stories/6-8-breach-collusion-defense.md] - Previous story patterns
- [Source: _bmad-output/implementation-artifacts/stories/2-7-topic-origin-tracking.md] - Topic origin foundation
- [Source: src/domain/models/topic_origin.py] - TopicOrigin model
- [Source: src/application/services/topic_origin_service.py] - Topic origin service
- [Source: src/application/ports/entropy_source.py] - Entropy source protocol
- [Source: _bmad-output/project-context.md] - Project implementation rules

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Story created with FR118-FR119 topic defense, pattern detection, seed validation, builds on Story 2.7 foundation | Create-Story Workflow (Opus 4.5) |

### File List

