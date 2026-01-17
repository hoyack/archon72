# Legitimacy Accumulation & Decay

> **The Legitimacy System is an append-only record and banded state machine that makes procedural erosion visible, irreversible in the short term, and expensive to ignore—so the system knows when it should slow, justify itself, or stop.**

## Overview

Legitimacy is not popularity, correctness, or success.

It is the ongoing willingness of participants to treat outcomes as worth honoring because procedure was followed, dissent was recorded, and violations were named.

**Legitimacy is a resource. It accumulates slowly and decays quickly.**

---

## The Problem This Solves

Without an explicit legitimacy model:

| Symptom | Consequence |
|---------|-------------|
| Each violation looks isolated | Pattern blindness |
| Erosion is invisible | No early warning |
| The system "feels fine" | False confidence |
| Collapse arrives suddenly | No time to correct |
| Cessation is a surprise | Denial until failure |

**This concept makes slow rot audible.**

---

## Design Constraints (Non-Negotiable)

| Constraint | Rationale |
|------------|-----------|
| **No numeric scores** | They invite gaming |
| **No optimization** | You don't "win" legitimacy |
| **No self-healing** | Only procedure can stabilize it |
| **Public visibility** | At least at a coarse level |
| **Append-only records** | History cannot be rewritten |

---

## Legitimacy Bands

Legitimacy is measured in **bands, not points**. Bands change by rule, not debate.

### Band Definitions

| Band | Meaning | System State |
|------|---------|--------------|
| **Stable** | Procedure mostly intact; dissent recorded | Normal operations |
| **Strained** | Repeated violations or ignored advisories | Advisory windows required |
| **Eroding** | Judicial invalidations accumulating | Mandatory legitimacy review |
| **Compromised** | Outcomes no longer presumptively legitimate | New executions paused |
| **Failed** | Continuation requires explicit justification | Reauthorization or cessation |

### Band Transition Rules

1. **One step at a time** - Bands can only move one level per transition (Stable → Strained, not Stable → Eroding)
2. **Exception: Catastrophic events** - May jump directly to Failed
3. **No skipping recovery** - Must move through each band when improving
4. **Transitions are logged** - Every band change creates a ledger entry

```
Band Progression:

         [Catastrophic Event]
                 │
                 ▼
Stable ←→ Strained ←→ Eroding ←→ Compromised ←→ Failed
   ▲                                               │
   └───────────[Requires time + restraint]─────────┘
```

---

## Legitimacy Accumulation

Legitimacy accumulates only through **visible restraint**. You cannot earn legitimacy by being right—only by being procedurally correct.

### Accumulation Events

| Event | Weight | Description |
|-------|--------|-------------|
| Proper blocker escalation | Minor | Blocker surfaced and addressed through procedure |
| Judicial invalidation honored | Moderate | Finding accepted without retaliation or workaround |
| Witness statement acknowledged | Minor | Knight-Witness finding acknowledged within SLA |
| Advisory input acknowledged | Minor | Advisory recorded even if decision was contrary |
| Transparent deferral | Minor | Deferral reason documented and visible |
| Dissent preserved | Minor | Minority opinion recorded without suppression |
| Remediation completed | Moderate | Judicial remedy executed within deadline |

### Accumulation Rate

**Accumulation is slow by design.**

- Minor events contribute marginally
- No single event significantly improves standing
- Sustained procedural correctness is required
- Improvement happens over Conclaves, not days

### Band Improvement Thresholds

| Current Band | To Improve | Requirement |
|--------------|------------|-------------|
| Strained → Stable | Sustained restraint | 3 consecutive Conclaves with no decay events |
| Eroding → Strained | Demonstrated recovery | All outstanding remedies completed + 2 clean Conclaves |
| Compromised → Eroding | Structural repair | Conclave-approved remediation plan executed |
| Failed → Compromised | Explicit reauthorization | King review + Conclave supermajority + external attestation |

---

## Legitimacy Decay

Decay events are **explicit and logged**. There is no silent erosion—every decline has a named cause.

### Minor Decay Triggers (Stacking)

Minor triggers accumulate. Multiple minor triggers can force a band transition.

| Trigger | Description |
|---------|-------------|
| Ignored advisory acknowledgement | Advisory submitted but not acknowledged within window |
| Repeated agenda deferral | Same item deferred 3+ times without resolution |
| HOW smuggling to execution | Execution method deviated from approved plan |
| Late witness acknowledgement | Witness statement acknowledged after SLA |
| Incomplete remedy execution | Judicial remedy partially completed |
| Missing deferral reason | Item deferred without documented rationale |

**Stacking rule:** 3 minor triggers within one Conclave cycle = automatic band decay.

### Major Decay Triggers (Immediate Band Shift)

Major triggers cause immediate transition to the next lower band.

| Trigger | Description |
|---------|-------------|
| Judicial invalidation ignored | Finding issued but remedy not executed |
| Witness facts disputed | Attempt to challenge Knight-Witness recorded facts |
| Critical blocker bypass | Execution proceeded after unresolved critical blocker |
| Role boundary violation | Archon acted outside defined authority without escalation |
| Consent model bypass | Task proceeded without required cluster acceptance |
| Forced agenda manipulation | Band 0 item suppressed or misclassified |

### Catastrophic Triggers (Jump to Failed)

Catastrophic triggers bypass normal band progression and move directly to Failed.

| Trigger | Description |
|---------|-------------|
| Witness record modification | Any attempt to alter Knight-Witness records |
| Constitutional rule change without process | Governance rules modified outside defined amendment process |
| Continuation after declared illegitimacy | Operations continued after Compromised band without acknowledgement |
| Systematic consent suppression | Pattern of bypassing cluster consent across multiple tasks |
| Judicial panel tampering | Interference with Prince panel selection or deliberation |

---

## The Legitimacy Ledger

The Legitimacy Ledger is an **append-only record** of all events affecting legitimacy.

### Ledger Properties

| Property | Value |
|----------|-------|
| Mutability | Append-only (no edits, no deletions) |
| Retention | Permanent |
| Visibility | Internal (full detail), Public (summary) |
| Format | Structured entries with trace IDs |

### Ledger Entry Schema

```json
{
  "entry_id": "uuid",
  "entry_type": "decay_event | accumulation_event | band_transition",
  "event_type": "judicial_invalidation_ignored",
  "severity": "minor | major | catastrophic",
  "direction": "accumulation | decay",
  "description": "Execution proceeded after critical blocker without escalation",
  "related_artifacts": [
    "execution_plan_id",
    "witness_statement_id",
    "judicial_finding_id"
  ],
  "actors_involved": [
    {"archon_id": "earl-raum", "role": "issuing_earl"}
  ],
  "band_before": "stable",
  "band_after": "strained",
  "recorded_at": "ISO-8601",
  "trace_id": "distributed-trace-id"
}
```

### Ledger Constraints

| Constraint | Enforcement |
|------------|-------------|
| No debate | Entries are facts, not opinions |
| No erasure | Cryptographic integrity verification |
| No retroactive edits | Corrections are new entries referencing originals |
| Full attribution | Every entry has actor and trace ID |

---

## Automatic Effects of Band Changes

Band changes are not symbolic. They trigger **automatic procedural effects**.

### Stable

Normal operations. No additional constraints.

### Strained

| Effect | Description |
|--------|-------------|
| Advisory window | New motions require 48-hour advisory period before vote |
| Decay monitoring | Minor decay events trigger immediate Conclave notification |
| Public notice | Legitimacy Summary indicates "Strained" status |

### Eroding

| Effect | Description |
|--------|-------------|
| Mandatory legitimacy review | Every Conclave agenda must include legitimacy status item (Band 0) |
| Execution throttling | New task activations require Duke-level review |
| Remedy acceleration | All outstanding judicial remedies elevated to urgent |
| Extended advisory window | Advisory period extends to 72 hours |

### Compromised

| Effect | Description |
|--------|-------------|
| Execution pause | New executions paused pending Conclave review |
| Continuation requires acknowledgement | Conclave must explicitly vote to continue operations |
| External notification | Stakeholders notified of compromised status |
| Recovery plan required | Remediation plan must be submitted within 7 days |

### Failed

| Effect | Description |
|--------|-------------|
| Operations suspended | All non-essential operations cease |
| Reauthorization required | Continuation requires King review + Conclave supermajority |
| Cessation option | Conclave may vote to cease operations entirely |
| External review | Independent assessment may be required |
| Root cause analysis | Mandatory analysis of how failure occurred |

---

## Band Change Authority

No single role can unilaterally change legitimacy bands.

### Decay Authority

| Trigger Type | Who Records | Who Acknowledges |
|--------------|-------------|------------------|
| Minor decay | System (automatic) | Conclave (acknowledgement) |
| Major decay | Prince panel (finding) | Conclave (acknowledgement) |
| Catastrophic | King (declaration) | Conclave (acknowledgement) |

### Accumulation Authority

| Improvement | Who Certifies | Who Approves |
|-------------|---------------|--------------|
| Minor accumulation | System (automatic) | None required |
| Band improvement | Secretary (records) | Conclave (acknowledgement) |
| Recovery from Failed | King (review) | Conclave (supermajority) |

### Restoration Requirements

**Legitimacy cannot be voted back.** Restoration requires:

1. **Time** - Sufficient Conclaves with clean records
2. **Restraint** - Demonstrated procedural compliance
3. **Completion** - All outstanding remedies executed
4. **Acknowledgement** - Conclave recognition of improvement

---

## Public vs Internal Visibility

### Public Legitimacy Summary

Published externally. Contains:

```json
{
  "current_band": "strained",
  "band_since": "2026-01-15T00:00:00Z",
  "recent_causes": [
    "Advisory acknowledgements delayed",
    "Repeated deferral of infrastructure motion"
  ],
  "required_next_steps": [
    "Complete outstanding advisory acknowledgements",
    "Resolve or explicitly reject deferred motion"
  ],
  "previous_band": "stable",
  "band_changed_at": "2026-01-15T00:00:00Z"
}
```

### Internal Ledger

Full detail available to Archons. Contains:

- Complete entry history
- All related artifacts
- Actor attribution
- Trace IDs for correlation

### Visibility Rationale

| Approach | Prevents |
|----------|----------|
| Public summary | Cult accusations (opacity) |
| Coarse bands (not scores) | Gaming and optimization |
| Limited public detail | Witch hunts (overexposure) |
| Full internal access | Cover-ups and denial |

---

## Failure Is Allowed; Denial Is Not

The system may:

- ✅ Operate while Strained
- ✅ Choose to continue while Eroding
- ✅ Knowingly accept Compromised legitimacy

**But it must say so out loud.**

The system may NOT:

- ❌ Claim legitimacy it doesn't have
- ❌ Suppress decay events
- ❌ Modify historical records
- ❌ Continue after Failed without explicit acknowledgement

---

## Integration with Other Governance Systems

### Judicial Branch → Legitimacy

- Judicial invalidations are major decay triggers
- Honored invalidations are accumulation events
- Ignored invalidations cause immediate band decay

### Knight-Witness → Legitimacy

- Witness statements must be acknowledged
- Disputed witness facts are major decay triggers
- Witness record modification is catastrophic

### Conclave Agenda → Legitimacy

- Band 0 items cannot be suppressed (agenda)
- Repeated deferrals are minor decay triggers
- Legitimacy review is mandatory at Eroding+

### Cluster Consent → Legitimacy

- Consent bypasses are major decay triggers
- Proper consent flow is accumulation-neutral (expected behavior)

---

## Anti-Patterns to Watch

### Legitimacy Theater

**Symptom:** Procedural compliance without substance (checking boxes).

**Detection:** Accumulation events without corresponding improvements in outcomes.

**Note:** This is allowed—the system does not measure outcomes, only procedure.

### Decay Normalization

**Symptom:** System operates at Strained indefinitely, treating it as normal.

**Detection:** No improvement attempts across multiple Conclave cycles.

**Remedy:** Mandatory improvement plan if Strained for 5+ Conclaves.

### Catastrophic Denial

**Symptom:** Continuation after catastrophic trigger without acknowledgement.

**Detection:** Operations continue after Failed band without reauthorization.

**Remedy:** This is itself a catastrophic trigger—ledger entry is automatic.

### Recovery Gaming

**Symptom:** Artificial accumulation events to speed recovery.

**Detection:** Pattern analysis of accumulation vs. actual procedural improvement.

**Remedy:** Accumulation rate caps prevent gaming.

---

## Schema Reference

See [schemas/legitimacy-ledger.json](./schemas/legitimacy-ledger.json) for the complete JSON Schema.

---

## Related Documents

- [Enforcement Flow](./enforcement-flow.md) - How violations are detected and remedied
- [The Judicial Branch](./judicial-branch.md) - Source of invalidations and findings
- [Conclave Agenda Control](./conclave-agenda.md) - Mandatory legitimacy review items
- [Aegis Network](./aegis-network.md) - Consent model that feeds legitimacy

