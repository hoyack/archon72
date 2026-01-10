# NCC Group Engagement - Outreach Materials (Backup)

**Project:** Archon 72 Conclave Backend
**Date:** 2026-01-09
**Target Firm:** NCC Group - Cryptography Services
**Status:** Backup option if Trail of Bits unavailable

---

## Outreach Email

**To:** https://www.nccgroup.com/us/contact-us/ (web form)
**Subject:** Cryptography Security Audit - AI Governance System (Ed25519/HSM/Hash Chains)

---

Dear NCC Group Cryptography Services Team,

We are seeking an external security audit focused on cryptographic components for **Archon 72**, a constitutional AI governance system. Your dedicated Cryptography Services practice and experience with HSM implementations, threshold cryptography, and protocol review align well with our requirements.

### Why NCC Group Cryptography Services

Your team's expertise is particularly relevant:
- **Dedicated cryptography practice** with specialists focused exclusively on crypto implementations
- **HSM and key management experience** from audits like Ontology blockchain infrastructure
- **Protocol review expertise** demonstrated in TLS 1.3, threshold ECDSA, and Keybase audits
- **Published audit reports** showing rigorous methodology

### Technical Overview

| Attribute | Details |
|-----------|---------|
| Language | Python 3.11+ |
| Framework | FastAPI |
| Cryptography | Ed25519 (PyNaCl), SHA-256 |
| Key Management | HSM abstraction (dev/cloud modes) |
| Architecture | Hexagonal (Ports & Adapters) |
| Codebase Size | ~50,000 lines |

### Cryptographic Components Requiring Audit

1. **HSM Integration**
   - Hardware Security Module abstraction layer
   - Development mode: plaintext key storage with mode watermark
   - Production mode: cloud HSM integration (AWS/Azure)
   - Environment validation to prevent mode confusion
   - **Key concern:** Dev keys must never work in production

2. **Ed25519 Signing Services**
   - Agent signature service (event attribution)
   - Keeper signature service (human override commands)
   - Witness attestation service (multi-party accountability)
   - Chain binding: signatures cover previous hash
   - Mode watermark embedded INSIDE signed content (not metadata)

3. **Key Generation Ceremony**
   - Multi-witness key creation protocol (3 witnesses required)
   - 1-hour ceremony timeout with state machine
   - 30-day key rotation transition period
   - Emergency revocation path for compromised keys
   - Bootstrap mode for initial system setup

4. **Hash Chain Integrity**
   - SHA-256 append-only event store
   - Canonical JSON hashing for determinism
   - Hash computation in PostgreSQL triggers (trust boundary)
   - Automatic system halt on integrity violations
   - Merkle tree proofs for light verification

### Known Security Findings (Internal)

We have identified and mitigated three findings internally and seek cryptographic validation:

| ID | Finding | Cryptographic Impact | Mitigation |
|----|---------|---------------------|------------|
| H1 | Environment variable poisoning | Dev mode allows plaintext keys in prod | Secondary environment validation |
| H2 | Unverified witnesses in bootstrap | Ceremonies could accept forged attestations | Explicit opt-in + audit logging |
| H3 | 30-day key rotation overlap | Compromised key usable during transition | Emergency revocation bypasses window |

### Desired Engagement

- **Focus:** Cryptographic implementation correctness and security
- **Scope:** HSM, signing services, key ceremony, hash chain
- **Duration:** Estimated 2-3 weeks
- **Deliverables:** Technical report, vulnerability assessment, remediation guidance

### Specific Cryptographic Questions

1. Is our Ed25519 implementation using PyNaCl correctly?
2. Does the mode watermark inside signatures prevent stripping attacks?
3. Is our canonical JSON hashing deterministic across platforms?
4. Are there timing attacks in our signature verification?
5. Is the 3-witness threshold sufficient for key generation ceremonies?

### Next Steps

We have prepared detailed documentation including architecture diagrams, security patterns (RT-1, FP-5, MA-2), and file inventories.

Would your Cryptography Services team be available for an introductory call to discuss scope and approach? I can share the complete documentation package upon confirmation of interest.

Best regards,

[Name]
[Title]
[Email]
[Phone]

---

## Attachment Checklist

When NCC Group responds, share these documents:

- [ ] `docs/security/audit-engagement-scope.md` - Full RFP
- [ ] `docs/security/external-security-audit-preparation.md` - Technical context
- [ ] `docs/security/audit-executive-brief.md` - Executive summary
- [ ] Repository access instructions (read-only)

---

## Call Preparation (NCC Group Specific)

### Key Points to Discuss

1. **Cryptography Focus**
   - Ed25519 implementation review
   - HSM abstraction security
   - Key ceremony protocol analysis
   - Hash chain integrity verification

2. **Team Composition**
   - Will Cryptography Services practice handle this?
   - Specialist availability
   - Multi-reviewer approach?

3. **Methodology**
   - Formal verification vs. manual review
   - Dynamic testing of crypto operations
   - Fuzzing of signature verification

4. **Compliance Alignment**
   - SOC 2 considerations
   - Audit report format for compliance use

### Questions to Ask NCC Group

1. How does your Cryptography Services practice approach HSM abstraction review?
2. Have you audited similar event-sourcing systems with hash chains?
3. What formal methods do you use for Ed25519 implementation verification?
4. Can you provide references for Python cryptography audits?
5. How do you structure findings for cryptographic vulnerabilities vs. implementation bugs?

---

## NCC Group vs. Trail of Bits Comparison

| Aspect | Trail of Bits | NCC Group |
|--------|---------------|-----------|
| **Python Expertise** | ★★★★★ (PyPI audit) | ★★★☆☆ |
| **Crypto Expertise** | ★★★★★ | ★★★★★ (dedicated practice) |
| **HSM Experience** | ★★★★☆ | ★★★★★ |
| **Published Audits** | Many | Many (TLS, ECDSA, Keybase) |
| **Engagement Style** | Shared Slack, weekly syncs | Formal, structured |
| **Pricing** | $$$$ | $$$$ |

**Recommendation:**
- Trail of Bits for comprehensive Python + crypto
- NCC Group if crypto depth is paramount or Trail of Bits unavailable

---

## Follow-up Timeline (if Trail of Bits falls through)

| Day | Action |
|-----|--------|
| 0 | Submit NCC Group contact form |
| 2 | Follow up via LinkedIn or direct email |
| 5 | Schedule introductory call |
| 10 | Receive proposal |

---

## NCC Group Contact Channels

| Channel | URL/Contact |
|---------|-------------|
| **Primary** | https://www.nccgroup.com/us/contact-us/ |
| **Cryptography Services** | https://www.nccgroup.com/us/assessment-advisory/cryptography/ |
| **LinkedIn** | Search "NCC Group Cryptography Services" |

---

## When to Activate NCC Group Backup

Trigger NCC Group outreach if:

1. Trail of Bits does not respond within 7 days
2. Trail of Bits timeline doesn't fit our schedule
3. Trail of Bits pricing exceeds budget significantly
4. Trail of Bits lacks crypto specialist availability

---

*Document Version: 1.0*
*Last Updated: 2026-01-09*
*Status: Backup - Activate if Trail of Bits unavailable*
