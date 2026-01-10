# Archon 72 - Security Audit Executive Brief

**For:** Trail of Bits Initial Call
**Date:** 2026-01-09
**Duration:** 30 minutes recommended

---

## What is Archon 72?

Archon 72 is a **constitutional AI governance system** where 72 autonomous AI agents ("Archons") deliberate and make collective decisions through parliamentary procedure.

**Core Principle:** All agent decisions must be cryptographically attributable, witnessed, and immutably recorded.

---

## Why Security Matters Here

| Risk | Impact |
|------|--------|
| Forged agent signatures | Decisions attributed to wrong agent |
| Tampered event history | Audit trail compromised |
| Bypassed human oversight | Keepers lose control |
| Mode confusion (dev/prod) | Production with weak crypto |

**Constitutional Truths enforced by the system:**
- **CT-11:** System halts on failures (never degrades)
- **CT-12:** Multiple witnesses required for accountability
- **CT-13:** Integrity outranks availability

---

## Security Architecture (1-Page Summary)

```
┌─────────────────────────────────────────────────────────────┐
│                    TRUST BOUNDARY                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              HSM (Hardware Security Module)          │   │
│  │  - Ed25519 key storage and signing                  │   │
│  │  - DevHSM (dev) vs CloudHSM (prod)                  │   │
│  │  - Mode watermark INSIDE signatures                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Signing Services Layer                  │   │
│  │  - SigningService (agent events)                    │   │
│  │  - KeeperSignatureService (human overrides)         │   │
│  │  - WitnessService (attestations)                    │   │
│  │  - Chain binding: signature covers prev_hash        │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Key Management                          │   │
│  │  - Key Generation Ceremony (3 witnesses)            │   │
│  │  - 30-day rotation overlap                          │   │
│  │  - Emergency revocation path                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Hash Chain (Event Store)                │   │
│  │  - SHA-256 with canonical JSON                      │   │
│  │  - Hash computed in PostgreSQL triggers             │   │
│  │  - Auto-halt on chain break                         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Audit Scope (Tiered)

### Tier 1: Critical (Must Audit)

| Component | Risk | Files |
|-----------|------|-------|
| HSM Integration | Mode confusion, key exposure | 4 |
| Signing Services | Signature forgery | 3 |
| Key Generation Ceremony | Unauthorized keys | 1 |
| Hash Chain | Tampered history | 2 |
| Environment Security | Dev mode in prod | 2 |

### Tier 2: High Priority

| Component | Risk | Files |
|-----------|------|-------|
| Key Registry | Key lifecycle issues | 3 |
| Merkle Tree Service | Proof manipulation | 1 |
| Witness Pool | Witness manipulation | 2 |

---

## Known Findings (Already Mitigated)

| ID | Issue | Fix |
|----|-------|-----|
| **H1** | DEV_MODE=true in production | Secondary ENVIRONMENT check |
| **H2** | Unverified witnesses at bootstrap | Explicit opt-in + audit log |
| **H3** | 30-day key rotation window | Emergency revocation |

**We need validation that these mitigations are effective.**

---

## Codebase at a Glance

| Metric | Value |
|--------|-------|
| Language | Python 3.11+ |
| Framework | FastAPI |
| Lines of Code | ~50,000 |
| Test Functions | 7,500+ |
| Architecture | Hexagonal (Ports & Adapters) |

**Test Coverage:** All security-critical paths have unit + integration tests.

---

## What We Need from the Audit

1. **Verify cryptographic implementation correctness**
   - Ed25519 signing/verification
   - SHA-256 hash chain
   - Merkle tree proofs

2. **Test security controls**
   - Environment validation (H1)
   - Bootstrap mode restrictions (H2)
   - Emergency revocation (H3)

3. **Identify unknown vulnerabilities**
   - Code review of critical components
   - Threat modeling
   - Penetration testing

4. **Provide remediation guidance**
   - Prioritized by severity
   - Specific code fixes
   - Retest verification

---

## Timeline Preference

| Phase | Duration |
|-------|----------|
| Kickoff + Discovery | 2-3 days |
| Assessment | 5-7 days |
| Report + Review | 2-3 days |
| Remediation (us) | 1-2 weeks |
| Retest | 1-2 days |

**Goal:** Complete before production deployment

---

## Questions for Trail of Bits

1. Have you audited similar event-sourced or AI governance systems?
2. Who would be assigned to this engagement (crypto specialists)?
3. What's your typical turnaround for a codebase of this size?
4. How do you handle critical findings mid-engagement?
5. What do you need from us to prepare a proposal?

---

## Contact

| Role | Responsibility |
|------|----------------|
| Project Lead | Architecture decisions, scope |
| Security Champion | Security design, Q&A |
| Dev Team Lead | Implementation details |

---

*This brief accompanies the full Audit Engagement Scope document.*
