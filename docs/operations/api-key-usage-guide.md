# API Key Usage Guide - Archon 72 Conclave Backend

**Created:** 2026-01-09
**Priority:** CRITICAL (from Full Project Retrospective)
**Status:** Initial Draft

---

## Overview

This document describes all key types used in the Archon 72 Conclave Backend, their purposes, storage requirements, rotation procedures, and security considerations.

---

## Key Types Summary

| Key Type | Algorithm | Purpose | Scope | Rotation Method |
|----------|-----------|---------|-------|-----------------|
| Supabase Anon Key | JWT | Public API access | Per-project | Project recreation |
| Supabase Service Key | JWT | Backend service access | Per-project | Project recreation |
| Agent Keys | Ed25519 | Event signing | Per-agent | Registry deactivation |
| Keeper Keys | Ed25519 | Override signing | Per-keeper | Ceremony + 30-day transition |
| Witness Keys | Ed25519 | Event attestation | Per-witness | Registry deactivation |

---

## 1. Supabase Keys

### 1.1 Anon Key (Public)

**Purpose:** Client-side API access with Row Level Security (RLS)

**Format:** JWT token (`eyJ...`)

**Storage:**
- Development: `.env` file (gitignored)
- Production: Environment variable `SUPABASE_ANON_KEY`

**Usage:**
```python
# Client initialization
from supabase import create_client

client = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_ANON_KEY")
)
```

**Security Considerations:**
- Safe to expose in client-side code
- RLS policies enforce access control
- Cannot bypass database security rules

**Rotation:**
- Requires Supabase project key regeneration
- All clients must update to new key
- No transition period (immediate swap)

---

### 1.2 Service Role Key (Secret)

**Purpose:** Backend service access bypassing RLS

**Format:** JWT token (`eyJ...`)

**Storage:**
- Development: `.env` file (gitignored)
- Production: Secret manager (e.g., AWS Secrets Manager, Vault)
- **NEVER** commit to version control

**Usage:**
```python
# Backend service initialization (ONLY in trusted backend code)
from supabase import create_client

admin_client = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_SERVICE_KEY")
)
```

**Security Considerations:**
- **CRITICAL:** Bypasses all RLS policies
- Must only be used in trusted backend services
- Never expose to client-side code
- Log all operations using this key

**Rotation:**
- Requires Supabase project key regeneration
- Coordinate with deployment to update all services
- Brief downtime may be required

---

## 2. Agent Keys (Ed25519)

### 2.1 Purpose

Agent keys sign events to provide cryptographic attribution (FR74, FR75).

**Constitutional Constraints:**
- FR74: Invalid agent signatures MUST be rejected
- FR75: Track active keys with temporal validity
- FR76: Historical keys NEVER deleted (append-only)
- MA-2: Signature MUST cover prev_hash (chain binding)

### 2.2 Key Format

```python
@dataclass(frozen=True)
class AgentKey:
    id: UUID                    # Unique record ID
    agent_id: str               # "agent-{uuid}" or "SYSTEM:{service_name}"
    key_id: str                 # HSM key identifier
    public_key: bytes           # Ed25519 public key (32 bytes)
    active_from: datetime       # UTC timestamp
    active_until: datetime | None  # None = currently active
```

### 2.3 Agent ID Formats

| Format | Example | Use Case |
|--------|---------|----------|
| Regular Agent | `agent-550e8400-e29b-41d4-a716-446655440000` | AI agents (72 Archons) |
| System Agent | `SYSTEM:EventWriter` | Internal services |

### 2.4 Storage

**Development:**
- HSM Stub: `~/.archon72/dev_keys.json`
- File permissions: 0600 (owner read/write only)
- Watermark: `[DEV MODE]` in signed content

**Production:**
- Cloud HSM (AWS CloudHSM, Azure HSM, etc.)
- Key material never leaves HSM
- Only public keys exported for verification

### 2.5 Key Lifecycle

```
[Generate] → [Register] → [Active] → [Deactivate] → [Historical]
                              ↑
                              └── Cannot delete (FR76)
```

**Generation:**
```python
# Generate new agent key pair
public_key, key_id = await hsm.generate_key_pair()

# Register in key registry
agent_key = AgentKey(
    id=uuid4(),
    agent_id=f"agent-{agent_uuid}",
    key_id=key_id,
    public_key=public_key,
    active_from=datetime.now(UTC),
    active_until=None
)
await key_registry.register_key(agent_key)
```

**Deactivation (Rotation):**
```python
# Deactivate old key (sets active_until, never deletes)
await key_registry.deactivate_key(
    key_id=old_key_id,
    active_until=datetime.now(UTC)
)

# Generate and register new key
# ... (same as generation)
```

### 2.6 Signing Events

```python
# Sign event with agent key
signature = await signing_service.sign_event(
    content_hash=event.content_hash,
    prev_hash=event.prev_hash,
    agent_id=event.agent_id
)

# Signature covers: agent_id + content_hash + prev_hash (chain binding)
```

### 2.7 Verification

```python
# Verify event signature
is_valid = await signing_service.verify_event_signature(
    signature=event.signature,
    content_hash=event.content_hash,
    prev_hash=event.prev_hash,
    agent_id=event.agent_id,
    signed_at=event.authority_timestamp  # For temporal validation
)
```

---

## 3. Keeper Keys (Ed25519)

### 3.1 Purpose

Keeper keys sign override commands (FR68-FR70). Keepers are human operators with elevated privileges.

**Constitutional Constraints:**
- FR68: Override commands require cryptographic signature from registered Keeper key
- FR69: Keeper keys SHALL be generated through witnessed ceremony
- FR70: Full authorization chain must be recorded
- CT-12: Witnessing creates accountability

### 3.2 Key Format

```python
@dataclass(frozen=True)
class KeeperKey:
    id: UUID                    # Unique record ID
    keeper_id: str              # "KEEPER:{name}" (e.g., "KEEPER:alice")
    key_id: str                 # HSM key identifier
    public_key: bytes           # Ed25519 public key (32 bytes)
    active_from: datetime       # UTC timestamp
    active_until: datetime | None  # None = currently active
```

### 3.3 Key Generation Ceremony (FR69)

Keeper keys MUST be generated through a witnessed ceremony:

```
[Start Ceremony] → [Collect Witnesses] → [Execute] → [Complete]
     │                    │                  │           │
     └── HALT CHECK       └── Verify sigs    └── HSM gen └── Register key
```

**Ceremony Requirements:**
- Minimum 3 witnesses (REQUIRED_WITNESSES threshold)
- Each witness must sign: `ceremony_id:witness_id:keeper_id`
- Ceremony timeout: 3600 seconds (1 hour)
- One ceremony at a time per Keeper (CM-5)

**Example Ceremony Flow:**
```python
# 1. Start ceremony
ceremony = await ceremony_service.start_ceremony(
    keeper_id="KEEPER:alice",
    initiator_id="KEEPER:bob"
)

# 2. Collect witness attestations
for witness_id, signature in witness_attestations:
    await ceremony_service.add_witness(
        ceremony_id=ceremony.id,
        witness_id=witness_id,
        signature=signature
    )

# 3. Execute when threshold met (automatic)
# Ceremony transitions: PENDING → APPROVED → EXECUTING → COMPLETED
```

### 3.4 Key Rotation (30-Day Transition)

Keeper key rotation uses a 30-day transition period where both old and new keys are valid:

```
Day 0:  [Generate new key via ceremony]
        [Old key: active]
        [New key: active]

Day 1-29: [Both keys valid for signing]
          [Both keys valid for verification]

Day 30: [Old key: deactivated (active_until set)]
        [New key: active (sole key)]
```

**Transition API:**
```python
# Begin transition (generates new key, both valid)
await keeper_key_registry.begin_transition(keeper_id="KEEPER:alice")

# Complete transition (deactivates old key)
await keeper_key_registry.complete_transition(keeper_id="KEEPER:alice")
```

### 3.5 Signing Overrides

```python
# Sign override command
signature = await keeper_signature_service.sign_override(
    keeper_id="KEEPER:alice",
    override_payload={
        "action_type": "HALT_SYSTEM",
        "scope": "GLOBAL",
        "duration": 3600,
        "reason": "Emergency maintenance"
    }
)

# Signature covers canonical JSON of payload
```

### 3.6 Verification

```python
# Verify override signature
is_valid = await keeper_signature_service.verify_override_signature(
    signature=override.signature,
    keeper_id=override.keeper_id,
    override_payload=override.payload,
    signed_at=override.initiated_at  # For temporal validation
)
```

---

## 4. Witness Keys (Ed25519)

### 4.1 Purpose

Witness keys attest to events, providing accountability (FR4, FR5, CT-12).

**Constitutional Constraints:**
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
- CT-12: Witnessing creates accountability

### 4.2 Key Format

```python
@dataclass(frozen=True)
class Witness:
    witness_id: str             # "WITNESS:{uuid}"
    public_key: bytes           # Ed25519 public key (32 bytes)
    active_from: datetime       # UTC timestamp
    active_until: datetime | None  # None = currently active
```

### 4.3 Witness Selection

Witnesses are selected using verifiable randomness (FR32):

```python
# Select witness with verifiable seed
witness = await witness_selection_service.select_witness(
    seed=entropy_seed,
    exclude_ids=["WITNESS:recent-1", "WITNESS:recent-2"]
)
```

### 4.4 Witness Signing

```python
# Witness signs event
witness_signature = await witness_service.sign_event(
    event=event,
    witness_id=witness.witness_id
)
```

---

## 5. Environment Configuration

### 5.1 Development Environment

```bash
# .env (gitignored)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# HSM Configuration
DEV_MODE=true
HSM_KEY_PATH=~/.archon72/dev_keys.json
```

### 5.2 Production Environment

```bash
# Environment variables (set via deployment platform)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=<from-secret-manager>

# HSM Configuration
DEV_MODE=false
HSM_PROVIDER=aws-cloudhsm
HSM_CLUSTER_ID=cluster-xxx
```

---

## 6. Security Best Practices

### 6.1 Key Storage

| Environment | Key Type | Storage Method |
|-------------|----------|----------------|
| Development | All | `.env` file (gitignored) + HSM stub |
| Staging | Supabase | Environment variables |
| Staging | Ed25519 | Cloud HSM (test cluster) |
| Production | Supabase | Secret manager |
| Production | Ed25519 | Cloud HSM (production cluster) |

### 6.2 Key Rotation Schedule

| Key Type | Rotation Frequency | Procedure |
|----------|-------------------|-----------|
| Supabase Keys | As needed (breach) | Project key regeneration |
| Agent Keys | Quarterly | Registry deactivation + new key |
| Keeper Keys | Annually | Witnessed ceremony + 30-day transition |
| Witness Keys | Quarterly | Registry deactivation + new key |

### 6.3 Incident Response

**Key Compromise Procedures:**

1. **Immediate Actions:**
   - Deactivate compromised key immediately
   - Generate replacement key
   - Log incident as constitutional breach

2. **Investigation:**
   - Review audit trail for unauthorized signatures
   - Identify scope of compromise
   - Assess impact on event integrity

3. **Recovery:**
   - Issue new keys to affected entities
   - Update all dependent services
   - Document incident and remediation

---

## 7. Audit Trail

All key operations are logged as constitutional events:

| Event Type | Trigger | Data Captured |
|------------|---------|---------------|
| `KEY_GENERATED` | Key creation | key_id, entity_id, public_key |
| `KEY_REGISTERED` | Registry add | key_id, entity_id, active_from |
| `KEY_DEACTIVATED` | Rotation/revocation | key_id, entity_id, active_until, reason |
| `CEREMONY_STARTED` | Keeper key ceremony | ceremony_id, keeper_id, initiator_id |
| `CEREMONY_WITNESSED` | Witness attestation | ceremony_id, witness_id |
| `CEREMONY_COMPLETED` | Key generated | ceremony_id, new_key_id |

---

## 8. Quick Reference

### Common Operations

**Check if key is active:**
```python
key.is_active_at(datetime.now(UTC))
```

**Get active key for agent:**
```python
key = await key_registry.get_active_key_for_agent(agent_id)
```

**Verify signature with temporal check:**
```python
# Ensure key was active at signing time
key = await key_registry.get_active_key_for_agent(agent_id)
if not key.is_active_at(signed_at):
    raise InvalidSignatureError("Key not active at signing time")
```

---

## References

- [Security Audit Plan](/docs/operations/security-audit-plan.md)
- [Full Project Retrospective](/_bmad-output/implementation-artifacts/full-project-retrospective-2026-01-09.md)
- [Story 5-6: Keeper Key Cryptographic Signature](/_bmad-output/implementation-artifacts/stories/5-6-keeper-key-cryptographic-signature.md)
- [Story 5-7: Keeper Key Generation Ceremony](/_bmad-output/implementation-artifacts/stories/5-7-keeper-key-generation-ceremony.md)

---

*Document Version: 1.0*
*Last Updated: 2026-01-09*
