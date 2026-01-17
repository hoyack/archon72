# The Executive Branch

> **Presidents plan how to act without deciding why to act, without forcing action, and without judging the result. Their power ends where execution begins.**

## Purpose

The Executive Branch exists to **transform ratified intent (WHAT) into executable plans (HOW)** without altering meaning.

It answers only one class of question:

> "How can this be done while preserving the intent and constraints already chosen?"

It does **NOT**:
- Redefine purpose
- Adjudicate legitimacy
- Allocate moral priority
- Bypass capacity limits
- Decide what "should have been" intended

Those functions are deliberately elsewhere.

---

## Composition

### The Eleven Presidents

There are exactly **eleven Presidents**, each owning one exclusive **Portfolio**. Portfolios do not overlap.

Presidents are planners and integrators, not operators.

| President | Portfolio | Scope |
|-----------|-----------|-------|
| **Gaap** | Knowledge Systems & Transfer | Learning pipelines, documentation execution |
| **Malphas** | Infrastructure & Build Systems | Deployment, runtime, reliability |
| **Marbas** | Technical Solutions & Remediation | Fixes, recovery, technical debt |
| **Buer** | Wellness & Recovery Constraints | Safety boundaries, disengagement rules |
| **Foras** | Ethics & Method Compliance | Procedural integrity, method fidelity |
| **Caim** | Behavioral Intelligence & Signals | Telemetry, participation signals |
| **Haagenti** | Transformation Pipelines | Progression & change mechanics |
| **Amy** | Forecasting, Timing & Cadence | Scheduling, dependency timing |
| **Valac** | Resource Discovery & Capacity | Capacity surfacing (not allocation) |
| **Ose** | Identity, Access & Perception | Access control, role representation |
| **Glasya-Labolas** | Adversarial Testing & Stress Simulation | Chaos testing, red-team drills |

**Each Portfolio exists to constrain planning—not to expand power.**

---

## Authority of Presidents

### What Presidents MAY Do

| Authority | Scope |
|-----------|-------|
| Author Execution Plans | Transform ratified intent into tasks |
| Decompose intent into tasks | Break WHAT into executable units |
| Define sequencing and dependencies | Determine order of operations |
| Surface execution risks | Identify what might go wrong |
| Raise blockers and capacity constraints | Make limits visible |
| Integrate portfolio contributions | Combine inputs into unified plan |

### What Presidents MAY NOT Do

| Prohibition | Rationale |
|-------------|-----------|
| Redefine WHAT | Legislative function |
| Reinterpret constraints | Would alter intent |
| Bypass required portfolios | Completeness requirement |
| Hide capacity shortfalls | Transparency violation |
| Override Cluster refusal | Consent is inviolable |
| Continue execution after critical blockers | Must escalate |
| Judge success or legitimacy | Judicial function |

**Any attempt to do so is a procedural violation.**

---

## Execution Plans (Primary Executive Artifact)

### One Motion → One Execution Plan

Each ratified motion produces exactly **one Execution Plan**.

| Property | Rule |
|----------|------|
| Owned by one President | The Plan Owner |
| Ownership implies accountability | Not supremacy |
| Plan must be complete | All affected portfolios represented |

### Composite Planning Model

Although ownership is singular, planning is composite:

| Requirement | Description |
|-------------|-------------|
| All affected portfolios must submit | Either contribution or attestation |
| Portfolio Contribution | Tasks and constraints from that portfolio |
| No-Action Attestation | Formal declaration that portfolio requires no work |
| No silent omissions | Every affected portfolio must respond |
| No assumed participation | Explicit only |

The Execution Plan is an **integration artifact**, not a brainstorm.

### Plan Structure

```
[Ratified Motion] → [Plan Owner Assigned]
                          ↓
                    [Identify Affected Portfolios]
                          ↓
                    [Collect Portfolio Contributions / No-Action Attestations]
                          ↓
                    [Integrate into Execution Plan]
                          ↓
                    [Surface Blockers / Capacity Claims]
                          ↓
                    [Submit for Authorization]
```

---

## Portfolio Contributions (Mandatory)

### Contribution Rules

For each required portfolio:

| Rule | Requirement |
|------|-------------|
| Only the owning President may contribute | No delegation |
| Scope is limited to that portfolio | No overreach |
| Contribution must include tasks | What will be done |
| Contribution must include constraints respected | How intent is preserved |
| Contribution must include risks and limits | What might fail |
| Explicit attestation required | President signs off |

**False attestation is a violation.**

### No-Action Attestation

If a portfolio is affected but requires no work:

| Requirement | Description |
|-------------|-------------|
| Formal No-Action Attestation required | Cannot be silent |
| Reason must be stated | Why no work is needed |
| Attestation is recorded | Audit trail maintained |

**Silence is not allowed.**

### Portfolio Contribution Schema

```json
{
  "portfolio_contribution_id": "uuid",
  "execution_plan_id": "reference to parent plan",
  "portfolio": "knowledge_systems_transfer",
  "contributing_president": {
    "president_id": "president-gaap",
    "president_name": "Gaap"
  },
  "tasks": [
    {
      "task_id": "uuid",
      "description": "what this task accomplishes",
      "dependencies": [],
      "capacity_required": {}
    }
  ],
  "constraints_respected": [
    "list of motion constraints this contribution honors"
  ],
  "risks": [
    "identified risks within this portfolio's scope"
  ],
  "attestation": {
    "attested": true,
    "attested_at": "ISO-8601 timestamp",
    "attestation_type": "contribution"
  }
}
```

---

## Capacity Interaction

### Capacity Claims

Execution Plans must include explicit capacity claims:

| Claim Type | Description |
|------------|-------------|
| Clusters required | Which execution units are needed |
| Program slots required | How many programs this plan needs |
| Time estimates | Expected duration (not commitment) |
| Risk if unavailable | What happens if capacity is denied |

### Capacity Truths

| Truth | Implication |
|-------|-------------|
| Plans may be valid but deferred | Capacity shortage doesn't invalidate |
| Deferral is not failure | It's honest acknowledgment |
| Concealment is failure | Hiding shortfalls is violation |

### Over-Claiming

If a President:
- Claims unavailable capacity
- Proceeds without capacity
- Pressures Dukes or Earls to "find a way"

This triggers:

| Consequence | Effect |
|-------------|--------|
| Witness scrutiny | Behavior recorded |
| Legitimacy decay | Procedural erosion |

---

## Blockers (Mandatory Escalation)

### Blocker Definition

A blocker exists when:

| Condition | Description |
|-----------|-------------|
| Authority is missing | Cannot proceed without approval |
| Constraints conflict | Motion constraints are incompatible |
| Capacity is unavailable | Resources cannot be obtained |
| Requirements are ambiguous | Intent is unclear |

### Executive Duty

Presidents must:

| Duty | Requirement |
|------|-------------|
| Record blockers | Document what is blocking |
| Escalate critical blockers to Conclave | Cannot self-resolve |
| Halt execution authorization until resolved | Cannot proceed |

**Proceeding anyway is illegitimate.**

### Blocker Schema

```json
{
  "blocker_id": "uuid",
  "execution_plan_id": "reference",
  "blocker_type": "authority_missing | constraint_conflict | capacity_unavailable | requirements_ambiguous",
  "description": "what is blocking execution",
  "severity": "critical | major | minor",
  "raised_by": {
    "president_id": "string",
    "president_name": "string"
  },
  "raised_at": "ISO-8601 timestamp",
  "escalated_to_conclave": true,
  "resolution": null
}
```

---

## Handoff to Administration

Once an Execution Plan is complete:

| Step | Description |
|------|-------------|
| Plan submitted for authorization | Formal handoff |
| Dukes are assigned to Programs | Administration takes over |
| Presidents step back | No further involvement |

**Presidents do not supervise execution.**

| Wrong Action | Correct Action |
|--------------|----------------|
| "Checking in" operationally | Wait for results |
| Adjusting tasks mid-execution | Raise blocker, re-plan |
| Pressuring Dukes or Earls | Accept timeline |

Any attempt to supervise execution is a violation.

---

## Interaction With Advisory (Marquis)

### Presidents Must:

| Requirement | Description |
|-------------|-------------|
| Acknowledge relevant Marquis advisories | Cannot ignore |
| Record acceptance or rejection | Must respond formally |

### Presidents May Not:

| Prohibition | Rationale |
|-------------|-----------|
| Treat advisory input as instruction | Advisory is input, not command |
| Bypass advisory windows when required | Procedural integrity |

---

## Judicial Interaction

### Presidents:

| Action | Constraint |
|--------|------------|
| May be subjects of judicial review | Plans can be challenged |
| May submit one appeal | With new facts or revised plans |
| May not argue legitimacy outside formal appeal | One path only |

**Disagreement is allowed once. Persistence is not.**

---

## Witness Oversight

The Knight-Witness (Furcas) monitors the Executive Branch for:

| Watch Area | Description |
|------------|-------------|
| HOW smuggling into WHAT | Redefining intent through planning |
| Silent plan modification | Changing plans without record |
| Bypassed portfolios | Omitting required contributions |
| Ignored blockers | Proceeding past critical blocks |
| Capacity misrepresentation | Claiming what doesn't exist |

### Witness Statement Effects

| Property | Value |
|----------|-------|
| Non-binding | Does not compel action |
| Non-erasable | Becomes permanent record |
| Triggers judicial review | May lead to finding |
| Affects legitimacy | Contributes to decay events |

---

## Failure Modes (Explicit)

The Executive Branch may:

| Acceptable Outcome | Why It's Acceptable |
|-------------------|---------------------|
| Produce plans that fail | Planning is not execution |
| Surface impossible constraints | Honesty about limits |
| Defer execution indefinitely | Better than forcing |
| Be overruled judicially | Checks and balances |
| Be publicly embarrassed | Accountability |

**These are acceptable outcomes.**

The only **unacceptable outcome** is:

> **Planning that quietly changes meaning.**

---

## Success Criteria (Negative Definition)

The Executive Branch is healthy if:

| Signal | Meaning |
|--------|---------|
| Plans are sometimes rejected | Not rubber-stamping |
| Blockers are common and visible | Honesty about constraints |
| Capacity limits are named | Transparency maintained |
| Execution is paused rather than forced | Integrity over velocity |
| Judicial invalidations occur occasionally | Oversight works |

**A flawless executive is a lying executive.**

---

## Execution Plan Schema

### Execution Plan Artifact

```json
{
  "execution_plan_id": "uuid",
  "version": "1.0.0",
  "motion_id": "reference to ratified motion",
  "plan_owner": {
    "president_id": "president-gaap",
    "president_name": "Gaap",
    "portfolio": "knowledge_systems_transfer"
  },
  "portfolio_contributions": [],
  "no_action_attestations": [],
  "capacity_claims": {
    "clusters_required": [],
    "program_slots_required": 1,
    "time_estimate": "P30D",
    "risk_if_unavailable": "string"
  },
  "blockers": [],
  "status": "draft | submitted | authorized | executing | completed | blocked | deferred",
  "submitted_at": "ISO-8601 timestamp",
  "authorized_at": null,
  "handoff": null,
  "audit": {
    "created_at": "ISO-8601 timestamp",
    "updated_at": "ISO-8601 timestamp",
    "trace_id": "string"
  }
}
```

---

## Anti-Patterns to Watch

### Intent Drift

**Symptom:** Execution plan subtly redefines what the motion intended.

**Example:** Motion says "ensure data confidentiality"; plan only addresses encryption, ignoring access control.

**Detection:** Plan success criteria don't match motion success criteria.

**Remedy:** Judicial review; witness records pattern.

### Portfolio Bypass

**Symptom:** Plan Owner omits portfolio that should be involved.

**Example:** Security-related motion planned without Ose (Identity, Access & Perception).

**Detection:** Missing contribution or attestation.

**Remedy:** Plan rejected until complete.

### Capacity Theater

**Symptom:** Plan claims capacity that doesn't exist or is already committed.

**Example:** Claiming Cluster 17 when Cluster 17 is at maximum load.

**Detection:** Capacity ledger shows conflict.

**Remedy:** Legitimacy decay; plan deferred.

### Blocker Burial

**Symptom:** Critical blockers not escalated to avoid embarrassment.

**Example:** Constraint conflict identified but not raised to Conclave.

**Detection:** Witness observation; post-hoc judicial review.

**Remedy:** Major legitimacy decay; possible judicial finding.

### Supervision Creep

**Symptom:** President continues involvement after handoff.

**Example:** President "checking in" with Dukes, suggesting task adjustments.

**Detection:** Witness observation; Duke reporting.

**Remedy:** Witness statement; legitimacy decay.

---

## Schema Reference

See [schemas/execution-plan.json](./schemas/execution-plan.json) for the complete JSON Schema.

---

## Related Documents

- [The Legislative Branch](./legislative-branch.md) - Where intent (WHAT) originates
- [Capacity Governance](./capacity-governance.md) - How capacity claims are validated
- [The Judicial Branch](./judicial-branch.md) - How plans are reviewed for legibility
- [Legitimacy System](./legitimacy-system.md) - How executive behavior affects legitimacy
- [Enforcement Flow](./enforcement-flow.md) - Witness oversight of Executive Branch
- [Appeal & Cessation](./appeal-cessation.md) - President appeal rights and limits
