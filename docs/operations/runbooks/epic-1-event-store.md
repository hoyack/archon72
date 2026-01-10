# Event Store Operations & Recovery

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for operating, monitoring, and recovering the Archon 72 event store - the append-only constitutional record that forms the foundation of system integrity.

## Prerequisites

- [ ] Database admin access
- [ ] Understanding of hash chain mechanics
- [ ] Backup access for recovery scenarios

## Trigger Conditions

When to execute this runbook:

- Hash chain verification failure
- Sequence gap detected
- Witness attribution issues
- Event store recovery needed
- Performance degradation on event queries

## Procedure

### Hash Chain Verification

The event store maintains cryptographic integrity through hash chaining.

#### Step 1: Run Integrity Check

- [ ] Execute hash chain verification
- [ ] Check for sequence gaps
- [ ] Verify witness attributions

```sql
-- Check for sequence gaps
SELECT
    sequence_number,
    sequence_number - LAG(sequence_number) OVER (ORDER BY sequence_number) as gap
FROM events
WHERE sequence_number - LAG(sequence_number) OVER (ORDER BY sequence_number) > 1;

-- Verify hash chain (simplified)
SELECT COUNT(*) as invalid_hashes
FROM events e1
JOIN events e2 ON e2.sequence_number = e1.sequence_number - 1
WHERE e1.previous_hash != e2.hash;
```

**Verification:**

- Expected outcome: 0 gaps, 0 invalid hashes
- If ANY issues found: **HALT system and escalate**

#### Step 2: Verify Witness Attestations

- [ ] Check all events have witness records
- [ ] Verify witness signatures

```sql
-- Events missing witnesses
SELECT e.id, e.sequence_number, e.event_type
FROM events e
LEFT JOIN witnesses w ON w.event_id = e.id
WHERE w.id IS NULL;
```

**Verification:**

- Expected outcome: 0 events without witnesses
- Constitutional requirement: Every event MUST be witnessed

---

### Sequence Gap Investigation

If a sequence gap is detected:

#### Step 1: Identify Gap Details

- [ ] Find exact gap location
- [ ] Document missing sequence numbers
- [ ] Check timestamps around gap

```sql
-- Find gap boundaries
WITH gaps AS (
    SELECT
        sequence_number as current_seq,
        LAG(sequence_number) OVER (ORDER BY sequence_number) as prev_seq
    FROM events
)
SELECT prev_seq + 1 as gap_start, current_seq - 1 as gap_end
FROM gaps
WHERE current_seq - prev_seq > 1;
```

#### Step 2: Investigate Root Cause

Possible causes:
- Database transaction rollback
- Replication issue
- Manual data manipulation (CRITICAL)

- [ ] Check database logs around gap timestamp
- [ ] Check application logs for errors
- [ ] Check for any manual SQL execution

#### Step 3: Response

**If gap is recent (< 24 hours):**
- Check if events exist in replica or backup
- Attempt recovery from backup

**If gap is old or unrecoverable:**
- Document gap as permanent
- Create constitutional event documenting the gap
- Escalate to governance

**Verification:**

- Expected outcome: Gap explained and documented
- If unexplained: **Constitutional crisis - halt system**

---

### Event Recovery from Backup

#### Step 1: Identify Recovery Point

- [ ] Find backup containing missing events
- [ ] Verify backup integrity

#### Step 2: Extract Missing Events

- [ ] Restore backup to temporary database
- [ ] Extract missing events
- [ ] Verify hash continuity

```bash
# Restore backup to temp DB
pg_restore -d temp_recovery backup.dump

# Extract missing events
psql -d temp_recovery -c "
COPY (
    SELECT * FROM events
    WHERE sequence_number BETWEEN $START AND $END
) TO '/tmp/missing_events.csv' CSV HEADER;
"
```

#### Step 3: Reinsert Events

**CRITICAL:** This requires governance approval.

- [ ] Verify events maintain hash chain
- [ ] Reinsert with original timestamps
- [ ] Verify chain after insertion

---

### Witness Attribution Troubleshooting

#### No Witness for Event

If an event lacks witness attribution:

1. Check if witness service was running
2. Check witness pool availability
3. Check key registry for valid keys

```sql
-- Check witness pool status at event time
SELECT * FROM witness_pool_status
WHERE recorded_at <= (SELECT created_at FROM events WHERE id = $EVENT_ID)
ORDER BY recorded_at DESC
LIMIT 1;
```

#### Witness Signature Invalid

If a witness signature fails verification:

1. Check key validity at signing time
2. Verify key wasn't rotated
3. Check HSM availability at event time

---

### Performance Optimization

#### Slow Event Queries

For queries exceeding 30-second SLA (FR106):

1. Check query plan: `EXPLAIN ANALYZE <query>`
2. Verify indexes exist on:
   - `sequence_number`
   - `created_at`
   - `event_type`
   - `hash`

```sql
-- Check index usage
SELECT indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE relname = 'events';
```

#### High Write Latency

1. Check for lock contention
2. Verify no long-running transactions
3. Check disk I/O

```sql
-- Check for locks
SELECT * FROM pg_locks WHERE relation = 'events'::regclass;

-- Check long transactions
SELECT * FROM pg_stat_activity
WHERE state = 'active'
AND query_start < NOW() - INTERVAL '1 minute';
```

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Hash chain broken | System Architect + Governance | [TBD] |
| Sequence gap detected | System Architect | [TBD] |
| Witness pool depleted | Security Lead | [TBD] |
| Performance SLA breach | System Architect | [TBD] |

## Rollback

Event store operations generally don't support rollback (append-only). Instead:

1. Document any issues as events
2. Use [Recovery Procedures](recovery.md) for disaster recovery
3. Constitutional rollback requires governance approval

## Constitutional Reminders

- **CT-11:** CHECK HALT STATE before any write operations
- **FR1:** Events are append-only - no modifications allowed
- **FR62-67:** Hash chain must be continuous and verifiable
- Every event MUST be witnessed atomically (RT-1)

## References

- [Backup Procedures](backup.md)
- [Recovery Procedures](recovery.md)
- [Halt & Fork Recovery](epic-3-halt-fork.md)
- Architecture: ADR-1 (Event Store Topology)
- Epic 1: Witnessed Event Store stories
