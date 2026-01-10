# Story 8.1: Operational Metrics Collection (FR51)

Status: done

## Story

As a **system operator**,
I want uptime, latency, and error rate monitoring,
So that I can maintain system health.

## Acceptance Criteria

### AC1: Prometheus Metrics Endpoint (NFR27)
**Given** the Prometheus metrics system
**When** I scrape `/v1/metrics` endpoint
**Then** all operational metrics are available in Prometheus format
**And** labels include service name and environment
**And** response is text/plain with prometheus exposition format

### AC2: Uptime Tracking Per Service
**Given** the monitoring system
**When** metrics are collected
**Then** uptime is tracked per service (api, event-writer, observer, watchdog)
**And** uptime_seconds gauge shows seconds since last restart
**And** service_starts_total counter tracks restarts

### AC3: Latency Percentiles (NFR27)
**Given** HTTP requests to the API
**When** I examine metrics
**Then** latency percentiles are recorded: p50, p95, p99
**And** histogram buckets are configured appropriately (10ms to 10s)
**And** metrics include: request_duration_seconds histogram

### AC4: Error Rate Tracking
**Given** the API layer
**When** errors occur
**Then** error rates are tracked with labels (endpoint, status_code, error_type)
**And** http_requests_total counter tracks all requests
**And** http_requests_failed_total counter tracks failures (4xx, 5xx)

### AC5: Health and Ready Endpoints (NFR28)
**Given** health endpoints
**When** I call `/v1/health` and `/v1/ready`
**Then** appropriate status is returned (healthy/unhealthy, ready/not-ready)
**And** `/health` checks liveness (process alive)
**And** `/ready` checks readiness (dependencies connected)
**And** dependencies checked include: database, Redis, event store

### AC6: Operational Metrics ONLY (FR52 Alignment)
**Given** the metrics endpoint
**When** I scrape it
**Then** ONLY operational metrics appear (uptime, latency, errors)
**And** NO constitutional metrics appear (breach counts, halt state, witness coverage)
**And** constitutional health is kept separate (Story 8.10)

## Tasks / Subtasks

- [x] **Task 1: Create Prometheus Metrics Infrastructure** (AC: 1,2,3,4)
  - [x] Create `src/infrastructure/monitoring/metrics.py`
    - [x] Use `prometheus_client` library
    - [x] Define `UPTIME_SECONDS` Gauge per service
    - [x] Define `SERVICE_STARTS_TOTAL` Counter
    - [x] Define `HTTP_REQUEST_DURATION_SECONDS` Histogram (buckets: 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    - [x] Define `HTTP_REQUESTS_TOTAL` Counter with labels (method, endpoint, status)
    - [x] Define `HTTP_REQUESTS_FAILED_TOTAL` Counter with labels
    - [x] Create `MetricsCollector` class to manage all metrics
  - [x] Add `prometheus_client` to `pyproject.toml` dependencies
  - [x] Export from `src/infrastructure/monitoring/__init__.py`

- [x] **Task 2: Create Metrics Middleware** (AC: 3,4)
  - [x] Create `src/api/middleware/metrics_middleware.py`
    - [x] FastAPI middleware to record request duration
    - [x] Track requests by endpoint, method, status code
    - [x] Update latency histogram on request completion
    - [x] Increment error counter for 4xx/5xx responses
  - [x] Register middleware in `src/api/main.py`

- [x] **Task 3: Add Metrics Endpoint** (AC: 1)
  - [x] Create `src/api/routes/metrics.py`
    - [x] `GET /v1/metrics` -> Prometheus exposition format
    - [x] Use `generate_latest()` from prometheus_client
    - [x] Return `text/plain; version=0.0.4; charset=utf-8` content type
  - [x] Register router in `src/api/main.py`

- [x] **Task 4: Enhance Health Endpoints** (AC: 5)
  - [x] Update `src/api/routes/health.py`
    - [x] Add `/v1/ready` endpoint for readiness check
    - [x] Enhance `/v1/health` to include uptime_seconds
  - [x] Update `src/api/models/health.py`
    - [x] `HealthResponse` with status, uptime_seconds
    - [x] `ReadyResponse` with status, checks dict (db, redis, event_store)
    - [x] `DependencyCheck` with name, healthy, latency_ms
  - [x] Create `src/application/services/health_service.py`
    - [x] `check_liveness()` -> HealthResponse
    - [x] `check_readiness()` -> ReadyResponse
    - [x] `check_database()` -> DependencyCheck
    - [x] `check_redis()` -> DependencyCheck
    - [x] `check_event_store()` -> DependencyCheck
  - [x] Export from `src/application/services/__init__.py`

- [x] **Task 5: Add Startup Metrics Recording** (AC: 2)
  - [x] Update `src/api/startup.py` or create if needed
    - [x] Record startup time for uptime calculation
    - [x] Increment service_starts_total on startup
    - [x] Use FastAPI lifespan for proper startup/shutdown
  - [x] Store startup timestamp in metrics collector

- [x] **Task 6: Unit Tests** (AC: 1,2,3,4,5,6)
  - [x] Create `tests/unit/infrastructure/test_metrics.py`
    - [x] Test MetricsCollector initialization
    - [x] Test uptime gauge updates
    - [x] Test histogram recording
    - [x] Test counter increments
    - [x] Test no constitutional metrics exposed
  - [x] Create `tests/unit/api/test_metrics_middleware.py`
    - [x] Test request duration recording
    - [x] Test status code labeling
    - [x] Test error tracking
  - [x] Create `tests/unit/application/test_health_service.py`
    - [x] Test liveness check
    - [x] Test readiness check with mocked dependencies
    - [x] Test dependency failure handling

- [x] **Task 7: Integration Tests** (AC: 1,2,3,4,5,6)
  - [x] Create `tests/integration/test_metrics_collection_integration.py`
    - [x] Test `/v1/metrics` returns Prometheus format
    - [x] Test metrics contain uptime_seconds gauge
    - [x] Test metrics contain request_duration histogram
    - [x] Test metrics contain error counters
    - [x] Test no constitutional metrics (breach_count, halt_state, etc.)
  - [x] Create `tests/integration/test_health_ready_integration.py`
    - [x] Test `/v1/health` returns healthy status
    - [x] Test `/v1/ready` checks all dependencies
    - [x] Test `/v1/ready` returns unhealthy if db down
    - [x] Test `/v1/ready` returns unhealthy if redis down

## Dev Notes

### Relevant Architecture Patterns and Constraints

**NFR27 (Observability) Specifics:**
- Prometheus metrics format required
- Labels must include: service, environment
- Latency histograms with standard buckets
- Structured JSON logging (already in place via structlog)

**NFR28 (Health Endpoints) Specifics:**
- `/health` for liveness (is process running?)
- `/ready` for readiness (are dependencies connected?)
- Kubernetes probe compatible responses

**FR52 (Operational-Constitutional Separation) CRITICAL:**
- This story creates ONLY operational metrics
- Constitutional metrics (breach_count, halt_state, dissent_health, witness_coverage) belong to Story 8.10
- Operational metrics go to Prometheus, NOT the event store
- Constitutional metrics route to governance, not ops

**Developer Golden Rules:**
1. **NO CONSTITUTIONAL METRICS** - Keep operational and constitutional separate (FR52)
2. **PROMETHEUS FORMAT** - Use prometheus_client library standard format
3. **LABELED METRICS** - All metrics have service and environment labels
4. **ASYNC COMPATIBLE** - Metrics middleware must not block async operations

### Source Tree Components to Touch

**Files to Create:**
```
src/infrastructure/monitoring/metrics.py             # Prometheus metrics
src/api/middleware/__init__.py                       # Middleware package
src/api/middleware/metrics_middleware.py             # Request instrumentation
src/api/routes/metrics.py                           # /v1/metrics endpoint
src/application/services/health_service.py           # Health check service
tests/unit/infrastructure/test_metrics.py
tests/unit/api/test_metrics_middleware.py
tests/unit/application/test_health_service.py
tests/integration/test_metrics_collection_integration.py
tests/integration/test_health_ready_integration.py
```

**Files to Modify:**
```
src/infrastructure/monitoring/__init__.py            # Export metrics
src/api/routes/health.py                            # Add /ready, enhance /health
src/api/models/health.py                            # Add response models
src/api/main.py                                     # Register middleware and routes
src/application/services/__init__.py                # Export health_service
pyproject.toml                                      # Add prometheus_client dependency
```

### Related Existing Code (MUST Review)

**Existing Health Endpoint (Basic):**
- `src/api/routes/health.py:10-17` - Simple health check, needs enhancement
- `src/api/models/health.py` - Basic HealthResponse model

**External Monitor (Reference Pattern):**
- `src/infrastructure/monitoring/external_monitor.py` - AlertSeverity enum, MonitoringConfig pattern
- Uses structlog for logging (reuse pattern)
- httpx for async HTTP (consistent with project)

**API Middleware Patterns:**
- Check `src/api/middleware/` if exists for patterns
- FastAPI middleware registration in `src/api/main.py`

### Design Decisions

**Why prometheus_client Library:**
1. Industry standard for Python Prometheus metrics
2. Built-in exposition format generation
3. Thread-safe metric updates
4. Histogram buckets out of the box

**Metric Naming Convention:**
```
# Counters end in _total
http_requests_total{method="GET", endpoint="/v1/health", status="200"}
http_requests_failed_total{method="POST", endpoint="/v1/events", status="500"}

# Gauges describe current value
uptime_seconds{service="api"}

# Histograms end in _seconds for timing
http_request_duration_seconds_bucket{le="0.1", endpoint="/v1/health"}
http_request_duration_seconds_sum{endpoint="/v1/health"}
http_request_duration_seconds_count{endpoint="/v1/health"}
```

**Readiness vs Liveness:**
```
/health (liveness):
  - Is the process responding?
  - Fast check, no external calls
  - 200 = alive, 503 = restart needed

/ready (readiness):
  - Can the service handle traffic?
  - Checks: DB, Redis, event store connectivity
  - 200 = ready, 503 = not accepting traffic
```

**Excluded Metrics (FR52 Separation):**
These belong to Story 8.10 Constitutional Health, NOT this story:
- `constitutional_breach_count`
- `halt_state`
- `dissent_health_ratio`
- `witness_coverage_percent`
- `override_frequency`

### Testing Standards Summary

- **Unit Tests Location**: `tests/unit/infrastructure/`, `tests/unit/api/`, `tests/unit/application/`
- **Integration Tests Location**: `tests/integration/`
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Mock Prometheus registry for isolation, mock dependencies for health checks
- **Coverage**: All metric types (counter, gauge, histogram) tested

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Infrastructure layer: `src/infrastructure/monitoring/metrics.py`
- API middleware: `src/api/middleware/`
- API routes: `src/api/routes/`
- Application services: `src/application/services/health_service.py`

**Import Rules:**
- `metrics.py` is infrastructure, no domain imports needed
- `health_service.py` is application, imports only from domain
- Middleware imports from infrastructure metrics

### Previous Story Intelligence (7-10)

**Learnings from Story 7-10:**
1. **Registry pattern works well** - IntegrityGuarantee registry pattern
2. **Stub implementations first** - Create stubs for testing
3. **Export from __init__.py** - Maintain clean exports
4. **19 integration tests standard** - Comprehensive coverage

**Key patterns established:**
- All async methods use `pytest.mark.asyncio`
- structlog for all logging
- Pydantic v2 for all API models

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit patterns:**
- Feature commits use `feat(story-X.Y):` prefix
- Include FR/NFR reference in commit message
- Co-Authored-By footer for AI assistance

### Dependencies to Add

```toml
# pyproject.toml
[project.dependencies]
prometheus_client = ">=0.19.0"
```

### Edge Cases to Test

1. **Metrics endpoint under load**: Should not block
2. **Database down**: Ready check returns 503, health returns 200
3. **Redis down**: Ready check returns 503, health returns 200
4. **Event store connectivity lost**: Ready check reflects
5. **Histogram bucket overflow**: Very slow requests handled
6. **Counter overflow**: Long-running service handling
7. **Concurrent scrapes**: Thread-safe metric access

### Environment Variables (Optional)

```bash
# For labeling metrics
SERVICE_NAME=archon72-api
ENVIRONMENT=production  # or development, staging
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.1] - Story requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR27] - Observability requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-010] - Constitutional health separation
- [Source: src/infrastructure/monitoring/external_monitor.py] - Existing monitoring patterns
- [Source: src/api/routes/health.py] - Existing health endpoint
- [Source: _bmad-output/project-context.md] - Project rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- Implemented Prometheus metrics using prometheus-client library (Task 1)
- Created MetricsCollector singleton with uptime gauge, service starts counter, request duration histogram, and request counters
- Added MetricsMiddleware for automatic request instrumentation (Task 2)
- Created /v1/metrics endpoint returning Prometheus exposition format (Task 3)
- Enhanced /v1/health and added /v1/ready endpoints with dependency checks (Task 4)
- Integrated startup recording in lifespan context manager (Task 5)
- 56 unit tests pass (15 metrics + 24 middleware + 17 health service) (Task 6)
- 34 integration tests pass covering all acceptance criteria (Task 7)
- Total: 90 tests passing
- FR52 compliance verified: NO constitutional metrics exposed
- NOTE: HealthService uses stub checkers by default. Call `configure_health_service()` at startup with real `DatabaseChecker`, `RedisChecker`, `EventStoreChecker` to enable real dependency checks. This is intentional for MVP - real DI configuration should be added in production deployment setup.

### File List

**Created:**
- src/infrastructure/monitoring/metrics.py - Prometheus metrics infrastructure
- src/api/middleware/__init__.py - Middleware package
- src/api/middleware/metrics_middleware.py - Request instrumentation
- src/api/routes/metrics.py - /v1/metrics endpoint
- src/application/services/health_service.py - Health check service
- tests/unit/infrastructure/test_metrics.py - 15 unit tests
- tests/unit/api/test_metrics_middleware.py - 24 unit tests (10 middleware + 14 error classifier)
- tests/unit/application/test_health_service.py - 17 unit tests
- tests/integration/test_metrics_collection_integration.py - 16 integration tests
- tests/integration/test_health_ready_integration.py - 18 integration tests

**Modified:**
- pyproject.toml - Added prometheus-client dependency
- src/infrastructure/monitoring/__init__.py - Exported metrics
- src/api/models/health.py - Added HealthResponse, DependencyCheck, ReadyResponse
- src/api/routes/health.py - Enhanced with /ready endpoint
- src/api/routes/__init__.py - Exported metrics router
- src/api/main.py - Registered middleware and metrics router
- src/api/startup.py - Added record_service_startup function
- src/application/services/__init__.py - Exported HealthService

## Change Log

- 2026-01-08: Story created via create-story workflow with comprehensive context
- 2026-01-09: All 7 tasks completed, 90 tests pass (56 unit + 34 integration), status -> review
- 2026-01-09: Code review completed - Fixed H1 (test count docs), M1 (exports), M3 (stub docs). All ACs verified. Status -> done
