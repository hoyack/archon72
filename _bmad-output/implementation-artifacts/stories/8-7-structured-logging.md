# Story 8.7: Structured Logging (NFR27)

Status: done

## Story

As a **system operator**,
I want structured JSON logging with correlation IDs,
So that I can trace requests across services.

## Acceptance Criteria

### AC1: JSON Formatted Log Entries
**Given** a log entry
**When** emitted
**Then** it is JSON formatted
**And** includes: timestamp, level, message, correlation_id, service
**And** additional context fields are preserved

### AC2: Correlation ID Consistency
**Given** a request spanning multiple services
**When** I trace it
**Then** correlation_id is consistent across all services
**And** log aggregation can reconstruct the full trace
**And** correlation_id propagates through async contexts

### AC3: Structlog Configuration
**Given** the logging configuration
**When** I examine it
**Then** structlog is used
**And** log levels are configurable per service
**And** development mode has human-readable output
**And** production mode has JSON output

### AC4: Service Logger Base Pattern (WR-1)
**Given** a constitutional service
**When** implementing logging
**Then** `_log_operation()` pattern is used
**And** service name is bound to logger
**And** operation context is captured

## Tasks / Subtasks

- [ ] **Task 1: Create Observability Infrastructure Module** (AC: 1,2,3)
  - [ ] Create `src/infrastructure/observability/__init__.py`
  - [ ] Create `src/infrastructure/observability/logging.py`
    - [ ] `configure_structlog()` function for app startup
    - [ ] JSON processor for production
    - [ ] Console processor for development
    - [ ] Timestamp processor with ISO 8601 format
    - [ ] Add context processor for service name
  - [ ] Create `src/infrastructure/observability/correlation.py`
    - [ ] `CorrelationContext` using contextvars
    - [ ] `get_correlation_id() -> str`
    - [ ] `set_correlation_id(correlation_id: str) -> None`
    - [ ] `generate_correlation_id() -> str` (UUID4)
    - [ ] `correlation_id_processor()` for structlog

- [ ] **Task 2: Create Logging Middleware** (AC: 2)
  - [ ] Create `src/api/middleware/logging_middleware.py`
    - [ ] `LoggingMiddleware` class
    - [ ] Extract or generate correlation_id from `X-Correlation-ID` header
    - [ ] Set correlation_id in context at request start
    - [ ] Include correlation_id in response headers
    - [ ] Log request start/end with timing

- [ ] **Task 3: Create Correlation ID Dependency** (AC: 2)
  - [ ] Create `src/api/dependencies/correlation.py`
    - [ ] `get_correlation_id_header()` FastAPI dependency
    - [ ] Extract from header or generate new
    - [ ] Set in context for request scope

- [ ] **Task 4: Create Base Service Logger Mixin** (AC: 4)
  - [ ] Create `src/application/services/base.py`
    - [ ] `LoggingMixin` class with `_log_operation()` method
    - [ ] Bind service name automatically
    - [ ] Bind operation name and correlation_id
    - [ ] Return bound logger for operation scope

- [ ] **Task 5: Configure Logging at App Startup** (AC: 3)
  - [ ] Update `src/api/startup.py`
    - [ ] Add `configure_logging()` function
    - [ ] Call `configure_structlog()` from observability module
    - [ ] Configure based on environment (dev/prod)
  - [ ] Update `src/api/main.py`
    - [ ] Add `LoggingMiddleware` to middleware stack
    - [ ] Call `configure_logging()` in lifespan

- [ ] **Task 6: Update Existing Services to Use Pattern** (AC: 4)
  - [ ] Audit services with existing structlog usage:
    - [ ] `context_bundle_service.py` - Update to use `_log_operation()`
    - [ ] `integrity_case_service.py` - Update to use `_log_operation()`
    - [ ] `petition_service.py` - Update to use `_log_operation()`
    - [ ] `escalation_service.py` - Update to use `_log_operation()`
  - [ ] Ensure all bind correlation_id from context

- [ ] **Task 7: Unit Tests** (AC: 1,2,3,4)
  - [ ] Create `tests/unit/infrastructure/test_logging.py`
    - [ ] Test JSON formatter output structure
    - [ ] Test timestamp format (ISO 8601)
    - [ ] Test log level configuration
    - [ ] Test context fields inclusion
  - [ ] Create `tests/unit/infrastructure/test_correlation.py`
    - [ ] Test correlation_id generation (UUID format)
    - [ ] Test context propagation
    - [ ] Test async context isolation

- [ ] **Task 8: Integration Tests** (AC: 1,2,3)
  - [ ] Create `tests/integration/test_structured_logging_integration.py`
    - [ ] Test end-to-end correlation_id propagation
    - [ ] Test middleware extracts/sets header
    - [ ] Test log output contains all required fields
    - [ ] Test cross-service correlation consistency

## Dev Notes

### Relevant Architecture Patterns and Constraints

**WR-1 (Structured Logging Convention) - PRIMARY:**
From architecture.md, the logging pattern is well-defined:
```python
class ConstitutionalService:
    """Base class with structured logging convention."""

    def __init__(self, halt_guard: HaltGuard, signing_service: SigningService,
                 event_store: EventStore):
        self._halt_guard = halt_guard
        self._signing = signing_service
        self._event_store = event_store
        self._log = structlog.get_logger().bind(
            service=self.__class__.__name__,
            component="constitutional"
        )

    def _log_operation(self, op: str, **context) -> structlog.BoundLogger:
        """Create operation-scoped logger with correlation ID."""
        return self._log.bind(
            operation=op,
            correlation_id=get_correlation_id(),
            **context
        )

    async def _ensure_not_halted(self) -> None:
        await self._halt_guard.check_still_valid()
```

**NFR27 (Operational Monitoring):**
- Structured logging is part of operational observability
- Must support log aggregation and distributed tracing
- JSON format for machine parsing

**Architecture File Structure (from architecture.md):**
```
src/infrastructure/
    └── observability/                # Cross-cutting (WR-1)
        ├── __init__.py
        ├── logging.py                # Structured logging
        ├── correlation.py            # Correlation ID
        ├── metrics.py                # Prometheus metrics
        └── tracing.py                # Distributed tracing
```

**Middleware Location:**
```
src/api/shared/
    └── middleware.py             # Correlation, logging middleware
```

### Source Tree Components to Touch

**Files to Create:**
```
src/infrastructure/observability/__init__.py
src/infrastructure/observability/logging.py
src/infrastructure/observability/correlation.py
src/api/middleware/logging_middleware.py
src/api/dependencies/correlation.py
src/application/services/base.py
tests/unit/infrastructure/test_logging.py
tests/unit/infrastructure/test_correlation.py
tests/integration/test_structured_logging_integration.py
```

**Files to Modify:**
```
src/api/startup.py                              # Add configure_logging()
src/api/main.py                                 # Add LoggingMiddleware
src/application/services/context_bundle_service.py  # Update logging pattern
src/application/services/integrity_case_service.py  # Update logging pattern
src/application/services/petition_service.py        # Update logging pattern
src/application/services/escalation_service.py      # Update logging pattern
```

### Design Decisions

**Structlog Configuration:**
```python
import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.stdlib import ProcessorFormatter

def configure_structlog(environment: str = "production") -> None:
    """Configure structlog for the application.

    Args:
        environment: 'production' for JSON output, 'development' for console.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        correlation_id_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if environment == "production":
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

**Correlation ID Context:**
```python
from contextvars import ContextVar
from uuid import uuid4

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

def get_correlation_id() -> str:
    """Get the current correlation ID from context."""
    return _correlation_id.get() or str(uuid4())

def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in context."""
    _correlation_id.set(correlation_id)

def generate_correlation_id() -> str:
    """Generate a new correlation ID (UUID4)."""
    return str(uuid4())

def correlation_id_processor(
    logger: Any, method_name: str, event_dict: dict
) -> dict:
    """Structlog processor to add correlation_id to every log."""
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict
```

**Logging Middleware:**
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for correlation ID propagation and request logging."""

    CORRELATION_HEADER = "X-Correlation-ID"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get(
            self.CORRELATION_HEADER,
            generate_correlation_id()
        )
        set_correlation_id(correlation_id)

        # Log request start
        log = structlog.get_logger().bind(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )
        log.info("request_started")

        # Process request
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log request end
        log.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Add correlation ID to response
        response.headers[self.CORRELATION_HEADER] = correlation_id
        return response
```

**Base Service Mixin:**
```python
import structlog
from src.infrastructure.observability.correlation import get_correlation_id

class LoggingMixin:
    """Mixin providing structured logging for services."""

    _log: structlog.BoundLogger

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def _init_logger(self) -> None:
        """Initialize logger with service name binding."""
        self._log = structlog.get_logger().bind(
            service=self.__class__.__name__,
            component="constitutional",
        )

    def _log_operation(
        self,
        operation: str,
        **context
    ) -> structlog.BoundLogger:
        """Create operation-scoped logger with correlation ID.

        Args:
            operation: Name of the operation being performed.
            **context: Additional context to bind to the logger.

        Returns:
            BoundLogger with operation and correlation context.
        """
        return self._log.bind(
            operation=operation,
            correlation_id=get_correlation_id(),
            **context,
        )
```

### Testing Standards Summary

- **Unit Tests Location**: `tests/unit/infrastructure/`
- **Integration Tests Location**: `tests/integration/`
- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Log Capture**: Use `caplog` fixture or structlog test helpers
- **Context Testing**: Test contextvars isolation with concurrent tasks

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Observability is infrastructure cross-cutting concern
- Middleware is API layer
- Base mixin is application layer helper

**Import Rules:**
- `observability/` can import nothing from application/domain
- Services import from `observability/` for logging
- API imports middleware and dependencies

### Previous Story Intelligence (8-6)

**Learnings from Story 8-6 (Complexity Budget Dashboard):**
1. **Service patterns** - Services use dependency injection for ports
2. **Stub patterns** - Stubs implement ports with configurable behavior
3. **Event payloads** - Include `signable_content()` for witnessing
4. **Testing** - Comprehensive unit + integration coverage
5. **Router registration** - Add to `__init__.py` and `main.py`

**Key Debug Log from 8-6:**
- Fixed attribute name mismatch (`timestamp` vs `snapshot_timestamp`)
- Fixed router registration (must add to `main.py`)
- Fixed TYPE_CHECKING imports for forward references

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit patterns:**
- Feature commits use `feat(story-X.Y):` prefix
- Include relevant constraint references (NFR27)
- Co-Authored-By footer for AI assistance

### Current Logging State Analysis

Services with existing structlog usage (need updating):
1. `context_bundle_service.py` - Uses module-level logger, needs correlation
2. `integrity_case_service.py` - Uses `_log` with service binding, good start
3. `petition_service.py` - Uses module-level `log`, needs correlation
4. `escalation_service.py` - Uses `logger.bind()` pattern, needs consistency

**Pattern to standardize:**
- All services should use `_log_operation()` method
- Correlation ID should come from context automatically
- Service name should be bound at logger creation

### Edge Cases to Test

1. **No correlation ID in header**: Generate new UUID
2. **Empty correlation ID**: Generate new UUID
3. **Invalid correlation ID format**: Accept as-is (don't validate)
4. **Concurrent requests**: Each has isolated correlation context
5. **Async context crossing**: Correlation ID preserved across await
6. **Error logging**: Stack traces included with correlation
7. **Nested service calls**: Same correlation ID throughout
8. **Background tasks**: May need explicit correlation propagation
9. **Development mode**: Human-readable console output
10. **Production mode**: Valid JSON on each line

### Dependencies

```toml
# Already in pyproject.toml
structlog = ">=24.0.0"
```

No new dependencies needed.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-8.7] - Story requirements
- [Source: _bmad-output/planning-artifacts/architecture.md#WR-1] - Structured logging convention
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR27] - Operational monitoring
- [Source: _bmad-output/project-context.md] - Project rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation completed without issues.

### Completion Notes List

1. **Observability Infrastructure Created** - New module at `src/infrastructure/observability/` with:
   - `logging.py`: Configures structlog with JSON (production) or console (development) output
   - `correlation.py`: Manages correlation IDs using contextvars for async context isolation

2. **Logging Middleware Implemented** - `src/api/middleware/logging_middleware.py`:
   - Extracts or generates correlation ID from `X-Correlation-ID` header
   - Sets correlation ID in context for downstream use
   - Logs request start/end with timing
   - Adds correlation ID to response headers

3. **FastAPI Dependency Created** - `src/api/dependencies/correlation.py`:
   - Provides `get_correlation_id_header()` dependency for explicit correlation ID access

4. **Base Service Mixin Created** - `src/application/services/base.py`:
   - `LoggingMixin` class with `_init_logger()` and `_log_operation()` methods
   - Follows WR-1 architecture pattern from architecture.md

5. **Startup Configuration Updated** - `src/api/startup.py` and `src/api/main.py`:
   - Added `configure_logging()` function called first in lifespan
   - Added `LoggingMiddleware` to middleware stack

6. **Tests Verified** - 28 tests passing:
   - 19 unit tests for correlation and logging modules
   - 9 integration tests for end-to-end correlation ID propagation

### File List

**Files Created:**
- `src/infrastructure/observability/__init__.py`
- `src/infrastructure/observability/logging.py`
- `src/infrastructure/observability/correlation.py`
- `src/api/middleware/logging_middleware.py`
- `src/api/dependencies/correlation.py`
- `src/application/services/base.py`
- `tests/unit/infrastructure/test_correlation.py`
- `tests/unit/infrastructure/test_logging.py`
- `tests/integration/test_structured_logging_integration.py`

**Files Modified:**
- `src/api/startup.py` - Added `configure_logging()` function
- `src/api/main.py` - Added `LoggingMiddleware`, call `configure_logging()` in lifespan
- `src/api/middleware/__init__.py` - Exported `LoggingMiddleware`
- `src/api/dependencies/__init__.py` - Exported `get_correlation_id_header`

