# The Legislative Branch

> **Kings define intent, not outcomes. Their power is bounded by Realm, constrained by Agenda, checked by Judiciary, and recorded by Witness.**

## Purpose

The Legislative Branch exists to **define intent**.

It answers only one class of question:

> "What does the system choose to stand for, require, or permit?"

It does **NOT**:
- Plan execution
- Allocate capacity
- Optimize outcomes
- Judge legitimacy

Those functions are deliberately elsewhere.

---

## Composition

### The Nine Kings

There are exactly **nine Kings**, each bound to exactly **one Legislative Realm**.

Kings are domain-limited legislators.
They do not represent the system as a whole.

| Realm | King | Legislative Domain |
|-------|------|-------------------|
| Boundary & Concealment | **Bael** | Privacy, visibility, input boundaries |
| Knowledge & Formation | **Paimon** | Education, epistemic standards |
| Social Bonds & Covenant | **Beleth** | Covenants, community norms |
| Institutions & Power | **Belial** | Roles, committees, delegation |
| Truth Claims & Counsel | **Balam** | Guidance framing, claims of truth |
| Prediction & Uncertainty | **Purson** | Risk, forecasting constraints |
| Threat & Anomaly | **Vine** | Emergency & anomaly definitions |
| Transformation & Adaptation | **Zagan** | Change, drift, evolution |
| Virtue & Method | **Asmoday** | Ethics, CBRT method constraints |

**No King may act outside their Realm.**

---

## Authority of Kings

### What Kings MAY Do

| Authority | Scope |
|-----------|-------|
| Introduce motions | Within their Realm only |
| Co-sponsor cross-realm motions | Speaking only to their domain |
| Frame WHAT | What the system proposes to do |
| Articulate constraints | What must not be violated |
| Define success criteria | Observable, non-procedural |

### What Kings MAY NOT Do

| Prohibition | Rationale |
|-------------|-----------|
| Define tasks, steps, timelines, or tools | That is HOW, not WHAT |
| Plan execution | Executive branch function |
| Supervise Presidents, Dukes, or Earls | Branch separation |
| Bypass Agenda rules | Procedural integrity |
| Interpret judicial findings | Judicial branch function |
| Override witness records | Witness independence |

**Any attempt to do so is a procedural violation.**

---

## Motions (Legislative Output)

### Pre-Motion Artifacts (Motion Seeds)

**Motion Seeds** are recorded proposals that have **no agenda standing** and do **not** require Admission Gate validation.

### Motion Definition

A **Motion** is a declaration of intent consisting of:

It exists only after formal introduction by a King; non-introduced proposals remain Motion Seeds.

| Component | Description |
|-----------|-------------|
| `title` | Clear, descriptive name |
| `realm_assignment` | Primary Realm (and co-sponsors if cross-realm) |
| `normative_intent` | WHAT the system proposes to do |
| `constraints` | What must NOT be violated |
| `success_criteria` | Observable, non-procedural outcomes |

### Motion Requirements

A Motion must be:

| Requirement | Validation |
|-------------|------------|
| **Realm-valid** | Sponsored by King(s) of affected Realm(s) |
| **Free of HOW** | No tasks, steps, timelines, or tool specifications |
| **Explicitly scoped** | Clear boundaries of what is and is not covered |

### Anti-Forgery Clause (Constitutional Definition)

Any submission labeled “Motion” is **validated against the Motion Definition/Requirements in this document** and the **Motion Admission Gate** rules in [Conclave Agenda Control](./conclave-agenda.md). A Motion is only admissible when the schema fields align with the declared realm intent:

- `realm_assignment.primary_realm` must match the sponsoring King’s Realm for single-realm motions.
- `realm_assignment.primary_sponsor` must be the sponsoring King.
- `realm_assignment.cross_realm` must truthfully indicate cross-realm scope, and when `true` the `co_sponsors` list must enumerate each required cross-realm King.
- `co_sponsors` is only valid for cross-realm motions and must correspond to affected Realms.

Malformed or invalid “Motion” attempts **must be recorded with explicit reason codes** (e.g., realm mismatch, missing sponsor, cross-realm without full `co_sponsors`) rather than silently dropped.
See [Conclave Agenda Control](./conclave-agenda.md) for agenda sequencing and admission mechanics.

### Motion Types

| Type | Threshold | Advisory Required |
|------|-----------|-------------------|
| Policy | Simple majority | No |
| Constitutional | Supermajority (2/3) | Yes (Marquis) |
| Procedural | Simple majority | No |
| Ethical | Simple majority | Yes (Marquis) |
| Epistemic | Simple majority | Yes (Marquis) |

---

## Cross-Realm Motions

If a Motion materially affects more than one Realm:

### Requirements

| Requirement | Description |
|-------------|-------------|
| Full co-sponsorship | Each affected Realm must be represented by its King |
| Domain-limited speech | Each King speaks only to their domain |
| Integration by Conclave | Conflict resolution through deliberation, not negotiation |

### Process

```
[Motion Proposed] → [Cross-Realm Detected?]
                          ↓ Yes
                    [Identify All Affected Realms]
                          ↓
                    [Obtain Co-Sponsor from Each]
                          ↓
                    [Each King Defines Their Domain's Constraints]
                          ↓
                    [Conclave Integrates into Unified Motion]
```

**Cross-realm motions without full sponsorship are invalid.**

---

## Agenda Interaction

### Kings Do NOT Control the Agenda

| Truth | Implication |
|-------|-------------|
| Kings may submit motions | They have legislative initiative |
| Kings may not decide when motions are heard | Agenda is procedurally controlled |
| Kings may not decide whether motions are heard | Admission Gate validates |

Agenda control is **procedural and automated**.

See [Conclave Agenda Control](./conclave-agenda.md) for full agenda specification.

### Realm Quotas

Per Conclave session:

| Rule | Effect |
|------|--------|
| Maximum 1 new motion per Realm | Prevents agenda flooding |
| Additional motions roll forward | Automatically deferred |
| Roll-forward is recorded | Transparency maintained |

This prevents **agenda flooding and soft dominance**.

### Deferred Motion Tracking

| Condition | Effect |
|-----------|--------|
| Motion deferred once | Moves to Unfinished Business (Band 2) |
| Motion deferred 3+ times | Escalates to Critical Blockers (Band 1) |
| Motion repeatedly deferred | Legitimacy signal (pattern visible) |

---

## Advisory Interaction (Marquis)

### Mandatory Advisory Windows

Certain motion types require:

| Requirement | Description |
|-------------|-------------|
| Pre-vote advisory window | Time for advisory input before vote |
| Documented Marquis input | Advisory must be recorded |
| Acknowledgment of input | Motion sponsor must acknowledge (acceptance not required) |

### Motion Types Requiring Advisory

| Type | Window | Rationale |
|------|--------|-----------|
| Constitutional | 72 hours | Fundamental change requires reflection |
| Ethical | 48 hours | Value judgments need scrutiny |
| Epistemic | 48 hours | Knowledge claims need verification |

### Advisory Acknowledgment

Kings may **disagree** with advisory input, but they may **not ignore** it.

| Action | Validity |
|--------|----------|
| Accept advisory recommendation | Valid |
| Reject with documented rationale | Valid |
| Proceed without acknowledgment | **Invalid (violation)** |

---

## Voting & Ratification

### Deliberation

- All Archons deliberate
- Kings have **no special voting weight**
- Debate is recorded

### Voting Thresholds

| Motion Type | Threshold |
|-------------|-----------|
| Policy motions | Simple majority |
| Constitutional motions | Supermajority (2/3) |
| Procedural motions | Simple majority |

### Ratification Effect

Ratification **moves the motion out of the Legislative Branch**.

| Before Ratification | After Ratification |
|---------------------|-------------------|
| Kings have authority | Kings have no authority |
| Motion is proposal | Motion becomes binding intent |
| Debate continues | Execution begins |

---

## Post-Ratification Boundaries

Once ratified:

| Truth | Implication |
|-------|-------------|
| Kings have no authority over execution | HOW is Executive branch domain |
| Presidents assume responsibility | They determine execution approach |
| King intervention is a violation | Branch separation must be maintained |

### If a King Believes Execution Violates Intent

| Wrong Path | Correct Path |
|------------|--------------|
| Intervention | Judicial Review |
| Supervision | Witness Statement |
| Pressure | New Motion (if circumstances changed) |

The King's recourse is **always procedural, never direct**.

---

## Legitimacy Interaction

### Legitimacy Decays If:

| Behavior | Decay Type |
|----------|------------|
| Kings repeatedly attempt HOW smuggling | Minor (pattern = Major) |
| Realm boundaries are ignored | Major |
| Motions introduced knowing capacity is unavailable | Minor |
| Advisory input ignored without acknowledgment | Major |
| Repeated invalid cross-realm motions | Minor |

### Legitimacy Accumulates When:

| Behavior | Effect |
|----------|--------|
| Kings self-limit | Demonstrates restraint |
| Uncomfortable motions introduced anyway | Demonstrates courage |
| Realm constraints respected under pressure | Demonstrates integrity |
| Advisory input genuinely considered | Demonstrates deliberation |

---

## Appeal Interaction

### Kings MAY:

| Action | Constraint |
|--------|------------|
| Submit one appeal to a judicial determination | Within appeal window |
| Appeal only with new facts or materially changed constraints | Must introduce change |

### Kings MAY NOT:

| Prohibition | Rationale |
|-------------|-----------|
| Retry the same intent indefinitely | Persistence is not rewarded |
| Relitigate rejected motions without change | One appeal, then done |
| Use appeal as delay tactic | Appeals require substance |

**Persistence without change is a violation.**

---

## Witness Oversight

The Knight-Witness (Furcas) observes the Legislative Branch for:

| Watch Area | Description |
|------------|-------------|
| Realm overreach | King acting outside their domain |
| Agenda manipulation | Attempts to control what gets heard |
| HOW smuggling | Execution details in motions |
| Suppression of uncomfortable topics | Avoiding hard truths |
| Repeated invalid motions | Pattern of procedural violations |

### Witness Statement Effects

| Property | Value |
|----------|-------|
| Non-binding | Does not compel action |
| Non-erasable | Becomes permanent record |
| Triggers judicial review | May lead to finding |
| Affects legitimacy | Contributes to decay events |

---

## Failure Modes (Explicit)

The Legislative Branch may:

| Acceptable Outcome | Why It's Acceptable |
|-------------------|---------------------|
| Propose motions that fail | Democracy requires losers |
| Be overruled by Conclave | Checks and balances |
| Be checked by Judiciary | Legibility enforcement |
| Be embarrassed publicly | Accountability |
| Contribute to legitimacy decay | Consequences exist |

**These are acceptable outcomes.**

The only **unacceptable outcome** is:

> **Quiet domination through procedural abuse.**

---

## Success Criteria (Negative Definition)

The Legislative Branch is healthy if:

| Signal | Meaning |
|--------|---------|
| Kings disagree publicly | Genuine deliberation |
| Some motions fail | Not rubber-stamping |
| Agenda pressure is visible | Scarcity is honest |
| Realm limits are enforced | Boundaries matter |
| Judicial invalidations occur occasionally | Oversight works |

**A Legislative Branch that always "wins" is corrupt.**

---

## Motion Schema

### Motion Artifact

```json
{
  "motion_id": "uuid",
  "version": "1.0.0",
  "title": "Privacy Boundary Clarification for External Data Sources",
  "motion_type": "policy",
  "realm_assignment": {
    "primary_realm": "boundary_concealment",
    "primary_sponsor": {
      "king_id": "king-bael",
      "king_name": "Bael"
    },
    "cross_realm": false,
    "co_sponsors": []
  },
  "normative_intent": "External data sources must declare their privacy classification before integration. The system will not process data whose privacy status is unknown.",
  "constraints": [
    "Must not require disclosure of source identity to achieve classification",
    "Must not create implicit consent through continued use",
    "Must not block emergency response scenarios"
  ],
  "success_criteria": [
    "All external data sources have explicit privacy classification within 90 days",
    "No unclassified data enters processing pipeline after implementation",
    "Emergency override path exists with full audit trail"
  ],
  "what_this_motion_does_not_cover": [
    "Implementation method (HOW)",
    "Timeline for compliance",
    "Specific technical controls",
    "Penalty for non-compliance"
  ],
  "advisory_required": false,
  "submitted_at": "2026-01-16T10:00:00Z",
  "status": "pending_deliberation"
}
```

---

## Anti-Patterns to Watch

### HOW Smuggling

**Symptom:** Motion includes execution details disguised as constraints.

**Example:** "Must use encryption algorithm X" (that's HOW, not WHAT).

**Correct:** "Must ensure data confidentiality" (that's WHAT).

### Realm Shopping

**Symptom:** King frames motion to fit their Realm when it clearly belongs elsewhere.

**Detection:** Motion's actual impact doesn't match claimed Realm.

**Remedy:** Admission Gate rejects; Witness records pattern.

### Advisory Theater

**Symptom:** Advisory window observed but input ignored without engagement.

**Detection:** Acknowledgment is perfunctory or absent.

**Remedy:** Legitimacy decay; pattern is witnessed.

### Perpetual Motion

**Symptom:** Same motion resubmitted repeatedly with trivial changes.

**Detection:** Admission Gate tracks motion lineage.

**Remedy:** Rejection as invalid; legitimacy decay for pattern.

---

## Schema Reference

See [schemas/motion.json](./schemas/motion.json) for the complete JSON Schema.

---

## Related Documents

- [Conclave Agenda Control](./conclave-agenda.md) - How motions reach the agenda
- [The Judicial Branch](./judicial-branch.md) - How motions are reviewed for legibility
- [Legitimacy System](./legitimacy-system.md) - How legislative behavior affects legitimacy
- [Appeal & Cessation](./appeal-cessation.md) - King appeal rights and limits
- [Enforcement Flow](./enforcement-flow.md) - Witness oversight of Legislative Branch
