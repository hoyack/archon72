# Operational Runbooks Index

Last Updated: 2026-01-08
Version: 1.0

## Quick Reference

### By Severity

| Severity | Runbooks |
|----------|----------|
| **CRITICAL** | [Halt & Fork Recovery](epic-3-halt-fork.md), [Cessation Procedures](epic-7-cessation.md) |
| **HIGH** | [Breach Detection](epic-6-breach.md), [Emergence Audit](epic-9-emergence-audit.md), [Incident Response](incident-response.md) |
| **MEDIUM** | [Event Store Recovery](epic-1-event-store.md), [Keeper Operations](epic-5-keeper.md) |
| **LOW** | [Scaling](scaling.md), [Backup](backup.md) |
| **INFO** | [Startup](startup.md), [Shutdown](shutdown.md) |

### By Scenario

| Scenario | Primary Runbook | Related |
|----------|-----------------|---------|
| System won't start | [Startup](startup.md) | [Pre-Op Verification](epic-8-monitoring.md) |
| Halt signal received | [Halt & Fork Recovery](epic-3-halt-fork.md) | [Incident Response](incident-response.md) |
| Fork detected | [Halt & Fork Recovery](epic-3-halt-fork.md) | [Event Store](epic-1-event-store.md) |
| Breach declared | [Breach Detection](epic-6-breach.md) | [Incident Response](incident-response.md) |
| Emergence violation | [Emergence Audit](epic-9-emergence-audit.md) | [Breach Detection](epic-6-breach.md) |
| Quarterly audit due | [Emergence Audit](epic-9-emergence-audit.md) | [Monitoring](epic-8-monitoring.md) |
| Cessation triggered | [Cessation Procedures](epic-7-cessation.md) | [Incident Response](incident-response.md) |
| Agent heartbeat missed | [Deliberation Monitoring](epic-2-deliberation.md) | [Monitoring](epic-8-monitoring.md) |
| Override logged | [Keeper Operations](epic-5-keeper.md) | [Incident Response](incident-response.md) |
| Observer API down | [Observer API](epic-4-observer.md) | [External Monitoring](../external-monitoring-setup.md) |
| Need to scale | [Scaling](scaling.md) | [Monitoring](epic-8-monitoring.md) |
| Disaster recovery | [Recovery](recovery.md) | [Backup](backup.md) |

---

## Core Operational Runbooks

| Runbook | Purpose | Frequency |
|---------|---------|-----------|
| [Startup](startup.md) | Service startup procedures | On deployment |
| [Shutdown](shutdown.md) | Graceful shutdown procedures | On maintenance |
| [Scaling](scaling.md) | Horizontal scaling procedures | As needed |
| [Backup](backup.md) | Database and event store backup | Daily/scheduled |
| [Recovery](recovery.md) | General disaster recovery | Emergency |

---

## Epic-Specific Runbooks

| Epic | Runbook | Focus Area |
|------|---------|------------|
| 0 | [Developer Environment](epic-0-dev-environment.md) | Dev setup, HSM stub, pre-commit |
| 1 | [Event Store Operations](epic-1-event-store.md) | Hash chain, witnesses, DR |
| 2 | [Deliberation Monitoring](epic-2-deliberation.md) | 72 agents, heartbeats, context |
| 3 | [Halt & Fork Recovery](epic-3-halt-fork.md) | Dual-channel halt, 48-hour recovery |
| 4 | [Observer API Operations](epic-4-observer.md) | 99.9% SLA, verification toolkit |
| 5 | [Keeper Operations](epic-5-keeper.md) | Override logging, key ceremonies |
| 6 | [Breach Detection](epic-6-breach.md) | 7-day escalation, witness randomness |
| 7 | [Cessation Procedures](epic-7-cessation.md) | Irreversibility, read-only access |
| 8 | [Operational Monitoring](epic-8-monitoring.md) | Metrics, complexity budget, alerts |
| 9 | [Emergence Audit](epic-9-emergence-audit.md) | Quarterly audits, prohibited language, remediation |

---

## Incident Response

| Runbook | Purpose |
|---------|---------|
| [Incident Response](incident-response.md) | Cross-cutting incident handling procedures |

---

## Constitutional vs Operational

All runbooks clearly distinguish between:

- **Operational procedures** - Affect system performance/availability
- **Constitutional procedures** - Affect governance/integrity guarantees

**Critical Rule (CT-11):** All constitutional procedures must CHECK HALT STATE FIRST before any write operation.

---

## Emergency Contacts

| Role | Responsibility | Contact |
|------|---------------|---------|
| On-Call Operator | First responder | [TBD] |
| System Architect | Escalation for architectural issues | [TBD] |
| Governance Lead | Constitutional/breach matters | [TBD] |
| Legal Counsel | Cessation/compliance matters | [TBD] |

---

## Template

New runbooks should follow: [TEMPLATE.md](TEMPLATE.md)
