# Incident Response

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team + Governance Team

## Purpose

Cross-cutting incident response procedures for handling all types of incidents, from operational issues to constitutional crises. This runbook provides the framework for coordinated response.

## Prerequisites

- [ ] Access to monitoring systems
- [ ] Communication channels configured
- [ ] Escalation contacts available
- [ ] Incident management tool access

## Trigger Conditions

When to execute this runbook:

- Any alert above INFO severity
- User-reported issues
- External monitoring alerts
- Security incidents
- Constitutional events requiring response

## Incident Classification

### By Type

| Type | Description | Primary Owner | Example |
|------|-------------|---------------|---------|
| **OPERATIONAL** | Affects availability/performance | Operations | API down, high latency |
| **CONSTITUTIONAL** | Affects governance/integrity | Governance | Breach, halt, fork |
| **SECURITY** | Affects confidentiality/integrity | Security | Key compromise, intrusion |
| **COMPLIANCE** | Affects regulatory requirements | Legal | Data exposure, audit failure |

### By Severity

| Severity | Response Time | Communication | Examples |
|----------|---------------|---------------|----------|
| **CRITICAL** | Immediate | All stakeholders | Cessation, data corruption, security breach |
| **HIGH** | 15 minutes | On-call + leads | Halt, fork, >3 overrides, SLA breach |
| **MEDIUM** | 1 hour | On-call | Performance degradation, warning threshold |
| **LOW** | Next business day | Ticket | Minor issue, non-urgent fix needed |

## Procedure

### Step 1: Incident Detection

- [ ] Identify how incident was detected
- [ ] Classify incident type
- [ ] Assess initial severity
- [ ] Create incident record

```markdown
## Initial Assessment

Incident ID: INC-[timestamp]
Detected: [timestamp]
Detection method: [alert/user report/monitoring/other]
Initial classification: [operational/constitutional/security/compliance]
Initial severity: [critical/high/medium/low]
Summary: [brief description]
```

### Step 2: Triage and Classification

#### Operational vs Constitutional Decision Tree

```
Is system availability affected?
├── YES: Operational component
│   └── Is data integrity also affected?
│       ├── YES: Both Operational AND Constitutional
│       └── NO: Operational only
└── NO: Is governance/integrity affected?
    ├── YES: Constitutional
    └── NO: Other (Security/Compliance)
```

#### Update Classification

- [ ] Confirm or update incident type
- [ ] Confirm or update severity
- [ ] Assign incident owner based on type

### Step 3: Initial Response

#### For CRITICAL Severity

- [ ] Page all relevant on-call personnel immediately
- [ ] Start incident bridge (video/voice)
- [ ] Begin status page updates
- [ ] Consider activating halt (if constitutional risk)

#### For HIGH Severity

- [ ] Alert on-call and team leads
- [ ] Begin active investigation
- [ ] Start status page updates
- [ ] Prepare stakeholder communication

#### For MEDIUM/LOW Severity

- [ ] Assign to on-call
- [ ] Begin investigation
- [ ] Schedule fix as appropriate

### Step 4: Investigation

- [ ] Gather relevant logs
- [ ] Identify timeline of events
- [ ] Determine root cause (or working hypothesis)
- [ ] Document findings in incident record

**Log Sources:**
- Application logs (correlation ID search)
- Database logs
- Infrastructure logs
- Monitoring dashboards

### Step 5: Containment

**Goal:** Stop the bleeding before fixing root cause.

#### Operational Containment

- [ ] Isolate affected components
- [ ] Route traffic away from affected systems
- [ ] Scale down problematic services

#### Constitutional Containment

- [ ] Activate halt if integrity at risk
- [ ] Block problematic operations
- [ ] Preserve evidence (don't modify data)

### Step 6: Resolution

- [ ] Implement fix
- [ ] Verify fix is effective
- [ ] Monitor for recurrence
- [ ] Update status page

### Step 7: Communication

#### Internal Communication

- Update incident channel regularly
- Status updates every 30 minutes for CRITICAL
- Status updates every hour for HIGH
- Final resolution notice to all involved

#### External Communication

**For incidents affecting observers:**
- Update status page
- Send push notifications if configured
- Prepare public incident report

**Template for Status Update:**
```
[INVESTIGATING/IDENTIFIED/MONITORING/RESOLVED]

Time: [timestamp]
Issue: [brief description]
Impact: [what's affected]
Status: [current state]
Next update: [time]
```

### Step 8: Post-Incident

- [ ] Create incident report (FR54)
- [ ] Schedule post-mortem review
- [ ] Document lessons learned
- [ ] Create follow-up tasks

---

## Incident Report Template

```markdown
# Incident Report: INC-[ID]

## Summary
- **Type:** [operational/constitutional/security/compliance]
- **Severity:** [critical/high/medium/low]
- **Duration:** [start] to [end]
- **Impact:** [description]

## Timeline
| Time | Event |
|------|-------|
| HH:MM | First symptom observed |
| HH:MM | Alert fired |
| HH:MM | Investigation started |
| HH:MM | Root cause identified |
| HH:MM | Fix implemented |
| HH:MM | Incident resolved |

## Root Cause
[Detailed explanation of what caused the incident]

## Impact Assessment
### Operational Impact
- Services affected: [list]
- Duration of degradation: [time]
- Users affected: [count/percentage]

### Constitutional Impact
- Events affected: [count]
- Data integrity: [verified/compromised]
- Governance actions required: [yes/no]

## Response
### What Went Well
- [Item]

### What Could Be Improved
- [Item]

## Action Items
| ID | Action | Owner | Due Date |
|----|--------|-------|----------|
| 1 | [action] | [owner] | [date] |

## Approval
- Technical Review: [name] [date]
- Governance Review: [name] [date] (if constitutional)
```

---

## Special Incident Types

### Halt Incident

1. Follow [Halt & Fork Recovery](epic-3-halt-fork.md)
2. This is CONSTITUTIONAL - involve governance
3. Create incident report within 7 days

### Fork Incident

1. Follow [Halt & Fork Recovery](epic-3-halt-fork.md)
2. Potentially CRITICAL severity
3. Involve governance and system architect

### Override Threshold Incident

1. Follow [Keeper Operations](epic-5-keeper.md)
2. >3 daily overrides = automatic incident report
3. Involve governance

### Breach Incident

1. Follow [Breach Detection](epic-6-breach.md)
2. Constitutional - involve governance
3. Track 7-day escalation deadline

### Cessation Incident

1. Follow [Cessation Procedures](epic-7-cessation.md)
2. CRITICAL severity by definition
3. All hands required

---

## Escalation Matrix

| Condition | First Contact | Escalate To | Final Escalation |
|-----------|---------------|-------------|------------------|
| API unavailable | On-Call Ops | Operations Lead | System Architect |
| Database issues | On-Call DBA | DBA Lead | System Architect |
| Halt signal | On-Call Ops | Governance Lead | Full Governance |
| Fork detected | System Architect | Governance Lead | Full Governance |
| Security breach | Security On-Call | Security Lead | CISO + Legal |
| Cessation triggered | All | Full Governance | Legal + Board |

---

## Communication Channels

| Channel | Purpose | Participants |
|---------|---------|--------------|
| #incidents | Real-time incident updates | All responders |
| #incident-[id] | Specific incident thread | Assigned responders |
| Status Page | External communication | Public |
| Email List | Stakeholder updates | Management |

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Can't classify incident | Operations Lead | [TBD] |
| Constitutional component | Governance Lead | [TBD] |
| Security component | Security Lead | [TBD] |
| Legal/compliance component | Legal Counsel | [TBD] |
| Executive notification needed | Executive on-call | [TBD] |

## References

- [Startup Procedures](startup.md)
- [Shutdown Procedures](shutdown.md)
- [Halt & Fork Recovery](epic-3-halt-fork.md)
- [Breach Detection](epic-6-breach.md)
- [Cessation Procedures](epic-7-cessation.md)
- [Operational Monitoring](epic-8-monitoring.md)
- All epic-specific runbooks
