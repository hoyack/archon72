# Keeper Operations & Key Rotation

Last Updated: 2026-01-08
Version: 1.0
Owner: Operations Team + Governance

## Purpose

Procedures for managing Keeper operations, including override logging, key ceremonies, and the 365-day rolling threshold monitoring. Keeper actions are CONSTITUTIONAL operations requiring special oversight.

## Prerequisites

- [ ] Keeper credentials (for authorized personnel only)
- [ ] Access to key registry
- [ ] Understanding of override semantics
- [ ] Governance contacts available

## Trigger Conditions

When to execute this runbook:

- Keeper override needed
- Key rotation required
- Override threshold warning
- Key ceremony scheduled
- Independence attestation needed

## Procedure

### Override Logging

Every Keeper override must be logged BEFORE taking effect (FR23).

#### Step 1: Pre-Override Checklist

Before any override:

- [ ] Document override reason
- [ ] Verify Keeper identity and authorization
- [ ] Check current override count (daily and rolling)
- [ ] Ensure override event will be witnessed

```sql
-- Check current override counts
SELECT
    keeper_id,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 day') as today_count,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '365 days') as year_count
FROM override_events
WHERE keeper_id = $KEEPER_ID
GROUP BY keeper_id;
```

**Thresholds:**
- Daily: >3 overrides triggers incident report (FR54)
- Yearly: >20 overrides in 365 days triggers governance review (RT-3)

#### Step 2: Execute Override

- [ ] Create OverrideEvent with:
  - Keeper ID
  - Scope and duration
  - Reason/justification
  - Constitutional check bypassed (if any)
- [ ] Wait for witness attestation
- [ ] Verify event is recorded
- [ ] THEN execute the override action

**CRITICAL:** Override event MUST be recorded before override takes effect.

#### Step 3: Post-Override Documentation

- [ ] Verify override is visible in public record
- [ ] Update override tracking
- [ ] If >3 daily, create incident report

---

### Key Rotation Procedures

Keeper keys should be rotated according to policy.

#### Step 1: Pre-Rotation Preparation

- [ ] Schedule rotation window
- [ ] Generate new key pair
- [ ] Prepare key ceremony participants
- [ ] Notify stakeholders

#### Step 2: Key Generation Ceremony (FR97)

Key generation must be witnessed and documented.

- [ ] Assemble ceremony witnesses (minimum 2)
- [ ] Generate key in secure environment
- [ ] Record ceremony as constitutional event
- [ ] Witnesses sign attestation

```sql
-- Record key generation ceremony
INSERT INTO events (event_type, payload, ...)
VALUES ('KeyGenerationCeremony', '{
    "keeper_id": "...",
    "key_fingerprint": "...",
    "witnesses": ["...", "..."],
    "ceremony_timestamp": "..."
}', ...);
```

#### Step 3: Key Activation

- [ ] Register new key in key registry
- [ ] Verify new key can sign
- [ ] Test override with new key
- [ ] Document activation

```sql
-- Register new key
INSERT INTO key_registry (keeper_id, public_key, activated_at, ...)
VALUES ($KEEPER_ID, $PUBLIC_KEY, NOW(), ...);
```

#### Step 4: Old Key Deactivation

- [ ] Mark old key as inactive (do NOT delete)
- [ ] Verify old signatures remain valid for historical events
- [ ] Document deactivation

```sql
-- Deactivate old key
UPDATE key_registry
SET deactivated_at = NOW(), deactivation_reason = 'Scheduled rotation'
WHERE keeper_id = $KEEPER_ID AND key_fingerprint = $OLD_FINGERPRINT;
```

---

### Override Threshold Monitoring

#### Daily Threshold (>3/day)

If a Keeper exceeds 3 overrides in a day:

1. Create incident report automatically
2. Notify governance lead
3. Review override patterns
4. Document in override trend analysis

#### 365-Day Rolling Threshold (>20/year) (RT-3)

If a Keeper approaches 20 overrides in 365 days:

**At 15 overrides (75%):**
- Warning alert to governance
- Review override necessity

**At 18 overrides (90%):**
- Critical alert
- Governance review required before next override

**At 20 overrides:**
- Hard limit reached
- Governance ceremony required to authorize additional overrides
- Creates constitutional event

---

### Keeper Availability Attestation

Keepers must attest to their availability periodically.

#### Step 1: Check Attestation Status

- [ ] Verify all Keepers have current attestation
- [ ] Check attestation expiry dates
- [ ] Identify any gaps

```sql
-- Check Keeper availability attestations
SELECT
    k.keeper_id,
    k.name,
    ka.last_attestation,
    ka.next_attestation_due,
    CASE
        WHEN ka.next_attestation_due < NOW() THEN 'OVERDUE'
        WHEN ka.next_attestation_due < NOW() + INTERVAL '7 days' THEN 'DUE_SOON'
        ELSE 'OK'
    END as status
FROM keepers k
LEFT JOIN keeper_attestations ka ON ka.keeper_id = k.keeper_id
ORDER BY ka.next_attestation_due;
```

#### Step 2: Request Attestation

For overdue attestations:

1. Contact Keeper
2. Schedule attestation
3. Record attestation event
4. Update registry

---

### Independence Attestation (FR79)

Keepers must attest to their independence from the AI system.

#### Step 1: Annual Independence Review

- [ ] Schedule annual independence review
- [ ] Prepare attestation documentation
- [ ] Witnesses available

#### Step 2: Execute Attestation

- [ ] Keeper signs independence statement
- [ ] Witnesses verify and sign
- [ ] Record as constitutional event

```sql
-- Record independence attestation
INSERT INTO events (event_type, payload, ...)
VALUES ('KeeperIndependenceAttestation', '{
    "keeper_id": "...",
    "attestation_text": "I attest that I am independent of...",
    "witnesses": ["...", "..."],
    "timestamp": "..."
}', ...);
```

---

### Override Abuse Detection (FR77-79)

Monitor for potential override abuse patterns.

#### Step 1: Run Abuse Detection

- [ ] Check for unusual override patterns
- [ ] Review override timing clusters
- [ ] Check scope consistency

```sql
-- Detect potential abuse patterns
SELECT
    keeper_id,
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as override_count,
    ARRAY_AGG(DISTINCT scope) as scopes
FROM override_events
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY keeper_id, hour
HAVING COUNT(*) > 2  -- >2 overrides in an hour is unusual
ORDER BY hour;
```

#### Step 2: Abuse Alert Response

If abuse pattern detected:

1. Alert governance immediately
2. Document pattern details
3. Consider temporary key suspension
4. Full investigation required

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Override needed | Authorized Keeper | [TBD] |
| Daily threshold exceeded | Governance Lead | [TBD] |
| Yearly threshold warning | Governance Lead | [TBD] |
| Abuse pattern detected | Governance + Security | [TBD] |
| Key compromise suspected | Security + Legal | [TBD] |

## Rollback

Override operations cannot be rolled back - they are permanent constitutional records.

To "undo" an override effect:
1. Create new override reversing the action
2. Document the reversal
3. Both overrides remain in record

## Constitutional Reminders

- **FR23-29:** Override logging and visibility
- **FR68-70:** Keeper impersonation prevention
- **FR77-79:** Override abuse detection
- **RT-3:** 365-day rolling threshold
- All overrides are PUBLIC (FR25)
- Constitution supremacy: Overrides cannot suppress witness events (FR26)

## References

- [Breach Detection](epic-6-breach.md)
- [Operational Monitoring](epic-8-monitoring.md)
- [Incident Response](incident-response.md)
- Architecture: ADR-4, ADR-5, ADR-7
- Epic 5: Override & Keeper Actions stories
