# Security Audit Plan - Archon 72 Conclave Backend

**Created:** 2026-01-09
**Priority:** CRITICAL (from Full Project Retrospective)
**Status:** Planning

---

## Executive Summary

This document outlines the security audit plan for the Archon 72 Conclave Backend, a constitutional AI governance system with cryptographic integrity guarantees. The audit focuses on key management, signing operations, HSM integration, and attack surface analysis.

---

## Audit Scope

### In Scope

| Category | Components | Risk Level |
|----------|------------|------------|
| **HSM Implementation** | hsm_dev.py, hsm_cloud.py, hsm_factory.py, hsm.py port | CRITICAL |
| **Key Management** | AgentKey, KeeperKey, KeyRegistry, KeeperKeyRegistry | CRITICAL |
| **Signing Services** | SigningService, KeeperSignatureService, WitnessService | CRITICAL |
| **Key Generation Ceremony** | KeyGenerationCeremonyService, ceremony protocol | HIGH |
| **Witness Selection** | VerifiableWitnessSelectionService, entropy sources | HIGH |
| **Event Integrity** | Hash chain, append-only enforcement, signature verification | HIGH |
| **API Authentication** | Supabase keys, API key handling | MEDIUM |

### Out of Scope (for initial audit)

- UI/Frontend components (backend-only project)
- CrewAI agent implementation details
- Database schema design (covered in functional testing)
- Performance optimization

---

## Critical Attack Surfaces

### 1. Development HSM Key Storage (CRITICAL)

**Location:** `src/infrastructure/adapters/security/hsm_dev.py`

**Current Implementation:**
- Keys stored in `~/.archon72/dev_keys.json` (plaintext JSON)
- File permissions set to 0600
- In-memory key cache during runtime

**Attack Vectors:**
- [ ] File system access to key file
- [ ] Memory dump extraction
- [ ] Process inspection (ptrace, /proc/mem)
- [ ] Environment variable bypass to enable dev mode in production

**Audit Tasks:**
- [ ] Verify file permission enforcement
- [ ] Test environment variable isolation
- [ ] Review memory handling for key material
- [ ] Confirm [DEV MODE] watermark in all dev signatures

---

### 2. HSM Factory Selection (CRITICAL)

**Location:** `src/infrastructure/adapters/security/hsm_factory.py`

**Current Implementation:**
- `is_dev_mode()` environment check determines HSM selection
- Production mode returns CloudHSM (placeholder that fails)
- Development mode returns DevHSM

**Attack Vectors:**
- [ ] Environment variable injection (`DEV_MODE=true`)
- [ ] Configuration file manipulation
- [ ] Process environment inheritance

**Audit Tasks:**
- [ ] Review `is_dev_mode()` implementation
- [ ] Test CloudHSM fail-safe behavior
- [ ] Verify no fallback to DevHSM in production
- [ ] Document production HSM configuration requirements

---

### 3. Key Temporal Validity (CRITICAL)

**Locations:**
- `src/domain/models/agent_key.py`
- `src/domain/models/keeper_key.py`
- `src/application/ports/key_registry.py`
- `src/application/ports/keeper_key_registry.py`

**Current Implementation:**
- Keys have `active_from` and `active_until` timestamps
- `is_active_at(timestamp)` method validates temporal window
- 30-day transition period for key rotation

**Attack Vectors:**
- [ ] Clock skew between services
- [ ] Timezone manipulation
- [ ] Historical key reuse after deactivation
- [ ] Transition period exploitation (compromised key still valid)

**Audit Tasks:**
- [ ] Review temporal validation logic
- [ ] Test boundary conditions (exact timestamp matching)
- [ ] Verify timezone handling (UTC enforcement)
- [ ] Document key rotation procedures

---

### 4. Signature Content Reconstruction (HIGH)

**Locations:**
- `src/domain/events/signing.py`
- `src/application/services/signing_service.py`
- `src/application/services/keeper_signature_service.py`

**Current Implementation:**
- `compute_signable_content()` creates canonical bytes
- Canonical JSON: sorted keys, no whitespace
- Chain binding via `prev_hash` (MA-2 pattern)

**Attack Vectors:**
- [ ] JSON canonicalization inconsistency
- [ ] Whitespace injection
- [ ] Unicode normalization differences
- [ ] Field ordering manipulation

**Audit Tasks:**
- [ ] Verify canonical JSON implementation
- [ ] Test cross-platform signature verification
- [ ] Review chain binding (prev_hash inclusion)
- [ ] Confirm RT-1 mode watermark in signed content

---

### 5. Witness Signature Bootstrap (HIGH)

**Location:** `src/application/services/key_generation_ceremony_service.py`

**Current Implementation:**
- Unregistered witnesses allowed during initial bootstrap
- Warning logged but signature accepted
- Signature content: `ceremony_id:witness_id:keeper_id`

**Attack Vectors:**
- [ ] Rogue witness during initial setup
- [ ] Witness ID spoofing
- [ ] Insufficient witness threshold

**Audit Tasks:**
- [ ] Review bootstrap witness handling
- [ ] Verify REQUIRED_WITNESSES threshold
- [ ] Test ceremony state machine transitions
- [ ] Document witness onboarding procedure

---

### 6. Keeper/Agent ID Spoofing (MEDIUM)

**Locations:**
- `src/domain/models/agent_key.py` - Agent ID format
- `src/domain/models/keeper_key.py` - Keeper ID format
- `src/domain/models/witness.py` - Witness ID format

**Current Implementation:**
- Agent ID: `agent-{uuid}` or `SYSTEM:{service_name}`
- Keeper ID: `KEEPER:{name}`
- Witness ID: `WITNESS:{uuid}`
- Format validation at dataclass level only

**Attack Vectors:**
- [ ] ID collision (same name, different keys)
- [ ] System agent impersonation
- [ ] Cross-role ID confusion

**Audit Tasks:**
- [ ] Review ID format validation
- [ ] Test uniqueness constraints
- [ ] Verify registry enforcement
- [ ] Document ID generation procedures

---

## Audit Checklist

### Phase 1: Code Review (Internal)

**HSM Layer:**
- [ ] `hsm_dev.py` - Development HSM stub
- [ ] `hsm_cloud.py` - Production HSM placeholder
- [ ] `hsm_factory.py` - HSM selection logic
- [ ] `hsm.py` - HSM protocol definition

**Key Management:**
- [ ] `agent_key.py` - Agent key model
- [ ] `keeper_key.py` - Keeper key model
- [ ] `key_registry.py` - Agent key registry port
- [ ] `keeper_key_registry.py` - Keeper key registry port

**Signing Services:**
- [ ] `signing_service.py` - Event signing
- [ ] `keeper_signature_service.py` - Override signing
- [ ] `signing.py` - Signing utilities

**Ceremony:**
- [ ] `key_generation_ceremony.py` - Ceremony protocol
- [ ] `key_generation_ceremony_service.py` - Ceremony orchestration

### Phase 2: Dynamic Testing

**Key Generation:**
- [ ] Generate agent key pair
- [ ] Generate keeper key pair via ceremony
- [ ] Test key rotation with transition period
- [ ] Verify old key rejection after transition

**Signature Verification:**
- [ ] Sign and verify event
- [ ] Sign and verify override
- [ ] Test signature rejection (wrong key)
- [ ] Test signature rejection (expired key)
- [ ] Test cross-environment signature (dev vs prod)

**Attack Simulation:**
- [ ] Attempt environment variable bypass
- [ ] Attempt key file access
- [ ] Attempt clock manipulation
- [ ] Attempt ID spoofing

### Phase 3: External Audit (Recommended)

**Scope for External Auditor:**
1. Cryptographic implementation review (Ed25519 usage)
2. Key management lifecycle analysis
3. HSM integration security
4. Temporal validation robustness
5. Attack surface penetration testing

**Deliverables:**
- Vulnerability assessment report
- Remediation recommendations
- Compliance verification (if applicable)

---

## API Key Documentation Requirements

As identified in the retrospective, API key usage documentation is a critical priority.

### Key Types to Document

| Key Type | Purpose | Storage | Rotation |
|----------|---------|---------|----------|
| **Supabase Anon Key** | Public API access | Environment variable | Project recreation |
| **Supabase Service Key** | Backend service access | Environment variable | Project recreation |
| **Agent Keys (Ed25519)** | Event signing | HSM (dev: file) | Registry deactivation |
| **Keeper Keys (Ed25519)** | Override signing | HSM (dev: file) | Ceremony + 30-day transition |
| **Witness Keys (Ed25519)** | Event attestation | HSM (dev: file) | Registry deactivation |

### Documentation Sections Needed

1. **Key Generation Procedures**
   - Initial setup
   - Key rotation
   - Emergency revocation

2. **Key Storage Requirements**
   - Development environment
   - Production environment
   - Backup procedures

3. **Key Usage Guidelines**
   - Which key for which operation
   - Temporal validity rules
   - Chain binding requirements

4. **Incident Response**
   - Key compromise procedures
   - Audit trail analysis
   - Recovery steps

---

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation Status |
|------|------------|--------|-------------------|
| Dev HSM in production | Low | Critical | Environment gating |
| Key temporal bypass | Medium | High | Needs audit |
| Signature replay | Low | High | Chain binding (MA-2) |
| Witness bootstrap attack | Low | Medium | Warning logged |
| ID spoofing | Low | Medium | Format validation |
| Clock manipulation | Medium | Medium | Needs UTC enforcement |

---

## Timeline & Resources

### Internal Audit
- **Lead:** Dev Team
- **Scope:** Phase 1 (Code Review) + Phase 2 (Dynamic Testing)
- **Deliverable:** Internal audit report with findings

### External Audit
- **Provider:** TBD (recommend cryptography specialist)
- **Scope:** Phase 3 (Full security assessment)
- **Deliverable:** External audit report with certification

---

## Next Steps

1. **Immediate:** Complete API key usage documentation
2. **Short-term:** Execute Phase 1 internal code review
3. **Medium-term:** Execute Phase 2 dynamic testing
4. **Pre-production:** Engage external auditor for Phase 3

---

## References

- [Full Project Retrospective](/_bmad-output/implementation-artifacts/full-project-retrospective-2026-01-09.md)
- [Architecture Document](/_bmad-output/planning-artifacts/architecture.md)
- [ADR-1: Event Store Implementation](/_bmad-output/planning-artifacts/architecture.md#adr-001)
- [Story 5-6: Keeper Key Cryptographic Signature](/_bmad-output/implementation-artifacts/stories/5-6-keeper-key-cryptographic-signature.md)
- [Story 5-7: Keeper Key Generation Ceremony](/_bmad-output/implementation-artifacts/stories/5-7-keeper-key-generation-ceremony.md)

---

*Document Version: 1.0*
*Last Updated: 2026-01-09*
