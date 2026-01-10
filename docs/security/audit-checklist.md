# Security Audit Checklist

**Project:** Archon 72 Conclave Backend
**Date:** 2026-01-09

---

## Pre-Engagement Checklist

### Repository & Documentation
- [ ] Grant auditor read-only repository access
- [ ] Provide architecture overview document
- [ ] Share all 12 ADR documents
- [ ] Provide this audit preparation guide
- [ ] Share full project retrospective (known issues)

### Environment Setup
- [ ] Document reproducible dev environment setup
- [ ] Verify `make test` passes (all 7,500+ tests)
- [ ] Prepare isolated test environment
- [ ] Document all environment variables

### Team Availability
- [ ] Designate primary point of contact
- [ ] Schedule kickoff meeting
- [ ] Plan Q&A availability windows

---

## Audit Scope Checklist

### Priority 1: HSM & Key Management (CRITICAL)

**HSM Implementation:**
- [ ] Review `hsm_factory.py` mode selection logic
- [ ] Audit `hsm_dev.py` key storage security
- [ ] Verify RT-1 watermark cannot be bypassed
- [ ] Test H1 fix (environment validation)

**Key Generation Ceremony:**
- [ ] Review ceremony state machine
- [ ] Test multi-witness requirement (3)
- [ ] Verify ceremony timeout (1 hour)
- [ ] Test H2 bootstrap mode controls
- [ ] Test H3 emergency revocation

**Key Registry:**
- [ ] Review key lifecycle management
- [ ] Verify key immutability (FR76)
- [ ] Test key deactivation flow

### Priority 2: Cryptographic Operations (CRITICAL)

**Signing Services:**
- [ ] Verify Ed25519 implementation
- [ ] Test FP-5 centralized signing pattern
- [ ] Verify MA-2 chain binding
- [ ] Check for timing attacks

**Hash Chain:**
- [ ] Verify SHA-256 implementation
- [ ] Test canonical JSON determinism
- [ ] Verify hash chain continuity
- [ ] Test hash mismatch halt behavior

**Merkle Trees:**
- [ ] Verify tree construction
- [ ] Test proof generation
- [ ] Test proof verification

### Priority 3: Environment & Startup (HIGH)

**Startup Security:**
- [ ] Review `startup.py` validation sequence
- [ ] Test pre-operational verification
- [ ] Test configuration floor enforcement
- [ ] Verify production environment detection

**Environment Variables:**
- [ ] Test DEV_MODE protections
- [ ] Test ENVIRONMENT validation
- [ ] Test WITNESS_BOOTSTRAP_ENABLED controls
- [ ] Test ALLOW_VERIFICATION_BYPASS restrictions

---

## Known Security Findings to Verify

### H1 - Environment Poisoning
- [ ] Confirm DEV_MODE=true fails in production environment
- [ ] Test various environment variable combinations
- [ ] Verify startup blocks (not just logs)

### H2 - Bootstrap Mode
- [ ] Confirm requires explicit WITNESS_BOOTSTRAP_ENABLED=true
- [ ] Verify unverified witnesses create audit events
- [ ] Test transition to verified mode

### H3 - Key Rotation
- [ ] Test emergency revocation immediacy
- [ ] Verify revoked keys rejected
- [ ] Confirm audit trail created

---

## Post-Audit Checklist

### Findings Review
- [ ] Review all findings with auditor
- [ ] Classify severity (Critical/High/Medium/Low)
- [ ] Create remediation plan

### Remediation
- [ ] Address Critical findings before production
- [ ] Address High findings before production
- [ ] Document accepted risks for Medium/Low
- [ ] Re-test after fixes

### Documentation
- [ ] Update security documentation
- [ ] Archive audit report
- [ ] Update CLAUDE.md with findings

---

## Quick Reference

**Critical Files:**
```
src/infrastructure/adapters/security/hsm_*.py
src/application/services/signing_service.py
src/application/services/key_generation_ceremony_service.py
src/domain/events/hash_utils.py
src/domain/models/signable.py
src/api/startup.py
```

**Key Tests:**
```
tests/unit/infrastructure/test_hsm_dev.py
tests/integration/test_agent_signing_integration.py
tests/integration/test_key_generation_ceremony_integration.py
tests/integration/test_hash_chain_integration.py
```

**Constitutional Truths:**
- CT-11: Halt over degrade
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

---

*Checklist Version: 1.0*
