# Run the Full Pipeline (Two Wheels Architecture)

This guide documents the pipeline architecture, which consists of two distinct loops:

1. **Execution Loop** (Wheel 2): Conclave mandates flow directly to Executive for implementation
2. **Discovery Loop** (Wheel 1): Emergent recommendations from debate flow through review before returning to Conclave

## Two Wheels Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  WHEEL 2: EXECUTION LOOP                                                    │
│  (Mandates become reality)                                                  │
│                                                                             │
│  Conclave PASS → Registrar → Executive → Administrative → Earl Tasking     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  WHEEL 1: DISCOVERY LOOP                                                    │
│  (Emergent recommendations need approval)                                   │
│                                                                             │
│  Debate → Secretary → Consolidator → Review → Conclave (for voting)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key insight**: A motion that passes Conclave has already been debated, voted on, and ratified. It should flow directly to execution—not through Secretary/Consolidator/Review again.

## Wheel 2: Execution Loop (Mandate Path)

When Conclave passes a motion, execute it directly:

```bash
# 1. Conclave votes on motion(s)
python scripts/run_conclave.py

# 2. Direct execution (auto-registers mandates and runs Executive)
python scripts/run_executive_pipeline.py --from-conclave _bmad-output/conclave --mode llm
```

Or with explicit Registrar step for audit/inspection:

```bash
# 1. Conclave
python scripts/run_conclave.py

# 2. Register mandates in ledger
python scripts/run_registrar.py _bmad-output/conclave

# 3. Execute from ledger
python scripts/run_executive_pipeline.py --from-ledger _bmad-output/motion-ledger/<session_id> --mode llm
```

## Wheel 1: Discovery Loop (Recommendation Path)

Emergent recommendations from debate need Conclave approval:

```bash
# 1. Extract recommendations from debate
python scripts/run_secretary.py _bmad-output/conclave/<transcript>.md --enhanced

# 2. Consolidate into mega-motions
python scripts/run_consolidator.py

# 3. Pre-screen before Conclave
python scripts/run_review_pipeline.py --real-agent

# 4. Conclave votes on recommendations
python scripts/run_conclave.py
# → If passed, they become mandates (Wheel 2)
```

---

## Detailed Step-by-Step

**v2 Executive Pipeline** features:
- **LLM-powered President deliberation** (per-Archon LLM bindings)
- **Epics with acceptance intent** (no story points)
- **Blocker classification and disposition** (ESCALATE_NOW, DEFER_DOWNSTREAM, MITIGATE_IN_EXECUTIVE)
- **Downstream artifacts** (conclave queue items, discovery task stubs)

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
- Conclave results: `conclave-results-<session_id>-<timestamp>.json` (structured vote records)
- Motion queue under `_bmad-output/motion-queue/`

The `conclave-results-*.json` file contains:
- `passed_motions[]`: Motions that received supermajority approval
- `failed_motions[]`: Motions that were voted down
- `died_no_second[]`: Motions that no King would second
- Full vote records with ayes/nays/abstentions

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

### 4b) Run Registrar (record mandates in ledger)

The Registrar records passed Conclave motions in an immutable ledger:

```bash
python scripts/run_registrar.py _bmad-output/conclave
```

Accepts:
- A Conclave output directory (finds latest `conclave-results-*.json`)
- A specific `conclave-results-*.json` file
- A checkpoint JSON file

Outputs:
- Motion Ledger under `_bmad-output/motion-ledger/`
- `ledger.json`: Index of all recorded mandates
- `mandates/<mandate_id>.json`: Individual mandate files
- Session output: `ratified_mandates.json`

Note: The Registrar enforces immutability—existing mandate files are never overwritten.

### 5) Run Executive Pipeline (v2: epics + work packages + blockers)

The Executive pipeline transforms mandates or ratified motions into execution plans via President deliberation.

**From Conclave (recommended):** Auto-registers mandates and executes:
```bash
python scripts/run_executive_pipeline.py --from-conclave _bmad-output/conclave --mode llm
```

**From Ledger:** Execute from previously registered mandates:
```bash
python scripts/run_executive_pipeline.py --from-ledger _bmad-output/motion-ledger/<session_id> --mode llm
```

**From Review Pipeline:** Legacy path via Secretary → Consolidator → Review:
```bash
python scripts/run_executive_pipeline.py --mode llm
```

**With blocker workup (E2.5):** Enable LLM-powered blocker classification and disposition:
```bash
python scripts/run_executive_pipeline.py --from-conclave _bmad-output/conclave --mode llm --llm-blocker-workup
```

Flags:
- `--from-conclave <path>`: Execute mandates directly from Conclave output (runs Registrar automatically).
- `--from-ledger <path>`: Execute from Motion Ledger session directory.
- `--mode {manual,llm,auto}`: Deliberation mode (default: `auto`).
- `--llm-blocker-workup`: Enable E2.5 blocker workup (classifies blockers, assigns dispositions).
- `--require-gates`: Exit with error if any gates fail.
- `--verbose`: Verbose logging.

Outputs (v2):
- Executive plans under `_bmad-output/executive/<session_id>/`
- `execution_plan.json`: Contains `epics[]`, `work_packages[]`, `blockers[]`
- `execution_plan_handoff.json`: Handoff to Administration with gate status
- `blocker_workup_result.json`: Blocker classification results (if `--llm-blocker-workup`)
- `peer_review_summary.json`: Peer review findings (if `--llm-blocker-workup`)
- `conclave_queue_items.json`: Items requiring Conclave escalation
- `discovery_task_stubs.json`: Discovery tasks for deferred blockers

v2 Schema Changes:
- **Epics**: High-level work units with `success_signals` and `mapped_motion_clauses` (traceability)
- **Work Packages**: Thin scope descriptions (no story points, estimates, or FR/NFR)
- **Blockers**: Classified by `blocker_class` with `disposition` (ESCALATE_NOW, DEFER_DOWNSTREAM, MITIGATE_IN_EXECUTIVE)

Role-based overrides (optional, `.env`):
```bash
# Direct model specification (v2 preferred)
PRESIDENT_DELIBERATOR_MODEL=ollama/qwen3:latest
PRESIDENT_DELIBERATOR_TEMPERATURE=0.3

# Or legacy Archon UUID
PRESIDENT_DELIBERATOR_ARCHON_ID=<archon-uuid>

# For draft generation
EXECUTION_PLANNER_ARCHON_ID=<archon-uuid>
```

### 5b) Legacy Execution Planner (v1)

For v1-style task-based planning (deprecated):

```bash
python scripts/run_execution_planner.py
```

LLM-powered:
```bash
python scripts/run_execution_planner.py --real-agent _bmad-output/review-pipeline/<session_id>
```

Outputs:
- Execution plans under `_bmad-output/execution-planner/`
- Blockers summary: `blockers_summary.json`

### 6) Run Conclave again (consume blockers/escalations)

**From v2 Executive pipeline (conclave queue items):**
```bash
python scripts/run_conclave.py --blockers-path _bmad-output/executive/<session_id>
```

This loads `conclave_queue_items.json` which contains blocker escalations requiring Conclave resolution.

**From v1 Execution planner (legacy blockers):**
```bash
python scripts/run_conclave.py --blockers-path _bmad-output/execution-planner/<session_id>
```

This loads agenda items from `blockers_summary.json`.

## Run Options

### Wheel 2: Direct Mandate Execution (recommended)

Execute passed Conclave motions directly:

```bash
# Conclave votes on motion
python scripts/run_conclave.py

# Direct execution (auto-registers and runs)
python scripts/run_executive_pipeline.py --from-conclave _bmad-output/conclave --mode llm

# Continue to Administration...
python scripts/run_administrative_pipeline.py
```

### Wheel 2: With Explicit Registrar

For audit/inspection of mandates before execution:

```bash
python scripts/run_conclave.py
python scripts/run_registrar.py _bmad-output/conclave
# Inspect: cat _bmad-output/motion-ledger/<session_id>/ratified_mandates.json
python scripts/run_executive_pipeline.py --from-ledger _bmad-output/motion-ledger/<session_id> --mode llm
```

### Wheel 1: Discovery Loop

Process emergent recommendations from debate:

```bash
# Extract recommendations from debate transcript
python scripts/run_secretary.py _bmad-output/conclave/<transcript>.md --enhanced

# Consolidate and review
python scripts/run_consolidator.py
python scripts/run_review_pipeline.py --real-agent

# Submit to Conclave for voting
python scripts/run_conclave.py
# → If passed, use Wheel 2 to execute
```

### Combined: Both Wheels

Full session with mandate execution + discovery:

```bash
# 1. Conclave votes on motion(s)
python scripts/run_conclave.py

# 2. WHEEL 2: Execute passed mandates
python scripts/run_executive_pipeline.py --from-conclave _bmad-output/conclave --mode llm

# 3. WHEEL 1: Discover emergent recommendations from debate
python scripts/run_secretary.py _bmad-output/conclave/<transcript>.md --enhanced
python scripts/run_consolidator.py
python scripts/run_review_pipeline.py --real-agent
# → Recommendations queued for next Conclave

# 4. Handle escalated blockers from Executive
python scripts/run_conclave.py --blockers-path _bmad-output/executive/<session_id>
```

### Legacy: Review Pipeline Path (deprecated)

For backwards compatibility with pre-Registrar flow:

```bash
python scripts/run_conclave.py
python scripts/run_secretary.py _bmad-output/conclave/<transcript>.md --enhanced
python scripts/run_consolidator.py
python scripts/run_review_pipeline.py --real-agent
python scripts/run_executive_pipeline.py --mode llm  # from ratification_results.json
python scripts/run_conclave.py --blockers-path _bmad-output/executive/<session_id>
```

## Notes and Gotchas

### Executive Pipeline (v2)

- **Auto mode** (`--mode auto`, default) checks for manual artifacts in the inbox before using LLM.
- **Epics are required** in v2 mode; plans without epics fail the Legibility gate.
- **Blocker disposition rules**:
  - `INTENT_AMBIGUITY` blockers must have `ESCALATE_NOW` disposition and generate a conclave queue item.
  - `DEFER_DOWNSTREAM` blockers must have verification tasks and generate discovery task stubs.
  - `MITIGATE_IN_EXECUTIVE` blockers must have mitigation notes.
- **Forbidden fields**: v2 artifacts cannot contain `story_points`, `estimate`, `hours`, `FR`, `NFR`, or `detailed_requirements` (these belong in Administration).
- Set `PRESIDENT_DELIBERATOR_MODEL` for direct model specification (e.g., `ollama/qwen3:latest`).
- Set `PRESIDENT_DELIBERATOR_TEMPERATURE` to override temperature (default: 0.3).

### General

- `scripts/run_review_pipeline.py --real-agent` only uses real LLM reviews if the reviewer agent initializes successfully.
- `scripts/run_executive_pipeline.py` consumes `ratification_results.json` from the review pipeline output directory.
- If you pass `--triage-only`, no review/ratification files are generated.
- For role-based overrides, set the Archon UUIDs in `.env` and ensure those IDs exist in `docs/archons-base.json`.
- Async vote validation (Spec v2) requires `SECRETARY_TEXT_ARCHON_ID`, `SECRETARY_JSON_ARCHON_ID`,
  and `WITNESS_ARCHON_ID`. If any are missing, Conclave falls back to sync validation.
- `ENABLE_ASYNC_VALIDATION=true` enables the in-process async validator in `run_conclave.py`.
  `KAFKA_ENABLED=true` only publishes audit events; Kafka health should be verified first.
- If you hit Ollama Cloud rate limits, lower `--voting-concurrency` and/or set
  `OLLAMA_MAX_CONCURRENT` plus `OLLAMA_RETRY_*` backoff settings.
