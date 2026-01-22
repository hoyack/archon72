# Secretary Process Documentation (`scripts/run_secretary.py`)

This document explains, in detail, what the **Secretary stage** does, what it reads/writes, and what happens under the hood in code. It also includes practical notes on model selection (including role-based Archon-ID overrides), auditability, and performance.

Primary entrypoints:
- CLI: `scripts/run_secretary.py`
- Service: `src/application/services/secretary_service.py`
- Enhanced agent port: `src/application/ports/secretary_agent.py`
- CrewAI implementation: `src/infrastructure/adapters/external/secretary_crewai_adapter.py`
- Secretary LLM config (defaults): `config/secretary-llm-config.yaml`

---

## What This Stage Is For

The Secretary stage is post-processing for a completed Conclave transcript. Its job is to turn the transcript into downstream-friendly artifacts:

- Extract concrete recommendations from Archon speeches
- Cluster similar recommendations into themes
- Produce a **Motion Seed queue** (candidates for next Conclave)
- Produce a **task registry** (operational work items that don’t require a vote)
- Detect conflicting positions (where stances oppose on overlapping topics)

There are two modes:

1) **Regex-based** (fast, deterministic, minimal dependencies)
2) **LLM-enhanced** via CrewAI (more nuanced extraction/clustering; slower and requires LLM setup)

---

## Inputs (What It Reads)

### 1) Conclave transcript markdown

You pass a transcript path, typically produced by `scripts/run_conclave.py`:

- `_bmad-output/conclave/transcript-<session_uuid>-<timestamp>.md`

The Secretary parser expects Conclave’s transcript structure, especially speech headers like:

- `**[HH:MM:SS] Archon Name:**`

The regex-mode extractor intentionally ignores:
- Procedural entries like `**[HH:MM:SS] [PROCEDURAL] ...`
- Vote lines containing `Vote: AYE|NAY|ABSTAIN`

### 2) Environment (`.env`)

`scripts/run_secretary.py` loads `.env` via `python-dotenv`.

Common env vars used across the repo (relevant here):
- `OLLAMA_HOST` (when running local provider models via Ollama)
- Provider API keys (if your chosen LLM configs use them), e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

Role-based overrides (optional, recommended if you want dynamic model routing):
- `SECRETARY_TEXT_ARCHON_ID=<archon-uuid>`
- `SECRETARY_JSON_ARCHON_ID=<archon-uuid>`

These select **which Archon profile’s** `llm_config` will be used for each Secretary role (text vs JSON). See “Model selection” below.

### 3) Secretary default LLM config (enhanced mode)

In `--enhanced` mode, the Secretary starts by loading defaults from:
- `config/secretary-llm-config.yaml`

If that file is missing, hard-coded defaults from `src/domain/models/secretary_agent.py` are used.

### 4) Archon profiles and LLM bindings (role overrides)

If you set `SECRETARY_TEXT_ARCHON_ID` or `SECRETARY_JSON_ARCHON_ID`, `scripts/run_secretary.py` resolves those IDs via:
- `create_archon_profile_repository()` (loads `docs/archons-base.json` and merges bindings such as `config/archon-llm-bindings.yaml`)

This is how role-based routing stays consistent with the rest of the pipeline.

---

## Outputs (What It Writes)

### 1) Main report directory

`SecretaryService.save_report()` writes a per-session directory:

- `_bmad-output/secretary/<source_session_uuid>/`

Files:
- `recommendations-register.md`: human-readable clusters grouped by consensus tier
- `motion-queue.md`: human-readable Motion Seed queue
- `secretary-report.json`: summary stats (counts and metadata)
- `recommendations.json`: full extracted recommendations (JSON)
- `motion-queue.json`: queued motions (JSON)

### 2) Enhanced-mode checkpoints (audit trail)

If checkpoints are enabled (default), the CrewAI adapter also writes:

- `_bmad-output/secretary/checkpoints/<session_uuid>_<epoch>_<step>.json`

Steps written by `SecretaryCrewAIAdapter.process_full_transcript()`:
- `01_extraction`
- `02_validation`
- `03_clustering`
- `04_conflicts`
- `05_motions`

Notes:
- These checkpoints are currently **write-only** (they’re not used to auto-resume inside the adapter today), but they provide an auditable trace of intermediate outputs.

### 3) Motion Queue import (next Conclave input)

After saving the report, `scripts/run_secretary.py` attempts to import the Motion Seed queue into the persistent queue store:

- `_bmad-output/motion-queue/active-queue.json`
- `_bmad-output/motion-queue/archive/…` (later, after Conclave votes)

This is performed via `MotionQueueService.import_from_report(report)`.

---

## CLI Flags and Behavior

### Basic usage

Regex mode (fast):
```bash
python scripts/run_secretary.py _bmad-output/conclave/transcript-<...>.md
```

Enhanced mode (LLM):
```bash
python scripts/run_secretary.py _bmad-output/conclave/transcript-<...>.md --enhanced
```

Flags:
- `--enhanced`: Use LLM-enhanced extraction via CrewAI (falls back to regex mode if no agent is configured)
- `--verbose` / `-v`: Verbose CrewAI logging (enhanced mode only)
- `--session-name <name>`: Override the session name stored in Secretary outputs

Session ID/name inference:
- The script tries to infer `session_id` + a human-readable `session_name` from a transcript filename like `transcript-<uuid>-<timestamp>.md`.
- If it can’t parse a UUID, it generates a new UUID for the Secretary report metadata.

---

## Model Selection (How the LLM Is Chosen)

Enhanced mode uses a **dual-model design**:
- **Text model**: extraction tasks (natural language understanding)
- **JSON model**: structured output (validation/clustering/motion formatting)

### Default path (YAML-configured)

If you set no role-based overrides, configs come from:
- `config/secretary-llm-config.yaml` → `load_secretary_config_from_yaml()`

### Role-based override path (Archon-ID routing)

If you set:
- `SECRETARY_TEXT_ARCHON_ID=<uuid>`
- `SECRETARY_JSON_ARCHON_ID=<uuid>`

Then `scripts/run_secretary.py`:
1. Loads YAML defaults
2. Resolves each env UUID to an Archon profile via the profile repository
3. Replaces the corresponding LLM config with `profile.llm_config`

This gives you a simple, dynamic “routing knob”:
- swap the UUID in `.env` to run the Secretary on a different model/provider without changing code
- keep a single canonical mapping source (Archon profiles / bindings)

Important: the script prints which override was applied (env var + Archon name) so it’s visible in the run log.

---

## Under the Hood: Processing Flow

### Step 0: Transcript parsing (shared)

Both modes start by reading the transcript and parsing speeches in `SecretaryService._parse_speeches()`:

- Detects speech headers: `**[HH:MM:SS] <speaker>:**`
- Collects all following lines until the next header
- Skips procedural lines and vote lines

Speaker filtering (auditability fix):
- The service attempts to load the known set of Archon names from the Archon profile repository.
- If the set is available, any transcript “speaker” not in that set is treated as non-Archon and skipped.
- The service also explicitly excludes reserved non-Archon labels:
  - `[SYSTEM]`, `SYSTEM`, `Execution Planner`
- When speakers are skipped, the service logs a structured event:
  - `transcript_speakers_skipped` with line numbers and speaker names

This prevents non-Archon transcript entries (like externally injected agenda items) from polluting supporter lists downstream.

---

## Regex Mode (Deterministic, No LLM)

Entry point:
- `SecretaryService.process_transcript(...)`

### 1) Extract recommendations per speech

For each parsed speech, `_extract_recommendations_from_speech()`:
- Applies a list of regex `EXTRACTION_PATTERNS` (recommendations section, “I recommend…”, “Establish…”, “Implement…”, etc.)
- Normalizes and truncates recommendation text by `SecretaryConfig` bounds
- Extracts clustering keywords using `extract_keywords()` (keyword-category matching)
- Creates domain objects with traceability:
  - `SourceReference` (archon name/id, rank, line number, timestamp, raw text)
  - `ExtractedRecommendation` (category/type/summary/keywords/stance)

It also deduplicates within a speech using a simple signature:
- `rec.summary.lower()[:100]`

### 2) Cluster recommendations

`cluster_recommendations()` builds clusters using:
- a simple similarity score combining:
  - category match
  - keyword overlap (Jaccard)
  - light word overlap (minus stop words)

Clusters refine their theme label after multiple members are added.

### 3) Build motion queue + tasks

For each cluster:
- If it has “enough” unique Archons (default `min_cluster_size_for_queue = 3`)
  - policy clusters become Motion Seeds (`QueuedMotion.from_cluster(...)`)
  - task clusters become `TaskItem.from_cluster(...)`

### 4) Detect conflicts

`_detect_conflicts()`:
- groups recommendations by keyword topic
- looks for pairs where:
  - one has stance `FOR`
  - another has stance `AGAINST`
  - and topical similarity crosses a low threshold

The output is a list of `ConflictingPosition` objects with traceability back to the two source recommendations.

---

## Enhanced Mode (CrewAI + LLM)

Entry points:
- CLI: `scripts/run_secretary.py --enhanced`
- Service: `SecretaryService.process_transcript_enhanced(...)`
- Agent adapter: `SecretaryCrewAIAdapter.process_full_transcript(...)`

### 1) Convert speeches into `SpeechContext`

The service converts parsed speeches into `SpeechContext` objects:
- `archon_name`, `archon_id`
- `speech_content`
- `line_start`, `line_end` (estimated)

### 2) Full LLM pipeline (adapter)

`SecretaryCrewAIAdapter.process_full_transcript()` runs a 5-step flow and writes checkpoint files after each step (if enabled):

1. **Extraction (per speech, sequential)**
   - For each speech, creates a single-task Crew with one agent and calls `crew.kickoff()` in a thread.
   - Prompts the model to output ONLY a JSON array of recommendations.
   - Parses the JSON using:
     - `strip_markdown_fence()`
     - bracket balancing extraction
     - JSON sanitization + an “aggressive cleaning” fallback

2. **Validation (sample-based)**
   - Validates a sample of extracted recommendations vs a sample of speeches.
   - Produces a confidence score and “missed_count” estimate (best-effort).

3. **Semantic clustering (batched)**
   - Clusters recommendations in batches (`CLUSTERING_BATCH_SIZE`, currently 50).
   - Each batch asks the model to output clusters as a JSON array, keyed by recommendation IDs.
   - Note: the current implementation does not merge clusters across batches, so large runs can produce overlapping themes.

4. **Conflict detection (sample-based)**
   - Asks the JSON model to identify conflicts in a sample.
   - Note: the adapter currently records the conflict count but does not map results into `ConflictingPosition` domain objects (so `conflicts` are typically empty in enhanced-mode outputs).

5. **Motion synthesis**
   - For clusters above a (currently low) supporter threshold, asks the model to generate formal motion text.
   - If JSON parsing fails, the adapter returns a fallback motion rather than failing the whole run.

### 3) Map agent results back into the Secretary report

The service then:
- sets `report.recommendations`, `report.clusters`, `report.conflict_report`
- appends agent-produced `report.motion_queue`
- derives `report.task_registry` from task-type clusters meeting the queue threshold

---

## Downstream Integration (What Uses Secretary Output)

### Consolidator

The consolidator stage typically consumes:
- `_bmad-output/secretary/checkpoints/*_05_motions.json`

This is the “Motion Seed list” that the consolidator reduces into mega-motions.

### Motion Queue → Next Conclave

If `MotionQueueService.import_from_report()` succeeds, Conclave can later pull motions from:
- `_bmad-output/motion-queue/active-queue.json`

---

## Performance Recommendations

### Choose the right mode
- Use **regex mode** for quick iterations, debugging transcript formatting, and deterministic pipelines.
- Use **enhanced mode** when you need nuanced extraction, better clustering labels, or synthesized motion text.

### Primary bottlenecks (enhanced mode)
- **Per-speech extraction is sequential** today (72 speeches → 72 LLM calls).
- **Clustering is batched** but still sequential per batch.
- JSON cleaning/parsing retries can add overhead.

### Practical optimization levers (no semantics change)
- Use faster models via `SECRETARY_TEXT_ARCHON_ID` / `SECRETARY_JSON_ARCHON_ID`.
- Keep `max_tokens` reasonable in your chosen LLM configs.
- Prefer local inference on a fast GPU (or distributed inference via per-Archon `base_url` in bindings).

### Potential code-level speedups (would require changes)
- Parallelize extraction with a bounded semaphore (e.g., 4–8 concurrent speeches), while preserving deterministic output ordering by sorting results by input speech order afterward.
- Parallelize clustering batches similarly.
- Reduce per-speech prompt size (truncate speech content more aggressively).

Rate limit caution:
- Cloud providers will enforce per-minute limits; concurrency must be tuned to avoid throttling.
- Local Ollama servers can also overload; concurrency should match hardware capacity.

---

## Troubleshooting & Common Failure Modes

### “model not found” (local / Ollama)

If you see errors like:
- `{"error":"model 'X' not found"}`

Then either:
- pull the model on your Ollama host (`ollama list` to confirm availability), or
- set `SECRETARY_TEXT_ARCHON_ID` / `SECRETARY_JSON_ARCHON_ID` to Archons bound to models that exist on the current host.

### Transcript parsing yields “missing” speakers

If a transcript speaker name doesn’t match Archon profile names exactly, it may be skipped and logged under:
- `transcript_speakers_skipped`

Fixes:
- ensure the transcript speaker names match profile names
- or fix the transcript generator / naming normalization upstream

### Re-running can create duplicate queue entries

IDs (`report_id`, `recommendation_id`, `cluster_id`, etc.) are UUIDs created at runtime.
This means:
- content may be similar between runs, but IDs will differ
- importing multiple runs into the motion queue can produce duplicates unless downstream dedup is improved

If you need clean runs, consider clearing `_bmad-output/motion-queue/active-queue.json` (or using a fresh output dir) before re-importing.

