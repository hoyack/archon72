# Potential Security Audit Firms

**Project:** Archon 72 Conclave Backend
**Date:** 2026-01-09
**Status:** Vendor Research Complete

---

## Executive Summary

Based on our requirements (Python, cryptography, Ed25519, HSM, event sourcing), we have identified 6 potential security audit firms. Each has been evaluated against our specific needs.

**Top Recommendations:**
1. **Trail of Bits** - Best overall fit (Python expertise, cryptography, public audit history)
2. **NCC Group** - Premium cryptography specialists (dedicated crypto practice)
3. **Cure53** - Excellent value, thorough methodology (European option)

---

## Detailed Firm Profiles

### 1. Trail of Bits (Recommended)

| Attribute | Details |
|-----------|---------|
| **Location** | New York, USA |
| **Founded** | 2012 |
| **Specialty** | Application security, cryptography, blockchain, AI/ML |
| **Python Expertise** | **Excellent** - Audited PyPI, developed Python security tools |

**Why Trail of Bits:**
- Performed security audit of [PyPI (Python Package Index)](https://blog.trailofbits.com/2023/11/14/our-audit-of-pypi/) - demonstrates deep Python expertise
- Developed Python security tools: [abi3audit](https://github.com/trailofbits/abi3audit), [Fickling](https://github.com/trailofbits/fickling)
- Extensive cryptographic review experience
- Published audit reports (transparency)
- Experience with event-sourced and distributed systems

**Services Relevant to Us:**
- [Application Security](https://www.trailofbits.com/services/software-assurance/appsec/)
- [Security Engineering](https://www.trailofbits.com/services/security-engineering/)
- Cryptography review
- Threat modeling

**Notable Clients:** Adobe, Microsoft, Stripe, Reddit, Zoom, cURL, KEDA

**Engagement Style:**
- Shared Slack for real-time communication
- Weekly syncs with status reports
- Final presentation with comprehensive report
- Fix review phase after remediation

**Contact:** https://www.trailofbits.com/contact

**Fit Score:** ★★★★★ (5/5)

---

### 2. NCC Group - Cryptography Services

| Attribute | Details |
|-----------|---------|
| **Location** | Global (HQ: Manchester, UK; offices worldwide) |
| **Founded** | 1999 |
| **Specialty** | Cryptography, application security, compliance |
| **Python Expertise** | Good - general application security |

**Why NCC Group:**
- [Dedicated Cryptography Services practice](https://www.nccgroup.com/us/assessment-advisory/cryptography/) - specialized team focused exclusively on crypto
- Audited TLS 1.3 implementations, threshold ECDSA, blockchain platforms
- Experience with HSM and key management systems
- [Code Review services](https://www.nccgroup.com/us/technical-assurance/application-security/code-review/)
- Academic cryptography background

**Notable Crypto Audits:**
- [Cloudflare TLS 1.3](https://blog.cloudflare.com/ncc-groups-cryptography-services-audit-of-tls-1-3/)
- [DFINITY Threshold ECDSA](https://forum.dfinity.org/t/threshold-ecdsa-cryptography-review-by-ncc-group-third-party-security-audit-3/13853)
- [TrueCrypt](https://www.nccgroup.com/research-blog/isec-completes-truecrypt-audit/)
- [Keybase Protocol](https://keybase.io/docs-assets/blog/NCC_Group_Keybase_KB2018_Public_Report_2019-02-27_v1.3.pdf)
- Ontology blockchain

**Services Relevant to Us:**
- Cryptographic design and implementation review
- Key management system assessment
- Protocol analysis
- Source code review

**Contact:** https://www.nccgroup.com/us/contact-us/

**Fit Score:** ★★★★★ (5/5) for cryptography focus

---

### 3. Cure53

| Attribute | Details |
|-----------|---------|
| **Location** | Berlin, Germany |
| **Founded** | ~2009 |
| **Specialty** | Web/mobile security, infrastructure, cryptography |
| **Python Expertise** | Good - general application security |

**Why Cure53:**
- [15+ years of security testing and code audits](https://cure53.de/)
- Known for meticulous, thorough methodology
- Both black-box and white-box testing
- Cryptographic algorithm and implementation assessment
- Excellent documentation and reporting

**Notable Audits:**
- [Tor Project](https://www.torproject.org/static/findoc/code_audits/Cure53_audit_jan_2024.pdf) (34 days, comprehensive)
- [ExpressVPN](https://www.expressvpn.com/blog/kpmg-privacy-policy-cure53-trustedserver-audit/)
- [NordVPN](https://nordvpn.com/blog/cure53-security-assesment/)
- [Obsidian](https://obsidian.md/blog/cure53-security-audit/)
- [RealVNC](https://www.realvnc.com/en/blog/cure53-security-audit-reaffirms-realvnc-strong-security-stance/)
- [Psono Password Manager](https://psono.com/upload/security-audit-2025-cure53.pdf) (12 days)

**Engagement Style:**
- Direct contact with development team during engagement
- Critical bugs often fixed before report submission
- Ongoing communication and knowledge transfer
- Typical engagements: 12-34 days depending on scope

**European Advantage:**
- GDPR-familiar
- EU timezone overlap
- Potential compliance benefits

**Contact:** https://cure53.de/

**Fit Score:** ★★★★☆ (4/5)

---

### 4. Doyensec

| Attribute | Details |
|-----------|---------|
| **Location** | USA / Europe |
| **Founded** | 2014 |
| **Specialty** | Web/mobile application security, source code auditing |
| **Python Expertise** | Good - large codebase experience |

**Why Doyensec:**
- [Expert source code auditing](https://www.doyensec.com/services/web-applications-and-apis.html)
- Experience with large codebases and deep-dives
- Combines source code review with dynamic testing
- Background in big tech companies and startups

**Notable Audits:**
- [Gravitational Teleport](https://blog.doyensec.com/2020/03/02/gravitational-audit.html) - security infrastructure
- [Brave Wallet](https://doyensec.com/resources/Doyensec_BraveWallet_TestingReport_Q32022_AfterRetest.pdf) - crypto wallet
- [Canary Tokens](https://resources.canary.tools/documents/Doyensec_ThinkstCanaryTokensOSS_Report_Q22024_WithRetesting.pdf) - security tooling

**Services Relevant to Us:**
- Source code auditing
- Security architecture review
- Retest after remediation (1-2 days typically)

**Contact:** https://doyensec.com/

**Fit Score:** ★★★★☆ (4/5)

---

### 5. Bishop Fox

| Attribute | Details |
|-----------|---------|
| **Location** | Phoenix, AZ, USA (global) |
| **Founded** | 2005 |
| **Specialty** | Offensive security, penetration testing, code review |
| **Python Expertise** | Good - listed in supported languages |

**Why Bishop Fox:**
- [20+ years of offensive security expertise](https://bishopfox.com/)
- [Secure Code Review](https://bishopfox.com/services/penetration-testing-services/secure-code-review) with Python support
- [Architecture Security Assessment](https://bishopfox.com/services/penetration-testing-services/architecture-security-assessment)
- OWASP alignment
- Compliance support (SOC 2, PCI DSS)

**Services Relevant to Us:**
- Secure code review (3 depth levels: Baseline, Targeted, In-depth)
- Cryptographic component review (13-point methodology)
- Architecture and design review
- Threat modeling

**Engagement Options:**
- **Baseline:** Static analysis + expert validation
- **Targeted:** + Manual code review
- **In-depth:** + Threat modeling

**Contact:** https://bishopfox.com/contact

**Fit Score:** ★★★☆☆ (3/5) - Less crypto specialization

---

### 6. Zellic

| Attribute | Details |
|-----------|---------|
| **Location** | USA |
| **Founded** | 2020 |
| **Specialty** | Blockchain, cryptography, zero-knowledge proofs |
| **Python Expertise** | Moderate - blockchain focus |

**Why Zellic:**
- Founded by top CTF competition winners
- [Cryptographic audits](https://www.zellic.io/) for ZKPs, MPC
- High-assurance security solutions
- Cutting-edge cryptography expertise

**Services Relevant to Us:**
- Cryptographic implementation review
- Protocol analysis
- Zero-knowledge system audits

**Note:** More blockchain/Web3 focused, but strong crypto fundamentals

**Contact:** https://www.zellic.io/

**Fit Score:** ★★★☆☆ (3/5) - Blockchain-focused

---

## Comparison Matrix

| Firm | Python | Crypto | HSM/Keys | Code Review | Pricing | Overall |
|------|--------|--------|----------|-------------|---------|---------|
| **Trail of Bits** | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★★★ | $$$$ | **Best Fit** |
| **NCC Group** | ★★★☆☆ | ★★★★★ | ★★★★★ | ★★★★☆ | $$$$ | **Crypto Focus** |
| **Cure53** | ★★★☆☆ | ★★★★☆ | ★★★☆☆ | ★★★★★ | $$$ | **Best Value** |
| **Doyensec** | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★★★ | $$$ | Good |
| **Bishop Fox** | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | ★★★★☆ | $$$$ | Good |
| **Zellic** | ★★☆☆☆ | ★★★★★ | ★★★☆☆ | ★★★☆☆ | $$$$ | Specialized |

**Pricing Legend:** $ = Budget, $$ = Moderate, $$$ = Premium, $$$$ = Enterprise

---

## Recommended Approach

### Option A: Single Comprehensive Audit
**Recommended Firm:** Trail of Bits

**Rationale:**
- Best Python expertise (PyPI audit, Python tools)
- Strong cryptography practice
- Experience with similar systems
- Published audit methodology

**Estimated Scope:** 2-3 weeks

---

### Option B: Split Audit (Specialized)
**Cryptography Focus:** NCC Group Cryptography Services
**Application Security:** Cure53 or Doyensec

**Rationale:**
- NCC Group's dedicated crypto team for HSM, signing, key management
- Cure53/Doyensec for application-level code review
- Multiple perspectives on security

**Estimated Scope:** 2 weeks each (parallel or sequential)

---

### Option C: Budget-Conscious
**Recommended Firm:** Cure53

**Rationale:**
- Excellent reputation and methodology
- Competitive European pricing
- Strong documentation
- Good crypto capabilities

**Estimated Scope:** 2-3 weeks

---

## Next Steps

1. **Select approach** (A, B, or C)
2. **Contact firms** - Request introductory calls
3. **Share scope document** - `docs/security/audit-engagement-scope.md`
4. **Request proposals** - Compare pricing and approach
5. **Select vendor(s)** - Based on evaluation criteria
6. **Schedule engagement** - Coordinate with development schedule

---

## Contact Templates

### Initial Outreach Email

```
Subject: Security Audit Inquiry - Constitutional AI Governance System

Dear [Firm Name] Team,

We are seeking an external security audit for Archon 72, a constitutional
AI governance system built with Python/FastAPI. The system implements
cryptographic integrity guarantees including:

- Ed25519 signing with HSM abstraction
- Hash chain integrity (SHA-256)
- Multi-witness key generation ceremonies
- Human oversight ("Keeper") controls

Key audit areas:
- HSM integration and key management
- Cryptographic signing services
- Hash chain implementation
- Environment security controls

Codebase: ~50,000 lines Python, 7,500+ tests
Timeline: Seeking to begin within [X weeks]

Would you be available for an introductory call to discuss scope and
approach? I can share our detailed scope document upon interest.

Best regards,
[Name]
```

---

## Sources

- [Trail of Bits - Software Assurance](https://www.trailofbits.com/services/software-assurance/)
- [Trail of Bits - PyPI Audit](https://blog.trailofbits.com/2023/11/14/our-audit-of-pypi/)
- [NCC Group - Cryptography Services](https://www.nccgroup.com/us/assessment-advisory/cryptography/)
- [NCC Group - Code Review](https://www.nccgroup.com/us/technical-assurance/application-security/code-review/)
- [Cure53 - Security Assessments](https://cure53.de/)
- [Doyensec - Web and Mobile Security](https://doyensec.com/)
- [Bishop Fox - Secure Code Review](https://bishopfox.com/services/penetration-testing-services/secure-code-review)
- [Zellic - Blockchain Security](https://www.zellic.io/)
- [Astra - Top Cybersecurity Audit Companies](https://www.getastra.com/blog/security-audit/cyber-security-audit-companies/)

---

*Document Version: 1.0*
*Last Updated: 2026-01-09*
