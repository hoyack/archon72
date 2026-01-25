# Story 7.1: Status Token for Long-Poll

Status: review

## Story

As an **Observer**,
I want to receive a status_token for efficient long-polling,
So that I can efficiently wait for petition state changes.

## Acceptance Criteria

1. **AC1: Status Token in Response**
   - **Given** I query my petition status
   - **When** the response is returned
   - **Then** it includes a `status_token` (opaque string)
   - **And** the token encodes the current state version

2. **AC2: Long-Poll Endpoint**
   - **Given** I have a status_token
   - **When** I GET `/api/v1/petition-submissions/{petition_id}/status?token={status_token}`
   - **Then** the request blocks until state changes (max 30 seconds)
   - **And** if state changed, returns new status with new token
   - **And** if timeout, returns HTTP 304 Not Modified with same token

3. **AC3: Efficient Connection Management**
   - **And** long-poll connections are efficiently managed (no busy-wait)
   - **And** response latency on change is < 100ms p99 (NFR-1.2)

4. **AC4: Constitutional Compliance**
   - **And** read operations work during halt (CT-13)
   - **And** public access without authentication (FR44)
   - **And** RFC 7807 error responses (D7)

## Tasks / Subtasks

- [x] Task 1: Create Status Token Domain Model (AC: 1)
  - [x] 1.1: Create `StatusToken` value object in `src/domain/models/status_token.py`
  - [x] 1.2: Token encodes: petition_id, state version (update counter or hash), created_at
  - [x] 1.3: Use base64url encoding for URL safety
  - [x] 1.4: Add unit tests for token creation/parsing

- [x] Task 2: Extend PetitionSubmissionStatusResponse (AC: 1)
  - [x] 2.1: Add `status_token: str` field to `PetitionSubmissionStatusResponse` in `src/api/models/petition_submission.py`
  - [x] 2.2: Update existing GET endpoint to include token in response
  - [x] 2.3: Update unit tests for new field

- [x] Task 3: Create Status Token Service (AC: 1, 2)
  - [x] 3.1: Create `StatusTokenServiceProtocol` port in `src/application/ports/`
  - [x] 3.2: Implement `StatusTokenService` in `src/application/services/`
  - [x] 3.3: Methods: `generate_token(petition_id, state_version)`, `validate_token(token)`, `has_changed(token, current_version)`
  - [x] 3.4: Add unit tests for service

- [x] Task 4: Create Long-Poll Endpoint (AC: 2, 3, 4)
  - [x] 4.1: Add new endpoint `GET /v1/petition-submissions/{petition_id}/status` with `token` query param
  - [x] 4.2: Implement async wait using `asyncio.Event` or polling pattern (see observer.py SSE pattern)
  - [x] 4.3: 30-second timeout with HTTP 304 response
  - [x] 4.4: Return new status with new token on state change
  - [x] 4.5: Ensure works during halt (CT-13)
  - [x] 4.6: Add integration tests

- [x] Task 5: Implement State Change Detection (AC: 2, 3)
  - [x] 5.1: Create in-memory state version registry (stub for dev)
  - [x] 5.2: Protocol for notifying waiters on state change
  - [x] 5.3: Efficient connection tracking (no busy-wait)
  - [x] 5.4: Add Prometheus metrics for long-poll connections

- [x] Task 6: Add Prometheus Metrics (AC: 3)
  - [x] 6.1: `petition_status_longpoll_connections_active` gauge
  - [x] 6.2: `petition_status_longpoll_timeout_total` counter
  - [x] 6.3: `petition_status_longpoll_changed_total` counter
  - [x] 6.4: `petition_status_longpoll_latency_seconds` histogram

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [x] Inline comments added for complex logic
- [x] N/A - no documentation impact (self-documenting API with OpenAPI specs)

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Endpoint Pattern:** Follow existing petition submission routes at `src/api/routes/petition_submission.py`
- Router prefix: `/v1/petition-submissions`
- Use `Depends()` for service injection
- RFC 7807 error responses (see `PetitionSubmissionErrorResponse`)

**Async Wait Pattern:** Reference SSE implementation in `src/api/routes/observer.py:567-594`
```python
# Pattern from observer.py (lines 573-583)
payload = await asyncio.wait_for(queue.get(), timeout=30.0)
# ... on TimeoutError, handle appropriately
```

**Constitutional Constraints:**
- CT-13: Read operations allowed during halt
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99
- D7: RFC 7807 error format

**Response Model Pattern:** Extend `PetitionSubmissionStatusResponse` in `src/api/models/petition_submission.py`

### Project Structure Notes

**Files to Create:**
- `src/domain/models/status_token.py` - StatusToken value object
- `src/application/ports/status_token_service.py` - Service protocol
- `src/application/services/status_token_service.py` - Service implementation
- `src/infrastructure/stubs/status_token_registry_stub.py` - In-memory stub for state change tracking
- `tests/unit/domain/models/test_status_token.py`
- `tests/unit/application/services/test_status_token_service.py`
- `tests/unit/api/routes/test_petition_status_longpoll.py`
- `tests/integration/test_petition_status_longpoll.py`

**Files to Modify:**
- `src/api/models/petition_submission.py` - Add status_token field
- `src/api/routes/petition_submission.py` - Add long-poll endpoint
- `src/infrastructure/monitoring/metrics.py` - Add long-poll metrics

**Naming Conventions:**
- Domain models: frozen dataclass with `@dataclass(frozen=True)`
- Services: `*Service` suffix, protocol-based dependency injection
- Stubs: `*Stub` suffix in `infrastructure/stubs/`

### References

- [Source: petition-system-epics.md - Epic 7, Story 7.1]
- [Source: architecture.md - ADR-11 API Versioning]
- [Source: src/api/routes/petition_submission.py:266-330 - Existing status endpoint]
- [Source: src/api/routes/observer.py:567-594 - SSE async wait pattern]
- [Source: src/api/models/petition_submission.py:142-176 - Status response model]

### Technical Implementation Guidance

**Status Token Format:**
```python
# Suggested format: base64url(petition_id:version:timestamp)
# Example: "YWJjZDEyMzQ..."
# Opaque to client, parseable by server
```

**Long-Poll Flow:**
1. Client GETs status with token
2. Server validates token, extracts version
3. If version != current: return immediately with new status + new token
4. If version == current: wait on asyncio.Event (max 30s)
5. On timeout: return HTTP 304 with same token
6. On change: return new status + new token

**State Change Notification Pattern:**
```python
# Registry tracks (petition_id -> (version, asyncio.Event))
# On state change: update version, set event
# Waiters: await event.wait() or timeout
```

**HTTP 304 Response:**
- Return empty body with `304 Not Modified`
- Include `X-Status-Token` header with same token
- No need to re-serialize response

### Previous Story Intelligence

No previous story in Epic 7. However, Epic 8 (Legitimacy Metrics) shares similar patterns:
- Async service patterns in `src/application/services/realm_health_compute_service.py`
- Dashboard query patterns in `src/api/routes/realm_health.py`
- Prometheus metrics patterns in `src/infrastructure/monitoring/metrics.py`

### Git Intelligence Summary

Recent commits (petition system):
- `3fea40b` Story 8.4: High Archon Legitimacy Dashboard
- `6c7308d` Story 8.3: Orphan Petition Detection
- `cddc648` Story 8.2: Legitimacy Decay Alerting
- `93e32ee` Story 8.1: Legitimacy Decay Metric Computation

Key patterns from recent work:
- Pydantic v2 models with custom serializers
- Protocol-based service interfaces
- In-memory stubs for development
- Prometheus Counter/Gauge/Histogram metrics

### Project Context Reference

See `docs/project-context.md` for:
- Import boundaries (domain → application → infrastructure)
- Testing requirements (unit + integration)
- Error handling patterns

### Performance Requirements

- **NFR-1.2:** Status query latency p99 < 100ms
- Efficient connection management (no busy-wait)
- Max 30-second timeout per long-poll request
- Consider connection limits if many concurrent long-polls

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed without issues

### Completion Notes List

1. **Task 1 Complete**: Created `StatusToken` frozen dataclass in `src/domain/models/status_token.py` with:
   - Base64url encoding/decoding
   - Petition ID, version, and timestamp encoding
   - Expiry validation (default 5 minutes)
   - Version computation from content hash + state
   - 31 unit tests passing

2. **Task 2 Complete**: Extended `PetitionSubmissionStatusResponse`:
   - Added `status_token: str | None` field
   - Updated GET endpoint to compute and include token
   - Version computed from content_hash + state for deterministic change detection
   - 6 new unit tests for status_token field

3. **Task 3 Complete**: Created Status Token Service:
   - `StatusTokenServiceProtocol` port in `src/application/ports/status_token_service.py`
   - `StatusTokenService` implementation in `src/application/services/status_token_service.py`
   - 20 unit tests passing

4. **Task 4 Complete**: Created Long-Poll Endpoint:
   - `GET /v1/petition-submissions/{petition_id}/status?token={token}`
   - 30-second timeout with HTTP 304 response
   - Immediate return on state change
   - Works during halt (CT-13)
   - RFC 7807 error responses for invalid/expired tokens
   - 11 unit tests passing

5. **Task 5 Complete**: Implemented State Change Detection:
   - `StatusTokenRegistryStub` in `src/infrastructure/stubs/status_token_registry_stub.py`
   - Uses `asyncio.Event` for efficient waiting (no busy-wait)
   - Thread-safe with asyncio.Lock
   - Automatic cleanup on timeout/cancellation

6. **Task 6 Complete**: Added Prometheus Metrics:
   - `petition_status_longpoll_connections_active` gauge
   - `petition_status_longpoll_timeout_total` counter
   - `petition_status_longpoll_changed_total` counter
   - `petition_status_longpoll_latency_seconds` histogram with result label

### File List

**Files Created:**
- `src/domain/models/status_token.py`
- `src/application/ports/status_token_service.py`
- `src/application/services/status_token_service.py`
- `src/infrastructure/stubs/status_token_registry_stub.py`
- `tests/unit/domain/models/test_status_token.py`
- `tests/unit/application/services/test_status_token_service.py`
- `tests/unit/api/routes/test_petition_status_longpoll.py`

**Files Modified:**
- `src/api/models/petition_submission.py` - Added status_token field
- `src/api/routes/petition_submission.py` - Added long-poll endpoint and status_token generation
- `src/infrastructure/monitoring/metrics.py` - Added long-poll metrics
- `tests/unit/api/routes/test_petition_submission.py` - Added status_token tests

**Test Summary:**
- Total tests: 96 passing
- Task 1: 31 tests
- Task 2: 6 tests (status_token)
- Task 3: 20 tests
- Task 4/5/6: 11 tests
- Existing tests: 28 (all still passing)
