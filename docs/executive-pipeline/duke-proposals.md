# Duke Proposals: From RFP to Competing Implementation Plans

After the Executive branch produces a finalized RFP (Implementation Dossier), every
Administrative Duke reads it and generates a complete implementation proposal
describing HOW to accomplish the requirements from their domain expertise. Each
Duke runs through a 5-phase multi-pass pipeline to avoid single-call token
truncation.

```
Conclave PASS
  |
  v
run_rfp_generator.py              11 Presidents contribute requirements
  |
  v
rfp.json  +  rfp.md               Implementation Dossier (status: final)
  |
  v
run_duke_proposals.py              23 Dukes generate proposals              <- THIS
  |
  v
proposals_inbox/                   23 proposal .json + .md pairs
  |
  v
run_proposal_selection.py          11 Presidents score, rank, deliberate
  |
  v
selection/                         Winner selected (or revision/escalation)
```

---

## 1. Run It

### Auto-detect (recommended)

```bash
python scripts/run_duke_proposals.py
```

Finds the most recent RFP session under `_bmad-output/rfp/*/`, locates
`rfp.json` within the first mandate directory, loads all Administrative
Senior Dukes from `docs/archons-base.json`, and runs the 5-phase pipeline
for each Duke.

### From a specific RFP session

```bash
python scripts/run_duke_proposals.py \
  --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e
```

### Explicit RFP file

```bash
python scripts/run_duke_proposals.py --rfp-file path/to/rfp.json
```

### Single Duke

```bash
python scripts/run_duke_proposals.py --duke-name Agares
```

Generates a proposal for one Duke only. Useful for debugging or re-running a
single failed Duke.

### Simulation mode (no LLM)

```bash
python scripts/run_duke_proposals.py --mode simulation -v
```

Generates templated proposals with deterministic content. Each Duke gets one
tactic, one risk, one resource request, and pre-filled coverage/deliverable
tables. Useful for testing the pipeline end-to-end.

### Checkpoint management

```bash
# Fresh run (delete all existing checkpoints)
python scripts/run_duke_proposals.py --clear-checkpoints

# Disable checkpointing entirely
python scripts/run_duke_proposals.py --no-checkpoint
```

---

## 2. All Flags

| Flag | Description |
|------|-------------|
| `--rfp-file PATH` | Path to `rfp.json` file (auto-detects if not specified) |
| `--from-rfp-session PATH` | Path to RFP session directory to find `rfp.json` in |
| `--mandate-id STR` | Mandate ID to process (when multiple mandates exist) |
| `--outdir PATH` | Output directory (defaults to the RFP session mandate dir) |
| `--mode {llm,simulation,auto}` | Generation mode: `llm` uses LLM, `simulation` generates test proposals, `auto` uses LLM when available (default: `auto`) |
| `--duke-name STR` | Generate proposal for a single Duke only |
| `--model STR` | Override LLM model name |
| `--provider STR` | Override LLM provider (e.g., `ollama`, `openai`, `anthropic`) |
| `--base-url STR` | Override LLM base URL |
| `--checkpoint-dir PATH` | Override checkpoint directory for multi-pass pipeline |
| `--no-checkpoint` | Disable checkpointing (each run starts fresh, no resume) |
| `--clear-checkpoints` | Delete existing checkpoint directory before starting |
| `-v` / `--verbose` | Enable verbose logging |

---

## 3. The 5-Phase Pipeline

Each Duke runs through 5 phases sequentially. Each phase is a separate
CrewAI call with its own prompt, producing Markdown output that is
checkpointed to disk.

### Phase 1: Strategic Foundation

Generates three sections: **Overview**, **Issues**, and **Approach Philosophy**.

The prompt includes the full RFP context (motion title, text, justification,
objectives, functional requirements, non-functional requirements, constraints,
deliverables, evaluation criteria) plus the Duke's identity (name, role,
backstory, 4-char abbreviation).

Three constitutional constraints are injected into the prompt:

| Constraint | Purpose |
|------------|---------|
| Administrative Scope | Duke proposes HOW, not WHAT; must not redefine requirements |
| Context Purity | May not invent real-world domains or external compliance frameworks |
| Branch Boundary | May not assign work to other branches or create governance structures |

**Checkpoint key:** `phase_1_foundation`

### Phase 2: Per-Deliverable Solutions

Loops over every deliverable in the RFP. For each deliverable, one LLM call
produces:

- **Tactics** (`T-{ABBREV}-NNN`): 2-4 per deliverable
- **Risks** (`R-{ABBREV}-NNN`): 1-2 per deliverable
- **Resource Requests** (`RR-{ABBREV}-NNN`): 0-2 per deliverable

Counters (`t_ctr`, `r_ctr`, `rr_ctr`) carry forward across deliverables so
IDs never collide. The prompt includes:

- Focused deliverable context (name, description, acceptance criteria, dependencies)
- All FRs, NFRs, and constraints (for cross-reference)
- An accumulated summary of all T-/R-/RR- IDs produced so far

When resuming from checkpoints, counter state is reconstructed by scanning
the highest ID numbers in each cached section.

**Checkpoint key:** `phase_2_{deliverable_id}` (one per deliverable)

### Phase 3: Cross-Cutting

Generates the sections that tie individual deliverable work together:

| Section | Content |
|---------|---------|
| Requirement Coverage | Table mapping every FR/NFR to tactic references and confidence |
| Deliverable Plan | Table mapping every deliverable to approach, tactics, duration |
| Capacity Commitment | Portfolio ID, committed units, unit label, confidence |
| Assumptions | 3-6 bullet points |
| Constraints Acknowledged | Bullet points referencing constraint IDs |

The prompt receives all FR IDs, NFR IDs, and deliverable IDs as JSON arrays
plus the accumulated T-/R-/RR- summary from Phase 2.

**Checkpoint key:** `phase_3_cross_cutting`

### Phase 4: Consolidation Review

An optional editorial pass by a Secretary Text agent (separate LLM). The
secretary reviews the assembled proposal for consistency:

- Fixes inconsistent tactic references in tables
- Adds an "Alternatives & Trade-offs" section if missing
- Flags gaps with `<!-- GAP: description -->` comments
- Does NOT add, remove, or renumber any T-/R-/RR- items

**Sanity check:** If the output is missing expected `T-{ABBREV}-` markers or
is less than 50% of the original length, the consolidation is discarded and
the original is kept.

**Skipped when:** `SECRETARY_TEXT_ARCHON_ID` environment variable is not set.

**Checkpoint key:** `phase_4_consolidated`

### Phase 5: Executive Summary

Synthesizes a 4-6 sentence executive summary covering:
core approach, key risks, and expected outcomes. Uses the accumulated
T-/R-/RR- summary (not full Markdown) to stay within token budget.

**Execution order note:** Phase 5 runs _before_ Phase 4 in the actual code
so the consolidation review sees the executive summary.

**Checkpoint key:** `phase_5_exec_summary`

### Assembly

After all phases complete, per-deliverable Phase 2 outputs are re-sorted
into grouped sections. The interleaved T-/R-/RR- items from each
deliverable call are split by regex (`^### T-`, `^### R-`, `^### RR-`) and
collected into three buckets.

Final section order in the assembled proposal:

1. `# Proposal from Duke {Name}`
2. `## Executive Summary` (Phase 5)
3. `## Overview` / `## Issues` / `## Approach Philosophy` (Phase 1)
4. `## Tactics` (Phase 2, re-sorted)
5. `## Risks` (Phase 2, re-sorted)
6. `## Resource Requests` (Phase 2, re-sorted)
7. `## Requirement Coverage` / `## Deliverable Plan` / `## Capacity Commitment` / `## Assumptions` / `## Constraints Acknowledged` (Phase 3)

---

## 4. Checkpointing

Each phase writes its Markdown output to a checkpoint file on disk. On
subsequent runs, cached phases are skipped.

### Directory structure

```
<outdir>/proposal_drafts/
├── agares/
│   ├── phase_1_foundation.md
│   ├── phase_2_D-001.md
│   ├── phase_2_D-002.md
│   ├── phase_3_cross_cutting.md
│   ├── phase_4_consolidated.md
│   └── phase_5_exec_summary.md
├── valefor/
│   ├── phase_1_foundation.md
│   └── ...
└── ...
```

### Behavior

| Scenario | What happens |
|----------|-------------|
| Normal run | Checks for existing checkpoint before each phase; skips if found |
| `--clear-checkpoints` | Deletes the entire `proposal_drafts/` directory before starting |
| `--no-checkpoint` | Disables all checkpoint reads and writes |
| `--checkpoint-dir PATH` | Overrides the default checkpoint directory |
| Partial failure | Resume picks up from the last successful phase |

### Counter reconstruction

When Phase 2 is resumed from checkpoints, the adapter scans each cached
deliverable section for the highest `T-{ABBREV}-NNN`, `R-{ABBREV}-NNN`, and
`RR-{ABBREV}-NNN` numbers to restore counter state before generating the
next deliverable.

---

## 5. Output Structure

```
<outdir>/proposals_inbox/
├── inbox_manifest.json                # Submission status for each Duke
├── proposal_summary.json              # Aggregate statistics
├── proposal_agares.json               # Metadata + counts (no Markdown body)
├── proposal_agares.md                 # Full Markdown proposal
├── proposal_valefor.json
├── proposal_valefor.md
├── ...                                # One .json + .md pair per Duke
└── duke_proposal_events.jsonl         # Event trail
```

### proposal_summary.json

```json
{
  "schema_version": "2.0",
  "artifact_type": "duke_proposal_summary",
  "rfp_id": "rfp-xxx",
  "mandate_id": "mandate-xxx",
  "created_at": "2026-01-31T12:00:00+00:00",
  "total_proposals": 23,
  "generated_count": 21,
  "failed_count": 1,
  "simulation_count": 1,
  "total_tactics": 184,
  "total_risks": 72,
  "total_resource_requests": 38,
  "duke_names": ["Agares", "Valefor", "..."],
  "proposals": [
    {
      "proposal_id": "dprop-agar-a1b2c3d4",
      "duke_name": "Agares",
      "duke_abbreviation": "AGAR",
      "status": "GENERATED",
      "tactic_count": 8,
      "risk_count": 3,
      "resource_request_count": 2,
      "requirement_coverage_count": 12,
      "deliverable_plan_count": 4
    }
  ]
}
```

### inbox_manifest.json

```json
{
  "artifact_type": "duke_proposals_inbox_manifest",
  "rfp_id": "rfp-xxx",
  "mandate_id": "mandate-xxx",
  "created_at": "2026-01-31T12:00:00+00:00",
  "total_dukes": 23,
  "submissions": [
    {
      "duke_name": "Agares",
      "duke_abbreviation": "AGAR",
      "duke_archon_id": "uuid-xxx",
      "proposal_file": "proposal_agares.json",
      "proposal_markdown_file": "proposal_agares.md",
      "status": "GENERATED",
      "submitted_at": "2026-01-31T12:00:00+00:00",
      "llm_provider": "ollama",
      "llm_model": "qwen3:latest"
    }
  ]
}
```

### Per-Duke JSON sidecar

The `.json` file contains metadata and counts but _not_ the Markdown body:

```json
{
  "schema_version": "2.0",
  "artifact_type": "duke_proposal",
  "proposal_id": "dprop-agar-a1b2c3d4",
  "duke": {
    "archon_id": "uuid-xxx",
    "name": "Agares",
    "domain": "Market Disruption",
    "abbreviation": "AGAR"
  },
  "rfp_id": "rfp-xxx",
  "mandate_id": "mandate-xxx",
  "status": "GENERATED",
  "created_at": "2026-01-31T12:00:00+00:00",
  "counts": {
    "tactics": 8,
    "risks": 3,
    "resource_requests": 2,
    "requirement_coverage": 12,
    "deliverable_plans": 4,
    "assumptions": 5,
    "constraints": 3
  },
  "trace": {
    "llm_model": "qwen3:latest",
    "llm_provider": "ollama",
    "failure_reason": ""
  }
}
```

---

## 6. Proposal Format

The final `.md` file follows this structure:

```markdown
# Proposal from Duke Agares

## Executive Summary
(4-6 sentences)

## Overview
(3-5 sentences: what, current state, why)

## Issues
- Key pain point 1
- Key pain point 2
- ...

## Approach Philosophy
(3-5 sentences: guiding principles)

## Tactics

### T-AGAR-001: Title
- **Description:** ...
- **Deliverable:** D-001
- **Rationale:** ...
- **Prerequisites:** ...
- **Dependencies:** ...
- **Estimated Duration:** P7D
- **Owner:** duke_agares

### T-AGAR-002: Title
...

## Risks

### R-AGAR-001: Title
- **Description:** ...
- **Deliverable:** D-001
- **Likelihood:** RARE|UNLIKELY|POSSIBLE|LIKELY|ALMOST_CERTAIN
- **Impact:** NEGLIGIBLE|MINOR|MODERATE|MAJOR|SEVERE
- **Mitigation Strategy:** ...
- **Contingency Plan:** ...
- **Trigger Conditions:** ...

## Resource Requests

### RR-AGAR-001: Title
- **Type:** COMPUTE|STORAGE|NETWORK|HUMAN_HOURS|TOOLING|EXTERNAL_SERVICE|BUDGET|ACCESS|OTHER
- **Description:** ...
- **Deliverable:** D-001
- **Justification:** ...
- **Required By:** 2026-06-01T00:00:00Z
- **Priority:** CRITICAL|HIGH|MEDIUM|LOW

## Requirement Coverage
| Requirement ID | Type | Covered | Description | Tactic References | Confidence |
|---------------|------|---------|-------------|-------------------|------------|
| FR-TECH-001 | functional | Yes | How addressed | T-AGAR-001 | HIGH |

## Deliverable Plan
| Deliverable ID | Approach | Tactic References | Duration | Dependencies |
|---------------|----------|-------------------|----------|--------------|
| D-001 | How to produce it | T-AGAR-001 | P14D | |

## Capacity Commitment
| Field | Value |
|-------|-------|
| Portfolio ID | duke_agares |
| Committed Units | 40.0 |
| Unit Label | hours |
| Confidence | HIGH |

## Assumptions
- Assumption 1
- Assumption 2

## Constraints Acknowledged
- Constraint 1 (C-001)
- Constraint 2 (C-002)
```

---

## 7. Count Extraction

Counts in the JSON sidecar are derived from the final Markdown, not from
structured LLM output:

| Count | Extraction method |
|-------|-------------------|
| `tactics` | Count lines matching `^### T-` |
| `risks` | Count lines matching `^### R-` (not `^### RR-`) |
| `resource_requests` | Count lines matching `^### RR-` |
| `requirement_coverage` | Data rows in the `## Requirement Coverage` table (total rows minus header) |
| `deliverable_plans` | Data rows in the `## Deliverable Plan` table |
| `assumptions` | Bullet items (`- `) under `## Assumptions` |
| `constraints` | Bullet items (`- `) under `## Constraints Acknowledged` |

---

## 8. Lint Validation

After Phase 4 consolidation, the proposal is linted for constitutional
compliance before being accepted.

**Cross-branch assignment check:** Scans for assignment phrases
(`must be performed by`, `must be validated by`, `must be approved by`,
`assigned to the`, `responsibility of the`) co-occurring with branch terms
(`legislative`, `executive`, `judicial`, `conclave shall`, `king shall`,
`president shall`).

If any violation is detected, the proposal is marked `FAILED` with the
violation description as the `failure_reason`.

---

## 9. Event Trail

Events are appended to `duke_proposal_events.jsonl`:

| Event | When |
|-------|------|
| `duke_proposal.started` | Pipeline begins for all Dukes |
| `duke_proposal.requested` | A single Duke's generation is starting |
| `duke_proposal.received` | A Duke's proposal was successfully generated |
| `duke_proposal.retry` | A retryable error triggered a retry attempt |
| `duke_proposal.failed` | A Duke's proposal generation failed after all retries |
| `duke_proposal.complete` | All Dukes processed |

---

## 10. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRETARY_TEXT_ARCHON_ID` | (none) | UUID of Secretary Text archon for Phase 4 consolidation; if unset, Phase 4 is skipped |
| `DUKE_PROPOSAL_MAX_RETRIES` | 3 | Service-level retries per Duke |
| `DUKE_PROPOSAL_INTER_REQUEST_DELAY` | 1.0 | Seconds between Dukes (service layer) |
| `DUKE_PROPOSAL_BACKOFF_BASE_SECONDS` | 2.0 | Base backoff for service-level retries |
| `DUKE_PROPOSAL_BACKOFF_MAX_SECONDS` | 15.0 | Max backoff cap for service-level retries |
| `DUKE_PROPOSAL_CREWAI_RETRIES` | 3 | Adapter-level retries per CrewAI call |

Adapter-level backoff uses a separate base/max pair:

| Variable | Default | Description |
|----------|---------|-------------|
| `DUKE_PROPOSAL_BACKOFF_BASE_SECONDS` | 1.0 | Base backoff for adapter-level retries |
| `DUKE_PROPOSAL_BACKOFF_MAX_SECONDS` | 8.0 | Max backoff cap for adapter-level retries |

LLM configuration is per-Duke via `archon-llm-bindings.yaml` through the
profile repository, with global fallback to `qwen3:latest` on Ollama.

---

## 11. Architecture

### Domain Model (`src/domain/models/duke_proposal.py`)

| Class | Purpose |
|-------|---------|
| `DukeProposal` | Aggregate root: identity, RFP reference, status, Markdown body, counts, trace metadata |
| `DukeProposalSummary` | Aggregate statistics across all Duke proposals for one RFP |
| `ProposalStatus` | Enum: `GENERATED`, `FAILED`, `SIMULATION` |

Schema version: `2.0` (Markdown-first with count sidecars).

### Port (`src/application/ports/duke_proposal_generation.py`)

`DukeProposalGeneratorProtocol` defines one method:

```
generate_proposal(rfp, duke_archon_id, duke_name, duke_domain,
                  duke_role, duke_backstory, duke_personality) -> DukeProposal
```

### Service (`src/application/services/duke_proposal_service.py`)

`DukeProposalService` orchestrates:

- `generate_all_proposals()` — sequential generation with retry and inter-request delay
- `_simulate_proposals()` — templated proposals without LLM
- `save_proposals()` — writes per-Duke JSON + MD, summary, inbox manifest
- `load_rfp()` — static method to deserialize `rfp.json`

### Adapter (`src/infrastructure/adapters/external/duke_proposal_crewai_adapter.py`)

`DukeProposalCrewAIAdapter` implements the 5-phase pipeline:

- Per-Duke LLM resolution via profile repository (cached)
- Secretary Text LLM for Phase 4 (resolved via `SECRETARY_TEXT_ARCHON_ID`)
- Checkpoint read/write per phase
- CrewAI Agent/Task/Crew per call with retry and exponential backoff
- Assembly: re-sorts per-deliverable items into grouped `## Tactics`, `## Risks`, `## Resource Requests`
- Count extraction from final Markdown
- Constitutional lint before acceptance

### Factory

`create_duke_proposal_generator()` in the adapter module wires up the adapter
with profile repository, LLM overrides, secretary archon ID, and checkpoint
directory.

### CLI (`scripts/run_duke_proposals.py`)

Resolves RFP path (auto-detect, session, or explicit), loads Dukes from
`docs/archons-base.json` (filters to `branch == "administrative_senior"`),
wires the service and adapter, runs generation, saves results, and prints a
summary with per-Duke status markers (`+` generated, `X` failed, `~` simulation).
