# Story 1.4: Submitter Rate Limiting

**Epic:** Petition Epic 1: Petition Intake & State Machine
**Story ID:** petition-1-4-submitter-rate-limiting
**Status:** ready-for-dev
**Priority:** P1
**Created:** 2026-01-19

---

## User Story

As a **system**,
I want to enforce rate limits per submitter,
So that no single identity can flood the petition queue.

---

## Business Context

This story implements per-submitter rate limiting per FR-1.5 and HC-4. Unlike the queue overflow protection (Story 1.3) which protects the system globally, this story prevents individual submitters from flooding the queue, preserving fairness for all petitioners.

**Constitutional Alignment:**
- **CT-11:** "Silent failure destroys legitimacy" - Return 429 with clear rate limit info, never silently drop
- **HC-4:** "Rate limit: 10 petitions/user/hour" - Configurable hardening control
- **NFR-5.1:** "Rate limiting per identity: Configurable per type" - Security requirement
- **D4:** "Rate Limiting Strategy: PostgreSQL time-bucket counters" - Architecture decision

**Dependencies:**
- Story 1.1: Petition Submission REST Endpoint (COMPLETE) - Endpoint to protect
- Story 1.3: Queue Overflow Protection (COMPLETE) - 503 pattern established, reuse RFC 7807 format

**Blocking:**
- Story 5.4: SYBIL-1 Rate Limiting (co-sign rate limits) - Same pattern

---

## Acceptance Criteria

### AC1: Per-Submitter Rate Limit Check

**Given** a submitter_id has submitted petitions
**When** they exceed the rate limit (10 petitions/hour, configurable via HC-4)
**Then** subsequent submissions return HTTP 429 Too Many Requests
**And** the response includes:
  - `Retry-After` header with seconds until next allowed submission
  - RFC 7807 error with `rate_limit_remaining` and `rate_limit_reset` extensions
**And** the response includes governance extensions (trace_id, actor, cycle_id, as_of_seq per D7)

### AC2: Rate Limit Window Expiry

**Given** the rate limit window expires (hourly sliding window)
**When** the submitter submits again
**Then** the submission is accepted normally (HTTP 201)
**And** the rate limit counter increments for the new submission

### AC3: PostgreSQL Time-Bucket Counters (D4)

**Given** the rate limiting architecture decision D4
**When** rate limit state is tracked
**Then** state is stored in PostgreSQL time-bucket counters
**And** minute buckets are summed over the last hour for sliding window
**And** TTL cleanup removes expired buckets (via scheduled job or ON DELETE trigger)

### AC4: Rate Limit Prometheus Metrics

**Given** the metrics endpoint is available
**When** I query `/metrics`
**Then** `petition_rate_limit_hits_total{submitter_id="..."}` counter tracks 429 responses
**And** `petition_rate_limit_remaining{submitter_id="..."}` gauge shows remaining submissions
**And** rate limit blocks are witnessed as governance-relevant events

### AC5: Configurable Rate Limit Thresholds

**Given** the application configuration
**When** `PETITION_RATE_LIMIT_PER_HOUR` environment variable is set
**Then** the threshold is configurable (default: 10 per HC-4)
**And** `PETITION_RATE_LIMIT_WINDOW_MINUTES` sets the window size (default: 60)

### AC6: Rate Limit Check Performance

**Given** a petition submission request
**When** rate limit is checked
**Then** the check adds < 10ms latency (efficient bucket query)
**And** single database query per rate limit check

---

## Technical Specification

### Architecture Decision: PostgreSQL Time-Bucket Counters (D4)

Per architecture decision D4:
- Minute buckets summed over last hour for sliding window
- Persistent and distributed-safe via PostgreSQL
- Bounded by periodic TTL cleanup
- Rate-limit blocks surfaced to client via D7 error format
- **Blocks recorded as governance-relevant events (witnessed)**

**Thresholds (M1 per architecture):**
- Per-user: 10 petitions/hour (HC-4)
- Per-realm: 100 petitions/hour (future: Story 5.x)
- Global: 1000 petitions/hour (future: Story 5.x)

### Component Design

```
┌─────────────────────────────────────────────────────────────────┐
│                   Rate Limit Check Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  POST /v1/petition-submissions                                   │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Queue Capacity  │◄── Story 1.3 (already implemented)         │
│  │    Check        │                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│      is_accepting?                                               │
│           │                                                      │
│     YES   │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Rate Limit      │◄── THIS STORY                              │
│  │    Check        │    (per-submitter, PostgreSQL buckets)     │
│  └────────┬────────┘                                            │
│           │                                                      │
│   within_limit?                                                  │
│           │                                                      │
│    ┌──────┴──────┐                                              │
│    │             │                                               │
│   YES           NO                                               │
│    │             │                                               │
│    ▼             ▼                                               │
│ Continue    Return 429                                           │
│ to service  with Retry-After + rate_limit_remaining              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
-- Migration: 016_create_rate_limit_buckets.sql

CREATE TABLE IF NOT EXISTS petition_rate_limit_buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submitter_id UUID NOT NULL,
    bucket_minute TIMESTAMP WITH TIME ZONE NOT NULL,  -- Truncated to minute
    count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Unique constraint for upsert on (submitter_id, bucket_minute)
    CONSTRAINT uq_rate_limit_bucket UNIQUE (submitter_id, bucket_minute)
);

-- Index for efficient bucket queries
CREATE INDEX IF NOT EXISTS idx_rate_limit_submitter_minute
    ON petition_rate_limit_buckets(submitter_id, bucket_minute DESC);

-- TTL cleanup: buckets older than 2 hours (buffer beyond 1h window)
-- Run via scheduled job or cron trigger
```

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/application/ports/rate_limiter.py` | CREATE | Port for rate limiting |
| `src/application/services/rate_limit_service.py` | CREATE | Time-bucket rate limiting service |
| `src/infrastructure/adapters/persistence/rate_limit_store.py` | CREATE | PostgreSQL bucket adapter |
| `src/infrastructure/stubs/rate_limiter_stub.py` | CREATE | Stub for testing |
| `src/domain/models/rate_limit_bucket.py` | CREATE | Rate limit bucket domain model |
| `src/domain/errors/rate_limit.py` | CREATE | RateLimitExceededError exception |
| `src/api/routes/petition_submission.py` | MODIFY | Add rate limit check after capacity check |
| `src/api/dependencies/petition_submission.py` | MODIFY | Wire up rate limit service |
| `src/infrastructure/monitoring/metrics.py` | MODIFY | Add rate limit metrics |
| `src/config/petition_config.py` | MODIFY | Add rate limit configuration |
| `migrations/016_create_rate_limit_buckets.sql` | CREATE | Database migration |
| `tests/unit/application/services/test_rate_limit_service.py` | CREATE | Unit tests |
| `tests/integration/test_submitter_rate_limiting.py` | CREATE | Integration tests |

### Port Interface

```python
# src/application/ports/rate_limiter.py
from __future__ import annotations
from typing import Protocol
from datetime import datetime
from uuid import UUID

class RateLimiterPort(Protocol):
    """Port for checking submitter rate limits (Story 1.4, FR-1.5, HC-4).

    Constitutional Constraints:
    - FR-1.5: Enforce rate limits per submitter_id
    - HC-4: 10 petitions/user/hour (configurable)
    - NFR-5.1: Rate limiting per identity
    - D4: PostgreSQL time-bucket counters
    """

    async def check_rate_limit(self, submitter_id: UUID) -> RateLimitResult:
        """Check if submitter is within rate limit.

        Returns:
            RateLimitResult with allowed status, remaining count, and reset time.
        """
        ...

    async def record_submission(self, submitter_id: UUID) -> None:
        """Record a submission against the submitter's rate limit.

        Must be called AFTER successful submission, not before.
        """
        ...

    async def get_remaining(self, submitter_id: UUID) -> int:
        """Get remaining submissions in current window.

        Returns:
            Number of submissions remaining before rate limit.
        """
        ...

    def get_limit(self) -> int:
        """Get configured rate limit per hour.

        Returns:
            Maximum submissions per submitter per hour.
        """
        ...
```

### Service Implementation Pattern

```python
# src/application/services/rate_limit_service.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Optional

from src.application.services.base import LoggingMixin
from src.application.ports.rate_limit_store import RateLimitStorePort


@dataclass(frozen=True)
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    remaining: int
    reset_at: datetime
    current_count: int
    limit: int


class RateLimitService(LoggingMixin):
    """Manages per-submitter rate limits with PostgreSQL time-bucket counters.

    Implements D4 architecture decision: minute buckets summed over sliding window.
    """

    def __init__(
        self,
        store: RateLimitStorePort,
        limit_per_hour: int = 10,  # HC-4 default
        window_minutes: int = 60,
    ) -> None:
        self._store = store
        self._limit = limit_per_hour
        self._window_minutes = window_minutes
        self._init_logger(component="petition.rate_limit")

    async def check_rate_limit(self, submitter_id: UUID) -> RateLimitResult:
        """Check if submitter is within rate limit using sliding window."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self._window_minutes)

        # Get total submissions in sliding window
        current_count = await self._store.get_submission_count(
            submitter_id=submitter_id,
            since=window_start,
        )

        remaining = max(0, self._limit - current_count)
        allowed = current_count < self._limit

        # Calculate reset time (next minute boundary when oldest bucket expires)
        reset_at = await self._store.get_oldest_bucket_expiry(
            submitter_id=submitter_id,
            since=window_start,
        ) or (now + timedelta(minutes=self._window_minutes))

        if not allowed:
            self._log.info(
                "rate_limit_exceeded",
                submitter_id=str(submitter_id),
                current_count=current_count,
                limit=self._limit,
            )

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            current_count=current_count,
            limit=self._limit,
        )

    async def record_submission(self, submitter_id: UUID) -> None:
        """Record a submission in the current minute bucket."""
        now = datetime.now(timezone.utc)
        bucket_minute = now.replace(second=0, microsecond=0)

        await self._store.increment_bucket(
            submitter_id=submitter_id,
            bucket_minute=bucket_minute,
        )

        self._log.debug(
            "submission_recorded",
            submitter_id=str(submitter_id),
            bucket_minute=bucket_minute.isoformat(),
        )

    async def get_remaining(self, submitter_id: UUID) -> int:
        """Get remaining submissions in current window."""
        result = await self.check_rate_limit(submitter_id)
        return result.remaining

    def get_limit(self) -> int:
        """Get configured rate limit per hour."""
        return self._limit
```

### Route Integration

```python
# src/api/routes/petition_submission.py (MODIFY)

from src.application.ports.rate_limiter import RateLimiterPort
from src.domain.errors.rate_limit import RateLimitExceededError

@router.post("")
async def submit_petition_submission(
    request_data: SubmitPetitionSubmissionRequest,
    request: Request,
    service: PetitionSubmissionService = Depends(get_petition_submission_service),
    capacity: QueueCapacityPort = Depends(get_queue_capacity_service),
    rate_limiter: RateLimiterPort = Depends(get_rate_limiter),  # NEW
) -> SubmitPetitionSubmissionResponse:
    # 1. QUEUE CAPACITY CHECK (Story 1.3, FR-1.4)
    if not await capacity.is_accepting_submissions():
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/queue-overflow",
                "title": "Queue Overflow",
                "status": 503,
                "detail": "Petition queue capacity exceeded. Please retry later.",
                "instance": str(request.url),
            },
            headers={"Retry-After": str(capacity.get_retry_after_seconds())},
        )

    # 2. RATE LIMIT CHECK (THIS STORY, FR-1.5, HC-4)
    rate_result = await rate_limiter.check_rate_limit(request_data.submitter_id)
    if not rate_result.allowed:
        retry_after = int((rate_result.reset_at - datetime.now(timezone.utc)).total_seconds())
        raise HTTPException(
            status_code=429,
            detail={
                "type": "urn:archon72:petition:rate-limit-exceeded",
                "title": "Rate Limit Exceeded",
                "status": 429,
                "detail": f"Maximum {rate_result.limit} petitions per hour exceeded",
                "instance": str(request.url),
                # Governance extensions (D7)
                "trace_id": get_trace_id(request),
                "actor": f"submitter:{request_data.submitter_id}",
                "cycle_id": get_current_cycle_id(),
                "as_of_seq": await get_current_sequence(),
                # Rate limit extensions
                "rate_limit_remaining": rate_result.remaining,
                "rate_limit_reset": rate_result.reset_at.isoformat(),
                "rate_limit_limit": rate_result.limit,
            },
            headers={"Retry-After": str(max(1, retry_after))},
        )

    # 3. Continue with existing submission flow...
    result = await service.submit_petition(...)

    # 4. Record submission against rate limit AFTER success
    await rate_limiter.record_submission(request_data.submitter_id)

    return result
```

### Metrics Integration

```python
# src/infrastructure/monitoring/metrics.py (ADD)

# Add to MetricsCollector.__init__:

# Rate limit hits counter (AC4)
self.petition_rate_limit_hits_total = Counter(
    name="petition_rate_limit_hits_total",
    documentation="Total petition submissions rejected due to rate limiting",
    labelnames=["service", "environment"],
    registry=self._registry,
)

# Rate limit remaining gauge (AC4)
self.petition_rate_limit_remaining = Gauge(
    name="petition_rate_limit_remaining",
    documentation="Remaining submissions before rate limit for active submitters",
    labelnames=["service", "environment", "submitter_id"],
    registry=self._registry,
)
```

### Configuration Update

```python
# src/config/petition_config.py (MODIFY)

@dataclass(frozen=True)
class PetitionQueueConfig:
    """Configuration for petition queue overflow protection (Story 1.3)."""
    threshold: int = 10_000
    hysteresis: int = 500
    cache_ttl_seconds: float = 5.0
    retry_after_seconds: int = 60


@dataclass(frozen=True)
class PetitionRateLimitConfig:
    """Configuration for submitter rate limiting (Story 1.4, HC-4, D4)."""
    limit_per_hour: int = 10  # HC-4 default
    window_minutes: int = 60
    bucket_ttl_hours: int = 2  # Cleanup buffer


def load_petition_config() -> tuple[PetitionQueueConfig, PetitionRateLimitConfig]:
    """Load petition configuration from environment."""
    queue_config = PetitionQueueConfig(
        threshold=int(os.environ.get("PETITION_QUEUE_THRESHOLD", "10000")),
        hysteresis=int(os.environ.get("PETITION_QUEUE_HYSTERESIS", "500")),
        cache_ttl_seconds=float(os.environ.get("PETITION_QUEUE_CACHE_TTL", "5.0")),
        retry_after_seconds=int(os.environ.get("PETITION_RETRY_AFTER", "60")),
    )
    rate_limit_config = PetitionRateLimitConfig(
        limit_per_hour=int(os.environ.get("PETITION_RATE_LIMIT_PER_HOUR", "10")),
        window_minutes=int(os.environ.get("PETITION_RATE_LIMIT_WINDOW_MINUTES", "60")),
        bucket_ttl_hours=int(os.environ.get("PETITION_RATE_LIMIT_TTL_HOURS", "2")),
    )
    return queue_config, rate_limit_config
```

---

## Tasks / Subtasks

- [ ] **Task 1: Create database migration** (AC: 3)
  - [ ] Create `migrations/016_create_rate_limit_buckets.sql`
  - [ ] Define petition_rate_limit_buckets table with (submitter_id, bucket_minute, count)
  - [ ] Add unique constraint for upsert support
  - [ ] Add index for efficient bucket queries
  - [ ] Run migration and verify schema

- [ ] **Task 2: Create RateLimiterPort interface** (AC: 1, 2)
  - [ ] Define `RateLimiterPort` protocol in `src/application/ports/rate_limiter.py`
  - [ ] Define `RateLimitResult` dataclass with allowed, remaining, reset_at, current_count, limit
  - [ ] Add docstrings with FR-1.5, HC-4, D4 references
  - [ ] Export from `src/application/ports/__init__.py`

- [ ] **Task 3: Create RateLimitService** (AC: 1, 2, 3, 5, 6)
  - [ ] Implement sliding window with minute buckets summed over window
  - [ ] Calculate remaining submissions and reset time
  - [ ] Add structured logging for rate limit events
  - [ ] Inject via constructor with configurable thresholds

- [ ] **Task 4: Create RateLimitStore adapter** (AC: 3)
  - [ ] Create `src/infrastructure/adapters/persistence/rate_limit_store.py`
  - [ ] Implement PostgreSQL queries for bucket operations
  - [ ] Use UPSERT (INSERT ... ON CONFLICT) for increment_bucket
  - [ ] Efficient SUM query for get_submission_count

- [ ] **Task 5: Create RateLimiterStub for testing** (AC: all)
  - [ ] Create stub in `src/infrastructure/stubs/rate_limiter_stub.py`
  - [ ] Support configurable limit and current count per submitter
  - [ ] Export from `src/infrastructure/stubs/__init__.py`

- [ ] **Task 6: Add Prometheus metrics** (AC: 4)
  - [ ] Add `petition_rate_limit_hits_total` counter
  - [ ] Add `petition_rate_limit_remaining` gauge
  - [ ] Increment metrics on rate limit check

- [ ] **Task 7: Update PetitionConfig** (AC: 5)
  - [ ] Add `PetitionRateLimitConfig` dataclass
  - [ ] Define environment variable mappings
  - [ ] Set sensible defaults (10/hour per HC-4, 60 minute window)

- [ ] **Task 8: Integrate into petition submission route** (AC: 1, 2)
  - [ ] Add rate limit check AFTER capacity check
  - [ ] Return RFC 7807 error with governance extensions and rate limit info
  - [ ] Include `Retry-After` header
  - [ ] Record submission AFTER successful persist

- [ ] **Task 9: Wire up dependency injection** (AC: all)
  - [ ] Add `get_rate_limiter` to dependencies
  - [ ] Pass store and config to service constructor
  - [ ] Update route to inject rate limiter

- [ ] **Task 10: Write unit tests** (AC: all)
  - [ ] Test allowing when below limit
  - [ ] Test rejecting at limit
  - [ ] Test remaining count calculation
  - [ ] Test reset time calculation
  - [ ] Test sliding window behavior (bucket expiry)
  - [ ] Test configuration from environment

- [ ] **Task 11: Write integration tests** (AC: all)
  - [ ] Test 429 response when rate limited
  - [ ] Test Retry-After header present
  - [ ] Test rate_limit_remaining in response
  - [ ] Test normal 201 after window expires
  - [ ] Test RFC 7807 error format with governance extensions
  - [ ] Test metrics exposed correctly

- [ ] **Task 12: Create bucket TTL cleanup job** (AC: 3)
  - [ ] Add scheduled job or trigger to clean expired buckets
  - [ ] Delete buckets older than 2 hours (configurable)
  - [ ] Log cleanup statistics

---

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed) - N/A, follows D4 decision
- [ ] API docs updated (429 response documented) - RFC 7807 inline documentation
- [ ] README updated (if setup/usage changed) - N/A, no setup changes
- [ ] Inline comments added for complex logic - Sliding window and bucket TTL documented

---

## Dev Notes

### Developer Golden Rules

1. **RATE LIMIT AFTER CAPACITY** - Check rate limit AFTER queue capacity check (more specific)
2. **RECORD AFTER SUCCESS** - Only increment rate limit counter after successful submission
3. **FAIL LOUD** - Return 429 with full rate limit info, never silently drop
4. **WITNESS BLOCKS** - Rate limit blocks are governance-relevant events (per D4)
5. **D4 COMPLIANCE** - Use PostgreSQL time-bucket counters, NOT Redis or in-memory

### Previous Story Intelligence (Story 1.3)

From Story 1.3 implementation:
- Route follows RFC 7807 error pattern - **REUSE THIS PATTERN**
- Service uses `LoggingMixin` for structured logging - **SAME PATTERN**
- `SystemHaltedError` and `QueueOverflowError` already return 503/429 - **SAME APPROACH**
- Dependency injection via `get_queue_capacity_service` pattern - **COPY THIS**
- Queue capacity check is FIRST, rate limit check is SECOND

From Story 1.3 files created:
- `src/application/ports/queue_capacity.py` - Port pattern to follow
- `src/application/services/queue_capacity_service.py` - Service pattern to follow
- `src/infrastructure/stubs/queue_capacity_stub.py` - Stub pattern to follow
- `src/config/petition_config.py` - Config pattern to extend

### Sliding Window Implementation

```
┌─────────────────────────────────────────────────────────────────┐
│                   Time-Bucket Sliding Window                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Hour Window (60 minutes)                                        │
│  ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐           │
│  │ M1 │ M2 │ M3 │ M4 │...│M57 │M58 │M59 │M60 │NOW │           │
│  │ 0  │ 2  │ 0  │ 1  │...│ 0  │ 1  │ 1  │ 0  │    │           │
│  └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘           │
│                                                                  │
│  Total submissions in window = SUM(bucket counts) = 8            │
│  Remaining = 10 - 8 = 2                                          │
│  Reset at = when oldest non-zero bucket expires                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### PostgreSQL Bucket Query Pattern

```sql
-- Get submission count in sliding window
SELECT COALESCE(SUM(count), 0) as total
FROM petition_rate_limit_buckets
WHERE submitter_id = $1
  AND bucket_minute > NOW() - INTERVAL '60 minutes';

-- Upsert bucket (increment or insert)
INSERT INTO petition_rate_limit_buckets (submitter_id, bucket_minute, count)
VALUES ($1, date_trunc('minute', NOW()), 1)
ON CONFLICT (submitter_id, bucket_minute)
DO UPDATE SET count = petition_rate_limit_buckets.count + 1;

-- Get oldest bucket expiry for reset time
SELECT bucket_minute + INTERVAL '60 minutes' as expires_at
FROM petition_rate_limit_buckets
WHERE submitter_id = $1
  AND bucket_minute > NOW() - INTERVAL '60 minutes'
ORDER BY bucket_minute ASC
LIMIT 1;
```

### Error Response Format (D7)

Must match RFC 7807 pattern with governance extensions:

```json
{
  "type": "urn:archon72:petition:rate-limit-exceeded",
  "title": "Rate Limit Exceeded",
  "status": 429,
  "detail": "Maximum 10 petitions per hour exceeded",
  "instance": "/api/v1/petition-submissions",
  "trace_id": "abc123def456",
  "actor": "submitter:550e8400-e29b-41d4-a716-446655440000",
  "cycle_id": "2026-Q1",
  "as_of_seq": 42857,
  "rate_limit_remaining": 0,
  "rate_limit_reset": "2026-01-19T11:30:00Z",
  "rate_limit_limit": 10
}
```

Headers:
```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 1800
```

### Project Structure Notes

- **Port Location:** `src/application/ports/rate_limiter.py` (hexagonal pattern)
- **Service Location:** `src/application/services/rate_limit_service.py`
- **Adapter Location:** `src/infrastructure/adapters/persistence/rate_limit_store.py`
- **Stub Location:** `src/infrastructure/stubs/rate_limiter_stub.py`
- **Config Location:** `src/config/petition_config.py` (extend existing)
- **Domain Model:** `src/domain/models/rate_limit_bucket.py`
- **Follows existing patterns from:** `queue_capacity`, `content_hash_service`

### References

- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#FR-1.5]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#NFR-5.1]
- [Source: _bmad-output/planning-artifacts/petition-system-architecture.md#D4]
- [Source: _bmad-output/planning-artifacts/petition-system-architecture.md#HC-4]
- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story-1.4]
- [Source: _bmad-output/project-context.md#RFC-7807-Error-Responses]

---

## FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| FR-1.5 | Enforce rate limits per submitter_id | RateLimitService with PostgreSQL buckets |
| HC-4 | Rate limit: 10 petitions/user/hour | Configurable threshold, default 10 |
| NFR-5.1 | Rate limiting per identity: Configurable per type | Environment variable configuration |
| D4 | PostgreSQL time-bucket counters | Minute buckets summed over sliding window |
| D7 | RFC 7807 + governance extensions | Full error response with trace_id, actor, etc. |

---

## Testing Requirements

### Unit Tests (>90% coverage)

1. **RateLimitService**
   - `test_allowing_below_limit`
   - `test_rejecting_at_limit`
   - `test_rejecting_above_limit`
   - `test_remaining_count_calculation`
   - `test_reset_time_calculation`
   - `test_sliding_window_bucket_expiry`
   - `test_record_submission_increments_bucket`
   - `test_configuration_from_constructor`

2. **RateLimitStore**
   - `test_increment_bucket_creates_new`
   - `test_increment_bucket_updates_existing`
   - `test_get_submission_count_sums_buckets`
   - `test_get_submission_count_excludes_expired`
   - `test_get_oldest_bucket_expiry`

3. **Route Integration**
   - `test_429_returned_when_rate_limited`
   - `test_retry_after_header_present`
   - `test_rate_limit_remaining_in_response`
   - `test_rfc_7807_error_format_with_governance_extensions`
   - `test_201_returned_when_within_limit`
   - `test_submission_recorded_after_success`

### Integration Tests

1. **End-to-End Flow**
   - `test_rate_limit_blocks_after_threshold`
   - `test_rate_limit_allows_after_window_expires`
   - `test_rate_limit_sliding_window_behavior`
   - `test_metrics_endpoint_exposes_rate_limit_hits`
   - `test_rate_limit_counter_incremented`

---

## Definition of Done

- [ ] RateLimiterPort interface defined
- [ ] RateLimitService implements PostgreSQL time-bucket counting (D4)
- [ ] RateLimitStore adapter with efficient bucket queries
- [ ] RateLimiterStub created for testing
- [ ] Petition submission route checks rate limit after capacity
- [ ] HTTP 429 returned with RFC 7807 format + governance extensions (D7)
- [ ] Retry-After header included in response
- [ ] rate_limit_remaining and rate_limit_reset in response
- [ ] Prometheus metrics exposed (hits, remaining)
- [ ] Configuration via environment variables
- [ ] Database migration created and tested
- [ ] Unit test coverage > 90%
- [ ] Integration tests pass
- [ ] Bucket TTL cleanup mechanism implemented

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
