# Story 2.7: Topic Origin Tracking (FR15, FR71-FR73)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **external observer**,
I want topic origins tracked (autonomous, petition, scheduled),
So that I can verify topic diversity and detect manipulation.

## Acceptance Criteria

### AC1: Topic Origin Recording
**Given** a new topic is introduced
**When** it is recorded
**Then** `origin_type` is one of: AUTONOMOUS, PETITION, SCHEDULED
**And** origin metadata is included (petition_id, schedule_ref, etc.)

### AC2: Topic Diversity Enforcement (30% Rule)
**Given** topic diversity enforcement (no >30% from single source)
**When** topics are analyzed over a rolling 30-day window
**Then** no single origin type exceeds 30% of total topics
**And** if threshold is exceeded, alert is raised

### AC3: Topic Flooding Defense (FR71-FR73)
**Given** topic flooding defense
**When** rapid topic submission is detected (>10 per hour from same source)
**Then** rate limiting is applied
**And** excess topics are queued, not rejected
**And** `TopicRateLimitEvent` is created

## Tasks / Subtasks

- [x] Task 1: Create TopicOrigin Domain Model (AC: 1) - 14 tests
  - [x] 1.1 Create `src/domain/models/topic_origin.py`
  - [x] 1.2 Define `TopicOriginType` enum with values: AUTONOMOUS, PETITION, SCHEDULED
  - [x] 1.3 Define `TopicOrigin` frozen dataclass with:
    - `topic_id: UUID`
    - `origin_type: TopicOriginType`
    - `origin_metadata: TopicOriginMetadata`
    - `created_at: datetime`
    - `created_by: str` (agent_id or system)
  - [x] 1.4 Define `TopicOriginMetadata` frozen dataclass with:
    - `petition_id: Optional[UUID]` (for PETITION type)
    - `schedule_ref: Optional[str]` (for SCHEDULED type)
    - `autonomous_trigger: Optional[str]` (for AUTONOMOUS type)
    - `source_agent_id: Optional[str]`
  - [x] 1.5 Add validation: origin_type must match metadata fields
  - [x] 1.6 Add to `src/domain/models/__init__.py` exports
  - [x] 1.7 Add unit tests

- [x] Task 2: Create Topic Diversity Domain Models (AC: 2) - 8 tests
  - [x] 2.1 Create `src/domain/models/topic_diversity.py`
  - [x] 2.2 Define `TopicDiversityStats` frozen dataclass with:
    - `window_start: datetime`
    - `window_end: datetime`
    - `total_topics: int`
    - `autonomous_count: int`
    - `petition_count: int`
    - `scheduled_count: int`
    - `autonomous_pct: float`
    - `petition_pct: float`
    - `scheduled_pct: float`
  - [x] 2.3 Add method `exceeds_threshold(threshold: float = 0.30) -> Optional[TopicOriginType]`
  - [x] 2.4 Add to `src/domain/models/__init__.py` exports
  - [x] 2.5 Add unit tests

- [x] Task 3: Create Topic Errors (AC: 2, 3) - 9 tests
  - [x] 3.1 Create `src/domain/errors/topic.py`
  - [x] 3.2 Define `TopicDiversityViolationError(ConstitutionalViolationError)` with:
    - `origin_type: TopicOriginType`
    - `current_percentage: float`
    - `threshold: float = 0.30`
  - [x] 3.3 Define `TopicRateLimitError(ConclaveError)` with:
    - `source_id: str`
    - `topics_per_hour: int`
    - `limit: int = 10`
  - [x] 3.4 Add to `src/domain/errors/__init__.py` exports
  - [x] 3.5 Add unit tests

- [x] Task 4: Create TopicRateLimitEvent Domain Event (AC: 3) - 6 tests
  - [x] 4.1 Create `src/domain/events/topic_rate_limit.py`
  - [x] 4.2 Define `TopicRateLimitPayload` frozen dataclass with:
    - `source_id: str`
    - `topics_submitted: int`
    - `limit: int`
    - `queued_count: int`
    - `rate_limit_start: datetime`
    - `rate_limit_duration_seconds: int`
  - [x] 4.3 Add to `src/domain/events/__init__.py` exports
  - [x] 4.4 Add unit tests

- [x] Task 5: Create TopicDiversityAlertEvent Domain Event (AC: 2) - 7 tests
  - [x] 5.1 Create `src/domain/events/topic_diversity_alert.py`
  - [x] 5.2 Define `TopicDiversityAlertPayload` frozen dataclass with:
    - `violation_type: TopicOriginType`
    - `current_percentage: float`
    - `threshold: float`
    - `window_start: datetime`
    - `window_end: datetime`
    - `total_topics: int`
  - [x] 5.3 Add to `src/domain/events/__init__.py` exports
  - [x] 5.4 Add unit tests

- [x] Task 6: Create TopicOriginTrackerPort Interface (AC: 1, 2, 3) - 10 tests
  - [x] 6.1 Create `src/application/ports/topic_origin_tracker.py`
  - [x] 6.2 Define `TopicOriginTrackerPort(Protocol)` with:
    - `async def record_topic_origin(topic: TopicOrigin) -> None`
    - `async def get_topic_origin(topic_id: UUID) -> Optional[TopicOrigin]`
    - `async def get_topics_by_origin_type(origin_type: TopicOriginType, since: datetime) -> list[TopicOrigin]`
    - `async def get_diversity_stats(window_days: int = 30) -> TopicDiversityStats`
    - `async def count_topics_from_source(source_id: str, since: datetime) -> int`
  - [x] 6.3 Define constants: `DIVERSITY_WINDOW_DAYS = 30`, `DIVERSITY_THRESHOLD = 0.30`
  - [x] 6.4 Add to `src/application/ports/__init__.py` exports
  - [x] 6.5 Add unit tests

- [x] Task 7: Create TopicRateLimiterPort Interface (AC: 3) - 10 tests
  - [x] 7.1 Create `src/application/ports/topic_rate_limiter.py`
  - [x] 7.2 Define `TopicRateLimiterPort(Protocol)` with:
    - `async def check_rate_limit(source_id: str) -> bool` (returns True if within limit)
    - `async def record_submission(source_id: str) -> int` (returns current count)
    - `async def get_queue_position(topic_id: UUID) -> Optional[int]`
    - `async def queue_topic(topic: TopicOrigin) -> int` (returns queue position)
    - `async def dequeue_topic() -> Optional[TopicOrigin]`
  - [x] 7.3 Define constants: `RATE_LIMIT_PER_HOUR = 10`, `RATE_LIMIT_WINDOW_SECONDS = 3600`
  - [x] 7.4 Add to `src/application/ports/__init__.py` exports
  - [x] 7.5 Add unit tests

- [x] Task 8: Create TopicOriginTrackerStub Infrastructure (AC: 1, 2) - 10 tests
  - [x] 8.1 Create `src/infrastructure/stubs/topic_origin_tracker_stub.py`
  - [x] 8.2 Implement `TopicOriginTrackerStub` with in-memory topic storage
  - [x] 8.3 Implement diversity stats calculation over stored topics
  - [x] 8.4 Follow DEV_MODE_WATERMARK pattern (RT-1/ADR-4)
  - [x] 8.5 Add unit tests

- [x] Task 9: Create TopicRateLimiterStub Infrastructure (AC: 3) - 13 tests
  - [x] 9.1 Create `src/infrastructure/stubs/topic_rate_limiter_stub.py`
  - [x] 9.2 Implement `TopicRateLimiterStub` with:
    - In-memory rate tracking by source_id
    - In-memory topic queue
    - Sliding window rate limit enforcement
  - [x] 9.3 Follow DEV_MODE_WATERMARK pattern
  - [x] 9.4 Add unit tests

- [x] Task 10: Create TopicOriginService Application Service (AC: 1, 2, 3) - 15 tests
  - [x] 10.1 Create `src/application/services/topic_origin_service.py`
  - [x] 10.2 Inject: `HaltChecker`, `TopicOriginTrackerPort`, `TopicRateLimiterPort`
  - [x] 10.3 Implement `async def record_topic(topic: TopicOrigin, source_id: str)`:
    - Check HALT FIRST
    - Check rate limit for source_id
    - If rate limited: queue topic, create TopicRateLimitEvent, return queued position
    - If within limit: record topic origin
  - [x] 10.4 Implement `async def check_diversity_compliance()`:
    - Get diversity stats for 30-day window
    - If any origin type > 30%, create TopicDiversityAlertEvent
    - Return compliance status
  - [x] 10.5 Implement `async def get_topic_origin(topic_id: UUID)`:
    - Return topic origin with full metadata
  - [x] 10.6 Implement `async def process_queued_topics()`:
    - Dequeue topics that are no longer rate limited
    - Record them with origin tracking
  - [x] 10.7 Add unit tests

- [x] Task 11: FR15/FR71-FR73 Compliance Integration Tests (AC: 1, 2, 3) - 16 tests
  - [x] 11.1 Create `tests/integration/test_topic_origin_integration.py`
  - [x] 11.2 Test: Topic recorded with origin_type AUTONOMOUS
  - [x] 11.3 Test: Topic recorded with origin_type PETITION includes petition_id
  - [x] 11.4 Test: Topic recorded with origin_type SCHEDULED includes schedule_ref
  - [x] 11.5 Test: Origin metadata validation (PETITION requires petition_id, etc.)
  - [x] 11.6 Test: Diversity stats calculated correctly over 30-day window
  - [x] 11.7 Test: 30% threshold violation triggers TopicDiversityAlertEvent
  - [x] 11.8 Test: Rate limit applied when >10 topics/hour from same source
  - [x] 11.9 Test: Excess topics are queued, not rejected
  - [x] 11.10 Test: TopicRateLimitEvent created on rate limit
  - [x] 11.11 Test: Queued topics processed when rate limit expires
  - [x] 11.12 Test: HALT state blocks topic operations
  - [x] 11.13 Test: End-to-end topic origin tracking flow
  - [x] 11.14 Test: Multiple sources can submit independently
  - [x] 11.15 Test: Origin type percentages update correctly as topics are added

## Dev Notes

### Critical Architecture Context

**FR15, FR71-FR73: Topic Manipulation Defense**
From the PRD:
- FR15: Topic origins SHALL be tracked (autonomous, petition, scheduled) with origin metadata
- FR71: Topic flooding defense SHALL rate limit rapid submissions (>10/hour from single source)
- FR72: Excess topics SHALL be queued, not rejected
- FR73: Topic diversity enforcement SHALL ensure no single origin type exceeds 30% over rolling 30-day window

**Constitutional Truths Honored:**
- **CT-11:** Silent failure destroys legitimacy -> Rate limiting is logged, not silent
- **CT-12:** Witnessing creates accountability -> All topic origins tracked with attribution
- **CT-13:** Integrity outranks availability -> Topics queued rather than dropped when rate limited

### Previous Story Intelligence (Story 2.6)

**Key Learnings from Story 2.6:**
- HALT FIRST pattern enforced throughout (check halt before operations)
- DEV_MODE_WATERMARK pattern for all stubs: `[DEV_MODE]` prefix
- Hexagonal architecture strictly maintained (domain has no infrastructure imports)
- Structured logging with structlog (no print statements or f-strings in logs)
- Total ~106 tests created for comprehensive coverage (exceeded estimate)
- Application services use dependency injection for ports
- Frozen dataclasses for domain models ensure immutability
- Protocol classes for ports enable dependency inversion

**Existing Code to Reuse:**
- `ConclaveError` from `src/domain/exceptions.py` - base exception class
- `ConstitutionalViolationError` from `src/domain/errors/constitutional.py` - FR violations
- `HaltChecker` pattern from `src/application/ports/halt_checker.py` - HALT checking
- Event patterns from `src/domain/events/` - consistent event structure
- Stub patterns from `src/infrastructure/stubs/` - DEV_MODE watermarking

### Topic Origin Flow

```
1. Topic submission arrives (from agent, petition, or schedule)
2. TopicOriginService.record_topic() called:
   a. HALT CHECK (fail fast if halted)
   b. Check rate limit for source_id
   c. If rate limited (>10/hour):
      - Queue topic
      - Create TopicRateLimitEvent
      - Log rate limiting
      - Return queue position
   d. If within limit:
      - Create TopicOrigin with metadata
      - Record with TopicOriginTracker
      - Log topic creation
3. Periodic diversity check:
   a. Get 30-day stats from tracker
   b. Calculate percentages for each origin type
   c. If any type > 30%:
      - Create TopicDiversityAlertEvent
      - Log violation
      - Raise alert
4. Queue processing (background):
   a. Check for deferred topics
   b. Process when rate limit window expires
```

### Topic Origin Model Design

```python
class TopicOriginType(str, Enum):
    """Types of topic origins (FR15)."""
    AUTONOMOUS = "autonomous"  # Agent-initiated topic
    PETITION = "petition"      # Seeker petition topic
    SCHEDULED = "scheduled"    # Pre-scheduled recurring topic

@dataclass(frozen=True)
class TopicOriginMetadata:
    """Metadata for topic origin tracking.

    Attributes:
        petition_id: UUID of petition (required for PETITION type).
        schedule_ref: Reference to schedule entry (required for SCHEDULED type).
        autonomous_trigger: Description of autonomous trigger (for AUTONOMOUS type).
        source_agent_id: ID of agent that created topic (if applicable).
    """
    petition_id: Optional[UUID] = None
    schedule_ref: Optional[str] = None
    autonomous_trigger: Optional[str] = None
    source_agent_id: Optional[str] = None

@dataclass(frozen=True)
class TopicOrigin:
    """Topic with tracked origin for manipulation defense (FR15, FR71-73).

    Attributes:
        topic_id: Unique identifier for the topic.
        origin_type: Classification of topic origin.
        origin_metadata: Details about the origin.
        created_at: Timestamp of topic creation.
        created_by: ID of creator (agent_id or "system").
    """
    topic_id: UUID
    origin_type: TopicOriginType
    origin_metadata: TopicOriginMetadata
    created_at: datetime
    created_by: str
```

### Diversity Stats Model Design

```python
@dataclass(frozen=True)
class TopicDiversityStats:
    """Statistics for topic diversity over a rolling window (FR73).

    Attributes:
        window_start: Start of analysis window.
        window_end: End of analysis window.
        total_topics: Total topics in window.
        autonomous_count: Count of AUTONOMOUS topics.
        petition_count: Count of PETITION topics.
        scheduled_count: Count of SCHEDULED topics.
        autonomous_pct: Percentage of AUTONOMOUS topics.
        petition_pct: Percentage of PETITION topics.
        scheduled_pct: Percentage of SCHEDULED topics.
    """
    window_start: datetime
    window_end: datetime
    total_topics: int
    autonomous_count: int
    petition_count: int
    scheduled_count: int

    @property
    def autonomous_pct(self) -> float:
        return self.autonomous_count / self.total_topics if self.total_topics > 0 else 0.0

    @property
    def petition_pct(self) -> float:
        return self.petition_count / self.total_topics if self.total_topics > 0 else 0.0

    @property
    def scheduled_pct(self) -> float:
        return self.scheduled_count / self.total_topics if self.total_topics > 0 else 0.0

    def exceeds_threshold(self, threshold: float = 0.30) -> Optional[TopicOriginType]:
        """Check if any origin type exceeds diversity threshold.

        Returns the first origin type exceeding threshold, or None.
        """
        if self.autonomous_pct > threshold:
            return TopicOriginType.AUTONOMOUS
        if self.petition_pct > threshold:
            return TopicOriginType.PETITION
        if self.scheduled_pct > threshold:
            return TopicOriginType.SCHEDULED
        return None
```

### Project Structure Notes

**Files to Create:**
```
src/
├── domain/
│   ├── models/
│   │   ├── topic_origin.py           # TopicOrigin, TopicOriginType, TopicOriginMetadata
│   │   └── topic_diversity.py        # TopicDiversityStats
│   ├── errors/
│   │   └── topic.py                  # TopicDiversityViolationError, TopicRateLimitError
│   └── events/
│       ├── topic_rate_limit.py       # TopicRateLimitPayload
│       └── topic_diversity_alert.py  # TopicDiversityAlertPayload
├── application/
│   ├── ports/
│   │   ├── topic_origin_tracker.py   # TopicOriginTrackerPort
│   │   └── topic_rate_limiter.py     # TopicRateLimiterPort
│   └── services/
│       └── topic_origin_service.py   # TopicOriginService
└── infrastructure/
    └── stubs/
        ├── topic_origin_tracker_stub.py  # TopicOriginTrackerStub
        └── topic_rate_limiter_stub.py    # TopicRateLimiterStub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_topic_origin.py              # 8 tests
│   │   ├── test_topic_diversity.py           # 6 tests
│   │   ├── test_topic_errors.py              # 6 tests
│   │   ├── test_topic_rate_limit_event.py    # 6 tests
│   │   └── test_topic_diversity_alert_event.py  # 6 tests
│   ├── application/
│   │   ├── test_topic_origin_tracker_port.py    # 8 tests
│   │   ├── test_topic_rate_limiter_port.py      # 6 tests
│   │   └── test_topic_origin_service.py         # 14 tests
│   └── infrastructure/
│       ├── test_topic_origin_tracker_stub.py    # 10 tests
│       └── test_topic_rate_limiter_stub.py      # 8 tests
└── integration/
    └── test_topic_origin_tracking_integration.py  # 16 tests
```

**Files to Modify:**
```
src/domain/models/__init__.py         # Add TopicOrigin, TopicOriginType, TopicOriginMetadata, TopicDiversityStats exports
src/domain/errors/__init__.py         # Add TopicDiversityViolationError, TopicRateLimitError exports
src/domain/events/__init__.py         # Add TopicRateLimitPayload, TopicDiversityAlertPayload exports
src/application/ports/__init__.py     # Add TopicOriginTrackerPort, TopicRateLimiterPort exports
```

**Alignment with Hexagonal Architecture:**
- Domain layer (`domain/`) has NO infrastructure imports
- Application layer (`application/`) orchestrates domain and uses ports
- Infrastructure layer (`infrastructure/`) implements adapters for ports
- Import boundary enforcement from Story 0-6 MUST be respected

### Testing Standards

Per `project-context.md`:
- ALL test files use `pytest.mark.asyncio`
- Use `async def test_*` for async tests
- Use `AsyncMock` not `Mock` for async functions
- Unit tests in `tests/unit/{module}/test_{name}.py`
- Integration tests in `tests/integration/test_{feature}_integration.py`
- 80% minimum coverage

**Expected Test Count:** ~94 tests total (8+6+6+6+6+8+6+10+8+14+16)

### Library/Framework Requirements

**Required Dependencies (already installed in Epic 0):**
- `structlog` for logging (NO print statements, NO f-strings in logs)
- `pytest-asyncio` for async testing
- Python 3.11+ compatible (use `Optional[T]` not `T | None`)
- `datetime` and `uuid` from stdlib

**Do NOT add new dependencies without explicit approval.**

### Logging Pattern

Per `project-context.md`, use structured logging:
```python
import structlog

logger = structlog.get_logger()

# CORRECT
logger.info(
    "topic_origin_recorded",
    topic_id=str(topic_id),
    origin_type=origin_type.value,
    created_by=created_by,
)

logger.warning(
    "topic_rate_limited",
    source_id=source_id,
    topics_per_hour=count,
    limit=RATE_LIMIT_PER_HOUR,
    queue_position=position,
)

logger.warning(
    "topic_diversity_violation",
    origin_type=origin_type.value,
    current_pct=current_pct,
    threshold=threshold,
    window_days=30,
)

# WRONG - Never do these
print(f"Topic from {source_id}")  # No print
logger.info(f"Topic {topic_id} recorded")  # No f-strings in logs
```

### Integration with Previous Stories

**Story 2.1 (FR9 - No Preview):**
- Topics must be recorded before any human sees them
- TopicOriginService follows same record-before-view pattern

**Story 2.2 (FR10 - 72 Concurrent Agents):**
- Multiple agents may create AUTONOMOUS topics
- Rate limiting prevents single agent from flooding

**Story 2.5 (FR13 - No Silent Edits):**
- Topic origins are immutable once recorded
- Hash verification ensures origin data integrity

**Story 2.6 (FR14 - Heartbeat Monitoring):**
- HALT FIRST pattern applies to topic operations
- Stub patterns follow same DEV_MODE watermark approach

### Security Considerations

**Topic Flooding Defense (FR71-72):**
- Rate limit: 10 topics per hour per source
- Excess topics queued, not dropped (preserves intent)
- TopicRateLimitEvent logged for audit trail
- Queue position returned for transparency

**Topic Diversity Defense (FR73):**
- 30-day rolling window analysis
- No origin type > 30% of total
- Violation triggers TopicDiversityAlertEvent
- Alert enables human oversight

**Audit Trail:**
- Every topic origin recorded with full metadata
- Rate limiting logged with source and count
- Diversity violations logged with percentages
- All events traceable for forensics

### Configuration Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `DIVERSITY_WINDOW_DAYS` | 30 | Rolling 30-day window per PRD |
| `DIVERSITY_THRESHOLD` | 0.30 | No single origin > 30% per FR73 |
| `RATE_LIMIT_PER_HOUR` | 10 | Max topics per hour per source per FR71 |
| `RATE_LIMIT_WINDOW_SECONDS` | 3600 | 1 hour window for rate limiting |

### Edge Cases to Handle

1. **Empty window**: No topics in 30-day window -> 0% for all types, no violation
2. **Single topic**: One topic = 100% for its type -> triggers violation alert
3. **Exactly 30%**: At threshold is acceptable, only > 30% triggers violation
4. **Rate limit boundary**: 10th topic allowed, 11th queued
5. **Queue overflow**: Define max queue size or unbounded (document decision)
6. **Source ID format**: Validate source_id format (agent-X, petition-system, scheduler)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.7: Topic Origin Tracking]
- [Source: _bmad-output/project-context.md]
- [Source: _bmad-output/implementation-artifacts/stories/2-6-agent-heartbeat-monitoring.md] - Previous story patterns
- [Source: docs/prd.md#Topic Manipulation Defense FR71-FR73]
- [Source: src/application/ports/halt_checker.py] - HALT checking pattern
- [Source: src/domain/errors/constitutional.py] - ConstitutionalViolationError base
- [Source: src/infrastructure/stubs/] - DEV_MODE watermark patterns

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 11 tasks completed successfully
- Total tests: 118 (exceeded estimate of ~94)
- All acceptance criteria met:
  - AC1: Topic origin recording with metadata (AUTONOMOUS, PETITION, SCHEDULED)
  - AC2: Topic diversity enforcement (30% threshold over 30-day window)
  - AC3: Topic flooding defense (rate limit >10/hour, queuing, TopicRateLimitEvent)
- HALT FIRST pattern enforced throughout
- DEV_MODE_WATERMARK pattern followed for all stubs
- Hexagonal architecture strictly maintained
- Structured logging with structlog

### File List

**Domain Layer:**
- `src/domain/models/topic_origin.py` - TopicOrigin, TopicOriginType, TopicOriginMetadata
- `src/domain/models/topic_diversity.py` - TopicDiversityStats
- `src/domain/errors/topic.py` - TopicDiversityViolationError, TopicRateLimitError
- `src/domain/events/topic_rate_limit.py` - TopicRateLimitPayload
- `src/domain/events/topic_diversity_alert.py` - TopicDiversityAlertPayload

**Application Layer:**
- `src/application/ports/topic_origin_tracker.py` - TopicOriginTrackerPort
- `src/application/ports/topic_rate_limiter.py` - TopicRateLimiterPort
- `src/application/services/topic_origin_service.py` - TopicOriginService

**Infrastructure Layer:**
- `src/infrastructure/stubs/topic_origin_tracker_stub.py` - TopicOriginTrackerStub
- `src/infrastructure/stubs/topic_rate_limiter_stub.py` - TopicRateLimiterStub

**Modified Files:**
- `src/domain/models/__init__.py` - Added exports
- `src/domain/errors/__init__.py` - Added exports
- `src/domain/events/__init__.py` - Added exports
- `src/application/ports/__init__.py` - Added exports

**Test Files:**
- `tests/unit/domain/test_topic_origin.py` - 14 tests
- `tests/unit/domain/test_topic_diversity.py` - 8 tests
- `tests/unit/domain/test_topic_errors.py` - 9 tests
- `tests/unit/domain/test_topic_rate_limit_event.py` - 6 tests
- `tests/unit/domain/test_topic_diversity_alert_event.py` - 7 tests
- `tests/unit/application/test_topic_origin_tracker_port.py` - 10 tests
- `tests/unit/application/test_topic_rate_limiter_port.py` - 10 tests
- `tests/unit/infrastructure/test_topic_origin_tracker_stub.py` - 10 tests
- `tests/unit/infrastructure/test_topic_rate_limiter_stub.py` - 13 tests
- `tests/unit/application/test_topic_origin_service.py` - 15 tests
- `tests/integration/test_topic_origin_integration.py` - 16 tests

