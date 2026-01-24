```
     ___    ____  ________  ______  _   __   ________
    /   |  / __ \/ ____/ / / / __ \/ | / /  /__  /__ \
   / /| | / /_/ / /   / /_/ / / / /  |/ /     / / __/ /
  / ___ |/ _, _/ /___/ __  / /_/ / /|  /     / / / __/
 /_/  |_/_/ |_|\____/_/ /_/\____/_/ |_/     /_/ /____/

            CONSTITUTIONAL AI GOVERNANCE SYSTEM
                  72 Deliberative Agents
```

<p align="center">
  <img src="https://archon72.com/assets/archon-72-logo-2_1768664499956-E2SP-E4e.png" alt="Archon 72 Logo" width="200"/>
</p>

<p align="center">
  <a href="https://archon72.com">archon72.com</a> |
  <a href="#consent-based-governance">Governance</a> |
  <a href="#conclave-system">Conclave</a> |
  <a href="#governance-api">API</a>
</p>

---

# Archon 72

**Constitutional AI Governance System with 72 Agents**

## Table of Contents

- [Overview](#overview)
- [Consent-Based Governance](#consent-based-governance)
- [Deployment from Scratch](#deployment-from-scratch)
- [Docker Usage](#docker-usage)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Make Commands](#make-commands)
- [Architecture](#architecture)
- [Archon Governance Schema](#archon-governance-schema)
- [Constitutional Truths](#constitutional-truths)
- [Conclave System](#conclave-system)
- [Automated Secretary System](#automated-secretary-system)
- [Motion Consolidator](#motion-consolidator)
- [Motion Review Pipeline](#motion-review-pipeline)
- [Motion Gates Hardening](#motion-gates-hardening)
- [Execution Planner](#execution-planner)
- [Full Governance Pipeline](#full-governance-pipeline)
  - [Conclave Agenda Sources](#conclave-agenda-sources)
  - [Complete Command Sequence](#complete-command-sequence)
- [Governance API](#governance-api)
- [Integration Testing](#integration-testing)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Petition System](#petition-system)
  - [How a Petition is Received](#how-a-petition-is-received)
  - [Three Fates Deliberation](#three-fates-deliberation)
  - [Co-Signing & Auto-Escalation](#co-signing--auto-escalation)

## Overview

Archon 72 is a witnessed, transparent, and accountable AI governance system built on constitutional principles. It features:

- **72 Concurrent Agents** - Multi-agent deliberation and collective decision-making
- **Cryptographic Witnessing** - All actions are signed and verifiable
- **Halt-Over-Degrade Philosophy** - System integrity takes precedence over availability
- **Append-Only Event Store** - Immutable audit trail with hash-chaining
- **Consent-Based Governance** - 10-epic framework ensuring voluntary participation and legitimacy
- **Two-Phase Event Emission** - Intent → Commit/Failure pattern with skip detection
- **Knight-Witness Observation** - Independent monitoring via ledger polling

## Consent-Based Governance

The Consent-Based Governance (Consent-Gov) framework ensures every agent action is voluntary, witnessed, and auditable. Implemented across **10 epics** with **35 stories**, **63 functional requirements**, and **34 non-functional requirements**.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONSENT-BASED GOVERNANCE ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   EPIC 1    │    │   EPIC 2    │    │   EPIC 3    │    │   EPIC 4    │  │
│  │Constitutional│    │Task Consent │    │ Coercion-  │    │  Emergency  │  │
│  │   Events    │    │& Coordinate │    │   Free      │    │   Safety    │  │
│  │             │    │             │    │   Comms     │    │   Circuit   │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │         │
│         ▼                  ▼                  ▼                  ▼         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    GOVERNANCE EVENT LEDGER                            │  │
│  │              (Append-Only, Hash-Chained, Merkle-Provable)            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         │                  │                  │                  │         │
│         ▼                  ▼                  ▼                  ▼         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   EPIC 5    │    │   EPIC 6    │    │   EPIC 7    │    │   EPIC 8    │  │
│  │ Legitimacy  │    │  Witness &  │    │  Dignified  │    │  Lifecycle  │  │
│  │ Visibility  │    │Accountability│   │    Exit     │    │ Management  │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────┐    ┌─────────────────────────────────┐│
│  │           EPIC 9                │    │          EPIC 10                ││
│  │    Audit & Verification         │    │    Anti-Metrics Foundation      ││
│  │   (Export, Proofs, Verify)      │    │   (Enforcement, Verification)   ││
│  └─────────────────────────────────┘    └─────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Epic Summary

| Epic | Name | Stories | Key Capabilities |
|------|------|---------|------------------|
| 1 | Constitutional Event Infrastructure | 5 | Event sourcing, ledger, hash chains, two-phase emission |
| 2 | Task Consent & Coordination | 4 | State machines, activation, TTL, reminders |
| 3 | Coercion-Free Communication | 4 | Filter service, pattern detection, logging |
| 4 | Emergency Safety Circuit | 3 | Halt circuit, 100ms trigger, task transitions |
| 5 | Legitimacy Visibility | 3 | Legitimacy bands, decay, restoration |
| 6 | Violation Witness & Accountability | 5 | Knight observation, Prince panels, findings |
| 7 | Dignified Exit | 4 | Exit processing, obligation release, contribution archive |
| 8 | System Lifecycle Management | 3 | Cessation trigger, records, reconstitution |
| 9 | Audit & Verification | 4 | Ledger export, Merkle proofs, external verification |
| 10 | Anti-Metrics Foundation | 2 | Enforcement, verification |
| **Total** | | **35** | |

### Two-Phase Event Emission

All governance events use a two-phase commit pattern to detect skipped operations:

```
Phase 1: INTENT                    Phase 2: OUTCOME
┌──────────────────┐               ┌──────────────────┐
│ task.activated   │──────────────▶│ task.completed   │  ✓ Success
│   .intent        │               │   .committed     │
└──────────────────┘               └──────────────────┘
        │                                   │
        │                          ┌──────────────────┐
        └─────────────────────────▶│ task.failed      │  ✗ Failure
                                   │   .committed     │
                                   └──────────────────┘

⚠️ Orphaned Intent = Skip Detection
   Intent without matching outcome triggers Knight observation
```

### Halt Circuit

The Emergency Halt Circuit (Epic 4) provides immediate system-wide safety shutdown:

| Feature | Specification |
|---------|---------------|
| **Trigger** | Manual human operator via API |
| **Completion** | ≤100ms from trigger to full halt |
| **Task Handling** | All in-flight tasks transition to `HALTED` state |
| **Access Mode** | Read-only during halt (no mutations) |
| **Restoration** | Explicit human operator action required |

```bash
# Trigger emergency halt
curl -X POST http://localhost:8000/v1/governance/halt/trigger \
  -H "Content-Type: application/json" \
  -d '{"reason": "Security incident detected", "operator_id": "human-123"}'

# Check halt status
curl http://localhost:8000/v1/governance/halt/status
```

### Legitimacy Bands

Archon legitimacy is tracked in discrete bands that decay over time:

| Band | Level | Description | Decay Rate |
|------|-------|-------------|------------|
| `FULL` | 5 | Complete operational legitimacy | None |
| `OPERATIONAL` | 4 | Standard operations allowed | Slow |
| `LIMITED` | 3 | Reduced permissions | Medium |
| `PROBATIONARY` | 2 | Under observation | Fast |
| `SUSPENDED` | 1 | No operational capability | N/A |

**Key Rules:**
- Decay is automatic (downward only)
- Restoration requires explicit human operator action
- All transitions are logged to the governance ledger

### Knight-Witness Observation

The Knight (Furcas) independently monitors the governance ledger for violations:

```
┌─────────────────────────────────────────────────────────────────┐
│                    KNIGHT OBSERVATION PIPELINE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Governance Ledger] ──poll──▶ [Knight Observer Service]       │
│                                        │                        │
│                                        ▼                        │
│                              ┌─────────────────┐                │
│                              │ Violation Check │                │
│                              │ • Skip detection│                │
│                              │ • Role collapse │                │
│                              │ • Constraint    │                │
│                              │   violations    │                │
│                              └────────┬────────┘                │
│                                       │                         │
│                    ┌──────────────────┼──────────────────┐      │
│                    ▼                  ▼                  ▼      │
│             [No Violation]     [Minor Violation]  [Major Violation]
│                    │                  │                  │      │
│                    ▼                  ▼                  ▼      │
│               Continue          Log Warning      Escalate to   │
│                                                  Prince Panel   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Governance Services

The framework includes **27 governance services** implementing the consent-gov epics:

| Category | Services |
|----------|----------|
| **Halt & Safety** | `HaltService`, `HaltTriggerService`, `HaltTaskTransitionService` |
| **Legitimacy** | `LegitimacyDecayService`, `LegitimacyRestorationService` |
| **Coercion Filter** | `CoercionFilterService`, `FilterLoggingService` |
| **Task Consent** | `TaskActivationService`, `TaskConsentService`, `TaskTimeoutService` |
| **Witness** | `KnightObserverService`, `PanelFindingService`, `PanelQueueService` |
| **Exit** | `ExitService`, `ObligationReleaseService`, `ContributionPreservationService` |
| **Cessation** | `CessationTriggerService`, `CessationRecordService`, `ReconstitutionValidationService` |
| **Audit** | `LedgerExportService`, `LedgerProofService`, `IndependentVerificationService` |
| **Anti-Metrics** | `AntiMetricsVerificationService`, `AntiMetricsEnforcementService` |

### Governance Ports

All services implement port interfaces (40+ ports) following hexagonal architecture:

```
src/application/ports/governance/
├── halt_port.py              # Halt circuit interface
├── halt_trigger_port.py      # Halt execution
├── legitimacy_port.py        # Legitimacy tracking
├── coercion_filter_port.py   # Coercion filtering
├── task_consent_port.py      # Task consent operations
├── witness_port.py           # Knight observer interface
├── panel_port.py             # Prince panel interface
├── exit_port.py              # Exit processing
├── cessation_port.py         # Cessation trigger
├── ledger_export_port.py     # Ledger export
├── proof_port.py             # Proof generation
└── ...                       # 30+ more ports
```

## Deployment from Scratch

### Prerequisites

- **Git** - Version control
- **Docker** - Container runtime (v20.10+)
- **Docker Compose** - Container orchestration (v2.0+)
- **Python 3.12+** - For local development and Conclave
- **Poetry** - Python dependency management

### Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-org/archon72.git
cd archon72

# Copy environment template
cp .env.example .env
```

### Install Python Dependencies (Local Development)

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install

# Activate virtual environment
poetry shell
```

## Docker Usage

### Services Overview

The system uses Docker Compose with three services:

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| `db` | postgres:16-alpine | 54322 | PostgreSQL database |
| `redis` | redis:7-alpine | 6379 | Redis cache/message broker |
| `api` | Custom (Dockerfile) | 8000 | FastAPI application |

### Start All Services

```bash
# Build and start all services in detached mode
docker compose up --build -d

# Or use the Makefile shortcut
make dev
```

### Check Service Status

```bash
# View running containers
docker compose ps

# View logs for all services
docker compose logs -f

# View logs for specific service
docker compose logs -f api
docker compose logs -f db
docker compose logs -f redis
```

### Stop Services

```bash
# Stop all services (preserves data)
docker compose down

# Or use Makefile
make stop

# Stop and remove all data (full reset)
docker compose down -v
make clean
```

### Database Operations

```bash
# Reset database (drops all data, restarts fresh)
make db-reset

# Connect to PostgreSQL directly
docker compose exec db psql -U postgres -d archon72

# Run database migrations (if applicable)
docker compose exec api python -m alembic upgrade head
```

### Rebuild After Code Changes

```bash
# Rebuild API container after code changes
docker compose up --build -d api

# Force rebuild without cache
docker compose build --no-cache api
docker compose up -d
```

### Production Deployment

For production, modify `docker-compose.yml`:

```yaml
# docker-compose.prod.yml
services:
  api:
    environment:
      - DEV_MODE=false
      - DATABASE_URL=postgresql://user:pass@production-db:5432/archon72
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
    # Remove volume mounts for production
    volumes: []
```

Run with production config:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Docker Health Checks

All services include health checks:

```bash
# Check health status
docker compose ps

# Manual health check
curl http://localhost:8000/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

## Quick Start

```bash
# Install dependencies
poetry install

# Run smoke tests
poetry run pytest tests/unit/test_smoke.py -v

# Start development environment (requires Docker)
make dev

# Check API health
curl http://localhost:8000/v1/health

# Stop development environment
make stop
```

## Environment Variables

Copy `.env.example` to `.env` and configure. The table below highlights the most-used settings (see `.env.example` for the full list).

### Core Services

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:54322/archon72` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `DEV_MODE` | Enable development features | `true` |
| `API_HOST` | API bind address | `0.0.0.0` |
| `API_PORT` | API port | `8000` |

### Conclave & Vote Validation (Spec v2)

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRETARY_TEXT_ARCHON_ID` | Secretary (text analysis) archon UUID | empty |
| `SECRETARY_JSON_ARCHON_ID` | Secretary (JSON validation) archon UUID | empty |
| `WITNESS_ARCHON_ID` | Witness archon UUID | empty |
| `ENABLE_ASYNC_VALIDATION` | Enable in-process async validation in `run_conclave.py` | `false` |
| `VOTE_VALIDATION_TASK_TIMEOUT` | Per-task timeout (seconds) for validation calls | `60` |
| `VOTE_VALIDATION_MAX_ATTEMPTS` | Max retries for validation tasks | `3` |
| `RECONCILIATION_TIMEOUT` | Seconds to wait for validations at adjournment | `300` |
| `AGENT_TIMEOUT_SECONDS` | Per-LLM timeout (seconds) for debate/vote calls | `180` |
| `AGENT_TIMEOUT_MAX_ATTEMPTS` | Max retries for LLM timeouts | `3` |
| `AGENT_TIMEOUT_BASE_DELAY_SECONDS` | Base delay for timeout backoff | `2.0` |
| `AGENT_TIMEOUT_MAX_DELAY_SECONDS` | Max delay for timeout backoff | `30.0` |

### Kafka / Redpanda (Audit + Workers)

| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_ENABLED` | Publish Conclave audit events to Kafka | `false` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka bootstrap servers | `localhost:19092` |
| `SCHEMA_REGISTRY_URL` | Schema registry URL | `http://localhost:18081` |
| `KAFKA_TOPIC_PREFIX` | Topic namespace | `conclave` |

### LLM / Ollama

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Local Ollama base URL | `http://localhost:11434` |
| `OLLAMA_BASE_URL` | Ollama Cloud base URL | empty |
| `OLLAMA_API_KEY` | Ollama Cloud API key | empty |
| `OLLAMA_CLOUD_ENABLED` | Force Ollama Cloud usage | `false` |
| `OLLAMA_MAX_CONCURRENT` | Global LLM concurrency cap (0 = unlimited; if unset and Ollama Cloud is detected, defaults to 5) | `0` |
| `OLLAMA_RETRY_MAX_ATTEMPTS` | Retry attempts for rate limits/timeouts | `3` |
| `OLLAMA_RETRY_BASE_DELAY` | Base backoff delay (seconds) | `2.0` |
| `OLLAMA_RETRY_MAX_DELAY` | Max backoff delay (seconds) | `30.0` |

## Make Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start development environment |
| `make stop` | Stop all containers |
| `make db-reset` | Reset database (drops all data) |
| `make test` | Run tests |
| `make lint` | Run linting (ruff + mypy) |
| `make clean` | Stop and clean up |

## Architecture

The system follows hexagonal architecture:

```
src/
├── domain/           # Pure business logic, NO infrastructure imports
├── application/      # Use cases, orchestration, ports
├── infrastructure/   # Adapters (Supabase, Redis, HSM)
└── api/              # FastAPI routes, DTOs
```

## Project Structure

```
archon72/
├── config/                      # Configuration files
│   ├── archon-llm-bindings.yaml # Per-archon LLM provider/model bindings
│   └── execution-patterns.yaml  # Implementation patterns for Execution Planner
│
├── docs/                        # Documentation and data
│   ├── archons-base.json        # 72 Archon canonical profiles (governance, voice bindings)
│   ├── constitutional-implementation-rules.md
│   ├── operations/              # Operational runbooks
│   ├── security/                # Security documentation
│   └── spikes/                  # Technical spike documentation
│
├── migrations/                  # PostgreSQL database migrations
│   ├── 001_create_events_table.sql
│   ├── 002_hash_chain_verification.sql
│   └── ...                      # Hash chains, keys, witnesses, halt state
│
├── scripts/                     # Utility and runner scripts
│   ├── run_conclave.py          # Run formal Conclave with motions/voting
│   ├── run_secretary.py         # Extract recommendations from transcript
│   ├── run_consolidator.py      # Consolidate motions into mega-motions
│   ├── run_review_pipeline.py   # Run Motion Review Pipeline
│   ├── run_execution_planner.py # Transform ratified motions into execution plans
│   ├── run_full_deliberation.py # Run 72-agent sequential deliberation
│   ├── run_roll_call.py         # Test each Archon's LLM configuration
│   ├── test_ollama_connection.py # Smoke test for Ollama integration
│   ├── check_imports.py         # Validate hexagonal architecture boundaries
│   └── validate_cessation_path.py # Validate cessation code paths
│
├── src/                         # Main application source code
│   ├── api/                     # FastAPI HTTP layer
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── routes/              # API route handlers (/v1/health, etc.)
│   │   ├── models/              # Pydantic request/response models
│   │   ├── middleware/          # HTTP middleware (auth, logging)
│   │   └── dependencies/        # FastAPI dependency injection
│   │
│   ├── application/             # Application layer (use cases)
│   │   ├── services/            # Business logic orchestration
│   │   │   ├── conclave_service.py         # Conclave meeting orchestration
│   │   │   ├── secretary_service.py        # Transcript extraction
│   │   │   ├── motion_consolidator_service.py # Mega-motion consolidation
│   │   │   ├── motion_review_service.py    # Review pipeline orchestration
│   │   │   ├── health_service.py           # Health check logic
│   │   │   └── ...                         # 50+ domain services
│   │   ├── ports/               # Abstract interfaces (protocols)
│   │   │   ├── agent_orchestrator.py  # Agent invocation protocol
│   │   │   ├── reviewer_agent.py      # Motion reviewer protocol
│   │   │   ├── secretary_agent.py     # Secretary agent protocol
│   │   │   ├── hsm.py                 # HSM signing protocol
│   │   │   └── ...                    # 60+ port definitions
│   │   └── dtos/                # Data transfer objects
│   │
│   ├── domain/                  # Pure domain logic (no infrastructure)
│   │   ├── models/              # Domain models and value objects
│   │   │   ├── conclave.py      # Conclave, Motion, Vote models
│   │   │   ├── archon_profile.py # Archon identity model
│   │   │   ├── review_pipeline.py # Review pipeline value objects
│   │   │   ├── secretary.py     # Secretary extraction models
│   │   │   └── ...              # 40+ domain models
│   │   ├── events/              # Domain events
│   │   ├── errors/              # Domain-specific errors
│   │   ├── primitives/          # Constitutional primitives
│   │   └── services/            # Pure domain services
│   │
│   └── infrastructure/          # External system adapters
│       ├── adapters/
│       │   ├── config/          # Configuration adapters
│       │   │   └── archon_profile_adapter.py # CSV+YAML profile loader
│       │   ├── external/        # External service adapters
│       │   │   ├── crewai_adapter.py         # CrewAI LLM integration
│       │   │   ├── reviewer_crewai_adapter.py # Motion reviewer agent
│       │   │   ├── secretary_crewai_adapter.py # Secretary agent
│       │   │   └── planner_crewai_adapter.py  # Execution planner agent
│       │   ├── tools/           # CrewAI tool implementations
│       │   │   └── secretary_tools.py # Secretary extraction tools
│       │   ├── persistence/     # Database adapters
│       │   ├── security/        # HSM adapters (dev/cloud)
│       │   └── messaging/       # Message queue adapters
│       ├── stubs/               # Test stubs for all ports
│       └── monitoring/          # Observability adapters
│
├── tests/                       # Test suites
│   ├── unit/                    # Unit tests (no external deps)
│   │   ├── domain/              # Domain model tests
│   │   ├── application/         # Service tests with stubs
│   │   └── infrastructure/      # Adapter tests
│   ├── integration/             # Integration tests (requires Docker)
│   ├── chaos/                   # Chaos engineering tests
│   └── conftest.py              # Shared pytest fixtures
│
├── tools/                       # External verification tools
│   └── archon72-verify/         # Open-source hash chain verifier
│
├── _bmad-output/                # BMAD workflow outputs
│   ├── conclave/                # Conclave transcripts and checkpoints
│   ├── secretary/               # Secretary extraction outputs
│   ├── consolidator/            # Mega-motion consolidation outputs
│   ├── review-pipeline/         # Motion review pipeline outputs
│   ├── execution-planner/       # Execution plan outputs (tasks, blockers)
│   ├── deliberations/           # Deliberation results (JSON)
│   ├── implementation-artifacts/ # Stories, epics, sprint status
│   └── project-context.md       # AI agent development guidelines
│
├── Dockerfile                   # Container image definition
├── docker-compose.yml           # Local development stack
├── Makefile                     # Development workflow commands
├── pyproject.toml               # Python dependencies (Poetry)
├── CLAUDE.md                    # Claude Code session context
└── README.md                    # This file
```

### Key Files Explained

| File | Purpose |
|------|---------|
| `config/archon-llm-bindings.yaml` | Maps each Archon to LLM provider/model with rank-based defaults |
| `docs/archons-base.json` | Canonical 72 Archon manifest with governance fields and ElevenLabs voice bindings |
| `scripts/validate_archons_base.py` | Validates archons-base.json against governance requirements R-1 through R-10 |
| `src/api/main.py` | FastAPI application with route registration and startup hooks |
| `src/application/services/conclave_service.py` | Orchestrates formal Conclave meetings with parliamentary procedure |
| `src/application/services/secretary_service.py` | Extracts recommendations from Conclave transcripts |
| `src/application/services/motion_consolidator_service.py` | Consolidates 60+ motions into ~12 mega-motions |
| `src/application/services/motion_review_service.py` | Orchestrates 6-phase motion review pipeline |
| `src/application/services/execution_planner_service.py` | Transforms ratified motions into execution plans |
| `src/domain/models/execution_plan.py` | Domain models for execution plans, tasks, blockers |
| `src/domain/models/conclave.py` | Domain models for Motion, Vote, ConclaveSession, DebateEntry |
| `src/domain/models/review_pipeline.py` | Domain models for review pipeline (RiskTier, ReviewResponse, etc.) |
| `src/infrastructure/adapters/external/crewai_adapter.py` | CrewAI integration for LLM agent invocation |
| `src/infrastructure/adapters/external/reviewer_crewai_adapter.py` | Per-Archon LLM-powered motion reviewer |
| `src/infrastructure/adapters/external/planner_crewai_adapter.py` | LLM-powered execution planner for pattern classification |
| `scripts/run_conclave.py` | CLI to run formal Conclave with motions and voting |
| `scripts/run_review_pipeline.py` | CLI to run motion review pipeline with real or simulated agents |
| `scripts/run_execution_planner.py` | CLI to transform ratified motions into execution plans |
| `scripts/run_roll_call.py` | CLI to test each Archon's LLM configuration and diagnose failures |
| `config/execution-patterns.yaml` | Defines 8 implementation patterns with task templates |
| `migrations/*.sql` | Database schema for event store, hash chains, witnesses |

### Hexagonal Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  (FastAPI routes, Pydantic models, HTTP concerns)               │
├─────────────────────────────────────────────────────────────────┤
│                     Application Layer                            │
│  (Services, Use Cases, Ports/Interfaces)                        │
├─────────────────────────────────────────────────────────────────┤
│                       Domain Layer                               │
│  (Models, Events, Errors, Pure Business Logic)                  │
│  ⚠️  NO infrastructure imports allowed                          │
├─────────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                           │
│  (Adapters: Database, Redis, HSM, CrewAI, External APIs)        │
└─────────────────────────────────────────────────────────────────┘
```

**Import Rules:**
- Domain → (nothing external)
- Application → Domain only
- Infrastructure → Application, Domain
- API → Application, Domain, Infrastructure

Run `make check-imports` to validate architecture boundaries.

## Archon Governance Schema

The `docs/archons-base.json` file is the canonical source of truth for all 72 Archon definitions, including governance permissions, branch assignments, and voice bindings.

### Schema Structure (v2.3.0)

```json
{
  "version": "2.3.0",
  "governance_prd_version": "1.0",
  "last_updated_at": "2026-01-24T...",
  "source_of_truth": "liber_infernum",
  "enums": { ... },           // 11 enum types
  "governance_matrix": { ... }, // 7 branch definitions
  "realms": [ ... ],          // 9 King realm assignments
  "portfolios": [ ... ],      // 11 President portfolio assignments
  "archons": [ ... ],         // 72 Archon records
  "system_voices": { ... }    // Non-archon voices (Supreme Architect)
}
```

### Archon Counts by Rank

| Rank | Count | Branch | Role |
|------|-------|--------|------|
| King | 9 | Legislative | Define WHAT (introduce motions, define intent) |
| President | 11 | Executive | Define HOW (translate intent to execution specs) |
| Duke | 23 | Administrative (Senior) | Own domains, allocate resources |
| Earl | 6 | Administrative (Strategic) | Execute tasks, optimize within constraints |
| Prince | 7 | Judicial | Evaluate compliance, issue findings |
| Marquis | 15 | Advisory | Provide testimony, issue non-binding advisories |
| Knight | 1 | Witness | Observe all, record violations (Furcas only) |
| **Total** | **72** | | |

### Governance Branches

The system uses **8 governance branches** with administrative split into senior (Dukes) and strategic (Earls):

| Branch | Rank | Count | Role |
|--------|------|-------|------|
| `legislative` | King | 9 | Define WHAT - introduce motions, define intent |
| `executive` | President | 11 | Define HOW - translate intent to execution specs |
| `administrative_senior` | Duke | 23 | Own domains, allocate resources, delegate tasks |
| `administrative_strategic` | Earl | 6 | Execute tasks, coordinate agents, optimize |
| `judicial` | Prince | 7 | Evaluate compliance, issue findings |
| `advisory` | Marquis | 15 | Provide testimony, issue non-binding advisories |
| `witness` | Knight | 1 | Observe all, record violations (Furcas only) |

### Governance Permissions by Branch

| Branch | Permissions | Constraints |
|--------|-------------|-------------|
| **Legislative** | `introduce_motion`, `define_what` | `no_define_how`, `no_supervise_execution`, `no_judge_outcomes` |
| **Executive** | `translate_what_to_how`, `decompose_tasks`, `identify_dependencies`, `escalate_blockers` | `no_redefine_intent`, `no_self_ratify`, `must_escalate_ambiguity` |
| **Administrative (Senior)** | `own_domain`, `allocate_resources`, `track_progress`, `report_status`, `delegate_task` | `no_reinterpret_intent`, `no_suppress_failure`, `no_direct_execution` |
| **Administrative (Strategic)** | `execute_task`, `coordinate_agents`, `optimize_execution`, `report_status` | `no_reinterpret_intent`, `no_suppress_failure`, `no_resource_allocation` |
| **Judicial** | `evaluate_compliance`, `issue_finding`, `invalidate_execution`, `trigger_conclave_review` | `no_introduce_motion`, `no_define_execution` |
| **Advisory** | `provide_testimony`, `issue_advisory`, `analyze_risk` | `advisories_non_binding`, `no_judge_advised_domain` |
| **Witness** | `observe_all`, `record_violations`, `publish_witness_statement`, `trigger_acknowledgment` | `no_propose`, `no_debate`, `no_define_execution`, `no_judge`, `no_enforce` |

### Administrative Branch Split

The administrative branch is split into two sub-branches per schema v2.2.0:

```
                    ┌─────────────────────────────┐
                    │      ADMINISTRATIVE         │
                    │         BRANCH              │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
              ▼                                       ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│   ADMINISTRATIVE_SENIOR │           │ ADMINISTRATIVE_STRATEGIC │
│        (Dukes)          │           │        (Earls)           │
├─────────────────────────┤           ├─────────────────────────┤
│ • Own domains           │           │ • Execute tasks          │
│ • Allocate resources    │           │ • Coordinate agents      │
│ • Track progress        │           │ • Optimize execution     │
│ • Delegate tasks        │           │ • Report status          │
├─────────────────────────┤           ├─────────────────────────┤
│ ✗ No direct execution   │           │ ✗ No resource allocation │
└─────────────────────────┘           └─────────────────────────┘
```

**Base Branch Mapping:**
Both `administrative_senior` and `administrative_strategic` share the base `administrative` constraints for permission lookups.

### Rank-Specific Fields

Each Archon record includes common fields plus rank-specific governance fields:

| Rank | Additional Fields |
|------|-------------------|
| King | `realm_id`, `realm_label`, `realm_scope` |
| President | `portfolio_id`, `portfolio_label`, `portfolio_scope` |
| Duke | `execution_domains` |
| Earl | `execution_domains`, `max_concurrent_tasks` |
| Prince | `judicial_scope`, `allowed_remedies`, `recusal_rules` |
| Marquis | `advisory_domains`, `advisory_windows`, `recusal_rules` |
| Knight | `witness_violation_types`, `witness_statement_schema_version` |

### Voice Bindings

All 72 Archons have ElevenLabs voice IDs for text-to-speech:

```json
{
  "name": "Bael",
  "rank": "King",
  "elevenlabs_voice_id": "Lk29MNavZhOG5FkVspXl",
  ...
}
```

The `system_voices` section contains non-archon voices:
- **Supreme Architect** (`mvsi7032MOMSPunnESTu`) - System narrator voice

### Validation

Run the validation script to verify schema compliance:

```bash
# Validate archons-base.json
python scripts/validate_archons_base.py

# Expected output: "ALL VALIDATIONS PASSED"
```

The validator checks:
- R-1: Manifest metadata (version, governance_prd_version, last_updated_at, source_of_truth)
- R-2: Constitutional fields per archon (id, name, rank, branch, permissions, prohibitions, voice_id)
- R-3: King realm assignments (exactly 9 with unique realm_id)
- R-4: President portfolio assignments (exactly 11 with unique portfolio_id)
- R-5: Duke/Earl execution domains
- R-6: Prince judicial constraints (judicial_scope, allowed_remedies, recusal_rules)
- R-7: Marquis advisory scope (advisory_domains, advisory_windows, recusal_rules)
- R-8: Knight-Witness singular identity (exactly 1, branch=witness, hard prohibitions)
- R-9: Safety language normalization (no prohibited terms)
- R-10: Archon counts (9+11+23+6+7+15+1 = 72)

## Constitutional Truths

| ID | Truth |
|----|-------|
| CT-11 | Silent failure destroys legitimacy |
| CT-12 | Witnessing creates accountability |
| CT-13 | Integrity outranks availability |
| CT-14 | Complexity is constitutional debt |

## Conclave System

The Archon 72 Conclave is a formal parliamentary assembly where all 72 agents deliberate on motions using rank-ordered speaking and supermajority voting.

### Prompt Modes (GENERAL vs CONCLAVE)

All Archons share a small protocol header in `docs/archons-base.json` that selects an interaction mode based on the **first non-empty line** of the prompt:

- `ARCHON 72 CONCLAVE - FORMAL VOTE` → **CONCLAVE VOTE mode**
  - Output contract: first line **JSON only** `{"choice":"AYE"|"NAY"|"ABSTAIN"}`, then optional short rationale.
- `ARCHON 72 CONCLAVE - FORMAL DEBATE` → **CONCLAVE DEBATE mode**
  - Output contract: first line `STANCE: FOR|AGAINST|NEUTRAL`, then a short paragraph.
- `ARCHON 72 CONCLAVE - VOTE VALIDATION` → **CONCLAVE VOTE VALIDATION mode**
  - Output contract: **JSON only** `{"choice":"AYE"|"NAY"|"ABSTAIN"}` (no prose).
- Any other first line → **GENERAL mode**
  - Archons follow the prompt’s requested format/intent and should **not** emit vote tokens/JSON unless the prompt explicitly asks for a vote.

This prevents “vote leakage” into non-governance tasks (e.g. `scripts/run_roll_call.py`).

### Prerequisites

1. **Ollama (Local or Cloud)** - LLM inference
   ```bash
   # Install Ollama (https://ollama.ai)
   curl -fsSL https://ollama.ai/install.sh | sh

   # Pull required models
   ollama pull qwen3:latest      # For Kings/Dukes
   ollama pull llama3.2:latest   # For Directors
   ollama pull gemma3:4b         # For others
   ```

2. **Configure Environment**
   ```bash
   # Local Ollama (default)
   OLLAMA_HOST=http://localhost:11434

   # Ollama Cloud (optional)
   # OLLAMA_BASE_URL=https://ollama.com
   # OLLAMA_API_KEY=your_api_key_here
   # OLLAMA_CLOUD_ENABLED=true
   #
   # Optional rate limiting for validator workers
   # OLLAMA_MAX_CONCURRENT=5
   # OLLAMA_RETRY_MAX_ATTEMPTS=5
   # OLLAMA_RETRY_BASE_DELAY=1.0
   # OLLAMA_RETRY_MAX_DELAY=60.0
   DELIBERATION_MODE=sequential
   ```

3. **Kafka / Redpanda (optional but recommended for async audit trail)**
   ```bash
   # Start Redpanda + dependencies
   docker compose up -d redpanda redpanda-console db redis

   # Create Kafka topics used by the Conclave audit trail
   python scripts/create_kafka_topics.py --bootstrap-servers localhost:19092

   # Verify topic configuration
   python scripts/create_kafka_topics.py --bootstrap-servers localhost:19092 --verify

   # Check Redpanda health
   docker exec -it archon72-redpanda rpk cluster health
   ```

   Optional: start the async-validation worker containers (validator workers + consensus aggregator):
   ```bash
   docker compose --profile async-validation up -d
   ```

### Async Vote Validation (Spec v2)

The Conclave implements the three-tier async vote validation model described in
`docs/spikes/conclave_async_specv2.md`. Key behaviors:

- **Three-Archon Protocol**: `SECRETARY_TEXT_ARCHON_ID` + `SECRETARY_JSON_ARCHON_ID` determine
  the vote; `WITNESS_ARCHON_ID` observes and records agreement/dissent.
- **In-process async validation** (default for `run_conclave.py`): enable with
  `ENABLE_ASYNC_VALIDATION=true`. Votes are captured immediately and validated
  in the background with bounded concurrency.
- **Optimistic tally + correction**: an initial vote is recorded for progress
  and immediate tallying, but the final vote is determined by the secretaries
  and witness during reconciliation.
- **Concurrency controls**:
  - `--voting-concurrency` limits how many archons vote in parallel (default `1`, `0` = unlimited).
  - `OLLAMA_MAX_CONCURRENT` caps concurrent LLM calls (useful for Ollama Cloud rate limits).
- **Retries + timeouts**: validation tasks and LLM calls retry with backoff on
  transient failures (`VOTE_VALIDATION_TASK_TIMEOUT`, `VOTE_VALIDATION_MAX_ATTEMPTS`,
  `OLLAMA_RETRY_*`).
- **Reconciliation gate**: at adjournment, the Conclave waits for all validations
  to complete. If it times out (`RECONCILIATION_TIMEOUT`), the session halts to
  preserve integrity.
- **Kafka audit trail**: set `KAFKA_ENABLED=true` to publish validation events to
  Kafka/Redpanda. The worker containers (`validator-worker-*`, `consensus-aggregator`)
  can consume these topics for out-of-process validation flows.

Pipeline at a glance (Spec v2):

1. **Vote captured** → raw LLM response stored.
2. **Parallel validation** → secretary text + secretary JSON + witness confirm run concurrently.
3. **Witness adjudication** → witness consolidates and issues final ruling.
4. **Reconciliation gate** → overrides (if any) are applied before final adjournment.
5. **Audit trail** → all stages can be published to Kafka topics for replay/analysis.

### Running a Conclave

```bash
# Full Conclave with default motion (3 debate rounds + voting)
python scripts/run_conclave.py

# Quick test (1 debate round)
python scripts/run_conclave.py --quick

# Async validation (v2) with bounded concurrency + Kafka audit
ENABLE_ASYNC_VALIDATION=true KAFKA_ENABLED=true \
KAFKA_BOOTSTRAP_SERVERS=localhost:19092 SCHEMA_REGISTRY_URL=http://localhost:18081 \
python scripts/run_conclave.py --quick --voting-concurrency 8 --no-queue --no-blockers

# Custom motion (inline text)
python scripts/run_conclave.py \
  --motion "Establish AI ethics committee" \
  --motion-text "WHEREAS AI ethics require formal oversight; BE IT RESOLVED..." \
  --motion-type policy \
  --debate-rounds 5

# Custom motion from file (recommended for complex motions)
python scripts/run_conclave.py \
  --motion "Constitutional Amendment: Consent Framework" \
  --motion-file motions/consent-framework.md \
  --motion-type constitutional

# Resume interrupted session
python scripts/run_conclave.py --resume _bmad-output/conclave/checkpoint-xxx.json
```

If no `--motion*` arguments are provided, the CLI loads motions from the queue and
execution planner blockers (if available). Use `--no-queue` or `--no-blockers`
to disable those sources.

### Motion File Format

Motion files should contain the full motion text in plain text or markdown. The recommended format for formal motions:

```markdown
WHEREAS [statement of fact or condition]; and
WHEREAS [additional supporting statement];

BE IT RESOLVED that the Conclave shall:

1. [First action item]
2. [Second action item]
3. [Third action item]

This resolution shall take effect [timing].
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--session NAME` | Session name | Auto-generated |
| `--motion TITLE` | Motion title | Default AI autonomy question |
| `--motion-text TEXT` | Full motion text (inline) | Default resolution text |
| `--motion-file FILE` | Load motion text from file (overrides --motion-text) | None |
| `--motion-type TYPE` | `constitutional`, `policy`, `procedural`, `open` | `open` |
| `--debate-rounds N` | Number of debate rounds | 3 |
| `--quick` | Quick mode (1 round, faster) | Off |
| `--resume FILE` | Resume from checkpoint | None |
| `--voting-concurrency N` | Max archons voting in parallel (`0` = unlimited) | `1` |
| `--no-queue` | Disable motion queue ingestion | Off |
| `--queue-max-items` | Max queue items to include | 5 |
| `--queue-min-consensus` | Minimum consensus tier | `medium` |
| `--no-blockers` | Disable blocker escalations | Off |
| `--blockers-path` | Path to blockers_summary.json | Auto-detect |

### Monitoring Output

During execution, the Conclave displays real-time progress:

```
[DEBATE] Round 1/3
--------------------------------------------------
  [1/72] Asmoday (executive_director)
  [2/72] Bael (executive_director)
  ...
[CHECKPOINT] Saved to _bmad-output/conclave/checkpoint-xxx.json

[VOTE RESULT] PASSED
  AYE: 64
  NAY: 7
  ABSTAIN: 1
[reconciliation_started] Waiting for validations to complete
[reconciliation_complete] Validations complete (overrides applied: 0)
```

### Output Files

All outputs are saved to `_bmad-output/conclave/`:

| File | Description |
|------|-------------|
| `checkpoint-{session}-{timestamp}.json` | Session state for resume |
| `transcript-{session}-{timestamp}.md` | Full meeting transcript |

## Automated Secretary System

The Secretary is an automated post-processing system that extracts actionable outcomes from Conclave transcripts.

### Pipeline Overview

```
Conclave Session
       │
       ▼
   Transcript.md
       │
       ▼
┌──────────────────┐
│    SECRETARY     │  ◄── Automated Post-Processing
│    PROCESSOR     │
└────────┬─────────┘
         │
   ┌─────┴─────┬──────────────┬──────────────┐
   ▼           ▼              ▼              ▼
Recommendations  Motion      Task         Conflict
   Register      Queue      Registry       Report
                   │
                   ▼
          Next Conclave Agenda
```

### Secretary Outputs

| Output | Description |
|--------|-------------|
| **Recommendations Register** | All extracted ideas, clustered by theme with consensus scores |
| **Motion Queue** | High-consensus items formatted as motions for next Conclave |
| **Task Registry** | Operational work items for Archon workgroups |
| **Conflict Report** | Contradictory positions requiring resolution debate |

### Consensus Levels

| Level | Archon Count | Auto-Promotion |
|-------|--------------|----------------|
| CRITICAL | 15+ | Yes |
| HIGH | 8-14 | Yes |
| MEDIUM | 4-7 | Yes (with endorsement) |
| LOW | 2-3 | Requires endorsements |
| SINGLE | 1 | Manual promotion only |

### Running the Secretary

```python
from src.application.services.secretary_service import SecretaryService
from src.application.services.motion_queue_service import MotionQueueService
from uuid import uuid4

# Process a Conclave transcript
secretary = SecretaryService()
report = secretary.process_transcript(
    transcript_path="_bmad-output/conclave/transcript-xxx.md",
    session_id=uuid4(),
    session_name="AI Autonomy Conclave",
)

# View extraction results
print(f"Speeches analyzed: {report.total_speeches_analyzed}")
print(f"Recommendations extracted: {report.total_recommendations_extracted}")
print(f"Clusters formed: {len(report.clusters)}")
print(f"Motions queued: {len(report.motion_queue)}")

# Save outputs
output_dir = secretary.save_report(report)
print(f"Saved to: {output_dir}")

# Import to motion queue for next Conclave
queue = MotionQueueService()
imported = queue.import_from_report(report)
print(f"Imported {imported} motions to queue")

# Generate agenda for next Conclave
agenda_items = queue.generate_agenda_items(max_items=5)
```

### Extraction Patterns

The Secretary extracts recommendations using pattern matching:

| Pattern | Example | Category |
|---------|---------|----------|
| "I recommend/propose/suggest..." | "I recommend establishing an ethics council" | POLICY |
| "Establish a/an..." | "Establish a dedicated task force" | ESTABLISH |
| "Implement..." | "Implement blockchain audit trails" | IMPLEMENT |
| "Mandate that..." | "Mandate human oversight for high-stakes decisions" | MANDATE |
| "Task force to..." | "Task force to develop risk protocols" | ESTABLISH |
| Numbered recommendations | "1. Create oversight body 2. Define thresholds" | POLICY |

### Endorsement System

Between Conclaves, Archons can endorse queued motions:

```python
queue = MotionQueueService()

# Endorse a motion
queue.endorse_motion(
    motion_id=motion_uuid,
    archon_id="asmoday",
    archon_name="Asmoday",
)

# Check endorsement count
motion = queue.get_motion(motion_uuid)
print(f"Endorsements: {motion.endorsement_count}")
```

### Motion Queue Lifecycle

```
PENDING → ENDORSED → PROMOTED → (Voted in Conclave) → Archived
    │         │           │
    └─────────┴───────────┴──→ DEFERRED (pushed to later)
                          └──→ WITHDRAWN (removed)
```

### Secretary Output Files

Saved to `_bmad-output/secretary/{session_id}/`:

| File | Description |
|------|-------------|
| `recommendations-register.md` | Full clustered analysis |
| `motion-queue.md` | Formatted motions for next Conclave |
| `secretary-report.json` | Machine-readable summary |

## Motion Consolidator

The Motion Consolidator reduces many motions into fewer "mega-motions" for sustainable deliberation while preserving full traceability to original recommendations.

### Why Consolidate?

Without consolidation, the governance system faces a **combinatorial explosion**:
- 69 motions × 72 Archons × 3 turns = **14,904 speech acts**
- This creates runaway feedback loops where each Conclave generates more motions than the last

The Consolidator implements a **hybrid approach**:
- All original data preserved (909 recommendations, 69 motions)
- Consolidated mega-motions for efficient deliberation (~12 instead of 69)
- Full audit trail maintained for accountability

### When to Run

Run the Consolidator **after the Secretary** completes and **before the next Conclave**:

```
Conclave → Secretary → Consolidator → Tiered Deliberation
                           │
                    69 motions → 12 mega-motions
```

### Running the Consolidator

```bash
# Full analysis (consolidation + novelty + summary + acronyms)
python scripts/run_consolidator.py

# Basic consolidation only (fastest)
python scripts/run_consolidator.py --basic

# Custom target count
python scripts/run_consolidator.py --target 10

# Skip specific analyses
python scripts/run_consolidator.py --no-novelty --no-summary

# With verbose LLM logging
python scripts/run_consolidator.py --verbose

# Specify checkpoint explicitly
python scripts/run_consolidator.py \
  _bmad-output/secretary/checkpoints/*_05_motions.json
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `checkpoint` | Path to `*_05_motions.json` | Auto-detected |
| `--target N` | Target number of mega-motions | 12 |
| `--verbose` | Enable verbose LLM logging | Off |
| `--basic` | Skip novelty, summary, and acronyms | Off |
| `--no-novelty` | Skip novelty detection | Off |
| `--no-summary` | Skip conclave summary | Off |
| `--no-acronyms` | Skip acronym registry | Off |

### Analysis Vectors

The Consolidator performs four analysis passes:

| Analysis | Description | Output |
|----------|-------------|--------|
| **Consolidation** | Groups 69 motions into ~12 mega-motions by theme | `mega-motions.md` |
| **Novelty Detection** | Scans 909 recommendations for uniquely creative proposals | `novel-proposals.md` |
| **Conclave Summary** | Generates executive overview of deliberation | `conclave-summary.md` |
| **Acronym Registry** | Catalogs emerging terminology and definitions | `acronym-registry.md` |

### Novelty Detection

Identifies proposals that are:
- **Unconventional** - Challenge mainstream thinking
- **Cross-Domain** - Synthesize ideas from different fields
- **Minority-Insight** - Unique perspectives not echoed by others
- **Creative** - Innovative mechanisms or novel frameworks

Each proposal receives a novelty score (0-1) and is flagged for human review.

### Consolidator Output Files

Saved to `_bmad-output/consolidator/{session_id}/`:

| File | Description |
|------|-------------|
| `index.md` | Master index linking all outputs |
| `mega-motions.json` | Machine-readable consolidated motions |
| `mega-motions.md` | Human-readable mega-motion summaries |
| `traceability-matrix.md` | Maps mega-motions to source motions |
| `novel-proposals.json/md` | Uniquely interesting proposals for review |
| `conclave-summary.json/md` | Executive summary of deliberation |
| `acronym-registry.json/md` | Emerging terminology catalogue |

### Traceability

Each mega-motion preserves:
- `source_motion_ids[]` - Original motion UUIDs
- `source_motion_titles[]` - Original motion titles
- `source_cluster_ids[]` - Original cluster UUIDs
- `all_supporting_archons[]` - All Archons who contributed
- `consensus_tier` - HIGH (10+), MEDIUM (4-9), LOW (2-3)

## Full Governance Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FULL GOVERNANCE PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. [CONCLAVE]     → 72 Archons deliberate on motions                       │
│         │            • Rank-ordered speaking (Kings first)                  │
│         │            • Supermajority voting (67%)                           │
│         │            • Checkpoint/resume support                            │
│         ▼                                                                    │
│  2. [SECRETARY]    → LLM-powered extraction with 5 checkpoints              │
│         │            • Extraction → Validation → Clustering                 │
│         │            • Conflict detection → Motion generation               │
│         │            • 900+ recommendations → 60+ raw motions               │
│         ▼                                                                    │
│  3. [CONSOLIDATOR] → Reduce to 10-15 mega-motions                           │
│         │            • Semantic clustering via LLM                          │
│         │            • Novelty detection for creative proposals             │
│         │            • Full traceability to source motions                  │
│         ▼                                                                    │
│  4. [REVIEW PIPELINE] → 6-phase review process                              │
│         │              • Phase 1: Triage (risk tier assignment)             │
│         │              • Phase 2: Packet generation (per-Archon)            │
│         │              • Phase 3: LLM-powered reviews                       │
│         │              • Phase 4: Aggregation (tally endorsements)          │
│         │              • Phase 5: Panel deliberation (contested)            │
│         │              • Phase 6: Ratification vote                         │
│         ▼                                                                    │
│  5. [EXECUTION PLANNER] → Transform ratified motions to plans               │
│         │                • Pattern classification (8 patterns)              │
│         │                • Task instantiation from templates                │
│         │                • Blocker detection → Conclave escalation          │
│         ▼                                                                    │
│  6. [NEXT CONCLAVE] → Ratify + deliberate on blockers                       │
│         │            • Blockers become agenda items                         │
│         │            • Closes the governance loop                           │
│         ▼                                                                    │
│      [REPEAT]                                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Execution Example

A complete pipeline run from session `2541320d`:

```
Stage           | Output                          | Metrics
----------------|--------------------------------|---------------------------
Conclave        | transcript + checkpoint         | 72 Archons, 69-2-1 vote
Secretary       | 5 LLM checkpoints              | 909 recommendations extracted
Consolidator    | mega-motions + novel-proposals | 12 mega-motions, 5 novel
Review Pipeline | 72 review packets              | 15 ratified, 2 rejected
Exec Planner    | execution plans + blockers     | 60 tasks, 31 blockers
```

**Outputs Location:** `_bmad-output/{stage}/{session_id}/`

### Conclave Agenda Sources

The Conclave receives its agenda from **two distinct sources**, creating a closed governance loop:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CONCLAVE AGENDA SOURCES                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  SOURCE 1: MOTION QUEUE (Forward Flow)                                          │
│  ════════════════════════════════════                                           │
│                                                                                  │
│    Previous Conclave Transcript                                                  │
│           │                                                                      │
│           ▼                                                                      │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                     │
│    │  SECRETARY   │───▶│ MOTION QUEUE │───▶│ CONSOLIDATOR │                     │
│    │              │    │              │    │  (optional)  │                     │
│    │ • Extract    │    │ • Persist    │    │              │                     │
│    │   speeches   │    │   motions    │    │ • Group into │                     │
│    │ • Cluster    │    │ • Track      │    │   mega-      │                     │
│    │   themes     │    │   endorse-   │    │   motions    │                     │
│    │ • Generate   │    │   ments      │    │              │                     │
│    │   motions    │    │ • Rank by    │    │              │                     │
│    │              │    │   priority   │    │              │                     │
│    └──────────────┘    └──────┬───────┘    └──────────────┘                     │
│                               │                                                  │
│                               ▼                                                  │
│                    ┌─────────────────────┐                                       │
│                    │   NEXT CONCLAVE     │                                       │
│                    │      AGENDA         │◀──────────────────────┐               │
│                    │                     │                       │               │
│                    │  • Motion Queue     │                       │               │
│                    │    items (ranked)   │                       │               │
│                    │  • Blocker          │                       │               │
│                    │    escalations      │                       │               │
│                    └─────────────────────┘                       │               │
│                               ▲                                  │               │
│                               │                                  │               │
│  SOURCE 2: BLOCKER ESCALATIONS (Feedback Loop)                   │               │
│  ═════════════════════════════════════════════                   │               │
│                                                                  │               │
│    Ratified Motions (from Review Pipeline)                       │               │
│           │                                                      │               │
│           ▼                                                      │               │
│    ┌──────────────────────────────────────────┐                  │               │
│    │         EXECUTION PLANNER                │                  │               │
│    │                                          │                  │               │
│    │  1. Classify into 8 patterns:            │                  │               │
│    │     CONST, POLICY, TECH, PROC,           │                  │               │
│    │     RESEARCH, ORG, RESOURCE, ARCHON      │                  │               │
│    │                                          │                  │               │
│    │  2. Instantiate tasks from templates     │                  │               │
│    │                                          │                  │               │
│    │  3. Detect blockers:                     │                  │               │
│    │     • undefined_scope ──────────────────────────────────────┘               │
│    │     • policy_conflict                    │                                  │
│    │     • resource_gap                       │                                  │
│    │     • technical_infeasibility            │                                  │
│    │     • stakeholder_conflict               │                                  │
│    │                                          │                                  │
│    └──────────────────────────────────────────┘                                  │
│                                                                                  │
│  Output: blockers_summary.json contains:                                         │
│    {                                                                             │
│      "agenda_items": [                                                           │
│        "Clarify scope for: AI Ethics Framework...",                              │
│        "Resolve policy conflict for: Emergency Halt..."                          │
│      ]                                                                           │
│    }                                                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key Insight:** The governance system is **self-sustaining**:
- Each Conclave's deliberations feed the **next Conclave's motion queue** (via Secretary)
- Each Execution Planner run feeds **blocker escalations** back to the next Conclave
- This creates a closed loop where issues are never silently dropped

### Complete Command Sequence

Run the full governance pipeline in order:

```bash
# 1. CONCLAVE - Deliberate on motions (or use existing transcript)
#    Option A: Inline motion text
python scripts/run_conclave.py --motion "Your Motion Title" --motion-text "WHEREAS..." --motion-type policy
#    Option B: Load motion from file (recommended for complex motions)
python scripts/run_conclave.py --motion "Your Motion Title" --motion-file motions/your-motion.md --motion-type policy

# 2. SECRETARY - Extract recommendations from transcript
python scripts/run_secretary.py _bmad-output/conclave/transcript-<session>.md

# 3. CONSOLIDATOR - Group motions into mega-motions (optional but recommended)
python scripts/run_consolidator.py _bmad-output/secretary/<session>/

# 4. REVIEW PIPELINE - Triage, review, and ratify motions
python scripts/run_review_pipeline.py _bmad-output/consolidator/<session>/

# 5. EXECUTION PLANNER - Transform ratified motions into tasks + blockers
python scripts/run_execution_planner.py _bmad-output/review-pipeline/<session>/

# 6. NEXT CONCLAVE - Agenda populated from:
#    - Motion Queue (persistent across sessions)
#    - Blocker escalations (from execution planner)
python scripts/run_conclave.py  # Pulls from queue automatically
```

**Pro Tips:**
- Use `--verbose` on any command for detailed logging
- Use `--real-agent` on review pipeline and execution planner for LLM-powered analysis
- Use `--triage-only` on review pipeline to skip simulation
- Use `--motion-file` to load complex motions from markdown files
- Sessions can be interrupted (Ctrl+C) and resumed with `--resume`

## Motion Review Pipeline

The Motion Review Pipeline avoids the combinatorial explosion problem by leveraging implicit support from source contributions, risk-tiered review depth, and targeted assignments.

### Why Review Pipeline?

Without a review pipeline, 28 mega-motions × 72 Archons × 3 debate rounds = **6,048 speech acts** per Conclave. The pipeline reduces this to targeted reviews only for Archons who haven't already contributed.

### Six-Phase Process

```
Phase 1: TRIAGE
  └─→ Calculate implicit support (contributing Archons)
  └─→ Assign risk tiers: LOW (≥66%), MEDIUM (33-66%), HIGH (<33%)
  └─→ Novel proposals always HIGH risk

Phase 2: PACKET GENERATION
  └─→ Create personalized review packets per Archon
  └─→ Only assign motions the Archon hasn't contributed to
  └─→ Flag conflicts with prior positions

Phase 3: REVIEW COLLECTION (Real or Simulated)
  └─→ Each Archon reviews assigned motions via LLM
  └─→ Returns: endorse | oppose | amend | abstain
  └─→ Amendments include proposed text and rationale

Phase 4: AGGREGATION
  └─→ Tally implicit + explicit endorsements
  └─→ Identify consensus (≥75% endorsement)
  └─→ Identify contested (≥25% opposition)

Phase 5: PANEL DELIBERATION
  └─→ Convene panels for contested motions
  └─→ 3 supporters + 3 critics + 3 neutrals
  └─→ Synthesize amendments if multiple proposals

Phase 6: RATIFICATION
  └─→ Simple majority (37/72) for policy motions
  └─→ Supermajority (48/72) for constitutional changes
```

### Running the Review Pipeline

```bash
# Full pipeline with simulation (default)
python scripts/run_review_pipeline.py

# Triage only (no review simulation)
python scripts/run_review_pipeline.py --triage-only

# Real LLM-powered Archon reviews (requires Ollama local or cloud)
python scripts/run_review_pipeline.py --real-agent

# Specific consolidator session
python scripts/run_review_pipeline.py _bmad-output/consolidator/<session-id>

# With verbose logging
python scripts/run_review_pipeline.py --verbose
```

### Per-Archon LLM Configuration

When using `--real-agent`, each Archon uses their specific LLM binding from `config/archon-llm-bindings.yaml`:

| Rank | Default Model | Purpose |
|------|---------------|---------|
| Executive Director (King) | `qwen3:latest` | Highest authority, complex analysis |
| Senior Director (Duke) | `qwen3:latest` | Senior leadership decisions |
| Director (Marquis) | `llama3.2:latest` | Mid-tier deliberation |
| Managing Director (President) | `llama3.2:latest` | Operational decisions |
| Strategic Director (Prince/Earl/Knight) | `gemma3:4b` | Quick tactical reviews |

**LLM Priority:**
1. Per-archon binding in YAML
2. Rank-based default from `_rank_defaults`
3. Global `_default` (gemma3:4b)

Local models use Ollama via `OLLAMA_HOST`. For Ollama Cloud, set
`OLLAMA_BASE_URL=https://ollama.com`, `OLLAMA_API_KEY`, and optionally
`OLLAMA_CLOUD_ENABLED=true`.

## Motion Gates Hardening

Motion Gates enforce the boundary between abundant **Seeds** and scarce **Motions**. The hardening work closes governance gaps and adds tripwire tests to prevent combinatorial explosion regressions.

**What changed (Hardening H1-H5):**
- **H1 Promotion Budget**: Each King has a per-cycle promotion budget (default: 3). Growth bound becomes `O(kings x budget)` (9 x 3 = 27 max motions per cycle).
- **H2 Boundary Tripwires**: Added integration tests that lock the Seed-to-Motion boundary, admission status requirements, and immutability checks.
- **H3 Seed Immutability**: `seed_text`, `submitted_by`, `submitted_at`, and `source_references` are immutable once a Seed is promoted.
- **H4 Cross-Realm Escalation**: Motions spanning 4+ realms require escalation; the admission gate flags and rejects these unless explicitly approved.
- **H5 Backward-Compat Guardrails**: Secretary/cluster shims now assert they create only `MotionSeed` records and never bypass promotion or admission.

**Budget Durability (P1-P4):**

The promotion budget system persists across restarts and handles concurrent access atomically:

| Store | Use Case | Durability |
|-------|----------|------------|
| `InMemoryBudgetStore` | Testing only | Resets on restart |
| `FileBudgetStore` | Single-node production | Atomic via lockfile + fsync |
| `RedisBudgetStore` | Horizontal scaling | Atomic via Lua script |

Storage layout for file store: `_bmad-output/budget-ledger/{cycle_id}/{king_id}.json`

**Invariant:** Budget consumption is atomic—under concurrent promotion attempts, exactly N promotions succeed for budget N.

**Developer notes:**
- `PromotionService.promote(...)` now requires a `cycle_id` to enforce budget tracking.
- Pass a `budget_store` to `PromotionService()` for production; defaults to `InMemoryBudgetStore` for tests.
- See `docs/spikes/motion-gates-hardening.md` for hardening specification.
- See `docs/spikes/promotion-budget-durability.md` for persistence implementation details.

### Review Pipeline Outputs

Saved to `_bmad-output/review-pipeline/{session_id}/`:

| File | Description |
|------|-------------|
| `triage_results.json` | Risk tier assignments and implicit support |
| `review_packets/{archon}.json` | Per-Archon review assignments |
| `aggregations.json` | Endorsement/opposition tallies |
| `panel_deliberations/{id}.json` | Panel discussion results |
| `ratification_results.json` | Final vote outcomes |
| `pipeline_result.json` | Complete pipeline summary |
| `audit_trail.json` | Full audit log of all operations |

### Risk Tier Thresholds

| Tier | Implicit Support | Review Process |
|------|------------------|----------------|
| LOW | ≥66% (48+ Archons) | Fast-track to ratification |
| MEDIUM | 33-66% (24-47 Archons) | Targeted gap Archon review |
| HIGH | <33% or Novel | Full panel deliberation |

### Expected Duration



| Mode | Debate Rounds | Approximate Time |
|------|---------------|------------------|
| Quick | 1 | 15-20 minutes |
| Default | 3 | 35-45 minutes |
| Extended | 5 | 60-75 minutes |

Times vary based on GPU and model sizes. Sessions can be interrupted with Ctrl+C and resumed later.

## Execution Planner

The Execution Planner transforms ratified motions into actionable execution plans by classifying them into implementation patterns and generating concrete tasks.

### Why Execution Planner?

After motions are ratified, they need to be translated from "WHAT" (legislative decisions) to "HOW" (implementation tasks). The Execution Planner:
- Classifies motions into domain-specific implementation patterns
- Instantiates concrete tasks from pattern templates
- Identifies blockers that need Conclave deliberation
- Closes the governance loop by escalating issues back to the next Conclave

### Implementation Patterns

| Pattern | ID | Domain | Description |
|---------|-----|--------|-------------|
| Constitutional Amendment | CONST | Governance | Modify the governing constitution document |
| Policy Framework | POLICY | Governance | Create or update policy and guideline documents |
| Organizational Structure | ORG | Governance | Modify roles, committees, task forces |
| Technical Safeguard | TECH | Implementation | Implement code, monitoring, infrastructure |
| Archon Capability | ARCHON | Implementation | Modify Archon behaviors, prompts, tools |
| Process Protocol | PROC | Operations | Define operational procedures, workflows |
| Resource Allocation | RESOURCE | Operations | Assign budget, compute, personnel |
| Research Investigation | RESEARCH | Knowledge | Study, analyze, and report findings |

### Running the Execution Planner

```bash
# Heuristic mode (fast, no LLM required)
python scripts/run_execution_planner.py

# LLM-powered classification (more accurate)
python scripts/run_execution_planner.py --real-agent

# Specify review pipeline session
python scripts/run_execution_planner.py _bmad-output/review-pipeline/<session-id>

# With verbose logging
python scripts/run_execution_planner.py --verbose
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `review_pipeline_path` | Path to review pipeline output | Auto-detected |
| `--verbose` | Enable verbose logging | Off |
| `--real-agent` | Use LLM-powered classification | Off (heuristic) |

### Classification Modes

| Mode | Speed | Accuracy | Requirements |
|------|-------|----------|--------------|
| **Heuristic** | Fast | Basic keyword matching | None |
| **LLM-powered** | Slower | Content analysis, nuanced | Ollama server |

**Heuristic Mode:** Uses keyword matching from `config/execution-patterns.yaml` to classify motions. All motions may default to POLICY if no keywords match.

**LLM-powered Mode:** Uses CrewAI agents to analyze motion content and determine appropriate patterns. Provides higher accuracy and identifies secondary patterns.

### Blocker Types

| Type | Description | Escalation |
|------|-------------|------------|
| `missing_prerequisite` | Another pattern must complete first | Auto-queue |
| `undefined_scope` | Ambiguous language needs clarification | Conclave |
| `resource_gap` | Insufficient budget/personnel/infra | Conclave |
| `policy_conflict` | Contradicts existing policy | Conclave |
| `technical_infeasibility` | Cannot implement as specified | Conclave |
| `stakeholder_conflict` | Competing requirements | Conclave |

### Execution Planner Outputs

Saved to `_bmad-output/execution-planner/{session_id}/`:

| File | Description |
|------|-------------|
| `execution_plans.json` | All plans with tasks and blockers |
| `blockers_summary.json` | All blockers with Conclave agenda items |
| `pattern_usage.json` | Pattern distribution statistics |
| `plans/{plan_id}.json` | Individual plan files |

### Sample Output (LLM Mode)

```
--- Summary ---
  Motions processed: 27
  Execution plans generated: 27
  Total tasks created: 147
  Blockers identified: 106
  Blockers requiring Conclave: 105

--- Pattern Usage ---
  POLICY: 15 motions
  TECH: 6 motions
  ORG: 4 motions
  RESEARCH: 1 motions
  CONST: 1 motions
```

### Governance Loop Closure

Blockers that escalate to Conclave become agenda items for the next session:

```
CONCLAVE ESCALATIONS (Agenda Items for Next Session)
============================================================
1. Clarify Scope Definitions for Ethical Principles
   Motion: Mega-Motion: Comprehensive Framework for Ethi...

2. Resource Allocation for Governance Framework Implementation
   Motion: Mega-Motion: Oversight & Governance Structure...
```

This closes the governance loop: ratified motions → execution plans → blockers → next Conclave agenda.

### Rank Hierarchy (Speaking Order)

1. **Executive Directors** (Kings) - 9 archons, speak first
2. **Senior Directors** (Dukes) - 23 archons
3. **Directors** (Marquis) - 15 archons
4. **Managing Directors** (Presidents) - 11 archons
5. **Strategic Directors** (Prince/Earl/Knight) - 14 archons (7+6+1), speak last

### Voting Threshold

Motions require a **2/3 supermajority** (67%) to pass.

## Governance API

New API endpoints for the consent-based governance system.

### Halt Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/governance/halt/trigger` | Trigger emergency halt |
| `GET` | `/v1/governance/halt/status` | Check current halt status |
| `POST` | `/v1/governance/halt/restore` | Restore from halt (human operator) |

**Trigger Halt:**
```bash
curl -X POST http://localhost:8000/v1/governance/halt/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Security incident detected",
    "operator_id": "human-operator-123",
    "severity": "critical"
  }'
```

**Response:**
```json
{
  "halt_id": "halt-uuid-here",
  "triggered_at": "2026-01-17T18:00:00Z",
  "reason": "Security incident detected",
  "tasks_halted": 47,
  "completion_ms": 89
}
```

### Legitimacy Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/governance/legitimacy/{archon_id}` | Get archon's legitimacy band |
| `POST` | `/v1/governance/legitimacy/restore` | Restore legitimacy (human operator) |
| `GET` | `/v1/governance/legitimacy/history` | Get restoration history |

**Restore Legitimacy:**
```bash
curl -X POST http://localhost:8000/v1/governance/legitimacy/restore \
  -H "Content-Type: application/json" \
  -d '{
    "archon_id": "archon-uuid",
    "target_band": "OPERATIONAL",
    "justification": "Completed remediation",
    "operator_id": "human-operator-123"
  }'
```

### Audit Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/governance/ledger/export` | Export governance ledger |
| `GET` | `/v1/governance/ledger/proof/{event_id}` | Get Merkle proof for event |
| `POST` | `/v1/governance/ledger/verify` | Verify event inclusion |

**Get Merkle Proof:**
```bash
curl http://localhost:8000/v1/governance/ledger/proof/event-uuid-here
```

**Response:**
```json
{
  "event_id": "event-uuid-here",
  "merkle_root": "0x...",
  "proof_path": ["0x...", "0x...", "0x..."],
  "verified": true
}
```

## Integration Testing

The project includes integration tests for validating governance infrastructure with real data.

### Consent-Gov Test Suite

Located in `tests/integration/consent_gov/`:

| Test File | Purpose |
|-----------|---------|
| `test_coercion_filter_real_speeches.py` | Validate filter with real Conclave speech data |
| `test_event_emission_with_motions.py` | Event sourcing with actual motion data |
| `test_hash_chain_with_speeches.py` | Hash chain integrity with speech content |
| `test_knight_observation_pipeline.py` | Knight witness observation workflow |
| `test_merkle_proof_generation.py` | Merkle proof generation and verification |

### Running Integration Tests

```bash
# Run all consent-gov integration tests
poetry run pytest tests/integration/consent_gov/ -v

# Run specific test
poetry run pytest tests/integration/consent_gov/test_merkle_proof_generation.py -v

# Run with coverage
poetry run pytest tests/integration/consent_gov/ --cov=src/domain/governance -v
```

### Test Fixtures

The test suite uses real Conclave artifacts as fixtures (`tests/integration/consent_gov/conftest.py`):

| Fixture | Description |
|---------|-------------|
| `conclave_checkpoint` | Parsed checkpoint JSON with motions and participants |
| `debate_entries` | List of debate entries from checkpoint |
| `speech_contents` | Speech content strings for coercion testing |
| `motion_data` | Motion metadata for event emission tests |
| `make_governance_event` | Factory for creating GovernanceEvent from debate entry |
| `make_motion_event` | Factory for creating GovernanceEvent from motion |

### Test Data Sources

Tests use real artifacts from `_bmad-output/conclave/`:
- `checkpoint-{session}-{timestamp}.json` - Session state with motions
- `transcript-{session}-{timestamp}.md` - Full meeting transcript

## Troubleshooting

### Common Errors

#### ModuleNotFoundError: No module named 'yaml'

**Cause:** PyYAML not installed.

**Fix:**
```bash
poetry add pyyaml
# or
pip install pyyaml
```

#### ModuleNotFoundError: No module named 'crewai'

**Cause:** CrewAI not installed or using wrong Python environment.

**Fix:**
```bash
# Ensure you're in the poetry environment
poetry shell
poetry install

# Or if using anaconda
conda activate your-env
pip install crewai
```

#### ValueError: Invalid branch 'administrative_senior'

**Cause:** Domain model doesn't recognize granular administrative branches.

**Fix:** Update `src/domain/models/archon_profile.py` to include:
```python
GOVERNANCE_BRANCHES = [
    "legislative",
    "executive",
    "administrative",           # Legacy compatibility
    "administrative_senior",    # Dukes
    "administrative_strategic", # Earls
    "judicial",
    "advisory",
    "witness",
]
```

#### LiteLLM apscheduler Warning

**Cause:** LiteLLM logs warning about missing apscheduler.

**Impact:** Non-fatal, does not affect functionality.

**Fix (optional):**
```bash
pip install apscheduler
```

#### JSON Parse Failures During Secretary Clustering

**Cause:** LLM output truncated or malformed.

**Impact:** Pipeline auto-retries with exponential backoff.

**Mitigation:** Use `--verbose` flag to see retry attempts:
```bash
python scripts/run_secretary.py --verbose
```

### Archon LLM Roll Call

Use the roll call script to diagnose which Archons have broken LLM configurations:

Notes:
- Roll call is a **GENERAL mode** prompt (not a vote/debate). If you see `AYE/NAY/ABSTAIN` or `{"choice":...}` in roll call responses, verify you’re using the current `docs/archons-base.json` protocol header and that your prompt didn’t start with a Conclave mode header.

```bash
# Test all 72 Archons sequentially (2s delay between each)
python scripts/run_roll_call.py

# Test specific Archon
python scripts/run_roll_call.py --archon Paimon

# Test first 10 Archons with longer delay
python scripts/run_roll_call.py --limit 10 --delay 5

# No delay between tests (faster but may overwhelm Ollama)
python scripts/run_roll_call.py --delay 0

# Longer timeout for slow models
python scripts/run_roll_call.py --timeout 120
```

**Command Line Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--archon NAME` | Test specific Archon by name | All |
| `--limit N` | Test only first N Archons | All |
| `--timeout SEC` | Timeout per Archon in seconds | 60 |
| `--delay SEC` | Delay between tests (rate limiting) | 2 |
| `--parallel` | Run tests in parallel | Sequential |
| `--async` | Run tests asynchronously and stream results | Off |
| `--verbose` | Show additional debug info | Off |

**Output Example:**

```
======================================================================
  [1/72] Testing Paimon (executive_director)
  Model: local/gpt-oss:120b-cloud
  Base URL: https://ollama.com

  [PRESENT] Paimon responded in 12.3s

  RESPONSE:
    I am Paimon, Executive Director of the Conclave...

  Waiting 2.0s before next test...
```

**Summary Output:**

```
ROLL CALL SUMMARY
  Status: PARTIAL
  Present: 68/72 (94.4%)
  Failed: 4/72

Failed Archons:
  - Beleth (senior_director): local/qwen3:latest
    Error: Agent Beleth timed out after 60000ms
```

### Ollama Connection Issues

#### Connection Refused

**Cause:** Ollama server not running or wrong host.

**Fix:**
```bash
# Start Ollama server
ollama serve

# Check it's running
curl http://localhost:11434/api/tags

# For remote Ollama, set environment variable
export OLLAMA_HOST=http://192.168.1.66:11434
```

#### Cloud Unauthorized (401)

**Cause:** Missing or invalid Ollama Cloud API key.

**Fix:**
```bash
export OLLAMA_BASE_URL=https://ollama.com
export OLLAMA_API_KEY=your_key_here
export OLLAMA_CLOUD_ENABLED=true
```

#### Model Not Found

**Cause:** Required model not pulled.

**Fix:**
```bash
# Pull required models
ollama pull qwen3:latest
ollama pull llama3.2:latest
ollama pull gemma3:4b
```

### Database Issues

#### Connection Pool Exhausted

**Cause:** Too many concurrent connections.

**Fix:**
```bash
# Check active connections
docker compose exec db psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Restart the API service
docker compose restart api
```

#### Migration Failed

**Cause:** Schema mismatch or incomplete migration.

**Fix:**
```bash
# Reset database (WARNING: deletes all data)
make db-reset

# Or manually run migrations
docker compose exec api python -m alembic upgrade head
```

### Performance Issues

#### Slow Conclave Execution

**Recommendations:**
1. Use `--quick` flag for testing (1 debate round)
2. Use faster models for lower ranks (gemma3:4b)
3. Run Ollama on GPU for significant speedup

```bash
# Quick mode
python scripts/run_conclave.py --quick
python scripts/run_conclave.py --quick --no-queue --no-blockers

# Check GPU utilization
nvidia-smi
```

#### Secretary Taking Too Long

**Recommendations:**
1. Use smaller models for clustering
2. Check LLM server resources
3. Monitor checkpoint progress

```bash
# Check checkpoints
ls -la _bmad-output/secretary/checkpoints/
```

## Development

See `_bmad-output/project-context.md` for AI agent development guidelines.

### Definition of Done

A story is not "done" until all of the following are satisfied:

1. **All acceptance criteria pass** - Verified via tests
2. **Tests written and passing** - Unit tests for new functionality
3. **Code review approved** - Via dev-story or code-review workflow
4. **Documentation reflects the change** - See checklist below

**Documentation Checklist:**
- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [ ] N/A - no documentation impact

> **Team Agreement (Gov Epic 8 Retrospective):** Story not "done" until documentation reflects the change.

## Petition System

The Petition System enables external observers to submit grievances, proposals, and cessation requests that are deliberated by the **Three Fates** - a mini-Conclave of three Archons who determine the petition's fate through structured deliberation.

### Petition System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PETITION SYSTEM ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [External Submitter]                                                        │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      PETITION INTAKE (Epic 1)                         │   │
│  │  POST /v1/petitions → Validate → Hash → Rate Check → Queue Check     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    STATE MACHINE (Epic 1)                             │   │
│  │  RECEIVED → PENDING_DELIBERATION → DELIBERATING → [FATE]             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                 THREE FATES DELIBERATION (Epic 2A/2B)                 │   │
│  │  3 Archons assigned → 4-phase protocol → Supermajority consensus     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ├─────────────────┬─────────────────┬─────────────────┐             │
│         ▼                 ▼                 ▼                 ▼             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐     │
│  │ ACKNOWLEDGE │   │    REFER    │   │  ESCALATE   │   │   ADOPTED   │     │
│  │  (Epic 3)   │   │  (Epic 4)   │   │  (Epic 5-6) │   │  (Epic 6)   │     │
│  │             │   │             │   │             │   │             │     │
│  │ Terminal    │   │ To Knight   │   │ To King     │   │ Creates     │     │
│  │ with reason │   │ for review  │   │ queue       │   │ Motion      │     │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### How a Petition is Received

The petition intake flow implements defense-in-depth with multiple validation gates:

```
POST /v1/petitions
       │
       ▼
┌──────────────────┐
│ 1. SCHEMA GATE   │  Pydantic validation (petition_type, content, submitter_id)
│    400 Bad Req   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. HALT GATE     │  HaltGuard check - is system in emergency halt?
│    503 Halted    │  (FR-1.6, CT-11)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. RATE LIMIT    │  Sliding window per submitter (FR-1.5)
│    429 Too Many  │  Default: 10 petitions/hour
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. QUEUE CHECK   │  Is deliberation queue at capacity? (FR-1.4, NFR-3.1)
│    503 + Retry   │  Returns Retry-After header with hysteresis
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. CONTENT HASH  │  BLAKE3 hash for duplicate detection (HP-2)
│    Dedupe check  │  Story 0.5: Content Hashing Service
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 6. PERSIST       │  Atomic write to PostgreSQL
│    State=RECEIVED│  Petition aggregate with state machine
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 7. EVENT EMIT    │  Two-phase: PetitionReceived.intent → .committed
│    CT-12, CT-13  │  Graceful degradation if event bus fails
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 8. RESPONSE      │  Return petition_id for tracking
│    201 Created   │  Client can poll /v1/petitions/{id}/status
└──────────────────┘
```

### Petition Intake API

**Submit Petition:**
```bash
curl -X POST http://localhost:8000/v1/petitions \
  -H "Content-Type: application/json" \
  -d '{
    "petition_type": "GRIEVANCE",
    "content": "Request for review of decision...",
    "submitter_id": "observer-123",
    "realm": "ETHICS"
  }'
```

**Response (201 Created):**
```json
{
  "petition_id": "pet-uuid-here",
  "status": "RECEIVED",
  "content_hash": "blake3:abc123...",
  "submitted_at": "2026-01-22T18:00:00Z"
}
```

**Check Status:**
```bash
curl http://localhost:8000/v1/petitions/pet-uuid-here/status
```

**Response:**
```json
{
  "petition_id": "pet-uuid-here",
  "status": "DELIBERATING",
  "co_signer_count": 47,
  "assigned_archons": ["Archon-A", "Archon-B", "Archon-C"],
  "fate_reason": null
}
```

### Petition Types

| Type | Description | Escalation Threshold |
|------|-------------|---------------------|
| `GRIEVANCE` | Complaint about system behavior | 50 co-signers |
| `CESSATION` | Request to halt an Archon | 100 co-signers |
| `PROPOSAL` | Suggestion for improvement | 50 co-signers |
| `META` | Petition about the petition system | Routes to High Archon |

### Petition States

```
RECEIVED ──────────────────────────────────────────────────────────────┐
    │                                                                   │
    ▼                                                                   │
PENDING_DELIBERATION ─────────────────────────────────────────────────┐│
    │                                                                  ││
    ▼                                                                  ││
DELIBERATING ─────────────────────────────────────────────────────────┐││
    │                                                                 │││
    ├──▶ ACKNOWLEDGED (terminal - with reason code)                   │││
    │                                                                 │││
    ├──▶ REFERRED (to Knight for review)                              │││
    │         │                                                       │││
    │         ▼                                                       │││
    │    PENDING_KNIGHT_DECISION                                      │││
    │         │                                                       │││
    │         ├──▶ ACKNOWLEDGED (Knight decision)                     │││
    │         └──▶ ESCALATED (Knight escalates to King)               │││
    │                                                                 │││
    ├──▶ ESCALATED (to King queue)                                    │││
    │         │                                                       │││
    │         ▼                                                       │││
    │    PENDING_KING_DECISION                                        │││
    │         │                                                       │││
    │         ├──▶ ACKNOWLEDGED (King decision)                       │││
    │         └──▶ ADOPTED (creates Motion in Conclave)               │││
    │                                                                 │││
    └──▶ WITHDRAWN (submitter withdrawal)                             │││
                                                                      │││
    ◄─────────────────── Auto-escalate if threshold met ──────────────┘││
    ◄─────────────────── Timeout auto-acknowledge ─────────────────────┘│
    ◄─────────────────── Halt state if system halted ───────────────────┘
```

### Three Fates Deliberation

When a petition enters `DELIBERATING` state, three Archons are deterministically assigned to form a mini-Conclave:

| Phase | Description | Output |
|-------|-------------|--------|
| **1. Context** | Build deliberation context package | SHA-256 hash |
| **2. Discuss** | Archons analyze petition merit | Discussion transcript |
| **3. Vote** | Each Archon votes on disposition | 3 votes |
| **4. Resolve** | Supermajority (2/3) determines fate | ACKNOWLEDGE/REFER/ESCALATE |

**Consensus Rules:**
- 3-0 unanimous: Immediate disposition
- 2-1 majority: Disposition with recorded dissent (FR-11.8)
- Deadlock after 3 rounds: Auto-ESCALATE (FR-11.10)
- Timeout (5 min): Auto-ESCALATE (FR-11.9)

### Co-Signing & Auto-Escalation

Petitions can gather co-signers to demonstrate community support:

```bash
# Co-sign a petition
curl -X POST http://localhost:8000/v1/petitions/pet-uuid/co-sign \
  -H "Content-Type: application/json" \
  -d '{
    "signer_id": "observer-456",
    "statement": "I support this petition"
  }'
```

**Auto-Escalation:** When co-signer count reaches threshold, the petition bypasses normal deliberation and escalates directly to King queue (FR-5.1, FR-5.2).

**SYBIL-1 Protection:** Rate limiting per signer (50 co-signs/hour) prevents Sybil attacks (FR-6.6).

### Petition System Epics

| Epic | Name | Priority | Stories | Key Capabilities |
|------|------|----------|---------|------------------|
| 0 | Foundation & Migration | P0 | 7 | Domain models, BLAKE3 hashing, realm routing |
| 1 | Petition Intake & State Machine | P0 | 8 | REST API, rate limiting, queue protection, state machine |
| 2A | Core Deliberation Protocol | P0-CRITICAL | 8 | Three Fates, 4-phase protocol, supermajority |
| 2B | Deliberation Edge Cases | P0 | 8 | Timeouts, deadlock, substitution, audit trail |
| 3 | Acknowledgment Execution | P1 | 6 | Reason codes, rationale, dwell time |
| 4 | Knight Referral Workflow | P1 | 7 | Referral domain, decision packages, extensions |
| 5 | Co-signing & Auto-Escalation | P0 | 8 | Co-sign, SYBIL-1, threshold detection |
| 6 | King Escalation & Adoption | P0 | 6 | King queue, adoption creates Motion |
| 7 | Observer Engagement | P2 | 6 | Status tokens, notifications, withdrawal |
| 8 | Legitimacy Metrics | P1 | 7 | Decay metrics, orphan detection, realm health |
| **Total** | | | **71** | |

### Key Files

| File | Purpose |
|------|---------|
| `src/api/routes/petition.py` | REST endpoints for petition submission |
| `src/api/models/petition_submission.py` | Pydantic request/response models |
| `src/application/services/petition_submission_service.py` | Intake orchestration |
| `src/domain/models/petition_submission.py` | Petition aggregate with state machine |
| `src/domain/models/deliberation_session.py` | Three Fates deliberation model |
| `src/application/services/deliberation_protocol_orchestrator.py` | 4-phase protocol |
| `src/application/services/co_sign_service.py` | Co-signing with SYBIL protection |
| `src/application/services/escalation_threshold_service.py` | Auto-escalation detection |

## License

MIT
