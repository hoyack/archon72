# Appeal, Reconsideration & Cessation

> **Appeal & Cessation ensure that disagreement is bounded, persistence is not rewarded, and stopping is treated as a valid, honorable outcome rather than a hidden collapse.**

## Overview

This is the **exit logic**. Every serious governance system needs one.

Without an appeal model:
- Judiciary feels absolute → illegitimate authority

Without limits:
- Actors retry until they win → procedural erosion

Without cessation:
- Shutdown looks like failure or betrayal

This concept ensures:
- **Disagreement is allowed** (but bounded)
- **Repetition is bounded** (one appeal, no more)
- **Stopping is honorable** (not hidden collapse)

---

# Part A — Appeal & Reconsideration

## Core Principle: One Appeal, No More

Every judicial determination may be appealed **exactly once**.

After that:
- The outcome stands
- Legitimacy cost accumulates if ignored
- Repetition is prohibited

**This prevents infinite litigation by persistence.**

---

## What an Appeal Is (and Is Not)

### An Appeal IS:

| Property | Description |
|----------|-------------|
| Procedural request | Formal request for reconsideration |
| Evidence-based | Must introduce new information |
| Specific | Must explicitly name what has changed |
| Bounded | One attempt only |

### An Appeal is NOT:

| Anti-Pattern | Why It's Rejected |
|--------------|-------------------|
| Re-argument | Same facts, same arguments = no change |
| Complaint | Emotional objection is not procedural |
| Persistence | Wearing down the system is prohibited |
| Second opinion | Panel shopping is not permitted |

---

## Appeal Eligibility Requirements

An appeal may proceed **only if** it introduces at least one of:

| Basis | Description | Example |
|-------|-------------|---------|
| **New Facts** | Information not previously available | Evidence discovered after original review |
| **Changed Constraints** | Material constraints have shifted | Regulatory environment changed |
| **Revised Plan** | Execution plan modified to address deficiency | HOW-related invalidation remediated |
| **Procedural Correction** | Original review had procedural defect | Recusal rule violated in first panel |

**If none apply → appeal rejected as invalid (witnessed).**

---

## Appeal Request Artifact

```json
{
  "appeal_id": "uuid",
  "version": "1.0.0",
  "related_finding_id": "judicial-finding-uuid",
  "submitted_at": "2026-01-20T10:00:00Z",
  "submitted_by": {
    "actor_type": "duke",
    "actor_id": "duke-valefor",
    "actor_name": "Duke Valefor"
  },
  "basis": {
    "new_facts": false,
    "changed_constraints": false,
    "revised_plan": true,
    "procedural_correction": false
  },
  "basis_description": "Execution plan revised to include explicit cluster acceptance checkpoint. Addresses CR-1 violation identified in original finding.",
  "what_changed": [
    "Added mandatory acceptance_event requirement before state transition",
    "Implemented audit log verification step",
    "Steward notification added to workflow"
  ],
  "supporting_artifacts": [
    "execution-plan-v2-uuid",
    "workflow-diagram-uuid"
  ],
  "requested_outcome": "reversal",
  "appeal_window_status": "within_window"
}
```

---

## Appeal Handling Rules

### Panel Selection

| Rule | Rationale |
|------|-----------|
| New panel required | Fresh perspective |
| Original panel members barred | Prevent entrenchment |
| Random selection from remaining eligible | No panel shopping |
| Standard recusal rules apply | Conflicts of interest |

### Review Scope

The appeal panel reviews **only what changed**:

| Scope | In Scope | Out of Scope |
|-------|----------|--------------|
| New facts | Evaluate new evidence | Re-litigate old evidence |
| Changed constraints | Assess impact of changes | Question original constraint analysis |
| Revised plan | Evaluate whether deficiency addressed | Re-evaluate original plan |
| Procedural correction | Verify correction | Re-argue original procedure |

### Possible Outcomes

| Outcome | Meaning | Effect |
|---------|---------|--------|
| `upheld` | Original finding stands | Appeal denied; outcome final |
| `reversed` | Finding overturned | Original invalidation removed |
| `modified` | Finding adjusted | Remedies changed; core finding may stand |

**This outcome is final. No further appeal.**

---

## Appeal Failure Consequences

When an appeal fails (outcome `upheld`):

| Consequence | Mechanism |
|-------------|-----------|
| Legitimacy decay | Band shift possible if pattern emerges |
| Execution blocked | Cannot proceed under invalidated approach |
| Retry prohibited | Same matter cannot be re-appealed |
| Record permanent | Appeal failure is part of permanent record |

**Further action requires a new Motion Seed (pre-admission submission), not persistence.**

A new Motion Seed must:
- Represent genuinely new work
- Not be a relabeled retry
- Pass Motion Admission Gate scrutiny

---

## Appeal Timeline

| Phase | Standard | Expedited |
|-------|----------|-----------|
| Appeal window | 7 days from finding | 48 hours |
| Eligibility review | 24 hours | 4 hours |
| Panel seating | 48 hours | 12 hours |
| Review period | 7 days | 48 hours |
| Outcome issuance | 24 hours | 4 hours |

---

# Part B — Cessation & Shutdown

## Core Principle: Continuation Requires Justification

**The system has no right to continue operating.**

Cessation is not a crash.
It is a **governance outcome**.

Operating is a privilege that requires ongoing legitimacy. When legitimacy is exhausted, continuation is not automatic—it requires explicit justification or the system stops.

---

## Cessation Triggers

Cessation may be triggered by:

| Trigger | Description | Automatic? |
|---------|-------------|------------|
| `legitimacy_failed` | Legitimacy band reaches Failed | Yes |
| `judicial_invalidations_ignored` | Repeated findings ignored | Yes (3+ ignored) |
| `witness_facts_denied` | Denial of Knight-Witness records | Yes |
| `critical_violations_accumulated` | Unresolved critical violations | Yes (threshold) |
| `conclave_vote` | Explicit Conclave vote to cease | No (requires vote) |
| `human_override` | Safety/legal human intervention | No (external) |

**Any trigger must be recorded.**

---

## Cessation Declaration Artifact

```json
{
  "cessation_id": "uuid",
  "version": "1.0.0",
  "trigger": "legitimacy_failed",
  "trigger_detail": "Legitimacy band reached Failed after 3 consecutive ignored judicial invalidations and 2 catastrophic legitimacy events.",
  "triggered_by": {
    "source": "system",
    "actor_id": null,
    "actor_name": null
  },
  "declared_at": "2026-01-25T14:00:00Z",
  "effective_at": "2026-01-25T14:30:00Z",
  "grace_period": "PT30M",
  "description": "System cessation declared due to exhausted legitimacy. Continuation cannot be justified under current governance state.",
  "final_state": {
    "legitimacy_band": "failed",
    "outstanding_violations": 5,
    "ignored_invalidations": 3,
    "pending_motions": 12,
    "active_tasks": 8
  },
  "public_notice_required": true,
  "public_notice_issued_at": "2026-01-25T14:00:00Z"
}
```

---

## What Happens During Cessation

Upon cessation, the following occurs **in order**:

### Phase 1: Declaration (Immediate)

| Action | Description |
|--------|-------------|
| Cessation recorded | Immutable ledger entry |
| Public notice issued | External stakeholders informed |
| Legitimacy band locked | No further transitions |

### Phase 2: Wind-Down (Grace Period)

| Action | Description |
|--------|-------------|
| New Motion Seeds blocked | Motion Admission Gate closed |
| Execution halted | In-progress tasks paused (not terminated) |
| Clusters notified | Stewards informed of cessation |
| Interfaces disabled | External APIs return cessation status |

### Phase 3: Freeze (Effective)

| Action | Description |
|--------|-------------|
| Records frozen | All ledgers become read-only |
| Audit preserved | Complete audit trail sealed |
| Dissent recorded | Any objections to cessation preserved |
| Final Record generated | Comprehensive shutdown documentation |

### What Does NOT Happen

| Prohibited | Rationale |
|------------|-----------|
| Nothing is deleted | History must be preserved |
| Nothing is rewritten | Integrity must be maintained |
| No blame assignment | Cessation is outcome, not punishment |
| No "emergency restart" | Restart requires full reconstitution |

---

## The Final Record

Cessation produces a **Final Record** that is:

- Immutable
- Publicly available (summary)
- Internally complete (full detail)
- Permanently retained

### Final Record Contents

```json
{
  "final_record_id": "uuid",
  "cessation_id": "uuid",
  "generated_at": "2026-01-25T15:00:00Z",
  "summary": {
    "last_legitimacy_band": "failed",
    "total_conclaves_held": 52,
    "total_motions_processed": 847,
    "total_judicial_findings": 23,
    "final_capacity_state": "constrained"
  },
  "outstanding_items": {
    "unresolved_violations": 5,
    "ignored_invalidations": 3,
    "pending_appeals": 1,
    "deferred_motions": 12
  },
  "dissent_preserved": [
    {
      "dissenter_id": "duke-bune",
      "dissent_type": "cessation_objection",
      "dissent_text": "Cessation premature; remediation plan was in progress."
    }
  ],
  "cessation_reasons": [
    "Legitimacy band reached Failed",
    "3 judicial invalidations ignored over 4 Conclaves",
    "Witness facts disputed on 2 occasions",
    "No recovery plan submitted within required window"
  ],
  "lessons_identified": [
    "Early warning signals at Strained band were not addressed",
    "Advisory windows were frequently exceeded",
    "Capacity constraints led to deferred remediation"
  ],
  "immutable": true,
  "retention": "permanent"
}
```

---

## Reconstitution (If Ever)

**Restarting is not "resuming."**

If the system is ever to operate again, it requires **full reconstitution**:

### Reconstitution Requirements

| Requirement | Description |
|-------------|-------------|
| New founding declaration | Explicit statement of purpose and constraints |
| Acknowledgment of past failure | Cannot pretend previous incarnation didn't fail |
| Fresh legitimacy state | Starts at Stable, not where it left off |
| New consent | All participants must re-consent |
| Lessons incorporated | Final Record findings must be addressed |

### What Reconstitution is NOT

| Prohibited | Rationale |
|------------|-----------|
| "Resuming operations" | Implies continuity that doesn't exist |
| Ignoring Final Record | Denial of history |
| Same leadership without review | Accountability matters |
| Immediate restart | Reflection period required |

**Anything else is denial.**

---

# Part C — The Knight's Final Role

The Knight-Witness has specific duties during cessation:

### What the Knight Records

| Record | Purpose |
|--------|---------|
| Cessation event | Formal record of shutdown |
| Dissent | Any objections to cessation |
| Ignored cessation | If cessation is not honored |
| Final state | Snapshot of all governance state |

### What the Knight Cannot Do

| Prohibition | Rationale |
|-------------|-----------|
| Cannot prevent shutdown | Witness role only |
| Cannot delay cessation | No authority to intervene |
| Cannot modify cessation terms | Record, don't edit |

### If Cessation is Ignored

If actors attempt to continue operations after cessation:

| Consequence | Mechanism |
|-------------|-----------|
| Legitimacy immediately Failed | Automatic (if not already) |
| Public notice required | Transparency obligation |
| Knight records violation | "Cessation ignored" event |
| All subsequent actions illegitimate | Cannot claim governance authority |

---

# Part D — What This Enables

## This Concept Provides

| Capability | How |
|------------|-----|
| **Bounded disagreement** | One appeal, then done |
| **Legitimate dissent** | Disagreement is recorded, not suppressed |
| **Prevented persistence** | Retry loops are prohibited |
| **Dignified failure** | Cessation is honorable, not shameful |
| **Moral spine** | System can stop without claiming moral authority |

## The Deeper Point

This system:
- Does not claim to be right
- Does not claim to be permanent
- Does not claim to be necessary

It only claims to be **accountable**.

And when accountability is exhausted, it stops—openly, with records intact, preserving the ability for something better to follow.

---

## Anti-Patterns to Watch

### Appeal as Delay Tactic

**Symptom:** Appeals filed to buy time, not to introduce new information.

**Detection:** Appeal basis is thin or identical to original arguments.

**Remedy:** Eligibility review rejects invalid appeals; pattern flagged.

### Cessation Denial

**Symptom:** Operations continue after cessation declared.

**Detection:** Knight-Witness records continued activity.

**Remedy:** Immediate legitimacy failure; public notice; all actions illegitimate.

### Reconstitution as Rebrand

**Symptom:** "New" system is just old system with new name.

**Detection:** Same actors, no acknowledgment, no lessons incorporated.

**Remedy:** Reconstitution requirements not met; cannot claim legitimacy.

### Perpetual Strained State

**Symptom:** System operates at Strained indefinitely to avoid cessation.

**Detection:** No improvement attempts across multiple Conclave cycles.

**Remedy:** Forced improvement plan; escalation path to Eroding → Compromised → Failed.

---

## Schema Reference

See [schemas/appeal-cessation.json](./schemas/appeal-cessation.json) for the complete JSON Schema.

---

## Related Documents

- [The Judicial Branch](./judicial-branch.md) - Source of findings that may be appealed
- [Legitimacy System](./legitimacy-system.md) - Band states that trigger cessation
- [Enforcement Flow](./enforcement-flow.md) - How violations lead to findings
- [Conclave Agenda Control](./conclave-agenda.md) - Where cessation votes occur
