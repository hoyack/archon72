# Run the Full Pipeline (Conclave → Secretary → Consolidator → Review → Planner → Conclave)

This guide documents a full end-to-end cycle, including the circular return to Conclave with execution planner blockers.

## Overview of the Cycle

1. Run Conclave to produce a transcript and motions queue.
2. Run Secretary to extract recommendations and motions from the transcript.
3. Run Consolidator to merge motions into mega-motions.
4. Run Review Pipeline to triage, review, deliberate, and ratify.
5. Run Execution Planner to turn ratified motions into tasks/blockers.
6. Run Conclave again to consume the new blockers as agenda items.

## Step-by-Step Commands

### 0) Start Docker dependencies (Postgres, Redis, Redpanda)

```bash
# Start core services needed by Conclave + Kafka audit trail
docker compose up -d db redis redpanda redpanda-console

# Create Kafka topics required for async vote validation + audit trail
python scripts/create_kafka_topics.py --bootstrap-servers localhost:19092

# Verify topic configuration
python scripts/create_kafka_topics.py --bootstrap-servers localhost:19092 --verify

# Sanity check Redpanda health
docker exec -it archon72-redpanda rpk cluster health
```

Optional: start async-validation workers (validator workers + consensus aggregator):
```bash
docker compose --profile async-validation up -d
```

### 1) Run Conclave (initial session)

```bash
python scripts/run_conclave.py
```

Common flags:
- `--session <name>`: Override session name.
- `--resume <checkpoint.json>`: Resume a prior session.
- `--motion "<title>"`: Title for new business.
- `--motion-text "<full text>"`: Inline motion body.
- `--motion-file <path>`: Motion text file (overrides `--motion-text`).
- `--motion-type constitutional|policy|procedural|open`: Motion type (default: `open`).
- `--debate-rounds <int>`: Max debate rounds (default: 3).
- `--quick`: Quick mode (1 debate round).
- `--voting-concurrency <int>`: Max archons voting in parallel (`0` = unlimited, default `1`).
- `--no-queue`: Skip motion queue loading.
- `--queue-max-items <int>`: Max queued items (default: 5).
- `--queue-min-consensus critical|high|medium|low|single`: Min consensus tier.
- `--no-blockers`: Skip execution planner blockers.
- `--blockers-path <path>`: Path to `blockers_summary.json` or planner session dir.

Outputs:
- Transcript under `_bmad-output/conclave/`
- Motion queue under `_bmad-output/motion-queue/`

Async validation (Spec v2) example:
```bash
ENABLE_ASYNC_VALIDATION=true KAFKA_ENABLED=true \
KAFKA_BOOTSTRAP_SERVERS=localhost:19092 SCHEMA_REGISTRY_URL=http://localhost:18081 \
python scripts/run_conclave.py --quick --voting-concurrency 8 --no-queue --no-blockers
```

Async validation summary (Spec v2):
- **Secretaries** (`SECRETARY_TEXT_ARCHON_ID`, `SECRETARY_JSON_ARCHON_ID`) determine the vote.
- **Witness** (`WITNESS_ARCHON_ID`) records agreement/dissent and adjudicates.
- Validation runs in-process with bounded concurrency; reconciliation is enforced at adjournment
  (`RECONCILIATION_TIMEOUT`).

### 2) Run Secretary (extract recommendations/motions)

```bash
python scripts/run_secretary.py _bmad-output/conclave/<transcript>.md --enhanced
```

Flags:
- `--enhanced`: Use LLM-enhanced extraction (recommended).
- `--verbose`: Verbose CrewAI logging.
- `--session-name <name>`: Override session name.

Outputs:
- Report and checkpoints under `_bmad-output/secretary/`

Role-based overrides (optional, `.env`):
- `SECRETARY_TEXT_ARCHON_ID=<archon-uuid>`
- `SECRETARY_JSON_ARCHON_ID=<archon-uuid>`

### 3) Run Consolidator (merge into mega-motions)

```bash
python scripts/run_consolidator.py
```

Flags:
- `--target <int>`: Target mega-motion count (default: 12).
- `--verbose`: Verbose LLM logging.
- `--basic`: Skip novelty/summary/acronym steps.
- `--no-novelty`: Skip novelty detection.
- `--no-summary`: Skip summary generation.
- `--no-acronyms`: Skip acronym extraction.

Outputs:
- Consolidated motions under `_bmad-output/consolidator/`

Role-based override (optional, `.env`):
- `CONSOLIDATOR_ARCHON_ID=<archon-uuid>`

### 4) Run Review Pipeline (triage, reviews, ratification)

Simulated (default):
```bash
python scripts/run_review_pipeline.py
```

Real-agent reviews:
```bash
python scripts/run_review_pipeline.py --real-agent
```

Flags:
- `--triage-only`: Only triage, no reviews.
- `--no-simulate`: Skip simulated reviews (triage+packets only).
- `--real-agent`: Use real Archon LLM reviews (requires LLM setup).
- `--verbose`: Verbose logging.

Outputs:
- Review pipeline output under `_bmad-output/review-pipeline/`
- Ratification results: `ratification_results.json`

Note: If reviewer agent init fails, the script falls back to simulation.

### 5) Run Execution Planner (tasks + blockers)

Heuristic mode:
```bash
python scripts/run_execution_planner.py
```

LLM-powered:
```bash
python scripts/run_execution_planner.py --real-agent _bmad-output/review-pipeline/<session_id>
```

Flags:
- `--real-agent`: Use LLM-powered planner.
- `--verbose`: Verbose logging.

Outputs:
- Execution plans under `_bmad-output/execution-planner/`
- Blockers summary: `blockers_summary.json`

Role-based override (optional, `.env`):
- `EXECUTION_PLANNER_ARCHON_ID=<archon-uuid>`

### 6) Run Conclave again (consume blockers)

```bash
python scripts/run_conclave.py --blockers-path _bmad-output/execution-planner/<session_id>
```

This will load agenda items from `blockers_summary.json`.

## Circular Run Options

### Full circular run (real LLMs)

```bash
python scripts/run_conclave.py
python scripts/run_secretary.py _bmad-output/conclave/<transcript>.md --enhanced
python scripts/run_consolidator.py
python scripts/run_review_pipeline.py --real-agent
python scripts/run_execution_planner.py --real-agent _bmad-output/review-pipeline/<session_id>
python scripts/run_conclave.py --blockers-path _bmad-output/execution-planner/<session_id>
```

### Full circular run (real agents end-to-end)

```bash
python scripts/run_conclave.py
python scripts/run_secretary.py _bmad-output/conclave/<transcript>.md --enhanced
python scripts/run_consolidator.py
python scripts/run_review_pipeline.py --real-agent
python scripts/run_execution_planner.py --real-agent _bmad-output/review-pipeline/<session_id>
python scripts/run_conclave.py --blockers-path _bmad-output/execution-planner/<session_id> --real-agent
```

### Full circular run (simulation)

```bash
python scripts/run_conclave.py --quick
python scripts/run_secretary.py _bmad-output/conclave/<transcript>.md
python scripts/run_consolidator.py --basic
python scripts/run_review_pipeline.py
python scripts/run_execution_planner.py
python scripts/run_conclave.py --blockers-path _bmad-output/execution-planner/<session_id>
```

## Notes and Gotchas

- `scripts/run_review_pipeline.py --real-agent` only uses real LLM reviews if the reviewer agent initializes successfully.
- `scripts/run_execution_planner.py` consumes `ratification_results.json` from the review pipeline output directory.
- If you pass `--triage-only`, no review/ratification files are generated.
- For role-based overrides, set the Archon UUIDs in `.env` and ensure those IDs exist in `docs/archons-base.json`.
- Async vote validation (Spec v2) requires `SECRETARY_TEXT_ARCHON_ID`, `SECRETARY_JSON_ARCHON_ID`,
  and `WITNESS_ARCHON_ID`. If any are missing, Conclave falls back to sync validation.
- `ENABLE_ASYNC_VALIDATION=true` enables the in-process async validator in `run_conclave.py`.
  `KAFKA_ENABLED=true` only publishes audit events; Kafka health should be verified first.
- If you hit Ollama Cloud rate limits, lower `--voting-concurrency` and/or set
  `OLLAMA_MAX_CONCURRENT` plus `OLLAMA_RETRY_*` backoff settings.
