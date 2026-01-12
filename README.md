# Archon 72

Constitutional AI Governance System with 72 Agents

## Overview

Archon 72 is a witnessed, transparent, and accountable AI governance system built on constitutional principles. It features:

- **72 Concurrent Agents** - Multi-agent deliberation and collective decision-making
- **Cryptographic Witnessing** - All actions are signed and verifiable
- **Halt-Over-Degrade Philosophy** - System integrity takes precedence over availability
- **Append-Only Event Store** - Immutable audit trail with hash-chaining

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
