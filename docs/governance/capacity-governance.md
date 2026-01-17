# Capacity Governance

> **Capacity Governance is an append-only system that records what can be done, what is claimed, and what is deferred—so scarcity becomes visible, prioritization becomes explicit, and execution pressure cannot masquerade as inevitability.**

## Overview

Capacity is real, finite execution ability:

- Available Clusters
- Human time
- Cognitive bandwidth
- Operational attention

It is not money, not merit, not moral worth.
It is simply **how much can actually be done without lying.**

**Unacknowledged scarcity is where favoritism hides.**

---

## The Problem This Solves

Without explicit capacity governance:

| Symptom | Hidden Dynamic |
|---------|----------------|
| Presidents "sequence" plans informally | Invisible prioritization |
| Dukes quietly favor some programs | Shadow allocation |
| Urgent rhetoric beats uncomfortable work | Emotional manipulation |
| Deferral looks like forgetfulness | Plausible deniability |

This creates a **shadow treasury**—power without a name.

---

## Design Constraints (Non-Negotiable)

| Constraint | Rationale |
|------------|-----------|
| **No hidden prioritization** | All sequencing must be recorded |
| **No optimization for fairness** | Fairness is a judgment; visibility is a fact |
| **No central allocator with discretion** | Discretion is where corruption hides |
| **Deferral must be named** | Not implied, forgotten, or explained away |
| **Scarcity must be visible** | To everyone, not just decision-makers |

**Capacity governance doesn't make decisions better. It makes them accountable.**

---

## The Capacity Ledger

Capacity is represented as a **Ledger, not a Controller**.

The Capacity Ledger is append-only, descriptive, not directive.

### What the Ledger Records

| Record Type | Description |
|-------------|-------------|
| Declared capacity | What sources say is available |
| Claimed capacity | What plans require |
| Consumed capacity | What is actually in use |
| Deferred capacity | What was requested but not available |
| Idle capacity | When availability exceeds claims |

### What the Ledger Does NOT Do

- Does not assign work
- Does not prioritize
- Does not optimize
- Does not decide

**It only records the state of reality.**

---

## Capacity Sources

Capacity enters the system from four canonical sources. All four must be recorded to avoid blame-shifting.

### Source 1: Clusters (Availability)

Clusters are the primary source of execution capacity.

| Attribute | Description |
|-----------|-------------|
| Available task slots | Concurrent tasks cluster can accept |
| Availability status | available, limited, unavailable |
| Constraints | Restrictions on task types |
| Hours of operation | When capacity is active |

### Source 2: Dukes (Program Load)

Dukes manage program-level capacity.

| Attribute | Description |
|-----------|-------------|
| Active programs | Programs currently managed |
| Program slots | Maximum concurrent programs |
| Remaining slots | Available program capacity |

### Source 3: Earls (Task Saturation)

Earls manage task-level throughput.

| Attribute | Description |
|-----------|-------------|
| Active tasks | Tasks currently in flight |
| Max tasks | Earl's task management ceiling |
| Saturation status | available, near_capacity, saturated |

### Source 4: Presidents (Plan Scope)

Presidents create demand through execution plans.

| Attribute | Description |
|-----------|-------------|
| Active plans | Plans currently executing |
| Pending plans | Plans awaiting capacity |
| Claimed capacity | Total capacity required by plans |

---

## Capacity Units

Avoid fine-grained units that invite gaming. Use **coarse, honest units**.

### Defined Units

| Unit | Meaning | Declared By |
|------|---------|-------------|
| `cluster-slot` | One concurrent task slot in a Cluster | Cluster Steward |
| `program-slot` | One program management slot | Duke |
| `task-slot` | One task management slot | Earl |
| `plan-slot` | One execution plan in flight | President |

### Unit Properties

- **Self-declared** - Sources declare their own capacity
- **Witnessed** - Knight-Witness records declarations
- **Coarse** - No fractional units or complex formulas
- **Time-bounded** - Declarations have validity periods

---

## Capacity Declaration Artifacts

### Cluster Capacity Declaration

Clusters declare their execution availability.

```json
{
  "declaration_id": "uuid",
  "declaration_type": "cluster_capacity",
  "cluster_id": "cluster-17",
  "declared_at": "2026-01-16T08:00:00Z",
  "valid_until": "2026-01-23T08:00:00Z",
  "availability": "limited",
  "available_task_slots": 2,
  "max_task_slots": 4,
  "constraints": [
    "No sensitive data tasks this week",
    "Reduced hours: 09:00-17:00 only"
  ],
  "reason_for_limitation": "Team member on leave",
  "steward_attestation": true
}
```

### Duke Program Load Declaration

Dukes declare their program management capacity.

```json
{
  "declaration_id": "uuid",
  "declaration_type": "duke_program_load",
  "duke_id": "duke-valefor",
  "declared_at": "2026-01-16T08:00:00Z",
  "active_programs": 2,
  "max_program_slots": 3,
  "remaining_program_slots": 1,
  "active_program_ids": [
    "program-q1-security-review",
    "program-infrastructure-upgrade"
  ],
  "constraints": [
    "Cannot accept programs requiring judicial oversight"
  ]
}
```

### Earl Task Saturation Report

Earls report their task management saturation.

```json
{
  "declaration_id": "uuid",
  "declaration_type": "earl_task_saturation",
  "earl_id": "earl-raum",
  "declared_at": "2026-01-16T08:00:00Z",
  "active_tasks": 5,
  "max_tasks": 5,
  "status": "saturated",
  "active_task_ids": [
    "task-001", "task-002", "task-003", "task-004", "task-005"
  ],
  "estimated_slot_available_at": "2026-01-18T12:00:00Z",
  "bottleneck_reason": "Waiting on Cluster 17 results for task-003"
}
```

### President Plan Demand Declaration

Presidents declare capacity requirements when submitting plans.

```json
{
  "declaration_id": "uuid",
  "declaration_type": "president_plan_demand",
  "president_id": "president-paimon",
  "execution_plan_id": "plan-q2-expansion",
  "declared_at": "2026-01-16T08:00:00Z",
  "claimed_capacity": {
    "clusters_required": 3,
    "program_slots_required": 2,
    "task_slots_required": 8,
    "estimated_duration": "P14D"
  },
  "risk_if_unavailable": "high",
  "deferral_acceptable": true,
  "deferral_max_duration": "P30D"
}
```

---

## Capacity Claims During Planning

When a President submits an Execution Plan, they must include a **Capacity Claim**.

### Capacity Claim Schema

```json
{
  "claim_id": "uuid",
  "execution_plan_id": "plan-uuid",
  "claimed_at": "2026-01-16T10:00:00Z",
  "claimed_capacity": {
    "clusters_required": 3,
    "cluster_capabilities_required": ["research", "analysis"],
    "program_slots_required": 2,
    "task_slots_required": 8,
    "estimated_duration": "P14D"
  },
  "risk_if_unavailable": "high",
  "priority_justification": "Q2 deadline commitment to stakeholders",
  "alternatives_if_constrained": [
    "Reduce scope to 2 clusters, extend duration to P21D",
    "Defer non-critical tasks to Q3"
  ]
}
```

### Claim Resolution

| Scenario | Outcome |
|----------|---------|
| Capacity available | Plan proceeds to execution |
| Capacity partially available | Plan modified or partially executed |
| Capacity unavailable | Plan deferred with explicit record |
| Capacity contested | Conclave prioritization required |

**If capacity isn't available:**
- The plan remains valid
- Execution is deferred
- The deferral is explicit
- **No "we'll figure it out later"**

---

## Deferral as First-Class Outcome

Deferral is not a failure state. It is an **explicit, recorded decision**.

### Deferral Record

```json
{
  "deferral_id": "uuid",
  "item_type": "execution_plan",
  "item_id": "plan-q2-expansion",
  "deferred_at": "2026-01-16T14:00:00Z",
  "reason": "insufficient_cluster_capacity",
  "reason_detail": "Required 3 clusters with research capability; only 1 available until 2026-01-25",
  "severity": "operational",
  "deferred_by": "capacity_governance_system",
  "acknowledged_by": "president-paimon",
  "next_review_at": "2026-01-20T14:00:00Z",
  "deferral_count": 1,
  "escalation_threshold": 3
}
```

### Deferral Requirements

Deferrals must:

| Requirement | Mechanism |
|-------------|-----------|
| Appear on Conclave Agenda | Bounded by agenda control |
| Age visibly | Deferral count tracked |
| Escalate if repeated | 3+ deferrals → forced agenda item |
| Have review dates | Cannot be deferred indefinitely |

**Deferral is not failure. Concealment is.**

---

## Capacity States

The system tracks capacity in defined states.

### State Definitions

| State | Meaning | Trigger |
|-------|---------|---------|
| `abundant` | Available capacity exceeds claims | Idle slots > 50% |
| `balanced` | Claims roughly match availability | Utilization 50-80% |
| `constrained` | Claims exceed comfortable availability | Utilization 80-95% |
| `scarce` | Claims significantly exceed availability | Utilization > 95% |
| `crisis` | Critical work cannot proceed | Essential capacity unavailable |

### State Effects

| State | Effect |
|-------|--------|
| Abundant | Normal operations |
| Balanced | Normal operations |
| Constrained | Advisory: capacity pressure visible |
| Scarce | New claims require explicit prioritization |
| Crisis | Mandatory Conclave acknowledgement; execution pause for non-essential work |

---

## Integration with Agenda Control

Capacity governance feeds directly into agenda control.

### Automatic Agenda Items

| Condition | Agenda Effect |
|-----------|---------------|
| Repeated deferrals (3+) | Forced Band 1 item |
| Capacity crisis | Forced Band 0 acknowledgement |
| Over-claimed capacity | Witness statement → Band 0 |
| Persistent scarcity (3+ Conclaves) | Mandatory capacity review |

### Capacity-Agenda Flow

```
[Capacity Declaration] → [Claim Submitted] → [Insufficient Capacity?]
                                                    ↓ Yes
                                            [Deferral Record]
                                                    ↓
                                            [Deferral Count++]
                                                    ↓
                                            [Count >= 3?] → Yes → [Band 1 Agenda Item]
                                                    ↓ No
                                            [Standard Review]
```

---

## Integration with Legitimacy System

Capacity governance affects legitimacy through recorded events.

### Accumulation Events

| Event | Weight |
|-------|--------|
| Honest capacity declaration | Minor |
| Deferral acknowledged transparently | Minor |
| Capacity crisis handled procedurally | Moderate |

### Decay Events

| Event | Severity |
|-------|----------|
| Capacity over-claim detected | Minor |
| Silent prioritization | Major |
| Deferral concealment | Major |
| Work proceeded without declared capacity | Major |

---

## Knight-Witness Role

The Knight monitors capacity governance for violations.

### Witness Types

| Type | Description |
|------|-------------|
| `capacity_overclaim` | Declared capacity exceeds actual availability |
| `silent_prioritization` | Work reordered without recorded justification |
| `deferral_concealment` | Deferral not recorded or made visible |
| `optimistic_declaration` | Pattern of declarations that don't match reality |
| `capacity_hoarding` | Declared scarcity when capacity exists |

### Detection Patterns

| Pattern | Detection Method |
|---------|------------------|
| Work proceeding without capacity | Execution events without matching declarations |
| Silent reordering | Execution sequence differs from recorded priority |
| Optimistic declarations | Declarations repeatedly revised downward |
| Repeated "temporary" deferrals | Same item deferred 3+ times |

---

## What Capacity Governance Does NOT Do

| Does Not | Why |
|----------|-----|
| Decide which motion is more important | That's politics |
| Allocate resources optimally | Optimization hides values |
| Enforce fairness | Fairness is subjective |
| Eliminate politics | Politics are inevitable |

**It simply ensures politics leave fingerprints.**

---

## Anti-Patterns to Watch

### Optimistic Capacity Theater

**Symptom:** Sources consistently over-declare capacity, then revise downward.

**Detection:** Pattern of declarations that don't match actual availability.

**Remedy:** Repeated optimistic declarations are witnessable violations.

### Scarcity as Leverage

**Symptom:** Capacity declared scarce to force prioritization of preferred work.

**Detection:** Idle capacity exists while scarcity is claimed.

**Remedy:** Idle capacity must be recorded; false scarcity is witnessable.

### Deferral Laundering

**Symptom:** Items deferred repeatedly under different reasons to reset count.

**Detection:** Same item deferred with different stated reasons.

**Remedy:** Deferral tracking follows item, not reason.

### Urgency Inflation

**Symptom:** Everything claimed as high priority to bypass capacity constraints.

**Detection:** High-priority claims exceed capacity consistently.

**Remedy:** High-priority work that cannot proceed becomes visible crisis.

---

## Schema Reference

See [schemas/capacity-ledger.json](./schemas/capacity-ledger.json) for the complete JSON Schema.

---

## Related Documents

- [Conclave Agenda Control](./conclave-agenda.md) - Where deferrals surface as agenda items
- [Legitimacy System](./legitimacy-system.md) - How capacity violations affect legitimacy
- [Aegis Network](./aegis-network.md) - Cluster capacity is primary source
- [Task Lifecycle](./task-lifecycle.md) - Where capacity is consumed
- [Enforcement Flow](./enforcement-flow.md) - Knight-Witness monitoring

