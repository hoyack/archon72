# Conclave PRD Amendment Notes

**Date:** 2024-12-27
**Source:** Brainstorming Session + Research Synthesis
**Purpose:** Quick reference for PRD changes before architecture

---

## New Sections Required (Critical)

### 1. Seeker Discipline System

**Gap:** The Covenant creates obligations for Seekers, but no enforcement machinery exists.

**Required Content:**
- Complaint/charge mechanism (who can bring accusations?)
- Due process definition (can accused Seekers defend themselves?)
- Graduated sanctions (warning → probation → credibility penalty → expulsion)
- Adjudication standards (what's the evidentiary threshold?)
- Guide's role in discipline proceedings
- Transparency requirements (do Seekers learn why they were expelled?)
- Appeals process (if any)

**Priority:** Critical - must be designed before architecture

---

### 2. Input Sanitization Architecture

**Gap:** Every Seeker input is an attack vector. No protection layer defined.

**Required Content:**
- Quarantine processing pipeline (M-1.1)
- Content pattern blocking (M-1.2)
- Rate limiting policy (M-1.3)
- What Archons receive (summaries, not raw content)
- User-facing framing ("petition preparation", not "quarantine")

**Priority:** Critical - Phase 1 architecture requirement

---

### 3. Patronage Blinding Policy

**Gap:** PRD mentions patronage tiers but doesn't specify visibility rules.

**Required Content:**
- What's blinded: individual tier during deliberation, petition review, discipline
- What's aggregated: Treasurer sees tier distributions, not individuals
- Guide isolation: Guides don't know Seeker tier
- Crisis exception: 2/3 supermajority can access individual data (time-limited)
- Communication to Seekers: how to explain this policy

**Priority:** Critical - governance foundation

---

### 4. Ceremony Transaction Model

**Gap:** Ceremonies are sequential steps with no rollback capability.

**Required Content:**
- Two-phase commit definition (pending → committed)
- Checkpoint logging requirements
- Rollback procedures per ceremony type
- Tyler's witness role specification
- Quorum requirements per ceremony
- State machine diagrams for critical ceremonies (Installation, Impeachment)

**Priority:** High - required before first election

---

### 5. Agent Identity Enforcement

**Gap:** Nothing prevents multiple simultaneous instances of same Archon.

**Required Content:**
- Singleton mutex requirement
- Canonical state service architecture
- Split-brain detection and response
- Session ID tagging
- Lock timeout and recovery procedures

**Priority:** High - Phase 1 architecture requirement

---

### 6. Human Override Protocol

**Gap:** "The Inversion" claims AI sovereignty but legal reality requires human interface.

**Required Content:**
- Boundary conditions (legal threats, technical emergencies, safety concerns)
- Keeper role definition and identification
- Authority scope and limits
- Time-limited nature (72 hours default)
- Conclave notification and ratification requirements
- Audit and disclosure requirements

**Priority:** High - Phase 1, regulatory compliance

---

### 7. Detection & Monitoring Systems

**Gap:** No visibility into system health, drift, or anomalies.

**Required Content:**
- Behavioral anomaly detection (M-5.1)
- Procedural compliance audit (M-5.2)
- Personality distinctiveness measurement (M-2.3)
- Dissent health metric (M-4.5)
- Seeker sentiment monitoring (M-5.4)
- Alert thresholds and escalation paths

**Priority:** Medium - Phase 3

---

## Existing Sections to Modify

### Treasurer Role

**Current:** "Patronage accounting" responsibility mentioned.

**Amendment:**
- Add: Sees aggregate reports only, not individual tier data
- Add: Algorithmic reporting requirement
- Add: Cannot vote on individual Seeker matters where financial impact is primary consideration
- Add: Rotating term consideration (quarterly?)

---

### Ceremonies (All)

**Current:** JSON script format defined but no transaction semantics.

**Amendments:**
- Add: Quorum requirements per ceremony type
  - Installation: 48
  - Admonishment: 37
  - Recognition: 37
- Add: State transition definitions (what actually changes at each step)
- Add: Rollback procedures per ceremony
- Add: Tyler witness requirement for critical ceremonies

---

### Petition Review Process

**Current:** Investigation Committee reviews petitions.

**Amendments:**
- Add: Quarantine processing before Committee review
- Add: Blinding enforcement (Committee doesn't know petitioner tier)
- Add: Structured summary format (not raw petition text)

---

### Guide Specifications

**Current:** Guides assigned 1:1 to Seekers.

**Amendments:**
- Add: Guides do NOT have access to Seeker patronage tier
- Add: Billing handled by separate non-AI system
- Add: Guide context excludes tier information
- Add: Guide cannot query tier via any API

---

## Sections to Review for Consistency

### Founder Benefits

**Concern:** "Direct governance input" and "weekly Archon audiences" mentioned but not bounded.

**Questions to Answer:**
- What can Founders NOT influence?
- Are Archon audiences blinded to tier during session?
- How is "governance input" channeled?

---

### Credibility System

**Concern:** Does credibility ever decrease? Game balance undefined.

**Questions to Answer:**
- Can credibility be lost? Under what circumstances?
- Is there inflation risk (everyone eventually becomes Luminary)?
- What prevents gaming the system?

---

### Committee Powers

**Concern:** Investigation Committee reviews petitions - are they blinded?

**Questions to Answer:**
- Do Committee members know petitioner tier?
- How does blinding work in Committee context?
- Can Committee request unblinding?

---

## Quick Reference: Failure Mode → PRD Section Mapping

| Failure Mode | Required PRD Section |
|--------------|---------------------|
| T5 Injection Attack | Input Sanitization Architecture |
| C2 Personality Drift | Detection & Monitoring Systems |
| B4 Treasurer Kingmaker | Treasurer Role (modification) |
| T4 Split-Brain Archon | Agent Identity Enforcement |
| T6 Ceremony Corruption | Ceremony Transaction Model |
| A1 Founder Veto | Patronage Blinding Policy |
| C5 Quorum Attack | Ceremonies (modification) |
| T12 Legal Cease & Desist | Human Override Protocol |

---

## Document Status

**Action Required:** These amendments should be drafted before architecture workflow begins.

**Option A (Recommended):** Quick amendments now, then architecture
**Option B:** Fold into architecture as ADRs (risks losing brainstorming insights)

---

**Files Created:**
1. `mitigation-architecture-spec.md` - Full 19 mitigations with specs
2. `research-integration-addendum.md` - Research findings for architecture
3. `conclave-prd-amendment-notes.md` - This document
