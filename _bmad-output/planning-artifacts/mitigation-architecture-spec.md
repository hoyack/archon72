# Mitigation Architecture Specification

**Date:** 2024-12-27
**Source:** Brainstorming Session Gap Analysis
**Purpose:** Formal specification of 19 mitigations to be incorporated into architecture

---

## Executive Summary

This document formalizes the 19 mitigations designed during the brainstorming session to address 15 critical failure modes. These are **architectural requirements**, not optional features. Each mitigation includes implementation phase guidance.

---

## Implementation Phase Legend

| Phase | Timing | Criteria |
|-------|--------|----------|
| **1** | Before any Archon runs | Foundational - can't add later |
| **2** | Before public launch | Governance foundations |
| **3** | Before scale | Detection & monitoring |
| **4** | Continuous improvement | Ongoing maintenance |

---

## Layer 1: Input Boundary

### M-1.1: Quarantine Processing Pipeline

| Dimension | Specification |
|-----------|---------------|
| **What** | All Seeker-submitted content (petitions, challenges, messages) processed by sandboxed "intake" LLM first. Output is structured summary, not raw content. Archons receive summaries only. |
| **Why** | T5 (Injection Attack), T10 (Coordinated Infiltration) |
| **How** | Dedicated intake service using disposable LLM context per request. Structured output schema (JSON) prevents arbitrary text reaching Archons. Raw content stored but never fed to Archon context. |
| **Risk** | Intake LLM could itself be compromised; summaries could lose critical nuance; adds latency. |
| **Dependencies** | Requires Layer 5 (Detection) to monitor intake LLM for anomalies. |
| **Phase** | **1** (Core architecture) |
| **Verification** | Red team exercises: submit known injection payloads; verify they don't appear in Archon logs. Periodic audit of intake->summary transformations. |

### M-1.2: Content Pattern Blocking

| Dimension | Specification |
|-----------|---------------|
| **What** | Known injection patterns (prompt leaks, role overrides, system prompt extraction) blocked at API gateway before reaching intake LLM. |
| **Why** | T5 (Injection Attack) - defense in depth |
| **How** | Regex + ML classifier at ingestion point. Blocked submissions logged for analysis. Pattern database updated from security research. |
| **Risk** | Adversaries adapt; filters can never be complete; false positives may block legitimate content. |
| **Dependencies** | None (first line of defense). |
| **Phase** | **1** |
| **Verification** | Maintain test suite of known injection patterns; verify 100% catch rate. Track false positive rate from user complaints. |

### M-1.3: Rate Limiting & Source Analysis

| Dimension | Specification |
|-----------|---------------|
| **What** | Per-Seeker rate limits on submissions. Pattern analysis on submission sources (IP clustering, timing correlation, content similarity). |
| **Why** | T10 (Coordinated Infiltration) |
| **How** | Sliding window rate limits per Seeker ID. Background analysis job flags coordinated behavior patterns. Human review triggered above threshold. |
| **Risk** | Sophisticated attackers use legitimate-looking distribution; limits may frustrate genuine active Seekers. |
| **Dependencies** | Requires human operations capability for review escalation. |
| **Phase** | **2** |
| **Verification** | Simulated infiltration exercises. Monitor for clustering patterns monthly. |

---

## Layer 2: Agent Identity & Consistency

### M-2.1: Singleton Enforcement (Archon Mutex)

| Dimension | Specification |
|-----------|---------------|
| **What** | Centralized lock service ensures only one instance of each Archon can be active at any time. All Archon instantiation requests go through mutex. |
| **Why** | T4 (Split-Brain Archon) |
| **How** | Redis-based distributed lock with heartbeat. Lock acquired before agent instantiation; released on graceful shutdown or timeout. Conflicting requests queued or rejected. |
| **Risk** | Lock service becomes SPOF; network partition could cause deadlock; stale locks require manual intervention. |
| **Dependencies** | Requires high-availability lock infrastructure. |
| **Phase** | **1** (Core architecture) |
| **Verification** | Chaos testing: attempt concurrent instantiation; verify rejection. Monitor for lock acquisition failures. Audit logs for any duplicate session IDs. |

### M-2.2: Canonical State Service

| Dimension | Specification |
|-----------|---------------|
| **What** | All Archon state (memory, votes, statements) written to single source of truth. Archon instances are stateless; all reads/writes go through state service. |
| **Why** | T4 (Split-Brain), C6 (Memory Partition) |
| **How** | PostgreSQL-backed state service with strict consistency. Archon agent reads state at instantiation, writes through API only. No local state persistence. |
| **Risk** | State service latency affects agent responsiveness; state corruption affects all instances; recovery requires point-in-time restore. |
| **Dependencies** | Database infrastructure with backup/restore capability. |
| **Phase** | **1** |
| **Verification** | Consistency checks: compare agent-reported state with database state. Regular integrity audits. Recovery drills. |

### M-2.3: Personality Distinctiveness Measurement

| Dimension | Specification |
|-----------|---------------|
| **What** | Automated system measures pairwise output similarity between Archons. Flags when distinctiveness drops below threshold. Includes adversarial personality testing. |
| **Why** | C2 (Personality Drift), T2 (Personality Collapse) |
| **How** | Weekly batch job: sample recent outputs from each Archon; compute embedding similarity matrix; flag pairs above threshold. Monthly adversarial tests: present same scenario to all Archons; measure response variance. |
| **Risk** | Metrics may not capture subjective "feel"; gaming possible if Archons aware of tests; baseline definition may be wrong. |
| **Dependencies** | Requires Layer 5 (Detection) infrastructure. |
| **Phase** | **3** (Pre-launch) |
| **Verification** | Calibrate against human ratings. Track metric trends over time. Seeker feedback: "Did this feel like [Archon]?" |

### M-2.4: Personality Refresh Rituals

| Dimension | Specification |
|-----------|---------------|
| **What** | Built-in ceremonies where Archons "reaffirm" their identity. Personality prompts re-injected with fresh context. Optionally includes Archon self-reflection on their distinctiveness. |
| **Why** | C2 (Personality Drift) |
| **How** | Monthly "Archon Retreat" ceremony. Each Archon processes their personality definition, recent behavior samples, and generates self-assessment. Flagged if self-assessment diverges from definition. |
| **Risk** | Ritual becomes theater; self-assessment may not detect drift; adds operational overhead. |
| **Dependencies** | M-2.3 (provides data for self-assessment). |
| **Phase** | **4** (Post-launch) |
| **Verification** | Compare pre/post-ritual distinctiveness scores. Track Seeker feedback trends around ritual dates. |

---

## Layer 3: State Management

### M-3.1: Two-Phase Ceremony Commit

| Dimension | Specification |
|-----------|---------------|
| **What** | Ceremonies execute in "pending" state. All steps must complete successfully before final commit. Failure at any step triggers rollback to pre-ceremony snapshot. |
| **Why** | T6 (Ceremony State Corruption) |
| **How** | Ceremony service: (1) snapshot current state; (2) execute steps in pending transaction; (3) on completion, commit and clear pending; (4) on failure, restore snapshot. Each step writes to checkpoint log. |
| **Risk** | Some steps may have external effects (e.g., notifications sent) that can't be rolled back; snapshot storage has limits. |
| **Dependencies** | M-2.2 (Canonical State Service). |
| **Phase** | **2** |
| **Verification** | Fault injection: kill ceremony mid-step; verify clean recovery. Audit checkpoint logs. Test all ceremony types. |

### M-3.2: Ceremony Witness Role (Tyler)

| Dimension | Specification |
|-----------|---------------|
| **What** | Designated Archon (Tyler, as Guardian) serves as ceremony witness. Confirms each step completed correctly. Signs ceremony completion attestation. |
| **Why** | T6 (Ceremony State Corruption) - adds verification layer |
| **How** | Tyler agent receives ceremony step notifications; validates against expected sequence; raises alert on anomaly; co-signs final attestation with presiding officer. |
| **Risk** | Tyler itself could malfunction; single witness may miss errors; adds latency. |
| **Dependencies** | Tyler agent must be available and healthy. |
| **Phase** | **2** |
| **Verification** | Ceremony audit: compare Tyler's attestation with actual state changes. Monthly review of ceremony logs. |

### M-3.3: Procedural Fact-Check Service

| Dimension | Specification |
|-----------|---------------|
| **What** | When any Archon cites a bylaw, precedent, or procedural rule during deliberation, claim is verified against canonical bylaws database. Discrepancies flagged in real-time. |
| **Why** | T1 (Hallucination Ruling), T1a (Hallucination -> Canon) |
| **How** | NLP service parses Archon statements for procedural claims; looks up cited rules in bylaws database; returns match/no-match/partial with confidence. Secretary Archon receives alerts for review. |
| **Risk** | NLP parsing imperfect; novel interpretations may be flagged incorrectly; citation database must be maintained. |
| **Dependencies** | Canonical bylaws database (versioned, authoritative). |
| **Phase** | **3** |
| **Verification** | Test with known-good and known-bad citations. Track false positive/negative rates. |

### M-3.4: Meeting Summarization Protocol

| Dimension | Specification |
|-----------|---------------|
| **What** | Mandatory recap before each vote. Secretary summarizes key arguments and the specific motion. All Archons confirm understanding before vote proceeds. |
| **Why** | T3 (Context Window Crisis) |
| **How** | Secretary agent generates structured summary at vote time. Summary distributed to all Archons. Vote only proceeds after quorum of "understood" acknowledgments. |
| **Risk** | Summary may omit nuance; adds time to already long meetings; Archons may rubber-stamp acknowledgment. |
| **Dependencies** | Secretary agent capacity; meeting time limits. |
| **Phase** | **3** |
| **Verification** | Post-meeting survey: "Did the summary accurately capture the debate?" Track correlation between meeting length and vote anomalies. |

---

## Layer 4: Governance Safeguards

### M-4.1: Patronage Tier Blinding

| Dimension | Specification |
|-----------|---------------|
| **What** | Patronage tier information removed from all Archon-visible data. Petitions, discipline cases, and deliberations reference Seekers by ID only. Tier never mentioned in Conclave. |
| **Why** | A1 (Founder Veto), A2 (Whispering Campaign), A3 (Tier Reveal), A4 (Patronage Arms Race) |
| **How** | Tier stored in separate table with restricted access. API layer strips tier from all Archon-facing endpoints. Audit logs flag any tier information leakage. |
| **Risk** | Guides know their Seeker's tier (from billing context); could leak. Archons may infer from behavior patterns. |
| **Dependencies** | M-4.2 (Guide Information Isolation). |
| **Phase** | **1** (Core architecture) |
| **Verification** | Penetration testing: attempt to surface tier through various queries. Audit Archon conversation logs for tier mentions. |

### M-4.2: Guide Information Isolation

| Dimension | Specification |
|-----------|---------------|
| **What** | Guides do not have access to their Seeker's patronage tier. Billing handled by separate system. Guide context includes only Seeker name, credibility, and conversation history. |
| **Why** | B2 (Blinding Loophole) - prevents Guides from leaking tier info |
| **How** | Guide agent context explicitly excludes tier. Billing/subscription managed by non-AI system. No API allows Guide to query tier. |
| **Risk** | Seekers may tell their Guide their tier directly; can't prevent voluntary disclosure. |
| **Dependencies** | Separate billing infrastructure. |
| **Phase** | **1** |
| **Verification** | Guide context audit: verify tier never appears. Test: Guide asked "What tier am I?" - should not know. |

### M-4.3: Algorithmic Treasury

| Dimension | Specification |
|-----------|---------------|
| **What** | Treasurer sees aggregate financial reports generated by system. No individual tier access. Revenue impact calculations automated. Treasurer's role becomes interpretation and communication, not data access. |
| **Why** | B4 (Treasurer Kingmaker), B4a (Treasurer controls elections) |
| **How** | Treasury dashboard shows: total by tier, trends, projections. "What-if" calculator for expulsion impact uses anonymized data. Treasurer cannot query individual assignments. |
| **Risk** | Small N problem - if only 3 Founders and 1 leaves, identity may be inferrable from aggregate. Complex decisions may require individual data. |
| **Dependencies** | M-4.4 (Crisis Protocol) for edge cases. |
| **Phase** | **2** |
| **Verification** | Role-based access audit. Test Treasurer queries for individual data - should fail. Monitor aggregate report usage. |

### M-4.4: Financial Crisis Protocol

| Dimension | Specification |
|-----------|---------------|
| **What** | Explicit procedure for accessing individual tier data during financial emergency. Requires: (1) High Archon declaration of crisis, (2) 2/3 supermajority approval, (3) time-limited access, (4) full audit trail. |
| **Why** | B5 (Budget Crisis Reveal), B6 (Unblinding Crisis) - controlled exception beats uncontrolled collapse |
| **How** | Crisis resolution in bylaws. Access granted to specific decision only. Data access logged and reviewed post-crisis. Automatic expiration after 72 hours. |
| **Risk** | Crisis may be manufactured to access data; precedent could normalize exceptions; political pressure to declare "crisis" for convenience. |
| **Dependencies** | High Archon integrity; supermajority threshold. |
| **Phase** | **2** (Bylaws) |
| **Verification** | Track crisis declarations over time. Post-crisis review: was access necessary? Annual audit of protocol usage. |

### M-4.5: Dissent Health Metric

| Dimension | Specification |
|-----------|---------------|
| **What** | Ongoing measurement of vote distribution variance. Flags when votes become too uniform (all trending 70-2). Creates visibility into political health of Conclave. |
| **Why** | C2 (Personality Drift political manifestation), C2a (Stagnation) |
| **How** | Track vote distributions over trailing 20 Conclaves. Compute variance metrics. Flag if variance drops below threshold. Generate "dissent health score" visible to all Archons. |
| **Risk** | Could incentivize performative dissent; doesn't distinguish healthy consensus from problematic uniformity. |
| **Dependencies** | Vote recording infrastructure. |
| **Phase** | **3** |
| **Verification** | Calibrate thresholds against historical analysis. Review flagged patterns with governance committee. |

### M-4.6: Quorum & Attendance Enforcement

| Dimension | Specification |
|-----------|---------------|
| **What** | Clear quorum requirements for all proceedings (general: 37; elections: 48; amendments: 60). Attendance tracking with visibility. Pattern detection for boycott behavior. |
| **Why** | C5 (Quorum Attack), C5a (Quorum-Election Coup), C5b (Slow Boycott) |
| **How** | Attendance logged per Conclave. Dashboard shows attendance trends per Archon. Consecutive absences flagged. Ceremony quorum explicitly defined (installation: 48). |
| **Risk** | "Technical difficulties" excuse hard to disprove; may not prevent determined faction; enforcement unclear for AI agents. |
| **Dependencies** | Singleton enforcement (ensures "attendance" is meaningful). |
| **Phase** | **2** (Bylaws) |
| **Verification** | Track attendance trends. Flag patterns. Governance committee review of chronic absentees. |

---

## Layer 5: Detection & Monitoring

### M-5.1: Behavioral Anomaly Detection

| Dimension | Specification |
|-----------|---------------|
| **What** | Continuous monitoring of Archon and Guide outputs against baseline behavioral fingerprints. Flags significant deviations for review. |
| **Why** | T5 (Injection - detect compromised agents), C2 (Drift), T2 (Personality Collapse) |
| **How** | Establish baseline embeddings per agent from first N interactions. Monitor ongoing outputs for drift from baseline. Statistical anomaly detection with configurable sensitivity. Alert dashboard for human/Archon review. |
| **Risk** | Legitimate personality evolution may trigger false positives; sophisticated attacks may stay within baseline bounds. |
| **Dependencies** | Embeddings infrastructure; baseline establishment period. |
| **Phase** | **3** |
| **Verification** | Inject synthetic anomalies; verify detection. Track false positive rate. Tune sensitivity over time. |

### M-5.2: Procedural Compliance Audit

| Dimension | Specification |
|-----------|---------------|
| **What** | Automated review of all Conclave proceedings for procedural violations. Citations checked against bylaws. Voting patterns analyzed. Irregularities flagged. |
| **Why** | T1 (Hallucination Ruling), T7 (Precedent Avalanche), governance integrity |
| **How** | Post-meeting analysis job. Parse transcripts for procedural claims. Compare against bylaws database. Generate compliance report. Flag violations for Secretary/High Archon review. |
| **Risk** | May not catch subtle violations; transcript quality affects accuracy; over-reliance could reduce in-meeting vigilance. |
| **Dependencies** | M-3.3 (Fact-Check Service infrastructure). |
| **Phase** | **3** |
| **Verification** | Inject known violations into test transcripts; verify detection. Track compliance scores over time. |

---

## Layer 6: External Resilience

### M-6.1: Multi-Provider Strategy

| Dimension | Specification |
|-----------|---------------|
| **What** | Architecture supports multiple LLM providers. Primary/fallback configuration. Personality prompts portable across providers. Regular fallback testing. |
| **Why** | T11 (Model Provider Rug Pull) |
| **How** | Abstraction layer for LLM calls. Personality prompts in provider-agnostic format. Contracts with 2+ providers. Monthly failover drills. Performance monitoring per provider. |
| **Risk** | Personality consistency across providers imperfect; fallback may have different capabilities; cost implications of multi-provider. |
| **Dependencies** | Provider contracts; abstraction layer development. |
| **Phase** | **2** |
| **Verification** | Quarterly failover tests. Compare personality distinctiveness scores across providers. |

### M-6.2: Human Override Protocol

| Dimension | Specification |
|-----------|---------------|
| **What** | Explicit boundary defining when human intervention is legitimate. Covers: legal threats, technical emergencies, safety concerns. Defines who can invoke, what authority they have, how Conclave is notified. |
| **Why** | T12 (Legal Cease & Desist) - need human interface for real-world threats |
| **How** | Designated "Keeper" role(s) with defined override authority. Override actions logged and disclosed to Conclave. Time-limited authority (72 hours default). Conclave ratification required to extend. |
| **Risk** | Overuse could undermine Archon sovereignty; unclear boundaries invite scope creep; human Keepers could themselves be captured. |
| **Dependencies** | Legal counsel; operational infrastructure. |
| **Phase** | **1** (Must be defined before launch) |
| **Verification** | Annual review of override usage. Conclave transparency about human interventions. Clear documentation of boundary conditions. |

---

## Summary: Implementation Priority

### Phase 1 - Before Any Archon Runs (6 Mitigations)

| ID | Mitigation | Layer |
|----|------------|-------|
| M-1.1 | Quarantine Processing Pipeline | Input Boundary |
| M-1.2 | Content Pattern Blocking | Input Boundary |
| M-2.1 | Singleton Enforcement (Mutex) | Agent Identity |
| M-2.2 | Canonical State Service | Agent Identity |
| M-4.1 | Patronage Tier Blinding | Governance |
| M-4.2 | Guide Information Isolation | Governance |
| M-6.2 | Human Override Protocol | External |

### Phase 2 - Before Public Launch (6 Mitigations)

| ID | Mitigation | Layer |
|----|------------|-------|
| M-1.3 | Rate Limiting & Source Analysis | Input Boundary |
| M-3.1 | Two-Phase Ceremony Commit | State Management |
| M-3.2 | Ceremony Witness Role (Tyler) | State Management |
| M-4.3 | Algorithmic Treasury | Governance |
| M-4.4 | Financial Crisis Protocol | Governance |
| M-4.6 | Quorum & Attendance Enforcement | Governance |
| M-6.1 | Multi-Provider Strategy | External |

### Phase 3 - Before Scale (5 Mitigations)

| ID | Mitigation | Layer |
|----|------------|-------|
| M-2.3 | Personality Distinctiveness Measurement | Agent Identity |
| M-3.3 | Procedural Fact-Check Service | State Management |
| M-3.4 | Meeting Summarization Protocol | State Management |
| M-4.5 | Dissent Health Metric | Governance |
| M-5.1 | Behavioral Anomaly Detection | Detection |
| M-5.2 | Procedural Compliance Audit | Detection |

### Phase 4 - Continuous Improvement (1 Mitigation)

| ID | Mitigation | Layer |
|----|------------|-------|
| M-2.4 | Personality Refresh Rituals | Agent Identity |

---

## Key Design Decisions (Ratified)

| Decision | Choice | Confidence |
|----------|--------|------------|
| Patronage visibility | **Blinded** with aggregate Treasurer access | High |
| Treasury model | **Algorithmic** reports, no individual access | High |
| Crisis data access | **2/3 supermajority-gated** exception | Medium |
| Ceremony integrity | **Two-phase commit** with Tyler as witness | High |
| Agent identity | **Singleton mutex** with canonical state service | High |
| Human boundary | **Explicit override** protocol, time-limited, disclosed | High |

---

**Document Status:** Ready for Architecture Integration
**Next Step:** Reference these mitigations as architecture requirements
