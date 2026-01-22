# Conclave Process Documentation (`scripts/run_conclave.py`)

This document explains, in detail, what the **Conclave stage** does, what it reads/writes, and what happens under the hood in code. It also includes practical performance notes (sequential vs async, distributed inference, and levers you can pull without changing semantics).

Primary entrypoints:
- CLI: `scripts/run_conclave.py`
- Service: `src/application/services/conclave_service.py`
- Domain models: `src/domain/models/conclave.py`
- Queue integration: `src/application/services/motion_queue_service.py`

---

## What This Stage Is For

The Conclave stage runs a formal parliamentary-style session for the 72 Archons:

- Establishes a session and records a transcript
- Introduces motions (from queue, blockers, or custom input)
- Seconding, debate, and voting
- Produces a transcript artifact that downstream stages consume (Secretary)
- Updates the motion queue lifecycle (promoted → voted → archived)

This is the “governance ceremony” stage that generates the canonical discussion record.

---

## Inputs (What It Reads)

### 1) Archon profiles and LLM bindings

`scripts/run_conclave.py` loads Archon profiles through:
- `create_archon_profile_repository()` → loads `docs/archons-base.json` and merges in `config/archon-llm-bindings.yaml`

This determines:
- the list of Archons and their ranks
- the model/provider/base_url to use per Archon (through the CrewAI adapter)

### 2) Environment variables

The script loads `.env` via `python-dotenv`.

Key env vars:
- `OLLAMA_HOST` (fallback for local provider)
- provider API keys (Anthropic/OpenAI/etc.) if configured via bindings

It also pre-sets CrewAI-related env vars (telemetry off, writable storage), similar to other scripts:
- `CREWAI_DISABLE_TELEMETRY`, `CREWAI_DISABLE_TRACKING`, `OTEL_SDK_DISABLED`, `CREWAI_TRACING_ENABLED`
- `XDG_DATA_HOME=/tmp/crewai-data`

### 3) Motion sources (one of)

The script builds a list of “motion plans” from one or more sources:

1. **Motion Queue** (default unless disabled or a custom motion is provided)
   - Uses `MotionQueueService.select_for_conclave()`
   - Promotes items with `MotionQueueService.promote_to_conclave()` (marks them PROMOTED in `_bmad-output/motion-queue/active-queue.json`)

2. **Execution Planner Blockers** (default unless disabled or a custom motion is provided)
   - Reads `_bmad-output/execution-planner/*/blockers_summary.json` (latest by mtime), or a user-specified `--blockers-path`
   - Converts agenda items into procedural motions titled `Blocker Escalation: ...`
   - These motions are “external motions” (not proposed by an actual Archon in-session)

3. **Custom motion** (if any of `--motion`, `--motion-text`, `--motion-file` are provided)
   - File overrides inline text
   - Motion type selected by `--motion-type`

### 4) Resume checkpoint (optional)

If `--resume <checkpoint.json>` is provided:
- `ConclaveService.load_session()` deserializes the session state and transcript.

---

## Outputs (What It Writes)

### 1) Transcript markdown

At the end of the run:
- `ConclaveService.save_transcript()` writes a markdown transcript:
  - `transcript-<session_uuid>-<timestamp>.md`
  - Under `_bmad-output/conclave/`

This transcript is the primary downstream input for Secretary.

### 2) Checkpoints (JSON)

Checkpoints are written periodically and on exit paths:
- After each debate round
- After each vote
- On adjournment (final checkpoint)
- On KeyboardInterrupt or error (best-effort emergency checkpoint)

Location:
- `_bmad-output/conclave/checkpoint-<session_id>-<timestamp>.json`

These checkpoints include:
- session metadata and phase
- motions, votes, and debate entries
- transcript entries
- agenda items (if used)

### 3) Motion queue lifecycle updates

If a motion came from the queue:
- It is promoted to the Conclave at the start
- After voting, `MotionQueueService.mark_voted()` archives it:
  - `_bmad-output/motion-queue/archive/<queued_motion_id>.json`
  - Removes it from `active-queue.json`

### 4) Console progress stream

The CLI sets a progress callback (`format_progress`) and prints:
- phase changes
- who is speaking/voting
- checkpoint saves
- vote tallies

---

## CLI Flags and Behavior

`scripts/run_conclave.py` supports:

- `--session <name>`: custom session name (default auto-generated `conclave-YYYYMMDD-HHMMSS`)
- `--resume <checkpoint.json>`: resume from checkpoint

Custom motion input:
- `--motion <title>`
- `--motion-text <text>`
- `--motion-file <path>` (takes precedence over `--motion-text`)
- `--motion-type constitutional|policy|procedural|open` (default: `open`)

Debate control:
- `--debate-rounds <N>` (default: 3 in the script; service default is 5)
- `--quick` (forces 1 debate round and reduces `agent_timeout_seconds` to 60)

Queue integration:
- `--no-queue` (don’t load from motion queue)
- `--queue-max-items <N>` (default: 5)
- `--queue-min-consensus critical|high|medium|low|single` (default: medium)

Blockers integration:
- `--no-blockers` (don’t load from execution planner blockers)
- `--blockers-path <path>` (either a `blockers_summary.json` or an execution-planner session dir)

Important selection rule:
- If any custom motion flags are used, queue + blockers are skipped and only the custom motion is run.

---

## Under the Hood: Execution Flow

### 1) Bootstrapping and dependencies

`scripts/run_conclave.py`:
1. Loads `.env`
2. Loads the Archon profile repository (JSON + YAML)
3. Creates a CrewAI-based orchestrator via `create_crewai_adapter(profile_repository=...)`
4. Builds a `ConclaveService` instance
5. Creates/resumes a session
6. Builds motions from queue/blockers/custom
7. Runs the session phases and motion lifecycle
8. Saves transcript and prints summary

### 2) Session and phase management

`ConclaveService` manages phases (`ConclavePhase` in `src/domain/models/conclave.py`):

- NOT_STARTED → CALL_TO_ORDER → ROLL_CALL → NEW_BUSINESS → ADJOURNMENT → ADJOURNED

Note:
- The service supports intermediate phases (approval of minutes, reports, etc.) in the enum, but the CLI uses an “expedited path” and jumps directly to NEW_BUSINESS.

Roll call behavior today:
- `conduct_roll_call()` marks *all* archons present (no real “absent” detection).
- Quorum check is effectively always true in this mode.

### 3) Motion lifecycle

Domain motion state machine (`MotionStatus`):
- PROPOSED → SECONDED → DEBATING → CALLED → VOTING → PASSED/FAILED

Motion proposal:
- Custom motions call `ConclaveService.propose_motion()`
  - Optional permission enforcement exists (if a permission enforcer is injected), but the CLI currently does not supply one.
- Queue/blocker motions are added via `ConclaveService.add_external_motion()`
  - This bypasses proposer permission checks (intended for externally sourced agenda items).

Seconding:
- `second_motion()` calls `motion.second()` and records a transcript entry.

### 4) Debate (the largest runtime cost)

Debate is implemented as **round-based, rank-ordered, sequential invocation**:

- `conduct_debate()` loops rounds up to `max_debate_rounds`
- `_conduct_debate_round()` loops over `_profiles_by_rank`
  - `_profiles_by_rank` is computed by sorting by `get_rank_priority(aegis_rank)`

Each Archon is invoked with:
- A `ContextBundle` containing a debate prompt produced by `_build_debate_context()`
- The orchestrator call: `self._orchestrator.invoke(archon.id, bundle)`

Debate context includes:
- motion title/type/text
- round number
- up to the last 10 prior debate entries (so later speakers “see” earlier context)

Rank-constraint validation:
- After each speech, `_validate_speech_for_rank()` checks whether King-rank archons defined “HOW” (execution details) instead of “WHAT”.
- Violations are recorded in transcript as `violation_speech` and emitted via progress callback.
- The script can also emit “system” transcript entries on agent invocation failures.

Checkpointing:
- A checkpoint is saved after each debate round.

### 5) Calling the question

`call_question()` transitions the motion from DEBATING to CALLED and records a procedural transcript entry.

### 6) Voting

Voting is also **sequential**:

- `conduct_vote()` iterates through `present_participants` (the list populated during roll call).
- For each Archon, `_get_archon_vote()` invokes the orchestrator with a vote prompt.
- `_parse_vote()` looks for:
  - “I VOTE AYE”
  - “I VOTE NAY”
  - “I ABSTAIN”
  - Defaults to ABSTAIN if unclear.

Outcome rule (important detail):
- The domain model `Motion.tally_votes()` requires a **2/3 supermajority of votes cast** (ayes+nays only; abstentions excluded).
- `ConclaveConfig.supermajority_threshold` is printed by the CLI, but `Motion.tally_votes()` currently uses a hard-coded 2/3 rule.

Checkpointing:
- A checkpoint is saved after each vote.

### 7) Adjournment and transcript writing

`adjourn()`:
- sets ended timestamp
- advances phase to ADJOURNED
- writes final procedural transcript entries
- saves a final checkpoint

`save_transcript()` writes a markdown transcript grouped by phase.

---

## Why “SYSTEM” and “Execution Planner” Can Appear in Transcripts

When Conclave adds blocker motions from the execution planner:
- it uses proposer name “Execution Planner”
- those entries are recorded as motion transcript entries with that speaker name

When an Archon invocation fails during debate/vote:
- Conclave records a transcript entry with `entry_type="system"` and content like:
  - `[Error: <Archon> unable to contribute: <exception>]`

Downstream stages must treat those as non-Archon speakers (Secretary now filters them).

---

## Performance Notes and Optimization Recommendations

### What dominates runtime

For a single motion:
- Debate calls: `72 * max_debate_rounds` LLM invocations
- Vote calls: `72` LLM invocations

For M motions:
- Total calls ≈ `M * (72*(rounds + 1))`

### “Round robin” vs async (correctness vs throughput)

Debate is inherently order-dependent in the current design:
- Later speakers see previous contributions in the context prompt.
- If you run all speakers concurrently, you lose “reactive” debate unless you restructure prompts.

So:
- **Sequential / round robin** preserves the semantics of debate-as-proceedings.
- **Async / parallel** can be faster but changes the interaction model unless you:
  - run one rank tier at a time (Kings first), then parallelize within the next tier using the post-King context
  - or accept “independent statements” rather than responsive debate

Voting, however, can be parallelized with minimal semantic change *in the current implementation* because:
- vote prompts do not include debate history; they include motion text only
- therefore, votes are independent given the motion text

### Low-risk speed levers (no semantic changes)

- Use `--quick` (1 debate round)
- Reduce `--debate-rounds`
- Reduce motion count from queue (`--queue-max-items`)
- Increase queue min consensus threshold (`--queue-min-consensus high`)
- Run blockers-only or queue-only (disable the other source)

### High-impact speed levers (infrastructure)

- Use distributed inference:
  - different `base_url` per Archon in `config/archon-llm-bindings.yaml`
  - then parallelization becomes viable without melting a single GPU

### Higher-risk speed levers (changes semantics)

- Don’t have all 72 Archons speak every round:
  - sample speakers per rank
  - have only “gap archons” speak (those not contributing)
  - use a panel model similar to the review pipeline for some motions
- Replace multi-round debate with a single “position statement” round
- Collapse debate into summary + vote (skipping per-Archon debate)

---

## Practical Debugging Tips

- If you see many `[SYSTEM]` errors in the transcript, it usually means LLM config/model availability problems for specific Archons.
  - Run `scripts/run_roll_call.py` to identify which Archons have broken bindings.
- If you need to stop mid-session:
  - Ctrl+C will checkpoint and tell you the `--resume` command to continue.
- If motion queue items disappear:
  - check `_bmad-output/motion-queue/archive/` for the archived record and vote details.
