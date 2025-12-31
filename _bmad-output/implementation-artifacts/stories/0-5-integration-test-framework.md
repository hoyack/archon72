# Story 0.5: Integration Test Framework

Status: review

## Story

As a **developer**,
I want an integration test framework with containerized dependencies,
So that I can run integration tests locally with real Supabase and Redis.

## Acceptance Criteria

### AC1: Testcontainers Setup with Docker

**Given** Docker is running
**When** I run `make test-integration`
**Then** testcontainers starts:
  - PostgreSQL container (Supabase-compatible, version 16)
  - Redis container (version 7)
**And** integration tests run against these containers
**And** containers are cleaned up after tests complete

### AC2: Database Session Fixture

**Given** an integration test file in `tests/integration/`
**When** I use the `@pytest.fixture` for `db_session`
**Then** I get a real async database connection to the test container
**And** the database is reset between tests

### AC3: Single Test Execution Speed

**Given** the test framework
**When** I run a single integration test with `pytest tests/integration/test_example.py -v`
**Then** only that test runs with full container setup
**And** execution time is under 30 seconds for container startup

### AC4: Redis Session Fixture

**Given** an integration test file in `tests/integration/`
**When** I use the `@pytest.fixture` for `redis_client`
**Then** I get a real Redis connection to the test container
**And** Redis is flushed between tests

### AC5: Session-Scoped Containers

**Given** multiple integration tests
**When** I run `make test-integration`
**Then** containers are reused across all tests in the session (not started per-test)
**And** only database/Redis state is reset between tests

## Tasks / Subtasks

- [x] Task 1: Add testcontainers dependencies to pyproject.toml (AC: 1, 5)
  - [x] 1.1 Add `testcontainers[postgres,redis]>=4.0.0` to dev dependencies
  - [x] 1.2 Run `poetry lock && poetry install`
  - [x] 1.3 Verify installation with `poetry show testcontainers`

- [x] Task 2: Create container fixtures in conftest.py (AC: 1, 5)
  - [x] 2.1 Create `tests/integration/conftest.py` (separate from unit test conftest)
  - [x] 2.2 Implement `postgres_container` fixture with `@pytest.fixture(scope="session")`
  - [x] 2.3 Implement `redis_container` fixture with `@pytest.fixture(scope="session")`
  - [x] 2.4 Use PostgreSQL 16 image for Supabase compatibility
  - [x] 2.5 Use Redis 7 image to match docker-compose.yml
  - [x] 2.6 Add container cleanup in fixture teardown

- [x] Task 3: Create async database session fixture (AC: 2)
  - [x] 3.1 Create `db_session` fixture using SQLAlchemy async engine
  - [x] 3.2 Connect to postgres_container URL
  - [x] 3.3 Create all tables at session start using SQLAlchemy metadata
  - [x] 3.4 Implement per-test transaction rollback pattern for isolation
  - [x] 3.5 Use `AsyncSession` from sqlalchemy.ext.asyncio

- [x] Task 4: Create Redis client fixture (AC: 4)
  - [x] 4.1 Create `redis_client` fixture using redis-py async client
  - [x] 4.2 Connect to redis_container URL
  - [x] 4.3 Implement `FLUSHDB` between tests for isolation

- [x] Task 5: Add make test-integration target (AC: 1, 3)
  - [x] 5.1 Add `test-integration` target to Makefile
  - [x] 5.2 Use `poetry run pytest tests/integration/ -v -m integration`
  - [x] 5.3 Add `--tb=short` for cleaner output
  - [x] 5.4 Ensure existing `make test` still runs all tests

- [x] Task 6: Create example integration test (AC: 1, 2, 3, 4)
  - [x] 6.1 Create `tests/integration/test_database_integration.py`
  - [x] 6.2 Test database connectivity and basic CRUD
  - [x] 6.3 Verify test isolation (changes in one test don't affect another)
  - [x] 6.4 Measure and document startup time

- [x] Task 7: Update existing integration tests (AC: 2, 4)
  - [x] 7.1 Review `test_health_integration.py` - no container deps needed (uses ASGI)
  - [x] 7.2 Review `test_hsm_integration.py` - no container deps needed (uses temp files)
  - [x] 7.3 Mark tests appropriately with `@pytest.mark.integration`
  - [x] 7.4 Ensure all integration tests pass with `make test-integration`

- [x] Task 8: Add fixture documentation (AC: 2, 4, 5)
  - [x] 8.1 Add docstrings to all fixtures explaining usage
  - [x] 8.2 Add example usage in docstrings
  - [x] 8.3 Document container reuse pattern in `tests/integration/conftest.py` header

## Dev Notes

### Critical Architecture Requirements

**Testcontainers Pattern for Supabase Compatibility:**
```python
# tests/integration/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def postgres_container():
    """Session-scoped PostgreSQL container matching Supabase."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def redis_container():
    """Session-scoped Redis container."""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis
```

**Async Database Session Fixture (CRITICAL):**
```python
@pytest.fixture
async def db_session(postgres_container):
    """Per-test async database session with rollback isolation."""
    url = postgres_container.get_connection_url()
    # Convert sync URL to async
    async_url = url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(async_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()  # Isolation: rollback after each test
```

**Redis Fixture Pattern:**
```python
import redis.asyncio as redis

@pytest.fixture
async def redis_client(redis_container):
    """Per-test Redis client with FLUSHDB isolation."""
    url = redis_container.get_connection_url()
    client = redis.from_url(url)
    yield client
    await client.flushdb()  # Clean up after each test
    await client.aclose()
```

### Makefile Addition

```makefile
# Run integration tests only
test-integration:
	poetry run pytest tests/integration/ -v -m integration --tb=short

# Run all tests (unit + integration)
test-all:
	poetry run pytest tests/ -v --tb=short
```

### pyproject.toml Dependencies

```toml
[tool.poetry.group.dev.dependencies]
# Add to existing dev dependencies:
testcontainers = {version = ">=4.0.0", extras = ["postgres", "redis"]}
```

### Container Startup Time Target

Per AC3, container startup must be under 30 seconds. Testcontainers uses:
- Image caching (first run downloads, subsequent runs reuse)
- Container reuse within session (not per-test)
- Parallel container startup where possible

### Previous Story Learnings (Story 0.4)

From Story 0.4 completion:
- Ed25519 signatures work correctly for HSM operations
- All 71 tests pass in current test suite
- Temporary directories work well for test isolation
- Integration tests can run alongside unit tests with proper markers

### Import Boundary Rules

These fixtures belong in `tests/` - no domain import rules apply, but follow these patterns:
- Fixtures in `tests/integration/conftest.py` (not root conftest)
- Use `@pytest.mark.integration` for all integration tests
- Use `@pytest.mark.asyncio` for async tests (auto mode is enabled)

### Testing Notes

**Container Health Checks:**
```python
# Testcontainers automatically waits for containers to be healthy
# PostgreSQL: checks pg_isready
# Redis: checks redis-cli ping
```

**Test Isolation Patterns:**
1. Session-scoped containers (started once)
2. Function-scoped sessions (fresh connection per test)
3. Transaction rollback (changes don't persist between tests)

### File Structure After Completion

```
tests/
├── conftest.py                          # Root conftest (existing)
├── integration/
│   ├── __init__.py                      # Existing
│   ├── conftest.py                      # NEW: Container fixtures
│   ├── test_health_integration.py       # Existing (no changes needed)
│   ├── test_hsm_integration.py          # Existing (no changes needed)
│   └── test_database_integration.py     # NEW: Example DB test
└── unit/
    └── ...                              # Existing unit tests
```

### Docker Dependency Note

Integration tests require Docker to be running. The Makefile target should check for Docker:
```makefile
test-integration:
	@docker info > /dev/null 2>&1 || (echo "Docker is not running. Please start Docker first." && exit 1)
	poetry run pytest tests/integration/ -v -m integration --tb=short
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 0.5]
- [Source: _bmad-output/project-context.md#Testing Rules]
- [Source: _bmad-output/project-context.md#Technology Stack & Versions]
- [Source: _bmad-output/implementation-artifacts/stories/0-4-software-hsm-stub-with-watermark.md#Dev Agent Record]
- [Source: docker-compose.yml - PostgreSQL 16, Redis 7 versions]
- [Source: pyproject.toml - pytest-asyncio configuration]

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No significant debug issues encountered

### Completion Notes List

- **Task 1**: Added `testcontainers = {version = ">=4.0.0", extras = ["postgres", "redis"]}` to pyproject.toml dev dependencies. Added mypy override for testcontainers module. Ran `poetry lock && poetry install`. Verified installation (v4.13.3).

- **Task 2**: Created `tests/integration/conftest.py` with session-scoped `postgres_container` (postgres:16-alpine) and `redis_container` (redis:7-alpine) fixtures. Containers start once per session and cleanup automatically via context manager.

- **Task 3**: Implemented `db_session` fixture using `async_sessionmaker` from SQLAlchemy. Converts psycopg2 URL to asyncpg URL. Uses per-test transaction with rollback for isolation.

- **Task 4**: Implemented `redis_client` fixture using `redis.asyncio`. Connects to container host/port. Uses FLUSHDB after each test for isolation.

- **Task 5**: Added Makefile targets: `test-integration` (with Docker check), `test-unit`, `test-all`. Updated help text. All targets working correctly.

- **Task 6**: Created `test_database_integration.py` with 8 tests covering connectivity, PostgreSQL 16 version verification, CRUD operations, and test isolation. Created `test_redis_integration.py` with 10 tests covering connectivity, Redis 7 version, operations (GET/SET/HSET/RPUSH/SETEX), and test isolation.

- **Task 7**: Added `@pytest.mark.integration` to all tests in `test_health_integration.py`. HSM tests already had markers. All 31 integration tests pass with `make test-integration`.

- **Task 8**: Added comprehensive docstrings to all fixtures with usage examples. Added module-level documentation explaining container reuse pattern.

### File List

**New Files:**
- `tests/integration/conftest.py` - Container fixtures (postgres, redis, db_session, redis_client)
- `tests/integration/test_database_integration.py` - 8 database integration tests
- `tests/integration/test_redis_integration.py` - 10 Redis integration tests

**Modified Files:**
- `pyproject.toml` - Added testcontainers dependency and mypy override
- `Makefile` - Added test-integration, test-unit, test-all targets
- `tests/integration/test_health_integration.py` - Added @pytest.mark.integration markers
- `tests/integration/test_hsm_integration.py` - Fixed unused variable linting issue
- `poetry.lock` - Updated with testcontainers dependencies

### Change Log

- 2025-12-30: Story 0.5 implementation complete
  - Implemented testcontainers-based integration test framework
  - PostgreSQL 16 and Redis 7 containers with session-scoped reuse
  - Async database session fixture with transaction rollback isolation
  - Redis client fixture with FLUSHDB isolation
  - 18 new container-based tests, all 89 tests passing
  - Container startup time ~3.5 seconds (cached images)
