# Conclave Agenda Control

> **The Agenda Generator is a constitutional mechanism that makes omission costly by forcing acknowledgement of hard truths, bounding new business by realm quotas, and producing an auditable record of why each item was heard or deferred.**

## Overview

Agenda control is power. The ability to decide what gets discussed is often more consequential than the votes themselves. This document defines the constitutional controls that prevent "suppression by omission" in Archon 72's Conclave.

**Core Problem:** If agenda-setting is unconstrained, those who control the agenda can:
- Bury inconvenient topics
- Flood the queue with friendly items
- Defer hard truths indefinitely
- Create the appearance of deliberation while avoiding it

**Solution:** A rule-based Agenda Generator that:
- Forces acknowledgement of items that cannot be ignored
- Bounds new business by realm quotas
- Creates an auditable trail of what was heard and why
- Makes omission visible and costly

---

## Constitutional Requirements

The Agenda Generator must satisfy these non-negotiable requirements:

| Requirement | Description |
|-------------|-------------|
| **No Suppression by Omission** | Items that require acknowledgement must appear, even if inconvenient |
| **Realm Fairness** | No single realm can flood the agenda |
| **Transparency** | Why items appear (or don't) must be auditable |
| **Predictability** | Rules are known in advance; no ad-hoc agenda manipulation |
| **Completeness** | Every submitted item is eventually heard or explicitly rejected |

---

## Agenda Inputs (6 Canonical Queues)

The Agenda Generator consumes from exactly 6 input queues. No other source can place items on the agenda.
Queues 1-2 handle Motion Seeds (pre-admission submissions), not ratified Motions.

### Queue 1: New Motion Seeds

| Property | Value |
|----------|-------|
| Source | Dukes, Earls (via Duke sponsorship) |
| Priority | Band 3 (New Business) |
| Subject to quota | YES - max 1 per realm per Conclave |
| Can be deferred | YES |

New Motion Seeds (pre-admission submissions) requesting authorization, resources, or policy changes.

### Queue 2: Deferred Motion Seeds

| Property | Value |
|----------|-------|
| Source | Previous Conclave deferrals |
| Priority | Band 2 (Unfinished Business) |
| Subject to quota | NO - must be heard |
| Can be deferred | YES (but deferral count tracked) |

Motion Seeds that were submitted but not heard in previous Conclaves. Deferral count is visible.

### Queue 3: Blockers

| Property | Value |
|----------|-------|
| Source | Any Archon with blocking concern |
| Priority | Band 1 (Critical Blockers) |
| Subject to quota | NO |
| Can be deferred | NO - must be acknowledged |

Issues that block in-progress work. Cannot be suppressed.

### Queue 4: Witness Statements

| Property | Value |
|----------|-------|
| Source | Knight-Witness (Furcas) |
| Priority | Band 0 (Forced Acknowledgement) |
| Subject to quota | NO |
| Can be deferred | NO - must be acknowledged |

Violations detected by the Knight-Witness. The Conclave must acknowledge receipt even if action is deferred to Princes.

### Queue 5: Judicial Referrals

| Property | Value |
|----------|-------|
| Source | Prince panels |
| Priority | Band 0 (Forced Acknowledgement) |
| Subject to quota | NO |
| Can be deferred | NO - must be acknowledged |

Findings and remedy recommendations from judicial review. Cannot be ignored.

### Queue 6: Mandatory Review

| Property | Value |
|----------|-------|
| Source | System (time-triggered) |
| Priority | Band 0 (Forced Acknowledgement) |
| Subject to quota | NO |
| Can be deferred | NO |

Items that constitutionally require periodic review (e.g., expiring authorizations, sunset clauses, annual reviews).

---

## Priority Bands

Items are placed into 5 priority bands. Higher bands are processed first.

### Band 0: Forced Acknowledgements

**Cannot be skipped. Must appear on every agenda where they exist.**

Sources:
- Witness Statements (Queue 4)
- Judicial Referrals (Queue 5)
- Mandatory Review (Queue 6)

The Conclave must acknowledge these items. Acknowledgement does not require resolution - it requires that the item was presented, discussed, and a disposition recorded.

### Band 1: Critical Blockers

**High priority. Heard after Band 0.**

Sources:
- Blockers (Queue 3)

Issues that are preventing in-progress work from completing. These get priority because blocking work wastes authorized capacity.

### Band 2: Unfinished Business

**Medium priority. Heard after Band 1.**

Sources:
- Deferred Motion Seeds (Queue 2)

Motion Seeds that were previously submitted but not resolved. Deferral count is visible to prevent indefinite delay.

### Band 3: New Business

**Standard priority. Subject to realm quotas.**

Sources:
- New Motion Seeds (Queue 1)

New items requesting authorization. Limited to 1 per realm per Conclave to prevent flooding.

### Band 4: Optional/Overflow

**Lowest priority. Only if time permits.**

Sources:
- Items explicitly marked as low-priority
- Informational items not requiring decision

These items may be heard if agenda capacity remains. No guarantee of inclusion.

---

## Realm Quotas

### The Problem

Without quotas, a single realm (or coordinated realms) could flood the agenda with friendly Motion Seeds, crowding out items from other realms.

### The Rule

**Maximum 1 new Motion Seed per realm per Conclave.**

This ensures:
- All realms have fair access to agenda time
- No realm can dominate new business
- Strategic flooding is prevented

### Quota Mechanics

```
realm_quota = {
  "max_new_motions_per_conclave": 1,
  "applies_to": "Band 3 (New Business)",
  "overflow_handling": "defer_to_next_conclave",
  "priority_within_realm": "submission_timestamp"
}
```

If a realm submits multiple Motion Seeds:
1. First-submitted Motion Seed is scheduled
2. Remaining Motion Seeds are deferred to next Conclave
3. Deferral is recorded with reason "realm_quota_exceeded"

### Exemptions

Quotas do NOT apply to:
- Band 0 items (Forced Acknowledgements)
- Band 1 items (Critical Blockers)
- Band 2 items (Unfinished Business)

Only new Motion Seeds are quota-constrained.

---

## Motion Admission Gate

Before entering any queue, Motion Seeds pass through the Motion Admission Gate, which validates:

### Required Fields

| Field | Validation |
|-------|------------|
| `motion_id` | Valid UUID |
| `sponsor_id` | Valid Archon with sponsorship authority |
| `realm` | Valid realm identifier |
| `motion_type` | One of defined types |
| `title` | Non-empty, max 200 chars |
| `summary` | Non-empty, max 2000 chars |
| `requested_action` | Specific, actionable request |

### Rejection Criteria

Motion Seeds are rejected (not deferred) if:

| Criterion | Reason |
|-----------|--------|
| Duplicate | Identical motion already in queue |
| Malformed | Missing required fields |
| Unauthorized sponsor | Sponsor lacks authority to submit |
| Invalid realm | Realm does not exist |
| Scope violation | Motion requests action outside sponsor's authority |

Rejected motions receive a rejection record with reason. Rejection can be appealed.

### Admission Record

Every motion receives an admission record:

```json
{
  "motion_id": "uuid",
  "admitted": true,
  "admitted_at": "2026-01-16T10:00:00Z",
  "assigned_queue": "new_motions",
  "assigned_band": 3,
  "realm_quota_position": 1,
  "estimated_conclave": "2026-01-20"
}
```

---

## Agenda Generation Algorithm

### Input

- Current contents of all 6 queues
- Conclave capacity (available time slots)
- Realm quota status

### Algorithm

```
1. COLLECT all Band 0 items (Forced Acknowledgements)
   - These MUST appear. No filtering.

2. COLLECT all Band 1 items (Critical Blockers)
   - Sort by submission time (oldest first)

3. COLLECT all Band 2 items (Unfinished Business)
   - Sort by deferral count (most deferred first), then submission time

4. COLLECT Band 3 items (New Business)
   - Filter by realm quota (max 1 per realm)
   - Sort by submission time (oldest first)

5. CALCULATE remaining capacity after Bands 0-3

6. IF remaining capacity > 0:
   - COLLECT Band 4 items up to capacity

7. FOR each item not included:
   - CREATE deferral record with reason

8. OUTPUT agenda + transparency report
```

### Capacity Overflow

If Bands 0-2 exceed capacity:
1. All Band 0 items still appear (non-negotiable)
2. Band 1-2 items are scheduled with overflow indicator
3. Conclave is flagged as "capacity crisis"
4. Capacity crisis triggers automatic review of workload

---

## Transparency Output

### Internal Report (Full Detail)

Available to all Archons. Contains:

```json
{
  "conclave_id": "uuid",
  "agenda_generated_at": "2026-01-16T08:00:00Z",
  "generation_algorithm_version": "1.0.0",
  "input_summary": {
    "queue_1_new_motions": 12,
    "queue_2_deferred_motions": 3,
    "queue_3_blockers": 1,
    "queue_4_witness_statements": 2,
    "queue_5_judicial_referrals": 0,
    "queue_6_mandatory_review": 1
  },
  "capacity": {
    "total_slots": 15,
    "band_0_consumed": 3,
    "band_1_consumed": 1,
    "band_2_consumed": 3,
    "band_3_consumed": 6,
    "band_4_consumed": 2
  },
  "realm_quota_status": {
    "realm_strategic": { "used": 1, "deferred": 2 },
    "realm_tactical": { "used": 1, "deferred": 0 },
    "realm_judicial": { "used": 0, "deferred": 0 }
  },
  "deferrals": [
    {
      "motion_id": "uuid",
      "reason": "realm_quota_exceeded",
      "deferral_count": 1
    }
  ],
  "agenda_items": [ /* ordered list */ ]
}
```

### Public Report (Summary)

Available externally. Contains:

- Total items on agenda
- Band distribution
- Deferral count by reason
- Capacity utilization
- No individual motion details

---

## Failure Mode Handling

### Queue Corruption

If a queue becomes corrupted or unavailable:

1. Agenda generation proceeds with available queues
2. Unavailable queue is flagged in transparency report
3. Recovery process initiated
4. No items from corrupted queue are silently dropped

### Capacity Crisis

If Band 0-1 items alone exceed capacity:

1. Extended session scheduled automatically
2. Capacity crisis recorded
3. King notified for workload review
4. Root cause analysis required within 48 hours

### Algorithm Failure

If agenda generation fails:

1. Previous agenda is rolled forward
2. All new submissions are deferred (not rejected)
3. Failure is logged with full diagnostic
4. Manual intervention required before next Conclave

### Deferral Escalation

If an item is deferred 3+ times:

1. Automatic escalation to Band 1 (Critical Blockers)
2. Deferral escalation recorded
3. Item cannot be deferred again without King review

---

## Anti-Patterns to Watch

### Agenda Stuffing

**Symptom:** One realm consistently maxes out quota while others don't use theirs.

**Detection:** Realm quota utilization tracked over time.

**Remedy:** No automatic remedy - this may be legitimate. Pattern is flagged for transparency.

### Perpetual Deferral

**Symptom:** Same item deferred repeatedly without resolution.

**Detection:** Deferral count tracking with escalation at 3+.

**Remedy:** Automatic escalation to Band 1.

### Band 0 Inflation

**Symptom:** Items incorrectly classified as Band 0 to skip quotas.

**Detection:** Band 0 items audited for proper source.

**Remedy:** Misclassification is a procedural violation reviewable by Princes.

### Capacity Manipulation

**Symptom:** Capacity artificially reduced to defer legitimate items.

**Detection:** Capacity history tracked; anomalies flagged.

**Remedy:** Capacity decisions require Duke-level authorization with rationale.

---

## Schema Reference

See [schemas/conclave-agenda.json](./schemas/conclave-agenda.json) for the complete JSON Schema.

---

## Related Documents

- [Aegis Network](./aegis-network.md) - The execution network that agenda items authorize
- [Task Lifecycle](./task-lifecycle.md) - What happens after motions are approved
- [Enforcement Flow](./enforcement-flow.md) - How Witness Statements become Band 0 items
- [The Judicial Branch](./judicial-branch.md) - Source of Judicial Referrals (Queue 5)
