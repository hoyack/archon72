# Backup Procedures

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for backing up the Archon 72 Conclave Backend data, including the append-only event store, configuration, and operational data.

## Prerequisites

- [ ] Access to database with backup permissions
- [ ] Backup storage location available and writable
- [ ] Sufficient storage space for backup (estimate: 2x current DB size)
- [ ] Backup encryption keys available

## Trigger Conditions

When to execute this runbook:

- Scheduled daily backup (automated)
- Before major deployment or migration
- Before scaling operations
- After significant data ingestion
- Before maintenance window

## Procedure

### Step 1: Pre-Backup Assessment

#### Operational Check

- [ ] Verify backup storage is available
- [ ] Check available disk space
- [ ] Confirm no other backup is running

#### Constitutional Check

- [ ] Note current event store sequence number
- [ ] Document current hash chain head
- [ ] Record halt state at backup time

**Verification:**

- Expected outcome: Ready to proceed with backup
- SQL to verify: `SELECT MAX(sequence_number), hash FROM events ORDER BY sequence_number DESC LIMIT 1;`

### Step 2: Event Store Backup (Constitutional Data)

The event store is the most critical data - it contains the constitutional record.

#### Option A: PostgreSQL pg_dump

```bash
# Full backup of event store
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME \
  -t events -t witnesses -t halt_state -t key_registry \
  -F c -f backup_events_$(date +%Y%m%d_%H%M%S).dump
```

#### Option B: Supabase Backup

- [ ] Use Supabase dashboard for point-in-time recovery
- [ ] Or use pg_dump against Supabase connection string

#### Backup Verification

- [ ] Verify backup file was created
- [ ] Check backup file size is reasonable
- [ ] Verify backup file checksum

**Verification:**

- Expected outcome: Backup file exists with valid checksum
- Command to verify: `ls -la backup_*.dump && sha256sum backup_*.dump`

### Step 3: Configuration Backup

- [ ] Backup environment configuration (sanitized - no secrets)
- [ ] Backup Kubernetes/Docker configurations
- [ ] Backup load balancer configuration

```bash
# Example: Backup configs
tar -czf config_backup_$(date +%Y%m%d).tar.gz \
  --exclude='*.env' \
  --exclude='*secrets*' \
  configs/
```

**Verification:**

- Expected outcome: Configuration backup created
- Command to verify: `tar -tzf config_backup_*.tar.gz`

### Step 4: Redis Backup (Operational Data)

Redis contains operational state and caches.

```bash
# Trigger Redis background save
redis-cli BGSAVE

# Wait for completion
redis-cli LASTSAVE

# Copy RDB file
cp /var/lib/redis/dump.rdb backup_redis_$(date +%Y%m%d_%H%M%S).rdb
```

**Verification:**

- Expected outcome: Redis RDB file backed up
- Command to verify: `ls -la backup_redis_*.rdb`

### Step 5: Transfer to Offsite Storage

- [ ] Encrypt backup files
- [ ] Transfer to offsite/cloud storage
- [ ] Verify transfer completed successfully
- [ ] Update backup inventory

```bash
# Example: Encrypt and upload
gpg --encrypt --recipient backup@archon72 backup_events_*.dump
aws s3 cp backup_events_*.dump.gpg s3://archon72-backups/$(date +%Y/%m/%d)/
```

**Verification:**

- Expected outcome: Backup available in offsite storage
- Command to verify: `aws s3 ls s3://archon72-backups/$(date +%Y/%m/%d)/`

### Step 6: Document Backup

- [ ] Record backup in backup log
- [ ] Include: timestamp, sequence number, hash chain head, file sizes, storage location
- [ ] Update retention schedule

## Backup Retention

| Type | Retention | Storage |
|------|-----------|---------|
| Daily | 7 days | Local + Cloud |
| Weekly | 4 weeks | Cloud |
| Monthly | 12 months | Cloud (archive tier) |
| Yearly | Indefinite | Cold storage |

**Constitutional Requirement:** Event store backups must be retained indefinitely for audit purposes.

## Automated Backup Schedule

```cron
# Daily backup at 2 AM UTC
0 2 * * * /opt/archon72/scripts/backup.sh daily

# Weekly backup on Sunday at 3 AM UTC
0 3 * * 0 /opt/archon72/scripts/backup.sh weekly
```

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Backup fails | Operations Lead | [TBD] |
| Insufficient storage | Infrastructure Team | [TBD] |
| Backup integrity check fails | System Architect | [TBD] |
| Cannot access offsite storage | Infrastructure Team | [TBD] |

## Rollback

Backup procedures don't typically need rollback, but if issues occur:

1. Do NOT delete failed backup files until investigated
2. Check disk space and clear if needed
3. Retry backup after resolving issue
4. If backup consistently fails, escalate

## Restore Preview

To verify backup integrity without full restore:

```bash
# List contents of PostgreSQL backup
pg_restore -l backup_events_*.dump

# Verify event count matches expected
pg_restore -d temp_restore_db backup_events_*.dump
psql -d temp_restore_db -c "SELECT COUNT(*) FROM events;"
```

## References

- [Recovery Procedures](recovery.md)
- [Event Store Operations](epic-1-event-store.md)
- [Shutdown Procedures](shutdown.md) - for consistent backups
- Architecture: ADR-1 (Event Store Topology)
