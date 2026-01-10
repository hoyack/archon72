# Operations Documentation

This directory contains operational documentation for the Archon 72 Conclave Backend, including runbooks for all critical procedures.

## Quick Links

### Runbooks

**[Runbook Index](runbooks/index.md)** - Complete index of all operational runbooks with quick reference by severity and scenario.

### Core Documents

| Document | Purpose |
|----------|---------|
| [Runbook Index](runbooks/index.md) | Navigation hub for all runbooks |
| [External Monitoring Setup](external-monitoring-setup.md) | Configure external health monitoring |

## Runbook Summary

### Core Operational Runbooks

| Runbook | When to Use |
|---------|-------------|
| [Startup](runbooks/startup.md) | Starting the system |
| [Shutdown](runbooks/shutdown.md) | Graceful shutdown |
| [Scaling](runbooks/scaling.md) | Horizontal scaling |
| [Backup](runbooks/backup.md) | Data backup procedures |
| [Recovery](runbooks/recovery.md) | Disaster recovery |

### Epic-Specific Runbooks

| Epic | Runbook | Focus |
|------|---------|-------|
| 0 | [Developer Environment](runbooks/epic-0-dev-environment.md) | Dev setup, HSM, pre-commit |
| 1 | [Event Store Operations](runbooks/epic-1-event-store.md) | Hash chain, witnesses |
| 2 | [Deliberation Monitoring](runbooks/epic-2-deliberation.md) | 72 agents, heartbeats |
| 3 | [Halt & Fork Recovery](runbooks/epic-3-halt-fork.md) | Halt handling, fork detection |
| 4 | [Observer API Operations](runbooks/epic-4-observer.md) | 99.9% SLA, verification |
| 5 | [Keeper Operations](runbooks/epic-5-keeper.md) | Override logging, keys |
| 6 | [Breach Detection](runbooks/epic-6-breach.md) | 7-day escalation |
| 7 | [Cessation Procedures](runbooks/epic-7-cessation.md) | Irreversible shutdown |
| 8 | [Operational Monitoring](runbooks/epic-8-monitoring.md) | Metrics, complexity budget |
| 9 | [Emergence Audit](runbooks/epic-9-emergence-audit.md) | Quarterly audits, remediation |

### Cross-Cutting

| Runbook | When to Use |
|---------|-------------|
| [Incident Response](runbooks/incident-response.md) | Any incident |

## Constitutional vs Operational

**CRITICAL DISTINCTION:** This documentation maintains separation between:

- **Operational concerns** - System availability, performance, resources
- **Constitutional concerns** - Governance integrity, breach handling, cessation

### Quick Reference

| Concern | Routes To | Examples |
|---------|-----------|----------|
| Operational | Operations Team | API down, high latency, scaling |
| Constitutional | Governance Team | Breach, halt, override, cessation |

Both types are documented in runbooks but have different escalation paths and procedures.

## Severity Levels

| Severity | Response Time | Examples |
|----------|---------------|----------|
| **CRITICAL** | Immediate | Cessation, data corruption, security breach |
| **HIGH** | 15 minutes | Halt, fork, >3 overrides, SLA breach |
| **MEDIUM** | 1 hour | Performance degradation, warning threshold |
| **LOW** | Next business day | Minor issues, non-urgent fixes |

## On-Call Information

### Contacts

| Role | Responsibility | Contact |
|------|---------------|---------|
| On-Call Operator | First responder | [TBD] |
| Operations Lead | Operational escalation | [TBD] |
| System Architect | Technical escalation | [TBD] |
| Governance Lead | Constitutional matters | [TBD] |
| Security Lead | Security incidents | [TBD] |
| Legal Counsel | Compliance/cessation | [TBD] |

### Escalation

See [Incident Response](runbooks/incident-response.md) for full escalation matrix.

## Runbook Template

New runbooks should follow: [TEMPLATE.md](runbooks/TEMPLATE.md)

## Related Documentation

- [Architecture Decision Records](../adr/) - Architectural context
- [API Documentation](../api/) - API reference
- [Development Guide](../development/) - Developer documentation

---

Last Updated: 2026-01-08
