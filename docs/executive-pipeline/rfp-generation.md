# RFP Generation: From Conclave to Implementation Dossier

After Conclave passes a motion, the Executive branch translates it into a detailed
Implementation Dossier (RFP). All 11 Presidents contribute requirements and
constraints from their portfolio perspective. The dossier tells Administrative
**what** is needed without prescribing **how** to build it.

```
Conclave PASS
  |
  v
run_rfp_generator.py          11 Presidents contribute requirements
  |
  v
rfp.json  +  rfp.md           Implementation Dossier (status: final | blocked)
  |
  v
(if blocked) unblock_rfp.py   Diagnose failures, re-run only broken Presidents
  |
  v
Administrative Pipeline       Receives finalized dossier, produces proposals
```

---

## 1. Generate the RFP

### From Conclave output (recommended)

```bash
python scripts/run_rfp_generator.py --from-conclave _bmad-output/conclave
```

This auto-runs the Registrar to convert passed motions into mandates, then
generates a dossier for each mandate.

### From motion ledger

If you already ran the Registrar separately:

```bash
python scripts/run_rfp_generator.py --from-ledger _bmad-output/motion-ledger/<session_id>
```

### From a single mandate file

```bash
python scripts/run_rfp_generator.py --mandate-file path/to/mandate.json
```

### Auto-detect (no flags)

```bash
python scripts/run_rfp_generator.py
```

Picks the most recent conclave results or motion ledger session automatically.

### Common flags

| Flag | Description |
|------|-------------|
| `--mode simulation` | Use template contributions instead of LLM (fast, for testing) |
| `--mode llm` | Use LLM-powered generation (default) |
| `--model qwen3:latest` | Override LLM model for all Presidents |
| `--provider ollama` | Override LLM provider |
| `--base-url http://localhost:11434` | Override LLM base URL |
| `--deliberation-rounds 2` | Enable multi-round deliberation between Presidents |
| `--mandate-id <id>` | Process only one mandate |
| `-v` / `--verbose` | Verbose CrewAI logging |

### Output structure

```
_bmad-output/rfp/<session_id>/
+-- rfp_session_summary.json
+-- mandates/<mandate_id>/
    +-- rfp.json                                    # Structured dossier
    +-- rfp.md                                      # Human-readable version
    +-- rfp_events.jsonl                             # Event trail
    +-- contributions/
        +-- contribution_portfolio_architecture_engineering_standards.json
        +-- contribution_portfolio_adversarial_risk_security.json
        +-- contribution_portfolio_capacity_resource_planning.json
        +-- contribution_portfolio_change_management_migration.json
        +-- contribution_portfolio_ethics_privacy_trust.json
        +-- contribution_portfolio_identity_access_provenance.json
        +-- contribution_portfolio_infrastructure_platform_reliability.json
        +-- contribution_portfolio_model_behavior_alignment.json
        +-- contribution_portfolio_policy_knowledge_stewardship.json
        +-- contribution_portfolio_resilience_incident_response.json
        +-- contribution_portfolio_strategic_foresight_scenario_planning.json
```

### Check the result

After generation, look at the status:

```bash
python -c "
import json, sys
with open('_bmad-output/rfp/<session_id>/mandates/<mandate_id>/rfp.json') as f:
    d = json.load(f)
print(f'Status: {d[\"status\"]}')
print(f'FR:     {len(d[\"requirements\"][\"functional\"])}')
print(f'NFR:    {len(d[\"requirements\"][\"non_functional\"])}')
print(f'Const:  {len(d[\"constraints\"])}')
"
```

- **`final`**: All 11 Presidents contributed successfully. Ready for Administrative.
- **`blocked`**: One or more contributions failed. See Section 2.

---

## 2. Fixing a Blocked RFP

LLM generation is nondeterministic. Common failure modes:

| Failure type | Cause | Typical Presidents |
|---|---|---|
| **lint** | Contribution uses mechanism-specific language (`protocol`, `dashboard`, `schema`) | Gaap, Amy |
| **empty** | LLM returned no content | Marbas, any |
| **parse** | LLM output was not valid JSON | any |
| **timeout** | LLM did not respond in time | any |

`unblock_rfp.py` loads the blocked session, identifies which Presidents failed,
re-runs **only those Presidents**, and rebuilds the dossier in-place.

### Step 1: Diagnose

```bash
python scripts/unblock_rfp.py \
  --session-dir _bmad-output/rfp/<session_id> \
  --diagnose
```

Output shows every President's status:

```
Session diagnosis
  Mandate:  mandate-80b8d82e-21c9-43f2-a090-1702ba2e74e2
  Title:    Require Explicit Attribution and Verifiability...
  Status:   blocked
  Contributions: 11

  [  OK ] Marbas                CONTRIBUTED   FR=3 NFR=1 C=1
  [  OK ] Glasya-Labolas        CONTRIBUTED   FR=2 NFR=0 C=2
  [ FAIL] Gaap                  FAILED        (lint: Mechanism-specific term detected...)
  [  OK ] Valac                 CONTRIBUTED   FR=2 NFR=1 C=0
  ...
  [ FAIL] Marbas                FAILED        (empty: Empty contribution)

  2 failed contribution(s) need re-running.
```

Exit code is `0` if healthy, `1` if blocked.

### Step 2: Re-run with LLM

```bash
python scripts/unblock_rfp.py \
  --session-dir _bmad-output/rfp/<session_id>
```

This re-runs only the failed Presidents, swaps in the new contributions,
rebuilds the full dossier (synthesis + scope + terms), and saves in-place.

### Step 3: If lint failures persist, relax lint

Gaap and Amy often trip the mechanism-term lint (`protocol`, `schema`, `key`).
If re-running doesn't fix it, bypass lint:

```bash
python scripts/unblock_rfp.py \
  --session-dir _bmad-output/rfp/<session_id> \
  --relax-lint
```

This passes `lint_enabled=False` to the adapter. The contribution goes through
without constitutional lint checks. Normal `run_rfp_generator.py` runs still
have lint enabled.

### Step 4: If empty responses persist, increase retries

```bash
python scripts/unblock_rfp.py \
  --session-dir _bmad-output/rfp/<session_id> \
  --max-attempts 5
```

Default is 3 retries per President. Each retry uses exponential backoff.

### Iterative workflow

You can run `unblock_rfp.py` repeatedly. Each run:
- Reads the current state of the session
- Diagnoses what's still broken
- Re-runs only the remaining failures
- Appends events to `rfp_events.jsonl` (never overwrites)

Typical iteration:

```bash
# First pass: re-run with defaults
python scripts/unblock_rfp.py --session-dir _bmad-output/rfp/rfp_f35d55a37c3e

# Still blocked? Diagnose again
python scripts/unblock_rfp.py --session-dir _bmad-output/rfp/rfp_f35d55a37c3e --diagnose

# Gaap still failing on lint? Relax it
python scripts/unblock_rfp.py --session-dir _bmad-output/rfp/rfp_f35d55a37c3e --relax-lint

# Amy timing out? Try a different model with more retries
python scripts/unblock_rfp.py --session-dir _bmad-output/rfp/rfp_f35d55a37c3e \
  --model qwen3:latest --provider ollama --max-attempts 5
```

### All unblock flags

| Flag | Description |
|------|-------------|
| `--session-dir` | Path to the RFP session directory (required) |
| `--mandate-id` | Select mandate if session has multiple |
| `--diagnose` | Print report only, do not re-run |
| `--relax-lint` | Skip constitutional lint checks |
| `--max-attempts N` | Retry attempts per President (default: 3) |
| `--model <model>` | Override LLM model |
| `--provider <provider>` | Override LLM provider |
| `--base-url <url>` | Override LLM base URL |
| `--mode simulation` | Use template contributions (no LLM) |
| `--dump-raw` | Save debug output for each re-run to `contributions/debug_*.txt` |
| `-v` / `--verbose` | Verbose logging |

### Event trail

Every unblock run appends to `rfp_events.jsonl`:

| Event type | When |
|---|---|
| `unblock_started` | Script begins, lists failed Presidents |
| `unblock_contribution_retried` | A President is being re-run |
| `unblock_contribution_succeeded` | Re-run produced a valid contribution |
| `unblock_contribution_failed` | Re-run still failed |
| `unblock_finalized` | Dossier rebuilt and finalized |

### Testing with simulation mode

To verify the pipeline end-to-end without an LLM:

```bash
python scripts/unblock_rfp.py \
  --session-dir _bmad-output/rfp/<session_id> \
  --mode simulation
```

This replaces failed contributions with template data and rebuilds the dossier.
The dossier transitions to `final` status. Useful for testing downstream
Administrative pipeline integration.

---

## 3. What the Dossier Contains

The RFP is structured as an Executive Implementation Dossier:

| Section | Contents |
|---|---|
| Background | Motion text, business justification, strategic alignment |
| Scope of Work | Objectives, in/out of scope, success criteria |
| Functional Requirements | `FR-TECH-001`, `FR-CONF-001`, etc. with MoSCoW priority |
| Non-Functional Requirements | Performance, security, reliability targets |
| Constraints | Technical, resource, organizational limitations |
| Evaluation Criteria | How Administrative proposals will be scored |
| Deliverables | What the solution must produce |
| Terms | Governance requirements, escalation paths |
| Contributing Portfolios | Which President contributed what |
| Open Questions | Unresolved issues (populated when status is `blocked`) |

Each requirement is namespaced by portfolio abbreviation:

| Portfolio | Abbreviation | President |
|---|---|---|
| Architecture & Engineering Standards | TECH | Marbas |
| Adversarial Risk & Security | CONF | Glasya-Labolas |
| Policy & Knowledge Stewardship | KNOW | Gaap |
| Capacity & Resource Planning | RSRC | Valac |
| Infrastructure & Platform Reliability | INFR | Malphas |
| Change Management & Migration | ALCH | Haagenti |
| Model Behavior & Alignment | BEHV | Caim |
| Resilience & Incident Response | WELL | Buer |
| Strategic Foresight & Scenario Planning | ASTR | Amy |
| Identity, Access & Provenance | IDEN | Ose |
| Ethics, Privacy & Trust | ETHC | Foras |

---

## 4. Environment Variables

These control retry/backoff behavior during generation:

| Variable | Default | Description |
|---|---|---|
| `RFP_GENERATOR_MAX_ATTEMPTS` | 2 | Service-level retries per President |
| `RFP_GENERATOR_BACKOFF_BASE_SECONDS` | 2.0 | Base backoff for service retries |
| `RFP_GENERATOR_BACKOFF_MAX_SECONDS` | 15.0 | Max backoff cap |
| `RFP_GENERATOR_INTER_REQUEST_DELAY_SECONDS` | (none) | Delay between Presidents |
| `RFP_CONTRIBUTION_RETRIES` | 3 | Adapter-level retries per President |
| `RFP_CONTRIBUTION_BACKOFF_BASE_SECONDS` | 1.0 | Base backoff for adapter retries |
| `RFP_CONTRIBUTION_BACKOFF_MAX_SECONDS` | 8.0 | Max backoff cap |
| `RFP_CONTRIBUTION_EMPTY_COOLDOWN_SECONDS` | 0 | Extra delay after empty response |
| `SECRETARY_JSON_ARCHON_ID` | (none) | UUID of Secretary archon for JSON repair |

---

## 5. Downstream: Administrative Pipeline

Once the dossier reaches `final` status, it feeds into the Administrative
pipeline. The dossier is the input contract: Administrative produces proposals
that address the requirements, are scored against the evaluation criteria, and
respect the constraints.

See `docs/stages/run-pipeline.md` for the full pipeline sequence.
