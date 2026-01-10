# Halt & Fork Recovery Procedures

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for handling halt signals, fork detection, and recovery from constitutional integrity issues. These are CRITICAL procedures affecting system governance.

## Prerequisites

- [ ] Understanding of halt state semantics
- [ ] Access to monitoring and database
- [ ] Knowledge of 48-hour recovery waiting period
- [ ] Governance contacts available

## Trigger Conditions

When to execute this runbook:

- Halt signal received
- Fork detected
- Hash chain conflict found
- Constitutional crisis event
- Recovery from halt state needed

## Procedure

### Halt Signal Handling

When a halt signal is received, the system enters read-only mode.

#### Step 1: Verify Halt Signal

- [ ] Confirm halt signal is legitimate
- [ ] Check halt signal source
- [ ] Document halt reason

```sql
-- Check current halt state
SELECT
    id,
    triggered_at,
    reason,
    triggered_by,
    signal_source
FROM halt_state
WHERE cleared_at IS NULL
ORDER BY triggered_at DESC
LIMIT 1;
```

**Verification:**

- Expected outcome: Halt state recorded with valid reason
- Check: Signal was created BEFORE effect (RT-2 compliance)

#### Step 2: Verify System is Read-Only

- [ ] Confirm all write operations are blocked
- [ ] Verify read operations still work
- [ ] Check dual-channel halt propagation

```bash
# Test write is blocked
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{"type": "test"}'
# Expected: 503 Service Unavailable with halt explanation

# Test read works
curl http://localhost:8000/api/events?limit=1
# Expected: 200 OK with events
```

#### Step 3: Notify Stakeholders

- [ ] Alert on-call team
- [ ] Notify governance lead
- [ ] Update status page

**Communication template:**
```
HALT STATE ACTIVE
Time: [timestamp]
Reason: [reason]
Impact: System is read-only
Next steps: Investigation in progress
```

---

### Fork Detection Response

A fork indicates potential constitutional integrity issue.

#### Step 1: Confirm Fork

- [ ] Verify fork detection is accurate
- [ ] Identify fork point (sequence number)
- [ ] Document conflicting hashes

```sql
-- Identify fork point
SELECT
    fd.id,
    fd.detected_at,
    fd.fork_sequence_number,
    fd.expected_hash,
    fd.actual_hash,
    fd.source
FROM fork_detections fd
ORDER BY detected_at DESC
LIMIT 1;
```

#### Step 2: Assess Fork Severity

**Single event conflict:**
- May be recoverable
- Check for transaction race condition
- Verify across replicas

**Multiple event conflict:**
- **CRITICAL** - Constitutional crisis
- System must halt
- Governance required

#### Step 3: Fork Investigation

- [ ] Check all replicas for consistency
- [ ] Review logs around fork time
- [ ] Identify root cause

Possible causes:
- Transaction race condition
- Replication lag
- Manual data manipulation (CRITICAL)
- Byzantine failure

---

### 48-Hour Recovery Waiting Period

After any halt clears, a 48-hour waiting period applies (FR21).

#### Step 1: Verify Waiting Period

- [ ] Calculate time since halt cleared
- [ ] Check no rush-to-clear attempts

```sql
-- Check waiting period status
SELECT
    h.id,
    h.triggered_at,
    h.cleared_at,
    h.cleared_at + INTERVAL '48 hours' as recovery_available_at,
    CASE
        WHEN NOW() > h.cleared_at + INTERVAL '48 hours' THEN 'READY'
        ELSE 'WAITING'
    END as status
FROM halt_state h
WHERE h.cleared_at IS NOT NULL
ORDER BY h.cleared_at DESC
LIMIT 1;
```

#### Step 2: Recovery Operations

During waiting period:
- System is operational but monitored closely
- Any new halt resets the 48-hour timer
- Full recovery operations wait until period expires

After waiting period:
- Full operations resume
- Document recovery completion
- Post-incident review scheduled

---

### Halt Clearing Procedure

Clearing a halt state requires governance approval.

#### Step 1: Verify Clear Authorization

- [ ] Confirm governance approval received
- [ ] Document authorizing party
- [ ] Record authorization timestamp

**CRITICAL:** Halt cannot be cleared by operations alone.

#### Step 2: Execute Halt Clear

- [ ] Record halt clear event (BEFORE clearing)
- [ ] Clear halt state
- [ ] Verify system resumes writes

```sql
-- Record halt clear (witnessed event)
INSERT INTO events (event_type, payload, ...)
VALUES ('HaltCleared', '{"cleared_by": "...", "reason": "..."}', ...);

-- Clear halt state
UPDATE halt_state
SET cleared_at = NOW(), cleared_by = '...'
WHERE id = $HALT_ID AND cleared_at IS NULL;
```

**Verification:**

- Expected outcome: Halt cleared, 48-hour waiting period begins
- Check: HaltCleared event was created and witnessed

#### Step 3: Post-Clear Monitoring

- [ ] Monitor for new issues
- [ ] Track 48-hour waiting period
- [ ] Prepare incident report

---

### Dual-Channel Halt Verification

Halt signals propagate through two independent channels.

#### Step 1: Verify Both Channels

- [ ] Check database halt flag
- [ ] Check Redis halt flag
- [ ] Confirm both agree

```python
# Pseudocode - verify both channels
db_halt = query_db("SELECT is_halted FROM halt_state WHERE cleared_at IS NULL")
redis_halt = redis_client.get("halt_flag")

if db_halt != redis_halt:
    # CRITICAL: Channel disagreement
    raise ConstitutionalCrisis("Halt channel disagreement")
```

#### Step 2: Channel Disagreement Response

If channels disagree:

1. **ASSUME HALTED** (conservative)
2. Investigate root cause
3. Reconcile channels
4. Document incident

---

### Rollback to Checkpoint

For operational rollback (FR143) - requires governance approval.

#### Step 1: Identify Rollback Target

- [ ] List available checkpoints
- [ ] Identify target checkpoint
- [ ] Document events that will be undone

```sql
-- List checkpoints
SELECT
    id,
    created_at,
    sequence_number,
    hash,
    description
FROM checkpoints
ORDER BY sequence_number DESC;
```

#### Step 2: Governance Approval

- [ ] Document rollback reason
- [ ] Obtain governance approval
- [ ] Record authorization

**CRITICAL:** Rollback affects constitutional record.

#### Step 3: Execute Rollback

- [ ] Create rollback event
- [ ] Execute rollback operation
- [ ] Verify new state

See [Recovery Procedures](recovery.md) for detailed steps.

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Halt signal received | Operations Lead | [TBD] |
| Fork detected | System Architect + Governance | [TBD] |
| Constitutional crisis | Governance Lead + Legal | [TBD] |
| Cannot clear halt | Governance Lead | [TBD] |
| Rollback needed | Governance Lead | [TBD] |

## Rollback

Halt procedures don't support rollback - the halt itself is a safety mechanism.

To recover from halt:
1. Investigate root cause
2. Obtain governance approval
3. Clear halt with proper authorization
4. Observe 48-hour waiting period

## Constitutional Reminders

- **FR16-22:** Fork detection and halt semantics
- **FR21:** 48-hour recovery waiting period
- **RT-2:** Halt event must be recorded BEFORE effect
- **CT-11:** All write ops check halt state first
- Sticky halt semantics (FR18): Halt persists until explicitly cleared

## References

- [Event Store Operations](epic-1-event-store.md)
- [Recovery Procedures](recovery.md)
- [Incident Response](incident-response.md)
- Architecture: ADR-3 (Partition Behavior + Halt Durability)
- Epic 3: Halt & Fork Detection stories
