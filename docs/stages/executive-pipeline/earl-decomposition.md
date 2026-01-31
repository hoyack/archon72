# Earl Decomposition Bridge: From Winner Selected to Task Activations

After `run_proposal_selection.py` declares `WINNER_SELECTED`, the Earl
Decomposition Bridge reads the winning Duke proposal, decomposes its
tactics into activation-ready task drafts, matches those tasks to eligible
Aegis Clusters, and calls the existing governance activation API
(`TaskActivationService.create_activation`) to place tasks into the task
lifecycle (`AUTHORIZED -> ACTIVATED -> ROUTED`).

This stage does **not** create a new consent system, tool registry, or
state machine. Those already exist in the governance layer. The bridge
connects executive pipeline artifacts to governance inputs.

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
run_duke_proposals.py              23 Dukes generate proposals
  |
  v
proposals_inbox/                   23 proposal .json + .md pairs
  |
  v
run_proposal_selection.py          11 Presidents score, rank, deliberate
  |
  v
selection/                         Winner selected (WINNER_SELECTED)
  |
  v
run_earl_decomposition.py          Decompose tactics -> task drafts         <- THIS
  |
  v
execution_bridge/                  Task drafts + routing + activations
  |
  v
Governance (TaskActivation)        AUTHORIZED -> ACTIVATED -> ROUTED
  |
  v
Aegis Clusters                     Accept / decline / report
```

---

## 1. Expected Inputs

The bridge requires three input artifacts from upstream pipeline stages
plus two configuration files.

### 1a. `selection_result.json` (from Proposal Selection)

Produced by `run_proposal_selection.py`. The bridge reads `outcome` and
`winning_proposal_id` to identify the winner, then uses `rankings` to
resolve the Duke name.

```json
{
  "schema_version": "1.0",
  "artifact_type": "proposal_selection_result",
  "selection_id": "sel-80b8d82e",
  "status": "DECIDED",
  "outcome": "WINNER_SELECTED",
  "winning_proposal_id": "dprop-gusi-364851af",
  "rfp_id": "rfp-f35d55a37c3e",
  "mandate_id": "mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2",
  "rankings": [
    {
      "proposal_id": "dprop-gusi-364851af",
      "rank": 1,
      "duke_name": "Gusion",
      "duke_abbreviation": "GUSI",
      "statistics": { "mean": 8.24, "median": 8.5, "stddev": 0.72 },
      "tier": "FINALIST"
    },
    {
      "proposal_id": "dprop-barb-8e2f1a03",
      "rank": 2,
      "duke_name": "Barbatos",
      "duke_abbreviation": "BARB",
      "statistics": { "mean": 7.81, "median": 7.9, "stddev": 0.91 },
      "tier": "FINALIST"
    }
  ],
  "deliberation": {
    "recommended_winner_id": "dprop-gusi-364851af",
    "recommendation_rationale": "..."
  },
  "created_at": "2026-01-31T10:00:00+00:00"
}
```

**Required fields the bridge reads:**

| Field | Used for |
|-------|----------|
| `outcome` | Must be `WINNER_SELECTED` or bridge exits |
| `winning_proposal_id` | Identifies the winning proposal |
| `rankings[].proposal_id` | Matched against `winning_proposal_id` |
| `rankings[].duke_name` | Resolves proposal filename (`proposal_gusion.md`) |
| `rankings[].duke_abbreviation` | Fallback for filename resolution |

### 1b. Winning proposal Markdown (from Duke Proposals)

The winning Duke's `.md` file from `proposals_inbox/`. The bridge parses
tactic blocks using the `### T-{ABBREV}-NNN: Title` header pattern.

```markdown
# Proposal from Duke Gusion

## Executive Summary
Gusion proposes a phased approach to implementing the mandate...

## Tactics

### T-GUSI-001: Design Threat Intelligence Schema
- **Description:** Design and validate schema for threat intelligence data
- **Deliverable:** D-001
- **Rationale:** Enables downstream ingestion pipeline
- **Prerequisites:** None
- **Dependencies:** None
- **Estimated Duration:** P14D
- **Owner:** duke_gusion

### T-GUSI-002: Build Ingestion Pipeline
- **Description:** Implement automated ingestion of TI feeds
- **Deliverable:** D-001
- **Rationale:** Core capability required by FR-TECH-001
- **Prerequisites:** T-GUSI-001 completed
- **Dependencies:** T-GUSI-001
- **Estimated Duration:** P21D
- **Owner:** duke_gusion

### T-GUSI-003: Implement Audit Trail
- **Description:** Add audit logging to all TI operations
- **Deliverable:** D-002
- **Rationale:** Required by NFR-AUDIT-01
- **Prerequisites:** T-GUSI-001
- **Dependencies:** T-GUSI-001
- **Estimated Duration:** P7D
- **Owner:** duke_gusion

## Risks

### R-GUSI-001: Schema Migration Complexity
- **Description:** Existing data may not conform to new schema
- **Likelihood:** POSSIBLE
- **Impact:** MODERATE
...
```

**Parsed by the bridge:**

The `parse_tactics_from_markdown()` method extracts each `### T-{ABBREV}-NNN:`
block into a `TacticContext`:

| Markdown field | TacticContext field | Required |
|----------------|---------------------|----------|
| Header `T-GUSI-001` | `tactic_id` | Yes |
| Header `: Title` | `title` | Yes |
| `**Description:**` | `description` | Falls back to title |
| `**Deliverable:**` | `deliverable_id` | No |
| `**Prerequisites:**` | `prerequisites` | No |
| `**Dependencies:**` | `dependencies` | No |
| `**Estimated Duration:**` | `duration` | No |
| `**Owner:**` | `owner` | No |
| `**Rationale:**` | `rationale` | No |

### 1c. `rfp.json` (from RFP Generation)

The Implementation Dossier, used for requirement cross-referencing and
provenance mapping.

```json
{
  "implementation_dossier_id": "rfp-f35d55a37c3e",
  "mandate_id": "mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2",
  "deliverables": [
    {
      "deliverable_id": "D-001",
      "name": "Threat Intelligence Platform",
      "acceptance_criteria": [
        "Automated ingestion of 3+ TI feeds",
        "Query latency under 200ms at p95"
      ]
    }
  ],
  "requirements": {
    "functional": [
      { "req_id": "FR-TECH-001", "description": "..." },
      { "req_id": "FR-CONF-002", "description": "..." }
    ],
    "non_functional": [
      { "req_id": "NFR-AUDIT-01", "description": "..." }
    ]
  },
  "constraints": [
    { "constraint_id": "C-001", "description": "Must use existing data store" }
  ]
}
```

**Fields the bridge extracts:**

| Field | Purpose |
|-------|---------|
| `implementation_dossier_id` | Attached to every TaskDraft as `rfp_id` |
| `mandate_id` | Attached to every TaskDraft |
| `deliverables` | Looked up by `deliverable_id` from each tactic |
| `requirements.functional[].req_id` | Passed to decomposer as `related_fr_ids` |
| `requirements.non_functional[].req_id` | Passed to decomposer as `related_nfr_ids` |
| `constraints` | Passed to decomposer for awareness |

### 1d. Cluster definition JSON files (configuration)

Aegis Cluster definitions read from `--cluster-dir` (default:
`docs/governance/examples/`). Each `*.json` file defines a cluster's
capabilities, availability, and consent policy.

```json
{
  "cluster_id": "9c5f8a55-06f2-4f2b-bd95-0d2b9d14b0c4",
  "version": "1.0.0",
  "name": "Aegis Cluster 17 — Research & Analysis",
  "status": "active",
  "steward": {
    "steward_id": "steward-17",
    "display_name": "Cluster Steward 17",
    "contact": { "channel": "slack", "address": "#aegis-cluster-17" },
    "auth_level": "standard"
  },
  "capabilities": {
    "tags": ["research", "analysis", "writing"],
    "tooling": ["google_docs", "github", "notion"],
    "domain_focus": ["security", "ai_governance"]
  },
  "capacity": {
    "availability_status": "available",
    "max_concurrent_tasks": 3,
    "max_weekly_task_load": 10,
    "timezone": "America/Chicago"
  },
  "consent_policy": {
    "requires_explicit_acceptance": true,
    "refusal_is_penalty_free": true
  }
}
```

**Fields used for capability matching:**

| Field | Matching rule |
|-------|---------------|
| `status` | Must be `active` (not `paused` or `retired`) |
| `capacity.availability_status` | Must not be `unavailable` |
| `capabilities.tags` | Must be a superset of task's `capability_tags` |
| `steward.auth_level` | Must meet or exceed task sensitivity level |

### 1e. `earl_routing_table.json` (configuration)

Maps portfolio domains to Earl IDs for activation routing.

```json
{
  "schema_version": "1.0",
  "default_earl_id": "3af355a1-9026-4d4a-9294-9964bf230751",
  "portfolio_to_earl": {
    "acquisition": "07fec517-1529-4499-aa55-b0a9faaf47b1",
    "transformation": "3af355a1-9026-4d4a-9294-9964bf230751",
    "knowledge": "3af355a1-9026-4d4a-9294-9964bf230751",
    "military": "3836da54-2509-4dc1-be4d-0c321cd66e58"
  }
}
```

The bridge uses `default_earl_id` for activations in the MVP. In
multi-Earl LLM mode, `portfolio_to_earl` is also used for **facilitator
resolution**: the tactic's deliverable domain is matched against
portfolio entries to select which Earl synthesizes the collaborative
decomposition. If no match is found, `default_earl_id` (Bifrons) is the
fallback facilitator.

---

## 2. Run It

### Auto-detect (recommended)

```bash
python scripts/run_earl_decomposition.py
```

Finds the most recent `selection/` output under the latest RFP session
mandate directory, loads the winning proposal, RFP, and cluster
definitions, then generates task drafts, matches clusters, and submits
activation requests.

### From a specific selection directory

```bash
python scripts/run_earl_decomposition.py \
  --from-selection-dir _bmad-output/rfp/rfp_f35d55a37c3e/mandates/mandate-80b8d82e/selection
```

### From a specific selection result

```bash
python scripts/run_earl_decomposition.py \
  --selection-file _bmad-output/rfp/rfp_f35d55a37c3e/mandates/mandate-80b8d82e/selection/selection_result.json
```

### Simulation mode (no LLM)

```bash
python scripts/run_earl_decomposition.py --mode simulation -v
```

Produces deterministic task drafts (2 per tactic) and runs the full
bridge including cluster matching. No LLM calls.

### Single tactic (debug)

```bash
python scripts/run_earl_decomposition.py --tactic-id T-GUSI-002
```

Decomposes and routes one tactic only. All other tactics are skipped.

### Drafts only (no activation)

```bash
python scripts/run_earl_decomposition.py --no-activate
```

Generates task drafts and routing plan but does not call
`create_activation()`. Produces all output files except activation IDs.

### Dry run (no file writes)

```bash
python scripts/run_earl_decomposition.py --dry-run -v
```

Runs the full pipeline (decompose, lint, route) but writes nothing to
disk and does not call activation. Useful for inspecting verbose output.

### Resume after partial failure

```bash
python scripts/run_earl_decomposition.py -v
```

If a previous run failed mid-tactic, checkpoints for completed tactics
are preserved. Re-running picks up from the last successful tactic.

### Fresh start (clear old checkpoints)

```bash
python scripts/run_earl_decomposition.py --clear-checkpoints -v
```

Deletes checkpoint directory before starting. Forces re-decomposition of
all tactics.

---

## 3. All Flags

| Flag | Description |
|------|-------------|
| `--selection-file PATH` | Path to `selection_result.json` |
| `--from-selection-dir PATH` | Directory containing `selection_result.json` |
| `--rfp-file PATH` | Explicit `rfp.json` path (auto-detect if omitted) |
| `--proposal-md PATH` | Explicit winning proposal markdown path |
| `--cluster-dir PATH` | Directory of cluster definition JSON files (default: `docs/governance/examples`) |
| `--earl-routing-table PATH` | Path to `earl_routing_table.json` (default: `configs/admin/earl_routing_table.json`) |
| `--mode {llm,simulation,auto}` | Decomposition mode (default: `auto`) |
| `--tactic-id STR` | Decompose only a single tactic ID |
| `--max-tasks-per-tactic INT` | Explosion cap (default: 8) |
| `--ttl-hours INT` | TTL for activations in hours (default: 72) |
| `--route-top-k INT` | Route to top K eligible clusters per task (default: 1) |
| `--no-activate` | Generate drafts + routing plan without calling `create_activation()` |
| `--dry-run` | Do everything except writing outputs and calling activation |
| `--checkpoint-dir PATH` | Override checkpoint directory |
| `--no-checkpoint` | Disable checkpointing |
| `--clear-checkpoints` | Delete checkpoint directory before run |
| `-v` / `--verbose` | Verbose logging |

---

## 4. What This Stage Does

### Step A: Load winner + proposal + RFP

1. Reads `selection_result.json` from the selection directory
2. Verifies `outcome == "WINNER_SELECTED"` (exits if not)
3. Extracts `winning_proposal_id` and resolves Duke name from `rankings`
4. Loads the winning proposal from `proposals_inbox/proposal_{duke_name}.md`
5. Loads `rfp.json` from the mandate directory
6. Parses tactic blocks (`### T-{ABBREV}-NNN: Title`) from the proposal

### Step B: Decompose each tactic into TaskDrafts

For each tactic, the decomposer adapter produces 1..N TaskDrafts. The
bridge builds a `DecompositionContext` per tactic that includes:

- The tactic itself (ID, title, description, deliverable reference)
- RFP-level data (FR/NFR IDs, constraints, deliverable acceptance criteria)
- Proposal identity (rfp_id, mandate_id, proposal_id)

Each produced TaskDraft is:

- Singular and bounded (one executor can complete it)
- Referenced to its parent tactic ID
- Tagged with required capability tags
- Annotated with effort estimate and expected outcomes

#### Multi-Earl collaborative decomposition (LLM mode)

In LLM mode, all 6 Earls from the `administrative_strategic` branch
independently decompose each tactic, then a facilitator Earl synthesizes
the best elements into a final unified set of TaskDrafts.

| Earl | Domain | Model |
|------|--------|-------|
| Raum | acquisition | nemotron-3-nano:30b-cloud |
| Furfur | weather, discord | kimi-k2-thinking:cloud |
| Marax | astronomy, education | gpt-oss:120b-cloud |
| Halphas | military | gemma3:27b-cloud |
| Bifrons | transformation, knowledge | deepseek-v3.1:671b-cloud |
| Andromalius | asset_recovery | ministral-3:14b-cloud |

**Pipeline per tactic:**

```
Load all 6 Earls via profile_repository.get_by_branch("administrative_strategic")
  |
  v
Run all 6 Earls sequentially (each with own LLM from archons-base.json):
  Earl Raum         -> [TaskDraft, ...]    checkpoint: T-XXX-NNN.earl_raum.json
  Earl Furfur       -> [TaskDraft, ...]    checkpoint: T-XXX-NNN.earl_furfur.json
  Earl Marax        -> [TaskDraft, ...]    checkpoint: T-XXX-NNN.earl_marax.json
  Earl Halphas      -> [TaskDraft, ...]    checkpoint: T-XXX-NNN.earl_halphas.json
  Earl Bifrons      -> [TaskDraft, ...]    checkpoint: T-XXX-NNN.earl_bifrons.json
  Earl Andromalius  -> [TaskDraft, ...]    checkpoint: T-XXX-NNN.earl_andromalius.json
  |
  v
Save per-Earl vote metadata: T-XXX-NNN.earl_votes.json
  |
  v
Resolve facilitator Earl (closest domain match from earl_routing_table.json)
  |
  v
Facilitator receives all decompositions, merges best elements,
resolves conflicts, outputs final unified TaskDrafts
  |
  v
Save final: T-XXX-NNN.task_drafts.json (with vote_count / contributing_earls)
```

**Facilitator resolution:** The tactic's deliverable domain is matched
against `portfolio_to_earl` in `earl_routing_table.json`. If no match,
falls back to `default_earl_id` (Bifrons). The facilitator uses its own
LLM for the synthesis call.

**Failure handling:**
- If an Earl's LLM returns empty/errors: skip that Earl, continue
- If 1+ Earls succeed: synthesis proceeds with partial results
- If ALL 6 fail: return empty list (triggers `AMBIGUOUS` status via lint)

Each Earl's CrewAI agent uses the Earl's own identity from
`archons-base.json` (`role`, `backstory`) and their bound LLM model.

> **Lesson learned:** Earls are resolved via
> `get_by_branch("administrative_strategic")` — not
> `get_by_rank("strategic_director")`, which also returns Princes and
> Knight-Witness Furcas (14 archons instead of 6).

#### Simulation mode

**Simulation mode** produces exactly 2 tasks per tactic:
- Task `a`: "Design and document approach" (8 effort hours)
- Task `b`: "Implement and verify" (16 effort hours, depends on task `a`)

Both use tags `["dev_backend", "qa_testing"]`.

### Step C: Lint each TaskDraft

Every TaskDraft passes through hard lint and provenance checks before
being accepted (see Section 7 for full rules).

### Step D: Match TaskDrafts to eligible Clusters

Uses the cluster registry to find Clusters whose `capabilities.tags`
include the task's required tags. Filters by:

1. `cluster.status == active`
2. `cluster.capacity.availability_status != unavailable`
3. `required_tags` is a subset of `cluster.capabilities.tags`
4. Steward `auth_level` meets sensitivity gate

Selects top-K clusters per task (default: 1 for deterministic MVP).
Results sorted by `cluster_id` for deterministic ordering.

### Step E: Create activations

For each matched TaskDraft + Cluster pair, calls the existing
`TaskActivationService.create_activation()` with:

- `earl_id` from `earl_routing_table.json`
- `cluster_id` from capability matching
- `description` from the decomposed task
- `requirements` from the task (includes FR/NFR references)
- `expected_outcomes` (completion criteria)
- `ttl` (default 72 hours)

If `--no-activate` is set or no `TaskActivationService` is wired, this
step is skipped. Tasks remain at `PENDING_ACTIVATION` status.

---

## 5. Expected Outputs

All outputs are written to `<mandate-dir>/execution_bridge/`.

```
<mandate-dir>/execution_bridge/
├── task_drafts.json              # All valid TaskDrafts (pre-routing)
├── routing_plan.json             # Per-tactic decomposition status + task refs
├── activation_manifest.json      # TaskDraft -> cluster -> activation status
├── bridge_summary.json           # Aggregate counts, failures, warnings
├── bridge_events.jsonl           # Append-only event trail
└── checkpoints/                  # Per-tactic checkpoint files
    ├── T-GUSI-001.task_drafts.json
    ├── T-GUSI-002.task_drafts.json
    └── ...
```

### 5a. `task_drafts.json`

All TaskDrafts that passed hard lint. One entry per task.

```json
[
  {
    "task_ref": "TASK-GUSI-001a",
    "parent_tactic_id": "T-GUSI-001",
    "rfp_id": "rfp-f35d55a37c3e",
    "mandate_id": "mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2",
    "proposal_id": "dprop-gusi-364851af",
    "description": "Design and document approach for: Design Threat Intelligence Schema. Produce specification and test plan.",
    "requirements": [
      "Addresses FR-TECH-001",
      "Contributes to deliverable D-001"
    ],
    "expected_outcomes": [
      "Written specification for Design Threat Intelligence Schema reviewed and accepted",
      "Test plan with at least 3 acceptance criteria defined"
    ],
    "capability_tags": ["dev_backend", "qa_testing"],
    "effort_hours": 8.0,
    "deliverable_id": "D-001",
    "dependencies": []
  },
  {
    "task_ref": "TASK-GUSI-001b",
    "parent_tactic_id": "T-GUSI-001",
    "rfp_id": "rfp-f35d55a37c3e",
    "mandate_id": "mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2",
    "proposal_id": "dprop-gusi-364851af",
    "description": "Implement and verify: Design Threat Intelligence Schema. Produce working implementation with passing tests.",
    "requirements": [
      "Addresses FR-TECH-001",
      "Contributes to deliverable D-001"
    ],
    "expected_outcomes": [
      "Implementation of Design Threat Intelligence Schema passes all acceptance tests",
      "Code reviewed and merged to target branch"
    ],
    "capability_tags": ["dev_backend", "qa_testing"],
    "effort_hours": 16.0,
    "deliverable_id": "D-001",
    "dependencies": ["TASK-GUSI-001a"]
  }
]
```

**TaskDraft fields:**

| Field | Description |
|-------|-------------|
| `task_ref` | Unique task reference: `TASK-{ABBREV}-{NNN}{a\|b\|...}` |
| `parent_tactic_id` | The source tactic from the Duke proposal |
| `rfp_id` | Implementation Dossier ID for provenance |
| `mandate_id` | Mandate ID for provenance |
| `proposal_id` | Winning proposal ID for provenance |
| `description` | What the executor must do (singular, bounded) |
| `requirements` | FR/NFR references and deliverable contributions |
| `expected_outcomes` | Completion criteria (minimum 2) |
| `capability_tags` | Required cluster capabilities for routing |
| `effort_hours` | Estimated effort (must be > 0) |
| `deliverable_id` | Which deliverable this task contributes to |
| `dependencies` | Other task_refs that must complete first |
| `vote_count` | (LLM mode) Number of Earls whose decomposition contributed to this task |
| `contributing_earls` | (LLM mode) Names of Earls who contributed to this task's synthesis |

### 5b. `routing_plan.json`

Per-tactic decomposition manifest showing status and produced task refs.

```json
[
  {
    "tactic_id": "T-GUSI-001",
    "tactic_title": "Design Threat Intelligence Schema",
    "status": "completed",
    "task_refs": ["TASK-GUSI-001a", "TASK-GUSI-001b"],
    "failure_reason": "",
    "events": []
  },
  {
    "tactic_id": "T-GUSI-002",
    "tactic_title": "Build Ingestion Pipeline",
    "status": "completed",
    "task_refs": ["TASK-GUSI-002a", "TASK-GUSI-002b"],
    "failure_reason": "",
    "events": []
  },
  {
    "tactic_id": "T-GUSI-003",
    "tactic_title": "Implement Audit Trail",
    "status": "completed",
    "task_refs": ["TASK-GUSI-003a", "TASK-GUSI-003b"],
    "failure_reason": "",
    "events": ["bridge.provenance.weak_mapping"]
  }
]
```

**Possible status values:**

| Status | Meaning |
|--------|---------|
| `completed` | Tactic decomposed successfully |
| `ambiguous` | No valid TaskDrafts after lint |
| `review_required` | Too many drafts (explosion cap exceeded) |
| `overlap_review` | Duplicate task pattern detected |
| `failed` | Decomposition threw an error |

### 5c. `activation_manifest.json`

Per-task routing and activation results with full provenance chain.

```json
[
  {
    "task_ref": "TASK-GUSI-001a",
    "parent_tactic_id": "T-GUSI-001",
    "deliverable_id": "D-001",
    "rfp_requirement_ids": ["FR-TECH-001"],
    "cluster_id": "9c5f8a55-06f2-4f2b-bd95-0d2b9d14b0c4",
    "activation_id": "",
    "status": "PENDING_ACTIVATION",
    "routing_block_reason": ""
  },
  {
    "task_ref": "TASK-GUSI-002a",
    "parent_tactic_id": "T-GUSI-002",
    "deliverable_id": "D-001",
    "rfp_requirement_ids": ["FR-TECH-001"],
    "cluster_id": "",
    "activation_id": "",
    "status": "BLOCKED_BY_CAPABILITY",
    "routing_block_reason": "No eligible cluster"
  }
]
```

**Possible status values:**

| Status | Meaning |
|--------|---------|
| `PENDING_ACTIVATION` | Matched to cluster, awaiting `create_activation()` |
| `ROUTED` | `create_activation()` succeeded |
| `ACTIVATION_FAILED` | `create_activation()` returned an error |
| `BLOCKED_BY_CAPABILITY` | No cluster has the required capability tags |
| `ROUTED_WITH_CAPACITY_DEBT` | Cluster matched but capacity is unknown |

### 5d. `bridge_summary.json`

Aggregate statistics for the entire run.

```json
{
  "schema_version": "1.0",
  "artifact_type": "earl_decomposition_summary",
  "rfp_id": "rfp-f35d55a37c3e",
  "mandate_id": "mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2",
  "proposal_id": "dprop-gusi-364851af",
  "winning_duke_name": "Gusion",
  "created_at": "2026-01-31T12:00:00+00:00",
  "total_tactics": 3,
  "total_task_drafts": 6,
  "activations_attempted": 0,
  "activations_created": 0,
  "activations_failed": 0,
  "ambiguous_tactics": 0,
  "no_eligible_cluster": 2,
  "capacity_blocked": 0,
  "explosion_review": 0,
  "overlap_review": 0,
  "weak_provenance": 1
}
```

**Summary fields:**

| Field | Description |
|-------|-------------|
| `total_tactics` | Number of tactics processed |
| `total_task_drafts` | TaskDrafts that passed hard lint |
| `activations_attempted` | `create_activation()` calls made |
| `activations_created` | Successful activations |
| `activations_failed` | Failed activations |
| `ambiguous_tactics` | Tactics with 0 valid drafts |
| `no_eligible_cluster` | Tasks with no matching cluster |
| `capacity_blocked` | Tasks blocked by cluster capacity |
| `explosion_review` | Tactics exceeding `--max-tasks-per-tactic` |
| `overlap_review` | Tactics with duplicate task patterns |
| `weak_provenance` | Tasks referencing deliverables without FR/NFR IDs |

### 5e. `bridge_events.jsonl`

Append-only event trail. One JSON object per line.

```json
{"event_type": "bridge.started", "timestamp": "2026-01-31T12:00:00+00:00", "payload": {"selection_file": "...", "proposal_id": "dprop-gusi-364851af", "duke_name": "Gusion"}}
{"event_type": "bridge.loaded_selection", "timestamp": "2026-01-31T12:00:00+00:00", "payload": {"outcome": "WINNER_SELECTED", "winning_proposal_id": "dprop-gusi-364851af"}}
{"event_type": "bridge.loaded_proposal", "timestamp": "2026-01-31T12:00:00+00:00", "payload": {"tactic_count": 3}}
{"event_type": "bridge.tactic.decomposition_started", "timestamp": "2026-01-31T12:00:01+00:00", "payload": {"tactic_id": "T-GUSI-001", "title": "Design Threat Intelligence Schema"}}
{"event_type": "bridge.tactic.decomposition_completed", "timestamp": "2026-01-31T12:00:01+00:00", "payload": {"tactic_id": "T-GUSI-001", "task_count": 2}}
{"event_type": "bridge.task.routing_completed", "timestamp": "2026-01-31T12:00:02+00:00", "payload": {"task_ref": "TASK-GUSI-001a", "cluster_ids": ["9c5f8a55-..."]}}
{"event_type": "bridge.routing.no_eligible_cluster", "timestamp": "2026-01-31T12:00:02+00:00", "payload": {"task_ref": "TASK-GUSI-002a", "required_tags": ["dev_backend", "qa_testing"]}}
{"event_type": "bridge.complete", "timestamp": "2026-01-31T12:00:03+00:00", "payload": {"total_drafts": 6}}
```

---

## 6. Expected Console Output

### Verbose simulation run

```
$ python scripts/run_earl_decomposition.py --mode simulation -v

Winner: Gusion (dprop-gusi-364851af)
Found 3 tactics in proposal
Mode: simulation
  [event] bridge.started
  [event] bridge.loaded_selection
  [event] bridge.loaded_proposal
  [event] bridge.tactic.decomposition_started
    [checkpoint] saved T-GUSI-001.task_drafts.json
  [event] bridge.tactic.decomposition_completed
  [event] bridge.tactic.decomposition_started
    [checkpoint] saved T-GUSI-002.task_drafts.json
  [event] bridge.tactic.decomposition_completed
  [event] bridge.tactic.decomposition_started
    [checkpoint] saved T-GUSI-003.task_drafts.json
  [event] bridge.provenance.weak_mapping
  [event] bridge.tactic.decomposition_completed
Produced 6 task drafts
  [cluster-registry] loaded 1 clusters
  [event] bridge.routing.no_eligible_cluster
  ...
  [event] bridge.complete
  [bridge] outputs saved to .../execution_bridge

Earl Decomposition Bridge Summary
  Tactics processed:     3
  Task drafts created:   6
  Activations created:   0
  Activations failed:    0
  No eligible cluster:   6
  Weak provenance:       1
```

The `No eligible cluster: 6` above is expected when the example cluster
(`research`, `analysis`, `writing`) does not match the simulation's
required tags (`dev_backend`, `qa_testing`). This is correct behavior —
the bridge surfaces the mismatch rather than silently skipping.

### Verbose LLM run (multi-Earl)

```
$ python scripts/run_earl_decomposition.py -v --tactic-id T-ZEPA-001 --no-activate

Winner: ZEPA (dprop-zepa-a0fdfc25)
Found 13 tactics in proposal
Mode: LLM (CrewAI multi-Earl)
  [event] bridge.started
  [event] bridge.loaded_selection
  [event] bridge.loaded_proposal
  [event] bridge.tactic.decomposition_started
  [earl] Raum decomposing T-ZEPA-001 (nemotron-3-nano:30b-cloud)...
    [checkpoint] saved T-ZEPA-001.earl_raum.json (3 tasks)
  [earl] Furfur decomposing T-ZEPA-001 (kimi-k2-thinking:cloud)...
    [earl] Furfur: empty response (skipping)
  [earl] Marax decomposing T-ZEPA-001 (gpt-oss:120b-cloud)...
    [checkpoint] saved T-ZEPA-001.earl_marax.json (4 tasks)
  [earl] Halphas decomposing T-ZEPA-001 (gemma3:27b-cloud)...
    [checkpoint] saved T-ZEPA-001.earl_halphas.json (5 tasks)
  [earl] Bifrons decomposing T-ZEPA-001 (deepseek-v3.1:671b-cloud)...
    [checkpoint] saved T-ZEPA-001.earl_bifrons.json (4 tasks)
  [earl] Andromalius decomposing T-ZEPA-001 (ministral-3:14b-cloud)...
    [checkpoint] saved T-ZEPA-001.earl_andromalius.json (3 tasks)
    [checkpoint] saved T-ZEPA-001.earl_votes.json
  [synthesis] Facilitator: Earl Bifrons (default — no domain match)
  [synthesis] Merging 5/6 Earl decompositions...
    [checkpoint] saved T-ZEPA-001.task_drafts.json
  [event] bridge.tactic.decomposition_completed
Produced 4 task drafts
  [cluster-registry] loaded 2 clusters
  [event] bridge.routing.no_eligible_cluster
  ...
  [event] bridge.complete

Earl Decomposition Bridge Summary
  Tactics processed:     1
  Task drafts created:   4
  Activations created:   0
  Activations failed:    0
  No eligible cluster:   4
```

Note that Earl Furfur (kimi-k2-thinking) returned empty responses and
was skipped. The remaining 5 Earls succeeded, and synthesis proceeded
with partial results. This is expected failure handling.

### Quiet run (default)

```
$ python scripts/run_earl_decomposition.py

Earl Decomposition Bridge Summary
  Tactics processed:     3
  Task drafts created:   6
  Activations created:   0
  Activations failed:    0
  No eligible cluster:   6
```

### Error: no winner selected

```
$ python scripts/run_earl_decomposition.py
ERROR: Selection outcome is 'REVISION_REQUESTED', not WINNER_SELECTED. Cannot proceed.
```

### Error: no selection found

```
$ python scripts/run_earl_decomposition.py
ERROR: No RFP session found. Use --selection-file or --from-selection-dir.
```

---

## 7. Decomposition Lint

### Hard lint (TaskDraft must pass)

| Rule | Condition | Result |
|------|-----------|--------|
| Empty description | `description` is empty or whitespace | REJECT |
| Insufficient outcomes | `expected_outcomes` length < 2 | REJECT |
| No capability tags | `capability_tags` empty | REJECT |
| Zero effort | `effort_hours <= 0` | REJECT |
| Missing parent tactic | `parent_tactic_id` empty | REJECT |
| Non-legible outcomes | Outcomes are placeholder text | REJECT |

**Non-legible outcome terms (case-insensitive):** `tbd`, `???`, `n/a`,
`todo`, `finished`, `done`, `complete`, `completed`

### Provenance lint (soft, emits event)

If a TaskDraft references a deliverable (`deliverable_id` set), at least
one requirement line should include an FR or NFR ID (pattern:
`FR-{ABBREV}-{NNN}` or `NFR-{ABBREV}-{NNN}`). If not:

- Draft passes (not rejected)
- Event emitted: `bridge.provenance.weak_mapping`
- Counted in `bridge_summary.json` as `weak_provenance`
- Visible debt for audit

### Tactic-level failures

| Condition | Event | Status |
|-----------|-------|--------|
| 0 valid drafts after lint | `bridge.decomposition.ambiguous_tactic` | `AMBIGUOUS` |
| Drafts > `--max-tasks-per-tactic` | `bridge.decomposition.excessive_scope` | `REVIEW_REQUIRED` |
| Duplicate deliverable + outcomes | `bridge.decomposition.overlap_detected` | `OVERLAP_REVIEW` |

### Routing failures

| Condition | Event | Status |
|-----------|-------|--------|
| No cluster matches required tags | `bridge.routing.no_eligible_cluster` | `BLOCKED_BY_CAPABILITY` |
| Cannot compute headroom | `bridge.routing.capacity_unknown` | `ROUTED_WITH_CAPACITY_DEBT` |

---

## 8. Checkpointing

Checkpoints are saved per-tactic to avoid re-running successful
decompositions on resume.

### Directory structure

**Simulation mode:**

```
<mandate-dir>/execution_bridge/checkpoints/
├── T-GUSI-001.task_drafts.json
├── T-GUSI-002.task_drafts.json
└── T-GUSI-003.task_drafts.json
```

**LLM mode (multi-Earl):**

```
<mandate-dir>/execution_bridge/checkpoints/
├── T-ZEPA-001.earl_raum.json         # Earl Raum's independent decomposition
├── T-ZEPA-001.earl_furfur.json       # Earl Furfur's independent decomposition
├── T-ZEPA-001.earl_marax.json        # ...
├── T-ZEPA-001.earl_halphas.json
├── T-ZEPA-001.earl_bifrons.json
├── T-ZEPA-001.earl_andromalius.json
├── T-ZEPA-001.earl_votes.json        # Per-Earl vote metadata (EarlVote[])
├── T-ZEPA-001.task_drafts.json       # Final synthesized output
└── ...
```

Each per-Earl checkpoint contains that Earl's raw TaskDraft list.
The `earl_votes.json` records which Earls succeeded/failed and how many
tasks each produced. The final `task_drafts.json` is the facilitator's
synthesized output.

### Behavior

| Scenario | What happens |
|----------|-------------|
| Normal run | Checks for checkpoint before each tactic; skips decomposition if found and drafts pass lint |
| `--clear-checkpoints` | Deletes checkpoint directory before starting |
| `--no-checkpoint` | Disables all checkpoint reads and writes |
| Partial failure | Resume continues from last successful tactic |
| Checkpoint + lint fail | If a cached draft fails lint (e.g., rules tightened), it is rejected despite checkpoint |
| Full checkpoint resume (LLM) | If `T-XXX-NNN.task_drafts.json` exists, skip entire tactic (no LLM calls) |
| Partial Earl resume (LLM) | If some `earl_{name}.json` files exist, only re-run missing Earls, then re-synthesize |

---

## 9. Event Trail

Events are appended to `bridge_events.jsonl`:

| Event | When |
|-------|------|
| `bridge.started` | Pipeline begins |
| `bridge.loaded_selection` | Selection result loaded |
| `bridge.loaded_proposal` | Proposal parsed, tactics extracted |
| `bridge.tactic.decomposition_started` | A tactic decomposition begins |
| `bridge.tactic.decomposition_completed` | Tactic successfully decomposed |
| `bridge.tactic.decomposition_failed` | Tactic decomposition threw error |
| `bridge.decomposition.ambiguous_tactic` | Tactic too vague (0 valid drafts) |
| `bridge.decomposition.excessive_scope` | Too many drafts (explosion cap) |
| `bridge.decomposition.overlap_detected` | Duplicate task pattern detected |
| `bridge.provenance.weak_mapping` | Deliverable referenced without FR/NFR |
| `bridge.routing.no_eligible_cluster` | No cluster matches task tags |
| `bridge.task.routing_completed` | Task matched to cluster(s) |
| `bridge.task.activation_created` | Activation successfully created |
| `bridge.task.activation_failed` | Activation failed |
| `bridge.complete` | Pipeline finished |

---

## 10. Capability Matching

The bridge matches TaskDraft capability tags to Aegis Cluster
`capabilities.tags` using the `ClusterRegistryPort`.

### Cluster capability tags (from schema)

`research`, `analysis`, `writing`, `review`, `design`, `dev_backend`,
`dev_frontend`, `devops`, `security`, `data_engineering`, `qa_testing`,
`product_ops`, `community_ops`, `incident_response`, `compliance_ops`,
`other`

### Matching rules

1. Cluster must be `active` (not `paused` or `retired`)
2. `availability_status` must not be `unavailable`
3. All required tags must be present in cluster tags (subset check)
4. Steward auth level must meet task sensitivity gate
5. Results sorted by `cluster_id` for deterministic ordering
6. Top-K selected (configurable via `--route-top-k`)

### Auth level ordering

| Level | Rank | Can handle |
|-------|------|------------|
| `standard` | 0 | Standard tasks only |
| `sensitive` | 1 | Standard + sensitive tasks |
| `restricted` | 2 | All task sensitivity levels |

### MVP adapter

The `ClusterRegistryJsonAdapter` reads `*.json` files from `--cluster-dir`,
validates required fields (`cluster_id`, `status`), and returns matching
candidates. No database required.

---

## 11. Integration with Governance Layer

### Existing components used (not modified)

| Component | Location | Role |
|-----------|----------|------|
| `TaskActivationService` | `src/application/services/governance/task_activation_service.py` | Creates activations with Coercion Filter |
| `TaskState` | `src/domain/governance/task/task_state.py` | 11-state lifecycle machine |
| `TaskActivationRequest` | `src/domain/governance/task/task_activation_request.py` | Filtered content wrapper |
| Cluster Schema | `docs/governance/schemas/cluster-schema.json` | Capability + consent definitions |
| Earl Routing Table | `configs/admin/earl_routing_table.json` | Portfolio-to-Earl mapping |

### TaskState lifecycle (after bridge hands off)

```
AUTHORIZED -> ACTIVATED -> ROUTED -> ACCEPTED -> IN_PROGRESS -> REPORTED
                                  -> DECLINED
                                  -> QUARANTINED
                                  -> NULLIFIED
```

### Provenance chain (end-to-end)

```
Motion (Conclave)
  -> Mandate (Registrar)
    -> FR-TECH-001 (RFP / Presidents)
      -> T-GUSI-001 referencing D-001 (Duke Proposal)
        -> WINNER_SELECTED: Gusion (Selection)
          -> TASK-GUSI-001a from T-GUSI-001 (Earl Decomposition)
            -> TaskState(AUTHORIZED -> ACTIVATED -> ROUTED)
              -> Cluster accepts / declines
                -> ExecutionResult
                  -> Knight witnesses
```

Every link is auditable. Every link has an artifact or event.

---

## 12. Architecture

### Domain Model (`src/domain/models/earl_decomposition.py`)

| Class | Purpose |
|-------|---------|
| `TaskDraft` | Frozen dataclass mapping to `create_activation()` args. Includes `vote_count` and `contributing_earls` for multi-Earl synthesis audit. |
| `EarlVote` | Frozen dataclass tracking per-Earl decomposition results (earl_name, earl_id, task_count, succeeded, failure_reason) |
| `DecompositionStatus` | Enum: COMPLETED, AMBIGUOUS, REVIEW_REQUIRED, OVERLAP_REVIEW, FAILED, FAILED_LINT |
| `RoutingBlockReason` | Enum: BLOCKED_BY_CAPABILITY, BLOCKED_BY_CAPACITY, ROUTED_WITH_CAPACITY_DEBT |
| `TacticDecompositionEntry` | Per-tactic manifest row (tactic_id, status, task_refs, events) |
| `ActivationManifestEntry` | Per-task routing + activation row with provenance chain |
| `BridgeSummary` | Aggregate statistics for the run |

Lint functions:

| Function | Purpose |
|----------|---------|
| `lint_task_draft(draft)` | Hard lint — returns list of violation strings (empty = pass) |
| `check_provenance_mapping(draft)` | Soft lint — returns event descriptions for weak FR/NFR mapping |
| `detect_overlap(drafts)` | Tactic-level — returns pairs of overlapping task refs |

### Port (`src/application/ports/tactic_decomposition.py`)

| Protocol | Method |
|----------|--------|
| `TacticDecomposerProtocol` | `decompose_tactic(context: DecompositionContext) -> list[dict]` |
| `ClusterRegistryPort` | `find_eligible_clusters(tags, sensitivity) -> list[ClusterCandidate]` |
| `ClusterRegistryPort` | `get_all_clusters() -> list[ClusterCandidate]` |

Context dataclasses:

| Class | Purpose |
|-------|---------|
| `TacticContext` | Parsed tactic from Markdown (tactic_id, title, description, deliverable_id, etc.) |
| `DecompositionContext` | Full context for decomposer: tactic + RFP-level references |
| `ClusterCandidate` | Eligible cluster with capability tags, availability, auth level |

### Service (`src/application/services/earl_decomposition_service.py`)

`EarlDecompositionService` orchestrates the pipeline:

| Method | Purpose |
|--------|---------|
| `load_selection_result(path)` | Static — load `selection_result.json` |
| `load_rfp(path)` | Static — load `rfp.json` |
| `load_proposal_markdown(path)` | Static — load winning `.md` file |
| `load_earl_routing_table(path)` | Static — load earl routing config |
| `parse_tactics_from_markdown(md)` | Static — extract `T-XXXX-NNN` blocks into `TacticContext` list |
| `decompose_all(tactics, rfp, ...)` | Iterate tactics, invoke decomposer, apply lint, checkpoint |
| `route_all()` | Match tasks to clusters via `ClusterRegistryPort` |
| `activate_all(service)` | Call `create_activation()` for routed tasks (optional) |
| `save_outputs(output_dir)` | Write `execution_bridge/` directory with all artifacts |
| `print_summary()` | Print human-readable summary to stdout |

### Adapters

| Adapter | Location | Purpose |
|---------|----------|---------|
| `TacticDecomposerCrewAIAdapter` | `src/infrastructure/adapters/external/tactic_decomposer_crewai_adapter.py` | Multi-Earl collaborative decomposition: 6 Earls decompose independently, facilitator Earl synthesizes. Per-Earl LLM from `archons-base.json`. Per-Earl checkpointing. |
| `TacticDecomposerSimulationAdapter` | `src/infrastructure/adapters/external/tactic_decomposer_simulation_adapter.py` | Deterministic: 2 tasks/tactic, fixed tags, no LLM |
| `ClusterRegistryJsonAdapter` | `src/infrastructure/adapters/cluster/cluster_registry_json_adapter.py` | Reads cluster `*.json` files from directory |

### CLI (`scripts/run_earl_decomposition.py`)

Resolves inputs (auto-detect or explicit flags), wires service and
adapters, runs the async pipeline, saves results, and prints summary.

In LLM mode, the script loads the `ArchonProfileRepository` via
`create_archon_profile_repository()` and passes it to the CrewAI adapter
factory. Each Earl resolves its own LLM from profile data — there are no
`--model`, `--provider`, or `--base-url` CLI flags. The `--mode auto`
default tries LLM (requires profiles), and falls back to simulation if
initialization fails.

**Auto-detection order:**
1. Find latest `_bmad-output/rfp/*` session directory (by mtime)
2. Find latest mandate directory within the session
3. Find `selection/selection_result.json` within the mandate
4. Resolve winning Duke name from selection result
5. Find `proposals_inbox/proposal_{duke_name}.md`
6. Find `rfp.json` in the mandate directory

---

## 13. Lessons Learned (Cycle 1: ZEPA mandate)

### Branch vs Rank for Earl resolution

`get_by_rank("strategic_director")` returns **14 archons** — all 7
Princes, all 6 Earls, and Knight-Witness Furcas share
`aegis_rank=strategic_director`. The correct filter is
`get_by_branch("administrative_strategic")` which returns exactly the 6
Earls. This follows the same pattern issue discovered in earlier
pipeline stages.

### Model reliability varies

Earl Furfur's model (`kimi-k2-thinking:cloud`) consistently returned
empty responses across multiple retries and runs. The failure handling
(skip Earl, continue with remaining) works correctly — synthesis
proceeds with 5/6 Earls. No code fix needed; this is a model-level
issue. The `earl_votes.json` checkpoint records which Earls failed and
why, providing observability without manual investigation.

### Synthesis quality improves with diverse models

With 5 successful Earls using different model families (nemotron, gpt-oss,
gemma3, deepseek, ministral), the facilitator's synthesis produced more
nuanced task decompositions than any single Earl. Tasks showed proper
dependency chains, varied capability tags, and detailed expected outcomes
with quantitative thresholds (e.g., "99.9% of Authority-Bearing Actions
within 50ms latency").

### Checkpointing is essential for iterative development

Per-Earl checkpoints enabled rapid iteration during development:
- Full resume (all checkpoints present): instant, zero LLM calls
- Partial resume (some Earls cached): only re-runs missing Earls
- Clearing one Earl's checkpoint and re-running: tests that Earl in isolation

This granularity is worth the extra checkpoint files versus tactic-level-only
checkpointing.

### Cluster routing gap

All 4 synthesized tasks for T-ZEPA-001 received
`BLOCKED_BY_CAPABILITY` — no eligible cluster matched the required tags
(`dev_backend`, `data_engineering`, `security`, etc.). The example
clusters only offer `research`, `analysis`, `writing`. This is a known
gap: the Labor Pipeline (next stage) must define production clusters
with engineering capability tags, or the governance layer must support
manual routing overrides.
