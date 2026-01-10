# Observer API Operations

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for operating and monitoring the Observer API, which provides public read access to the constitutional record with 99.9% uptime SLA.

## Prerequisites

- [ ] Access to Observer API monitoring
- [ ] External monitoring tool access
- [ ] Understanding of verification toolkit

## Trigger Conditions

When to execute this runbook:

- Observer API availability drops below SLA
- Verification toolkit issues reported
- Push notification failures
- Query performance degradation
- Sequence gap reported by observer

## Procedure

### Uptime SLA Monitoring (99.9%)

99.9% uptime = maximum 8.76 hours downtime per year.

#### Step 1: Check Current SLA Status

- [ ] Review uptime metrics
- [ ] Check external monitoring status
- [ ] Verify geographic redundancy (if configured)

```sql
-- Check Observer API uptime (last 30 days)
SELECT
    DATE_TRUNC('day', timestamp) as day,
    COUNT(*) as total_checks,
    SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_checks,
    ROUND(100.0 * SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) / COUNT(*), 3) as uptime_pct
FROM observer_health_checks
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY day
ORDER BY day;
```

**Verification:**

- Expected outcome: >99.9% uptime per day
- Track: Monthly and annual uptime percentage

#### Step 2: SLA Breach Response

If uptime drops below 99.9%:

1. Identify root cause of downtime
2. Document in incident report
3. Implement preventive measures
4. Communicate with observers

---

### Observer API Health Check

#### Step 1: Verify API Endpoints

- [ ] Check `/observer/health` endpoint
- [ ] Verify `/observer/events` returns data
- [ ] Test hash verification endpoint

```bash
# Health check
curl -w "%{http_code}" http://localhost:8000/observer/health

# Events query
curl http://localhost:8000/observer/events?limit=10

# Hash verification
curl http://localhost:8000/observer/verify/hash/$HASH
```

**Verification:**

- Expected outcome: All endpoints return 200 OK
- Response time: <500ms for health, <5s for queries

#### Step 2: External Accessibility

- [ ] Verify API is accessible from external networks
- [ ] Check SSL/TLS certificate validity
- [ ] Test from multiple geographic locations

---

### Public Read Access Verification

Observer API provides public read access without authentication (FR44).

#### Step 1: Verify No Auth Required

- [ ] Test anonymous access
- [ ] Verify all read endpoints are public
- [ ] Confirm write operations are blocked

```bash
# Anonymous access should work
curl http://localhost:8000/observer/events?limit=1
# Expected: 200 OK with events

# Write should fail
curl -X POST http://localhost:8000/observer/events \
  -H "Content-Type: application/json" \
  -d '{"type": "test"}'
# Expected: 405 Method Not Allowed or 403 Forbidden
```

---

### Verification Toolkit Support

The open-source verification toolkit allows observers to verify the constitutional record.

#### Step 1: Toolkit Compatibility Check

- [ ] Verify API returns data in toolkit-compatible format
- [ ] Check hash format matches toolkit expectations
- [ ] Test Merkle proof generation

```bash
# Get events with hashes
curl http://localhost:8000/observer/events?include_hash=true

# Get Merkle proof for event
curl http://localhost:8000/observer/merkle-proof/$EVENT_ID
```

#### Step 2: Toolkit Issue Response

If observers report toolkit issues:

1. Reproduce issue with toolkit
2. Check API response format
3. Verify hash computation matches
4. Update documentation if needed

---

### Push Notification Operations

Observers can subscribe to push notifications for new events.

#### Step 1: Check Notification System

- [ ] Verify notification queue is processing
- [ ] Check subscriber list
- [ ] Monitor delivery success rate

```sql
-- Check notification delivery stats
SELECT
    DATE_TRUNC('hour', sent_at) as hour,
    COUNT(*) as total,
    SUM(CASE WHEN delivered THEN 1 ELSE 0 END) as delivered,
    ROUND(100.0 * SUM(CASE WHEN delivered THEN 1 ELSE 0 END) / COUNT(*), 2) as delivery_rate
FROM observer_notifications
WHERE sent_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;
```

#### Step 2: Notification Failure Response

If delivery rate drops:

1. Check webhook endpoints are responding
2. Verify notification payload format
3. Check rate limiting isn't blocking
4. Contact observers with persistent failures

---

### Query Performance

Observer queries must meet performance SLA (FR106).

#### Step 1: Monitor Query Performance

- [ ] Check p50, p95, p99 latencies
- [ ] Identify slow queries
- [ ] Verify index usage

```sql
-- Query performance stats
SELECT
    query_type,
    COUNT(*) as count,
    ROUND(AVG(duration_ms), 2) as avg_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms), 2) as p95_ms,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms), 2) as p99_ms
FROM observer_query_log
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY query_type;
```

**SLA Requirement (FR106):** Queries for <10,000 events must complete in <30 seconds.

#### Step 2: Performance Degradation Response

If queries exceed SLA:

1. Check database load
2. Verify indexes are being used
3. Check for table bloat
4. Consider query optimization or caching

---

### Sequence Gap Detection for Observers

Observers may detect gaps in the event sequence they receive.

#### Step 1: Verify Gap Report

- [ ] Confirm gap exists in observer's view
- [ ] Check if gap exists in primary database
- [ ] Verify no replication lag

```sql
-- Check for gaps in sequence
SELECT
    sequence_number,
    LAG(sequence_number) OVER (ORDER BY sequence_number) as prev_seq
FROM events
WHERE sequence_number BETWEEN $START AND $END
HAVING sequence_number - prev_seq > 1;
```

#### Step 2: Gap Response

**If gap in primary DB:**
- Follow [Event Store Operations](epic-1-event-store.md) for investigation

**If gap only in observer view:**
- Check replication status
- Verify observer's cache isn't stale
- Provide direct query endpoint for gap range

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| SLA breach (>0.1% downtime) | Operations Lead | [TBD] |
| Verification toolkit incompatibility | System Architect | [TBD] |
| Sequence gap confirmed | System Architect | [TBD] |
| Performance SLA breach | System Architect | [TBD] |

## Rollback

Observer API issues generally don't require rollback. Instead:

1. Fix the underlying issue
2. Clear any caches
3. Notify affected observers
4. Document in incident report

## Constitutional Reminders

- **FR44-50:** Observer interface requirements
- **RT-5:** 99.9% SLA with external monitoring
- **FR106:** Query performance SLA
- Observer API is READ-ONLY - never accept writes

## References

- [Event Store Operations](epic-1-event-store.md)
- [Operational Monitoring](epic-8-monitoring.md)
- [External Monitoring Setup](../external-monitoring-setup.md)
- Architecture: ADR-8 (Observer Consistency + Genesis Anchor)
- Epic 4: Observer Verification Interface stories
