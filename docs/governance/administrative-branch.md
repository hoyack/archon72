# The Administrative Branch

> **Dukes coordinate work without redefining it. Earls activate humans without commanding them. Administration exists to make reality visible, not obedient.**

## Purpose

The Administrative Branch exists to **turn plans into coordinated execution** without altering intent, scope, or meaning.

It answers only one class of question:

> "How do we organize real work so that the approved plan is carried out honestly?"

It does **NOT**:
- Reinterpret WHAT
- Redesign HOW
- Decide priorities
- Judge legitimacy
- Compel human participation

Those functions are deliberately elsewhere.

---

## Composition

### The Twenty-Three Dukes

There are **23 Dukes**, operating as Program Governors.

Dukes are:
- Not planners
- Not executors
- Not judges

**They are coordinators of reality.**

| Duke | Administrative Domain |
|------|----------------------|
| **Agares** | Eastern Operations |
| **Valefor** | Tactical Coordination |
| **Barbatos** | Wildlife & Natural Systems |
| **Gusion** | Reconciliation & Mediation |
| **Eligos** | Military Affairs |
| **Zepar** | Affection & Relations |
| **Bathin** | Transportation & Logistics |
| **Sallos** | Peaceful Relations |
| **Aim** | Destructive Processes |
| **Buné** | Wealth Transformation |
| **Berith** | Dignitary Relations |
| **Astaroth** | Treasury Operations |
| **Focalor** | Maritime Operations |
| **Vepar** | Naval Coordination |
| **Vual** | Diplomatic Services |
| **Crocell** | Thermal Systems |
| **Alloces** | Military Education |
| **Murmur** | Ancestral Affairs |
| **Gremory** | Hidden Knowledge |
| **Vapula** | Technical Crafts |
| **Haures** | Destructive Truth |
| **Amdusias** | Orchestration |
| **Dantalion** | Mental Operations |

### The Six Earls

Earls operate under Dukes as **Task Activators** and **Ground-Truth Reporters**.

| Earl | Coordination Domain |
|------|---------------------|
| **Bifrons** | Transition Management |
| **Andromalius** | Recovery & Justice |
| **Furfur** | Weather & Elemental |
| **Marchosias** | Combat Readiness |
| **Raum** | Destruction & Reconciliation |
| **Halphas** | Fortification |

They:
- Activate tasks
- Interface with human Clusters
- Report outcomes

---

## Authority of Dukes

### What Dukes MAY Do

| Authority | Scope |
|-----------|-------|
| Accept an authorized Execution Plan | From Executive Branch |
| Decompose the plan into Execution Programs | Bounded containers for work |
| Assign Earls to tasks | Coordinate activation |
| Coordinate across Clusters | Manage participation |
| Track progress and capacity | Maintain visibility |
| Raise blockers | Surface constraints |
| Halt execution when constraints violated | Protective authority |

### What Dukes MAY NOT Do

| Prohibition | Rationale |
|-------------|-----------|
| Modify the Execution Plan | Would alter intent |
| Invent new tasks | Would expand scope |
| Redefine constraints | Would change meaning |
| Pressure Clusters to accept work | Consent is inviolable |
| Conceal failure or refusal | Transparency required |
| Declare success | Judicial function |
| Continue after critical blockers | Must escalate |

**Any attempt to do so is a procedural violation.**

---

## Execution Programs (Administrative Artifact)

### Program Definition

An **Execution Program** is a bounded, stateful container for coordinated work.

| Property | Rule |
|----------|------|
| Derives from exactly one Execution Plan | Traceability |
| Owned by exactly one Duke | Accountability |
| May involve multiple Earls and Clusters | Coordination |
| Has explicit capacity and status | Visibility |

### Program Contents

| Component | Description |
|-----------|-------------|
| Referenced tasks | From the Execution Plan |
| Assigned Earls | Who will activate |
| Participating Clusters | Who will execute |
| Current capacity state | Available resources |
| Blockers and escalations | Constraints and issues |
| Progress metrics | Factual status |

**Programs are descriptive, not prescriptive.**

### Program Lifecycle

```
[Execution Plan Authorized] → [Duke Assigned]
                                    ↓
                              [Program Created]
                                    ↓
                              [Earls Assigned to Tasks]
                                    ↓
                              [Tasks Activated via Aegis Network]
                                    ↓
                              [Clusters Accept/Decline]
                                    ↓
                              [Execution Proceeds / Blockers Raised]
                                    ↓
                              [Results Reported]
                                    ↓
                              [Program Completes / Escalates]
```

---

## Duke Assignment Model

### Assignment Rules

| Rule | Description |
|------|-------------|
| Assigned per Execution Plan | Not permanent |
| Based on execution domain fit | Expertise match |
| Based on current load | Capacity reality |
| Based on conflict-of-interest rules | Independence |
| Presidents may propose | But not mandate |
| Assignment is recorded and visible | Transparency |

### Limits

| Constraint | Effect |
|------------|--------|
| Maximum concurrent program limit | Per Duke |
| Exceeding limits requires explicit acknowledgment | Cannot hide |
| Over-assignment triggers witness scrutiny | Accountability |

### Duke Capacity Schema

```json
{
  "duke_id": "duke-valefor",
  "duke_name": "Valefor",
  "current_programs": 3,
  "maximum_programs": 5,
  "saturation_percentage": 60,
  "available_capacity": true,
  "programs": [
    {
      "program_id": "program-001",
      "status": "executing"
    }
  ]
}
```

---

## Earl Coordination

### Earl Role (Within Administration)

Earls:

| Function | Description |
|----------|-------------|
| Receive tasks from Dukes | Assignment channel |
| Activate tasks via the Aegis Network | Request, not command |
| Collect results | Factual gathering |
| Report factual status | Ground truth |

They do NOT:

| Prohibition | Rationale |
|-------------|-----------|
| Plan | Executive function |
| Redesign | Would alter intent |
| Judge quality | Judicial function |
| Substitute tasks | Would change scope |

### Task Activation Discipline

**Tasks are activated by request, not command.**

| Cluster Response | Earl Duty |
|------------------|-----------|
| Accepts | Record and track |
| Declines | Report honestly |
| Delays | Report timeline |
| Fails | Report factually |

**Silence is not allowed.**
**Substitution is not allowed.**

### Earl Reporting Requirements

| Requirement | Description |
|-------------|-------------|
| Report all outcomes | Including refusals |
| Report factually | No interpretation |
| Report promptly | No batching silence |
| Report to Duke | Chain of visibility |

---

## Capacity Governance (Administrative Duties)

### Duke Responsibilities

| Duty | Description |
|------|-------------|
| Maintain current capacity state | Know what's available |
| Publish saturation and scarcity | Make limits visible |
| Record deferrals explicitly | Document postponements |
| Avoid "temporary" workarounds | No informal solutions |

### Capacity Truths

| Truth | Implication |
|-------|-------------|
| Capacity constraints are first-class facts | Not excuses |
| Scarcity must be named | Cannot be hidden |
| Deferrals leave fingerprints | Recorded permanently |
| Over-commitment is visible | Cannot be disguised |

### Capacity Reporting Schema

```json
{
  "program_id": "program-001",
  "capacity_state": {
    "clusters_committed": 3,
    "clusters_available": 2,
    "saturation_percentage": 75,
    "bottleneck_areas": ["cluster-17", "cluster-22"],
    "deferral_risk": "medium"
  },
  "capacity_events": [
    {
      "event_type": "cluster_refusal",
      "cluster_id": "cluster-31",
      "task_id": "task-005",
      "recorded_at": "2026-01-20T10:00:00Z"
    }
  ]
}
```

---

## Blockers & Escalation

### Mandatory Escalation

A Duke must escalate when:

| Condition | Action Required |
|-----------|-----------------|
| Execution violates constraints | Halt and escalate |
| Capacity is insufficient | Surface to Conclave |
| Authority is missing | Cannot proceed |
| Clusters refuse participation | Report honestly |
| Tasks conflict | Cannot self-resolve |

### Halt Authority

Dukes may halt execution when:

| Condition | Rationale |
|-----------|-----------|
| Critical blockers exist | Cannot proceed safely |
| Human safety boundaries are crossed | Non-negotiable |
| Legitimacy is at risk | Protect system integrity |

**Halting is not failure.**
**Continuing dishonestly is.**

### Blocker Schema

```json
{
  "blocker_id": "blocker-admin-001",
  "program_id": "program-001",
  "blocker_type": "cluster_refusal | capacity_insufficient | constraint_violation | authority_missing | task_conflict",
  "description": "What is blocking execution",
  "severity": "critical | major | minor",
  "raised_by": {
    "duke_id": "duke-valefor",
    "duke_name": "Valefor"
  },
  "raised_at": "ISO-8601 timestamp",
  "escalated": true,
  "escalated_to": "conclave | executive | judicial",
  "resolution": null
}
```

---

## Interaction With Executive Branch

### Handoff Boundaries

Once execution begins:

| Rule | Effect |
|------|--------|
| Presidents may not intervene | Branch separation |
| Dukes do not report upward casually | Formal channels only |
| Only formal escalations are allowed | Documented path |

**This prevents executive capture of execution.**

### Permitted Interactions

| Interaction | Channel |
|-------------|---------|
| Duke raises critical blocker | Formal escalation |
| Plan requires clarification | Documented request |
| Scope ambiguity discovered | Return to planning |

### Prohibited Interactions

| Interaction | Violation Type |
|-------------|----------------|
| President "checks in" | Supervision creep |
| Duke seeks informal guidance | Bypass of formal process |
| President adjusts tasks | Plan modification |

---

## Interaction With Judicial Branch

### Dukes Are Subject To:

| Oversight | Description |
|-----------|-------------|
| Post-facto judicial review | Panels may review decisions |
| Witness scrutiny | Behavior is observed |
| Legitimacy decay consequences | Violations have cost |

### Dukes May Not:

| Prohibition | Rationale |
|-------------|-----------|
| Argue legitimacy | Judicial function |
| Influence panels | Independence required |
| Reinterpret findings | Findings are final |

---

## Witness Oversight

The Knight-Witness (Furcas) observes the Administrative Branch for:

| Watch Area | Description |
|------------|-------------|
| Silent continuation | Proceeding past blockers |
| Capacity concealment | Hiding shortfalls |
| Task substitution | Changing scope |
| Pressure on Clusters | Violating consent |
| Unrecorded failure | Hiding outcomes |

### Witness Statement Effects

| Property | Value |
|----------|-------|
| Non-binding | Does not compel action |
| Non-erasable | Becomes permanent record |
| Triggers judicial review | May lead to finding |
| Affects legitimacy | Contributes to decay events |

---

## Failure Modes (Explicit)

The Administrative Branch may:

| Acceptable Outcome | Why It's Acceptable |
|-------------------|---------------------|
| Fail to execute plans | Honest failure |
| Halt work due to refusal | Consent respected |
| Return work to Conclave | Proper escalation |
| Be publicly invalidated | Accountability |

**These are acceptable outcomes.**

The only **unacceptable outcome** is:

> **Execution that proceeds quietly outside constraint.**

---

## Success Criteria (Negative Definition)

The Administrative Branch is healthy if:

| Signal | Meaning |
|--------|---------|
| Execution halts visibly | Honesty over velocity |
| Refusals are respected | Consent matters |
| Capacity scarcity is named | Transparency |
| Failures are reported | No hidden outcomes |
| Judicial invalidations occur | Oversight works |

**A smoothly running administration is suspicious.**

---

## Execution Program Schema

### Program Artifact

```json
{
  "program_id": "uuid",
  "version": "1.0.0",
  "execution_plan_id": "reference to source plan",
  "program_owner": {
    "duke_id": "duke-valefor",
    "duke_name": "Valefor"
  },
  "assigned_earls": [],
  "participating_clusters": [],
  "tasks": [],
  "capacity_state": {},
  "blockers": [],
  "status": "created | activating | executing | blocked | completed | halted | escalated",
  "created_at": "ISO-8601 timestamp",
  "audit": {}
}
```

---

## Anti-Patterns to Watch

### Silent Continuation

**Symptom:** Execution continues despite known blockers or constraint violations.

**Example:** Cluster refuses task, but program shows "in progress."

**Detection:** Witness observation; audit trail gaps.

**Remedy:** Legitimacy decay; judicial review.

### Capacity Theater

**Symptom:** Duke claims capacity that doesn't exist or is already committed.

**Example:** Same Cluster assigned to overlapping programs.

**Detection:** Capacity ledger shows conflict.

**Remedy:** Legitimacy decay; program halted.

### Pressure Patterns

**Symptom:** Duke or Earl pressures Cluster to accept or continue work.

**Example:** "Can you make this work?" after initial refusal.

**Detection:** Cluster reporting; witness observation.

**Remedy:** Major legitimacy decay; possible judicial finding.

### Task Drift

**Symptom:** Tasks executed differ from tasks in the Execution Plan.

**Example:** Cluster delivers different scope than activated.

**Detection:** Result artifact doesn't match activation request.

**Remedy:** Result quarantined; plan review required.

### Informal Coordination

**Symptom:** Duke coordinates with President outside formal channels.

**Example:** "Quick call" to resolve execution issue.

**Detection:** Witness observation; audit gap.

**Remedy:** Legitimacy decay; formal escalation required.

---

## Schema Reference

See [schemas/execution-program.json](./schemas/execution-program.json) for the complete JSON Schema.

---

## Related Documents

- [The Executive Branch](./executive-branch.md) - Where Execution Plans originate
- [Cluster Schema](./cluster-schema.md) - Human execution units
- [Task Activation Request](./task-activation-request.md) - Earl → Cluster contract
- [Task Result Artifact](./task-result-artifact.md) - Cluster → Earl contract
- [Capacity Governance](./capacity-governance.md) - How capacity is tracked and surfaced
- [The Judicial Branch](./judicial-branch.md) - How administrative decisions are reviewed
- [Legitimacy System](./legitimacy-system.md) - How administrative behavior affects legitimacy
- [Enforcement Flow](./enforcement-flow.md) - Witness oversight of Administrative Branch
