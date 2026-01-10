# Recovery Procedures

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for recovering the Archon 72 Conclave Backend from various failure scenarios, including disaster recovery from backups.

## Prerequisites

- [ ] Access to backup storage
- [ ] Backup decryption keys
- [ ] Clean infrastructure for recovery (VMs, containers)
- [ ] Database and Redis servers available
- [ ] Recovery has been authorized (governance approval for constitutional recovery)

## Trigger Conditions

When to execute this runbook:

- Database corruption detected
- Complete system failure
- Ransomware or security incident
- Data center failure
- Failed upgrade requiring rollback

## Recovery Decision Tree

```
Is the event store intact?
├── YES → Use [Operational Recovery](#operational-recovery)
└── NO → Is a valid backup available?
    ├── YES → Use [Full Disaster Recovery](#full-disaster-recovery)
    └── NO → CRITICAL: Escalate to Governance immediately
```

## Operational Recovery

For failures that don't affect the event store (constitutional data).

### Step 1: Assess Damage

- [ ] Identify what failed (API, Redis, infrastructure)
- [ ] Verify event store is intact
- [ ] Document failure timeline

**Verification:**

- Expected outcome: Clear understanding of failure scope
- SQL to verify event store: `SELECT COUNT(*), MAX(sequence_number) FROM events;`

### Step 2: Restore Infrastructure

- [ ] Provision replacement infrastructure if needed
- [ ] Restore configuration from backups
- [ ] Verify network connectivity

### Step 3: Restore Operational State

- [ ] Restore Redis from backup (if needed)
- [ ] Clear any stale locks or caches
- [ ] Verify operational data consistency

### Step 4: Restart Services

- [ ] Follow [Startup Procedures](startup.md)
- [ ] Verify pre-operational checks pass
- [ ] Monitor for issues

---

## Full Disaster Recovery

For catastrophic failures requiring restoration from backup.

### Step 1: Declare Disaster Recovery

#### Constitutional Requirement

- [ ] **GOVERNANCE APPROVAL REQUIRED** for restoring constitutional data
- [ ] Document authorization and authorizing party
- [ ] Record disaster recovery start time

**This is a CONSTITUTIONAL operation** - all steps must be witnessed and documented.

### Step 2: Prepare Recovery Environment

- [ ] Provision clean infrastructure
- [ ] Install database server
- [ ] Install Redis server
- [ ] Configure network and security

**Verification:**

- Expected outcome: Clean environment ready for restore
- Command to verify: Infrastructure health checks pass

### Step 3: Retrieve Backup Files

- [ ] Identify most recent valid backup
- [ ] Download from offsite storage
- [ ] Decrypt backup files
- [ ] Verify backup integrity (checksums)

```bash
# Download and decrypt
aws s3 cp s3://archon72-backups/YYYY/MM/DD/backup_events_*.dump.gpg .
gpg --decrypt backup_events_*.dump.gpg > backup_events.dump

# Verify checksum
sha256sum backup_events.dump
# Compare with recorded checksum from backup log
```

**Verification:**

- Expected outcome: Backup files available and verified
- Checksum must match backup log entry

### Step 4: Restore Database

- [ ] Create database
- [ ] Restore event store tables
- [ ] Restore supporting tables

```bash
# Create database
createdb archon72

# Restore from backup
pg_restore -d archon72 -c backup_events.dump

# Verify restore
psql -d archon72 -c "SELECT COUNT(*) FROM events;"
psql -d archon72 -c "SELECT MAX(sequence_number), hash FROM events ORDER BY sequence_number DESC LIMIT 1;"
```

**Verification:**

- Expected outcome: Event count and hash chain head match backup log
- Any discrepancy is CRITICAL - stop and escalate

### Step 5: Verify Hash Chain Integrity

**CRITICAL CONSTITUTIONAL CHECK**

- [ ] Run full hash chain verification
- [ ] Every event's hash must match computed hash
- [ ] No gaps in sequence numbers

```bash
# Run hash chain verification
make verify-hash-chain

# Or manual verification
psql -d archon72 -c "
SELECT e.id, e.sequence_number,
       e.hash = expected_hash(e.previous_hash, e.payload) as hash_valid
FROM events e
WHERE e.hash != expected_hash(e.previous_hash, e.payload);
"
# Expected: 0 rows (no invalid hashes)
```

**Verification:**

- Expected outcome: Zero invalid hashes, no sequence gaps
- **If ANY hash is invalid: STOP and escalate to Governance**

### Step 6: Restore Redis State

- [ ] Restore Redis RDB file (if available)
- [ ] Or start with empty Redis (caches will rebuild)
- [ ] Verify Redis connectivity

### Step 7: Deploy Application

- [ ] Deploy application code
- [ ] Configure environment variables
- [ ] Follow [Startup Procedures](startup.md)

### Step 8: Post-Recovery Validation

#### Operational Check

- [ ] All health checks pass
- [ ] API responds correctly
- [ ] Metrics are being collected

#### Constitutional Check

- [ ] Hash chain integrity verified
- [ ] Witness pool is functional
- [ ] Halt state is correct (should be checked per recovery context)
- [ ] All events since recovery point are documented as lost

**Verification:**

- Expected outcome: System operational with verified integrity
- Document: Recovery completion time, data loss window (if any)

### Step 9: Document Recovery

**REQUIRED:** Create incident report including:

- [ ] Failure cause
- [ ] Recovery authorization
- [ ] Backup used (date, checksum)
- [ ] Data loss window (events between backup and failure)
- [ ] Verification results
- [ ] Lessons learned

---

## Point-in-Time Recovery

For recovering to a specific point in time (e.g., before a bad event).

**WARNING:** This is a CONSTITUTIONAL operation that may result in data loss.

### Step 1: Governance Authorization

- [ ] Document reason for point-in-time recovery
- [ ] Obtain governance approval
- [ ] Record authorizing party and timestamp

### Step 2: Identify Recovery Point

- [ ] Identify target sequence number or timestamp
- [ ] Document events that will be lost
- [ ] Confirm this is acceptable

### Step 3: Execute Recovery

- [ ] Follow Full Disaster Recovery using backup from before target point
- [ ] OR use database point-in-time recovery if available

### Step 4: Document Data Loss

- [ ] List all events that were not recovered
- [ ] Create constitutional event documenting the recovery
- [ ] Notify affected parties

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Hash chain integrity failure | System Architect + Governance | [TBD] |
| No valid backup available | Governance Lead + Legal | [TBD] |
| Partial recovery only possible | Governance Lead | [TBD] |
| Recovery taking longer than expected | Operations Lead | [TBD] |

## Rollback

Recovery itself doesn't have rollback, but:

1. If recovery verification fails, do NOT proceed to startup
2. Try alternative backup if available
3. Document all attempts
4. Escalate if no valid backup can be restored

## References

- [Backup Procedures](backup.md)
- [Startup Procedures](startup.md)
- [Event Store Operations](epic-1-event-store.md)
- [Halt & Fork Recovery](epic-3-halt-fork.md)
- [Incident Response](incident-response.md)
- Architecture: ADR-1 (Event Store Topology)
