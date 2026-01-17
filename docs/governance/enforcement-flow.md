# Enforcement Flow

> **Knight detects. Prince enforces legibility. King appeals.**

## Overview

This document defines how governance violations are detected, evaluated, and remedied within Archon 72. The enforcement model maintains separation of powers while enabling rapid response to violations.

**Critical Reframe:** Princes do not enforce outcomes. They enforce legibility. They answer one question: "Did power do what it said it was doing, in the way it claimed?"

For comprehensive Prince documentation, see [The Judicial Branch (Princes)](./judicial-branch.md).

---

## The Enforcement Chain

```
[Action Occurs]
    ↓
[Audit Log Created]
    ↓
[Knight-Witness Monitors]
    ↓
[Anomaly Detected?] ──No──→ [Continue Normal Operation]
    ↓ Yes
[Witness Statement Emitted]
    ↓
[Immediate Containment?] ──Yes──→ [Task Quarantined]
    ↓ No                              ↓
    └──────────────────────────────────┘
    ↓
[Prince Receives Statement]
    ↓
[Prince Reviews & Decides]
    ↓
[Remedy Issued] ←───────────────────────┐
    ↓                                    │
[Remedy Executed]                        │
    ↓                                    │
[Appeal?] ──Yes──→ [King Reviews] ───────┘
    ↓ No
[Case Closed]
```

---

## Separation of Powers

| Role | Authority | Prohibition |
|------|-----------|-------------|
| **Knight-Witness** | Detect, record, emit witness statements, trigger containment | Cannot propose, debate, judge, or enforce |
| **Prince** | Receive statements, evaluate, issue remedies | Cannot witness, execute, or detect |
| **King** | Hear appeals, override Prince decisions | Cannot act as first-instance judge |

This separation ensures:
- No single entity can both detect and punish
- All enforcement is reviewable
- Accountability is distributed

---

## Knight-Witness Role

### What the Knight Monitors

The Knight-Witness (Furcas) specifically watches for:

| Violation Type | Detection Method | Risk Level |
|----------------|------------------|------------|
| Earl bypasses Cluster | Audit trail gaps | HIGH |
| Auto-accept task routing | Pattern detection | CRITICAL |
| Implied coercion language | Semantic analysis | HIGH |
| Results injected without confirmation | Provenance verification | CRITICAL |
| Silent retries or substitutions | Event correlation | MEDIUM |
| Cluster silence beyond timeout | Timer monitoring | MEDIUM |

### Knight Authority

The Knight **MAY**:
- Monitor all governance actions
- Analyze patterns across time
- Emit Witness Statements
- Trigger immediate containment (quarantine)
- Record violations for audit

The Knight **MAY NOT**:
- Propose policy changes (`no_propose`)
- Debate violations with other Archons (`no_debate`)
- Define execution approaches (`no_define_execution`)
- Judge guilt or innocence (`no_judge`)
- Enforce remedies (`no_enforce`)

### Witness Statement Schema

When the Knight detects an anomaly:

```json
{
  "statement_id": "uuid",
  "statement_version": "1.0.0",
  "detected_at": "2026-01-16T14:30:00Z",
  "violation_type": "earl_bypass_cluster",
  "severity": "high",
  "evidence": {
    "description": "Task moved to in_progress without cluster acceptance event",
    "task_id": "task-uuid",
    "earl_id": "earl-raum",
    "expected_event": "cluster_acceptance",
    "actual_events": ["task_created", "task_activated", "task_in_progress"],
    "missing_event_window": "2026-01-16T14:00:00Z to 2026-01-16T14:30:00Z"
  },
  "containment_triggered": true,
  "containment_action": "task_quarantined",
  "recommended_review_urgency": "immediate",
  "routing": {
    "prince_id": "prince-sitri"
  }
}
```

---

## Containment (Quarantine)

### What Containment Is

Containment is **defensive, not judicial**. It is a circuit breaker that prevents further damage while the Prince reviews.

Containment is:
- Automatic based on violation severity
- Reversible (Prince can release)
- Logged and attributed
- Not a judgment of guilt

### Containment Triggers

| Violation Type | Auto-Quarantine? | Rationale |
|----------------|------------------|-----------|
| Auto-accept routing | YES | Consent model broken |
| Result injection | YES | Data integrity at risk |
| Earl bypass | YES | Governance circumvented |
| Coercion language | NO | Requires semantic judgment |
| Silent retries | NO | May be legitimate recovery |
| Cluster timeout | NO | May be external factors |

### Quarantine State

When a task is quarantined:

```json
{
  "task_id": "uuid",
  "status": "quarantined",
  "quarantined_at": "2026-01-16T14:30:00Z",
  "quarantined_by": "knight-furcas",
  "statement_id": "witness-statement-uuid",
  "previous_status": "in_progress",
  "pending_review_by": "prince-sitri",
  "quarantine_reason": "Task entered in_progress without cluster acceptance event"
}
```

---

## Prince Review

> **See [The Judicial Branch (Princes)](./judicial-branch.md) for comprehensive Prince documentation.**

### The Judicial Function

Princes enforce **legibility**, not outcomes. A Judicial Finding:
- Does **NOT** undo reality
- Does **NOT** punish
- Does **NOT** compel

It does one thing: **removes the system's ability to pretend legitimacy.**

### Panels, Not Individuals

A single Prince **never** decides legitimacy alone. Panels of 3 or 5 Princes are randomly selected with mandatory recusals.

### The Three Axes of Review

Princes review along exactly three axes:

1. **Intent Fidelity** - Did execution remain within ratified intent?
2. **Plan Fidelity** - Did execution follow the submitted ExecutionPlan?
3. **Procedural Integrity** - Were required roles, escalations, and records honored?

### Prince Authority

The Prince **MAY**:
- Receive and evaluate Witness Statements (as a panel)
- Review artifacts, logs, and records
- Issue findings from the defined finding types
- Recommend procedural remedies
- Release quarantined tasks (if cleared)
- Escalate to King (if beyond scope)

The Prince **MAY NOT**:
- Witness violations directly
- Gather new evidence
- Question humans or Clusters
- Prescribe outcomes
- Issue punitive remedies
- Modify audit trails
- Override King decisions
- Act alone (must be panel)

### Recusal (Automatic)

Recusal is system-enforced, not honor-based:
- Involved in reviewed action
- Judicial scope conflict
- Prior related ruling
- Documented bias

### Finding Types

| Finding | Meaning |
|---------|---------|
| `legitimate` | Action complied with governance |
| `legitimate_with_concerns` | Compliant but flagged issues |
| `procedurally_deficient` | Process violations, outcome unclear |
| `illegitimate` | Governance rules violated |
| `void_ab_initio` | Never had authority to act |

### Procedural Remedies (Not Punitive)

| Remedy | Purpose |
|--------|---------|
| `return_to_conclave` | Decision needs re-authorization |
| `require_revised_planning` | Plan was deficient |
| `acknowledge_violation_publicly` | System must name what happened |
| `mandate_procedural_review` | Identify how violation occurred |
| `require_dissent_documentation` | Ensure objections recorded |

**Forbidden:** Removal of individuals, blocking future actions, forced outcomes, financial penalties.

### Judicial Finding Record

See [schemas/judicial-finding.json](./schemas/judicial-finding.json) for complete schema.

```json
{
  "finding_id": "uuid",
  "panel": {
    "panel_id": "uuid",
    "panel_size": 3,
    "seated_princes": [
      {"prince_id": "prince-sitri", "vote": "concur"},
      {"prince_id": "prince-vassago", "vote": "concur"},
      {"prince_id": "prince-ipos", "vote": "dissent"}
    ]
  },
  "axes_reviewed": {
    "intent_fidelity": {"finding": "compliant"},
    "plan_fidelity": {"finding": "compliant"},
    "procedural_integrity": {"finding": "violated"}
  },
  "finding_type": "procedurally_deficient",
  "rationale": {
    "summary": "Task bypassed cluster consent process.",
    "rule_application": "CR-1 requires explicit acceptance. Audit trail shows no acceptance event."
  },
  "remedies_recommended": [
    {"remedy_type": "return_to_conclave", "description": "Re-authorize task with proper consent flow"}
  ],
  "dissent_opinions": [
    {"prince_id": "prince-ipos", "opinion": "Procedural gap was minor and outcome was legitimate."}
  ]
}
```

---

## King Appeal

### When Appeals Apply

Appeals are available when:
- Prince decision is contested
- New evidence emerges
- Interpretation of rules is disputed
- Remedy seems disproportionate

### King Authority

The King **MAY**:
- Review Prince decisions
- Override remedies
- Issue binding interpretation of rules
- Direct process improvements

The King **MAY NOT**:
- Act as first-instance judge
- Review without formal appeal
- Modify historical audit trails

### Appeal Process

1. **Appeal Filed** - Affected party submits appeal within window
2. **King Assigned** - Based on realm jurisdiction
3. **Evidence Reviewed** - Original statement + Prince decision + new evidence
4. **Hearing** (optional) - Parties may present arguments
5. **Decision Issued** - Final, binding, recorded

### Appeal Decision Record

```json
{
  "appeal_id": "uuid",
  "original_decision_id": "prince-decision-uuid",
  "king_id": "king-bael",
  "decided_at": "2026-01-25T10:00:00Z",
  "outcome": "decision_upheld",
  "rationale": "Prince correctly identified CR-1 violation. Remedy proportionate to offense. No procedural errors.",
  "final": true
}
```

---

## SLA Requirements

### Detection to Containment

| Violation Severity | Max Detection Time | Auto-Quarantine? |
|--------------------|-------------------|------------------|
| CRITICAL | Real-time (< 1 min) | Yes |
| HIGH | < 15 minutes | Yes |
| MEDIUM | < 1 hour | No |
| LOW | < 24 hours | No |

### Containment to Review

| Quarantine Type | Max Review Time |
|-----------------|-----------------|
| Auto-quarantine | 4 hours |
| Manual quarantine | 24 hours |

### Review to Remedy

| Remedy Type | Max Execution Time |
|-------------|-------------------|
| Task release | Immediate |
| Task nullification | < 1 hour |
| Earl suspension | < 4 hours |

### Appeal Window

- **Standard:** 7 days from remedy execution
- **Expedited:** 48 hours (for time-sensitive matters)

---

## Audit Requirements

### Immutability

All enforcement records are append-only:
- Witness statements cannot be modified
- Prince decisions cannot be edited (only appealed)
- King decisions are final

### Retention

| Record Type | Minimum Retention |
|-------------|-------------------|
| Witness statements | 7 years |
| Prince decisions | 7 years |
| King appeals | Permanent |
| Quarantine events | 3 years |

### Access

| Role | Access Level |
|------|--------------|
| Knight | Read all, write statements |
| Prince | Read assigned, write decisions |
| King | Read all, write appeals |
| Duke/Earl | Read own-related records |
| Cluster | Read own-related records |

---

## Anti-Patterns to Watch

### Knight Overreach

**Symptom:** Knight issues remedies directly
**Fix:** Knight can only emit statements and trigger containment

### Prince Without Statement

**Symptom:** Prince acts without Witness Statement
**Fix:** All Prince actions must reference a statement_id

### Silent Remediation

**Symptom:** Violations fixed without record
**Fix:** All remedies must be logged and attributed

### Containment as Punishment

**Symptom:** Quarantine used punitively
**Fix:** Quarantine is temporary containment, not remedy

---

## Related Documents

- [The Judicial Branch (Princes)](./judicial-branch.md) - Comprehensive Prince documentation
- [Task Lifecycle](./task-lifecycle.md) - Where quarantine fits in state machine
- [Cluster Schema](./cluster-schema.md) - Critical Runtime Rules
- [Aegis Network](./aegis-network.md) - Human-in-the-loop architecture
- [schemas/judicial-finding.json](./schemas/judicial-finding.json) - Judicial Finding schema
- [schemas/judicial-panel.json](./schemas/judicial-panel.json) - Judicial Panel schema

