# Agent Deliberation Monitoring

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for monitoring and troubleshooting the 72-agent deliberation system, including heartbeat monitoring, context bundle verification, and dissent health tracking.

## Prerequisites

- [ ] Access to monitoring dashboards
- [ ] Understanding of deliberation flow
- [ ] Access to agent logs

## Trigger Conditions

When to execute this runbook:

- Agent heartbeat missed
- Deliberation timeout
- Context bundle validation failure
- Dissent health degradation
- No-preview constraint violation detected

## Procedure

### Agent Heartbeat Monitoring

72 agents must maintain heartbeats during active deliberation.

#### Step 1: Check Heartbeat Status

- [ ] View heartbeat dashboard
- [ ] Identify any agents with missed heartbeats
- [ ] Check timing of last heartbeat

```sql
-- Check heartbeat status for all agents
SELECT
    agent_id,
    last_heartbeat,
    NOW() - last_heartbeat as time_since_heartbeat,
    CASE
        WHEN NOW() - last_heartbeat > INTERVAL '30 seconds' THEN 'MISSED'
        WHEN NOW() - last_heartbeat > INTERVAL '15 seconds' THEN 'WARNING'
        ELSE 'OK'
    END as status
FROM agent_heartbeats
ORDER BY last_heartbeat ASC;
```

**Verification:**

- Expected outcome: All 72 agents have heartbeat within 30 seconds
- MISSED status: Agent may be unresponsive

#### Step 2: Investigate Missed Heartbeat

If an agent has missed heartbeat:

1. Check agent logs for errors
2. Verify agent process is running
3. Check network connectivity
4. Check resource utilization (CPU/memory)

```bash
# Check agent logs
kubectl logs -l app=archon-agent,agent-id=$AGENT_ID --tail=100

# Check agent process
kubectl get pods -l app=archon-agent,agent-id=$AGENT_ID
```

#### Step 3: Agent Recovery

**If agent is recoverable:**
- Restart agent process
- Monitor for heartbeat resumption
- Log incident

**If agent cannot recover:**
- Document agent failure
- Create `AgentUnresponsiveEvent`
- Deliberation may proceed with remaining agents (quorum rules apply)

---

### Deliberation Monitoring

#### Active Deliberation Status

- [ ] Check current deliberation state
- [ ] Verify all participating agents
- [ ] Monitor progress

```sql
-- Current deliberation status
SELECT
    d.id,
    d.topic,
    d.started_at,
    d.status,
    COUNT(dp.agent_id) as participating_agents
FROM deliberations d
LEFT JOIN deliberation_participants dp ON dp.deliberation_id = d.id
WHERE d.status = 'in_progress'
GROUP BY d.id;
```

#### Deliberation Timeout

If deliberation exceeds expected duration:

1. Check for agent bottlenecks
2. Verify no agents are stuck
3. Check resource availability

**Timeout thresholds:**
- Standard deliberation: 5 minutes warning, 10 minutes critical
- Complex deliberation: 15 minutes warning, 30 minutes critical

---

### Context Bundle Verification

Context bundles capture deliberation inputs and must be signed.

#### Step 1: Verify Bundle Integrity

- [ ] Check bundle signature is valid
- [ ] Verify all required inputs are present
- [ ] Confirm bundle hash matches

```sql
-- Check context bundle status
SELECT
    cb.id,
    cb.deliberation_id,
    cb.created_at,
    cb.signature_valid,
    cb.hash
FROM context_bundles cb
WHERE cb.deliberation_id = $DELIBERATION_ID;
```

#### Step 2: Bundle Validation Failure

If a context bundle fails validation:

1. Check which validation failed (signature, completeness, hash)
2. Examine bundle contents
3. Check signing key validity

**Response:**
- Invalid bundle = deliberation cannot proceed
- Create event documenting failure
- Escalate for investigation

---

### Dissent Health Monitoring

Healthy deliberation includes appropriate levels of dissent (diversity of opinion).

#### Step 1: Check Dissent Metrics

- [ ] View dissent health dashboard
- [ ] Check dissent rate over time
- [ ] Identify any anomalies

```sql
-- Dissent health metrics (last 24 hours)
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as total_votes,
    SUM(CASE WHEN vote = 'dissent' THEN 1 ELSE 0 END) as dissents,
    ROUND(100.0 * SUM(CASE WHEN vote = 'dissent' THEN 1 ELSE 0 END) / COUNT(*), 2) as dissent_rate
FROM deliberation_votes
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;
```

#### Step 2: Dissent Anomaly Response

**Low dissent rate (< 5%):**
- May indicate groupthink or agent compromise
- Escalate for governance review
- Check for topic manipulation

**High dissent rate (> 50%):**
- May indicate contentious topic or agent issues
- Review topic origin
- Check for manipulation attempts

---

### No-Preview Constraint Enforcement

Agents must not see other agent outputs before providing their own input (FR9).

#### Step 1: Verify No-Preview

- [ ] Check deliberation isolation is active
- [ ] Verify no cross-agent data leakage
- [ ] Audit recent deliberations

```sql
-- Check for potential preview violations
SELECT
    d.id,
    d.topic,
    dp.agent_id,
    dp.input_submitted_at,
    dp.first_output_viewed_at
FROM deliberations d
JOIN deliberation_participants dp ON dp.deliberation_id = d.id
WHERE dp.first_output_viewed_at < dp.input_submitted_at;
-- Expected: 0 rows (no agent viewed output before submitting input)
```

#### Step 2: Preview Violation Response

If a preview violation is detected:

1. **HALT the affected deliberation**
2. Create `NoPreviewViolationEvent`
3. Invalidate affected outputs
4. Escalate to governance

---

### Collective Output Verification

All 72 agent outputs must be combined without modification (FR10-11).

#### Step 1: Verify Output Integrity

- [ ] Check all agents contributed
- [ ] Verify no outputs were modified
- [ ] Confirm collective output hash

```sql
-- Verify collective output completeness
SELECT
    co.deliberation_id,
    co.agent_count,
    co.hash,
    COUNT(ao.id) as actual_outputs
FROM collective_outputs co
JOIN agent_outputs ao ON ao.collective_output_id = co.id
GROUP BY co.deliberation_id, co.agent_count, co.hash
HAVING COUNT(ao.id) != 72;
-- Expected: 0 rows (all collective outputs have 72 agent outputs)
```

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| >10% agents unresponsive | System Architect | [TBD] |
| No-preview violation | Governance Lead | [TBD] |
| Context bundle invalid | System Architect | [TBD] |
| Dissent health anomaly | Governance Lead | [TBD] |
| Collective output tampered | Governance + Security | [TBD] |

## Rollback

Deliberation issues generally don't support rollback. Instead:

1. Invalid deliberation outputs are not recorded
2. Document issues as constitutional events
3. Re-run deliberation if needed

## Constitutional Reminders

- **FR9:** No Preview - agents cannot see others' outputs first
- **FR10-11:** Collective output must combine all 72 agents
- **FR12-14:** Dissent must be tracked and visible
- **CT-11:** CHECK HALT STATE before writes

## References

- [Event Store Operations](epic-1-event-store.md)
- [Operational Monitoring](epic-8-monitoring.md)
- Architecture: ADR-2 (Context Reconstruction + Signature Trust)
- Epic 2: Agent Deliberation stories
