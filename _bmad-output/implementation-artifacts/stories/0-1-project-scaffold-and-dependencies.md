# Story 0.1: Project Scaffold & Dependencies

Status: ready-for-dev

## Story

As a **developer**,
I want a properly configured Python 3.11+ project with all required dependencies,
so that I can build constitutional features on a solid foundation.

## Acceptance Criteria

1. **AC1: Poetry Configuration**
   - `pyproject.toml` exists with Python 3.11+ requirement
   - Project metadata complete (name, version, description, authors)
   - Poetry lock file generated

2. **AC2: Core Dependencies Installed**
   - FastAPI 0.100+
   - CrewAI (latest stable)
   - supabase-py
   - redis-py
   - SQLAlchemy 2.0+ (with async extras)
   - Pydantic v2

3. **AC3: Infrastructure Dependencies**
   - structlog (structured logging)
   - cryptography (HSM signing)
   - httpx (async HTTP client)
   - alembic (migrations)

4. **AC4: Development Dependencies**
   - pytest with pytest-asyncio
   - hypothesis (property-based testing)
   - ruff (linting)
   - mypy (type checking with --strict)
   - black (formatting)
   - coverage (80% minimum)

5. **AC5: Smoke Test Passes**
   - `tests/unit/test_smoke.py` exists
   - Running `poetry install && poetry run pytest tests/unit/test_smoke.py` passes
   - Test verifies all critical imports work

## Tasks / Subtasks

- [ ] Task 1: Create pyproject.toml with Poetry (AC: 1, 2, 3, 4)
  - [ ] 1.1 Set Python version constraint to >=3.11
  - [ ] 1.2 Add core dependencies with version constraints
  - [ ] 1.3 Add dev dependencies group
  - [ ] 1.4 Configure tool settings (ruff, mypy, pytest)

- [ ] Task 2: Create minimal project structure (AC: 5)
  - [ ] 2.1 Create `src/__init__.py` with version constant
  - [ ] 2.2 Create `tests/__init__.py`
  - [ ] 2.3 Create `tests/conftest.py` with pytest configuration

- [ ] Task 3: Create smoke test (AC: 5)
  - [ ] 3.1 Create `tests/unit/__init__.py`
  - [ ] 3.2 Create `tests/unit/test_smoke.py` testing all imports
  - [ ] 3.3 Add async import verification
  - [ ] 3.4 Add version check assertion

- [ ] Task 4: Verify installation (AC: 1, 2, 3, 4, 5)
  - [ ] 4.1 Run `poetry install`
  - [ ] 4.2 Verify `poetry run python --version` shows 3.11+
  - [ ] 4.3 Run `poetry run pytest tests/unit/test_smoke.py`
  - [ ] 4.4 Verify all imports succeed

## Dev Notes

### Architecture Patterns

**Hexagonal Architecture Foundation:**
- This story creates the base for `src/domain/`, `src/application/`, `src/infrastructure/`, `src/api/` layers (Story 0.2)
- Use absolute imports from `src/` namespace

**Constitutional Constraints (CT-11, CT-14):**
- Keep dependencies minimal (complexity budget)
- Every dependency must be justified for constitutional requirements

### Technology Stack (From architecture.md)

| Dependency | Version | Constitutional Justification |
|------------|---------|------------------------------|
| FastAPI | 0.100+ | Async-first API, Pydantic v2 integration |
| CrewAI | latest | 72-agent orchestration (ADR-2) |
| SQLAlchemy | 2.0+ | Async mode required (CT-1 stateless reconstruction) |
| Pydantic | v2 | API models, context bundle validation |
| supabase-py | latest | Event store backend (ADR-1) |
| redis-py | latest | Dual-channel halt transport (ADR-3) |
| structlog | latest | Constitutional witnessing through structured logs |
| cryptography | latest | HSM signing, hash-chaining (ADR-4) |
| hypothesis | latest | Property-based testing for constitutional invariants |

### Source Tree Components

```
archon72/
├── pyproject.toml          # Poetry configuration (this story)
├── poetry.lock             # Generated lock file
├── src/
│   └── __init__.py         # Package with __version__
└── tests/
    ├── __init__.py
    ├── conftest.py         # Pytest configuration
    └── unit/
        ├── __init__.py
        └── test_smoke.py   # Dependency smoke test
```

### Testing Standards

- All tests use `pytest.mark.asyncio` when testing async
- Use `AsyncMock` for async function mocking
- Smoke test must verify:
  - All core imports work
  - Version constant is accessible
  - Async functionality available

### Project Structure Notes

- This story creates the minimal scaffold
- Story 0.2 adds the full hexagonal layer structure
- No circular import risk at this stage (flat structure)

### References

- [Source: _bmad-output/project-context.md#Technology Stack & Versions]
- [Source: _bmad-output/planning-artifacts/architecture.md#Technology Stack]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 0.1]
- [Source: docs/a/a-2.2.md#ADR-001 Event Store Implementation]
- [Source: docs/a/a-2.1.md#Complexity Budget]

## Dev Agent Record

### Agent Model Used

(To be filled by dev agent)

### Debug Log References

(To be filled during implementation)

### Completion Notes List

(To be filled on completion)

### File List

(To be filled on completion - list all files created/modified)
