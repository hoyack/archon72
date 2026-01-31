# Run the Legislative Pipeline (Wheel 1: Discovery Loop)

End-to-end operational guide for running the circular Discovery Loop that extracts emergent recommendations from Conclave debate and feeds them back as formal motions.

```
                          ┌──────────────┐
                   ┌─────►│  1. CONCLAVE  │─────┐
                   │      │  (Vote Queue) │     │
                   │      └──────────────┘     │ transcript
                   │                            ▼
          ┌────────────────┐            ┌──────────────┐
          │  5. CONCLAVE 2 │            │ 2. SECRETARY │
          │ (Vote Reviews) │            │  (Extract)   │
          └────────────────┘            └──────────────┘
                   ▲                            │
                   │                    motion queue
                   │                            ▼
          ┌────────────────┐            ┌──────────────┐
          │   4. REVIEW    │◄───────────│3. CONSOLIDATOR│
          │  (Ratify)      │ mega-motions│  (Merge)     │
          └────────────────┘            └──────────────┘
```

**Discovery Loop** (Wheel 1) handles emergent recommendations that need Conclave approval before execution. This differs from **Wheel 2** (Execution Loop), where passed mandates flow directly to the Executive pipeline. Motions that pass Conclave 2 graduate to Wheel 2 for implementation.

---

## Pipeline Scripts Tree

```
scripts/
├── run_full_pipeline.sh          # Master orchestrator (all 5 stages)
├── run_conclave.py               # Stage 1 & 5: Parliamentary debate + voting
├── run_secretary.py              # Stage 2: Transcript → recommendations
├── run_consolidator.py           # Stage 3: Recommendations → mega-motions
└── run_review_pipeline.py        # Stage 4: Triage, review, ratification

src/application/services/
├── conclave_service.py           # ConclaveService + ConclaveConfig
├── secretary_service.py          # SecretaryService + SecretaryConfig
├── motion_consolidator_service.py# MotionConsolidatorService
├── motion_review_service.py      # MotionReviewService (6-phase)
└── motion_queue_service.py       # MotionQueueService (persistence layer)

src/domain/models/
├── conclave.py                   # Motion, MotionType, ConclavePhase, AgendaItem
├── secretary.py                  # QueuedMotion, ConsensusLevel, SecretaryReport
└── motion_seed.py                # MotionSeed, SeedStatus, AdmissionRecord

config/
├── archon-llm-bindings.yaml      # Per-archon LLM provider config
└── secretary-llm-config.yaml     # Dual-model Secretary config

_bmad-output/
├── conclave/                     # Transcripts, results, checkpoints
├── secretary/                    # Reports, motion queues
├── consolidator/                 # Mega-motions, novel proposals
├── review-pipeline/              # Triage, ratification results
├── motion-queue/                 # active-queue.json + archive/
└── pipeline-runs/                # Per-run logs and status
```

---

## Stage-by-Stage Documentation

### Stage 1: Conclave (Initial Vote)

**Purpose:** Select motions from the queue and put them through parliamentary debate with all 72 Archons. Each motion requires a King's second to proceed to debate, then a 2/3 supermajority to pass.

**Command:**
```bash
poetry run python scripts/run_conclave.py \
    --queue-max-items 5 \
    --queue-min-consensus low \
    --debate-rounds 3 \
    --voting-concurrency 3 \
    --no-blockers
```

**All flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--session NAME` | auto | Session name |
| `--resume FILE` | - | Resume from checkpoint |
| `--motion TITLE` | - | Custom motion title |
| `--motion-text TEXT` | - | Inline motion body |
| `--motion-file FILE` | - | Load motion from file (overrides --motion-text) |
| `--motion-type TYPE` | `open` | `constitutional`, `policy`, `procedural`, `open` |
| `--debate-rounds N` | `3` | Max debate rounds |
| `--quick` | off | 1 debate round, 60s timeout |
| `--voting-concurrency N` | `1` | Parallel voters (0 = unlimited) |
| `--no-queue` | off | Skip loading motion queue |
| `--queue-max-items N` | `5` | Max items to pull from queue |
| `--queue-min-consensus` | `medium` | Min tier: `critical`, `high`, `medium`, `low`, `single` |
| `--no-blockers` | off | Skip execution planner blockers |
| `--blockers-path PATH` | auto | Path to `blockers_summary.json` |

**Input files:**
- `_bmad-output/motion-queue/active-queue.json` (motion queue state)
- `docs/archons-base.json` (72 Archon profiles)
- `config/archon-llm-bindings.yaml` (per-Archon LLM config)

**Output files:**
- `_bmad-output/conclave/transcript-{uuid}-{timestamp}.md`
- `_bmad-output/conclave/conclave-results-{uuid}-{timestamp}.json`
- `_bmad-output/conclave/conclave-checkpoint-{stage}.json`

**Sample output** (`conclave-results-*.json`, abbreviated):
```json
{
  "session_id": "6571eba0-872b-47a6-8ab1-b3ee83c1fcdb",
  "passed_motions": [],
  "failed_motions": [
    {
      "title": "Motion to Mandate Sunset Clauses for AI Governance",
      "ayes": 6, "nays": 60, "abstentions": 6
    }
  ],
  "died_no_second": []
}
```

**Key env vars:**
- `OLLAMA_HOST` - Ollama endpoint (default: `http://192.168.1.104:11434`)
- `AGENT_TIMEOUT_SECONDS` - Per-agent LLM timeout (default: 60 in quick mode)
- `AGENT_TIMEOUT_MAX_ATTEMPTS` - Retry count on timeout
- `WITNESS_ARCHON_ID`, `SECRETARY_TEXT_ARCHON_ID`, `SECRETARY_JSON_ARCHON_ID` - Vote validation archons

---

### Stage 2: Secretary (Extract Recommendations)

**Purpose:** Analyze the debate transcript to extract recommendations, cluster them by theme, compute consensus levels, and queue motions for the next Conclave cycle.

**Command:**
```bash
poetry run python scripts/run_secretary.py \
    _bmad-output/conclave/transcript-{uuid}-{timestamp}.md \
    --enhanced --verbose
```

**All flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `TRANSCRIPT_PATH` | required | Positional: path to transcript `.md` |
| `--enhanced` | off | Use LLM-enhanced extraction (vs regex-only) |
| `--verbose`, `-v` | off | Verbose CrewAI logging |
| `--session-name NAME` | auto | Override session name |

**Input files:**
- Conclave transcript from Stage 1

**Output files:**
- `_bmad-output/secretary/{session_id}/secretary-report.json`
- `_bmad-output/secretary/{session_id}/motion-queue.json`
- `_bmad-output/secretary/{session_id}/recommendations.json`
- `_bmad-output/secretary/checkpoints/` (intermediate state)

**Sample output** (abbreviated `secretary-report.json` metrics):
```json
{
  "total_speeches_analyzed": 735,
  "total_recommendations_extracted": 3472,
  "clusters": "261 clusters",
  "consensus_levels": {
    "critical": 36, "high": 16, "medium": 33,
    "low": 65, "single": 111
  },
  "processing_duration_seconds": 5129.6
}
```

**Key env vars:**
- `SECRETARY_TEXT_ARCHON_ID` - Override text extraction Archon
- `SECRETARY_JSON_ARCHON_ID` - Override JSON clustering Archon

**Configuration:** `config/secretary-llm-config.yaml` defines two models:
- `text_model` - Natural language extraction (temp 0.3, 4096 tokens)
- `json_model` - Structured JSON clustering (temp 0.1, 8192 tokens)

---

### Stage 3: Consolidator (Merge into Mega-Motions)

**Purpose:** Reduce potentially hundreds of motion seeds into a manageable set of mega-motions through semantic clustering, novelty detection, and summary generation.

**Command:**
```bash
poetry run python scripts/run_consolidator.py --verbose
```

**All flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `CHECKPOINT` | auto-detect | Optional positional: secretary report or checkpoint path |
| `--target N`, `-t` | `12` | Target mega-motion count |
| `--verbose`, `-v` | off | Verbose LLM logging |
| `--basic` | off | Skip novelty, summary, and acronym steps |
| `--no-novelty` | off | Skip novelty detection |
| `--no-summary` | off | Skip conclave summary generation |
| `--no-acronyms` | off | Skip acronym registry extraction |

**Input files:**
- `_bmad-output/secretary/{session_id}/secretary-report.json` (auto-detected)
- OR `_bmad-output/secretary/checkpoints/*_05_motions.json`

**Output files:**
- `_bmad-output/consolidator/{session_id}/mega-motions.json`
- `_bmad-output/consolidator/{session_id}/consolidation-report.json`
- `_bmad-output/consolidator/{session_id}/novel_proposals.json`

**Sample output** (abbreviated):
```json
{
  "original_motion_count": 150,
  "mega_motions": 10,
  "consolidation_ratio": "6.7%",
  "consensus_tiers": { "HIGH": 9, "MEDIUM": 1 },
  "archon_coverage_per_motion": "51-73 archons"
}
```

**Key env vars:**
- `CONSOLIDATOR_ARCHON_ID` - Override consolidator Archon UUID

---

### Stage 4: Review Pipeline (Triage & Ratification)

**Purpose:** Process mega-motions through a 6-phase review pipeline: risk triage, Archon assignment, review collection, consensus aggregation, panel deliberation, and ratification voting.

**Command:**
```bash
poetry run python scripts/run_review_pipeline.py --real-agent --verbose
```

**All flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `CONSOLIDATOR_PATH` | auto-detect | Optional positional: consolidator output dir |
| `--verbose`, `-v` | off | Verbose logging |
| `--triage-only` | off | Phase 1 only |
| `--no-simulate` | off | Skip simulated reviews (triage + packets only) |
| `--real-agent` | off | Use real LLM Archons (requires LLM setup) |
| `--include-deferred` | off | Include deferred proposals as high-risk inputs |

**6 Phases:**
1. **Triage** - Risk assessment by implicit support ratio and conflict detection
2. **Packet Generation** - Assign reviews to specific Archons
3. **Review Collection** - Gather Archon responses (simulated or real LLM)
4. **Aggregation** - Consensus building (2-of-3 supermajority)
5. **Panel Deliberation** - Convene panels for contested HIGH-risk motions
6. **Ratification** - Final votes (ratified, amended, rejected, deferred)

**Input files:**
- `_bmad-output/consolidator/{session_id}/mega-motions.json`
- `_bmad-output/consolidator/{session_id}/novel_proposals.json`

**Output files:**
- `_bmad-output/review-pipeline/{session_id}/triage_results.json`
- `_bmad-output/review-pipeline/{session_id}/review_packets.json`
- `_bmad-output/review-pipeline/{session_id}/panel_deliberations.json`
- `_bmad-output/review-pipeline/{session_id}/ratification_results.json`
- `_bmad-output/review-pipeline/{session_id}/motion_status_summary.json`

**Sample output** (`ratification_results.json`, abbreviated):
```json
{
  "votes": [
    {
      "mega_motion_title": "Mandatory AI Governance Attribution Framework",
      "outcome": "ratified",
      "yeas": 69, "nays": 2, "abstentions": 1,
      "threshold_type": "supermajority",
      "threshold_required": 36,
      "threshold_met": true
    }
  ]
}
```

---

### Stage 5: Conclave 2 (Circular Completion)

**Purpose:** Vote on the ratified recommendations from the review pipeline. This closes the Discovery Loop. Passed motions graduate to Wheel 2 (Execution Loop) for implementation.

The command is identical to Stage 1 -- it pulls from the same `active-queue.json`, which now contains newly imported motions from the Secretary and Review pipeline.

**Command:**
```bash
poetry run python scripts/run_conclave.py \
    --queue-max-items 5 \
    --queue-min-consensus low \
    --debate-rounds 3 \
    --voting-concurrency 3 \
    --no-blockers
```

---

## Full Commands to Run with Real LLMs

### Prerequisites

1. **Ollama** running with models pulled:
   ```bash
   # Verify Ollama is reachable
   curl -s http://192.168.1.104:11434/api/tags | python3 -c "import sys,json; print(len(json.load(sys.stdin)['models']), 'models')"

   # Required models (based on archon-llm-bindings.yaml defaults)
   ollama pull qwen3:latest       # Kings, Dukes
   ollama pull llama3.2:latest    # Marquis, Presidents
   ollama pull gemma3:4b          # Strategic ranks (fallback)
   ollama pull ministral-3:latest # Secretary text + json models
   ```

2. **Poetry** environment:
   ```bash
   poetry install
   ```

3. **Motion queue** must have at least 1 pending or endorsed motion:
   ```bash
   python3 -c "
   import json
   with open('_bmad-output/motion-queue/active-queue.json') as f:
       data = json.load(f)
   pending = [m for m in data['motions'] if m.get('status') in ('pending', 'endorsed')]
   print(f'{len(pending)} pending/endorsed motions')
   "
   ```

4. **Environment** (`.env`):
   ```bash
   OLLAMA_HOST=http://192.168.1.104:11434
   # Optional cloud provider keys:
   # ANTHROPIC_API_KEY=sk-ant-...
   # OPENAI_API_KEY=sk-...
   ```

### Running the Full Pipeline (Automated)

```bash
# Full run (~6 hours with local Ollama)
./scripts/run_full_pipeline.sh

# Quick mode (1 debate round, max 2 queue items)
./scripts/run_full_pipeline.sh --quick

# Dry run (preflight checks only)
./scripts/run_full_pipeline.sh --dry-run
```

### Resuming a Failed Run

Use `--skip-to` to restart from a specific stage after failure:

```bash
# Resume from Secretary (skips Conclave 1, uses latest transcript)
./scripts/run_full_pipeline.sh --skip-to secretary

# Resume from Review (skips Conclave 1, Secretary, Consolidator)
./scripts/run_full_pipeline.sh --skip-to review

# Resume from Conclave 2 only
./scripts/run_full_pipeline.sh --skip-to conclave2
```

Valid stage names: `conclave1`, `secretary`, `consolidator`, `review`, `conclave2`

### Running Individual Stages Manually

```bash
# 1. Conclave (initial)
poetry run python scripts/run_conclave.py \
    --debate-rounds 3 --voting-concurrency 3 \
    --queue-max-items 5 --queue-min-consensus low --no-blockers

# 2. Secretary
TRANSCRIPT=$(ls -t _bmad-output/conclave/transcript-*.md | head -1)
poetry run python scripts/run_secretary.py "$TRANSCRIPT" --enhanced --verbose

# 3. Consolidator
poetry run python scripts/run_consolidator.py --verbose

# 4. Review Pipeline
poetry run python scripts/run_review_pipeline.py --real-agent --verbose

# 5. Conclave (round 2)
poetry run python scripts/run_conclave.py \
    --debate-rounds 3 --voting-concurrency 3 \
    --queue-max-items 5 --queue-min-consensus low --no-blockers
```

### Quick Mode vs Full Mode

| Parameter | Quick | Full |
|-----------|-------|------|
| Debate rounds | 1 | 3 |
| Queue max items | 2 | 5 |
| Agent timeout | 60s | 180s |
| Consolidator | `--basic` | full analysis |
| Expected duration | ~2-3 hours | ~6+ hours |

---

## Configuration Reference

### `config/archon-llm-bindings.yaml`

Maps each of the 72 Archons to an LLM provider and model. Supports rank-based defaults with per-archon overrides.

```yaml
_default:                        # Global fallback
  provider: local                # local | anthropic | openai | google | ollama_cloud
  model: gemma3:4b
  temperature: 0.5
  max_tokens: 1024
  timeout_ms: 120000

_rank_defaults:                  # Override by Aegis rank tier
  executive_director:            # Kings (9 archons)
    model: qwen3:latest
    temperature: 0.7
    max_tokens: 2048
    timeout_ms: 180000
  senior_director:               # Dukes (12 archons)
    model: qwen3:latest
    temperature: 0.6
    max_tokens: 1536
    timeout_ms: 150000
  director:                      # Marquis (18 archons)
    model: llama3.2:latest
    temperature: 0.6
    max_tokens: 1024
    timeout_ms: 120000
  managing_director:             # Presidents (12 archons)
    model: llama3.2:latest
  strategic_director:            # Princes/Earls/Knights (21 archons)
    model: gemma3:4b

# Per-archon override (by UUID)
{archon-uuid}:
  provider: anthropic
  model: claude-sonnet-4-20250514
  api_key_env: ANTHROPIC_API_KEY
  base_url: https://api.anthropic.com  # optional distributed endpoint
```

### `config/secretary-llm-config.yaml`

Dual-model configuration for the Secretary (agent #73).

```yaml
secretary:
  id: "00000000-0000-0000-0000-000000000073"
  text_model:                    # Natural language extraction
    provider: local
    model: ministral-3:latest
    temperature: 0.3
    max_tokens: 4096
    timeout_ms: 180000
  json_model:                    # Structured JSON clustering
    provider: local
    model: ministral-3:latest
    temperature: 0.1
    max_tokens: 8192
    timeout_ms: 300000
  checkpoints:
    enabled: true
    output_dir: _bmad-output/secretary/checkpoints
```

### `.env` Pipeline Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://192.168.1.104:11434` | Ollama server endpoint |
| `AGENT_TIMEOUT_SECONDS` | `60` (quick) / `180` | Per-agent LLM call timeout |
| `AGENT_TIMEOUT_MAX_ATTEMPTS` | `5` | Retry count on agent timeout |
| `AGENT_TIMEOUT_BASE_DELAY_SECONDS` | - | Backoff base delay |
| `AGENT_TIMEOUT_MAX_DELAY_SECONDS` | - | Backoff ceiling |
| `VOTE_VALIDATION_TASK_TIMEOUT` | - | Task-level timeout for vote validation |
| `WITNESS_ARCHON_ID` | - | Knight Witness for vote recording |
| `SECRETARY_TEXT_ARCHON_ID` | - | Vote validation secretary (text) |
| `SECRETARY_JSON_ARCHON_ID` | - | Vote validation secretary (JSON) |
| `CONSOLIDATOR_ARCHON_ID` | - | Override consolidator Archon |
| `ENABLE_ASYNC_VALIDATION` | `false` | In-process async vote validation |
| `SKIP_ASYNC_VALIDATION_BATCH` | `false` | Skip 3-LLM validation batch |
| `KAFKA_ENABLED` | `false` | Publish audit events to Kafka |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:19092` | Kafka brokers |
| `OLLAMA_MAX_CONCURRENT` | - | Limit concurrent Ollama requests |
| `OLLAMA_RETRY_MAX_ATTEMPTS` | `5` | Ollama retry count |
| `OLLAMA_RETRY_BASE_DELAY` | `1.0` | Ollama retry base delay (seconds) |
| `OLLAMA_RETRY_MAX_DELAY` | `60.0` | Ollama retry ceiling (seconds) |

### ConclaveConfig Fields

Key fields from `ConclaveConfig` in `src/application/services/conclave_service.py`:

| Field | Default | Description |
|-------|---------|-------------|
| `max_debate_rounds` | `5` | Debate rounds per motion |
| `speaking_time_limit_seconds` | `120` | Per-turn time limit |
| `debate_digest_interval` | `10` | Digest every N debate entries |
| `exploitation_prompt_enabled` | `true` | "Consider how this could be abused" |
| `adversarial_digest_enabled` | `true` | Pattern-matched risk analysis |
| `consensus_break_enabled` | `true` | Force opposition at 85%+ consensus |
| `consensus_break_threshold` | `0.85` | Consensus cascade trigger |
| `red_team_enabled` | `true` | Mandatory adversarial round before vote |
| `red_team_count` | `5` | Archons in red team |
| `quorum_percentage` | `0.50` | 50% for quorum |
| `supermajority_threshold` | `0.667` | 2/3 for passage |
| `voting_concurrency` | `1` | Parallel voters (0 = unlimited) |
| `checkpoint_interval_minutes` | `5` | Auto-checkpoint frequency |

---

## Data Flow & Motion Queue Lifecycle

### Motion Status Lifecycle

```
PENDING ──► ENDORSED ──► PROMOTED ──► voted (passed/failed)
    │           │                         │
    ▼           ▼                         ▼
WITHDRAWN   DEFERRED                  archived
```

- **PENDING** - New motion in queue (from Secretary import)
- **ENDORSED** - Has received King endorsement(s)
- **PROMOTED** - Selected for and promoted to a Conclave session
- **voted** - Conclave voted; result recorded, motion archived

### Queue Selection Algorithm

`MotionQueueService.select_for_conclave(max_items, min_consensus)`:

1. Filter by status: only `pending` or `endorsed`
2. Filter by consensus tier >= `min_consensus` (ordering: critical > high > medium > low > single)
3. Sort by endorsement count (descending), then by creation date (oldest first)
4. Take top `max_items`

### Circular Completion (Secretary Import)

After the Secretary processes a transcript, it calls `MotionQueueService.import_from_report()` which:

1. Reads the `SecretaryReport.motion_queue` (list of `QueuedMotion`)
2. Deduplicates against existing queue entries by title similarity
3. Inserts new motions with status `PENDING` and computed `ConsensusLevel`
4. Persists to `_bmad-output/motion-queue/active-queue.json`

This is how the loop closes: debate generates recommendations, the Secretary extracts them, and they re-enter the queue for the next Conclave session.

---

## Sample Pipeline Run (Real Data)

Data from the January 30, 2026 pipeline run (`pipeline-20260130-082357`).

### Timeline

| Stage | Duration | Key Metrics |
|-------|----------|-------------|
| Preflight | - | 507 pending motions, Ollama OK |
| Conclave 1 | 189m 15s | 5 motions debated, 72 archons |
| Secretary | 85m 35s | 735 speeches, 3,472 recommendations, 261 clusters |
| Consolidator | 4m 40s | 150 seeds → 10 mega-motions (6.7% ratio) |
| Review | 7m 48s | 9 LOW risk, 1 HIGH risk; 10/10 ratified |
| Conclave 2 | 104m 29s | Failed (crash during voting) |
| **Total** | **~391 min** | |

A subsequent run (`pipeline-20260130-145924`) completed successfully using `--skip-to conclave2` in quick mode (268m for the Conclave 2 stage alone).

### Motion Queue Growth

| Checkpoint | Total Motions | Pending | Promoted |
|------------|---------------|---------|----------|
| Pre-run | 507 | 505 | 2 |
| Post-Secretary | ~671 | ~649 | ~22 |
| Current | 669 | 647 | 22 |

Each pipeline cycle adds ~160 new motions from Secretary extraction while processing ~5 through Conclave voting.

### Secretary Extraction Breakdown

| Category | Count |
|----------|-------|
| implement | 998 |
| establish | 949 |
| amend | 704 |
| mandate | 246 |
| pilot | 225 |
| review | 177 |
| investigate | 61 |
| other | 103 |
| educate | 9 |

### Consolidation Results

10 mega-motions produced from 150 motion seeds:
- 9 at HIGH consensus tier (attribution, review, security, resource management, authority, verification, compliance, rollback mechanisms, other)
- 1 at MEDIUM tier (system architecture)
- Archon coverage: 51-73 archons per mega-motion

### Ratification Results

All 10 mega-motions ratified unanimously:
- Final aggregate vote: 69 yeas, 2 nays, 1 abstention
- Supermajority threshold: 36 of 71 eligible (met for all)

---

## Improvements & Concerns

### Voting Resilience

Conclave 2 crashed during the initial full run. The `--skip-to conclave2` workaround succeeded but required manual intervention. Checkpoint/resume should handle mid-vote failures gracefully without operator involvement.

### Retry Coverage Gaps

Individual stage scripts have timeout and retry logic, but `run_full_pipeline.sh` treats any non-zero exit as fatal. A stage-level retry wrapper (e.g., retry Conclave 1 up to N times before aborting) would reduce manual restarts.

### Queue Growth Sustainability

Each cycle extracts ~160 new motions from debate while only processing ~5 through voting. At this rate, the queue grows by ~155 motions per cycle. Without pruning, deduplication improvements, or higher throughput, the queue becomes unmanageable within a few cycles.

**Mitigation options:**
- Increase `--queue-max-items` (process more per cycle)
- Raise `--queue-min-consensus` to filter low-signal motions
- Add queue-level deduplication/archiving for stale motions
- Add a periodic queue compaction pass

### Stage Coupling and Artifact Discovery

Each stage auto-detects the previous stage's output by scanning `_bmad-output/` with `ls -t` glob patterns. This works for single-pipeline runs but breaks when multiple runs overlap or when outputs are moved. Consider explicit artifact passing via CLI args or a manifest file.

### Monitoring and Observability

`run_full_pipeline.sh` logs to `_bmad-output/pipeline-runs/{run_id}/master.log` and tracks status in `status.json`. There is no real-time dashboard, alerting, or metrics export. The `tail -f` monitoring within the script is useful but doesn't survive terminal disconnection.

### Parallel Processing Opportunities

- **Debate:** Archon contributions are sequential by rank. Parallel debate contribution (within a rank tier) could reduce Conclave duration.
- **Review packets:** Archon review collection could be fully parallelized across all assigned reviewers.
- **Multi-motion Conclave:** Currently processes motions sequentially; batch voting on independent motions could be explored.

### Motion Passage Rates

In the observed run, Conclave 2 failed both motions that reached a vote (6/60 and 13/57 splits). The adversarial deliberation mechanisms (exploitation prompts, consensus breaks, red team rounds) may be calibrated too aggressively, or the motions emerging from the Discovery Loop may need better filtering before reaching the floor.

---

## TODO

- [ ] Add stage-level retry logic to `run_full_pipeline.sh`
- [ ] Implement queue compaction / archiving for stale motions
- [ ] Add explicit artifact manifest instead of glob-based discovery
- [ ] Investigate low passage rates in Conclave 2 (adversarial tuning)
- [ ] Add pipeline metrics export (duration, queue size, pass rates) for dashboards
- [ ] Test checkpoint/resume across all failure modes (mid-debate, mid-vote, mid-extraction)
- [ ] Document distributed inference setup (multi-GPU `base_url` fleet)
- [ ] Add `--max-retries` flag to `run_full_pipeline.sh`
