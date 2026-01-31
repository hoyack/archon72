# Proposal Selection: From Duke Proposals to Winning Implementation

After Administrative Dukes generate implementation proposals for a finalized RFP,
the 11 Executive Presidents review, score, rank, and deliberate to select a
winning proposal. The selection pipeline fills the gap between Duke Proposals
(Administrative) and Earl Tasking (Administrative Execution).

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
run_proposal_selection.py          11 Presidents score, rank, deliberate    <- THIS
  |
  v
selection/                         Winner selected (or revision/escalation)
  |
  v
Administrative Execution           Earl tasking from winning proposal
```

---

## 1. Run the Selection Pipeline

### Auto-detect (recommended)

```bash
python scripts/run_proposal_selection.py
```

Finds the most recent RFP session, locates `proposals_inbox/` and `rfp.json`,
loads all 11 Executive Presidents, and runs the full 6-phase pipeline.

### From a specific session

```bash
python scripts/run_proposal_selection.py \
  --from-rfp-session _bmad-output/rfp/rfp_f35d55a37c3e
```

### Simulation mode (no LLM)

```bash
python scripts/run_proposal_selection.py --mode simulation -v
```

Generates deterministic scores derived from proposal metadata (tactic count,
risk count, coverage count). Useful for testing the pipeline end-to-end
without an LLM.

### Score only (skip deliberation)

```bash
python scripts/run_proposal_selection.py --score-only
```

Runs phases 1-4 (load, score, novelty, aggregate) but skips the panel
deliberation phase. Produces `score_matrix.json` and rankings without a
final recommendation.

### All flags

| Flag | Description |
|------|-------------|
| `--from-rfp-session PATH` | Path to RFP session directory |
| `--mandate-id STR` | Mandate ID (when multiple mandates exist) |
| `--mode {llm,simulation}` | Scoring mode (default: llm) |
| `--max-rounds N` | Max revision iterations (default: 3) |
| `--top-n N` | Number of finalists for deliberation (default: 5) |
| `--model STR` | Override LLM model |
| `--provider STR` | Override LLM provider |
| `--base-url STR` | Override LLM base URL |
| `--score-only` | Stop after scoring (skip deliberation) |
| `-v` / `--verbose` | Verbose logging |

---

## 2. The 6-Phase Pipeline

### Phase 1: Load Proposals

Reads Duke proposals from `proposals_inbox/` and the RFP from `rfp.json`.
Filters to only `GENERATED` or `SIMULATION` status proposals.

### Phase 2: Score All Proposals

Each of the 11 Presidents scores every proposal on 6 dimensions (0-10 each):

| Dimension | Weight | Description |
|-----------|--------|-------------|
| feasibility | 0.20 | Can this actually be implemented? |
| completeness | 0.25 | Does it cover all RFP requirements? |
| risk_mitigation | 0.15 | Are risks identified and mitigated? |
| resource_efficiency | 0.10 | Is the resource usage reasonable? |
| innovation | 0.10 | Does it bring creative approaches? |
| alignment | 0.20 | Does it align with the RFP objectives? |

Each President also provides: overall score (0-10), confidence (0-1),
reasoning, strengths list, and weaknesses list.

Scoring is sequential per-President with 500ms inter-request delays to
avoid connection storms on rate-limited endpoints.

### Phase 3: Novelty Detection

An analyst agent examines proposals in batches of 10 for novel elements.
Each proposal receives a novelty score (0-1) and category
(`unconventional`, `cross-domain`, `minority-insight`, `creative`, or none).

### Phase 4: Aggregate Rankings

Pure computation (no LLM). For each proposal:

1. Z-score normalization per President to adjust for scoring bias
2. Weighted dimension means using the weights above
3. Novelty bonus: up to +0.5 on the 0-10 scale for proposals scoring ≥ 0.7 novelty
4. Tier assignment:
   - **FINALIST**: adjusted mean ≥ 7.0
   - **CONTENDER**: adjusted mean ≥ 5.0
   - **BELOW_THRESHOLD**: adjusted mean < 5.0
5. Supporter/critic identification (supporters score ≥ 7, critics score < 5)
6. Rank by adjusted mean (descending)

### Phase 5: Deliberation

A facilitator agent presents the top-N finalists to the panel with full
proposal text. The facilitator synthesizes arguments for and against each
finalist, records each President's vote, and recommends a winner.

### Phase 6: Determine Outcome

Decision logic:

| Condition | Outcome |
|-----------|---------|
| Panel recommends winner AND mean ≥ 7.0 | `WINNER_SELECTED` |
| All proposals mean < 5.0 | `NO_VIABLE_PROPOSAL` |
| Unresolved concerns AND round < max_rounds | `REVISION_NEEDED` |
| Round ≥ max_rounds and no winner | `ESCALATE_TO_CONCLAVE` |

---

## 3. Output Structure

```
_bmad-output/rfp/<session>/mandates/<mandate>/selection/
├── selection_result.json              # Full selection result
├── selection_result.md                # Human-readable summary
├── selection_session_summary.json     # Compact summary
├── scores/
│   ├── score_matrix.json              # Full 11×23 matrix
│   ├── scores_by_president/
│   │   ├── scores_marbas.json         # 23 scores from Marbas
│   │   └── ... (11 files)
│   └── scores_by_proposal/
│       ├── scores_dprop-agar-xxx.json # 11 scores for one proposal
│       └── ... (23 files)
├── novelty/
│   ├── novelty_flags.json
│   └── novelty_flags.md
├── deliberation/
│   ├── panel_deliberation.json
│   └── panel_deliberation.md
├── revisions/                         # Only if REVISION_NEEDED
│   └── round_1/
│       ├── feedback_agares.json
│       ├── feedback_valefor.json
│       └── handback.json
└── selection_events.jsonl             # Event trail
```

### Check the result

```bash
python -c "
import json
with open('_bmad-output/rfp/<session>/mandates/<mandate>/selection/selection_result.json') as f:
    d = json.load(f)
print(f'Outcome: {d[\"outcome\"]}')
print(f'Winner:  {d[\"winning_proposal_id\"]}')
print(f'Scores:  {len(d[\"president_scores\"])}')
print(f'Ranked:  {len(d[\"rankings\"])}')
"
```

---

## 4. Revision Loop

When the outcome is `REVISION_NEEDED`:

1. Revision guidance is saved to `revisions/round_N/feedback_<duke>.json`
2. A `handback.json` summarizes constraints and focus areas
3. The user re-runs Duke proposals manually with the revised context
4. Then re-runs `run_proposal_selection.py` again

The loop is manual by default. Automated revision would require coupling the
Duke Proposal and Selection pipelines.

---

## 5. Event Trail

| Event | When |
|-------|------|
| `selection.started` | Pipeline begins |
| `selection.proposals_loaded` | Phase 1 complete |
| `selection.scoring_started` | Phase 2 begins |
| `selection.score_recorded` | Each individual score recorded |
| `selection.scoring_complete` | All scores done |
| `selection.novelty_complete` | Phase 3 complete |
| `selection.aggregation_complete` | Phase 4 complete |
| `selection.deliberation_complete` | Phase 5 complete |
| `selection.outcome` | Phase 6 decision |
| `selection.complete` | Pipeline finished |

---

## 6. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROPOSAL_SCORER_BACKOFF_BASE_SECONDS` | 2.0 | Base backoff for scoring retries |
| `PROPOSAL_SCORER_BACKOFF_MAX_SECONDS` | 8.0 | Max backoff cap |

LLM configuration is per-President via `archon-llm-bindings.yaml`, with
global fallback to `qwen3:latest` on Ollama.

---

## 7. Architecture

### Domain Models (`src/domain/models/proposal_selection.py`)

| Class | Purpose |
|-------|---------|
| `ProposalScore` | One President's score of one proposal (6 dimensions) |
| `ProposalNovelty` | Novelty annotation for a proposal |
| `ProposalRanking` | Aggregated ranking with statistics and tier |
| `SelectionDeliberation` | Panel deliberation result |
| `DukeRevisionGuidance` | Feedback for a Duke needing revision |
| `ProposalSelectionResult` | Aggregate root for the entire selection |
| `SelectionHandback` | Handback package for the revision loop |

### Port (`src/application/ports/proposal_selection.py`)

`ProposalScorerProtocol` defines 4 methods: `score_proposal()`,
`batch_score_proposals()`, `detect_novelty()`, `run_deliberation()`.

### Service (`src/application/services/proposal_selection_service.py`)

`ProposalSelectionService` orchestrates the 6-phase pipeline. Supports
both LLM and simulation modes. Handles aggregation as pure computation.

### Adapter (`src/infrastructure/adapters/external/proposal_scorer_crewai_adapter.py`)

`ProposalScorerCrewAIAdapter` implements the protocol using CrewAI.
Per-President LLM caching, retry with exponential backoff, token truncation
(~800 tokens for scoring, ~3000 for deliberation).
