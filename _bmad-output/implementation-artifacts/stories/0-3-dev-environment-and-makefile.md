# Story 0.3: Dev Environment & Makefile

Status: done

## Story

As a **developer**,
I want a `make dev` command that starts the local development environment,
So that I can begin development with one command.

## Acceptance Criteria

### AC1: Make Dev Command

**Given** Docker and Docker Compose are installed
**When** I run `make dev`
**Then** the following services start:
  - Local Supabase (PostgreSQL + PostgREST)
  - Redis
  - FastAPI app with hot-reload
**And** the API is accessible at `http://localhost:8000`
**And** health endpoint returns 200 OK

### AC2: Make Stop Command

**Given** the dev environment is running
**When** I run `make stop`
**Then** all containers are stopped gracefully

### AC3: Make DB Reset Command

**Given** I want to reset the database
**When** I run `make db-reset`
**Then** all tables are dropped and migrations re-applied

## Tasks / Subtasks

- [x] Task 1: Create Docker Compose configuration (AC: 1)
  - [x] 1.1 Create `docker-compose.yml` with Supabase local services
  - [x] 1.2 Add Redis service to docker-compose
  - [x] 1.3 Add FastAPI app service with hot-reload (volume mount)
  - [x] 1.4 Configure network for inter-service communication

- [x] Task 2: Create Dockerfile for FastAPI app (AC: 1)
  - [x] 2.1 Create `Dockerfile` with Python 3.12 base
  - [x] 2.2 Install poetry and dependencies
  - [x] 2.3 Configure uvicorn with reload mode for dev

- [x] Task 3: Create minimal FastAPI health endpoint (AC: 1)
  - [x] 3.1 Create `src/api/routes/__init__.py`
  - [x] 3.2 Create `src/api/routes/health.py` with `/health` endpoint
  - [x] 3.3 Create `src/api/main.py` FastAPI app entry point
  - [x] 3.4 Wire health router into main app

- [x] Task 4: Create Makefile with targets (AC: 1, 2, 3)
  - [x] 4.1 Create `Makefile` with `dev` target (docker compose up)
  - [x] 4.2 Add `stop` target (docker compose down)
  - [x] 4.3 Add `db-reset` target (down -v, up, migrate)
  - [x] 4.4 Add `test` target (poetry run pytest)
  - [x] 4.5 Add `lint` target (poetry run ruff check)

- [x] Task 5: Create environment configuration (AC: 1)
  - [x] 5.1 Create `.env.example` with required environment variables
  - [x] 5.2 Add `.env` to `.gitignore` (already exists)
  - [x] 5.3 Document required env vars in README

- [x] Task 6: Verify setup with tests (AC: 1, 2, 3)
  - [x] 6.1 Create `tests/integration/test_health.py` to verify health endpoint
  - [x] 6.2 Run tests and verify health endpoint accessible
  - [x] 6.3 Verify all 32 tests pass
  - [x] 6.4 Verify health endpoint returns 200 OK

## Dev Notes

### Technology Stack (from project-context.md)

| Technology | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ (using 3.12) | Async/await required |
| FastAPI | latest | Async-first API |
| PostgreSQL | 16 | Via Supabase |
| Redis | latest | Locks + events |
| Docker | latest | Container runtime |
| Docker Compose | v2 | Orchestration |

### Supabase Local Development

Use official Supabase local development setup:
- `supabase/postgres:16` for PostgreSQL
- Configure with environment variables
- Default ports: PostgreSQL 54322, API 54321

**Alternative:** Use `supabase start` CLI if available, but Docker Compose provides more control.

### Docker Compose Structure

```yaml
# docker-compose.yml
version: "3.8"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: archon72
    ports:
      - "54322:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
      - ./tests:/app/tests
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/archon72
      - REDIS_URL=redis://redis:6379
      - DEV_MODE=true
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  postgres_data:
```

### Dockerfile Pattern

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (no dev deps in prod, but include for dev)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy source
COPY src/ ./src/
COPY tests/ ./tests/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### FastAPI Health Endpoint Pattern

```python
# src/api/routes/health.py
"""Health check endpoint for Archon 72 API."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return health status.

    Returns:
        Health status with 200 OK.
    """
    return {"status": "healthy"}
```

```python
# src/api/main.py
"""FastAPI application entry point for Archon 72."""

from fastapi import FastAPI

from src.api.routes.health import router as health_router

app = FastAPI(
    title="Archon 72 Conclave API",
    description="Constitutional AI Governance System",
    version="0.1.0",
)

app.include_router(health_router)
```

### Makefile Pattern

```makefile
# Makefile
.PHONY: dev stop db-reset test lint clean

# Start development environment
dev:
	docker compose up --build -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@curl -s http://localhost:8000/health || echo "API not ready yet"

# Stop all services
stop:
	docker compose down

# Reset database (drop volumes, restart)
db-reset:
	docker compose down -v
	docker compose up -d db
	@echo "Waiting for database..."
	@sleep 5
	# Add migration command when available
	docker compose up -d

# Run tests
test:
	poetry run pytest tests/ -v

# Run linting
lint:
	poetry run ruff check src/ tests/
	poetry run mypy src/ --strict

# Clean up
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
```

### Environment Variables

```bash
# .env.example
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/archon72

# Redis
REDIS_URL=redis://localhost:6379

# Development mode
DEV_MODE=true

# API
API_HOST=0.0.0.0
API_PORT=8000
```

### Previous Story Learnings (Story 0.2)

From completed Story 0.2:
- Poetry virtualenv with Python 3.12.12 is configured
- Hexagonal architecture layers exist: domain, application, infrastructure, api
- All layers have `__init__.py` and `README.md`
- Import boundary tests exist in `tests/unit/test_architecture.py`
- 29 tests currently pass (9 architecture + 20 smoke)

**Key Pattern:** Each layer has strict import rules:
- `api/` can only import from `application/`
- New routes go in `src/api/routes/`

### Files NOT to Modify

- `pyproject.toml` (no changes needed unless adding dependencies)
- `src/domain/` (health endpoint is API layer concern)
- Existing `__init__.py` files in layers

### Project Structure After Completion

```
archon72/
├── Dockerfile                # NEW
├── docker-compose.yml        # NEW
├── Makefile                  # NEW
├── .env.example              # NEW
├── src/
│   └── api/
│       ├── __init__.py       # (existing)
│       ├── README.md         # (existing)
│       ├── main.py           # NEW - FastAPI app entry
│       └── routes/
│           ├── __init__.py   # NEW
│           └── health.py     # NEW - Health endpoint
└── tests/
    └── integration/
        └── test_health.py    # NEW
```

### Testing Notes

- Integration tests require running services (`make dev` first)
- Mark integration tests with `@pytest.mark.integration`
- Health endpoint test should use `httpx.AsyncClient`

```python
# tests/integration/test_health.py
"""Integration tests for health endpoint."""

import pytest
from httpx import AsyncClient

from src.api.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    """Test health endpoint returns 200 OK."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
```

### References

- [Source: _bmad-output/project-context.md#Technology Stack]
- [Source: _bmad-output/project-context.md#Framework-Specific Rules (FastAPI)]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 0.3]
- [Source: _bmad-output/implementation-artifacts/stories/0-2-hexagonal-architecture-layers.md#File List]

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 32 tests pass (3 new integration + 29 existing)
- Poetry virtualenv with Python 3.12.12
- Docker Compose v2 format used

### Completion Notes List

1. Created `docker-compose.yml` with PostgreSQL 16, Redis 7, and FastAPI services
2. Configured health checks for all services with proper dependencies
3. Created custom bridge network `archon72-network` for service isolation
4. Created `Dockerfile` with Python 3.12-slim, poetry, and health check
5. Created FastAPI app with health endpoint at `/v1/health`
6. Created `Makefile` with dev, stop, db-reset, test, lint, and clean targets
7. Created `.env.example` with all required environment variables
8. Updated README.md with environment variables and make commands documentation
9. Created integration tests for health endpoint (3 tests)
10. All 32 tests passing - no regressions

**Code Review Fixes Applied:**
- Added `/v1` version prefix to health endpoint (project-context.md compliance)
- Created Pydantic `HealthResponse` model for response (no raw dicts)
- Added `response_model=` parameter to health route
- Renamed test file to `test_health_integration.py` (naming convention)
- Created `.dockerignore` for cleaner Docker builds

### File List

_Files created:_
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `.env.example`
- `.dockerignore`
- `src/api/main.py`
- `src/api/routes/__init__.py`
- `src/api/routes/health.py`
- `src/api/models/__init__.py`
- `src/api/models/health.py`
- `tests/integration/__init__.py`
- `tests/integration/test_health_integration.py`

_Files modified:_
- `README.md` (added environment variables and make commands docs)
