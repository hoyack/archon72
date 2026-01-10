# External Security Audit Preparation Guide

**Project:** Archon 72 Conclave Backend
**Version:** 1.0
**Date:** 2026-01-09
**Status:** Pre-Production Security Review Required

---

## Executive Summary

This document prepares external security auditors for reviewing the Archon 72 constitutional AI governance system. The system implements cryptographic integrity guarantees for autonomous agent deliberations with human oversight ("Keeper") controls.

**Critical Security Properties:**
- Append-only event store with hash chain integrity
- Cryptographic agent attribution (Ed25519 signatures)
- Witness attestation for all constitutional actions
- Keeper override controls with ceremony-based key generation
- Automatic system halt on integrity violations

---

## 1. Audit Scope Overview

### 1.1 Priority 1 - Critical (Must Review)

| Component | Location | Risk Level |
|-----------|----------|------------|
| HSM Integration | `src/infrastructure/adapters/security/` | CRITICAL |
| Signing Services | `src/application/services/signing_service.py` | CRITICAL |
| Key Generation Ceremony | `src/application/services/key_generation_ceremony_service.py` | CRITICAL |
| Hash Chain Implementation | `src/domain/events/hash_utils.py` | CRITICAL |
| Environment Security | `src/api/startup.py`, `src/domain/models/signable.py` | HIGH |

### 1.2 Priority 2 - High (Should Review)

| Component | Location | Risk Level |
|-----------|----------|------------|
| Key Registry | `src/infrastructure/adapters/persistence/key_registry.py` | HIGH |
| Keeper Signature Service | `src/application/services/keeper_signature_service.py` | HIGH |
| Witness Service | `src/application/services/witness_service.py` | HIGH |
| Merkle Tree Service | `src/application/services/merkle_tree_service.py` | MEDIUM |

### 1.3 Priority 3 - Medium (Review if Time Permits)

| Component | Location | Risk Level |
|-----------|----------|------------|
| Witness Pool | `src/infrastructure/adapters/persistence/witness_pool.py` | MEDIUM |
| Hash Verification | `src/application/services/hash_verification_service.py` | MEDIUM |
| Anomaly Detection | `src/application/services/witness_anomaly_detection_service.py` | LOW |

---

## 2. Architecture Overview

### 2.1 Hexagonal Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                           │
│  (FastAPI routes, request/response handling)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  (Services, orchestration, business logic)                 │
│  - SigningService, WitnessService, KeyGenerationCeremony   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Domain Layer                           │
│  (Models, events, business rules)                          │
│  - AgentKey, KeeperKey, Signable, HashUtils                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                       │
│  (Adapters, persistence, external services)                │
│  - HSM adapters, KeyRegistry, WitnessPool                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Trust Boundaries

```
┌────────────────────────────────────────────────────────────────┐
│  UNTRUSTED ZONE                                                │
│  - External API requests                                       │
│  - Environment variables (partially)                           │
└────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ VALIDATION LAYER  │
                    │ - Startup checks  │
                    │ - Request auth    │
                    └─────────┬─────────┘
                              │
┌────────────────────────────────────────────────────────────────┐
│  TRUSTED APPLICATION ZONE                                      │
│  - Signing services                                            │
│  - Business logic                                              │
└────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  CRYPTO BOUNDARY  │
                    │  - HSM operations │
                    │  - Key storage    │
                    └─────────┬─────────┘
                              │
┌────────────────────────────────────────────────────────────────┐
│  HIGHEST TRUST ZONE - HSM / Database                           │
│  - Hash computation (DB triggers)                              │
│  - Key material (HSM)                                          │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. Critical Security Components

### 3.1 HSM (Hardware Security Module)

**Files:**
- `src/application/ports/hsm.py` - Protocol definition
- `src/infrastructure/adapters/security/hsm_factory.py` - Mode selection
- `src/infrastructure/adapters/security/hsm_dev.py` - Development stub
- `src/infrastructure/adapters/security/hsm_cloud.py` - Production (placeholder)

**Security Design:**
- **RT-1 Pattern**: Mode watermark (`[DEV MODE]` or `[PROD]`) embedded INSIDE signed content
- Watermark cannot be stripped without invalidating signature
- DevHSM stores keys in plaintext JSON at `~/.archon72/dev_keys.json`
- File permissions: 0o600 (owner read/write only)
- CloudHSM raises `HSMNotConfiguredError` until properly implemented

**Known Mitigations:**
- **H1 Fix**: Secondary environment validation prevents DEV_MODE in production
- Validation checks `ENVIRONMENT` variable against `DEV_MODE` flag

**Audit Focus:**
- [ ] Verify RT-1 watermark cannot be bypassed
- [ ] Review DevHSM key file security
- [ ] Validate H1 environment poisoning fix
- [ ] Review CloudHSM integration design (when implemented)

### 3.2 Signing Services

**Files:**
- `src/application/services/signing_service.py` - Agent event signing
- `src/application/services/keeper_signature_service.py` - Keeper override signing
- `src/application/services/witness_service.py` - Witness attestation

**Security Design:**
- **FP-5 Pattern**: All signing centralized through dedicated services
- **MA-2 Pattern**: Chain binding - signature covers prev_hash
- Algorithm: Ed25519 (version 1, tracked for future migration)
- Signatures cover: (content_hash, prev_hash, agent_id)

**Audit Focus:**
- [ ] Verify Ed25519 implementation correctness
- [ ] Test chain binding (MA-2) prevents event repositioning
- [ ] Validate signature verification logic
- [ ] Check for timing attacks in verification

### 3.3 Key Generation Ceremony (FR69)

**File:** `src/application/services/key_generation_ceremony_service.py`

**Ceremony Flow:**
```
PENDING → (witnesses sign) → APPROVED → (execute) → COMPLETED
    │                            │                        │
    └─── EXPIRED (1hr timeout)   └─── FAILED (error)     │
                                                          │
                         Key registered, 30-day transition ◄┘
```

**Security Design:**
- **REQUIRED_WITNESSES**: 3 signatures needed for approval
- **CEREMONY_TIMEOUT_SECONDS**: 1 hour expiration
- **30-day transition period**: Both old and new keys valid
- **H2 Fix**: Bootstrap mode for initial setup (requires WITNESS_BOOTSTRAP_ENABLED=true)
- **H3 Fix**: Emergency revocation bypasses 30-day period

**Known Mitigations:**
- H2: Bootstrap mode explicitly logged, requires env var
- H3: Emergency revoke creates audit event with reason

**Audit Focus:**
- [ ] Test witness signature verification
- [ ] Validate ceremony timeout enforcement
- [ ] Review bootstrap mode security constraints
- [ ] Test emergency revocation path
- [ ] Verify CM-5 (single ceremony per Keeper)

### 3.4 Hash Chain Integrity

**File:** `src/domain/events/hash_utils.py`

**Security Design:**
- Algorithm: SHA-256 (version tracked in events)
- Genesis hash: 64 zeros for first event
- Canonical JSON: sorted keys, compact format
- Content hash covers: event_type, payload, signature, witness_id, witness_signature, local_timestamp
- Excluded: prev_hash, content_hash, sequence, authority_timestamp

**Database-Level Trust (ADR-1):**
- Hash computation performed in PostgreSQL triggers
- Application CANNOT fabricate hashes
- Append-only enforcement at database level

**Audit Focus:**
- [ ] Verify canonical JSON hashing is deterministic
- [ ] Test hash chain continuity verification
- [ ] Validate database trigger implementation
- [ ] Check for hash collision handling

---

## 4. Known Security Findings & Mitigations

### H1 - Environment Variable Poisoning (MITIGATED)

**Risk:** `DEV_MODE=true` in production allows plaintext key storage
**Attack:** Set DEV_MODE environment variable in production deployment
**Mitigation:** Secondary validation at startup

```python
# src/domain/models/signable.py
def validate_dev_mode_consistency():
    dev_mode = is_dev_mode()        # DEV_MODE env var
    environment = _detect_environment()  # ENVIRONMENT env var

    if dev_mode and is_production_environment():
        raise DevModeEnvironmentMismatchError(
            "DEV_MODE=true not allowed in production"
        )
```

**Audit Verify:**
- [ ] Test bypassing H1 fix with various environment combinations
- [ ] Verify error prevents startup, not just logging

### H2 - Unverified Witnesses in Bootstrap (MITIGATED)

**Risk:** Witnesses accepted without signature verification during bootstrap
**Attack:** Register malicious witnesses during initial setup
**Mitigation:** Explicit opt-in via environment variable + audit logging

```python
# Requires: WITNESS_BOOTSTRAP_ENABLED=true
# All unverified acceptances logged as events
```

**Audit Verify:**
- [ ] Verify bootstrap mode cannot be enabled accidentally
- [ ] Confirm all unverified witnesses create audit events
- [ ] Test transition from bootstrap to verified mode

### H3 - 30-Day Key Rotation Overlap (MITIGATED)

**Risk:** Compromised key usable for 30 days during rotation
**Attack:** Compromise key, use during transition period
**Mitigation:** Emergency revocation path bypasses transition

```python
# key_generation_ceremony_service.py
async def emergency_revoke_key(
    key_id: str,
    reason: str,
    revoked_by: str
) -> None:
    # Immediate revocation, creates audit event
```

**Audit Verify:**
- [ ] Test emergency revocation immediacy
- [ ] Verify revoked keys cannot be used
- [ ] Confirm audit trail for emergency revocations

---

## 5. Constitutional Security Properties

### 5.1 Constitutional Truths Referenced

| CT | Name | Security Implication |
|----|------|---------------------|
| CT-11 | Halt Over Degrade | System halts on integrity failures, never continues degraded |
| CT-12 | Witnessing Creates Accountability | Multiple witness signatures for constitutional actions |
| CT-13 | Integrity Outranks Availability | Hash mismatch triggers immediate halt |

### 5.2 Functional Requirements to Verify

| FR | Description | Audit Action |
|----|-------------|--------------|
| FR68 | Override commands require registered Keeper key signature | Test signature verification |
| FR69 | New Keeper key requires multi-witness ceremony | Test ceremony flow |
| FR74-FR76 | Agent signing with registered keys | Test key registration |
| FR82-FR85 | Hash chain integrity | Test chain verification |
| FR125 | Published selection algorithm | Review witness selection |

---

## 6. Files Requiring Audit

### 6.1 Critical Priority Files

```
src/infrastructure/adapters/security/
├── hsm_factory.py          # Mode selection logic
├── hsm_dev.py              # Development key storage
└── hsm_cloud.py            # Production HSM (placeholder)

src/application/services/
├── signing_service.py              # Agent signing
├── keeper_signature_service.py     # Keeper signing
├── witness_service.py              # Witness attestation
├── key_generation_ceremony_service.py  # Key ceremonies
├── hash_verification_service.py    # Chain verification
└── merkle_tree_service.py          # Merkle proofs

src/domain/
├── events/hash_utils.py    # Hash computation
├── models/signable.py      # Mode watermark + env validation
├── models/agent_key.py     # Agent key model
└── models/keeper_key.py    # Keeper key model

src/api/
└── startup.py              # Startup security validation
```

### 6.2 Supporting Files

```
src/infrastructure/adapters/persistence/
├── key_registry.py         # Key storage (in-memory)
└── witness_pool.py         # Witness management

src/application/ports/
├── hsm.py                  # HSM protocol
└── key_registry.py         # Registry protocol
```

---

## 7. Test Coverage for Security

### 7.1 Existing Security Tests

```
tests/unit/infrastructure/test_hsm_dev.py
tests/integration/test_agent_signing_integration.py
tests/integration/test_keeper_key_signature_integration.py
tests/integration/test_witness_attribution_integration.py
tests/integration/test_key_generation_ceremony_integration.py
tests/integration/test_hash_chain_integration.py
tests/integration/test_hash_verification_integration.py
```

### 7.2 Recommended Additional Tests

- [ ] Environment poisoning attempt tests (H1)
- [ ] Bootstrap mode abuse scenarios (H2)
- [ ] Key rotation during active compromise (H3)
- [ ] Signature replay attacks
- [ ] Hash collision resistance verification
- [ ] Timing attack resistance in verification

---

## 8. Engagement Recommendations

### 8.1 Suggested Audit Timeline

| Phase | Focus | Deliverable |
|-------|-------|-------------|
| 1 | HSM & Key Management | HSM security assessment |
| 2 | Cryptographic Operations | Crypto implementation review |
| 3 | Environment Security | Deployment security review |
| 4 | Integration Testing | Penetration test findings |

### 8.2 Required Auditor Access

- [ ] Source code repository (read-only)
- [ ] Development environment setup guide
- [ ] Architecture documentation (`docs/` folder)
- [ ] ADR documents (12 total)
- [ ] Test environment with DevHSM

### 8.3 Pre-Audit Preparation Checklist

- [ ] All tests passing (`make test`)
- [ ] Documentation current
- [ ] Known issues documented
- [ ] Environment setup reproducible
- [ ] Contact person designated

---

## 9. Contacts

| Role | Responsibility |
|------|---------------|
| Project Lead | Architecture decisions, scope clarification |
| Security Champion | Security design questions |
| Dev Team Lead | Implementation details |

---

## Appendix A: Security Architecture Patterns

### RT-1: Mode Watermark Inside Signature

```python
# Mode watermark embedded in signed bytes
signable_content = f"[{mode}]{payload}".encode()
signature = hsm.sign(signable_content)

# Verification must reconstruct with mode
def verify(signature, payload, mode):
    expected = f"[{mode}]{payload}".encode()
    return hsm.verify(signature, expected)
```

### FP-5: Centralized Signing

All signing operations MUST go through dedicated service:
- Agent events → `SigningService`
- Keeper overrides → `KeeperSignatureService`
- Witness attestations → `WitnessService`

### MA-2: Chain Binding

Signature covers prev_hash to prevent event repositioning:
```python
signable = SignableContent(
    content_hash=event.content_hash,
    prev_hash=event.prev_hash,  # Chain binding
    agent_id=event.agent_id
)
```

---

## Appendix B: Environment Variables

| Variable | Purpose | Security Impact |
|----------|---------|-----------------|
| `DEV_MODE` | HSM selection | CRITICAL - plaintext vs HSM |
| `ENVIRONMENT` | Production detection | HIGH - H1 fix validation |
| `WITNESS_BOOTSTRAP_ENABLED` | Bootstrap mode | HIGH - unverified witnesses |
| `ALLOW_VERIFICATION_BYPASS` | Startup bypass | MEDIUM - dev only |

---

*Document Version: 1.0*
*Last Updated: 2026-01-09*
*Classification: Internal - Security Sensitive*
