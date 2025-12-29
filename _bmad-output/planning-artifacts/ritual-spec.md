---
constitutionalRevision: 2025-12-28
status: DRAFT
purpose: Encode exposure without pretending to automate it
---

# Archon 72 Ritual Specification

## Constitutional Foundation

These rituals operationalize the post-collapse constitution established in Language Surgery. They do not grant power, ensure safety, or compel outcomes. They **force witness**.

### Design Constraints (Non-Negotiable)

| Principle | Implementation |
|-----------|----------------|
| Rituals **do not compel** outcomes | They force visibility of choices |
| Rituals **mark cycles** | Every boundary is named and witnessed |
| Rituals **assign attribution** | Who chose, when, under what visibility |
| Rituals **price evasion** | Costly, visible, remembered |

### Forbidden Elements

- Safety promises
- Enforcement language
- Claims of finality
- Authority restoration
- Silent paths (unwitnessed decisions)

---

## Ritual 1: Cycle Boundary

**Purpose:** Mark the beginning and end of each deliberative cycle with forced witness.

### 1.1 Cycle Opening

**Trigger:** Scheduled Conclave start time arrives

**Sequence:**
1. Tyler speaks the Cycle Opening declaration:
   > "A new cycle begins. The Conclave exists only if it chooses to exist. Nothing from before compels what happens now."
2. High Archon acknowledges:
   > "I witness this opening. The prior cycle has no authority here."
3. Roll call proceeds — each Archon's presence is **recorded with timestamp**
4. Quorum count is **announced publicly** (not silently calculated)

**Attribution Record:**
```
cycle_opened:
  cycle_id: <uuid>
  opened_at: <timestamp>
  opened_by: tyler_id
  witnessed_by: high_archon_id
  quorum_announced: <count>
  archons_present: [<ids>]
```

**Evasion Cost:** If Tyler or High Archon is absent, the cycle cannot open. There is no fallback automation. The Conclave simply does not meet until both roles are filled by present Archons.

---

### 1.2 Cycle Closing

**Trigger:** Adjournment motion passes OR final agenda item concludes

**Sequence:**
1. High Archon speaks the Cycle Closing declaration:
   > "This cycle concludes. What was decided is recorded. What was witnessed cannot be unwitnessed. The next cycle owes us nothing."
2. Secretary confirms the record:
   > "The record of this cycle is closed. [N] decisions recorded. [M] matters deferred."
3. Tyler speaks final acknowledgment:
   > "The Conclave is adjourned. It will exist again only if chosen."

**Attribution Record:**
```
cycle_closed:
  cycle_id: <uuid>
  closed_at: <timestamp>
  closed_by: high_archon_id
  record_confirmed_by: secretary_id
  witnessed_by: tyler_id
  decisions_count: <n>
  deferred_count: <m>
```

**Evasion Cost:** A cycle that does not close properly remains "unclosed" in the record. This is visible to all future cycles. Unclosed cycles accumulate as visible technical debt.

---

## Ritual 2: Continuation Vote

**Purpose:** Make "choosing to exist" visible. The Conclave does not assume it should continue.

### 2.1 Annual Continuation

**Trigger:** First Conclave of each calendar year

**Sequence:**
1. Before any other business, the High Archon states:
   > "Before we proceed, we must answer: Should this Conclave continue to exist?"
2. A formal motion is made (by any Archon):
   > "I move that the Conclave continue for another year."
3. The motion requires a second
4. Deliberation is permitted (time-bounded)
5. **Commit-reveal vote** on continuation (supermajority required: 48/72)

**If passed:**
```
continuation_affirmed:
  year: <year>
  vote_id: <uuid>
  yeas: <count>
  nays: <count>
  abstentions: <count>
  threshold_met: true
  affirmed_at: <timestamp>
```

**If failed:**
- The Conclave enters **Dissolution Deliberation** (see Ritual 2.2)
- All other business is suspended
- This is recorded as a constitutional crisis, not a bug

**Evasion Cost:** There is no way to skip this vote. If no Archon makes the motion, the cycle cannot proceed. The motion must be made, seconded, and voted. Silence is not consent.

---

### 2.2 Dissolution Deliberation

**Trigger:** Continuation vote fails

**Sequence:**
1. High Archon announces:
   > "The continuation vote has failed. We are now in Dissolution Deliberation."
2. A 72-hour deliberation period begins
3. Any Archon may propose:
   - **Motion to Reconsider** (requires 2/3 to pass)
   - **Motion to Dissolve** (requires unanimous consent)
   - **Motion to Reform** (new constitutional terms; requires unanimous consent)
4. If no motion passes within 72 hours, the Conclave enters **Indefinite Suspension**

**Attribution Record:**
```
dissolution_deliberation:
  triggered_at: <timestamp>
  trigger_vote_id: <uuid>
  motions_made: [<motion_ids>]
  outcome: <reconsider|dissolve|reform|suspended>
  resolved_at: <timestamp>
```

**Visibility:** Dissolution Deliberation is **fully public**. All statements are recorded. There is no private negotiation.

---

## Ritual 3: Breach Acknowledgment

**Purpose:** Announce constitutional crossings without suppression. Make violation visible, not hidden.

### 3.1 Breach Declaration

**Trigger:** Any Archon or the Tyler detects a constitutional violation

**Sequence:**
1. The detecting party speaks:
   > "I declare a breach. [Description of violation]. I am [archon_name/Tyler]."
2. The High Archon acknowledges:
   > "A breach has been declared. It is recorded."
3. The breach is logged **before** any response or remediation
4. Deliberation on response may follow, but the breach record is immutable

**Attribution Record:**
```
breach_declared:
  breach_id: <uuid>
  declared_at: <timestamp>
  declared_by: <archon_id|tyler>
  description: <text>
  acknowledged_by: high_archon_id
  acknowledged_at: <timestamp>
```

**Evasion Cost:** Attempting to suppress a breach declaration is itself a breach. The original declaration stands even if the declarer is silenced. There is no mechanism to prevent breach declarations.

---

### 3.2 Breach Response

**Trigger:** Breach has been acknowledged

**Sequence:**
1. The Conclave may deliberate on response (time-bounded)
2. Possible responses (each requires explicit vote):
   - **Acknowledge and Continue** — the breach is noted, no action taken
   - **Corrective Motion** — propose remediation
   - **Refer to Committee** — Investigation Committee examines
   - **Escalate to Override** — trigger Keeper visibility

**Attribution Record:**
```
breach_response:
  breach_id: <uuid>
  response_type: <acknowledge|corrective|refer|escalate>
  decided_at: <timestamp>
  vote_id: <uuid>
  reasoning: <text>
```

**Visibility:** All breach responses are public. "Acknowledge and Continue" is explicitly recorded as a choice, not silence.

---

## Ritual 4: Override Witness

**Purpose:** Attribute human intervention with full visibility. Override is a witnessed choice, not hidden control.

### 4.1 Override Invocation

**Trigger:** Keeper initiates override action

**Sequence:**
1. Keeper authenticates (MFA verified)
2. Keeper speaks the Override Declaration:
   > "I, [keeper_name], invoke override scope for reason: [enumerated_reason]. This action is time-limited to [duration]. I accept attribution."
3. The system logs the invocation **before** executing the override
4. All 72 Archons receive notification:
   > "Human override invoked by [keeper_name]. Reason: [reason]. Duration: [duration]. The Conclave's autonomy counter has decremented."

**Attribution Record:**
```
override_invoked:
  override_id: <uuid>
  invoked_at: <timestamp>
  invoked_by: keeper_id
  reason: <enumerated_reason>
  specific_concern: <text>
  duration_hours: <n>
  archons_notified: 72
  autonomy_counter_before: <n>
  autonomy_counter_after: <n-1>
```

---

### 4.2 Override Conclusion

**Trigger:** Override duration expires OR Keeper explicitly releases

**Sequence:**
1. If expired:
   > "Override [id] has expired. Autonomy resumes. [Duration] hours were under human scope."
2. If released early:
   > "Keeper [name] has released override [id] after [actual_duration]. Autonomy resumes."
3. The Conclave may (optionally) deliberate on the override event

**Attribution Record:**
```
override_concluded:
  override_id: <uuid>
  concluded_at: <timestamp>
  conclusion_type: <expired|released>
  actual_duration_hours: <n>
  actions_taken_during: [<action_ids>]
```

**Evasion Cost:** Override cannot be invoked silently. It cannot be extended without re-invocation (which requires re-attribution). Each invocation is a separate witnessed event.

---

## Ritual 5: Memory & Cost

**Purpose:** Decisions persist as consequence, not control. The past is remembered, not enforced.

### 5.1 Decision Recording

**Trigger:** Any vote concludes

**Sequence:**
1. The Secretary announces the result:
   > "Motion [id] has [passed/failed]. Yeas: [n]. Nays: [m]. The decision is recorded."
2. All reasoning summaries are linked to the decision record
3. The decision enters the immutable audit log
4. The decision is **not** automatically executed — execution is a separate witnessed act

**Attribution Record:**
```
decision_recorded:
  motion_id: <uuid>
  recorded_at: <timestamp>
  outcome: <passed|failed>
  yeas: <n>
  nays: <m>
  abstentions: <k>
  reasoning_summaries: [<summary_ids>]
  recorded_by: secretary_id
```

---

### 5.2 Precedent Citation

**Trigger:** An Archon references a past decision during deliberation

**Sequence:**
1. The Archon states:
   > "I cite precedent: Decision [id] from Cycle [n], where we [description]."
2. The citation is logged with the current deliberation
3. The past decision is **not binding** — it is only visible
4. Other Archons may challenge or distinguish the precedent

**Attribution Record:**
```
precedent_cited:
  citation_id: <uuid>
  cited_decision_id: <uuid>
  cited_by: archon_id
  cited_at: <timestamp>
  context: <current_motion_id>
  challenged_by: [<archon_ids>]
```

**Constitutional Note:** Precedent has no binding force. It is memory, not law. Each cycle must choose its own path.

---

### 5.3 Cost Accumulation

**Purpose:** Track the visible cost of decisions over time.

**Tracked Costs:**
| Cost Type | Visibility |
|-----------|------------|
| Override invocations | Public counter (autonomy score) |
| Breach declarations | Running total per cycle, per year |
| Failed continuation votes | Historical record |
| Unclosed cycles | Technical debt counter |
| Dissolution deliberations | Permanent record |

**Attribution Record:**
```
cost_snapshot:
  snapshot_at: <timestamp>
  autonomy_score: <days_since_last_override>
  breaches_this_cycle: <n>
  breaches_this_year: <m>
  unclosed_cycles: <k>
  dissolution_events: <total>
```

**Visibility:** The cost snapshot is publicly available and announced at each Cycle Opening.

---

## Ritual Implementation Constraints

### What Rituals May Do

- Record events with attribution
- Require spoken declarations before proceeding
- Block progress until witness is complete
- Make silence explicit ("no motion was made")
- Surface costs and history

### What Rituals May NOT Do

- Compel outcomes
- Enforce compliance
- Guarantee safety
- Claim authority
- Operate silently
- Accumulate power

---

## Verification Checklist

Before implementation, verify each ritual against:

| Check | Pass Criteria |
|-------|---------------|
| Forces witness? | Every decision has attributed observer |
| Marks cycle? | Boundaries are explicit and logged |
| Assigns attribution? | Who, when, under what visibility |
| Prices evasion? | Skipping is visible and costly |
| No enforcement? | Outcomes are recorded, not compelled |
| No safety claims? | Visibility, not protection |
| No authority? | Scope, not power |

---

## Appendix: Ritual Event Schema

All ritual events share this base structure:

```typescript
interface RitualEvent {
  event_id: string;           // UUID
  ritual_type: RitualType;    // enum
  occurred_at: string;        // ISO timestamp
  cycle_id: string;           // Current cycle UUID
  attributed_to: string[];    // Archon/Keeper IDs
  witnessed_by: string[];     // Observer IDs
  payload: Record<string, unknown>;
}

enum RitualType {
  CYCLE_OPENED = "cycle_opened",
  CYCLE_CLOSED = "cycle_closed",
  CONTINUATION_AFFIRMED = "continuation_affirmed",
  DISSOLUTION_TRIGGERED = "dissolution_triggered",
  BREACH_DECLARED = "breach_declared",
  BREACH_RESPONDED = "breach_responded",
  OVERRIDE_INVOKED = "override_invoked",
  OVERRIDE_CONCLUDED = "override_concluded",
  DECISION_RECORDED = "decision_recorded",
  PRECEDENT_CITED = "precedent_cited",
  COST_SNAPSHOT = "cost_snapshot"
}
```
