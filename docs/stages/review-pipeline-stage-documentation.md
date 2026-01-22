# Review Pipeline Stage Documentation (`scripts/run_review_pipeline.py`)

This document explains what the **Motion Review Pipeline** does, what artifacts it produces, what happens under the hood in code, and practical recommendations for improving throughput (especially when using real LLM reviews).

Primary entrypoints:
- CLI: `scripts/run_review_pipeline.py`
- Service: `src/application/services/motion_review_service.py`
- Real LLM reviewer adapter: `src/infrastructure/adapters/external/reviewer_crewai_adapter.py`

---

## What This Stage Is For

The review pipeline exists to avoid “full Conclave explosion” (72 agents debating every motion in one giant synchronous session) by:

1. Using **implicit support** (who contributed to a motion upstream) to estimate how risky a motion is.
2. Assigning “gap” Archons (those who did not contribute) targeted review work.
3. Aggregating review outcomes into:
   - “consensus reached” motions (can pass without deeper debate)
   - “contested” motions (must go to panel deliberation)
4. Producing a final **ratification results** file used downstream by the execution planner.

---

## Inputs (What It Reads)

This stage consumes the output of the consolidator stage:

From a consolidator session directory (default auto-detected):
- `mega-motions.json` (required for mega-motions)
- `novel-proposals.json` (optional; if present, these are treated as HIGH risk motions)
- `conclave-summary.json` (optional; used to set session name)

Loading logic lives in:
- `MotionReviewService.load_mega_motions()`

---

## Outputs (Why It Looks “Very Large”)

The pipeline writes a *lot* of structured artifacts under:
- `_bmad-output/review-pipeline/<session_id>/`

Key files/directories (written by `MotionReviewService.save_results()`):
- `triage_results.json` — implicit support + risk tier per motion
- `review_packets/` — **72 JSON files** (one per Archon) describing what they should review
- `aggregations.json` — counts/ratios per motion after collecting reviews
- `panel_deliberations/` — one JSON file per deliberation panel (if any)
- `ratification_results.json` — final “yeas/nays/abstentions” outcome per motion
- `pipeline_result.json` — summary object (top-level counts + references)
- `audit_trail.json` — chronological audit events appended during run

The output gets large mainly because:
- There are many Archons (72).
- Review packets are written per Archon.
- Real-agent runs can create many review responses and/or panel deliberation artifacts.

---

## CLI Flags and Modes

`scripts/run_review_pipeline.py` supports:

- Positional arg: `consolidator_path` (optional; auto-detected if omitted)
- `--verbose` / `-v`: increases logging
- `--triage-only`: runs only Phase 1 (triage) and prints risk breakdown
- `--no-simulate`: skips simulated reviews (produces triage + packets only)
- `--real-agent`: uses real LLM-powered Archon reviews via `ReviewerAgentProtocol`

Important behavioral notes:
- If `--real-agent` is set but the reviewer agent fails to initialize, the script falls back to simulation (it explicitly flips `args.real_agent = False`).
- `--triage-only` bypasses downstream phases.

---

## Under the Hood: The Six Phases

The pipeline’s conceptual phases are described at the top of `motion_review_service.py` and implemented across the service.

### Phase 0: Load Data

Code: `MotionReviewService.load_mega_motions()`

It builds:
- A list of `MegaMotionData` from `mega-motions.json`
- A list of “novel proposals” from `novel-proposals.json` (if present)

Novel proposals are promoted to “motions” for review:
- `is_novel=True`
- `unique_archon_count=1` (only the proposer)

### Phase 1: Triage (Implicit Support + Risk Tier)

Code: `MotionReviewService.triage_motions()` + `_calculate_implicit_support()`

For each motion:
- **Contributing Archons** = `supporting_archons` from consolidator output
- **Gap Archons** = `all_archons - contributing_archons`
- **Support ratio** = `len(contributing_archons) / 72`

Risk tier assignment:
- Novel proposals are forced `HIGH`.
- Otherwise:
  - `LOW` if support ratio ≥ `0.66` and no conflicts
  - `MEDIUM` if support ratio ≥ `0.33` and conflicts ≤ `5`
  - else `HIGH`

Current implementation note:
- Conflict detection is effectively stubbed: `conflicts` and `conflict_details` are currently empty in `_calculate_implicit_support()`.
  - Practically, risk is dominated by support ratio + “novelness”.

### Phase 2: Packet Generation (Who Reviews What)

Code: `MotionReviewService.generate_review_packets()`

For each Archon:
- LOW-risk motions:
  - If the Archon contributed, they’re marked “already_endorsed”.
  - Otherwise they are skipped (auto-ratify path).
- MEDIUM/HIGH risk motions:
  - If the Archon is a **gap archon** for that motion, they get assigned the motion.
  - If conflicts were implemented, conflicted Archons would also be assigned.

This produces `ReviewAssignment` objects and writes them to `review_packets/<archon_id>.json`.

### Phase 3–4: Review Collection (Simulation vs Real LLM) + Aggregation

There are two paths:

#### A) Simulated reviews

Code: `MotionReviewService.simulate_archon_reviews()`

This produces synthetic `ReviewResponse` objects using heuristics:
- If conflict flagged → AMEND
- Else if implicit support > 0.5 → ENDORSE
- Else → ABSTAIN

#### B) Real LLM reviews

Code: `MotionReviewService.collect_archon_reviews()`
Adapter: `ReviewerCrewAIAdapter` (`reviewer_crewai_adapter.py`)

How real reviews are executed today:
- `collect_archon_reviews()` loops **sequentially** over Archons with assignments.
- For each Archon, it constructs:
  - `ArchonReviewerContext` (lightweight backstory + identity)
  - a list of `MotionReviewContext` items (one per motion assigned to that Archon)
- It then calls:
  - `reviewer_agent.batch_review_motions(archon, motions)`

Important current performance characteristic:
- `ReviewerCrewAIAdapter.batch_review_motions()` is itself sequential and simply calls `review_motion()` for each motion.
- `review_motion()` creates a fresh CrewAI `Agent` and runs a single-task `Crew` kickoff.
  - That means many separate LLM calls, and significant per-call overhead.

#### Aggregation

Code: `MotionReviewService.aggregate_reviews()`

For each motion:
1. Counts explicit stances from collected `ReviewResponse`s.
2. Adds implicit endorsements (= number of contributing Archons).
3. Computes:
   - `endorsement_ratio = total_endorsements / engaged`
   - `opposition_ratio = oppositions / engaged`
4. Derives:
   - `consensus_reached` if endorsement_ratio ≥ `0.75`
   - `contested` if opposition_ratio ≥ `0.25`

### Phase 5: Panel Deliberation (Only for Contested Motions)

Code: `MotionReviewService.create_deliberation_panels()` + `run_real_panel_deliberation()`
Adapter: `ReviewerCrewAIAdapter.run_panel_deliberation()`

Panels are composed of:
- up to 3 supporters
- up to 3 critics
- 3 neutrals (first available names not already used)

Real panel deliberation is also sequential in the adapter:
- Supporters each produce an argument (one LLM call each).
- Critics each respond (one LLM call each).
- A “Panel Facilitator” synthesizes into JSON (one LLM call).

If panel deliberation fails, the service falls back to simulation.

### Phase 6: Ratification (Final Vote)

Two ratification paths:

#### A) Real agent mode: derived from real reviews

Code: `MotionReviewService.derive_ratification_from_reviews()`

This counts actual review stances per motion:
- ENDORSE → yea
- OPPOSE → nay
- AMEND/ABSTAIN → abstain

Then applies threshold rules:
- supermajority if the title contains “constitutional”
- else simple majority

#### B) Simulation mode: simulated ratification

Code: `MotionReviewService.simulate_ratification()`

This is a heuristic vote generator. The “default” branch produces a fixed split (e.g., 38/28/6), which can look suspiciously uniform if the upstream conditions don’t trigger other branches.

---

## Speed Optimization Recommendations

### 1) Parallelize across Archons (High impact, requires care)

Current bottleneck:
- `collect_archon_reviews()` runs per-Archon sequentially.

In principle, Archon reviews are independent and can be run concurrently with the same “effect” (same semantics), as long as:
- You can tolerate non-deterministic ordering of completion/logs.
- Your model provider(s) can handle concurrency (rate limits, GPU capacity).

Recommended design:
- Use `asyncio.gather()` on multiple Archon review tasks.
- Gate concurrency with a semaphore (e.g., 4–16).
- If you have distributed inference (different `base_url` per Archon), you can increase concurrency substantially.

When *not* to parallelize:
- Single-GPU / single Ollama instance: heavy parallelism can be slower due to contention.
  - In that case, round-robin/sequential can be the fastest stable configuration.

### 2) Parallelize within a panel deliberation (Medium impact)

Panel stage currently executes supporter arguments sequentially and critic arguments sequentially.
These can be run concurrently (each is independent text generation), then fed into synthesis.

### 3) Reduce per-review overhead (High impact)

Current adapter behavior:
- For each motion review, it creates a new CrewAI Agent and runs a Crew kickoff.

Possible improvements:
- Reuse the same CrewAI Agent for an Archon across multiple motion reviews.
- Replace “one motion per call” with a single prompt that reviews N motions at once, returning a JSON array of decisions.
  - This collapses many calls into one (large) call, often much faster on local inference.

### 4) Reduce workload by tightening triage rules (High impact)

If many motions end up MEDIUM/HIGH, the pipeline assigns them to many “gap” Archons, dramatically increasing calls.

Options:
- Increase `LOW_RISK_THRESHOLD` (more motions auto-ratify).
- Introduce a “sample size” cap: for medium risk, assign only K gap Archons (e.g., 5–12) instead of all.
- Incorporate consolidator `consensus_tier` and `unique_archon_count` directly into triage decisions.

### 5) Reduce tokens and context (Medium impact)

Most prompts include large motion text snippets (up to ~3000 chars for review, ~2000 chars in panels).
If your governance style allows:
- Reduce motion text slice lengths.
- Reduce max_tokens in the LLM configs for reviewer models.
- Use smaller, faster models for review unless escalated.

### 6) Use distributed inference (High impact, infrastructure-dependent)

Per-Archon `base_url` support exists in the profile/bindings ecosystem.
If you spread Archons across multiple Ollama servers:
- You can safely run higher concurrency.
- Total wall-clock time drops dramatically.

### 7) Reduce filesystem overhead (Low-to-medium impact)

Writing 72 packet files + many JSON artifacts isn’t the primary bottleneck, but can matter on slow disks.
If needed:
- Write compact JSON (no indent) for packet files.
- Optionally skip saving review packets unless in “debug/audit” mode.

---

## Round Robin vs Async: Practical Guidance

**Round robin / sequential execution** is best when:
- You have a single inference server (one GPU / one Ollama host).
- You care about predictable load and avoiding GPU thrash.

**Async / parallel execution** is best when:
- You have multiple inference endpoints (distributed base_urls).
- Your provider supports higher concurrency.
- You want maximum throughput and can accept non-deterministic completion order.

Semantically, the pipeline does not require round-robin ordering for correctness:
- Reviews and panel arguments do not depend on the order of other reviews.
- Aggregation and ratification operate on the collected set of responses.

---

## Suggested Next Improvements (If You Want to Implement Speedups)

If you want speed without changing governance semantics:
1. Add concurrency in `MotionReviewService.collect_archon_reviews()` with a semaphore.
2. Add concurrency in `ReviewerCrewAIAdapter.run_panel_deliberation()` for supporter/critic argument generation.
3. Rework `ReviewerCrewAIAdapter.batch_review_motions()` to do a true “single call returns many decisions” batch.

If you want speed by changing the review “coverage” model:
1. Cap gap-archon assignments per motion in `generate_review_packets()`.
2. Incorporate `consensus_tier` directly into low-risk auto-ratify decisions.
