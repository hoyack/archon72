# Motion Seeds and Motions — Behavioral Specification

## Scope

This specification defines how the system **records**, **classifies**, **promotes**, **queues**, **reviews**, and **disposes** of:

* **Motion Seeds** (non-binding proposals)
* **Motions** (agenda-eligible legislative artifacts)

This document is intentionally limited to the Motion Seed ↔ Motion boundary. It does **not** specify voting mechanics, ceremonies, overrides, or branch behaviors except where strictly necessary to define motion lifecycle semantics.

---

## Definitions

### Motion Seed

A **Motion Seed** is a **non-binding proposal artifact** recorded for visibility, traceability, and future consideration.

A Motion Seed:

* may be submitted by eligible participants (per branch procedures)
* **does not** claim agenda time
* **does not** trigger deliberation
* **does not** require Motion Admission Gate validation
* may be clustered, consolidated, or summarized without becoming a Motion

### Motion

A **Motion** is a **scarce, agenda-eligible legislative artifact**.

A Motion exists **only** after formal introduction by a **King** within a valid realm assignment, as defined by the Legislative Branch.

A Motion:

* is subject to the **Motion Admission Gate**
* may be placed into agenda queues once admitted
* is eligible for Conclave deliberation and decision recording

### Promotion

**Promotion** is the witnessed transition from **Motion Seed → Motion**. Promotion occurs only through formal introduction by a King and creates a new Motion artifact that references Seed provenance.

Promotion does not rewrite, merge, or delete Motion Seeds.

---

## Canonical Objects

### Motion Seed Record (Minimum Required)

A Motion Seed record MUST contain:

* `seed_id`
* `submitted_by`
* `submitted_at`
* `seed_text` (unaltered original proposal)
* optional `proposed_realm` (non-binding hint)
* optional `support_signals` (non-binding endorsements)
* `status` (e.g., recorded, clustered, promoted, archived)
* `provenance` (cycle, event, or source references)

### Motion Record (Minimum Required)

A Motion record MUST contain:

* `motion_id`
* `title`
* `realm_assignment`:

  * `primary_realm`
  * `primary_sponsor` (King reference)
  * optional co-sponsors / cross-realm flags
* `normative_intent` (WHAT)
* `constraints` (WHAT-level guardrails)
* `success_criteria`
* `submitted_at` (time of introduction)
* `source_seed_refs` (Seed IDs and/or other provenance)
* `admission` (admission status and reason codes)
* `status` (lifecycle state)

---

## Invariants

### I1 — No Silent Loss

No Motion Seed or Motion may disappear from history. All non-progression MUST be recorded as an explicit state transition or disposition.

### I2 — Speech Is Unbounded; Agenda Eligibility Is Scarce

Motion Seed creation may be unbounded. Motion creation is bounded by sponsor standing, admission validation, and agenda capacity rules.

### I3 — Admission Gate Applies to Motions Only

Motion Seeds are recorded without admission-gate validation. The Motion Admission Gate evaluates **only** Motions.

### I4 — Anti-Forgery Semantics

Any artifact presented as a Motion that fails required form invariants is **not a Motion** and MUST be recorded as a malformed or invalid motion attempt with explicit reason codes.

### I5 — Promotion Does Not Rewrite Seeds

Promotion creates a new Motion artifact. Motion Seeds remain intact and queryable.

### I6 — Consolidation Is Non-Binding and Trace-Mapped

Clustering or consolidation MUST preserve original Seeds and emit explicit inclusion/exclusion mappings.

---

## System Behavior

### A) Motion Seed Intake

**A1 — Accept and Record**
When a Motion Seed is submitted, the system MUST:

1. Record the Seed append-only
2. Emit a Seed Recorded event
3. Optionally compute non-binding metadata

**A2 — No Gate Rejection at Intake**
Seed intake MUST NOT be blocked due to ambiguity, HOW content, duplication, or quality.

**A3 — Non-Destructive Deduplication**
Near-duplicate Seeds MAY be clustered but MUST still be individually recorded.

---

### B) Seed Consolidation and Clustering (Non-Binding)

**B1 — Cluster Formation**
The system MAY cluster Seeds into themes.

**B2 — Draft Artifacts**
Any thematic summaries produced are drafts, not Motions, and MUST include provenance references.

**B3 — Dissent Handling**
Dissent from consolidation MUST be recorded without forcing agenda eligibility.

---

### C) Promotion: Seed → Motion

**C1 — Preconditions**
Promotion occurs only via formal introduction by a King within a valid realm.

**C2 — Promotion Act**
On promotion, the system MUST:

1. Create a Motion record
2. Link `source_seed_refs`
3. Emit a Motion Introduced event
4. Forward the Motion to the Admission Gate

**C3 — No Implied Admission**
Promotion does not imply admission or agenda placement.

---

### D) Motion Admission Gate

**D1 — Scope**
The gate evaluates Motions only.

**D2 — Outcomes**
Each evaluation MUST produce a recorded Admission Record with status and reason codes.

**D3 — Rejection Conditions (Non-Exhaustive)**

* Missing required fields
* Invalid sponsor or realm assignment
* Absent or non-normative intent
* Ambiguous scope (e.g., “as needed”)
* HOW/implementation detail embedded in WHAT

**D4 — No Silent Rewrite**
The gate MUST NOT rewrite Motion content.

---

### E) Queue Placement

**E1 — Motions Only**
Only admitted Motions may enter agenda-eligible queues.

**E2 — Seeds Excluded from Agenda**
Motion Seeds MUST NOT be scheduled as Motions.

**E3 — Deferral Is Explicit**
Quota or capacity deferrals MUST be recorded with reason codes.

---

### F) Lifecycle and Disposition

**F1 — Explicit Lifecycle States**
Motion lifecycle states MUST be queryable.

**F2 — Archive Is Disposition**
Archival records MUST include reason and history.

---

## Failure Modes (Witnessed)

* **Seed Treated as Motion** → boundary breach event recorded
* **Ambiguous Motion Language** → rejected with reason codes
* **Duplicate Motions** → preserved, optionally clustered

---

## Observability Requirements

The system MUST support queries showing:

* All Seeds per cycle
* Seed → Motion provenance
* Admission outcomes and reasons
* Queue eligibility and deferrals
* Consolidation mappings

---

## Acceptance Criteria

1. Queue 1 contains only Motion Seeds
2. Admission Gate evaluates Motions only
3. Seeds may contain HOW without rejection
4. Motions containing HOW are rejected with reasons
5. All Motions reference provenance
6. No Seed becomes agenda-eligible without promotion

---

## Non-Goals

* Enforcing outcomes
* Preventing proposal volume
* Inferring intent
* Optimizing deliberation speed

---

## Design Principle

> **Speech is unlimited. Agenda is scarce.**
> This specification governs agenda eligibility without suppressing speech.
