# Security Audit Engagement Scope

**Document Type:** Request for Proposal / Scope of Work
**Project:** Archon 72 Conclave Backend
**Version:** 1.0
**Date:** 2026-01-09

---

## 1. Executive Summary

### 1.1 Project Overview

Archon 72 is a constitutional AI governance system where 72 autonomous AI agents ("Archons") deliberate and make collective decisions through parliamentary procedure. The system implements cryptographic integrity guarantees to ensure:

- Immutable audit trail of all decisions
- Cryptographic attribution of agent actions
- Human oversight ("Keeper") controls with ceremony-based authorization
- Automatic system halt on integrity violations

### 1.2 Audit Objective

We seek an independent external security audit to validate the cryptographic integrity and security properties of the system before production deployment. The audit should identify vulnerabilities, verify security controls, and provide actionable remediation guidance.

### 1.3 Business Context

This system will govern autonomous AI agent decisions with real-world consequences. Security failures could result in:
- Undetected tampering of governance records
- Unauthorized agent impersonation
- Bypass of human oversight controls
- Loss of audit trail integrity

---

## 2. Technical Environment

### 2.1 Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.11+ |
| Framework | FastAPI | Latest |
| Database | PostgreSQL (Supabase) | 15+ |
| AI Orchestration | CrewAI | Latest |
| Cryptography | Ed25519 (PyNaCl) | Latest |
| Architecture | Hexagonal (Ports & Adapters) | N/A |

### 2.2 Codebase Statistics

| Metric | Value |
|--------|-------|
| Lines of Code | ~50,000 |
| Test Files | 437 |
| Test Functions | ~7,500 |
| Application Services | 60+ |
| Domain Models | 40+ |
| Infrastructure Adapters | 30+ |

### 2.3 Repository Structure

```
archon72/
├── src/
│   ├── api/              # FastAPI routes and startup
│   ├── application/      # Services and ports
│   │   ├── services/     # Business logic (60+ services)
│   │   └── ports/        # Interface definitions
│   ├── domain/           # Models, events, errors
│   │   ├── models/       # Domain entities
│   │   └── events/       # Event definitions
│   └── infrastructure/   # Adapters and implementations
│       ├── adapters/
│       │   ├── security/ # HSM implementations
│       │   └── persistence/ # Storage adapters
│       └── stubs/        # Development stubs
├── tests/
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── chaos/           # Chaos testing
├── migrations/          # Database migrations
└── docs/               # Documentation
```

---

## 3. Audit Scope

### 3.1 In-Scope Components

#### Tier 1: Critical (Required)

| Component | Description | Files | Estimated Effort |
|-----------|-------------|-------|------------------|
| HSM Integration | Hardware Security Module abstraction, key storage, mode selection | 4 files | High |
| Signing Services | Agent, Keeper, and Witness signature operations | 3 files | High |
| Key Generation Ceremony | Multi-witness key creation protocol | 1 file | High |
| Hash Chain Implementation | SHA-256 chain integrity, canonical hashing | 2 files | Medium |
| Environment Security | Startup validation, mode detection | 2 files | Medium |

#### Tier 2: High Priority (Required)

| Component | Description | Files | Estimated Effort |
|-----------|-------------|-------|------------------|
| Key Registry | Key lifecycle, registration, deactivation | 3 files | Medium |
| Merkle Tree Service | Proof generation and verification | 1 file | Medium |
| Witness Pool | Witness selection and management | 2 files | Medium |
| Hash Verification | Chain continuity verification | 1 file | Low |

#### Tier 3: Medium Priority (Recommended)

| Component | Description | Files | Estimated Effort |
|-----------|-------------|-------|------------------|
| Anomaly Detection | Witness behavior monitoring | 2 files | Low |
| Database Triggers | PostgreSQL hash enforcement | 4 files | Low |
| API Authentication | Request validation | 2 files | Low |

### 3.2 Out-of-Scope

The following are explicitly excluded from this audit:

- CrewAI framework internals (third-party)
- Supabase platform security (managed service)
- Frontend applications (none exist)
- Network infrastructure and deployment
- Business logic correctness (non-security)
- Performance optimization
- General code quality (non-security)

### 3.3 Specific Security Properties to Verify

| Property | Requirement | Verification Method |
|----------|-------------|---------------------|
| **Signature Integrity** | Ed25519 signatures cannot be forged | Code review + testing |
| **Chain Immutability** | Hash chain cannot be modified undetected | Code review + testing |
| **Key Isolation** | Development keys cannot work in production | Penetration testing |
| **Witness Verification** | Witnesses must be cryptographically verified | Code review |
| **Ceremony Security** | Key generation requires multiple witnesses | Code review + testing |
| **Halt Enforcement** | System halts on integrity violations | Testing |

---

## 4. Known Security Findings

We have identified and mitigated the following findings internally. We request the auditor verify these mitigations:

### 4.1 H1 - Environment Variable Poisoning

| Attribute | Details |
|-----------|---------|
| **Risk** | DEV_MODE=true in production allows plaintext key storage |
| **Severity** | Critical |
| **Mitigation** | Secondary validation checks ENVIRONMENT variable |
| **Status** | Mitigated - verify effectiveness |

### 4.2 H2 - Unverified Witnesses in Bootstrap

| Attribute | Details |
|-----------|---------|
| **Risk** | Witnesses accepted without signature verification during bootstrap |
| **Severity** | High |
| **Mitigation** | Explicit opt-in (WITNESS_BOOTSTRAP_ENABLED) + audit logging |
| **Status** | Mitigated - verify controls |

### 4.3 H3 - Key Rotation Overlap

| Attribute | Details |
|-----------|---------|
| **Risk** | Compromised key usable during 30-day transition period |
| **Severity** | High |
| **Mitigation** | Emergency revocation bypasses transition period |
| **Status** | Mitigated - verify revocation |

---

## 5. Deliverables

### 5.1 Required Deliverables

| Deliverable | Description | Format |
|-------------|-------------|--------|
| **Executive Summary** | High-level findings for leadership | PDF |
| **Technical Report** | Detailed findings with evidence | PDF + Markdown |
| **Vulnerability List** | Prioritized list with CVSS scores | Spreadsheet |
| **Remediation Guide** | Specific fix recommendations | Markdown |
| **Retest Report** | Verification of fixed issues | PDF |

### 5.2 Report Requirements

Each finding should include:
- Unique identifier (e.g., ARCH-001)
- Title and description
- Severity (Critical/High/Medium/Low/Informational)
- CVSS v3.1 score (where applicable)
- Affected components and files
- Steps to reproduce
- Evidence (screenshots, logs, code snippets)
- Recommended remediation
- References (CWE, OWASP, etc.)

### 5.3 Severity Definitions

| Severity | Definition | Response Time |
|----------|------------|---------------|
| **Critical** | Immediate compromise of core security properties | Immediate |
| **High** | Significant security impact, exploitable | Before production |
| **Medium** | Moderate impact, requires specific conditions | Before production |
| **Low** | Minor impact, defense in depth | Post-production acceptable |
| **Informational** | Best practice recommendations | Advisory |

---

## 6. Engagement Structure

### 6.1 Proposed Timeline

| Phase | Activities | Duration |
|-------|------------|----------|
| **Kickoff** | Scope review, access setup, Q&A | 1-2 days |
| **Discovery** | Architecture review, threat modeling | 2-3 days |
| **Assessment** | Code review, security testing | 5-7 days |
| **Reporting** | Draft report, findings review | 2-3 days |
| **Remediation** | Fix implementation (by us) | Variable |
| **Retest** | Verify fixes | 1-2 days |

**Total Estimated Duration:** 2-3 weeks (excluding remediation)

### 6.2 Access Requirements

| Access Type | Scope | Duration |
|-------------|-------|----------|
| Source Code | Read-only repository access | Engagement duration |
| Documentation | Full access to docs/ folder | Engagement duration |
| Test Environment | Isolated development instance | Engagement duration |
| Communication | Secure channel (encrypted email/chat) | Engagement + 30 days |

### 6.3 Communication Plan

| Meeting | Frequency | Participants |
|---------|-----------|--------------|
| Kickoff | Once | Full team |
| Daily Standup | Daily | Tech leads |
| Findings Review | As needed | Security + Dev |
| Draft Report Review | Once | Full team |
| Final Presentation | Once | Leadership + Tech |

---

## 7. Testing Authorization

### 7.1 Authorized Activities

The auditor is authorized to:
- Review all source code in the repository
- Execute existing test suites
- Create and execute custom security tests
- Attempt to bypass security controls in test environment
- Analyze cryptographic implementations
- Review configuration and environment handling

### 7.2 Prohibited Activities

The auditor shall NOT:
- Access production systems or data
- Perform denial-of-service testing
- Exfiltrate any data outside secure channels
- Share findings with third parties
- Introduce persistent changes to codebase
- Access systems outside defined scope

### 7.3 Rules of Engagement

- All testing in isolated test environment only
- Notify project team before destructive tests
- Document all testing activities
- Report critical findings immediately (within 24 hours)
- Maintain confidentiality of all findings

---

## 8. Auditor Requirements

### 8.1 Required Qualifications

| Requirement | Details |
|-------------|---------|
| **Cryptography Expertise** | Experience auditing Ed25519, SHA-256, hash chains |
| **Python Security** | Experience with Python security patterns |
| **HSM Experience** | Understanding of HSM architectures |
| **Relevant Certifications** | OSCP, OSCE, GWAPT, or equivalent |
| **Code Review Experience** | Demonstrated secure code review capability |

### 8.2 Preferred Qualifications

| Qualification | Details |
|---------------|---------|
| **AI/ML Security** | Experience with AI system security |
| **Event Sourcing** | Understanding of event-sourced architectures |
| **Blockchain/DLT** | Experience with immutable ledger systems |
| **FastAPI** | Familiarity with FastAPI framework |

### 8.3 References Required

Please provide:
- 2-3 relevant engagement references
- Sample redacted report (demonstrating quality)
- Team CVs/qualifications for assigned auditors

---

## 9. Proposal Requirements

### 9.1 Proposal Contents

Please include in your proposal:

1. **Company Overview**
   - Relevant experience and certifications
   - Team composition for this engagement

2. **Methodology**
   - Approach to code review
   - Testing methodology
   - Tools to be used

3. **Timeline**
   - Proposed schedule
   - Milestones and checkpoints

4. **Pricing**
   - Fixed price or time & materials
   - Breakdown by phase
   - Retest pricing

5. **References**
   - Similar engagements
   - Client contacts (with permission)

### 9.2 Evaluation Criteria

| Criterion | Weight |
|-----------|--------|
| Relevant Experience | 30% |
| Technical Approach | 25% |
| Team Qualifications | 20% |
| Pricing | 15% |
| References | 10% |

---

## 10. Appendices

### Appendix A: Key Files for Review

```
# Critical Priority
src/infrastructure/adapters/security/hsm_factory.py
src/infrastructure/adapters/security/hsm_dev.py
src/infrastructure/adapters/security/hsm_cloud.py
src/application/services/signing_service.py
src/application/services/keeper_signature_service.py
src/application/services/witness_service.py
src/application/services/key_generation_ceremony_service.py
src/domain/events/hash_utils.py
src/domain/models/signable.py
src/api/startup.py

# High Priority
src/infrastructure/adapters/persistence/key_registry.py
src/application/services/merkle_tree_service.py
src/infrastructure/adapters/persistence/witness_pool.py
src/application/services/hash_verification_service.py

# Medium Priority
src/application/services/witness_anomaly_detection_service.py
migrations/*.sql
```

### Appendix B: Constitutional Truths

The system enforces these security-critical properties:

| CT | Name | Security Implication |
|----|------|---------------------|
| CT-11 | Halt Over Degrade | System halts on failures, never continues degraded |
| CT-12 | Witnessing Creates Accountability | Multiple witnesses for constitutional actions |
| CT-13 | Integrity Outranks Availability | Hash mismatch triggers immediate halt |

### Appendix C: Security Patterns

| Pattern | Description |
|---------|-------------|
| **RT-1** | Mode watermark inside signed content (not metadata) |
| **FP-5** | All signing through centralized services |
| **MA-2** | Chain binding - signature covers prev_hash |

### Appendix D: Environment Variables

| Variable | Security Impact |
|----------|-----------------|
| `DEV_MODE` | Critical - controls HSM mode |
| `ENVIRONMENT` | High - production detection |
| `WITNESS_BOOTSTRAP_ENABLED` | High - unverified witness control |
| `ALLOW_VERIFICATION_BYPASS` | Medium - startup bypass |

---

## 11. Contact Information

| Role | Contact Method |
|------|----------------|
| Project Sponsor | [To be provided] |
| Technical Lead | [To be provided] |
| Security Champion | [To be provided] |

**Proposal Submission:**
- Deadline: [To be determined]
- Format: PDF via encrypted email
- Questions: [Contact email]

---

## 12. Confidentiality

This document and all related materials are confidential. By receiving this document, the recipient agrees to:

- Maintain confidentiality of all information
- Use information only for proposal preparation
- Return or destroy materials if not selected
- Not share with third parties without written consent

---

*Document Version: 1.0*
*Classification: Confidential - Prospective Vendors*
*Last Updated: 2026-01-09*
