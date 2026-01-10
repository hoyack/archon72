# Operational Monitoring & Incident Response

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for operational monitoring, complexity budget tracking, and responding to operational alerts while maintaining the critical separation between operational and constitutional health.

## Prerequisites

- [ ] Access to monitoring dashboards
- [ ] Access to Prometheus/Grafana
- [ ] Understanding of operational vs constitutional distinction
- [ ] Access to alerting system

## Trigger Conditions

When to execute this runbook:

- Operational alert fired
- Performance degradation detected
- Complexity budget warning
- Early warning from failure prevention system
- Query performance SLA breach

## Procedure

### Operational vs Constitutional Distinction

**CRITICAL:** Always distinguish between:

- **Operational metrics:** Uptime, latency, error rate, resource utilization
- **Constitutional metrics:** Breach count, override rate, dissent health, witness coverage

**Rule:** Operational issues route to Operations. Constitutional issues route to Governance.

```
┌─────────────────────────────────────────────────────────┐
│ Is the issue affecting system performance/availability? │
│                           │                             │
│            YES ─────────► OPERATIONAL ─► Ops Team       │
│            NO ──────────► CONSTITUTIONAL ─► Governance  │
└─────────────────────────────────────────────────────────┘
```

---

### Operational Metrics Monitoring (FR51)

#### Step 1: Check System Health Dashboard

- [ ] Review uptime per service
- [ ] Check latency percentiles (p50, p95, p99)
- [ ] Review error rates
- [ ] Check resource utilization

```bash
# Query Prometheus metrics
curl http://localhost:9090/api/v1/query?query=up
curl http://localhost:9090/api/v1/query?query=http_request_duration_seconds_bucket
curl http://localhost:9090/api/v1/query?query=http_requests_total{status=~"5.."}
```

#### Step 2: Health Endpoint Verification

- [ ] Check `/health` endpoint
- [ ] Check `/ready` endpoint
- [ ] Verify dependency checks pass

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status": "healthy", ...}

# Ready check
curl http://localhost:8000/ready
# Expected: {"status": "ready", ...}
```

---

### Query Performance Monitoring (FR106)

SLA: Queries for <10,000 events must complete in <30 seconds.

#### Step 1: Check Query Performance

- [ ] Review query latency metrics
- [ ] Identify slow queries
- [ ] Check index usage

```sql
-- Query performance stats
SELECT
    query_type,
    AVG(duration_ms) as avg_ms,
    MAX(duration_ms) as max_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_ms
FROM query_performance_log
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY query_type;
```

#### Step 2: SLA Breach Response

If queries exceed 30-second SLA:

1. Identify specific slow queries
2. Check database explain plans
3. Verify indexes are being used
4. Check for table bloat or lock contention
5. Scale database if resource-constrained

---

### Complexity Budget Dashboard (CT-14)

Track and enforce complexity limits.

#### Step 1: Check Complexity Metrics

- [ ] ADR count (limit: ≤15)
- [ ] Ceremony type count (limit: ≤10)
- [ ] Cross-component dependencies (limit: ≤20)

```sql
-- Complexity budget status
SELECT
    metric_name,
    current_value,
    limit_value,
    CASE
        WHEN current_value > limit_value THEN 'EXCEEDED'
        WHEN current_value > limit_value * 0.8 THEN 'WARNING'
        ELSE 'OK'
    END as status
FROM complexity_budget;
```

#### Step 2: Budget Exceeded Response

If complexity budget exceeded (RT-6):

1. **CONSTITUTIONAL:** Creates ComplexityBudgetBreachEvent
2. Governance ceremony required to proceed
3. Cannot add new complexity until resolved
4. Document what triggered the breach

---

### Early Warning System (FR106-107)

The failure prevention system provides early warnings.

#### Step 1: Check Early Warning Status

- [ ] Review warning dashboard
- [ ] Check for active warnings
- [ ] Review warning history

```sql
-- Active early warnings
SELECT
    warning_id,
    warning_type,
    severity,
    triggered_at,
    threshold_name,
    current_value,
    threshold_value,
    recommended_action
FROM early_warnings
WHERE resolved_at IS NULL
ORDER BY severity DESC, triggered_at DESC;
```

**Severity Levels:**
- **CRITICAL:** Immediate action required
- **HIGH:** Action within 15 minutes
- **MEDIUM:** Action within 1 hour
- **LOW:** Next business day

#### Step 2: Warning Response

For each active warning:

1. Review recommended action
2. Take preventive action
3. Document response
4. Monitor for resolution

---

### Load Shedding Decisions (FR107)

Under extreme load, the system may shed non-critical operations.

#### Step 1: Check Load Status

- [ ] Review current load metrics
- [ ] Check load shedding status
- [ ] Verify constitutional protection

```sql
-- Load shedding status
SELECT
    ls.timestamp,
    ls.load_level,
    ls.shedding_active,
    ls.operations_shed,
    ls.constitutional_operations_protected
FROM load_shedding_log ls
ORDER BY timestamp DESC
LIMIT 10;
```

**CRITICAL (FR107):** Constitutional events are NEVER shed, even under extreme load.

#### Step 2: Load Shedding Active Response

If load shedding is active:

1. Verify constitutional operations are protected
2. Identify cause of high load
3. Scale resources if possible
4. Wait for load to normalize
5. Monitor for data loss in operational telemetry

---

### Incident Report Creation (FR54)

Automatic incident reports for significant events.

#### Triggers for Incident Report

- Halt event
- Fork detection
- >3 overrides in a day
- SLA breach
- Constitutional alert

#### Step 1: Create Incident Report

- [ ] Document timeline
- [ ] Record impact
- [ ] Document response actions
- [ ] Record resolution

```markdown
## Incident Report Template

**Incident ID:** [auto-generated]
**Type:** [halt/fork/override/sla/constitutional]
**Severity:** [critical/high/medium/low]

### Timeline
- [timestamp]: First detection
- [timestamp]: Alert fired
- [timestamp]: Response began
- [timestamp]: Resolution

### Impact
- Systems affected: [list]
- Duration: [time]
- Data loss: [none/description]

### Response
- Actions taken: [list]
- Personnel involved: [list]

### Resolution
- Root cause: [description]
- Fix applied: [description]
- Prevention measures: [list]
```

#### Step 2: Publish Report

- [ ] Internal review complete
- [ ] Redact sensitive operational details
- [ ] Publish within 7 days (FR54)

---

### Structured Logging Operations (NFR27)

#### Step 1: Verify Log Collection

- [ ] Logs are JSON formatted
- [ ] Correlation IDs are present
- [ ] Log aggregation is receiving logs

```bash
# Check log format
tail -1 /var/log/archon72/api.log | jq .
# Expected: Valid JSON with timestamp, level, message, correlation_id

# Verify correlation ID tracking
grep "correlation_id" /var/log/archon72/api.log | head -5
```

#### Step 2: Log Investigation

For investigating issues:

1. Get correlation ID from error
2. Search logs across all services
3. Reconstruct request flow
4. Identify failure point

```bash
# Search by correlation ID
grep "abc123-correlation-id" /var/log/archon72/*.log
```

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Operational alert | Operations Lead | [TBD] |
| Constitutional alert | Governance Lead | [TBD] |
| Query SLA breach | System Architect | [TBD] |
| Complexity budget exceeded | Governance Lead | [TBD] |
| Load shedding active | Operations Lead | [TBD] |

## Rollback

Most operational issues don't require rollback. Instead:

1. Fix the underlying issue
2. Restore service
3. Document in incident report

## Constitutional Reminders

- **FR51-54:** Operational monitoring requirements
- **FR52:** Operational metrics excluded from event store
- **FR105-107:** Scale realism requirements
- **FR107:** Constitutional events NEVER shed
- **ADR-10:** Constitutional vs operational separation

## References

- [Startup Procedures](startup.md)
- [Scaling Procedures](scaling.md)
- [Incident Response](incident-response.md)
- [External Monitoring Setup](../external-monitoring-setup.md)
- Architecture: ADR-10 (Constitutional Health + Operational Governance)
- Epic 8: Operational Monitoring stories
