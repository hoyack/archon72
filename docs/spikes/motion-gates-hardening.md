# Motion Gates Hardening Specification

## Scope

This specification defines the minimum additional behaviors required to harden the Motion Gates system and fully close the remaining combinatorial-explosion and semantic-drift failure modes.

**In scope**:

* King promotion budget (throttle)
* Boundary tripwire tests (flow invariants)
* Seed immutability enforcement
* Cross-realm escalation enforcement
* Backward-compatibility shim constraints

**Out of scope**:

* UI / UX
* Voting, ceremonies, overrides
* Full pipeline rewiring beyond what is explicitly stated here

---

## H1 — King Promotion Budget (Mandatory Throttle)

### Requirement

The system MUST enforce a **per-cycle promotion budget** for each King.

* A default promotion budget MUST exist and be configurable.
* The budget MUST be enforced at **promotion time** (Seed → Motion candidate creation).
* Promotion attempts beyond the budget MUST be denied and recorded with explicit reason codes.

### Behavior

For a given `(cycle_id, king_id)`:

* `promotions_used` increments only on successful promotion.
* If `promotions_used >= budget`, further promotions are denied.

### Reason Codes

* `PROMOTION_BUDGET_EXCEEDED`
* `PROMOTION_BUDGET_UNCONFIGURED`

### Acceptance Criteria

1. Given `budget = N`, when a King attempts `N + 1` promotions in the same cycle, the final attempt fails with `PROMOTION_BUDGET_EXCEEDED`.
2. Promotions in different cycles do not affect each other.
3. A single promotion call referencing multiple Seeds still consumes exactly one budget unit.

---

## H2 — Boundary Tripwire Tests (Flow Invariants)

### Requirement

The repository MUST include tests that enforce **flow-level boundary invariants**, not just isolated unit behavior.

### Required Tests (Minimum)

**TEST A — Legacy Secretary Output → Seed ONLY**

* Calling `add_seed_from_queued_motion()` MUST:

  * create a MotionSeed
  * MUST NOT create, enqueue, or return a Motion

**TEST B — Seed Cannot Enter Agenda Queue**

* Any attempt to schedule a MotionSeed as an agenda-eligible Motion MUST fail with an explicit boundary-breach outcome.

**TEST C — Motion Requires Admission to Be Agenda-Eligible**

* A Motion without `AdmissionRecord.status == ADMITTED` MUST NOT be eligible for agenda placement.

**TEST D — Seed Immutability After Promotion**

* Once a Seed reaches `PROMOTED` status, attempts to modify `seed_text` MUST fail.

### Acceptance Criteria

* All four tests exist and pass.
* Each test asserts both the state outcome and the specific failure reason.

---

## H3 — Seed Immutability Enforcement

### Requirement

Motion Seeds MUST preserve original meaning-bearing content.

### Allowed Mutations

* Lifecycle status transitions (`RECORDED`, `CLUSTERED`, `PROMOTED`, `ARCHIVED`)
* Non-meaning metadata (tags, clustering, bookkeeping)

### Forbidden Mutations

* `seed_text`
* `submitted_by`
* `submitted_at`
* Provenance references

### Acceptance Criteria

1. Attempting to modify `seed_text` after promotion MUST raise or return a structured failure.
2. The failure MUST be covered by TEST D in H2.
3. Status transitions remain possible without altering original content.

---

## H4 — Cross-Realm Escalation Enforcement

### Requirement

Cross-realm Motions MUST NOT silently expand into mega-motions.

### Behavior

* A Motion MUST have exactly one `primary_realm`.
* Cross-realm participation requires explicit co-sponsors.
* Realm span exceeding the escalation threshold MUST require explicit escalation approval.

### Default Threshold Policy

* **1–3 realms**: allowed with required co-sponsors
* **4+ realms**: requires explicit escalation approval, otherwise rejected

### Reason Codes

* `EXCESSIVE_REALM_SPAN`
* `MISSING_REQUIRED_COSPONSOR`
* `MULTI_PRIMARY_REALM`

### Acceptance Criteria

1. A 4+ realm Motion without escalation approval is rejected with `EXCESSIVE_REALM_SPAN`.
2. A 2–3 realm Motion without required co-sponsor is rejected with `MISSING_REQUIRED_COSPONSOR`.
3. A single-realm Motion bypasses escalation logic.

---

## H5 — Backward Compatibility Shim Constraint

### Requirement

Backward compatibility MUST NOT provide a bypass path to Motion creation.

### Behavior

Compatibility helpers (e.g., `add_seed_from_queued_motion()`) MUST:

* create MotionSeeds only
* NEVER create Motion records
* NEVER attach AdmissionRecords
* NEVER enqueue agenda-eligible Motions

### Acceptance Criteria

* TEST A in H2 validates this behavior.
* Static inspection confirms no shim → Promotion or Admission Gate calls.

---

## H6 — Integration Invariant (Non-Negotiable)

### Requirement

The system MUST preserve the following invariant:

> **Nothing enters the agenda-eligible Motion Queue unless it is:**
>
> 1. promoted by a King,
> 2. admitted by the Admission Gate, and
> 3. within the King’s promotion budget.

### Acceptance Criteria

* Enforced by H1, H2 (TEST B & C), and H5.
* Any violation MUST produce an explicit failure outcome; silent paths are forbidden.

---

## Deliverables

* Code implementing H1, H3, H4, and H5 behaviors
* Tests implementing all H2 tripwires
* Brief documentation note stating:

  * “Motion Seeds are unbounded; Motions are scarce”
  * “King promotion budgets exist”
  * “Cross-realm escalation thresholds apply”

---

## Design Principle

> **Speech is unlimited. Agenda is scarce.**
> This hardening governs agenda eligibility without suppressing speech or rewriting history.
