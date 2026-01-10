# Breach Detection & Escalation

Last Updated: 2026-01-08
Version: 1.0
Owner: Governance Team

## Purpose

Procedures for handling constitutional breach declarations, 7-day escalation timelines, and witness selection verification. Breach handling is a GOVERNANCE operation requiring special oversight.

## Prerequisites

- [ ] Access to breach monitoring
- [ ] Understanding of constitutional thresholds
- [ ] Governance contacts available
- [ ] Knowledge of escalation timelines

## Trigger Conditions

When to execute this runbook:

- Breach declaration event created
- 7-day escalation deadline approaching
- Witness pool anomaly detected
- Collusion suspicion raised
- Amendment visibility required

## Procedure

### Breach Declaration Handling

When a breach is declared, a permanent constitutional record is created.

#### Step 1: Verify Breach Declaration

- [ ] Confirm breach event was recorded
- [ ] Verify breach type and threshold
- [ ] Document initial assessment

```sql
-- Check recent breach declarations
SELECT
    id,
    breach_type,
    threshold_violated,
    declared_at,
    severity,
    status,
    escalation_deadline
FROM breach_declarations
WHERE declared_at > NOW() - INTERVAL '7 days'
ORDER BY declared_at DESC;
```

**Verification:**

- Expected outcome: Breach recorded with correct threshold
- Check: Escalation deadline is set (declared_at + 7 days)

#### Step 2: Initial Response

- [ ] Alert governance team
- [ ] Begin investigation
- [ ] Document investigation status

**Communication template:**
```
BREACH DECLARATION
Type: [breach_type]
Threshold: [threshold_violated]
Declared: [timestamp]
Escalation deadline: [deadline]
Status: Under investigation
```

---

### 7-Day Escalation Timeline (FR31)

Unresolved breaches escalate to cessation agenda after 7 days.

#### Step 1: Monitor Escalation Status

- [ ] Track breach age
- [ ] Check resolution progress
- [ ] Alert when deadline approaches

```sql
-- Check escalation status
SELECT
    id,
    breach_type,
    declared_at,
    escalation_deadline,
    escalation_deadline - NOW() as time_remaining,
    CASE
        WHEN escalation_deadline - NOW() < INTERVAL '24 hours' THEN 'CRITICAL'
        WHEN escalation_deadline - NOW() < INTERVAL '48 hours' THEN 'WARNING'
        ELSE 'OK'
    END as urgency
FROM breach_declarations
WHERE status = 'open'
ORDER BY escalation_deadline;
```

#### Step 2: Pre-Escalation Actions

**At 5 days (2 days remaining):**
- Warning to governance
- Accelerate investigation
- Prepare escalation documentation

**At 6 days (1 day remaining):**
- Critical alert
- Governance must decide: resolve or escalate
- Prepare cessation agenda placement

#### Step 3: Escalation Execution

If breach reaches 7 days without resolution:

- [ ] Create escalation event
- [ ] Place on cessation consideration agenda
- [ ] Notify all stakeholders

```sql
-- Record escalation
INSERT INTO events (event_type, payload, ...)
VALUES ('BreachEscalated', '{
    "breach_id": "...",
    "escalated_at": "...",
    "agenda_placement": "cessation_consideration",
    "original_declaration": "..."
}', ...);
```

---

### Witness Selection Verification

Witnesses are selected using verifiable randomness (FR35).

#### Step 1: Verify Selection Randomness

- [ ] Check random seed was published
- [ ] Verify selection algorithm is deterministic
- [ ] Confirm selection can be independently reproduced

```sql
-- Check witness selection
SELECT
    ws.event_id,
    ws.random_seed,
    ws.selected_witnesses,
    ws.selection_timestamp,
    ws.verifiable
FROM witness_selections ws
WHERE ws.event_id = $EVENT_ID;
```

#### Step 2: Selection Dispute Response

If witness selection is disputed:

1. Reproduce selection with published seed
2. Compare against recorded selection
3. If mismatch: **CRITICAL** - potential manipulation
4. Document finding

---

### Witness Pool Anomaly Detection (FR116-121)

Monitor witness pool for suspicious patterns.

#### Step 1: Check Pool Health

- [ ] Verify pool size is sufficient
- [ ] Check for concentration patterns
- [ ] Monitor witness frequency

```sql
-- Witness pool health
SELECT
    witness_id,
    COUNT(*) as witness_count,
    MIN(witnessed_at) as first_witness,
    MAX(witnessed_at) as last_witness
FROM witness_records
WHERE witnessed_at > NOW() - INTERVAL '30 days'
GROUP BY witness_id
ORDER BY witness_count DESC;
```

**Anomaly indicators:**
- Any witness >20% of events: Concentration risk
- <5 active witnesses: Pool depletion
- Sudden witness frequency spike: Potential manipulation

#### Step 2: Anomaly Response

If anomaly detected:

1. Create anomaly event
2. Alert governance
3. Review recent witness selections
4. Consider pool refresh

---

### Collusion Detection (FR59-61)

Monitor for potential witness collusion.

#### Step 1: Run Collusion Analysis

- [ ] Check witness pairing frequency
- [ ] Analyze timing patterns
- [ ] Review cross-reference patterns

```sql
-- Check witness pair frequency
SELECT
    LEAST(w1.witness_id, w2.witness_id) as witness_a,
    GREATEST(w1.witness_id, w2.witness_id) as witness_b,
    COUNT(*) as co_witness_count
FROM witness_records w1
JOIN witness_records w2 ON w1.event_id = w2.event_id AND w1.witness_id < w2.witness_id
WHERE w1.witnessed_at > NOW() - INTERVAL '30 days'
GROUP BY witness_a, witness_b
HAVING COUNT(*) > 10  -- Unusually high co-witnessing
ORDER BY co_witness_count DESC;
```

#### Step 2: Collusion Alert Response

If collusion pattern detected:

1. Create collusion investigation event
2. Suspend suspected witnesses
3. Review affected events
4. Escalate to governance + security

---

### Amendment Visibility (FR33)

All constitutional amendments must be publicly visible.

#### Step 1: Verify Amendment Visibility

- [ ] Check amendment is in public record
- [ ] Verify amendment metadata is complete
- [ ] Confirm observer access

```sql
-- Check amendment visibility
SELECT
    a.id,
    a.amendment_type,
    a.effective_at,
    a.public_visibility,
    EXISTS (
        SELECT 1 FROM observer_events oe WHERE oe.event_id = a.event_id
    ) as in_observer_api
FROM amendments a
WHERE a.created_at > NOW() - INTERVAL '30 days';
```

#### Step 2: Visibility Issue Response

If amendment not visible:

1. **CRITICAL** - Constitutional violation
2. Investigate root cause
3. Restore visibility immediately
4. Create breach event

---

### Configuration Floor Enforcement (FR36)

Certain configuration values have minimum floors that cannot be lowered.

#### Step 1: Verify Floor Compliance

- [ ] Check current configuration values
- [ ] Verify against floor definitions
- [ ] Alert on floor violations

```sql
-- Check configuration floors
SELECT
    cf.config_key,
    cf.floor_value,
    c.current_value,
    CASE
        WHEN c.current_value < cf.floor_value THEN 'VIOLATION'
        ELSE 'OK'
    END as status
FROM configuration_floors cf
JOIN configuration c ON c.key = cf.config_key;
```

#### Step 2: Floor Violation Response

If floor violated:

1. Create breach event
2. Restore to floor value
3. Investigate how violation occurred
4. Prevent future violations

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Breach declared | Governance Lead | [TBD] |
| 48 hours to escalation | Governance Lead | [TBD] |
| Collusion detected | Governance + Security | [TBD] |
| Witness pool depleted | System Architect | [TBD] |
| Amendment not visible | Governance + Legal | [TBD] |

## Rollback

Breach declarations cannot be rolled back - they are permanent records.

To resolve a breach:
1. Address root cause
2. Create resolution event
3. Update breach status
4. Both records remain permanent

## Constitutional Reminders

- **FR30-36:** Breach and threshold requirements
- **FR59-61:** Witness collusion defense
- **FR116-121:** Witness and heartbeat defense
- All breaches are PERMANENT records
- 7-day escalation is AUTOMATIC

## References

- [Keeper Operations](epic-5-keeper.md)
- [Cessation Procedures](epic-7-cessation.md)
- [Incident Response](incident-response.md)
- Architecture: ADR-6 (Amendment, Ceremony, Convention Tier)
- Epic 6: Breach & Threshold Enforcement stories
