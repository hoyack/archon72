---
project_name: 'Archon 72 Conclave Backend'
user_name: 'Grand Architect'
date: '2025-12-28'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'security_rules', 'anti_patterns', 'constitutional_rules', 'architecture_summary']
status: 'complete'
rule_count: 62
optimized_for_llm: true
architecture_complete: true
architecture_date: '2025-12-28'
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

## Constitutional Implementation Rules

**CRITICAL:** This project has post-collapse constitutional constraints.

**Full Rules:** See `docs/constitutional-implementation-rules.md`

**Quick Reference:**

| Forbidden | Use Instead |
|-----------|-------------|
| enforce | verify |
| ensure safety | enable visibility |
| authority | scope |
| binding (as power) | recorded (with consequence) |
| automatic (for decisions) | witnessed, explicit |
| prevent harm | detect, surface |
| safeguard | expose |

**No Silent Paths:** Every decision must be witnessed and logged with attribution.

**CI Enforcement:** `scripts/constitutional_lint.py` fails build on violations.

---

## Architecture Summary (From Validated Architecture)

**Full Document:** `_bmad-output/planning-artifacts/architecture.md` (~5,400 lines)

### Constitutional Truths (Must Honor)

| ID | Truth | Implication |
|----|-------|-------------|
| **CT-11** | Silent failure destroys legitimacy | HALT OVER DEGRADE |
| **CT-12** | Witnessing creates accountability | Unwitnessed actions are invalid |
| **CT-13** | Integrity outranks availability | Availability may be sacrificed |
| **CT-6** | Cryptography depends on key custody | Key compromise is existential |

### Developer Golden Rules (MEMORIZE)

1. **HALT FIRST** - Check halt state before every operation
2. **SIGN COMPLETE** - Never sign payload alone, always `signable_content()`
3. **WITNESS EVERYTHING** - Constitutional actions require attribution
4. **FAIL LOUD** - Never catch `SystemHaltedError`

### Critical Code Patterns

**Halt Check Pattern (REQUIRED):**
```python
async def any_operation(self) -> Result:
    # ALWAYS check halt FIRST
    if await self.halt_transport.is_halted():
        raise SystemHaltedError("System halted")

    # Then proceed with operation
    ...
```

**Signature Verification Pattern (REQUIRED):**
```python
async def write_event(self, event: ConstitutionalEvent) -> None:
    # Verify BEFORE any DB interaction
    if not await self._verify_own_signature(event):
        raise SignatureVerificationError("Self-verification failed")

    async with self._db.transaction():
        await self._store.append(event)
```

**Dev Mode Watermark Pattern (REQUIRED):**
```python
class SignableContent:
    def to_bytes(self) -> bytes:
        # Mode MUST be inside signature, not metadata
        mode_prefix = b"[DEV MODE]" if is_dev() else b"[PROD]"
        return mode_prefix + self._content
```

### Key ADR Decisions

| ADR | Decision | File Path |
|-----|----------|-----------|
| **ADR-1** | Supabase + DB-level hash enforcement | `src/infrastructure/event_store/` |
| **ADR-2** | Signed canonical JSON context bundles | `src/domain/context/bundle_signer.py` |
| **ADR-3** | Dual-channel halt (Redis + DB flag) | `src/infrastructure/halt/dual_channel_halt.py` |
| **ADR-4** | Cloud HSM (prod) / Software stub (dev) | `src/infrastructure/hsm/` |
| **ADR-5** | Independent watchdog, multi-path observation | `src/infrastructure/watchdog/` |

### Hexagonal Architecture Layers

```
src/
├── domain/           # Pure business logic, NO infrastructure imports
├── application/      # Use cases, orchestration, ports
├── infrastructure/   # Adapters (Supabase, Redis, HSM)
└── api/              # FastAPI routes, DTOs
```

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`
- `api/` depends on `application/` services

### Alert Severity Levels

| Severity | Response | Example |
|----------|----------|---------|
| **CRITICAL** | Page immediately, halt system | Signature verification failed |
| **HIGH** | Page immediately | Halt signal detected |
| **MEDIUM** | Alert on-call, 15 min response | Watchdog heartbeat missed |
| **LOW** | Next business day | Ceremony quorum warning |
| **INFO** | No alert, log only | Event sequence milestone |

---

## Usage Guidelines

**For AI Agents:**
- Read this file AND `docs/constitutional-implementation-rules.md` before implementing
- Reference `_bmad-output/planning-artifacts/architecture.md` for detailed patterns
- Follow ALL rules exactly as documented
- When in doubt, prefer visibility over automation
- Constitutional lint must pass before any PR
- **HALT FIRST, SIGN COMPLETE, WITNESS EVERYTHING, FAIL LOUD**

**For Humans:**
- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Run `python scripts/constitutional_lint.py` before committing
- Review quarterly for outdated rules

---

_Project context complete. AI agents should read this file before implementing any code._

_Last updated: 2025-12-28 (Architecture workflow complete)_
