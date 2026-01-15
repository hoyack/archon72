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
│   ├── run_secretary.py         # Extract recommendations from transcript
│   ├── run_consolidator.py      # Consolidate motions into mega-motions
│   ├── run_review_pipeline.py   # Run Motion Review Pipeline
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
│       │   │   └── secretary_crewai_adapter.py # Secretary agent
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
| `src/application/services/secretary_service.py` | Extracts recommendations from Conclave transcripts |
| `src/application/services/motion_consolidator_service.py` | Consolidates 60+ motions into ~12 mega-motions |
| `src/application/services/motion_review_service.py` | Orchestrates 6-phase motion review pipeline |
| `src/domain/models/conclave.py` | Domain models for Motion, Vote, ConclaveSession, DebateEntry |
| `src/domain/models/review_pipeline.py` | Domain models for review pipeline (RiskTier, ReviewResponse, etc.) |
| `src/infrastructure/adapters/external/crewai_adapter.py` | CrewAI integration for LLM agent invocation |
| `src/infrastructure/adapters/external/reviewer_crewai_adapter.py` | Per-Archon LLM-powered motion reviewer |
| `scripts/run_conclave.py` | CLI to run formal Conclave with motions and voting |
| `scripts/run_review_pipeline.py` | CLI to run motion review pipeline with real or simulated agents |
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
│  5. [Review Pipeline] → Per-Archon review with LLM agents      │
│         │              Triage by implicit support               │
│         │              Panel deliberation for contested         │
│         ▼                                                       │
│  6. [Next Conclave] → Ratify reviewed mega-motions             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

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

# Real LLM-powered Archon reviews (requires Ollama)
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

All local models use Ollama via `OLLAMA_HOST` environment variable.

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
