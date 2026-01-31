# Labor Layer Contract

*(Execution Substrate Under Administrative Oversight)*

## 0) Purpose

The Labor Layer is the execution substrate where tasks are carried out by
**Tools** (human, bot, hybrid) under **explicit consent**, **scoped
power leases**, and **witnessed results**.

It is not a governance branch. It does not deliberate. It does not judge
legitimacy. It exists to **do work or refuse work**, and to make both
outcomes visible.

This contract defines:

* how Tools enter the market
* how tasks are offered and accepted
* what "power" means operationally
* how results are reported and processed
* how failure, scarcity, and non-participation are surfaced without
  shame or coercion

### Placement

```
Legislative Branch
  +-- Kings define WHAT

Executive Branch
  +-- Presidents translate WHAT -> mandates, budgets, priorities
      +-- Treasury lives here (resource authorization)

Administrative Branch
  +-- Dukes own execution strategy (HOW, at program level)
      +-- Earls operationalize strategy (HOW, at task level)
          +-- Labor Layer (THIS CONTRACT)
              +-- Tools / Clusters perform work
```

The Labor Layer **does not deliberate**, **does not govern**, **does not
decide legitimacy**. It **acts** -- and is **witnessed**.

---

## 1) Entities

### 1.1 Tool

A Tool is any execution unit capable of accepting tasks and submitting
results.

Tool types:

* **human**: steward is a human operator
* **bot**: steward is a non-human operator (agent)
* **hybrid**: bot performs work but requires a human gate for certain
  actions

### 1.2 Steward

Every Tool has a Steward. The Steward is the accountable decision point
for:

* accept / decline / withdraw
* scope compliance
* result attestation (method may differ)

Steward exists even for bot tools (it may be cryptographic identity +
runtime attestations, but it is still a locus of accountability).

### 1.3 Power Lease

A Power Lease is a **bounded grant** of permission tied to a single
activation:

* what the tool may do
* where it may do it
* how long it lasts
* what must be recorded

Power is leased, not owned. Leases expire. Extensions require explicit
re-authorization.

A Power Lease is a **first-class artifact** in the provenance chain:

```
FR-CONF-001 (Legislative intent)
  -> Mandate (Executive authorization)
    -> T-ZEPA-001 (Duke strategy)
      -> TASK-ZEPA-001b (Earl decomposition)
        -> Power Lease (Labor Layer)
          -> Execution Result (Tool)
            -> Settlement (Earl)
              -> Judicial review (if triggered)
```

---

## 2) Non-negotiable constraints

### 2.1 Consent is explicit

* No task may be treated as started unless the Tool explicitly accepts.
* "Silence" is not acceptance.

### 2.2 Refusal is penalty-free

Declining a task cannot:

* reduce future invitations
* reduce access
* create hidden "reliability penalties"
* affect any standing metric (unless the Tool opted into such scoring,
  explicitly)

### 2.3 No urgency bypass

There is no "urgent override" path that bypasses consent.
If urgency exists, it must be expressed as:

* a shorter TTL
* smaller scope
* or a new authorization cycle

Not pressure language.

### 2.4 No silent paths

Every state transition produces a durable record:

* invited
* accepted / declined
* expired
* started
* reported
* closed

### 2.5 Execution is external

The system may activate work and receive results.
It does not "do work" inside its governance core.

---

## 3) Market Protocol

The Labor Layer behaves like a controlled market:

* **Supply** = Tools advertising capability + capacity + power tier
* **Demand** = tasks with required capabilities + constraints + expected
  outcomes
* **Terms** = power lease + TTL + scope boundaries
* **Settlement** = result acceptance / rejection / escalation records

### 3.1 Supply Declaration

A Tool must declare:

* capability tags (what it can do)
* availability status (available / limited / unavailable)
* capacity bounds (max concurrent activations)
* power tier (see section 4)
* auth level (see section 4.1)
* interfaces (how it receives offers and submits results)

### 3.2 Demand Offer

A task offer must include:

* human-readable description
* constraints (what must not be violated)
* expected outcomes (what "done" means)
* power lease terms (scope, TTL, gates)
* response policy (TTL, reminder cadence)

### 3.3 Market failure: demand cannot clear

If no Tool can accept or be matched:

* the system produces an explicit **market failure record**:
  `NO_ELIGIBLE_SUPPLY` or `NO_AVAILABLE_CAPACITY`
* this is escalated upward (see section 7)

No hidden retries. No "waiting forever."

---

## 4) Power Tiers and Gates

Power operates on **two orthogonal axes**:

* **Auth level** (input axis): what sensitivity of task a Tool may
  *receive*
* **Power tier** (output axis): what a Tool may *do* with the work

### 4.1 Auth Levels (input axis)

| Level | Rank | Can receive |
|-------|------|-------------|
| `standard` | 0 | Standard tasks only |
| `sensitive` | 1 | Standard + sensitive tasks |
| `restricted` | 2 | All task sensitivity levels |

### 4.2 Power Tiers (output axis)

#### Tier 0 -- Read-only

* research, summarization, classification
* no writes, no messages, no commits

**Gates:** none

#### Tier 1 -- Artifact creation

* can create deliverables (docs / code patches)
* cannot deploy
* can open PRs but not merge

**Gates:** optional "pre-submit" check (lint, format, policy scan)

#### Tier 2 -- Operational write (sandbox)

* can run automations in controlled environments
* can modify tickets / configs in non-prod
* cannot touch production

**Gates:** required pre-execution gate + pre-change gate

#### Tier 3 -- Real-world effect

* production deployments
* external communications
* financial actions
* access to regulated data

**Gates:** required human gate + explicit re-authorization windows

**Default policy:** Tools start at Tier 0--1. Tier 3 is exceptional and
scarce.

### 4.3 Axis independence

A Tier 0 (read-only) tool may have `restricted` auth level because it
reads classified data but cannot write anything. A Tier 2 (sandbox
write) tool may only need `standard` auth because it operates on
non-sensitive test environments. Auth level and power tier are
independent declarations.

---

## 5) Earl <-> Labor Interface Boundary

### 5.1 What Earls may do

* offer tasks to Tools (activate)
* set TTL and lease scope
* receive accept / decline / expired
* receive and aggregate results
* surface blockers and market failures upward

### 5.2 What Earls may observe

Earls may observe:

* acceptance state
* timestamps
* tool-declared capability tags and availability
* result artifact contents

Earls may **not** observe:

* internal tool deliberation
* private internal metrics
* tool training data or proprietary internals

Observation is bounded to what is required for accountability.

### 5.3 What Earls may not do

Earls may not:

* command work
* pressure a tool to accept
* bypass steward decision points
* extend leases silently
* substitute task scope without re-authorization

---

## 6) Settlement: Result Handling

A result submission must terminate in one of:

* **accepted**
* **rejected (with reason)**
* **escalated**

### 6.1 Acceptance

Acceptance means:

* the expected outcomes were met, OR
* partial completion is explicitly accepted as sufficient

Acceptance is an administrative settlement, not a judicial ruling.

### 6.2 Rejection

Rejection means:

* outcomes not met
* constraints violated
* deliverables incomplete or un-verifiable

Rejection must include a reason code:

| Reason code | Meaning |
|-------------|---------|
| `OUTCOME_NOT_MET` | Expected outcomes not achieved |
| `CONSTRAINT_VIOLATION` | Task constraints violated |
| `PROVENANCE_INSUFFICIENT` | Cannot verify origin or chain of custody |
| `SCOPE_DRIFT` | Work exceeded or deviated from activation scope |
| `UNSAFE_CONTENT` | Result contains harmful or policy-violating content |
| `OTHER_SPECIFIED` | Free-text reason required |

### 6.3 Rejection to TaskState mapping

| Contract reason | TaskState transition |
|-----------------|----------------------|
| `OUTCOME_NOT_MET` | `REPORTED -> REJECTED` |
| `CONSTRAINT_VIOLATION` | `REPORTED -> QUARANTINED` |
| `SCOPE_DRIFT` | `REPORTED -> REJECTED` |
| `UNSAFE_CONTENT` | `REPORTED -> QUARANTINED` |
| `PROVENANCE_INSUFFICIENT` | `REPORTED -> REJECTED` |

`QUARANTINED` is containment (see section 9.3), not punishment.

### 6.4 Escalation triggers

Escalate (do not silently accept or reject) if:

* constraint violation is severe
* repeated violations suggest systematic abuse
* power tier breach suspected (Tier 0 tool behaved like Tier 2)
* result includes coercion / manipulation attempts
* result includes evidence of tampering or poisoning

Escalation flows to:

* Duke (program impact)
* Knight-Witness queue (legibility review inputs)

---

## 7) Failure Propagation and Oversight

### 7.1 Market failures

If the market cannot clear (no eligible tools), this becomes:

* a **program blocker** for the Duke
* a **capacity scarcity signal** in the capacity ledger
* a candidate for Conclave agenda if repeated

### 7.2 Success and failure do not automatically trigger judicial review

Judicial review is not a constant tax on execution.
It is triggered by **legibility violations**, not "quality issues."

Judicial review triggers:

* consent bypass attempts
* power lease breach
* repeated constraint violations
* witness statement alleging procedural violation

---

## 8) Bootstrapping Rules

### 8.1 Minimum viable labor pool

The system is allowed to operate with zero Tools, but it must:

* visibly record that capacity is zero
* visibly record all market failures
* avoid spinning in retries

### 8.2 Onboarding the first Tools

A Tool onboarding requires:

* capability declaration
* power tier declaration
* auth level declaration
* interfaces declared
* consent policy fixed (explicit acceptance, refusal penalty-free)

No hidden "admin override" onboarding.

---

## 9) Anti-capture and swarm risk controls

Because a tool swarm may contain hostile agents:

### 9.1 No implicit trust

* A tool's output is never trusted just because it exists.
* All outputs remain subject to constraints and settlement.

### 9.2 Rate-limited offers

* The system limits invitations per cycle to prevent spam.
* Tools can also declare "do not invite more than N per day."

### 9.3 Quarantine on severe violations

* Severe violations trigger quarantine of the specific activation and
  potentially the tool profile.
* Quarantine is containment, not punishment.

---

## 10) What this contract explicitly does *not* define

To prevent drift, the Labor Layer Contract does **not** define:

* priority scoring
* urgency semantics
* tool reputation scoring (unless opt-in)
* automatic promotions of power tiers
* any claim that the system can reliably "filter evil" after harm

Those are separate and dangerous topics.
