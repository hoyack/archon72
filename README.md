# Archon 72

Constitutional AI Governance System with 72 Agents

## Table of Contents

- [Overview](#overview)
- [Deployment from Scratch](#deployment-from-scratch)
- [Docker Usage](#docker-usage)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Make Commands](#make-commands)
- [Architecture](#architecture)
- [Constitutional Truths](#constitutional-truths)
- [Conclave System](#conclave-system)
- [Development](#development)

## Overview

Archon 72 is a witnessed, transparent, and accountable AI governance system built on constitutional principles. It features:

- **72 Concurrent Agents** - Multi-agent deliberation and collective decision-making
- **Cryptographic Witnessing** - All actions are signed and verifiable
- **Halt-Over-Degrade Philosophy** - System integrity takes precedence over availability
- **Append-Only Event Store** - Immutable audit trail with hash-chaining

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

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:54322/archon72` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `DEV_MODE` | Enable development features | `true` |
| `API_HOST` | API bind address | `0.0.0.0` |
| `API_PORT` | API port | `8000` |

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
│   └── archon-llm-bindings.yaml # Per-archon LLM provider/model bindings
│
├── docs/                        # Documentation and data
│   ├── archons-base.csv         # 72 Archon identity profiles (name, rank, backstory)
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
│   ├── run_full_deliberation.py # Run 72-agent sequential deliberation
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
│   │   │   ├── conclave_service.py    # Conclave meeting orchestration
│   │   │   ├── health_service.py      # Health check logic
│   │   │   └── ...                    # 50+ domain services
│   │   ├── ports/               # Abstract interfaces (protocols)
│   │   │   ├── agent_orchestrator.py  # Agent invocation protocol
│   │   │   ├── hsm.py                 # HSM signing protocol
│   │   │   └── ...                    # 60+ port definitions
│   │   └── dtos/                # Data transfer objects
│   │
│   ├── domain/                  # Pure domain logic (no infrastructure)
│   │   ├── models/              # Domain models and value objects
│   │   │   ├── conclave.py      # Conclave, Motion, Vote models
│   │   │   ├── archon_profile.py # Archon identity model
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
│       │   │   └── crewai_adapter.py # CrewAI LLM integration
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
| `docs/archons-base.csv` | Master list of 72 Archon identities (UUID, name, rank, backstory, system prompt) |
| `src/api/main.py` | FastAPI application with route registration and startup hooks |
| `src/application/services/conclave_service.py` | Orchestrates formal Conclave meetings with parliamentary procedure |
| `src/domain/models/conclave.py` | Domain models for Motion, Vote, ConclaveSession, DebateEntry |
| `src/infrastructure/adapters/external/crewai_adapter.py` | CrewAI integration for LLM agent invocation |
| `scripts/run_conclave.py` | CLI to run formal Conclave with motions and voting |
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

## Constitutional Truths

| ID | Truth |
|----|-------|
| CT-11 | Silent failure destroys legitimacy |
| CT-12 | Witnessing creates accountability |
| CT-13 | Integrity outranks availability |
| CT-14 | Complexity is constitutional debt |

## Conclave System

The Archon 72 Conclave is a formal parliamentary assembly where all 72 agents deliberate on motions using rank-ordered speaking and supermajority voting.

### Prerequisites

1. **Ollama Server** - Local LLM inference server
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
   # In .env file
   OLLAMA_HOST=http://localhost:11434
   DELIBERATION_MODE=sequential
   ```

### Running a Conclave

```bash
# Full Conclave with default motion (3 debate rounds + voting)
python scripts/run_conclave.py

# Quick test (1 debate round)
python scripts/run_conclave.py --quick

# Custom motion
python scripts/run_conclave.py \
  --motion "Establish AI ethics committee" \
  --motion-type policy \
  --debate-rounds 5

# Resume interrupted session
python scripts/run_conclave.py --resume _bmad-output/conclave/checkpoint-xxx.json
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--session NAME` | Session name | Auto-generated |
| `--motion TITLE` | Motion title | Default AI autonomy question |
| `--motion-text TEXT` | Full motion text | Default resolution text |
| `--motion-type TYPE` | `constitutional`, `policy`, `procedural`, `open` | `open` |
| `--debate-rounds N` | Number of debate rounds | 3 |
| `--quick` | Quick mode (1 round, faster) | Off |
| `--resume FILE` | Resume from checkpoint | None |

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
# Auto-detect latest motions checkpoint, consolidate to ~12 mega-motions
poetry run python scripts/run_consolidator.py

# Custom target count
poetry run python scripts/run_consolidator.py --target 10

# With verbose LLM logging
poetry run python scripts/run_consolidator.py --verbose

# Specify checkpoint explicitly
poetry run python scripts/run_consolidator.py \
  _bmad-output/secretary/checkpoints/*_05_motions.json
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `checkpoint` | Path to `*_05_motions.json` | Auto-detected |
| `--target N` | Target number of mega-motions | 12 |
| `--verbose` | Enable verbose LLM logging | Off |

### Consolidator Output Files

Saved to `_bmad-output/consolidator/`:

| File | Description |
|------|-------------|
| `mega-motions.json` | Machine-readable consolidated motions |
| `mega-motions.md` | Human-readable mega-motion summaries |
| `traceability-matrix.md` | Maps mega-motions to source motions |

### Traceability

Each mega-motion preserves:
- `source_motion_ids[]` - Original motion UUIDs
- `source_motion_titles[]` - Original motion titles
- `source_cluster_ids[]` - Original cluster UUIDs
- `all_supporting_archons[]` - All Archons who contributed
- `consensus_tier` - HIGH (10+), MEDIUM (4-9), LOW (2-3)

### Full Governance Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    GOVERNANCE PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. [Conclave]     → 72 Archons deliberate on motions          │
│         │                                                       │
│         ▼                                                       │
│  2. [Secretary]    → Extract 900+ recommendations              │
│         │            Cluster into 180+ themes                   │
│         │            Generate 60+ raw motions                   │
│         ▼                                                       │
│  3. [Consolidator] → Reduce to 10-15 mega-motions              │
│         │            Preserve full traceability                 │
│         ▼                                                       │
│  4. [Router]       → Tier by consensus level                   │
│         │            HIGH → Ratification (simple vote)          │
│         │            MEDIUM → Committee (12 Archons)            │
│         │            LOW → Backlog (future sessions)            │
│         ▼                                                       │
│  5. [Next Conclave] → Deliberate mega-motions efficiently      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Expected Duration

| Mode | Debate Rounds | Approximate Time |
|------|---------------|------------------|
| Quick | 1 | 15-20 minutes |
| Default | 3 | 35-45 minutes |
| Extended | 5 | 60-75 minutes |

Times vary based on GPU and model sizes. Sessions can be interrupted with Ctrl+C and resumed later.

### Rank Hierarchy (Speaking Order)

1. **Executive Directors** (Kings) - 9 archons, speak first
2. **Senior Directors** (Dukes) - 23 archons
3. **Directors** (Marquis) - 15 archons
4. **Managing Directors** (Presidents) - 11 archons
5. **Strategic Directors** (Prince/Earl/Knight) - 14 archons, speak last

### Voting Threshold

Motions require a **2/3 supermajority** (67%) to pass.

## Development

See `_bmad-output/project-context.md` for AI agent development guidelines.

## License

MIT
