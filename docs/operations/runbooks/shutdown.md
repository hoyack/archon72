# Shutdown Procedures

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for gracefully shutting down the Archon 72 Conclave Backend services while preserving data integrity and constitutional guarantees.

## Prerequisites

- [ ] Access to deployment environment
- [ ] Notification sent to stakeholders (if planned maintenance)
- [ ] No active deliberations in progress (preferred)
- [ ] Backup completed (recommended)

## Trigger Conditions

When to execute this runbook:

- Planned maintenance window
- Infrastructure migration
- Security patch requiring restart
- Emergency shutdown (see escalation)

## Procedure

### Step 1: Pre-Shutdown Assessment

#### Operational Check

- [ ] Check current request rate and active connections
- [ ] Verify no long-running operations in progress
- [ ] Confirm backup is recent (<24 hours or run new backup)

#### Constitutional Check

- [ ] Check if deliberation is in progress
- [ ] Verify no pending witnessed events awaiting confirmation
- [ ] Document current halt state

**Verification:**

- Expected outcome: Safe to proceed with shutdown
- Command to verify: `curl http://localhost:8000/health` and check logs

### Step 2: Stop Accepting New Requests

- [ ] Update load balancer to stop routing traffic
- [ ] Set service to "draining" mode if supported
- [ ] Wait for in-flight requests to complete (timeout: 30s)

**Verification:**

- Expected outcome: No new requests being accepted
- Command to verify: Check access logs for new requests

### Step 3: Complete In-Progress Operations

#### Constitutional Operations

- [ ] Allow any in-progress event writes to complete
- [ ] Ensure witness attestations are finalized
- [ ] Complete any pending hash chain updates

**Warning:** Do NOT interrupt constitutional writes. Wait for completion or timeout.

#### Operational Operations

- [ ] Allow health checks to complete
- [ ] Drain any queued metrics

**Verification:**

- Expected outcome: All pending operations complete or timeout
- Timeout: 60 seconds for constitutional, 30 seconds for operational

### Step 4: Stop API Service

- [ ] Send graceful shutdown signal (SIGTERM)
- [ ] Wait for process to exit (timeout: 30s)
- [ ] If not responding, use SIGKILL (last resort)

**Verification:**

- Expected outcome: Process exits cleanly
- Command to verify: `ps aux | grep uvicorn` shows no processes

### Step 5: Verify Data Integrity

Before stopping persistence layers:

- [ ] Verify last event in event store has valid hash
- [ ] Check Redis has no uncommitted data
- [ ] Confirm no orphaned locks

**Verification:**

- Expected outcome: Data is consistent
- SQL to verify: `SELECT id, hash FROM events ORDER BY sequence_number DESC LIMIT 1;`

### Step 6: Stop Redis (If Required)

- [ ] Trigger Redis BGSAVE for persistence
- [ ] Wait for save to complete
- [ ] Stop Redis service

**Verification:**

- Expected outcome: Redis data persisted
- Command to verify: Check Redis logs for "Background saving terminated with success"

### Step 7: Stop Database (If Required)

- [ ] Ensure no active connections remain
- [ ] Stop PostgreSQL/Supabase service

**Verification:**

- Expected outcome: Database stops cleanly
- Command to verify: Check database logs for clean shutdown

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Cannot complete in-flight constitutional writes | System Architect | [TBD] |
| Data integrity check fails | System Architect + DBA | [TBD] |
| Service won't stop gracefully | Operations Lead | [TBD] |
| Emergency shutdown required | On-Call + System Architect | [TBD] |

## Rollback

Shutdown is generally not "rolled back" but if issues occur:

1. If data integrity fails, do NOT proceed with DB shutdown
2. Document the state for investigation
3. Consider keeping database running for forensics
4. Follow [Recovery](recovery.md) runbook for restart

## Emergency Shutdown

For emergencies requiring immediate shutdown:

1. **Document the reason** before proceeding
2. Stop API service immediately (SIGKILL if needed)
3. Accept potential data loss for in-flight operations
4. Follow [Incident Response](incident-response.md)
5. Full integrity check required on next startup

## References

- [Startup Procedures](startup.md)
- [Recovery Procedures](recovery.md)
- [Event Store Operations](epic-1-event-store.md)
- [Backup Procedures](backup.md)
