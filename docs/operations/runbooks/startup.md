# Startup Procedures

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for starting the Archon 72 Conclave Backend services in the correct order with proper verification.

## Prerequisites

- [ ] Access to deployment environment
- [ ] Database credentials available
- [ ] Redis connection details available
- [ ] HSM/signing keys accessible
- [ ] No active halt state (or intentional restart during halt)

## Trigger Conditions

When to execute this runbook:

- Initial deployment
- After maintenance window
- After system crash/recovery
- After infrastructure changes

## Procedure

### Step 1: Pre-Flight Checks

#### Operational Check

- [ ] Verify infrastructure is available (VMs, containers, network)
- [ ] Confirm database server is running and accessible
- [ ] Confirm Redis server is running and accessible
- [ ] Check disk space on all nodes (>20% free)

**Verification:**

- Expected outcome: All infrastructure components respond
- Command to verify: `make health-check-infra` (if available) or manual ping

#### Constitutional Check

- [ ] Query current halt state from database
- [ ] If halt state is ACTIVE, document reason for restart
- [ ] Verify no pending cessation flag

**Verification:**

- Expected outcome: Halt state is known and documented
- SQL to verify: `SELECT * FROM halt_state ORDER BY created_at DESC LIMIT 1;`

### Step 2: Start Database Layer

- [ ] Ensure PostgreSQL/Supabase is running
- [ ] Verify database migrations are applied
- [ ] Check event store table integrity

**Verification:**

- Expected outcome: Database accepts connections, tables exist
- Command to verify: `make db-check` or `psql -c "\dt"`

### Step 3: Start Redis Layer

- [ ] Ensure Redis is running
- [ ] Verify Redis persistence is configured
- [ ] Check Redis memory usage

**Verification:**

- Expected outcome: Redis responds to PING
- Command to verify: `redis-cli ping`

### Step 4: Start API Service

- [ ] Start FastAPI application
- [ ] Wait for pre-operational verification to complete
- [ ] Monitor startup logs for errors

**Verification:**

- Expected outcome: API starts without errors, pre-op verification passes
- Command to verify: `curl http://localhost:8000/health`

### Step 5: Verify Pre-Operational Checks (FR105)

The API performs automatic pre-operational verification on startup:

- [ ] DB connectivity check passes
- [ ] Key availability check passes
- [ ] Halt state check completes (not necessarily clear)
- [ ] Hash chain integrity verified

**Verification:**

- Expected outcome: `/ready` endpoint returns 200
- Command to verify: `curl http://localhost:8000/ready`

### Step 6: Post-Startup Validation

#### Operational Check

- [ ] Verify `/metrics` endpoint is serving Prometheus metrics
- [ ] Check log aggregation is receiving logs
- [ ] Confirm external monitoring sees the service

#### Constitutional Check

- [ ] Verify hash chain is continuous (no gaps)
- [ ] Confirm witness pool is available
- [ ] Check agent signing capability

**Verification:**

- Expected outcome: All checks pass
- Command to verify: `make post-startup-check` or manual API calls

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Pre-op verification fails | System Architect | [TBD] |
| Hash chain integrity failure | System Architect + Governance | [TBD] |
| Cannot clear halt state | Governance Lead | [TBD] |
| Database corruption detected | DBA + System Architect | [TBD] |

## Rollback

If startup fails:

1. Stop API service immediately
2. Check logs for specific failure reason
3. Do NOT retry startup until root cause identified
4. If database issue, do NOT attempt migrations
5. Escalate per table above

## References

- [Pre-Operational Verification](epic-8-monitoring.md)
- [Event Store Operations](epic-1-event-store.md)
- [Halt & Fork Recovery](epic-3-halt-fork.md)
- Architecture: ADR-10 (Constitutional Health)
