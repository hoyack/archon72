# Story 1.3: Queue Overflow Protection (503 Response)

**Epic:** Petition Epic 1: Petition Intake & State Machine
**Story ID:** petition-1-3-queue-overflow-protection-503
**Status:** done
**Priority:** P0
**Created:** 2026-01-19

---

## User Story

As a **system operator**,
I want the system to return HTTP 503 when the petition queue is overwhelmed,
So that no petitions are silently dropped.

---

## Business Context

This story implements queue overflow protection per FR-1.4, ensuring the system never silently drops petitions. When the pending petition count exceeds a configurable threshold (default: 10,000), new submissions receive HTTP 503 with a `Retry-After` header. This is a constitutional requirement per CT-11 (silent failure destroys legitimacy) and I1 invariant (no silent petition loss).

**Constitutional Alignment:**
- **CT-11:** "Silent failure destroys legitimacy" - Return 503 instead of dropping
- **I1 Invariant:** "No silent petition loss" - Every petition either persists or receives explicit failure
- **NFR-3.1:** "0 lost petitions" - Explicit rejection preserves trust

**Dependencies:**
- Story 1.1: Petition Submission REST Endpoint (COMPLETE) - Endpoint to protect
- Story 1.2: Petition Received Event Emission (COMPLETE) - Event pipeline

**Blocking:**
- Story 1.4: Submitter Rate Limiting - Also uses 503 responses

---

## Acceptance Criteria

### AC1: Queue Depth Threshold Check

**Given** the system is under high load
**When** the pending petition count (state = RECEIVED) exceeds the configured threshold (default: 10,000)
**Then** new petition submissions return HTTP 503 Service Unavailable
**And** the response follows RFC 7807 format:
```json
{
  "type": "https://archon72.io/errors/queue-overflow",
  "title": "Queue Overflow",
  "status": 503,
  "detail": "Petition queue capacity exceeded. Please retry later.",
  "instance": "/api/v1/petition-submissions"
}
```
**And** the response includes `Retry-After` header with configurable delay (default: 60 seconds)
**And** no petition data is persisted or lost (the request simply wasn't accepted)

### AC2: Normal Operation Resumption

**Given** the queue depth drops below threshold (with hysteresis buffer)
**When** new submissions arrive
**Then** normal processing resumes (HTTP 201)
**And** no "thundering herd" effect from immediate retry storms

### AC3: Queue Depth Prometheus Metric

**Given** the metrics endpoint is available
**When** I query `/metrics`
**Then** `petition_queue_depth{state="RECEIVED"}` gauge is exposed
**And** `petition_queue_threshold` gauge shows configured threshold
**And** `petition_queue_rejections_total` counter tracks 503 responses

### AC4: Configurable Threshold

**Given** the application configuration
**When** `PETITION_QUEUE_THRESHOLD` environment variable is set
**Then** the threshold is configurable (default: 10,000)
**And** `PETITION_QUEUE_HYSTERESIS` sets the buffer below threshold to resume (default: 500)

### AC5: Graceful Check Performance

**Given** a petition submission request
**When** queue depth is checked
**Then** the check adds < 5ms latency (use cached count with TTL)
**And** database is not hit on every request

---

## Technical Specification

### Architecture Decision: Cached Queue Depth

Per NFR-1.1 (p99 < 200ms), the queue depth check must be performant. Options considered:

1. **Direct DB count per request** - Rejected (too slow, ~50ms per query)
2. **Cached count with TTL** - SELECTED (5-second TTL, background refresh)
3. **Redis counter** - Overkill for M1; can migrate later if needed

**Implementation:** Use application-level cache with periodic refresh from `list_by_state(RECEIVED)`.

### Component Design

```
┌─────────────────────────────────────────────────────────────────┐
│                     Petition Submission Flow                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  POST /v1/petition-submissions                                   │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Queue Capacity  │◄── QueueCapacityService                    │
│  │    Check        │    (cached count, threshold config)        │
│  └────────┬────────┘                                            │
│           │                                                      │
│     is_accepting?                                                │
│           │                                                      │
│    ┌──────┴──────┐                                              │
│    │             │                                               │
│   YES           NO                                               │
│    │             │                                               │
│    ▼             ▼                                               │
│ Continue    Return 503                                           │
│ to service  with Retry-After                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/application/ports/queue_capacity.py` | CREATE | Port for queue capacity checking |
| `src/application/services/queue_capacity_service.py` | CREATE | Cached capacity tracking service |
| `src/infrastructure/stubs/queue_capacity_stub.py` | CREATE | Stub for testing |
| `src/api/routes/petition_submission.py` | MODIFY | Add capacity check before submission |
| `src/api/dependencies/petition_submission.py` | MODIFY | Wire up capacity service |
| `src/infrastructure/monitoring/metrics.py` | MODIFY | Add queue depth metrics |
| `src/config/petition_config.py` | CREATE | Configuration for thresholds |
| `tests/unit/application/services/test_queue_capacity_service.py` | CREATE | Unit tests |
| `tests/integration/test_queue_overflow_protection.py` | CREATE | Integration tests |

### Port Interface

```python
# src/application/ports/queue_capacity.py
from typing import Protocol

class QueueCapacityPort(Protocol):
    """Port for checking petition queue capacity (Story 1.3, FR-1.4).

    Constitutional Constraints:
    - FR-1.4: Return HTTP 503 on queue overflow
    - NFR-3.1: No silent petition loss
    - CT-11: Fail loud, not silent
    """

    async def is_accepting_submissions(self) -> bool:
        """Check if queue has capacity for new submissions.

        Returns:
            True if queue depth < threshold, False if at capacity.
        """
        ...

    async def get_queue_depth(self) -> int:
        """Get current number of pending petitions (state = RECEIVED).

        Returns:
            Count of petitions in RECEIVED state.
        """
        ...

    def get_threshold(self) -> int:
        """Get configured queue threshold.

        Returns:
            Maximum queue depth before 503 responses.
        """
        ...

    def get_retry_after_seconds(self) -> int:
        """Get Retry-After header value.

        Returns:
            Seconds to include in Retry-After header.
        """
        ...
```

### Service Implementation Pattern

```python
# src/application/services/queue_capacity_service.py
import time
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.domain.models.petition_submission import PetitionState

class QueueCapacityService:
    """Manages petition queue capacity with cached depth tracking.

    Uses time-based caching to avoid database hits on every request.
    Implements hysteresis to prevent oscillation at threshold boundary.
    """

    def __init__(
        self,
        repository: PetitionSubmissionRepositoryProtocol,
        threshold: int = 10_000,
        hysteresis: int = 500,
        cache_ttl_seconds: float = 5.0,
        retry_after_seconds: int = 60,
    ) -> None:
        self._repository = repository
        self._threshold = threshold
        self._hysteresis = hysteresis
        self._cache_ttl = cache_ttl_seconds
        self._retry_after = retry_after_seconds
        self._cached_depth: int = 0
        self._cache_time: float = 0.0
        self._is_rejecting: bool = False  # Track rejection state for hysteresis

    async def is_accepting_submissions(self) -> bool:
        """Check if queue has capacity, with hysteresis."""
        depth = await self.get_queue_depth()

        if self._is_rejecting:
            # Currently rejecting - only resume if below threshold - hysteresis
            if depth < (self._threshold - self._hysteresis):
                self._is_rejecting = False
                return True
            return False
        else:
            # Currently accepting - reject if at or above threshold
            if depth >= self._threshold:
                self._is_rejecting = True
                return False
            return True

    async def get_queue_depth(self) -> int:
        """Get cached queue depth, refreshing if TTL expired."""
        now = time.time()
        if now - self._cache_time > self._cache_ttl:
            # Refresh cache
            _, total_count = await self._repository.list_by_state(
                state=PetitionState.RECEIVED,
                limit=1,  # We only need the count, not the items
            )
            self._cached_depth = total_count
            self._cache_time = now
        return self._cached_depth
```

### Route Integration

```python
# src/api/routes/petition_submission.py (MODIFY)

from src.application.ports.queue_capacity import QueueCapacityPort

@router.post("")
async def submit_petition_submission(
    request_data: SubmitPetitionSubmissionRequest,
    request: Request,
    service: PetitionSubmissionService = Depends(get_petition_submission_service),
    capacity: QueueCapacityPort = Depends(get_queue_capacity_service),  # NEW
) -> SubmitPetitionSubmissionResponse:
    # QUEUE CAPACITY CHECK (FR-1.4) - before any other processing
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

    # Continue with existing flow...
```

### Metrics Integration

```python
# src/infrastructure/monitoring/metrics.py (ADD)

# Add to MetricsCollector.__init__:

# Petition queue depth gauge (AC3)
self.petition_queue_depth = Gauge(
    name="petition_queue_depth",
    documentation="Current number of petitions in RECEIVED state",
    labelnames=["service", "environment", "state"],
    registry=self._registry,
)

# Petition queue threshold gauge
self.petition_queue_threshold = Gauge(
    name="petition_queue_threshold",
    documentation="Configured petition queue threshold",
    labelnames=["service", "environment"],
    registry=self._registry,
)

# Queue rejection counter
self.petition_queue_rejections_total = Counter(
    name="petition_queue_rejections_total",
    documentation="Total petition submissions rejected due to queue overflow",
    labelnames=["service", "environment"],
    registry=self._registry,
)
```

### Configuration

```python
# src/config/petition_config.py (CREATE)
import os

class PetitionConfig:
    """Configuration for petition system (Story 1.3+)."""

    # Queue overflow protection (Story 1.3, FR-1.4)
    QUEUE_THRESHOLD: int = int(os.environ.get("PETITION_QUEUE_THRESHOLD", "10000"))
    QUEUE_HYSTERESIS: int = int(os.environ.get("PETITION_QUEUE_HYSTERESIS", "500"))
    QUEUE_CACHE_TTL: float = float(os.environ.get("PETITION_QUEUE_CACHE_TTL", "5.0"))
    RETRY_AFTER_SECONDS: int = int(os.environ.get("PETITION_RETRY_AFTER", "60"))
```

---

## Tasks / Subtasks

- [x] **Task 1: Create QueueCapacityPort interface** (AC: 1, 2)
  - [x] Define `QueueCapacityPort` protocol in `src/application/ports/queue_capacity.py`
  - [x] Add docstrings with FR-1.4, NFR-3.1, CT-11 references
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 2: Create QueueCapacityService** (AC: 1, 2, 4, 5)
  - [x] Implement cached queue depth tracking with TTL
  - [x] Implement hysteresis logic for threshold boundary
  - [x] Add structured logging for state transitions
  - [x] Inject via constructor with configurable thresholds

- [x] **Task 3: Create QueueCapacityStub for testing** (AC: all)
  - [x] Create stub in `src/infrastructure/stubs/queue_capacity_stub.py`
  - [x] Support configurable threshold and current depth
  - [x] Export from `src/infrastructure/stubs/__init__.py`

- [x] **Task 4: Add Prometheus metrics** (AC: 3)
  - [x] Add `petition_queue_depth{state="RECEIVED"}` gauge to MetricsCollector
  - [x] Add `petition_queue_threshold` gauge
  - [x] Add `petition_queue_rejections_total` counter
  - [x] Update queue depth on service calls

- [x] **Task 5: Create PetitionConfig** (AC: 4)
  - [x] Create `src/config/petition_config.py`
  - [x] Define environment variable mappings
  - [x] Set sensible defaults (10,000 threshold, 500 hysteresis, 60s retry)

- [x] **Task 6: Integrate into petition submission route** (AC: 1, 2)
  - [x] Add capacity check as first operation in `submit_petition_submission`
  - [x] Return RFC 7807 error with `Retry-After` header
  - [x] Increment rejection counter on 503

- [x] **Task 7: Wire up dependency injection** (AC: all)
  - [x] Add `get_queue_capacity_service` to dependencies
  - [x] Pass repository and config to service constructor
  - [x] Update route to inject capacity service

- [x] **Task 8: Write unit tests** (AC: all)
  - [x] Test accepting when below threshold
  - [x] Test rejecting at threshold
  - [x] Test hysteresis prevents oscillation
  - [x] Test cache TTL behavior
  - [x] Test configuration from environment

- [x] **Task 9: Write integration tests** (AC: all)
  - [x] Test 503 response when queue full
  - [x] Test Retry-After header present
  - [x] Test normal 201 when capacity available
  - [x] Test RFC 7807 error format
  - [x] Test metrics exposed correctly

---

## Documentation Checklist

- [x] Architecture docs updated (if patterns/structure changed) - N/A, follows existing patterns
- [x] API docs updated (503 response documented) - RFC 7807 inline documentation
- [x] README updated (if setup/usage changed) - N/A, no setup changes
- [x] Inline comments added for complex logic - Hysteresis and caching documented

---

## Dev Notes

### Developer Golden Rules

1. **HALT CHECK FIRST** - Queue capacity check is BEFORE halt check (more efficient)
2. **FAIL LOUD** - Return 503, never silently drop
3. **CACHE WISELY** - 5s TTL balances accuracy vs performance
4. **HYSTERESIS** - Prevent thundering herd at threshold boundary

### Previous Story Intelligence (Story 1.1/1.2)

From Story 1.1 implementation:
- Route follows RFC 7807 error pattern - **REUSE THIS PATTERN**
- Service uses `LoggingMixin` for structured logging
- `SystemHaltedError` already returns 503 - capacity overflow should too
- Dependency injection via `get_petition_submission_service` pattern

From Story 1.2 implementation:
- Event emission is graceful degradation - same pattern for capacity errors
- Two-phase pattern (persist then emit) already established

### Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                   Cache Refresh Flow                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Request arrives                                             │
│       │                                                      │
│       ▼                                                      │
│  Is cache valid? (now - cache_time < TTL)                   │
│       │                                                      │
│   YES │   NO                                                 │
│   │   │                                                      │
│   │   └─► Query repository.list_by_state(RECEIVED, limit=1) │
│   │       │                                                  │
│   │       ▼                                                  │
│   │       Update cached_depth = total_count                  │
│   │       Update cache_time = now                            │
│   │       │                                                  │
│   │◄──────┘                                                  │
│   │                                                          │
│   ▼                                                          │
│  Return cached_depth                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Hysteresis Logic

To prevent rapid oscillation when queue depth hovers near threshold:

```
Threshold: 10,000
Hysteresis: 500

State: ACCEPTING
  - If depth >= 10,000 → State: REJECTING, return False

State: REJECTING
  - If depth < 9,500 (threshold - hysteresis) → State: ACCEPTING, return True
  - If depth >= 9,500 → State: REJECTING, return False

This prevents:
  10,001 (reject) → 9,999 (accept) → 10,001 (reject) → 9,999 (accept)...
Instead:
  10,001 (reject) → 9,999 (still reject) → ... → 9,499 (accept)
```

### Project Structure Notes

- **Port Location:** `src/application/ports/queue_capacity.py` (hexagonal pattern)
- **Service Location:** `src/application/services/queue_capacity_service.py`
- **Stub Location:** `src/infrastructure/stubs/queue_capacity_stub.py`
- **Config Location:** `src/config/petition_config.py` (new directory if needed)
- **Follows existing patterns from:** `halt_checker`, `content_hash_service`

### Error Response Format

Must match existing RFC 7807 pattern from Story 1.1:

```json
{
  "type": "https://archon72.io/errors/queue-overflow",
  "title": "Queue Overflow",
  "status": 503,
  "detail": "Petition queue capacity exceeded. Please retry later.",
  "instance": "/api/v1/petition-submissions"
}
```

Headers:
```
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
Retry-After: 60
```

### References

- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#FR-1.4]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#NFR-2.1]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#NFR-3.1]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#NFR-7.4]
- [Source: _bmad-output/planning-artifacts/petition-system-architecture.md#HC-6]
- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story-1.3]

---

## FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| FR-1.4 | Return HTTP 503 on queue overflow | QueueCapacityService threshold check |
| NFR-2.1 | Support 10,000+ concurrent petitions in RECEIVED | Configurable threshold |
| NFR-3.1 | No silent petition loss | Explicit 503 rejection |
| NFR-7.4 | Queue depth monitoring with backpressure | Prometheus metrics + threshold enforcement |
| CT-11 | Silent failure destroys legitimacy | Fail loud with RFC 7807 error |

---

## Testing Requirements

### Unit Tests (>90% coverage)

1. **QueueCapacityService**
   - `test_accepting_below_threshold`
   - `test_rejecting_at_threshold`
   - `test_rejecting_above_threshold`
   - `test_hysteresis_prevents_oscillation`
   - `test_cache_returns_stale_within_ttl`
   - `test_cache_refreshes_after_ttl`
   - `test_configuration_from_constructor`

2. **Route Integration**
   - `test_503_returned_when_capacity_exceeded`
   - `test_retry_after_header_present`
   - `test_rfc_7807_error_format`
   - `test_201_returned_when_capacity_available`

### Integration Tests

1. **End-to-End Flow**
   - `test_queue_overflow_returns_503`
   - `test_normal_submission_after_queue_drains`
   - `test_metrics_endpoint_exposes_queue_depth`
   - `test_metrics_endpoint_exposes_threshold`
   - `test_rejection_counter_incremented`

---

## Definition of Done

- [x] QueueCapacityPort interface defined
- [x] QueueCapacityService implements cached threshold checking
- [x] QueueCapacityStub created for testing
- [x] Petition submission route checks capacity first
- [x] HTTP 503 returned with RFC 7807 format
- [x] Retry-After header included in response
- [x] Prometheus metrics exposed (depth, threshold, rejections)
- [x] Configuration via environment variables
- [x] Unit test coverage > 90%
- [x] Integration tests pass
- [x] Hysteresis prevents oscillation
- [x] Cache prevents database overload

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- 2026-01-19: Implementation complete with all ACs satisfied
- 2026-01-19: Code review completed, 3 medium issues fixed:
  - Added `state` label to `petition_queue_depth` metric (AC3 compliance)
  - Added `record_rejection()` method to stub for interface parity
  - Added test for threshold metric set at startup

### File List

**Created:**
- `src/application/ports/queue_capacity.py` - QueueCapacityPort protocol
- `src/application/services/queue_capacity_service.py` - Cached capacity tracking with hysteresis
- `src/infrastructure/stubs/queue_capacity_stub.py` - Test stub with full behavior
- `src/config/petition_config.py` - PetitionQueueConfig dataclass
- `src/domain/errors/queue_overflow.py` - QueueOverflowError exception
- `tests/unit/application/ports/test_queue_capacity.py` - Port unit tests
- `tests/unit/application/services/test_queue_capacity_service.py` - Service unit tests
- `tests/unit/config/test_petition_config.py` - Config unit tests
- `tests/integration/test_queue_overflow_protection.py` - Integration tests

**Modified:**
- `src/api/routes/petition_submission.py` - Added capacity check before submission
- `src/api/dependencies/petition_submission.py` - DI wiring for QueueCapacityService
- `src/infrastructure/monitoring/metrics.py` - Added queue depth, threshold, rejections metrics
- `src/application/ports/__init__.py` - Exported QueueCapacityPort
- `src/application/services/__init__.py` - Exported QueueCapacityService
- `src/infrastructure/stubs/__init__.py` - Exported QueueCapacityStub
- `src/domain/errors/__init__.py` - Exported QueueOverflowError
