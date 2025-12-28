---
project_name: 'Archon 72 Conclave Backend'
date: '2025-12-27'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'security_rules', 'anti_patterns']
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

| Technology | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | Async/await required |
| FastAPI | latest | Async-first API |
| CrewAI | latest | Multi-agent orchestration |
| PostgreSQL | 16 | Via Supabase |
| SQLAlchemy | 2.0 | Async mode only |
| Pydantic | v2 | All API models |
| Redis | latest | Locks + events |
| structlog | latest | Structured logging |
| Alembic | latest | Migrations |
| pytest | latest | With pytest-asyncio |

**Version Constraints:**
- Python 3.11+ required for TaskGroup
- SQLAlchemy 2.0 for async support
- Pydantic v2 for FastAPI integration

---

## Critical Implementation Rules

### Language-Specific Rules (Python)

**Async/Await (CRITICAL):**
- ALL I/O operations MUST use async/await
- NEVER use blocking calls (requests, sync DB, time.sleep)
- Use `asyncio.TaskGroup` for concurrent operations
- Use `asyncio.to_thread()` for unavoidable blocking calls

**Type Hints (REQUIRED):**
- ALL function signatures MUST have type hints
- Use `Optional[T]` not `T | None` for clarity
- Use `UUID` from uuid module, not strings
- Return types required on all functions

**Imports:**
- Standard library first, then third-party, then local
- Use absolute imports from src/
- Never use wildcard imports (`from x import *`)

**Error Handling:**
- All domain exceptions inherit from `ConclaveError`
- Never catch bare `Exception` unless re-raising
- Always include context in exception messages
- Use specific exception types (QuorumNotMetError, not ValueError)

---

### Framework-Specific Rules (FastAPI)

**API Endpoints:**
- URL paths: snake_case, plural nouns (`/v1/meetings`)
- Path params: `{meeting_id}` not `:id`
- Query params: snake_case (`?archon_id=5`)
- Version prefix required (`/v1/`)

**Request/Response:**
- ALL bodies use Pydantic models (never raw dicts)
- Responses return Pydantic models directly
- Use `response_model=` parameter on routes
- Datetime as ISO 8601 UTC (`2025-12-27T10:30:00Z`)

**Error Responses (RFC 7807):**
```json
{
    "type": "https://archon72.io/errors/quorum-not-met",
    "title": "Quorum Not Met",
    "status": 400,
    "detail": "Meeting requires 49 Archons, only 47 present",
    "instance": "/v1/meetings/abc123/start"
}
```

**Dependency Injection:**
- Use FastAPI `Depends()` for services
- Services injected via `dependencies.py`
- Never instantiate services in route handlers

---

### Testing Rules

**Structure:**
- Unit tests: `tests/unit/{module}/test_{name}.py`
- Integration: `tests/integration/test_{feature}_integration.py`
- Fixtures: `tests/conftest.py`
- Factories: `tests/factories/{model}_factory.py`

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `async def test_*` for async tests
- Use `AsyncMock` not `Mock` for async functions

**Coverage Requirements:**
- Minimum 80% coverage (CI warning below)
- 100% coverage for security/ module
- All public functions must have tests

**Mocking:**
- Use `MockOrchestrator` for agent tests (never real LLM)
- Mock Redis in unit tests
- Integration tests use real DB (test container)

---

### Code Quality & Style Rules

**Naming Conventions:**

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case.py | `meeting_engine.py` |
| Classes | PascalCase | `MeetingEngine` |
| Functions | snake_case | `collect_votes()` |
| Variables | snake_case | `archon_id` |
| Constants | SCREAMING_SNAKE | `MAX_ARCHONS = 72` |
| Private | leading underscore | `_validate_quorum()` |

**Database Naming:**

| Element | Convention | Example |
|---------|------------|---------|
| Tables | snake_case, plural | `meeting_events` |
| Columns | snake_case | `archon_id` |
| Foreign Keys | `{table_singular}_id` | `meeting_id` |
| Indexes | `idx_{table}_{cols}` | `idx_votes_meeting_id` |

**Logging (CRITICAL):**
```python
# CORRECT
log = logger.bind(meeting_id=str(meeting_id))
log.info("meeting_started", archons_present=52)

# WRONG - Never do these
print(f"Meeting started")  # No print
logger.info(f"Started with {count}")  # No f-strings in logs
```

**Linting:**
- ruff for linting (CI failure)
- mypy --strict for type checking (CI failure)
- black for formatting

---

### Security Rules (CRITICAL)

**Patronage Tier Blinding:**
- Tier data in SEPARATE database schema (`patronage_private`)
- NO API path from Conclave services to tier lookup
- Guides, Committees, Archons NEVER see individual tier
- Only billing service has access

**Singleton Mutex:**
- Every Archon instantiation requires lock acquisition
- ALL state mutations require valid fencing token
- Stale tokens rejected at state layer
- Lock TTL: 5 minutes with heartbeat renewal

**Input Boundary:**
- Archons NEVER see raw petition text
- All external input through `input_boundary/` service
- Quarantine → Pattern Block → Summarize → Deliver
- No direct network path from InputBoundary to Conclave DB

**Commit-Reveal Voting:**
- Votes submitted as `hash(vote + nonce)`
- Revealed only after voting deadline
- Missing reveals = abstention
- Public commitment log before deadline

---

### Critical Anti-Patterns (NEVER DO)

**Async Violations:**
```python
# NEVER - Blocking in async
async def bad():
    result = requests.get(url)  # BLOCKING!
    time.sleep(5)  # BLOCKING!

# CORRECT
async def good():
    async with httpx.AsyncClient() as client:
        result = await client.get(url)
    await asyncio.sleep(5)
```

**Logging Violations:**
```python
# NEVER
print("Debug info")
logger.info(f"User {user_id} logged in")
logger.debug("Data: " + str(data))

# CORRECT
log.info("user_login", user_id=str(user_id))
log.debug("data_received", payload=data)
```

**Security Violations:**
```python
# NEVER - Accessing tier data
tier = await db.query(PatronageTier).filter_by(seeker_id=id).first()

# NEVER - Skipping fencing token
await state_service.update(archon_id, new_state)  # No token!

# CORRECT
await state_service.update(archon_id, new_state, fencing_token=lock.token)
```

**Error Handling Violations:**
```python
# NEVER
except Exception:
    pass

# NEVER
raise ValueError("Bad input")  # Use domain exceptions

# CORRECT
except SpecificError as e:
    log.warning("operation_failed", error=str(e))
    raise
```

---

## Quick Reference

**Before Writing Any Code:**
1. Check architecture.md for decisions
2. Use async/await for ALL I/O
3. Add type hints to ALL functions
4. Use Pydantic models for API bodies
5. Log with structlog (no print, no f-strings)
6. Raise domain exceptions (ConclaveError subclasses)
7. Verify security constraints (blinding, mutex, fencing)

**CI Will Fail If:**
- ruff finds linting errors
- mypy --strict finds type errors
- Coverage below 80%
- Blocking calls in async functions

---

_Project context complete. AI agents should read this file before implementing any code._
