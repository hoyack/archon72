# Consolidator Process Documentation (`scripts/run_consolidator.py`)

This document explains, in detail, what the **Consolidator stage** does, what it reads/writes, and what happens under the hood in code. It also covers role-based model routing (Archon-ID overrides), auditability artifacts (including `merge-audit.json`), and performance considerations.

Primary entrypoints:
- CLI: `scripts/run_consolidator.py`
- Service: `src/application/services/motion_consolidator_service.py`
- LLM factory: `src/infrastructure/adapters/external/crewai_llm_factory.py`

---

## What This Stage Is For

The Consolidator takes many “Motion Seeds” (typically produced by the Secretary) and reduces them into a smaller set of **mega-motions** so subsequent stages (review, deliberation, planning, and the next Conclave) can operate at a sustainable size.

Core goals:
- Produce a target number of mega-motions (default 12)
- Preserve full traceability from mega-motions back to:
  - the source Motion Seeds
  - the original supporting Archons
  - the originating clusters (when present)
- Optionally generate analysis artifacts:
  - novelty detection (creative / cross-domain proposals)
  - conclave summary
  - acronym registry
- Provide auditable “why/what merged” evidence (`merge-audit.json`)

---

## Inputs (What It Reads)

### 1) Secretary motion checkpoint (primary input)

By default, the script looks for the most recent:
- `_bmad-output/secretary/checkpoints/*_05_motions.json`

This file is produced by `SecretaryCrewAIAdapter.process_full_transcript()` in enhanced mode, and it contains the Motion Seed queue as JSON.

You can also pass an explicit path:
```bash
python scripts/run_consolidator.py _bmad-output/secretary/checkpoints/<...>_05_motions.json
```

### 2) Secretary report directory or `secretary-report.json` (optional convenience input)

`scripts/run_consolidator.py` also accepts:
- a directory containing `secretary-report.json`, or
- the `secretary-report.json` file itself

When you pass one of those, the script synthesizes “checkpoint-like” files in:
- `_tmp/secretary-checkpoints/`

Specifically:
- `<session_id>_<timestamp>_05_motions.json` (from `<session_dir>/motion-queue.json`)
- `<session_id>_<timestamp>_01_extraction.json` (from `<session_dir>/recommendations.json`, if present)

This helps when you want to consolidate directly from the Secretary report artifacts rather than the checkpoint folder.

### 3) Recommendations checkpoint (optional; used for novelty/summary/acronyms)

Inside `MotionConsolidatorService.consolidate_full(...)`, recommendations are loaded from:
- `_01_extraction.json` adjacent to the motions checkpoint (auto-detected by replacing `_05_motions` → `_01_extraction`)

If that file does not exist, novelty detection and summary generation are skipped (even if enabled), because they require recommendations.

### 4) Environment variables (`.env`)

The script loads `.env` via `python-dotenv`.

Important optional env var (role-based routing):
- `CONSOLIDATOR_ARCHON_ID=<archon-uuid>`

This selects the LLM profile (provider/model/base_url/etc.) from the Archon profile repository rather than using Consolidator defaults. This is the recommended way to avoid hard-coded local models that may not exist on your current inference host.

CrewAI runtime stability defaults (set by the script before imports):
- `CREWAI_DISABLE_TELEMETRY=true`
- `CREWAI_DISABLE_TRACKING=true`
- `OTEL_SDK_DISABLED=true`
- `CREWAI_TRACING_ENABLED=false`
- `CREWAI_TESTING=true`
- `XDG_DATA_HOME=/tmp/crewai-data` (ensures CrewAI has a writable data dir)

---

## Outputs (What It Writes)

The Consolidator saves outputs to a session-based directory:
- `_bmad-output/consolidator/<source_session_id>/`

### Always written

- `mega-motions.json`: machine-readable mega-motions with traceability fields
- `mega-motions.md`: human-readable mega-motions
- `traceability-matrix.md`: a compact mapping of mega-motions to source counts
- `index.md`: a master index linking all artifacts

### Written when applicable

- `merge-audit.json`: merge audit trail (only if mega-motions were merged in the merge pass)
- `novel-proposals.json` and `novel-proposals.md`: if novelty detection ran and found proposals
- `conclave-summary.json` and `conclave-summary.md`: if summary generation ran
- `acronym-registry.json` and `acronym-registry.md`: if acronym extraction ran and found acronyms

---

## CLI Flags and Behavior

Basic:
```bash
python scripts/run_consolidator.py
```

Flags:
- `--target` / `-t <int>`: target number of mega-motions (default: 12)
- `--verbose` / `-v`: verbose CrewAI logging
- `--basic`: skip novelty, summary, and acronym steps (consolidation only)
- `--no-novelty`: disable novelty detection
- `--no-summary`: disable summary generation
- `--no-acronyms`: disable acronym extraction

Input selection:
- If you pass no positional argument, the script auto-detects the latest `_05_motions.json` checkpoint.
- If you pass a directory or `secretary-report.json`, it generates temporary checkpoint files under `_tmp/secretary-checkpoints/` and uses those.

---

## Model Selection (How the LLM Is Chosen)

### Default path (no env override)

If `CONSOLIDATOR_ARCHON_ID` is not set, `MotionConsolidatorService.__init__()` builds its LLM using the “JSON model” from:
- `config/secretary-llm-config.yaml` (via `load_secretary_config_from_yaml()`)

This means the Consolidator will, by default, follow the Secretary’s YAML defaults (which are often local/Ollama models in test setups).

### Role-based override (recommended)

If you set:
- `CONSOLIDATOR_ARCHON_ID=<uuid>`

Then `scripts/run_consolidator.py` resolves the corresponding Archon profile via the profile repository and uses that profile’s `llm_config` to build the CrewAI LLM.

This makes model selection consistent with the rest of the pipeline and avoids stale/hard-coded local model names.

---

## Under the Hood: Execution Flow

### 1) Script bootstrapping

`scripts/run_consolidator.py`:
1. Sets CrewAI telemetry/storage env defaults (to avoid permission/telemetry issues)
2. Loads `.env`
3. Determines the input checkpoint(s):
   - auto-detect latest `_05_motions.json`, or
   - generate `_tmp/secretary-checkpoints/...` from a Secretary report directory
4. Resolves the consolidator’s LLM (optional `CONSOLIDATOR_ARCHON_ID`)
5. Calls `MotionConsolidatorService.consolidate_full(...)`
6. Saves outputs to `_bmad-output/consolidator/<session_id>/`

### 2) Loading inputs

`MotionConsolidatorService.consolidate_full(...)`:
- Extracts `(session_id, session_name)` from the checkpoint filename and (if available) the Secretary report at `_bmad-output/secretary/<session_id>/secretary-report.json`
- Loads motion seeds via `load_motions_from_checkpoint(...)`
- Auto-detects and loads recommendations via `load_recommendations_from_checkpoint(...)` if `_01_extraction.json` exists

### 3) Consolidation (group → synthesize → merge)

`MotionConsolidatorService.consolidate(...)` does:

#### Step A: LLM grouping into thematic buckets

`_identify_groupings(...)`:
- Prompts the LLM with a list of motion IDs + titles + themes + archon counts
- Requires the LLM to output exactly `target_count` groups, with each motion ID appearing exactly once

Robustness / auditability notes:
- `_parse_groupings(...)` aggressively sanitizes and parses JSON
- If the model omits motion IDs, the parser adds missing IDs to the final group (or creates an “Other” group)
- If parsing fails completely, it falls back to one group containing all motions

#### Step B: LLM synthesis of each mega-motion

For each group:
- `_synthesize_mega_motion(theme, motions)` prompts the LLM to produce a single consolidated motion (JSON: title/text/rationale)
- The service computes:
  - `all_supporting_archons` as the union of source supporters
  - `unique_archon_count`
  - `consensus_tier` (high/medium/low) using simple thresholds
- Parsing is hardened with multiple JSON sanitation strategies; if synthesis parsing fails, it falls back to concatenated source text.

#### Step C: Deterministic merge pass (auditable)

After initial mega-motion synthesis, `_merge_similar_mega_motions(...)`:
- Tokenizes each mega-motion’s title+theme
- Computes pairwise Jaccard similarity and applies deterministic merge rules:
  - exact theme match, or
  - “framework/governance” overlap with moderate similarity, or
  - high token overlap
- Finds connected components of merge candidates
- For each component, re-synthesizes a merged mega-motion using all source motions (LLM call)
- Records a merge audit object including:
  - which mega-motions were merged
  - their titles
  - which pairwise similarities triggered merges (with reasons)

This merge audit is exposed on the result and written to:
- `_bmad-output/consolidator/<session_id>/merge-audit.json`

### 4) Optional analysis vectors

#### Novelty detection (LLM; optional)

If enabled and recommendations exist, `detect_novel_proposals(...)`:
- selects top-N novelty candidates
- prompts the LLM for novelty score + reason + category
- writes `novel-proposals.json` / `novel-proposals.md`

#### Conclave summary (LLM; optional)

If enabled and recommendations exist, `generate_conclave_summary(...)`:
- generates key themes, consensus areas, contention points, and an executive summary
- writes `conclave-summary.json` / `conclave-summary.md`

#### Acronym registry (deterministic; optional)

If enabled, `extract_acronyms(...)`:
- uses regex scanning over recommendation and motion text
- tries to infer expansions from nearby context
- writes `acronym-registry.json` / `acronym-registry.md`

---

## Why This Stage Is Auditable

Key “witnessing” artifacts:
- `mega-motions.json` includes full provenance fields:
  - `source_motion_ids`, `source_motion_titles`, `source_cluster_ids`
  - `all_supporting_archons`, `unique_archon_count`, and `consensus_tier`
- `traceability-matrix.md` gives a compact overview of coverage
- `merge-audit.json` explains which mega-motions were merged and why (pairwise match reasons)
- Optional novelty/summary artifacts are recorded as separate files with structured JSON alongside markdown.

The service also reports traceability completeness:
- `traceability_complete` is `true` if no motions were orphaned
- `orphaned_motions` lists any motions that did not get assigned to a synthesized mega-motion (usually indicates LLM grouping issues)

---

## Performance Recommendations

### Biggest cost drivers
- LLM grouping (`_identify_groupings`) is one LLM call
- Mega-motion synthesis is one LLM call per group (≈ `target_count`)
- Merge pass can add additional synthesis calls when overlap is detected
- Novelty and summary add additional LLM calls (and typically require larger contexts)

### Practical speed levers (no code changes)
- Use `--basic` to skip novelty/summary/acronyms when iterating quickly
- Use `--no-novelty` / `--no-summary` if you only need mega-motions
- Choose a faster model using `CONSOLIDATOR_ARCHON_ID`
- Use a local inference host with the model already pulled (or a cloud provider with adequate rate limits)

### Potential code-level speedups (would require changes)
- Reduce synthesis prompt size (truncate source motion texts more aggressively)
- Lower `target_count` during early iterations
- Add bounded concurrency for synthesis calls (careful: it can increase provider throttling and reduce determinism if you don’t preserve output ordering)

---

## Troubleshooting & Common Failure Modes

### “model not found” (local / Ollama)

If you see errors like:
- `{"error":"model 'X' not found"}`

Then either:
- pull the model on your Ollama host (`ollama list` to confirm), or
- set `CONSOLIDATOR_ARCHON_ID` to an Archon bound to a model that exists on the current host (via `docs/archons-base.json` + `config/archon-llm-bindings.yaml`).

### Orphaned motions

If the output summary reports orphaned motions:
- check `_bmad-output/consolidator/<session_id>/traceability-matrix.md`
- check logs for `motions_missing_from_groups`

This usually means the LLM grouping output omitted IDs. The parser attempts to patch missing IDs into the last group, but if the grouping response is severely malformed and falls back to a single group, synthesis may still proceed but you should treat it as a degraded run.

### Passing a directory but missing `secretary-report.json`

If you pass a directory expecting report-based input, the script requires:
- `<dir>/secretary-report.json`

If it isn’t present, run the Secretary again or pass the checkpoint file directly.

