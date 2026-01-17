# The Aegis Network

> **The Aegis Network is a registry of human execution capacity, not a workforce to be commanded.**

## Overview

The Aegis Network is the human-in-the-loop execution layer of Archon 72. It is where work actually happens - outside the Archon system, under human judgment, with human accountability.

### What It Is (Operationally)

The Aegis Network is:
- A **registry of human execution capacity**
- **Grouped into Clusters**
- Each Cluster:
  - Has a domain focus
  - Has a human steward
  - Accepts tasks **voluntarily**
  - Reports results back into the system

Think of it as a **civil service + contractor mesh**, not a workforce.

### What It Is NOT

The Aegis Network is NOT:
- An automated execution engine
- A workforce that can be commanded
- A system where AI has authority over humans
- A way to bypass human consent

---

## Why This Architecture Exists

### The Problem It Solves

Most AI governance systems fail because they blur the line between **coordination** and **control**. This creates:

1. **Automation fantasy** - Pretending AI can execute real-world tasks
2. **Liability traps** - Unclear accountability when things go wrong
3. **Coercion risks** - Implicit pressure on humans to comply
4. **Silent failures** - No visibility into what's actually happening

### The Solution

By explicitly placing execution **outside** the Archon system boundary:

- **Humans remain in control** - They choose what to accept
- **Accountability is clear** - The Steward is responsible
- **Consent is explicit** - No silent assignment
- **Audit trails exist** - Every decision is logged

---

## The Cluster Model

### What Is a Cluster?

A Cluster is the **smallest unit where work happens** in the Aegis Network.

### Cluster Characteristics

| Attribute | Requirement |
|-----------|-------------|
| Size | 1-500 humans (5-50 recommended) |
| Leadership | One Cluster Steward (human) |
| Capabilities | Declared tags (research, dev, security, etc.) |
| Availability | Declared capacity and hours of operation |
| Participation | Opt-in only |

### Cluster Governance

Clusters are **not commanded**. They are **activated**.

This distinction is fundamental:
- **Command**: "You must do this task"
- **Activation**: "This task is available if you choose to accept it"

The asymmetry is intentional. Earls trigger work. Humans choose to do it.

---

## The Steward Role

### Who Is the Steward?

The Cluster Steward is the **human accountable operator** for the cluster. They are:
- The point of responsibility for all task decisions
- The gatekeeper for what the cluster accepts
- The attestor for results submitted back to Earls

### Steward Authority

The Steward may:
- Accept task activation requests
- Decline task activation requests
- Request clarification before deciding
- Delegate acceptance (via member_vote or hybrid methods)
- Attest to result accuracy and completeness

The Steward may NOT:
- Be bypassed by Earls or the system
- Be penalized for declining tasks
- Have their decisions overridden silently

### Steward Authorization Levels

| Level | May Accept |
|-------|------------|
| `standard` | Standard sensitivity tasks |
| `sensitive` | Standard + sensitive tasks |
| `restricted` | All task sensitivity levels |

---

## How Work Flows Through the Network

### Step 1: Task Authorization

A task is created upstream:
1. **President** creates the plan
2. **Duke** assigns to a program
3. **Earl** receives task for activation

At this point, the task is **authorized but dormant**.

### Step 2: Task Activation

The Earl emits a **Task Activation Request**:
- Task summary and human-readable description
- Constraints and success criteria
- Required capabilities
- Response deadline with dynamic backoff

This is **not an order**. It is a **call for participation**.

### Step 3: Cluster Matching

The system:
1. Matches task requirements to Cluster capabilities
2. Checks availability status
3. Routes to eligible Clusters

Cluster Stewards then decide:
- **Accept** - Begin execution
- **Decline** - Task remains available for other Clusters
- **Request clarification** - Need more information

**No silent assignment. No coercion.**

### Step 4: Human Execution

Humans do the work:
- Research, build, analyze, review, document
- **Outside** the Archon system
- In their own tools
- Under their own judgment
- With human accountability

This is critical for realism, ethics, and legal safety.

### Step 5: Result Submission

Clusters submit a **Task Result Artifact**:
- Status (completed, partial, failed, blocked)
- Deliverables with locations and checksums
- Issues encountered
- Steward attestation

**Failure is allowed. Silence is not.**

If they fail, they report:
- Failure
- Blockers
- Uncertainty

### Step 6: Earl Aggregation

The Earl:
- Aggregates cluster reports
- Updates task status
- Flags blockers if needed
- Forwards results to Duke

The Earl **does not judge quality**. They **report reality**.

### Step 7: Duke Integration

The Duke:
- Integrates task outcomes
- Updates program status
- Escalates issues to President if needed

Still no reinterpretation. Still no quiet fixes.

---

## Why This Works

This model:

| Benefit | How |
|---------|-----|
| Keeps humans in the loop | Explicit acceptance required |
| Prevents AI authority over people | Earls activate, not command |
| Prevents silent automation | All transitions logged |
| Preserves consent | Refusal is penalty-free |
| Creates audit trails | Steward attestation required |
| Allows refusal | Decline path is first-class |

And critically:

> **It makes Archon 72 a coordination system, not a control system.**

That distinction keeps you honest.

---

## Architectural Decision Record

### ADR: Aegis Network is External

**Status:** Accepted

**Context:** The Archon 72 system needs human execution capacity but must not have authority over humans or blur accountability.

**Decision:** The Aegis Network (Cluster registry, Steward interfaces, human execution environment) is **outside** the Archon 72 system boundary. Archon 72 emits activation requests and receives result artifacts. It does not manage Cluster internals.

**Consequences:**
- Clear system boundary for compliance and audit
- Cluster implementations can vary (different tooling, processes)
- Archon 72 cannot see inside Cluster execution (by design)
- Integration requires well-defined contracts (schemas)

---

## Related Documents

- [Cluster Schema](./cluster-schema.md) - Detailed schema and runtime rules
- [Task Activation Request](./task-activation-request.md) - Earl → Cluster contract
- [Task Result Artifact](./task-result-artifact.md) - Cluster → Earl contract
- [Enforcement Flow](./enforcement-flow.md) - Violation detection and handling

