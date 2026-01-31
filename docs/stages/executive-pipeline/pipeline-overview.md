# Executive Pipeline: Full Run Sequence

End-to-end workflow from Conclave mandate through Administrative execution.
Each stage has its own script, its own artifacts, and its own documentation.
This document ties the stages together with actual commands and real output
from the `rfp_f35d55a37c3e` session.

```
Conclave PASS
  |
  v
(1) run_rfp_generator.py             11 Presidents contribute requirements
  |
  v
rfp.json + rfp.md                    Implementation Dossier (status: final)
  |
  v
(2) run_duke_proposals.py            23 Dukes generate proposals
  |
  v
proposals_inbox/                     23 proposal .json + .md pairs
  |
  v
(3) run_proposal_selection.py        11 Presidents score, rank, deliberate
  |
  v
selection/                           Winner selected (or revision/escalation)
  |
  v
(4) run_selection_handoff.py         Bridge selection result -> handoff contract
  |
  v
administrative_handoff.json          Work package for Earl activation
  |
  v
(5) run_administrative_pipeline.py   Route Earl, filter tools, emit TARs
  |
  v
execution_program.json + TARs        Tasks activated for cluster execution
  |
  v
(6) ingest_task_result.py            Cluster submits result -> state update
  |
  v
(7) reroute_task.py                  On decline -> next tool (or escalate)
```

---

## Stage 1: RFP Generation

**Script:** `scripts/run_rfp_generator.py`
**Docs:** [rfp-generation.md](rfp-generation.md)

The Executive branch translates a Conclave mandate into a detailed
Implementation Dossier. All 11 Presidents contribute requirements from
their portfolio perspective.

### Run it

```bash
# Auto-detect latest conclave output
python scripts/run_rfp_generator.py

# From conclave results
python scripts/run_rfp_generator.py --from-conclave _bmad-output/conclave

# Simulation mode (no LLM)
python scripts/run_rfp_generator.py --mode simulation -v
```

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--from-conclave PATH` | | Path to conclave results |
| `--from-ledger PATH` | | Path to motion ledger session |
| `--mandate-file PATH` | | Path to a single mandate JSON |
| `--mandate-id STR` | | Filter to a single mandate |
| `--mode {llm,simulation}` | `llm` | LLM or template-based generation |
| `--deliberation-rounds N` | `0` | Post-contribution deliberation rounds |
| `--model STR` | | Override LLM model |
| `--provider STR` | | Override LLM provider |
| `--base-url STR` | | Override LLM base URL |
| `-v` | | Verbose logging |

### Output

```
_bmad-output/rfp/rfp_f35d55a37c3e/
├── rfp_session_summary.json
└── mandates/
    └── mandate-80b8d82e-.../
        ├── rfp.json                    # Structured dossier
        ├── rfp.md                      # Human-readable version
        ├── rfp_events.jsonl            # Event trail
        └── contributions/              # 11 portfolio contributions
            ├── contribution_portfolio_adversarial_risk_security.json
            ├── contribution_portfolio_architecture_engineering_standards.json
            ├── contribution_portfolio_capacity_resource_planning.json
            ├── contribution_portfolio_change_management_migration.json
            ├── contribution_portfolio_ethics_privacy_trust.json
            ├── contribution_portfolio_identity_access_provenance.json
            ├── contribution_portfolio_infrastructure_platform_reliability.json
            ├── contribution_portfolio_model_behavior_alignment.json
            ├── contribution_portfolio_policy_knowledge_stewardship.json
            ├── contribution_portfolio_resilience_incident_response.json
            └── contribution_portfolio_strategic_foresight_scenario_planning.json
```

### Blocked RFPs

If one or more Presidents fail (timeout, parse error, lint rejection), the
dossier status is `blocked` instead of `final`. Use `unblock_rfp.py` to
diagnose and re-run only the failed contributions:

```bash
# Diagnose without re-running
python scripts/unblock_rfp.py --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e --diagnose-only

# Re-run failed contributions
python scripts/unblock_rfp.py --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e -v

# Relax lint rules for stubborn failures
python scripts/unblock_rfp.py --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e --relax-lint -v
```

---

## Stage 2: Duke Proposals

**Script:** `scripts/run_duke_proposals.py`

The 23 Administrative Dukes each read the finalized RFP and produce an
implementation proposal from their domain expertise. Each proposal
describes **how** to accomplish the requirements.

### Run it

```bash
# Auto-detect latest RFP session
python scripts/run_duke_proposals.py

# From a specific RFP file
python scripts/run_duke_proposals.py --rfp-file _bmad-output/rfp/rfp_f35d55a37c3e/mandates/mandate-80b8d82e-.../rfp.json

# Single Duke only
python scripts/run_duke_proposals.py --duke-name Gusion -v

# Simulation mode (no LLM)
python scripts/run_duke_proposals.py --mode simulation -v
```

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--rfp-file PATH` | | Path to rfp.json |
| `--from-rfp-session PATH` | | Path to RFP session directory |
| `--mandate-id STR` | | Filter to a single mandate |
| `--mode {llm,simulation,auto}` | `auto` | Generation mode |
| `--duke-name STR` | | Generate for a single Duke only |
| `--model STR` | | Override LLM model |
| `--provider STR` | | Override LLM provider |
| `--base-url STR` | | Override LLM base URL |
| `-v` | | Verbose logging |

### Output

```
mandates/mandate-80b8d82e-.../
└── proposals_inbox/
    ├── proposal_summary.json          # Aggregate summary
    ├── inbox_manifest.json            # Manifest of all proposals
    ├── duke_proposal_events.jsonl     # Event trail
    ├── proposal_agares.json           # Structured proposal
    ├── proposal_agares.md             # Human-readable proposal
    ├── proposal_aim.json
    ├── proposal_aim.md
    └── ... (23 Dukes x 2 files = 46 proposal files)
```

Each proposal contains: executive summary, approach philosophy, tactics
(with dependencies, durations, owners), risks, resource requests,
requirement coverage, and deliverable plans.

---

## Stage 3: Proposal Selection

**Script:** `scripts/run_proposal_selection.py`
**Docs:** [proposal-selection.md](proposal-selection.md)

The 11 Executive Presidents review, score, rank, and deliberate on all 23
Duke proposals to select a winner. The pipeline has 6 phases:

1. **Load** — Read proposals from `proposals_inbox/` and RFP from `rfp.json`
2. **Score** — Each President scores each proposal on 6 dimensions (253 LLM calls)
3. **Novelty** — Analyst agent identifies creative/unconventional elements
4. **Aggregate** — Z-score normalization, weighted means, tier assignment (no LLM)
5. **Deliberate** — Panel facilitator synthesizes arguments and recommends winner
6. **Outcome** — Decision: WINNER_SELECTED, REVISION_NEEDED, NO_VIABLE_PROPOSAL, or ESCALATE_TO_CONCLAVE

### Run it

```bash
# Auto-detect latest session
python scripts/run_proposal_selection.py

# From a specific session
python scripts/run_proposal_selection.py \
  --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e

# Simulation mode (deterministic scores, no LLM)
python scripts/run_proposal_selection.py --mode simulation -v

# Score only (skip deliberation)
python scripts/run_proposal_selection.py --score-only

# With tuning
python scripts/run_proposal_selection.py --max-rounds 2 --top-n 3 -v
```

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--from-rfp-session PATH` | | Path to RFP session directory |
| `--mandate-id STR` | | Mandate ID (when multiple) |
| `--mode {llm,simulation}` | `llm` | Scoring mode |
| `--max-rounds N` | `3` | Maximum revision iterations |
| `--top-n N` | `5` | Finalist count for deliberation |
| `--model STR` | | Override LLM model |
| `--provider STR` | | Override LLM provider |
| `--base-url STR` | | Override LLM base URL |
| `--score-only` | | Stop after scoring |
| `-v` | | Verbose logging |

### Scoring dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| feasibility | 0.20 | Can this actually be implemented? |
| completeness | 0.25 | Does it cover all RFP requirements? |
| risk_mitigation | 0.15 | Are risks identified and mitigated? |
| resource_efficiency | 0.10 | Is the resource usage reasonable? |
| innovation | 0.10 | Does it bring creative approaches? |
| alignment | 0.20 | Does it align with the RFP objectives? |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRETARY_TEXT_ARCHON_ID` | | Archon ID for utility agents (novelty, deliberation) |
| `SECRETARY_JSON_ARCHON_ID` | | Archon ID for JSON repair fallback |
| `PROPOSAL_SCORER_BACKOFF_BASE_SECONDS` | `2.0` | Base backoff for scoring retries |
| `PROPOSAL_SCORER_BACKOFF_MAX_SECONDS` | `8.0` | Max backoff cap |

### Output

```
mandates/mandate-80b8d82e-.../
└── selection/
    ├── selection_result.json          # Full selection result
    ├── selection_result.md            # Human-readable summary
    ├── selection_session_summary.json # Compact summary
    ├── selection_events.jsonl         # Event trail
    ├── scores/
    │   ├── score_matrix.json          # Full 11x23 matrix
    │   ├── scores_by_president/       # 11 files (one per President)
    │   └── scores_by_proposal/        # 23 files (one per proposal)
    ├── novelty/
    │   ├── novelty_flags.json
    │   └── novelty_flags.md
    ├── deliberation/
    │   ├── panel_deliberation.json
    │   └── panel_deliberation.md
    └── revisions/                     # Only if REVISION_NEEDED
        └── round_1/
            ├── feedback_<duke>.json
            └── handback.json
```

### Outcome decision logic

| Condition | Outcome |
|-----------|---------|
| Panel recommends winner AND mean >= 7.0 | `WINNER_SELECTED` |
| All proposals mean < 5.0 | `NO_VIABLE_PROPOSAL` |
| Unresolved concerns AND round < max_rounds | `REVISION_NEEDED` |
| Round >= max_rounds and no winner | `ESCALATE_TO_CONCLAVE` |

---

## Actual Results: Session `rfp_f35d55a37c3e`

The following results are from the first full end-to-end LLM run.

**Motion:** Require Explicit Attribution and Verifiability for All
Authority-Bearing Actions

**Mandate:** `mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2`

### RFP Generation

- 11 Presidents contributed requirements from their portfolios
- Status: `final`
- RFP ID: `eid-3e902f0c-e9a7-4736-bad8-5dbe2a10b82b`

### Duke Proposals

- 23 Dukes produced implementation proposals
- All 23 achieved `GENERATED` status
- Tactic counts ranged from 0 (Gremory) to 9 (Astaroth)

### Proposal Selection

- **253 LLM scoring calls** (11 Presidents x 23 proposals)
- All scores completed successfully
- Secretary Text agent (Orias) handled novelty analysis and deliberation
- Secretary JSON agent (Orobas) repaired malformed JSON during scoring

**Outcome: `WINNER_SELECTED`**

| Rank | Duke | Proposal ID | Mean | Tier | Novelty |
|------|------|-------------|------|------|---------|
| 1 | **Gusion** | dprop-gusi-364851af | 7.1 | FINALIST | +0.40 |
| 2 | Vepar | dprop-vepa-4de95443 | 6.8 | FINALIST | +0.35 |
| 3 | Alloces | dprop-allo-e048ed36 | 6.6 | FINALIST | +0.40 |
| 4 | Valefor | dprop-vale-c8664706 | 6.6 | CONTENDER | +0.35 |
| 5 | Astaroth | dprop-asta-f2e272dc | 7.0 | CONTENDER | +0.00 |

**Winner: Duke Gusion** — Selected for mechanical verification over
interpretive trust, prevention through atomic capture, and independent
verifiability without system knowledge. 8 of 11 Presidents supported,
0 critics.

### Winner dimension scores

| Dimension | Mean | Weight |
|-----------|------|--------|
| alignment | 8.4 | 0.20 |
| completeness | 8.2 | 0.25 |
| feasibility | 7.4 | 0.20 |
| risk_mitigation | 6.6 | 0.15 |
| resource_efficiency | 6.3 | 0.10 |
| innovation | 6.2 | 0.10 |

### Selection Handoff

- Handoff created from selection result + RFP deliverables
- 9 deliverables mapped from RFP (D-TECH-001 through D-WELL-001)
- 11 portfolios included in context
- 2 explicit exclusions extracted from RFP constraints

### Administrative Execution

- Earl Bifrons assigned (default fallback — none of the 11 portfolio keys
  matched the routing table's domain-specific entries)
- 9 TARs emitted to `cluster:alpha` (the only registered HUMAN_CLUSTER tool)
- Program ID: `program-d6d1e216-b994-4232-923b-cb20dae77e49`

---

## Stage 4: Selection Handoff

**Script:** `scripts/run_selection_handoff.py`

Bridges the gap between proposal selection and administrative execution.
Reads the selection result and winning Duke proposal, extracts deliverables
from the RFP, and produces an `administrative_handoff.json` conforming to
the handoff schema at `schemas/contracts/administrative_handoff.schema.json`.

### Run it

```bash
# Auto-detect from latest session
python scripts/run_selection_handoff.py

# From a specific session
python scripts/run_selection_handoff.py \
  --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e

# Verbose output
python scripts/run_selection_handoff.py \
  --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e -v

# Dry run (validate and print, don't write files)
python scripts/run_selection_handoff.py --dry-run -v
```

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--from-rfp-session PATH` | | Path to RFP session directory |
| `--mandate-id STR` | | Mandate ID (when multiple) |
| `--deadline-hours N` | `168` | Hours until work deadline (7 days) |
| `--dry-run` | | Validate and print without writing |
| `-v` | | Verbose logging |

### What it does

1. Loads `selection_result.json` and validates outcome is `WINNER_SELECTED`
2. Loads the winning Duke proposal (JSON metadata + markdown body)
3. Loads `rfp.json` for deliverables, constraints, and portfolio context
4. Maps RFP deliverables into handoff work_package deliverables
5. Extracts exclusions from RFP constraints and scope
6. Builds portfolio context from RFP contribution portfolios
7. Validates the output against schema requirements
8. Writes `administrative_handoff.json` and event trail

### Output

```
mandates/mandate-80b8d82e-.../
└── handoff/
    ├── administrative_handoff.json    # Schema-validated handoff contract
    └── handoff_events.jsonl           # Event trail
```

### Actual result (session `rfp_f35d55a37c3e`)

```
Handoff ID: handoff-063c97a10faf
Award ID:   award-446c6e7988b2
Winner:     Gusion (dprop-gusi-364851af)
Deliverables: 9
  - D-TECH-001: Attribution Schema Specification
  - D-TECH-002: System Boundary Mapping
  - D-TECH-003: Verification Interface Definition
  - D-ALCH-001: Migration Attribution Verification Protocol
  - DEL-ATTR-001: Attribution Binding Capability
  - DEL-VERIF-001: Verification Capability
  - D-INFR-001: Audit Log System
  - D-KNOW-001: Authority Action Attribution Record
  - D-WELL-001: Verifiable Audit Trail
Portfolios: 11 (all Executive portfolios)
Deadline: 7 days from generation
```

### Chaining to Stage 5

The script prints the exact next command on completion:

```bash
python scripts/run_administrative_pipeline.py \
  --handoff <path>/handoff/administrative_handoff.json \
  --earl-routing configs/admin/earl_routing_table.json \
  --tool-registry configs/tools/tool_registry.json \
  --out-dir <path>/execution/ \
  -v
```

---

## Stage 5: Administrative Execution

**Script:** `scripts/run_administrative_pipeline.py`

Routes the winning proposal through an Earl to available tools. Creates
an Execution Program and emits Task Activation Requests (TARs).

### Run it

```bash
python scripts/run_administrative_pipeline.py \
  --handoff <path>/administrative_handoff.json \
  --earl-routing configs/admin/earl_routing_table.json \
  --tool-registry configs/tools/tool_registry.json \
  --out-dir <path>/execution/ \
  -v

# Dry run (TARs written to dry_run/ subdirectory)
python scripts/run_administrative_pipeline.py \
  --handoff <path>/administrative_handoff.json \
  --earl-routing configs/admin/earl_routing_table.json \
  --tool-registry configs/tools/tool_registry.json \
  --out-dir <path>/execution/ \
  --dry-run -v
```

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--handoff PATH` | *required* | Path to administrative_handoff.json |
| `--earl-routing PATH` | *required* | Path to earl_routing_table.json |
| `--tool-registry PATH` | *required* | Path to tool_registry.json |
| `--out-dir PATH` | *required* | Output directory |
| `--tool-class` | `HUMAN_CLUSTER` | Tool class for activation |
| `--required-capabilities` | `doc_drafting` | Comma-separated capabilities |
| `--response-hours N` | `8` | Hours until TAR deadline |
| `--dry-run` | | Write TARs to dry_run/ instead |
| `-v` | | Verbose logging |

### Earl routing

Earls are routed deterministically by portfolio context:

| Portfolio | Earl | ID |
|-----------|------|----|
| acquisition | Raum | 07fec517-... |
| transformation, knowledge | Bifrons | 3af355a1-... |
| military | Halphas | 3836da54-... |
| asset_recovery | Andromalius | 8bfe38f1-... |
| weather, discord | Furfur | 78c885cc-... |
| astronomy, education | Marax | 71d8cccb-... |
| *default fallback* | Bifrons | 3af355a1-... |

### Output

```
execution/
├── execution_program.json             # Program metadata + tasks
├── tars/                              # (or dry_run/)
│   ├── tar-<uuid>.json                # One TAR per deliverable
│   └── ...
└── events.jsonl                       # Event trail
```

---

## Stage 6: Task Result Ingestion

**Script:** `scripts/ingest_task_result.py`

After a tool (human cluster or digital) completes work, it submits a
Task Result Artifact (TRA). This script ingests the result and updates
the task state.

### Run it

```bash
python scripts/ingest_task_result.py \
  --result <path>/task_result_artifact.json \
  --program <path>/execution_program.json \
  --out-dir <path>/execution/ \
  -v
```

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--result PATH` | *required* | Path to task_result_artifact.json |
| `--program PATH` | | Path to execution_program.json (for validation) |
| `--out-dir PATH` | *required* | Output directory |
| `--dry-run` | | Emit events without writing task_state.json |
| `-v` | | Verbose logging |

### Outcome mapping

| TRA Outcome | Task State |
|-------------|------------|
| COMPLETED | CLOSED |
| PARTIAL | CLOSED_PARTIAL |
| DECLINED | NEEDS_REROUTE |
| WITHDRAWN | NEEDS_REROUTE |
| BLOCKED | BLOCKED |
| FAILED | FAILED |

---

## Stage 7: Task Rerouting

**Script:** `scripts/reroute_task.py`

When a tool declines or withdraws, the task enters `NEEDS_REROUTE` state.
This script finds the next eligible tool (excluding previous attempts) and
emits a new TAR. If no tools remain, the task is escalated to the Duke.

### Run it

```bash
python scripts/reroute_task.py \
  --task-state <path>/task_state.json \
  --program <path>/execution_program.json \
  --tool-registry configs/tools/tool_registry.json \
  --out-dir <path>/execution/ \
  -v
```

### Key flags

| Flag | Default | Description |
|------|---------|-------------|
| `--task-state PATH` | *required* | Path to task_state.json |
| `--program PATH` | *required* | Path to execution_program.json |
| `--tool-registry PATH` | *required* | Path to tool_registry.json |
| `--out-dir PATH` | *required* | Output directory |
| `--tool-class` | `HUMAN_CLUSTER` | Tool class for reroute |
| `--required-capabilities` | `doc_drafting` | Comma-separated capabilities |
| `--response-hours N` | `8` | Hours until TAR deadline |
| `--strategy` | `round_robin` | Tool selection strategy |
| `--dry-run` | | Write to dry_run/ instead |
| `-v` | | Verbose logging |

### Reroute loop

```
TAR emitted -> Tool responds
  |
  ACCEPT -> work proceeds
  DECLINE/WITHDRAW -> ingest_task_result.py (NEEDS_REROUTE)
    |
    reroute_task.py -> next eligible tool
      |
      no tools left -> BLOCKED, escalate to Duke
```

---

## Full Session Output Tree

Complete artifact tree from the `rfp_f35d55a37c3e` session:

```
_bmad-output/rfp/rfp_f35d55a37c3e/
├── rfp_session_summary.json
└── mandates/
    └── mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2/
        ├── rfp.json
        ├── rfp.md
        ├── rfp_events.jsonl
        ├── contributions/                     (11 files)
        ├── proposals_inbox/                   (46 files + 3 manifests)
        │   ├── proposal_summary.json
        │   ├── inbox_manifest.json
        │   ├── duke_proposal_events.jsonl
        │   ├── proposal_agares.{json,md}
        │   ├── proposal_aim.{json,md}
        │   ├── ...
        │   └── proposal_zepar.{json,md}
        ├── selection/                         (selection results)
        │   ├── selection_result.json
        │   ├── selection_result.md
        │   ├── selection_session_summary.json
        │   ├── selection_events.jsonl
        │   ├── scores/
        │   │   ├── score_matrix.json
        │   │   ├── scores_by_president/       (11 files)
        │   │   └── scores_by_proposal/        (23 files)
        │   ├── novelty/
        │   │   ├── novelty_flags.json
        │   │   └── novelty_flags.md
        │   ├── deliberation/
        │   │   ├── panel_deliberation.json
        │   │   └── panel_deliberation.md
        │   └── revisions/
        │       └── round_1/
        ├── handoff/
        │   ├── administrative_handoff.json
        │   └── handoff_events.jsonl
        └── execution/
            ├── execution_program.json
            ├── events.jsonl
            └── tars/
                ├── tar-<uuid>.json            (9 TARs, one per deliverable)
                └── ...
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `docs/archons-base.json` | All 72 Archon identities (Presidents, Dukes, Earls) |
| `config/archon-llm-bindings.yaml` | Per-Archon LLM model bindings |
| `configs/admin/earl_routing_table.json` | Portfolio-to-Earl routing |
| `configs/tools/tool_registry.json` | Available tools and capabilities |
| `schemas/contracts/administrative_handoff.schema.json` | Handoff contract schema |

## Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `SECRETARY_TEXT_ARCHON_ID` | Stages 1, 3 | Archon ID for text utility agents |
| `SECRETARY_JSON_ARCHON_ID` | Stages 1, 3 | Archon ID for JSON repair agents |
| `RFP_GENERATOR_MAX_ATTEMPTS` | Stage 1 | Max retry attempts per President |
| `PROPOSAL_SCORER_BACKOFF_BASE_SECONDS` | Stage 3 | Backoff base for scoring retries |
| `PROPOSAL_SCORER_BACKOFF_MAX_SECONDS` | Stage 3 | Max backoff cap |

---

## Completed: Selection Handoff (Stage 4)

- [x] Create `scripts/run_selection_handoff.py`
- [x] Test against current session (`rfp_f35d55a37c3e`, winner: Gusion)
- [x] Run Stage 5 (`run_administrative_pipeline.py`) with the produced handoff
- [x] Update this document with completed Stage 4 commands and output

Full pipeline verified end-to-end:

```bash
# Stage 1: RFP Generation (already done)
# Stage 2: Duke Proposals (already done)
# Stage 3: Proposal Selection (already done)

# Stage 4: Selection Handoff
python scripts/run_selection_handoff.py \
  --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e -v

# Stage 5: Administrative Execution
python scripts/run_administrative_pipeline.py \
  --handoff _bmad-output/rfp/rfp_f35d55a37c3e/mandates/mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2/handoff/administrative_handoff.json \
  --earl-routing configs/admin/earl_routing_table.json \
  --tool-registry configs/tools/tool_registry.json \
  --out-dir _bmad-output/rfp/rfp_f35d55a37c3e/mandates/mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2/execution \
  -v
```
