# Executive Planning v2: Deliberative Presidents + Blocker Disposition + Epic Handoff

**Status:** Planning
**Created:** 2026-01-27
**Author:** System + Human Oversight
**Schema Version:** 2.0

---

## Summary

Upgrade the Executive Pipeline to correct constitutional fault lines in the current implementation:

1. **Presidents (LLM) perform Executive planning** with deliberative mechanics, not manual human inbox editing
2. **Blockers become legible objects with disposition**, allowing planning to continue while preserving integrity
3. **Executive outputs Epics + acceptance intent**, not story points or FR/NFR details

This preserves the constitutional hierarchy: **Kings define WHAT**, **Presidents plan HOW**, **Dukes coordinate reality**, **Earls activate tools/clusters**, **humans are tools/override** (not primary authors).

---

## Problem Statement

### Current Implementation (v1)

The v1 Executive Pipeline implemented:
- E0 (Cycle Open), E1 (Assignment), E2 (Portfolio Drafting), E3 (Integration)
- Manual inbox system with scaffold templates for human editing
- LLM deliberation as an optional path (`--llm-deliberation`)
- Three gates: Completeness, Integrity, Visibility
- Portfolio contributions with tasks and story points

### Constitutional Fault Lines

1. **Human-centric workflow assumption**
   - Scaffold templates assume humans fill in JSON files
   - LLM path was added as secondary, not primary
   - Violates: "Presidents plan HOW" - Presidents are LLM agents, not humans

2. **Blocker halt reflex**
   - Current model: blockers either escalate or don't
   - No disposition mechanism for mitigation or deferral
   - Results in "blocker spam" halting all planning
   - Violates: Executive should produce actionable plans, not escalation queues

3. **Executive outputs are too detailed**
   - Current: tasks with story points, dependencies, constraints
   - Problem: story points and detailed requirements belong in Administration (Dukes)
   - Violates: separation between Executive (HOW strategy) and Administrative (HOW tactics)

4. **Integrity gate is binary**
   - Current: "blockers requiring escalation exist" → integrity concern
   - No nuance for blocker classification or disposition
   - Violates: legitimate blocking conditions vs. resolvable uncertainties

---

## Architectural Commitments

### Invariants (unchanged)

- One motion → one execution plan → one Plan Owner
- All affected portfolios must respond (contribution or attestation)
- No "plan ratification vote" - gates determine validity
- Humans are not required for Executive authoring

### New Constraints

- **Legibility gate** (renamed from Integrity): blockers are allowed, but unclassified or undispositioned blockers are not
- **Executive artifacts must not contain** `story_points`, `estimate`, `FR`, `NFR` fields - those are Administrative responsibilities
- **All artifacts include `schema_version`** for backward-compatible evolution

---

## Solution Design

### Phase Model Update

```
E0 — Cycle Open
    ↓
E1 — Assignment (Plan Owner + affected portfolios)
    ↓
E2 — Portfolio Drafting (LLM deliberation is PRIMARY path)
    ↓
E2.5 — Blocker Workup (deliberative disposition + peer review)
    ↓
E3 — Integration (Plan Owner assembles final plan with epics)
```

### Executive Output Contract

**Presidents output:**
- `epics[]` (acceptance intent with success signals)
- `discovery_tasks[]` (only for `DEFER_DOWNSTREAM` blockers)
- `work_packages[]` (thin units describing scope, no points/FR/NFR)

**Presidents do NOT output:**
- Story points or estimates
- Detailed functional requirements (FRs)
- Detailed non-functional requirements (NFRs)

**Dukes translate** epics into tasks + points + FR/NFR during Administrative decomposition.

---

### Blocker Model

#### Classes

| Class | Description | Required Disposition |
|-------|-------------|---------------------|
| `INTENT_AMBIGUITY` | Motion's WHAT is unclear/contradictory | Must be `ESCALATE_NOW` |
| `EXECUTION_UNCERTAINTY` | Feasibility unknown; needs discovery | `MITIGATE_IN_EXECUTIVE` or `DEFER_DOWNSTREAM` |
| `CAPACITY_CONFLICT` | Scarcity, contention, sequencing issues | `MITIGATE_IN_EXECUTIVE` or `DEFER_DOWNSTREAM` |

#### Dispositions

| Disposition | Description | Required Fields | Emits |
|-------------|-------------|-----------------|-------|
| `ESCALATE_NOW` | Band 1 escalation to Conclave queue | `escalation_conditions[]` | `conclave_queue_item.json` |
| `MITIGATE_IN_EXECUTIVE` | Presidents resolve in E2.5 | `mitigation_notes` | - |
| `DEFER_DOWNSTREAM` | Convert to discovery tasks | `verification_tasks[]`, `escalation_conditions[]` | `discovery_task_stub.json` |

#### Blocker Schema (v2)

```json
{
  "schema_version": "2.0",
  "id": "blocker_001",
  "blocker_class": "EXECUTION_UNCERTAINTY",
  "severity": "MEDIUM",
  "description": "Cryptographic proof mechanism selection requires security audit",
  "owner_portfolio_id": "portfolio_technical_solutions",
  "disposition": "DEFER_DOWNSTREAM",
  "ttl": "P7D",
  "escalation_conditions": [
    "Security audit not completed within TTL",
    "Audit reveals fundamental incompatibility"
  ],
  "verification_tasks": [
    {
      "task_id": "discovery_crypto_audit",
      "description": "Conduct security audit of candidate proof mechanisms",
      "success_signal": "Audit report with recommendation"
    }
  ],
  "mitigation_notes": null
}
```

---

### Downstream Artifacts

#### Discovery Task Stub (for `DEFER_DOWNSTREAM`)

Emitted into `execution_plan_handoff.json` for each deferred blocker:

```json
{
  "schema_version": "2.0",
  "task_id": "discovery_crypto_audit",
  "origin_blocker_id": "blocker_001",
  "question": "Which cryptographic proof mechanism should be adopted?",
  "deliverable": "Security audit report with recommendation",
  "max_effort": "P3D",
  "stop_conditions": [
    "Audit complete with clear recommendation",
    "No viable mechanism found (triggers escalation)"
  ],
  "ttl": "P7D",
  "escalation_conditions": [
    "TTL exceeded without deliverable",
    "Stop condition triggers escalation path"
  ],
  "suggested_tools": ["security_scanner", "compliance_checker"]
}
```

#### Conclave Queue Item (for `ESCALATE_NOW`)

Emitted when `INTENT_AMBIGUITY` blocker requires Conclave deliberation:

```json
{
  "schema_version": "2.0",
  "queue_item_id": "cqi_001",
  "cycle_id": "exec_abc123",
  "motion_id": "motion_xyz",
  "blocker_id": "blocker_002",
  "blocker_class": "INTENT_AMBIGUITY",
  "questions": [
    "Does 'all governance processes' include informal discussions?",
    "What is the acceptable latency for tamper detection?"
  ],
  "options": [
    "Narrow scope to formal votes only",
    "Broad scope including all deliberations",
    "Defer scope definition to Administration"
  ],
  "source_citations": [
    "Motion Section 2.1: 'all governance processes'",
    "Motion Section 3.4: 'tamper detection' (no latency specified)"
  ],
  "created_at": "2026-01-27T16:00:00Z"
}
```

---

### Epic Model

Executive outputs **Epics with acceptance intent**, not detailed tasks with story points.

#### Epic Schema

```json
{
  "schema_version": "2.0",
  "epic_id": "epic_security_framework_001",
  "intent": "Establish cryptographic verification layer for all governance processes",
  "success_signals": [
    "All vote records are cryptographically signed",
    "Tamper detection alerts within 60 seconds",
    "Audit trail passes third-party verification"
  ],
  "constraints": ["security", "auditability", "transparency"],
  "assumptions": [
    "Existing infrastructure supports cryptographic operations",
    "Key management system available"
  ],
  "discovery_required": [
    "blocker_001"
  ],
  "mapped_motion_clauses": [
    "Section 2.1: Cryptographic proof mechanisms",
    "Section 3.4: Tamper-evident audit trail"
  ]
}
```

#### Epic Validation Rules

Every epic must include:
- At least one `mapped_motion_clause` (traceability)
- At least one `success_signal` (verifiability)

Epics without these fail the Legibility gate.

---

### Work Package Model (replaces v1 tasks)

Presidents may emit thin work packages that describe scope without detail:

```json
{
  "schema_version": "2.0",
  "package_id": "wp_crypto_layer_001",
  "epic_id": "epic_security_framework_001",
  "scope_description": "Implement cryptographic signing for vote records",
  "portfolio_id": "portfolio_technical_solutions",
  "dependencies": [],
  "constraints_respected": ["security", "auditability"]
}
```

**Forbidden fields:** `story_points`, `estimate`, `hours`, `FR`, `NFR`, `detailed_requirements`

---

### Peer Review Summary (E2.5)

Plan Owner emits after blocker workup:

```json
{
  "schema_version": "2.0",
  "cycle_id": "exec_abc123",
  "motion_id": "motion_xyz",
  "plan_owner_portfolio_id": "portfolio_technical_solutions",
  "duplicates_detected": [],
  "conflicts_detected": [],
  "coverage_gaps": ["No portfolio claimed compliance monitoring"],
  "blocker_disposition_rationale": {
    "blocker_001": "Deferred: security audit is discovery work, not a planning halt",
    "blocker_002": "Escalated: intent ambiguity requires Conclave clarification"
  },
  "created_at": "2026-01-27T16:30:00Z"
}
```

---

### Gate Changes

#### Completeness (unchanged)
PASS if all affected portfolios have `PortfolioContribution` OR `NoActionAttestation`

#### Visibility (unchanged)
PASS if every response includes `capacity_claim`

#### Legibility (renamed from Integrity)

PASS only if:

1. **Schema version present:** All artifacts include `schema_version`
2. **Blocker completeness:** Every blocker has required fields: `id`, `blocker_class`, `severity`, `description`, `owner_portfolio_id`, `disposition`, `ttl`, `escalation_conditions[]`
3. **Intent ambiguity rule:** If `blocker_class == INTENT_AMBIGUITY` → `disposition == ESCALATE_NOW` AND `conclave_queue_item.json` exists
4. **Defer downstream rule:** If `disposition == DEFER_DOWNSTREAM` → `verification_tasks[]` non-empty AND `discovery_task_stub.json` emitted
5. **Mitigation rule:** If `disposition == MITIGATE_IN_EXECUTIVE` → `mitigation_notes` non-empty
6. **Epic traceability:** Every epic has at least one `mapped_motion_clause` and one `success_signal`
7. **No forbidden fields:** Artifacts do not contain `story_points`, `estimate`, `FR`, `NFR`

**Validation is schema-versioned:** v1 cycles use legacy blocker rules; v2 cycles use disposition rules.

---

## Current State (v1 Implementation)

### Files

| File | Purpose |
|------|---------|
| `src/domain/models/executive_planning.py` | Domain models (Blocker, PortfolioContribution, etc.) |
| `src/application/ports/president_deliberation.py` | Deliberation protocol interface |
| `src/application/services/executive_planning_service.py` | E0/E1/E2/E3 orchestration |
| `src/infrastructure/adapters/external/president_crewai_adapter.py` | CrewAI LLM adapter |
| `scripts/run_executive_pipeline.py` | CLI entry point |
| `tests/unit/application/services/test_executive_gates.py` | Gate tests (6 tests) |
| `tests/unit/application/ports/test_president_deliberation.py` | Deliberation port tests (4 tests) |

### Current Blocker Model (v1 - to be replaced)

```python
@dataclass
class Blocker:
    severity: str  # LOW|MEDIUM|HIGH|CRITICAL
    description: str
    requires_escalation: bool = False  # REMOVE: causes conceptual backsliding
```

### Current PortfolioContribution (v1 - to be evolved)

```python
@dataclass
class PortfolioContribution:
    cycle_id: str
    motion_id: str
    portfolio: PortfolioIdentity
    tasks: list[dict[str, Any]]  # RENAME to work_packages, forbid story_points
    capacity_claim: CapacityClaim
    blockers: list[Blocker] = field(default_factory=list)
```

---

## Implementation Plan

### Patch Order (optimized to reduce churn)

1. **Patch 1: Schema versioning + Blocker model expansion**
2. **Patch 2: Legibility gate changes** (version-aware)
3. **Patch 3: E2.5 Blocker workup** (now that blockers have shape)
4. **Patch 4: Epic model + work packages** (story-point separation is clear)
5. **Patch 5: Deliberation context enhancement**
6. **Patch 6: CLI + events**
7. **Patch 7: Tests**

---

### Patch 1: Schema Versioning + Blocker Model Expansion

**Goal:** Add versioning infrastructure and extend Blocker with classification, disposition, and required fields

**Changes:**
- Add `SCHEMA_VERSION = "2.0"` constant
- Add `BlockerClass` enum: `INTENT_AMBIGUITY`, `EXECUTION_UNCERTAINTY`, `CAPACITY_CONFLICT`
- Add `BlockerDisposition` enum: `ESCALATE_NOW`, `MITIGATE_IN_EXECUTIVE`, `DEFER_DOWNSTREAM`
- Add `VerificationTask` dataclass
- Add `BlockerV2` dataclass with new fields (keep `Blocker` for v1 compat)
- Add `BlockerV2.validate()` method for schema validation
- Remove `requires_escalation` field (conceptual backsliding)

**Files:**
- `src/domain/models/executive_planning.py`

---

### Patch 2: Legibility Gate Changes

**Goal:** Update integrity gate to validate blocker legibility with version awareness

**Changes:**
- Rename internal references from "integrity" to "legibility" in code comments
- Add `_validate_blocker_v2()` helper
- Add `_check_epic_traceability()` helper
- Add `_check_forbidden_fields()` helper
- Version-aware validation: v1 uses legacy rules, v2 uses new rules
- Add escalation artifact generation (`conclave_queue_item.json`)
- Add discovery task stub generation (`discovery_task_stub.json`)

**Files:**
- `src/application/services/executive_planning_service.py`

---

### Patch 3: E2.5 Blocker Workup

**Goal:** Add deliberative blocker disposition phase with peer review

**Changes:**
- Add `BlockerWorkupProtocol` port interface
- Add `PeerReviewSummary` dataclass
- Add `run_blocker_workup()` method to `ExecutivePlanningService`
- Add blocker workup adapter (LLM-powered cross-review)
- Add `blocker_packet.json` inbox artifact
- Add `peer_review_summary.json` artifact

**Files:**
- `src/application/ports/blocker_workup.py` (new)
- `src/domain/models/executive_planning.py`
- `src/application/services/executive_planning_service.py`
- `src/infrastructure/adapters/external/blocker_workup_adapter.py` (new)

---

### Patch 4: Epic Model + Work Packages

**Goal:** Add Epic structure and replace tasks with work packages

**Changes:**
- Add `Epic` dataclass with acceptance intent fields
- Add `WorkPackage` dataclass (thin, no points)
- Add `DiscoveryTaskStub` dataclass
- Add `ConclaveQueueItem` dataclass
- Rename `PortfolioContribution.tasks` → `work_packages`
- Add validation: reject artifacts with forbidden fields
- Update `ExecutiveCycleResult` to include `epics[]`

**Files:**
- `src/domain/models/executive_planning.py`

---

### Patch 5: Deliberation Context Enhancement

**Goal:** Enrich context for better LLM deliberation

**Changes:**
- Add `ratified_motion`, `review_artifacts`, `assignment_record` to `DeliberationContext`
- Add `generated_by` field to track LLM vs manual origin
- Add `trace_metadata` (timestamp, model, duration)
- Update adapter to emit trace metadata

**Files:**
- `src/application/ports/president_deliberation.py`
- `src/infrastructure/adapters/external/president_crewai_adapter.py`

---

### Patch 6: CLI + Events

**Goal:** Make LLM primary, add new flags and events

**Changes:**
- Add `--mode {manual,llm,auto}` with default `auto` (LLM when no manual artifacts exist)
- Add `--llm-blocker-workup` flag
- Deprecate `--scaffold-inbox` (keep for debugging)
- Add environment variables: `PRESIDENT_DELIBERATOR_MODEL`, `PRESIDENT_DELIBERATOR_TEMPERATURE`
- Add new events:
  - `executive.blocker.workup.started`
  - `executive.blocker.workup.completed`
  - `executive.blocker.escalated`
  - `executive.blocker.deferred_downstream`
  - `executive.blocker.mitigated_in_executive`
  - `executive.peer_review.completed`

**Files:**
- `scripts/run_executive_pipeline.py`
- `src/application/services/executive_planning_service.py`

---

### Patch 7: Tests

**Goal:** Add tests per spec requirements

**New Tests:**
1. Legibility fails if blocker missing required fields
2. Intent ambiguity must have `ESCALATE_NOW` disposition
3. `DEFER_DOWNSTREAM` requires `verification_tasks` and emits discovery stub
4. `MITIGATE_IN_EXECUTIVE` requires `mitigation_notes`
5. `ESCALATE_NOW` emits `conclave_queue_item.json`
6. LLM path produces artifacts with `generated_by` + trace
7. LLM deliberation does not bypass gates
8. Epic requires `mapped_motion_clause` and `success_signal`
9. Artifacts with `story_points` fail Legibility gate
10. Plans may PASS with deferred blockers (no Conclave escalation unless intent ambiguity)

**Files:**
- `tests/unit/domain/models/test_blocker_model.py` (new)
- `tests/unit/domain/models/test_epic_model.py` (new)
- `tests/unit/application/services/test_executive_gates.py` (expand)
- `tests/unit/application/services/test_blocker_workup.py` (new)

---

## Migration Strategy

1. **Schema versioning:** All artifacts include `schema_version`. v2 enforcement applies only to v2 cycles.
2. **Backward compatibility:** v1 inbox loading behavior unchanged for `schema_version: "1.x"`
3. **Additive changes:** LLM deliberation and blocker workup are additive paths
4. **Gate evolution:** Legibility gate validation is version-aware

### CLI Behavior Matrix

| Mode | Behavior |
|------|----------|
| `--mode auto` (default) | LLM deliberation when no manual inbox artifacts exist |
| `--mode llm` | Always use LLM deliberation |
| `--mode manual` | Only load from inbox (v1 behavior) |
| `--scaffold-inbox` | Create v1 templates (deprecated, for debugging) |

| Additional Flags | Effect |
|------------------|--------|
| `--llm-blocker-workup` | Run E2.5 via LLM |
| `--require-gates` | Exit 1 if gates fail |

---

## Open Questions

### Resolved (with defaults)

1. **Where do epics get authored?**
   - Plan Owner composes epics in E3 using portfolio contributions + motion clauses

2. **Where do dispositioned blockers live?**
   - Merged into final plan under `blockers[]`, referenced from affected epics via `discovery_required[]`

3. **What counts as escalation artifact?**
   - `conclave_queue_item.json` with questions, options, and source citations

### Deferred

1. **Cross-portfolio blocker ownership transfer** - Handle in future iteration
2. **Blocker TTL monitoring and automatic escalation** - Administration concern
3. **Conclave queue processing** - Separate workflow

---

## Acceptance Criteria

Running `--mode llm --llm-blocker-workup --require-gates` produces:

- [ ] `execution_plan.json` with:
  - [ ] `schema_version: "2.0"`
  - [ ] `plan_owner` identity
  - [ ] Explicit responses from all affected portfolios
  - [ ] `epics[]` with acceptance intent (no story points)
  - [ ] `work_packages[]` (no FR/NFR)
  - [ ] `blockers[]` with full disposition
  - [ ] Provenance + trace metadata

- [ ] Gates PASS when:
  - [ ] All portfolios responded
  - [ ] All capacity claims present
  - [ ] All blockers have valid class/disposition/required fields
  - [ ] All epics have traceability + success signals
  - [ ] No forbidden fields present

- [ ] Deferred blocker scenario:
  - [ ] Plans may PASS with `DEFER_DOWNSTREAM` blockers
  - [ ] `discovery_task_stub.json` emitted for each deferred blocker
  - [ ] No Conclave escalation required unless intent ambiguity exists

- [ ] Ambiguous motion produces:
  - [ ] `INTENT_AMBIGUITY` blocker with `ESCALATE_NOW` disposition
  - [ ] `executive.blocker.escalated` event
  - [ ] `conclave_queue_item.json` artifact
  - [ ] Legibility PASS only if escalation artifact exists

---

## References

- Current implementation: `src/application/services/executive_planning_service.py`
- Deliberation adapter: `src/infrastructure/adapters/external/president_crewai_adapter.py`
- Domain models: `src/domain/models/executive_planning.py`
- Existing tests: `tests/unit/application/services/test_executive_gates.py`
