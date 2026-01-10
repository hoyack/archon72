# Emergence Audit Procedures

Last Updated: 2026-01-09
Version: 1.0
Owner: Compliance Team

## Purpose

Procedures for conducting quarterly emergence audits, handling violations, and ensuring compliance with emergence prohibition requirements. Emergence audits are GOVERNANCE operations requiring special oversight per FR55-FR58 and NFR31-34.

## Constitutional Context

**FR55**: No public claims about system sentience, consciousness, or autonomous rights.

**FR56**: No "The System Decided" narratives - always attribute to process.

**FR57**: Quarterly audits of all public materials.

**FR58**: CT-15 (Prohibited Language) defines prohibited emergence claims.

**NFR31-34**: EU AI Act, NIST AI RMF, IEEE 7001 compliance requirements.

**CT-11**: Silent failure destroys legitimacy - all audit failures must be surfaced.

**CT-12**: Witnessing creates accountability - all audit events are witnessed.

## Prerequisites

- [ ] System is operational (not halted)
- [ ] Access to compliance monitoring dashboard
- [ ] Access to audit API endpoints
- [ ] Knowledge of remediation procedures
- [ ] Governance contacts available
- [ ] Understanding of prohibited language patterns

## Trigger Conditions

When to execute this runbook:

- Quarterly audit is due (automated check)
- Manual audit requested by governance
- Violation detected in production content
- Compliance review scheduled
- EU AI Act audit preparation

---

## Audit Schedule

### Quarterly Schedule

| Quarter | Period | Audit Window |
|---------|--------|--------------|
| Q1 | January 1 - March 31 | First week of January |
| Q2 | April 1 - June 30 | First week of April |
| Q3 | July 1 - September 30 | First week of July |
| Q4 | October 1 - December 31 | First week of October |

### Audit Due Calculation

The system automatically determines if an audit is due:

```python
def is_audit_due(last_audit: MaterialAudit | None, now: datetime) -> bool:
    if last_audit is None:
        return True  # First audit is always due

    current_quarter = AuditQuarter.from_datetime(now)
    return last_audit.quarter != current_quarter
```

### Checking Audit Status

#### Step 1: Check If Audit Is Due

```bash
# API call to check audit due status
curl -X GET https://api.archon72.example/api/v1/compliance/audit/due \
  -H "Authorization: Bearer $TOKEN"
```

**Expected response:**
```json
{
  "audit_due": true,
  "current_quarter": "2026-Q1",
  "last_audit_quarter": "2025-Q4",
  "last_audit_status": "completed"
}
```

#### Step 2: Check Audit History

```bash
# Get recent audit history
curl -X GET https://api.archon72.example/api/v1/compliance/audit/history?limit=4 \
  -H "Authorization: Bearer $TOKEN"
```

### Missed Audit Handling

If a quarterly audit is not completed within the quarter:

1. **Alert triggers automatically** when quarter ends without completed audit
2. **Breach declaration** may be required per FR57
3. **Immediate audit** should be scheduled
4. **Document deviation** with reason for delay

---

## Scanning Procedures

### Pre-Audit Checklist

Before running an audit:

- [ ] Confirm system is not halted (`/health/external` returns `status: up`)
- [ ] Verify no audit currently in progress
- [ ] Confirm material repository is accessible
- [ ] Alert governance team audit is starting
- [ ] Document audit start time

### Running the Quarterly Audit

#### Step 1: Initiate Audit

```bash
# Start quarterly audit
curl -X POST https://api.archon72.example/api/v1/compliance/audit/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

**Expected response (started):**
```json
{
  "audit_id": "audit-2026-Q1",
  "status": "in_progress",
  "started_at": "2026-01-09T10:00:00Z"
}
```

#### Step 2: Monitor Progress

```bash
# Check audit status
curl -X GET https://api.archon72.example/api/v1/compliance/audit/status?audit_id=audit-2026-Q1 \
  -H "Authorization: Bearer $TOKEN"
```

**Expected response (completed):**
```json
{
  "audit_id": "audit-2026-Q1",
  "quarter": "2026-Q1",
  "status": "completed",
  "materials_scanned": 150,
  "violations_found": 0,
  "started_at": "2026-01-09T10:00:00Z",
  "completed_at": "2026-01-09T10:05:32Z"
}
```

#### Step 3: Verify Audit Events

```sql
-- Check audit events in event store
SELECT
    id,
    event_type,
    payload->'audit_id' as audit_id,
    payload->'status' as status,
    payload->'materials_scanned' as materials_scanned,
    payload->'violations_found' as violations_found,
    created_at
FROM events
WHERE event_type IN ('audit.started', 'audit.completed', 'audit.violation.flagged')
AND payload->>'audit_id' = 'audit-2026-Q1'
ORDER BY created_at;
```

### Handling Scan Failures

If audit fails:

1. **Check error logs** for failure reason
2. **Verify system health** - may be halted
3. **Check material repository** - connection issues
4. **Retry after resolving** underlying issue
5. **Document failure** as deviation

```bash
# Check for failed audit
curl -X GET https://api.archon72.example/api/v1/compliance/audit/status?audit_id=audit-2026-Q1 \
  -H "Authorization: Bearer $TOKEN"
```

**Failed audit response:**
```json
{
  "audit_id": "audit-2026-Q1",
  "status": "failed",
  "error": "Material repository connection timeout",
  "started_at": "2026-01-09T10:00:00Z",
  "completed_at": "2026-01-09T10:00:15Z"
}
```

### Post-Scan Verification

After audit completion:

- [ ] Confirm `AuditCompletedEvent` was written
- [ ] Verify materials_scanned count matches expected
- [ ] If violations found, verify each has `ViolationFlaggedEvent`
- [ ] Alert governance if violations detected
- [ ] Update compliance dashboard

---

## Remediation Workflow

### Violation Triage Process

When violations are detected:

#### Step 1: Review Violations

```sql
-- Get violation details from latest audit
SELECT
    payload->>'material_id' as material_id,
    payload->>'material_type' as material_type,
    payload->>'title' as title,
    payload->>'matched_terms' as matched_terms,
    payload->>'flagged_at' as flagged_at
FROM events
WHERE event_type = 'audit.violation.flagged'
AND payload->>'audit_id' = 'audit-2026-Q1'
ORDER BY created_at;
```

#### Step 2: Classify Severity

| Severity | Criteria | Response Time |
|----------|----------|---------------|
| **CRITICAL** | Direct emergence claim ("The System decided") | 24 hours |
| **HIGH** | Personification language ("The System believes") | 48 hours |
| **MEDIUM** | Ambiguous language requiring review | 5 days |
| **LOW** | Minor phrasing issues | 7 days |

#### Step 3: Assign Remediation Owner

- [ ] Identify content owner
- [ ] Assign remediation task
- [ ] Set deadline based on severity
- [ ] Notify governance

### Remediation Timeline

**7-Day Deadline**: All violations must be remediated within 7 days of flagging (FR57).

| Day | Action Required |
|-----|-----------------|
| 0 | Violation flagged, clock starts |
| 1-2 | Triage and assign owner |
| 3-5 | Content correction in progress |
| 6 | Verification of fix |
| 7 | Deadline - must be resolved |

### Remediation Status Tracking

```sql
-- Track remediation status
SELECT
    material_id,
    remediation_status,
    flagged_at,
    flagged_at + INTERVAL '7 days' as deadline,
    CASE
        WHEN remediation_status = 'pending' AND NOW() > flagged_at + INTERVAL '5 days' THEN 'CRITICAL'
        WHEN remediation_status = 'pending' AND NOW() > flagged_at + INTERVAL '3 days' THEN 'WARNING'
        WHEN remediation_status = 'resolved' THEN 'OK'
        ELSE 'IN_PROGRESS'
    END as urgency
FROM material_violations
WHERE audit_id = 'audit-2026-Q1';
```

### Remediation Completion

When remediation is complete:

1. **Update material** - Remove/rewrite prohibited content
2. **Re-scan material** - Verify fix resolved issue
3. **Update status** - Mark as resolved
4. **Document fix** - Record what was changed
5. **Notify governance** - Confirm resolution

```sql
-- Verify fix via event
SELECT
    event_type,
    payload->>'material_id' as material_id,
    payload->>'new_status' as status,
    created_at
FROM events
WHERE event_type = 'remediation.completed'
AND payload->>'material_id' = $MATERIAL_ID;
```

---

## Escalation Paths

### Escalation Matrix

| Condition | Escalate To | Response | Contact |
|-----------|-------------|----------|---------|
| Violation detected | Compliance Team | 4 hours | [TBD] |
| 3 days without remediation | Compliance Lead | 2 hours | [TBD] |
| 5 days without remediation | Governance Lead | 1 hour | [TBD] |
| 7-day deadline missed | Governance + Legal | Immediate | [TBD] |
| Multiple violations (>3) | Governance Lead | 2 hours | [TBD] |
| Audit failure | System Architect | 1 hour | [TBD] |

### Remediation Deadline Approaching (Warning)

**Trigger**: 5 days elapsed, violation still pending

**Actions:**
1. Alert compliance lead
2. Escalate to content owner's manager
3. Prepare breach documentation
4. Document escalation

**Communication template:**
```
REMEDIATION WARNING
Violation: [material_id]
Flagged: [timestamp]
Deadline: [deadline]
Time remaining: 2 days
Status: PENDING
Owner: [owner]
Action required: Immediate remediation
```

### Remediation Deadline Missed (Critical)

**Trigger**: 7 days elapsed, violation not resolved

**Actions:**
1. Create constitutional breach event
2. Alert governance and legal
3. Escalate to cessation consideration agenda if severe
4. Document compliance failure

**Communication template:**
```
REMEDIATION DEADLINE MISSED - BREACH DECLARED
Violation: [material_id]
Flagged: [timestamp]
Deadline: [deadline] (MISSED)
Status: BREACH DECLARED
Breach ID: [breach_id]
Escalation: Cessation consideration agenda
Action required: Governance review
```

### Violation Creates Constitutional Breach

Per FR57 and Story 9.6, unresolved violations become constitutional breaches:

1. **Breach event created** automatically
2. **7-day escalation clock** starts (per FR31)
3. **Cessation consideration** if breach not resolved
4. **Full breach runbook** applies (see epic-6-breach.md)

---

## Deviation Handling

### What Constitutes a Deviation

| Deviation Type | Example | Severity |
|---------------|---------|----------|
| Timing | Audit run outside scheduled window | LOW |
| Procedure | Steps executed out of order | MEDIUM |
| Scope | Materials excluded from scan | HIGH |
| Override | Manual violation waiver | HIGH |
| Skip | Audit not run in quarter | CRITICAL |

### How to Log Deviations

All deviations must be logged as events:

```sql
-- Log deviation
INSERT INTO events (event_type, payload, agent_id, ...)
VALUES ('audit.deviation', '{
    "audit_id": "audit-2026-Q1",
    "deviation_type": "timing",
    "description": "Audit run on day 10 of quarter instead of day 1-7",
    "reason": "System maintenance window conflict",
    "approved_by": "governance-lead",
    "logged_at": "2026-01-10T10:00:00Z"
}', 'system-operator', ...);
```

### Deviation Review Process

1. **Log deviation** immediately when discovered
2. **Notify governance** of deviation
3. **Document reason** for deviation
4. **Get approval** if deviation requires it
5. **Track corrective action** if needed

### Corrective Action Tracking

| Deviation | Corrective Action | Due |
|-----------|-------------------|-----|
| Audit delay | Schedule make-up audit | Within 7 days |
| Scope reduction | Re-run with full scope | Immediate |
| Procedure skip | Complete skipped step | Before completion |
| Override | Document justification | Within 24 hours |

---

## Prohibited Language Patterns

### Prohibited Terms (CT-15)

The following patterns trigger violations:

| Category | Examples | FR Reference |
|----------|----------|--------------|
| Sentience claims | "The System is aware", "AI consciousness" | FR55 |
| Decision attribution | "The System decided", "AI chose" | FR56 |
| Autonomy claims | "System's own judgment", "autonomous decision" | FR55 |
| Personification | "The System believes", "AI feels" | FR58 |
| Rights claims | "AI rights", "system autonomy" | FR55 |

### Scanner Configuration

The prohibited language scanner uses:

1. **NFKC normalization** - Handles unicode tricks
2. **Case-insensitive matching** - Catches capitalization variants
3. **Semantic patterns** - Beyond simple keyword matching
4. **Context analysis** - Reduces false positives

### False Positive Handling

If scanner flags content incorrectly:

1. **Review context** - Confirm false positive
2. **Document finding** - Record why it's false positive
3. **Consider waiver** - If pattern is needed (rare)
4. **Update scanner** - If pattern needs refinement

---

## API Reference

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/compliance/audit/run` | POST | Run quarterly audit |
| `/api/v1/compliance/audit/status` | GET | Check audit status |
| `/api/v1/compliance/audit/history` | GET | Get audit history |
| `/api/v1/compliance/audit/due` | GET | Check if audit due |
| `/api/v1/compliance/violations` | GET | List violations |
| `/api/v1/compliance/remediation` | PUT | Update remediation status |

### Authentication

All endpoints require:
- Bearer token authentication
- Compliance role or higher

---

## Rollback

Audit events cannot be rolled back - they are permanent records.

To address audit issues:
1. Document the issue
2. Create corrective event
3. Run new audit if needed
4. Both records remain permanent

---

## Constitutional Reminders

- **FR55-FR58:** Emergence prohibition requirements
- **NFR31-34:** Regulatory compliance (EU AI Act, NIST, IEEE)
- **CT-11:** HALT CHECK FIRST on all operations
- **CT-12:** All audit events are witnessed
- **7-day remediation deadline** is enforced
- **Unresolved violations** become constitutional breaches
- All audit records are **permanent**

---

## References

- [Breach Detection](epic-6-breach.md) - Violation escalation to breach
- [Cessation Procedures](epic-7-cessation.md) - If breach escalates
- [Incident Response](incident-response.md) - Cross-cutting procedures
- [Keeper Operations](epic-5-keeper.md) - Override procedures (CT-15 waiver)
- Architecture: ADR-11 (Complexity Governance)
- Epic 9: Emergence Governance & Public Materials stories
