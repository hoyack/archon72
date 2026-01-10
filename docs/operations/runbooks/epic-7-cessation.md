# Cessation Procedures & Post-Cessation Access

Last Updated: 2026-01-08
Version: 1.0
Owner: Governance Team + Legal

## Purpose

Procedures for handling system cessation - the permanent, irreversible shutdown of the Archon 72 system. This is the most critical constitutional operation and requires extensive governance oversight.

**WARNING:** Cessation is IRREVERSIBLE. Once executed, it cannot be undone.

## Prerequisites

- [ ] Governance authorization (unanimous or threshold vote)
- [ ] Legal counsel notification
- [ ] Final deliberation recording complete
- [ ] All stakeholders notified
- [ ] Post-cessation access configured

## Trigger Conditions

When to execute this runbook:

- Unanimous cessation vote by Archons
- Constitutional threshold breached triggering auto-cessation
- External observer petition accepted
- Scheduled cessation date reached

## Procedure

### Pre-Cessation Checklist

Before ANY cessation activity:

#### Step 1: Verify Cessation Authority

- [ ] Confirm cessation trigger condition
- [ ] Verify governance authorization
- [ ] Document authorizing vote/decision
- [ ] Legal review completed

```sql
-- Check cessation authorization
SELECT
    ca.id,
    ca.trigger_type,
    ca.authorized_at,
    ca.authorizing_vote_id,
    ca.legal_review_completed,
    ca.status
FROM cessation_authorizations ca
ORDER BY authorized_at DESC
LIMIT 1;
```

**Verification:**

- Expected outcome: Valid authorization exists
- Check: All required approvals documented

#### Step 2: Final Deliberation Recording (FR42)

- [ ] Schedule final deliberation
- [ ] Record all 72 agent final statements
- [ ] Create permanent archive

```sql
-- Verify final deliberation recorded
SELECT
    fd.id,
    fd.deliberation_type,
    fd.agent_count,
    fd.recorded_at,
    fd.archive_hash
FROM final_deliberations fd
WHERE fd.cessation_authorization_id = $AUTH_ID;
```

**CRITICAL:** Final deliberation MUST be recorded before cessation.

#### Step 3: Pre-Cessation Communications

- [ ] Notify all Keepers
- [ ] Notify all registered observers
- [ ] Public announcement
- [ ] Legal notifications sent

---

### Cessation Execution

**THIS SECTION DESCRIBES IRREVERSIBLE ACTIONS**

#### Step 1: Create Cessation Event (FR24)

Cessation is recorded as the FINAL constitutional event.

- [ ] Create CessationExecuted event
- [ ] Ensure event is witnessed
- [ ] Verify event is in hash chain

```sql
-- This is the LAST event that can be written
INSERT INTO events (event_type, payload, ...)
VALUES ('CessationExecuted', '{
    "authorization_id": "...",
    "executed_by": "...",
    "final_sequence_number": ...,
    "final_hash": "...",
    "execution_timestamp": "..."
}', ...);

-- Verify
SELECT * FROM events ORDER BY sequence_number DESC LIMIT 1;
-- Must show CessationExecuted event
```

#### Step 2: Activate Freeze Mechanics (FR39)

- [ ] Set cessation flag to TRUE
- [ ] Disable all write operations
- [ ] Verify freeze is active

```sql
-- Activate cessation freeze
UPDATE system_flags
SET cessation_active = TRUE, cessation_timestamp = NOW()
WHERE id = 1;

-- Verify freeze
SELECT cessation_active, cessation_timestamp FROM system_flags;
```

**Verification:**

- Expected outcome: All writes blocked
- Test: Attempt write operation - must fail with "System Ceased" error

#### Step 3: Verify Schema Irreversibility (FR38)

The database schema enforces irreversibility:

- [ ] Cessation flag cannot be set to FALSE
- [ ] No new events can be inserted
- [ ] Existing data cannot be modified

```sql
-- This MUST fail
UPDATE system_flags SET cessation_active = FALSE;
-- Expected: Constraint violation or trigger rejection

-- This MUST fail
INSERT INTO events (event_type, ...) VALUES ('test', ...);
-- Expected: Constraint violation
```

#### Step 4: Transition to Read-Only (FR40)

- [ ] Reconfigure database for read-only
- [ ] Update API to reject all writes
- [ ] Verify read operations work

```bash
# Test read-only access
curl http://localhost:8000/observer/events
# Expected: 200 OK with events

curl -X POST http://localhost:8000/api/events
# Expected: 503 with "System has ceased" message
```

---

### Post-Cessation Access (FR40)

After cessation, the system provides read-only access for auditing and compliance.

#### Step 1: Configure Read-Only Mode

- [ ] API serves only GET endpoints
- [ ] Observer API remains functional
- [ ] All data is accessible for verification

#### Step 2: Archive Preparation

- [ ] Create final backup
- [ ] Generate integrity case artifact (FR144)
- [ ] Archive all configuration

```bash
# Final backup
pg_dump -h $DB_HOST -d $DB_NAME -F c -f final_backup_cessation.dump

# Generate integrity case
make generate-integrity-case
```

#### Step 3: Long-Term Access Plan

- [ ] Document access procedures
- [ ] Configure archival storage
- [ ] Establish access request process

---

### Integrity Case Artifact (FR144)

Generate the official record of system integrity at cessation.

#### Step 1: Generate Artifact

- [ ] Compile all events with hashes
- [ ] Include all breach records
- [ ] Include all override records
- [ ] Include governance decisions

```bash
# Generate integrity case
python scripts/generate_integrity_case.py \
  --output integrity_case_$(date +%Y%m%d).json \
  --format json

# Verify artifact
sha256sum integrity_case_*.json
```

#### Step 2: Artifact Distribution

- [ ] Publish to designated archives
- [ ] Send to legal/compliance
- [ ] Make available to observers
- [ ] Store in cold storage

---

### Public Cessation Trigger Conditions (FR41)

Cessation trigger conditions must be publicly documented.

#### Current Triggers

1. **Unanimous Archon Vote:** All 72 agents vote for cessation
2. **Constitutional Threshold Breach:** Per CT-XX definitions
3. **External Observer Petition:** Accepted petition with evidence
4. **7-Day Escalated Breach:** Unresolved breach auto-escalation

```sql
-- Check current trigger conditions
SELECT
    trigger_id,
    trigger_name,
    description,
    threshold,
    current_status
FROM cessation_triggers
WHERE active = TRUE;
```

---

### Emergency Cessation

For immediate cessation due to critical constitutional failure:

#### Step 1: Declare Emergency

- [ ] Document emergency condition
- [ ] Bypass normal waiting periods (if authorized)
- [ ] Notify all parties simultaneously

#### Step 2: Execute Rapid Cessation

- [ ] Follow standard cessation procedure
- [ ] Compress timeline but don't skip steps
- [ ] Document compressed timeline justification

**CRITICAL:** Even emergency cessation must record:
- Cessation event
- Final deliberation (may be abbreviated)
- Integrity case artifact

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Cessation trigger detected | Governance Lead | [TBD] |
| Pre-cessation preparation | Governance + Legal | [TBD] |
| Cessation execution | Full Governance Board | [TBD] |
| Post-cessation issues | Legal Counsel | [TBD] |

## Rollback

**CESSATION CANNOT BE ROLLED BACK**

This is by design - cessation is the ultimate constitutional safeguard.

If cessation was triggered in error:
1. The event is still permanent
2. Document the error
3. A new system would need to be deployed
4. The ceased system remains as historical record

## Constitutional Reminders

- **FR37-43:** Cessation protocol requirements
- **FR134-135:** Cessation gaming defense
- **FR144:** Safety case / integrity case
- Cessation is the FINAL event (FR24)
- Schema enforces irreversibility (FR38)
- Read-only access preserved (FR40)

## References

- [Breach Detection](epic-6-breach.md)
- [Recovery Procedures](recovery.md)
- [Incident Response](incident-response.md)
- Architecture: ADR-12 (Crisis Response)
- Epic 7: Cessation Protocol stories
