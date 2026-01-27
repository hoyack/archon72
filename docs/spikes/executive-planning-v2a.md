Got it. I **can’t actually open** `@scripts/run_execution_planner.py`, `@scripts/run_review_pipeline.py`, `@scripts/run_conclave.py`, or `@docs/spikes/executive-planning-v2.md` from this environment (they’re not present in the mounted files I can see), so I’m going to write the spec **at the interface boundaries** you described: *what artifacts come out of Review*, what Execution Planner must do, what loops exist, and what new “mini-review” stages you need so Conclave only ingests what truly requires Kings.

Below is a **spec for the changes** you’re aiming at.

---

# Spec: Execution Planner v2 Flow

## Deliberative Presidents → Epic Handoff → Admin Proposals → Executive Review → (Rare) Conclave Escalation

## Objective

Take the condensed/ratified output from `run_review_pipeline.py`, and:

1. **Assign each motion (or motion slices) to a President portfolio** (single plan owner).
2. Produce **Executive Epics + acceptance intent** (HOW strategy, not WHAT).
3. Convert uncertainties into **discovery stubs** (bottom-up resource discovery), not automatic Conclave escalation.
4. Support **two distinct feedback loops**:

   * **Implementation loop:** Executive → Administrative → Executive (expected, frequent)
   * **Intent loop:** Executive → Conclave (rare, only for intent ambiguity)

---

## Architectural Principle

### “Conclave is for intent. Administration is for reality.”

* If the issue is **WHAT** ambiguity → Kings must clarify → Conclave.
* If the issue is **HOW feasibility/capacity/tools** → Dukes/Earls/Tools discover → return proposal.

This prevents Conclave being used as a discovery mechanism.

---

## Inputs and Outputs

## Inputs (from Review Pipeline)

The Execution Planner must consume a **Ratified Intent Packet** (bundle view; no new data needed):

* `ratified_motion` (canonical intent, constraints, success signals)
* `ratification_record` (pass/fail, amendments applied, vote details)
* `review_artifacts` (dissent, concerns, “advisory acknowledged” footprints)
* `provenance` (sha256 + file lineage)

**Source:** whatever artifacts `run_review_pipeline.py` produces today (ratification_results, mega motions, aggregations, audit trail).

---

## Outputs (from Execution Planner)

### Primary output (to Administration)

1. `execution_plan_v2.json`

* `motion_id`, `cycle_id`
* `plan_owner` (President + portfolio)
* `affected_portfolios` (response completeness)
* `epics[]` (acceptance intent + constraints + mapped motion clauses)
* `blockers[]` (dispositioned; see below)
* `discovery_task_stubs[]` (only from DEFER_DOWNSTREAM blockers)
* provenance & trace

2. `execution_plan_handoff.json`

* minimal wrapper for Administration intake:

  * epic list + discovery stubs
  * hard constraints spotlight
  * stop conditions / escalation conditions

### Secondary output (to Conclave queue — rare)

3. `intent_clarification_queue_item.json` (ONLY for INTENT_AMBIGUITY)

* the exact ambiguity question(s)
* where in motion text the ambiguity exists
* 1–3 proposed interpretations (not decisions)
* why Executive cannot proceed without clarification

This is what you feed into Conclave ingestion, *not the whole motion again*.

---

## Blocker Disposition v2

### Blocker classes

* `INTENT_AMBIGUITY` → must produce `intent_clarification_queue_item.json`
* `EXECUTION_UNCERTAINTY` → mitigate or defer
* `CAPACITY_CONFLICT` → mitigate or defer

### Dispositions

* `ESCALATE_NOW` (only valid for intent ambiguity)
* `MITIGATE_IN_EXECUTIVE` (Presidents deliberate and attempt a resolution)
* `DEFER_DOWNSTREAM` (convert into discovery task stubs)

### Key change

**Integrity gate becomes “blockers are legible,” not “blockers are gone.”**

So planning doesn’t halt—uncertainty becomes controlled downstream work.

---

# The Missing Piece You Identified

## “Mini-review before Conclave ingestion”

You’re correct: not every question deserves Conclave. You need an **Executive Clarification Review** stage *before* anything becomes a Conclave agenda item.

### New stage: Executive Clarification Review (ECR)

This is review-pipeline-like, but scoped to Presidents:

**Input:** `intent_clarification_candidate.json`
**Output:** one of:

* `escalate_to_conclave.json` (confirmed intent ambiguity)
* `reclassify_as_execution_uncertainty.json` (defer downstream)
* `resolved_in_executive.json` (mitigation succeeded)

This prevents Conclave ingestion from being spammed by premature “blocker” labeling.

---

# End-to-End Flow

### Path A: Normal (most work)

`Review Pipeline (ratified)`
→ `Execution Planner (Presidents)` produce epics + deferred discovery
→ `Administrative Pipeline (Dukes)` produce implementation proposals + resource requests (bottom-up)
→ `Executive Review (E4)` accept / revise / re-defer / (rarely) escalate

### Path B: Intent ambiguity (rare)

`Execution Planner` identifies INTENT_AMBIGUITY
→ `Executive Clarification Review (Presidents)` confirms it’s truly intent
→ `Conclave Ingestion` creates a motion/agenda item specifically for clarification

---

# Administrative Pipeline (needed for your described loop)

You don’t need “resource allocation” at Executive yet; you need **resource request emergence**.

## Admin input

* `execution_plan_handoff.json` (epics + discovery stubs)

## Admin outputs

1. `implementation_proposal.json` (per epic)

* `epic_id`
* proposed approach (tactics)
* technical spec references (as artifacts, not prose blobs)
* risks
* **resource_requests[]** (bottom-up)
* capacity commitment (reality based)

2. `resource_request.json` (optional separate artifact)

* what resource
* why
* required by when
* alternatives if denied

These go back upstream to Executive Review (E4).

---

# Executive Review Phase (E4)

This is the missing “upward reverberation receiver.”

**Input:** execution plan + implementation proposals
**Output:**

* `plan_acceptance.json` (approved to proceed to Earl tasking)
* `revision_request.json` (sent back to Admin with constraints or questions)
* `conclave_escalation.json` (only if intent must change, or governance-level tradeoff)

This keeps the Executive Branch “HOW owners” without becoming implementers.

---

# Changes Required in `run_execution_planner.py`

## Responsibilities

1. **Load Ratified Intent Packet**
2. **Portfolio assignment**

   * identify affected portfolios
   * choose Plan Owner
3. **Deliberative planning**

   * Presidents draft epics + acceptance intent
   * identify blockers and dispositions
4. **Emit discovery task stubs for DEFER_DOWNSTREAM**
5. **Emit intent clarification queue items ONLY for INTENT_AMBIGUITY**
6. **Write handoff artifacts** to Admin

## CLI flags (recommended)

* `--input <review_output_dir>`
* `--out <exec_output_dir>`
* `--mode {llm,manual,hybrid}` default `llm`
* `--require-gates`
* `--emit-admin-handoff`
* `--emit-conclave-clarifications` (writes queue items; does not run conclave)
* `--run-exec-clarification-review` (optional: ECR stage)

---

# Gates for Execution Planner v2

* **Completeness:** all affected portfolios produced contribution or attestation
* **Visibility:** capacity claim present (coarse is OK) *at epic-level or portfolio-level*
* **Integrity (v2):** blockers are fully classified + dispositioned

  * INTENT_AMBIGUITY must have a conclave clarification artifact
  * DEFER_DOWNSTREAM must have discovery stubs + escalation conditions

**Important:** Plans can PASS with deferred blockers.

---

# Where “with what” belongs

Your phrasing “How (and with what to some extent)” is right, but bounded:

Executive may specify:

* *tool class* (e.g., “static analysis,” “schema migration,” “cryptographic signing”)
* constraints/invariants

Executive should not specify:

* exact vendors, exact humans, exact implementation choices (Admin proposes)
* that’s where bottom-up resource truth emerges

---

# Concrete Next Step

If you want this to land cleanly in your repo, the next actionable move is:

1. Add the **two missing artifacts**:

   * `intent_clarification_queue_item.json`
   * `implementation_proposal.json`

2. Add the **two missing runners** (even stubbed):

   * `scripts/run_administrative_pipeline.py` (consumes exec handoff, outputs proposals)
   * `scripts/run_executive_review.py` (E4 acceptance/revision)

3. Update `run_execution_planner.py` to emit:

   * `execution_plan_v2.json`
   * `execution_plan_handoff.json`
   * `intent_clarification_queue_item.json` (only for intent ambiguity)

---