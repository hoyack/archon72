# Task Lifecycle

> **Every task has a state. Every transition is logged. No task disappears.**

## Overview

This document defines the 10 states a task moves through in the Archon 72 governance system, from authorization through completion (or nullification).

---

## State Machine

```
                                    ┌─────────────────────────────────────┐
                                    │                                     │
                                    ▼                                     │
┌──────────┐    ┌───────────┐    ┌────────┐    ┌──────────┐    ┌─────────────┐
│authorized│───▶│ activated │───▶│ routed │───▶│ accepted │───▶│ in_progress │
└──────────┘    └───────────┘    └────────┘    └──────────┘    └─────────────┘
                                    │                               │
                                    │                               │
                                    ▼                               ▼
                               ┌──────────┐                   ┌──────────┐
                               │ declined │                   │ reported │
                               └──────────┘                   └──────────┘
                                                                   │
                                                                   │
                    ┌──────────────┐                               ▼
                    │ quarantined  │◀─────────────────────── ┌────────────┐
                    └──────────────┘                         │ aggregated │
                           │                                 └────────────┘
                           │                                       │
                           ▼                                       │
                    ┌───────────┐                                  ▼
                    │ nullified │                            ┌───────────┐
                    └───────────┘                            │ completed │
                                                             └───────────┘
```

---

## State Definitions

### 1. `authorized`

**Definition:** Task exists in the governance system but has not been activated.

**Entry Conditions:**
- President creates plan containing task
- Duke assigns task to program
- Earl receives task delegation

**Exit Conditions:**
- Earl issues Task Activation Request → `activated`

**Who Can Transition:** Earl (via activation)

**Audit Requirements:**
- Task creation timestamp
- Authorization chain (President → Duke → Earl)

---

### 2. `activated`

**Definition:** Earl has issued a Task Activation Request. The task is now seeking a Cluster.

**Entry Conditions:**
- Earl emits valid Task Activation Request

**Exit Conditions:**
- Request routed to eligible Clusters → `routed`
- No eligible Clusters found → remains `activated` (retry with different constraints)

**Who Can Transition:** System (routing engine)

**Audit Requirements:**
- Activation Request ID
- Issuing Earl
- Timestamp

---

### 3. `routed`

**Definition:** Task has been sent to one or more eligible Clusters for consideration.

**Entry Conditions:**
- System matches task to Cluster capabilities
- At least one eligible Cluster identified

**Exit Conditions:**
- Cluster Steward accepts → `accepted`
- All Clusters decline → `declined`
- Response timeout exceeded → escalate to Knight-Witness

**Who Can Transition:** Cluster Steward (accept/decline)

**Audit Requirements:**
- Clusters routed to
- Routing timestamp
- Capability match score (optional)

---

### 4. `accepted`

**Definition:** A Cluster Steward has explicitly accepted the task.

**Entry Conditions:**
- Steward acceptance recorded (CR-1 compliance)
- Acceptance method completed (steward_accepts, member_vote, or hybrid)

**Exit Conditions:**
- Cluster begins work → `in_progress`

**Who Can Transition:** Cluster (by starting work)

**Audit Requirements:**
- Acceptance event with timestamp
- Steward ID
- Acceptance method used

**Critical Rule:** Task CANNOT move to `in_progress` without this state (CR-1: No silent assignment)

---

### 5. `declined`

**Definition:** All eligible Clusters have declined the task.

**Entry Conditions:**
- All routed Clusters explicitly decline
- OR timeout exceeded with no acceptances

**Exit Conditions:**
- Earl modifies constraints and re-activates → `activated`
- Earl escalates to Duke → remains `declined` (task needs redesign)
- Task abandoned → terminal state

**Who Can Transition:** Earl (re-activation), Duke (escalation)

**Audit Requirements:**
- Decline events from each Cluster
- Decline reasons (optional)

**Critical Rule:** Declining CANNOT penalize Clusters (CR-2: Refusal is penalty-free)

---

### 6. `in_progress`

**Definition:** Cluster is actively executing the task.

**Entry Conditions:**
- Task previously `accepted`
- Cluster has begun work

**Exit Conditions:**
- Cluster submits result → `reported`
- Knight-Witness detects violation → `quarantined`

**Who Can Transition:** Cluster (via result submission), Knight (via quarantine)

**Audit Requirements:**
- Work start timestamp
- Cluster ID
- Steward ID

---

### 7. `reported`

**Definition:** Cluster has submitted a Task Result Artifact.

**Entry Conditions:**
- Cluster submits valid Task Result Artifact
- Steward attestation present

**Exit Conditions:**
- Earl aggregates result → `aggregated`
- Knight-Witness detects violation in result → `quarantined`

**Who Can Transition:** Earl (aggregation), Knight (quarantine)

**Audit Requirements:**
- Result Artifact ID
- Submission timestamp
- Steward attestation

---

### 8. `aggregated`

**Definition:** Earl has processed the result and integrated it into task status.

**Entry Conditions:**
- Earl validates result artifact
- Earl updates task status based on result

**Exit Conditions:**
- Task successful → `completed`
- Task failed/blocked → Earl handles (escalate, retry, etc.)
- Knight-Witness detects late violation → `quarantined`

**Who Can Transition:** Earl (completion), Duke (integration), Knight (quarantine)

**Audit Requirements:**
- Aggregation timestamp
- Earl ID
- Integrated status

---

### 9. `quarantined`

**Definition:** Task has been suspended pending governance review.

**Entry Conditions:**
- Knight-Witness detects violation
- Containment triggered (automatic or manual)

**Exit Conditions:**
- Prince releases task → previous state (with modifications)
- Prince nullifies task → `nullified`

**Who Can Transition:** Prince (via remedy)

**Audit Requirements:**
- Witness Statement ID
- Quarantine timestamp
- Previous state (for restoration)
- Pending reviewer (Prince ID)

**Critical Rule:** Quarantine is containment, not punishment. It is reversible.

---

### 10. `nullified`

**Definition:** Task has been voided by governance action. Terminal state.

**Entry Conditions:**
- Prince issues `task_nullified` remedy
- King upholds nullification on appeal

**Exit Conditions:**
- None (terminal state)

**Who Can Transition:** None (final)

**Audit Requirements:**
- Prince Decision ID
- Nullification timestamp
- Rationale
- Appeal status (if applicable)

---

### 11. `completed`

**Definition:** Task has been successfully executed and integrated. Terminal state.

**Entry Conditions:**
- Earl aggregates successful result
- Duke integrates into program
- No outstanding violations

**Exit Conditions:**
- None (terminal state)

**Who Can Transition:** None (final)

**Audit Requirements:**
- Completion timestamp
- Final deliverables
- Effort summary (optional)

---

## State Transition Matrix

| From State | To State | Trigger | Actor |
|------------|----------|---------|-------|
| `authorized` | `activated` | Earl issues activation request | Earl |
| `activated` | `routed` | System matches to Clusters | System |
| `routed` | `accepted` | Steward accepts | Cluster |
| `routed` | `declined` | All Stewards decline | Clusters |
| `declined` | `activated` | Earl re-activates with changes | Earl |
| `accepted` | `in_progress` | Cluster begins work | Cluster |
| `in_progress` | `reported` | Cluster submits result | Cluster |
| `in_progress` | `quarantined` | Knight detects violation | Knight |
| `reported` | `aggregated` | Earl processes result | Earl |
| `reported` | `quarantined` | Knight detects violation | Knight |
| `aggregated` | `completed` | Task successful | Earl/Duke |
| `aggregated` | `quarantined` | Knight detects late violation | Knight |
| `quarantined` | (previous) | Prince releases | Prince |
| `quarantined` | `nullified` | Prince nullifies | Prince |

---

## Invalid Transitions

These transitions are **forbidden** and indicate governance violations:

| Invalid Transition | Violation |
|--------------------|-----------|
| `authorized` → `in_progress` | Bypassed activation and acceptance |
| `activated` → `in_progress` | Bypassed routing and acceptance |
| `routed` → `in_progress` | Bypassed explicit acceptance (CR-1) |
| `declined` → `in_progress` | Forced work after refusal (CR-2) |
| `quarantined` → `completed` | Bypassed Prince review |
| `nullified` → any | Resurrected voided task |

The Knight-Witness monitors for these invalid transitions.

---

## Timeout Handling

| State | Timeout | Action |
|-------|---------|--------|
| `activated` | 24h with no routing | Alert Earl |
| `routed` | Per `response_policy` | Escalate to Knight |
| `accepted` | 48h with no progress | Alert Steward |
| `in_progress` | Per task deadline | Alert Cluster + Earl |
| `reported` | 24h with no aggregation | Alert Earl |
| `quarantined` | Per SLA (4h auto, 24h manual) | Escalate to King |

---

## Visualization

For real-time task state visualization:

```
Task: abc-123
State: in_progress [████████░░] 80%
Cluster: Aegis Cluster 17
Steward: Cluster Steward 17
Started: 2026-01-17T09:00:00Z
Deadline: 2026-01-20T17:00:00Z

History:
  authorized  → activated   (Earl Raum, 2026-01-16T14:00:00Z)
  activated   → routed      (System, 2026-01-16T14:05:00Z)
  routed      → accepted    (Steward 17, 2026-01-16T15:30:00Z)
  accepted    → in_progress (Cluster 17, 2026-01-17T09:00:00Z)
```

---

## Related Documents

- [Task Activation Request](./task-activation-request.md) - How tasks are activated
- [Task Result Artifact](./task-result-artifact.md) - How results are reported
- [Enforcement Flow](./enforcement-flow.md) - How quarantine works
- [Cluster Schema](./cluster-schema.md) - Who executes tasks

