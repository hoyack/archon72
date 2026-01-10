# [Runbook Title]

Last Updated: YYYY-MM-DD
Version: 1.0
Owner: [Team/Role]

## Purpose

[Brief description of when and why to use this runbook]

## Prerequisites

- [ ] Prerequisite 1
- [ ] Prerequisite 2

## Trigger Conditions

When to execute this runbook:

- Condition 1
- Condition 2

## Procedure

### Step 1: [Step Name]

- [ ] Action 1
- [ ] Action 2

**Verification:**

- Expected outcome: [description]
- Command to verify: `[command]`

### Step 2: [Step Name]

- [ ] Action 1
- [ ] Action 2

**Verification:**

- Expected outcome: [description]
- Command to verify: `[command]`

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| [condition] | [role] | [info] |

## Rollback

If procedure fails:

1. Step 1
2. Step 2

## References

- [Related documentation]
- [ADR references]

---

## Classification Legend

Use these markers to distinguish procedure types:

- **OPERATIONAL** - Affects system performance/availability
- **CONSTITUTIONAL** - Affects governance/integrity guarantees (CT-11: HALT CHECK FIRST)

Example usage in procedures:

```markdown
### Step 3: Verify System Health

#### Operational Check
- [ ] API responding to health endpoint
- [ ] Database connections healthy

#### Constitutional Check
- [ ] Halt state is clear
- [ ] Hash chain integrity verified
```
