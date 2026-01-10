# Scaling Procedures

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team

## Purpose

Procedures for horizontally scaling the Archon 72 Conclave Backend to handle increased load while maintaining constitutional guarantees.

## Prerequisites

- [ ] Access to deployment/orchestration platform
- [ ] Load balancer configuration access
- [ ] Monitoring dashboards available
- [ ] No active halt state (scaling during halt requires governance approval)

## Trigger Conditions

When to execute this runbook:

- Request latency exceeds SLA (p99 > 500ms)
- CPU utilization > 70% sustained
- Memory utilization > 80% sustained
- Planned capacity increase for expected load
- Early warning alert from failure prevention system

## Procedure

### Step 1: Assess Current State

#### Operational Check

- [ ] Check current instance count
- [ ] Review CPU/memory metrics across all instances
- [ ] Check request latency percentiles (p50, p95, p99)
- [ ] Review error rates

#### Constitutional Check

- [ ] Verify system is not in halt state
- [ ] Check complexity budget (CT-14) - scaling adds operational complexity
- [ ] Document scaling decision rationale

**Verification:**

- Expected outcome: Clear understanding of current load and reason for scaling
- Command to verify: Review Prometheus/Grafana dashboards

### Step 2: Pre-Scaling Validation

- [ ] Verify database can handle additional connections
- [ ] Check Redis connection pool capacity
- [ ] Ensure load balancer can route to new instances
- [ ] Verify container/VM quota allows scaling

**Verification:**

- Expected outcome: Infrastructure can support additional instances
- Check: Database max_connections, Redis maxclients

### Step 3: Scale API Instances

#### For Container Orchestration (Kubernetes/Docker Swarm)

- [ ] Update replica count in deployment configuration
- [ ] Apply configuration change
- [ ] Wait for new instances to become ready

```bash
# Example: Kubernetes
kubectl scale deployment archon72-api --replicas=N

# Example: Docker Compose
docker-compose up -d --scale api=N
```

#### For VM-Based Deployment

- [ ] Provision new VM(s)
- [ ] Deploy application to new instance(s)
- [ ] Configure and start service
- [ ] Add to load balancer

**Verification:**

- Expected outcome: New instances are running and healthy
- Command to verify: `kubectl get pods` or equivalent

### Step 4: Verify New Instances

#### Operational Check

- [ ] New instances pass health checks
- [ ] New instances appear in `/ready` endpoint
- [ ] Load balancer is routing traffic to new instances

#### Constitutional Check

- [ ] New instances can access HSM/signing keys
- [ ] New instances see consistent halt state
- [ ] Hash chain queries return consistent results across instances

**Verification:**

- Expected outcome: All instances operational and consistent
- Command to verify: `curl http://<new-instance>:8000/ready`

### Step 5: Monitor Post-Scaling

- [ ] Watch latency metrics for improvement
- [ ] Verify error rates remain stable or decrease
- [ ] Check that load is distributed across instances
- [ ] Monitor for any consistency issues

**Verification:**

- Expected outcome: Improved performance, no errors
- Duration: Monitor for at least 15 minutes

### Step 6: Document Scaling Event

- [ ] Record scaling event in operational log
- [ ] Update capacity documentation
- [ ] If scaling was reactive, create follow-up for capacity planning

## Scaling Down

When reducing capacity:

### Step 1: Pre-Scale-Down Checks

- [ ] Verify current load can be handled by fewer instances
- [ ] Ensure no instance is handling critical long-running operations

### Step 2: Drain Instance

- [ ] Mark instance for removal in load balancer
- [ ] Wait for in-flight requests to complete
- [ ] Follow [Shutdown Procedures](shutdown.md) for the instance

### Step 3: Remove Instance

- [ ] Remove from load balancer
- [ ] Terminate instance
- [ ] Update documentation

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Cannot scale due to infrastructure limits | Infrastructure Team | [TBD] |
| Scaling during halt state | Governance Lead | [TBD] |
| Consistency issues after scaling | System Architect | [TBD] |
| Performance not improving after scaling | System Architect | [TBD] |

## Rollback

If scaling causes issues:

1. Stop routing traffic to problematic instances
2. Investigate logs on new instances
3. If constitutional issues detected, halt system and investigate
4. Scale back to known-good configuration
5. Follow [Incident Response](incident-response.md) if needed

## Constitutional Considerations

**Important:** Scaling is an operational decision but has constitutional implications:

1. **All instances must see consistent halt state** - Use database/Redis as source of truth
2. **Hash chain must remain consistent** - Event writes are serialized at database level
3. **Witness attestations must work** - All instances need key access
4. **CT-14 Complexity Budget** - Document scaling as operational complexity

## References

- [Operational Monitoring](epic-8-monitoring.md)
- [Startup Procedures](startup.md)
- [Shutdown Procedures](shutdown.md)
- Architecture: ADR-10 (Constitutional Health)
