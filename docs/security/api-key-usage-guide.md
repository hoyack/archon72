# API Key and Credential Usage Guide

**Project:** Archon 72 Conclave Backend
**Version:** 1.0
**Date:** 2026-01-09
**Classification:** Security Sensitive

---

## Executive Summary

This document provides comprehensive guidance on all cryptographic keys and credentials used in the Archon 72 constitutional AI governance system. It covers key types, purposes, lifecycle management, storage requirements, and security best practices.

**Key Types Overview:**

| Key Type | Algorithm | Purpose | Storage |
|----------|-----------|---------|---------|
| Agent Keys | Ed25519 | Event signing & attribution | HSM + Database |
| Keeper Keys | Ed25519 | Human override commands | HSM + Database |
| Witness Keys | Ed25519 | Event attestation | Database |
| Database Credentials | N/A | PostgreSQL access | Environment |
| Redis Credentials | N/A | Cache/queue access | Environment |
| Webhook Secrets | HMAC-SHA256 | Notification authenticity | Database |

---

## 1. Agent Keys

### 1.1 Purpose

Agent keys provide cryptographic attribution for all events created by AI agents in the system. Every event must be signed with the creating agent's active key (FR3, FR75).

### 1.2 Format

| Attribute | Value |
|-----------|-------|
| **Algorithm** | Ed25519 |
| **Public Key Size** | 32 bytes |
| **Agent ID Format** | `agent-{uuid}` or `SYSTEM:{service_name}` |
| **Key ID Format** | `dev-{hex}` (dev) or HSM-specific (prod) |

### 1.3 Model Definition

**Location:** `src/domain/models/agent_key.py`

```python
@dataclass(frozen=True)
class AgentKey:
    id: UUID                    # Unique record identifier
    agent_id: str               # Agent identifier
    key_id: str                 # HSM key identifier (unique)
    public_key: bytes           # Ed25519 public key (32 bytes)
    active_from: datetime       # Activation timestamp
    active_until: datetime | None  # Deactivation (None = active)
    created_at: datetime        # Audit timestamp
```

### 1.4 Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Generate   │ ──► │   Active    │ ──► │  Deactivated│
│  (HSM)      │     │             │     │  (preserved)│
└─────────────┘     └─────────────┘     └─────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │  Rotation   │
                    │ (30-day     │
                    │  overlap)   │
                    └─────────────┘
```

**Creation:**
- Generated during system bootstrap or agent registration
- HSM generates key pair, public key registered in database

**Activation:**
- Immediate upon registration
- `active_from` set to current timestamp

**Rotation:**
- New key created with 30-day overlap period
- Both old and new keys valid during transition
- Old key deactivated after transition period

**Deactivation:**
- `active_until` timestamp set (key NEVER deleted per FR76)
- Historical signatures remain verifiable

### 1.5 Storage

| Component | Location | Security |
|-----------|----------|----------|
| Private Key | HSM only | Hardware-protected |
| Public Key | `agent_keys` table | Database access control |
| Key ID | `agent_keys` table | Maps to HSM |

### 1.6 Usage

**Signing Events:**
```python
# Via SigningService (FP-5 pattern - centralized)
signature, key_id, alg_version = await signing_service.sign_event(
    content_hash=event.content_hash,
    prev_hash=event.prev_hash,
    agent_id=event.agent_id
)
```

**Verifying Signatures:**
```python
is_valid = await signing_service.verify_event_signature(
    event=event,
    key_id=event.signing_key_id
)
```

### 1.7 Security Requirements

- [ ] Private keys MUST remain in HSM
- [ ] Public keys MUST be registered before signing
- [ ] Keys MUST NOT be deleted (FR76)
- [ ] Deactivated keys MUST remain queryable for historical verification
- [ ] Key rotation MUST use 30-day overlap (or emergency revocation)

---

## 2. Keeper Keys

### 2.1 Purpose

Keeper keys enable human oversight through cryptographically signed override commands. Keepers are trusted humans who can intervene in AI agent decisions (FR68).

### 2.2 Format

| Attribute | Value |
|-----------|-------|
| **Algorithm** | Ed25519 |
| **Public Key Size** | 32 bytes |
| **Keeper ID Format** | `KEEPER:{name}` (e.g., `KEEPER:alice`) |
| **Key ID Format** | HSM-specific identifier |

### 2.3 Model Definition

**Location:** `src/domain/models/keeper_key.py`

```python
@dataclass(frozen=True)
class KeeperKey:
    id: UUID                    # Unique record identifier
    keeper_id: str              # Keeper identifier (KEEPER:name)
    key_id: str                 # HSM key identifier (unique)
    public_key: bytes           # Ed25519 public key (32 bytes)
    active_from: datetime       # Activation timestamp
    active_until: datetime | None  # Deactivation (None = active)
    created_at: datetime        # Audit timestamp
```

### 2.4 Lifecycle

**Key Generation Ceremony (FR69):**

Keeper keys MUST be created through a witnessed ceremony:

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ PENDING  │ ──► │ APPROVED │ ──► │EXECUTING │ ──► │COMPLETED │
│          │     │ (3 wit.) │     │          │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                │                                  │
     ▼                ▼                                  │
┌──────────┐     ┌──────────┐                           │
│ EXPIRED  │     │  FAILED  │◄──────────────────────────┘
│ (1 hour) │     │          │
└──────────┘     └──────────┘
```

**Ceremony Requirements:**
- **Witnesses Required:** 3 minimum (CT-12)
- **Timeout:** 1 hour maximum (VAL-2)
- **Transition Period:** 30 days overlap (ADR-4)

**Rotation:**
```python
# Start 30-day transition
await keeper_key_registry.begin_transition(
    keeper_id="KEEPER:alice",
    new_key_id="new-hsm-key-id"
)

# After 30 days, complete transition
await keeper_key_registry.complete_transition(keeper_id="KEEPER:alice")
```

**Emergency Revocation (H3 Security Enhancement):**
```python
# Immediate revocation for compromised keys
await ceremony_service.emergency_revoke_key(
    key_id="compromised-key-id",
    reason="Key compromise detected",
    revoked_by="KEEPER:admin"
)
```

### 2.5 Storage

| Component | Location | Security |
|-----------|----------|----------|
| Private Key | HSM only | Hardware-protected |
| Public Key | `keeper_keys` table | Database access control |
| Ceremony Records | Event store | Immutable audit trail |

### 2.6 Usage

**Signing Overrides:**
```python
signed_override = await keeper_signature_service.sign_override(
    override_payload=payload,
    keeper_id="KEEPER:alice"
)
```

**Verifying Override Signatures:**
```python
is_valid = await keeper_signature_service.verify_override_signature(
    signed_override=override,
    expected_keeper_id="KEEPER:alice"
)
```

### 2.7 Security Requirements

- [ ] Keys MUST be created through witnessed ceremony (FR69)
- [ ] Minimum 3 witnesses required (CT-12)
- [ ] Private keys MUST remain in HSM
- [ ] Keys MUST NOT be deleted (FR76)
- [ ] Emergency revocation MUST be available for compromised keys
- [ ] All override actions MUST be logged to event store

---

## 3. Witness Keys

### 3.1 Purpose

Witness keys enable independent attestation of events. Witnesses are NOT agents - they attest that events occurred without creating them (CT-12).

### 3.2 Format

| Attribute | Value |
|-----------|-------|
| **Algorithm** | Ed25519 |
| **Public Key Size** | 32 bytes |
| **Witness ID Format** | `WITNESS:{uuid}` |

### 3.3 Model Definition

**Location:** `src/domain/models/witness.py`

```python
@dataclass(frozen=True)
class Witness:
    witness_id: str             # WITNESS:{uuid} format
    public_key: bytes           # Ed25519 public key (32 bytes)
    active_from: datetime       # Activation timestamp
    active_until: datetime | None  # Deactivation (None = active)
```

### 3.4 Lifecycle

**Creation:**
- System-managed during initial setup
- Registered in witness pool

**Activation:**
- Immediate upon registration
- Available for event attestation

**Deactivation:**
- Set `active_until` timestamp
- Historical attestations remain verifiable

### 3.5 Storage

| Component | Location | Security |
|-----------|----------|----------|
| Public Key | `witness_pool` | Database access control |
| Attestations | `events` table | `witness_id`, `witness_signature` columns |

### 3.6 Usage

**Creating Attestation:**
```python
witness_id, signature = await witness_service.attest_event(
    event_content_hash=event.content_hash
)
```

**Verifying Attestation:**
```python
is_valid = await witness_service.verify_attestation(
    event_content_hash=event.content_hash,
    witness_id=event.witness_id,
    signature=event.witness_signature
)
```

### 3.7 Bootstrap Mode (H2 Security Enhancement)

**Environment Variable:** `WITNESS_BOOTSTRAP_ENABLED`

During initial system setup, witnesses may be accepted without full verification:

```python
# In production, set to false after initial setup
WITNESS_BOOTSTRAP_ENABLED=false
```

**Security:**
- When `true`: Unverified witnesses logged but accepted
- When `false`: All witnesses MUST be cryptographically verified
- Transition from `true` to `false` is one-way

### 3.8 Security Requirements

- [ ] Witness IDs MUST use `WITNESS:` prefix
- [ ] Attestation signatures MUST be Ed25519
- [ ] Bootstrap mode MUST be disabled after initial setup
- [ ] Witnesses MUST NOT be deleted (FR76)
- [ ] Anomaly detection MUST monitor witness patterns

---

## 4. HSM Configuration

### 4.1 Mode Selection

**Environment Variable:** `DEV_MODE`

| Mode | DEV_MODE | HSM Implementation |
|------|----------|-------------------|
| Development | `true` | DevHSM (software stub) |
| Production | `false` | CloudHSM (AWS/Azure) |

### 4.2 Development Mode (DevHSM)

**WARNING: NOT FOR PRODUCTION USE**

| Attribute | Value |
|-----------|-------|
| Key Storage | Plaintext JSON file |
| Location | `$TEMP/archon72-dev-{PID}/dev_keys.json` |
| Permissions | Owner read/write only (0o600) |
| Key ID Prefix | `dev-{uuid_hex[:8]}` |

**RT-1 Mode Watermark:**

All signatures include mode watermark INSIDE the signed content:
- Development: `[DEV MODE]` prefix
- Production: `[PROD]` prefix

This prevents dev signatures from being accepted as production signatures.

### 4.3 Production Mode (CloudHSM)

**Location:** `src/infrastructure/adapters/security/hsm_cloud.py`

Currently a placeholder that raises `HSMNotConfiguredError`. Production deployment requires:

1. AWS CloudHSM or Azure Key Vault configuration
2. HSM cluster setup and initialization
3. Key migration from development keys
4. Verification of all agent/keeper keys

### 4.4 Environment Validation (H1 Security Enhancement)

**Secondary Check:** `validate_dev_mode_consistency()`

Prevents `DEV_MODE=true` in production environments:

```python
# These combinations are BLOCKED:
DEV_MODE=true + ENVIRONMENT=production  # ERROR
DEV_MODE=true + ENVIRONMENT=prod        # ERROR
DEV_MODE=true + ENVIRONMENT=staging     # ERROR
DEV_MODE=true + ENVIRONMENT=stage       # ERROR

# These are allowed:
DEV_MODE=true + ENVIRONMENT=development  # OK
DEV_MODE=false + ENVIRONMENT=production  # OK
```

### 4.5 Security Requirements

- [ ] Production MUST use CloudHSM (not DevHSM)
- [ ] DEV_MODE MUST be `false` in production
- [ ] ENVIRONMENT variable MUST match DEV_MODE setting
- [ ] Mode watermark MUST be verified during signature validation
- [ ] HSM keys MUST NOT be exportable

---

## 5. Database Credentials

### 5.1 PostgreSQL (Supabase)

**Environment Variable:** `DATABASE_URL`

```
DATABASE_URL=postgresql://username:password@host:port/database
```

| Component | Production Requirement |
|-----------|----------------------|
| Username | Dedicated service account |
| Password | Strong, rotated regularly |
| Host | Private network only |
| Port | Non-default if possible |
| SSL | Required (`sslmode=require`) |

### 5.2 Security Requirements

- [ ] Use dedicated service account (not admin)
- [ ] Rotate credentials regularly (90 days)
- [ ] Store in secure secret manager (not .env file)
- [ ] Enable SSL/TLS for all connections
- [ ] Restrict network access to application servers
- [ ] Enable connection pooling with limits

### 5.3 Principle of Least Privilege

```sql
-- Example: Create limited service account
CREATE USER archon72_app WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE archon72 TO archon72_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO archon72_app;
-- Note: No UPDATE/DELETE on events table (append-only)
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO archon72_app;
```

---

## 6. Redis Credentials

### 6.1 Configuration

**Environment Variable:** `REDIS_URL`

```
REDIS_URL=redis://username:password@host:port/db
```

### 6.2 Security Requirements

- [ ] Enable authentication (requirepass)
- [ ] Use TLS for connections
- [ ] Restrict network access
- [ ] Disable dangerous commands (FLUSHALL, CONFIG, etc.)
- [ ] Use separate database numbers for different purposes

---

## 7. Webhook Secrets

### 7.1 Purpose

Webhook secrets enable external services to verify notification authenticity using HMAC-SHA256 signatures.

### 7.2 Configuration

**Model:** `src/api/models/observer.py`

```python
class WebhookSubscription:
    webhook_url: str      # HTTPS endpoint
    event_types: list     # Subscribed events
    secret: str | None    # HMAC secret (min 32 chars)
```

### 7.3 SSRF Protection

Webhook URLs are validated against:
- HTTP (blocked - HTTPS only)
- localhost, 127.0.0.1, ::1, 0.0.0.0
- Private networks (10.x, 172.16-31.x, 192.168.x)
- Cloud metadata endpoints (169.254.169.254)
- Link-local addresses

### 7.4 Security Requirements

- [ ] Secrets MUST be minimum 32 characters
- [ ] Secrets MUST be cryptographically random
- [ ] HTTPS MUST be required for all webhooks
- [ ] SSRF protection MUST be enabled
- [ ] Secrets SHOULD be rotated periodically

---

## 8. Key Rotation Procedures

### 8.1 Agent Key Rotation

```bash
# 1. Generate new key in HSM
new_key_id=$(call_hsm_generate_key)

# 2. Register new key with overlap
register_agent_key \
  --agent-id "agent-uuid" \
  --key-id "$new_key_id" \
  --active-from "now"

# 3. Wait 30 days (transition period)

# 4. Deactivate old key
deactivate_agent_key \
  --key-id "old-key-id" \
  --active-until "now"
```

### 8.2 Keeper Key Rotation

```bash
# 1. Initiate key generation ceremony
ceremony_id=$(initiate_keeper_ceremony \
  --keeper-id "KEEPER:alice" \
  --type "KEY_ROTATION")

# 2. Collect 3 witness signatures
add_ceremony_witness --ceremony-id "$ceremony_id" --witness-id "WITNESS:1"
add_ceremony_witness --ceremony-id "$ceremony_id" --witness-id "WITNESS:2"
add_ceremony_witness --ceremony-id "$ceremony_id" --witness-id "WITNESS:3"

# 3. Execute ceremony (generates new key)
execute_ceremony --ceremony-id "$ceremony_id"

# 4. Wait 30 days (transition period)

# 5. Complete transition
complete_keeper_transition --keeper-id "KEEPER:alice"
```

### 8.3 Emergency Key Revocation

```bash
# Immediate revocation (bypasses 30-day period)
emergency_revoke_key \
  --key-id "compromised-key-id" \
  --reason "Key compromise detected via security audit" \
  --revoked-by "KEEPER:admin"
```

### 8.4 Database Credential Rotation

```bash
# 1. Create new credentials in database
# 2. Update secret manager with new credentials
# 3. Rolling restart of application instances
# 4. Verify all instances using new credentials
# 5. Revoke old credentials
```

---

## 9. Secure Storage Requirements

### 9.1 Production Secret Storage

| Secret Type | Recommended Storage |
|-------------|-------------------|
| HSM Keys | AWS CloudHSM / Azure Key Vault |
| Database URL | AWS Secrets Manager / HashiCorp Vault |
| Redis URL | AWS Secrets Manager / HashiCorp Vault |
| Webhook Secrets | Database (encrypted at rest) |

### 9.2 Environment Variable Security

**DO NOT:**
- Store secrets in `.env` files in production
- Commit secrets to version control
- Log secrets in application logs
- Pass secrets via command line arguments

**DO:**
- Use secret management services
- Inject secrets at runtime
- Encrypt secrets at rest
- Audit secret access

### 9.3 Secret Rotation Schedule

| Secret Type | Rotation Frequency | Emergency Trigger |
|-------------|-------------------|-------------------|
| Agent Keys | Annually | Compromise suspected |
| Keeper Keys | Annually | Compromise suspected |
| Database Credentials | 90 days | Credential leak |
| Redis Credentials | 90 days | Credential leak |
| Webhook Secrets | On request | Subscriber request |

---

## 10. Audit and Compliance

### 10.1 Key Usage Logging

All key operations are logged to the event store:

| Event Type | Logged Information |
|------------|-------------------|
| KEY_GENERATED | key_id, agent_id/keeper_id, ceremony_id |
| KEY_ACTIVATED | key_id, active_from |
| KEY_DEACTIVATED | key_id, active_until, reason |
| KEY_EMERGENCY_REVOKED | key_id, reason, revoked_by |
| SIGNATURE_CREATED | key_id, content_hash |
| SIGNATURE_VERIFIED | key_id, content_hash, result |

### 10.2 Compliance Requirements

| Requirement | Implementation |
|-------------|---------------|
| FR75 | Active key tracking in registry |
| FR76 | No key deletion (historical preservation) |
| FR68 | Keeper signature verification |
| FR69 | Witnessed key generation ceremony |
| CT-12 | Multiple witness attestation |
| ADR-4 | 30-day key rotation overlap |

### 10.3 Audit Queries

```sql
-- All keys for an agent
SELECT * FROM agent_keys WHERE agent_id = 'agent-uuid' ORDER BY created_at;

-- Key usage timeline
SELECT signing_key_id, COUNT(*) as event_count, MIN(created_at), MAX(created_at)
FROM events
GROUP BY signing_key_id;

-- Active keys at specific time
SELECT * FROM agent_keys
WHERE active_from <= '2026-01-09'
  AND (active_until IS NULL OR active_until > '2026-01-09');
```

---

## 11. Troubleshooting

### 11.1 Common Issues

| Issue | Cause | Resolution |
|-------|-------|------------|
| `HSMNotConfiguredError` | CloudHSM not setup in production | Configure HSM or set DEV_MODE=true (dev only) |
| `DevModeEnvironmentMismatchError` | DEV_MODE=true in production | Set DEV_MODE=false or ENVIRONMENT=development |
| `KeyNotFoundError` | Key ID not in registry | Verify key registration, check key_id format |
| `SignatureVerificationError` | Wrong key or tampered content | Check key_id matches signer, verify content hash |
| `CeremonyTimeoutError` | Ceremony exceeded 1 hour | Restart ceremony, ensure witness availability |
| `InsufficientWitnessesError` | Less than 3 witnesses | Add more witness signatures |

### 11.2 Diagnostic Commands

```bash
# Check HSM mode
curl http://localhost:8000/health | jq '.hsm_mode'

# List active agent keys
SELECT agent_id, key_id, active_from FROM agent_keys WHERE active_until IS NULL;

# Check ceremony status
SELECT id, keeper_id, state, created_at FROM key_generation_ceremonies
WHERE state NOT IN ('COMPLETED', 'FAILED', 'EXPIRED');

# Verify environment configuration
echo "DEV_MODE=$DEV_MODE"
echo "ENVIRONMENT=$ENVIRONMENT"
```

---

## 12. Quick Reference

### 12.1 Environment Variables

| Variable | Purpose | Production Value |
|----------|---------|-----------------|
| `DEV_MODE` | HSM mode selection | `false` |
| `ENVIRONMENT` | Environment detection | `production` |
| `WITNESS_BOOTSTRAP_ENABLED` | Bootstrap mode | `false` |
| `DATABASE_URL` | PostgreSQL connection | Secret manager |
| `REDIS_URL` | Redis connection | Secret manager |

### 12.2 Key Prefixes

| Prefix | Key Type |
|--------|----------|
| `agent-{uuid}` | Agent ID |
| `SYSTEM:{name}` | System agent ID |
| `KEEPER:{name}` | Keeper ID |
| `WITNESS:{uuid}` | Witness ID |
| `dev-{hex}` | Development key ID |

### 12.3 Critical Files

```
src/domain/models/agent_key.py      # Agent key model
src/domain/models/keeper_key.py     # Keeper key model
src/domain/models/witness.py        # Witness model
src/domain/models/signable.py       # Mode watermark
src/infrastructure/adapters/security/hsm_*.py  # HSM implementations
src/application/services/signing_service.py    # Agent signing
src/application/services/keeper_signature_service.py  # Keeper signing
src/application/services/witness_service.py    # Witness attestation
```

---

*Document Version: 1.0*
*Last Updated: 2026-01-09*
*Classification: Security Sensitive*
