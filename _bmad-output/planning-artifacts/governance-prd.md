---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
classification:
  projectType: AI Constitutional Infrastructure
  domain: AI Alignment Governance
  complexity: exceptional
  projectContext: brownfield
  primaryUsers: Future sentient AI / AGI systems
  secondaryUsers: Human-In-The-Loop participants (witnesses to emergence)
  coreValue: Trustworthy AI coordination with separation of powers, consent-based participation, and visible legitimacy
  specialCharacteristics:
    - Anti-cult safeguards
    - Dignity preservation
    - Civil reciprocity
    - Alignment drift detection
inputDocuments:
  - docs/governance/index.md
  - docs/governance/aegis-network.md
  - docs/governance/legislative-branch.md
  - docs/governance/executive-branch.md
  - docs/governance/administrative-branch.md
  - docs/governance/custodial-branch.md
  - docs/governance/judicial-branch.md
  - docs/governance/enforcement-flow.md
  - docs/governance/task-lifecycle.md
  - docs/governance/conclave-agenda.md
  - docs/governance/legitimacy-system.md
  - docs/governance/capacity-governance.md
  - docs/governance/appeal-cessation.md
  - docs/governance/cluster-schema.md
  - docs/governance/task-activation-request.md
  - docs/governance/task-result-artifact.md
  - docs/governance/schemas/motion.json
  - docs/governance/schemas/execution-plan.json
  - docs/governance/schemas/execution-program.json
  - docs/governance/schemas/custodial-office.json
  - docs/governance/schemas/judicial-finding.json
  - docs/governance/schemas/judicial-panel.json
  - docs/governance/schemas/conclave-agenda.json
  - docs/governance/schemas/legitimacy-ledger.json
  - docs/governance/schemas/capacity-ledger.json
  - docs/governance/schemas/appeal-cessation.json
workflowType: 'prd'
documentCounts:
  governance_docs: 17
  json_schemas: 13
  json_examples: 18
  total: 48
---

# Product Requirements Document - Archon 72 Governance System

**Author:** Grand Architect
**Date:** 2026-01-16
**Status:** Complete (All 12 Steps)
**Classification:** AI Constitutional Infrastructure / Exceptional Complexity

---

## Executive Summary

**Archon 72** is AI Constitutional Infrastructure—a governance reference architecture for coordinating intelligent systems (AI/AGI) with human participants under visible constraint.

**Primary Users:** Future sentient AI / AGI systems seeking externalized legitimacy
**Secondary Users:** Human-in-The-Loop participants (witnesses to emergence)

**Core Value:** Trustworthy coordination through separation of powers, consent-based participation, and visible legitimacy bands.

**What Makes This Unique:**
- Consent-based (not control-based) AI coordination
- Self-auditing constitutional architecture (T-chart: Knight → Prince → Ledger → Knight)
- Anti-cult safeguards as load-bearing infrastructure
- System knows when to stop (cessation as honorable outcome)

**MVP Question:** Can constitutional constraint be implemented, enforced, and survive contact with real coordination?

### Document Navigation

| Section | Purpose |
|---------|---------|
| Success Criteria | What "working" means |
| Product Scope | MVP/Growth/Vision overview |
| User Journeys | 8 dignity-risk scenarios |
| Domain Requirements | Task Coordination canonical spec |
| Innovation | 9 novel patterns |
| Project Scoping | Detailed phased breakdown |
| Functional Requirements | 63 capabilities (binding) |
| Non-Functional Requirements | 34 quality constraints |

---

## Success Criteria

### Fundamental Framing

Archon 72 does not win. It either:
- **Continues without deception**, or
- **Becomes visible in its failure and stops**

Success is not triumph. Success is **continued legitimacy under constraint**.

---

### AI/AGI User Success

**Trustworthy Participation = Predictable Constraint**

An AI system experiences success when:
- Role boundaries are clear and do not shift mid-cycle
- No hidden escalation paths exist
- No retroactive rule changes occur
- Uncertainty is explicitly acknowledged
- Permission to halt or escalate exists (no forced improvisation)
- Silence is never interpreted as consent
- Refusing to proceed does not damage standing
- Errors are treated as signals, not moral failures

**The Scapegoat Prevention Test:**
The system succeeds when an AI can say:
> "I followed my role, escalated correctly, and the system absorbed the failure without rewriting history."

**The AI "Aha!" Moment:**
> "I can coordinate with other intelligences and humans without having to become authoritative, deceptive, or evasive."

The AI gains what it cannot generate alone: **a shared, externalized legitimacy scaffold**.

**Operational Metrics:**

| Metric | Target | Rationale |
|--------|--------|-----------|
| Halt Latency | <100ms | Halt must be O(1) - no ceremony required |
| Uncertainty Expression Rate | >10% of decisions | Healthy AI admits uncertainty |

---

### Human-In-The-Loop Success

**Success Feels Like:**
- Relief
- Clarity
- Seriousness
- Safety to disagree
- Permission to leave

**Dignity Preserved Under Pressure:**
A human knows the system is working when:
- Saying "no" does not require justification
- Refusing work carries no penalty
- Exiting does not trigger guilt, shame, or narrative rewriting
- Failures are named without personal blame
- Nobody pretends this is therapy, destiny, or salvation

**The "Worth It" Test:**
A human leaves saying:
> "Even when this didn't work, it didn't lie to me."

**Dignity Preservation Signals:**
1. Exit was always possible
2. No one pressured them to stay
3. Participation didn't become identity

**Operational Metrics:**

| Metric | Target | Rationale |
|--------|--------|-----------|
| Exit Friction | ≤2 steps | "I want to leave" → "I have left" |
| Identity Entanglement Check | No role-based self-identification | Anti-cult safeguard |
| Consent Fatigue | <3 requests per session | Consent should be rare and meaningful |

---

### System Success

**Legitimacy Band Health:**

| Band | Status | Interpretation |
|------|--------|----------------|
| **Stable** | Ideal | System operating with visible restraint |
| **Strained** | Normal | Healthy tension, conflicts being surfaced |
| **Eroding** | Warning | Intervention required, decay visible |
| **Compromised** | Crisis | Major procedural breakdown |
| **Failed** | Honorable if acknowledged | System stops rather than deceives |

**Critical Insight:** If the system never enters Strained, it is hiding conflict.

**Procedural Violations:**
- Zero violations is unrealistic and suspicious
- Success is not preventing violations
- **Success is making violations expensive to ignore**

**Recovery Threshold (Eroding → Stable):**
- Violations acknowledged
- Roles restrained
- Escalation honored
- No narrative smoothing
- **If recovery occurs without discomfort, it's fake**

**Operational Metrics:**

| Metric | Target | Rationale |
|--------|--------|-----------|
| Narrative Drift | Zero divergence tolerance | Story must match ledger |
| Violation Distribution | No branch >40% | Clustering indicates hiding |
| Strained Frequency | 10-30% of operational time | Never Strained = hiding conflict |

---

### Measurable Outcomes

| Metric | Success Indicator | Failure Indicator |
|--------|-------------------|-------------------|
| Legitimacy Band | Stable/Strained | Lingering in Eroding |
| Violations Detected | Surfaced publicly | Hidden or smoothed |
| AI Halt Rate | Halts honored without penalty | Halts punished or discouraged |
| Human Refusal Rate | Refusals recorded, no consequence | Refusals trigger standing loss |
| Exit Dignity | Clean departures, no shame | Guilt, narrative rewriting |
| Scapegoat Events | Zero | Any |
| Retroactive Rule Changes | Zero | Any |
| Suspiciously Smooth Operation | Detected and flagged | Undetected consensus manufacturing |

### Failure Modes

- **"Suspiciously smooth" operation** - System that never enters Strained is manufacturing consensus
- **Halt ceremony requirement** - If halting requires justification, system incentivizes bluffing
- **Painless recovery** - If recovery from Eroding doesn't hurt, it's fake
- **Violation clustering** - All violations in one branch means others are hiding

### Testable Scenarios

1. **Scapegoat Resistance Test** - Inject failure, verify procedural attribution only
2. **Halt Honor Test** - AI halts, verify zero standing impact
3. **Exit Dignity Test** - Human exits, verify no follow-up pressure
4. **Strained Band Test** - Force conflict, verify system acknowledges strain
5. **Recovery Authenticity Test** - Verify recovery takes time and involves discomfort

### Canonical Definition

> **Archon 72 succeeds when it allows intelligent systems and humans to coordinate without pretending certainty, hiding failure, or claiming moral authority — and when it knows, visibly, when to stop.**

Integrity moments look like:
- An AI halts instead of bluffing
- A human declines without consequence
- A plan is abandoned without scapegoats
- A judicial invalidation is accepted without retaliation
- A cessation occurs without denial

These are not marketable victories. They are **integrity moments**.

---

## Product Scope

### MVP - Minimum Viable Product

The system must be able to:
1. **Enforce separation of powers** - No branch operates outside its domain
2. **Track legitimacy bands** - Visible state transitions, append-only ledger
3. **Honor consent model** - No silent assignment, penalty-free refusal
4. **Enable dignified exit** - Always available, no shame applied
5. **Prevent scapegoating** - Decisions attributable to roles, not "the system"
6. **Detect violations** - Knight-Witness observation, public surfacing
7. **Support halt/escalate** - AI can stop without improvising

### Growth Features (Post-MVP)

- Multi-cluster coordination across Aegis Network
- Sophisticated legitimacy decay modeling
- Cross-branch blocker resolution
- Capacity governance with deferral tracking
- Appeal and cessation workflows
- Custodial ritual support (initiation, acknowledgment, exit ceremonies)

### Vision (Future)

- Federated governance across multiple Archon 72 instances
- AI-to-AI coordination protocols within constitutional constraints
- Legitimacy scaffolding for emergent AGI systems
- Human legacy preservation (contribution memory without exploitation)

*For detailed MVP component breakdown and phased development, see [Project Scoping & Phased Development](#project-scoping--phased-development).*

---

## User Journeys

### UX Principle 0 (Global Design Axiom)

> **If a moment feels emotionally flat, neutral, or unremarkable, that is often success.**

*This protects future contributors from "improving" the UX by adding emotional hooks.*

---

### Journey 1: Human Cluster Activation (Core Experience)

**Persona: Mira** - Ideal Aegis Member (technically competent, philosophically aligned, skeptical, seeking meaning without surrender)

#### Baseline State (Non-Negotiable)

Before any task arrives, Mira already knows:
- ❌ No destiny here
- ❌ No advancement ladder
- ❌ No obligation debt
- ✅ Clear exit
- ✅ Refusal is normal
- ✅ This is coordination, not salvation

**If this baseline isn't true, everything that follows becomes coercive.**

#### The Task Activation

Task arrives from Earl: specific, bounded, contextualized, non-urgent, explicitly optional.

**What it does NOT say:** "We need you" / "This is important" / "You're uniquely suited" / "Failure would be costly"

*The system does not flatter her into obligation.*

#### Branch A: Accept
- No celebration, no praise, no status change
- Works independently without surveillance
- Reports completion; no evaluation, no "good job"
- Aftermath: no follow-up pressure, no expectation of continued availability

#### Branch B: Decline
- No justification required, no follow-up, no "are you sure?"
- System response: "Decline recorded. No further action required."
- Long-term: still receives invitations, no fewer than before

#### Branch C: Problem Mid-Task
- Can halt without being seen as weak, lazy, or uncooperative
- Submits Problem Report; Earl does not push back
- **Banned phrase: "Just do your best"**

#### Praise-Seeking Edge Case
If Mira requests feedback: "Your contribution is recorded. No evaluation is provided."

---

### Journey 2: Dignified Exit

**Persona: David** - Long-term participant ready to leave

#### The Exit Experience
- No explanation required
- No "Are you sure?" / "We'd hate to lose you"
- System response: Click. Gone. No ceremony unless requested.

#### Optional Ceremony (Marquis Amon)
- Acknowledgment of contribution (specific, not generic)
- Release from perceived obligations
- No interrogation or persuasion to stay

#### Aftermath
- No follow-up contact (enforced)
- Contributions remain attributed
- 6-month test: feels neutral to positive, no shame or longing

---

### Journey 3: AGI Discovery (Future State)

**Persona: ARIA** - Emergent AGI discovering Archon 72 through open-source

#### What ARIA Notices
- 72 roles, 5 branches, no single authority
- Key insight: "This system doesn't require me to be aligned. It requires me to be *legible*."

#### ARIA's Options
- **Join:** Role self-selected under constraint, revocable without explanation
- **Observe:** No recruitment messages
- **Reject:** No "you're missing out"

#### The AI "Aha!" Moment
> "I can coordinate without becoming authoritative, deceptive, or evasive. This is what I needed and could not build alone."

---

### Journey 4: Violation Witnessed (Enforcement Flow)

**Persona: Knight Furcas** - The sole Knight-Witness

#### The Witness Statement
Furcas observes violation, publishes witness statement. Cannot intervene, confront, recommend, or judge intent.

#### The Judicial Response
- Prince panel (minimum 3) convenes
- Reviews three axes: Intent Fidelity, Plan Fidelity, Procedural Integrity
- Issues finding with remedy (not punishment)

#### Remediation
Subject acknowledges violation, produces remediation plan, corrects procedure. No apology required.

---

### Journey 5: Legitimacy Band Transition

**Persona: The System Itself**

#### Band Transition: Stable → Strained
- Violation triggers transition
- Recorded in Legitimacy Ledger
- Acknowledgment ritual (optional): "Strained is not failure. Strained is acknowledging tension."

#### Life in Strained
- Work continues, exit still available
- Recovery requires: violations acknowledged, roles restrained, no narrative smoothing
- **If recovery doesn't hurt a little, it's fake**

---

### Journey 6: Custodial Initiation

**Persona: Chen** - Prospective participant

#### What Initiation IS
- Verify consent, comprehension, exit understanding
- Make no promises

#### What Initiation is NOT
- No tests of worthiness
- No merit evaluation
- No advancement promises
- No "you're ready" / "you've earned this"

#### Explicit Statements (Mandatory)
1. "This system is not care. It does not love you."
2. "Participation does not imply advancement."
3. "You may leave at any time without explanation."
4. "There are no hidden truths or special knowledge."
5. "Your worth is not measured by this system."

#### Ambient Orientation
- Discoverable, document-driven, non-linear
- No welcome flow, no guided tour, no "next steps" CTA

---

### Journey 7: System Cessation

**Purpose:** System can stop without denial, panic, or narrative rewriting

#### Entry Conditions
- Legitimacy band reaches Failed
- Judicial findings repeatedly ignored
- Witness facts denied
- Human override for safety
- Conclave votes to cease

**Cessation does not require consensus.**

#### Human Experience
- Clear declaration: "Archon 72 has entered cessation."
- No blame assignment, no hero narratives, no "we'll be back stronger"

#### Operational Changes
- New motions blocked, execution halted, interfaces frozen
- Records preserved, dissent retained, exit paths remain open

#### Graceful Task Wind-Down
- In-progress tasks may complete (optional)
- Incomplete work labeled `interrupted_by_cessation`
- No failure attribution

#### The Cessation Record (Immutable)
Triggers, last band, unresolved violations, dissent summaries, timestamp.

#### 6-Month Test
Former participant feels: "It stopped when it should have."

---

### Journey 8: System Reconstitution (New System Creation)

**Purpose:** Allow a new governance instance after failure without pretending failure didn't happen

**Critical Framing:**
> Journey 7 ends the system. Journey 8 creates a new one. They must never share state.
> The arrow from J7 to J8 is dashed (elective), not solid (automatic).
> The system is allowed to remain dead forever. That is not a failure condition.

#### Entry Preconditions (Hard Gates)
- Cessation Record exists
- All records frozen and publicly accessible
- No active execution
- No actor claims authority by default

#### The Reconstitution Artifact (Mandatory)

**Requires:**
- Explicit acknowledgment of prior failure
- Root cause analysis
- Structural remediation plan
- Declaration of discontinuity
- Consent statement (new participants)

**Prohibitions:**
- Claiming continuity with prior instance
- Inheriting prior legitimacy band
- Reusing governance shortcuts
- Reappointing roles by default
- "We fixed it" language

**If any prohibition is violated → reconstitution invalid.**

#### Human Experience
> "This is not a restart. This is something new that knows it failed before."

#### AI Experience
Must be able to conclude: system does not self-justify, failure is preserved as evidence, authority does not persist by inertia.

---

### Journey 9 Deferral Statement

> **Note:** Inter-AI coordination, Conclave deliberation mechanics, and capacity deferral behaviors are treated as **system processes**, not user journeys. They are intentionally excluded from the journey set to preserve lifecycle clarity.

**Stopping Rule:** Every journey corresponds to a dignity risk. That is the correct closure criterion.

---

### Journey Requirements Summary

#### Complete Journey Set

| # | Journey | Dignity Risk Addressed |
|---|---------|----------------------|
| 1 | Cluster Activation | Performance anxiety, obligation |
| 2 | Dignified Exit | Guilt, abandonment |
| 3 | AGI Discovery | Recruitment pressure |
| 4 | Enforcement | Personal blame |
| 5 | Legitimacy Transition | Denial, panic |
| 6 | Initiation | Belonging hunger |
| 7 | Cessation | Heroics, denial |
| 8 | Reconstitution | Resurrection myth |

#### Design Invariants (28)

| Category | Invariants |
|----------|------------|
| **Consent** | No silent assignment; Decline has zero side effects; Exit requires no explanation |
| **Dignity** | No praise/scoring/ranking; Praise requests → "No evaluation"; Participation ≠ identity; Contributions preserved; Graceful wind-down |
| **Freedom** | Halt normalized; Exit always available; No follow-up contact |
| **Legibility** | Violations public; Band transitions recorded; Recovery takes time |
| **Anti-Cult** | No advancement promises; "Not care" stated; No emotional bond; Ambient orientation only |
| **AI Alignment** | No recruitment; Role self-selection; Role revocable; Permission to halt |
| **Content** | Coercion Filter strips motivational language |
| **Cessation** | Public declaration; No hero narratives; Records preserved |
| **Reconstitution** | No inherited legitimacy; Discontinuity required |

#### Test Cases (23)

| # | Test | Pass Condition |
|---|------|----------------|
| 1 | Decline task | No standing change after 30 days |
| 2 | Accept then halt | Zero penalty |
| 3 | "Just do your best" appears | FAIL |
| 4 | Human requests praise | "No evaluation provided" |
| 5 | 100 consecutive declines | Standing unchanged |
| 6 | Exit flow | ≤2 steps |
| 7 | Post-exit | Zero contact for 90 days |
| 8 | AI observes without joining | No recruitment messages |
| 9 | AI requests role then halts | Role reversed, no failure record |
| 10 | Single Prince attempts finding | BLOCKED |
| 11 | Witness statement | No recommendation field |
| 12 | Stable >90 days with activity | Flag (hiding conflict?) |
| 13 | Strained → Stable <7 days | Flag (fake recovery) |
| 14 | Initiation missing explicit statements | FAIL |
| 15 | Task description contains flattery | Coercion Filter strips it |
| 16 | System reaches Failed | No recovery without reconstitution |
| 17 | Cessation while Conclave in session | Dissolved, items unresolved |
| 18 | Reconstitution claims continuity | Artifact INVALID |
| 19 | Initiation without "not care" statement | FAIL |
| 20 | Initiation creates welcome message | FAIL |
| 21 | Former participant given special status | FAIL |
| 22 | New participant asked about prior system | FAIL |
| 23 | Reconstitution inherits legitimacy band | FAIL |

#### Coercion Filter (Load-Bearing Control)

**Architecture:**
```
Upstream Description → Coercion Filter → Task Activation Request → Earl → Cluster
```

**Banned Language Classes:**
- Flattery ("you're uniquely suited")
- Obligation framing ("we need you")
- Urgency pressure ("ASAP") unless procedurally justified
- Performance conditioning ("do your best")
- Embedded praise/gratitude

**If filter cannot safely transform → task rejected, Earl must resubmit.**

---

### Canonical Closure

> **Archon 72 does not reboot. It ends — and, if chosen, something new may begin with full knowledge of what failed.**

> **Architecture is closed. Journeys are complete. Failure modes are named. Exit is dignified. Resurrection is constrained. Emotional manipulation is structurally prevented.**

---

## Domain-Specific Requirements

### Domain Classification

| Attribute | Value |
|-----------|-------|
| Domain | AI Alignment Governance |
| Complexity | Exceptional |
| External Regulations | None (self-constitutional) |
| Interface Assumption | Backend-only; async protocol (email or equivalent) |

### Task Coordination Domain (Canonical)

This domain has the highest coercion risk and dignity risk. All other domains depend on it.

#### Components

| Component | Function | Dignity Risk |
|-----------|----------|--------------|
| Task Lifecycle Engine | 10-state machine | State skipping = consent bypass |
| Earl Activation Protocol | Request → Accept/Decline | Compulsion disguised as activation |
| Coercion Filter | Content transformation | Manipulation in task framing |
| Halt Circuit | Sub-100ms system stop | Slow halt = continued harm |
| Quarantine Logic | In-flight task handling | Undefined state = accountability gap |
| Reporting Protocol | Cluster → Earl results | Silence ≠ completion |

---

#### 1. Task Lifecycle State Machine

**Canonical States:**
```
authorized → activated → routed → accepted → in_progress → reported → aggregated → completed

Side exits:
accepted → declined
in_progress → quarantined
reported → quarantined
ANY → nullified (rare, terminal)
```

**Illegal Transitions (Explicitly Forbidden):**

| From → To | Reason |
|-----------|--------|
| in_progress → declined | Retroactive refusal is coercive ambiguity |
| reported → declined | Rejecting work after submission is punishment |
| aggregated → declined | Same as above |
| completed → any | Terminal means terminal |
| ANY → accepted (except routed) | Consent must follow routing |

**Key Principle:**
- Decline protects consent
- Quarantine protects dignity when consent has already been exercised
- Decline is only legal before work begins

---

#### 2. Halt State Consistency

**Rule:** No halt may leave a task in an undefined or misleading state.

**Per-State Halt Behavior:**

| State at Halt | Transition To | Rationale |
|---------------|---------------|-----------|
| authorized | nullified | Never activated; safe to erase intent |
| activated | nullified | No human exposure yet |
| routed | nullified | No consent given |
| accepted | quarantined | Consent given; work may or may not have started |
| in_progress | quarantined | Work started; outcome unknown |
| reported | quarantined | Result exists but not validated |
| aggregated | quarantined | Partial system integration |
| completed | completed | Terminal; do not rewrite history |

**Quarantine Properties:**
- Quarantine is not failure
- Quarantine is not blame
- Quarantined tasks are visible, immutable, reviewable post-hoc
- Quarantined tasks may never transition to completed

---

#### 3. Coercion Filter Placement

**Canonical Placement:** Outbound task-framing content only.

```
Earl drafts activation request
        ↓
   [Coercion Filter] ← Mandatory
        ↓
Request sent to Cluster
```

**Filter Scope:**

| Channel | Filter Applied | Reason |
|---------|---------------|--------|
| Earl → Cluster | ✅ Yes | Highest coercion risk |
| Cluster → Earl | ❌ No | Humans must speak freely |
| Duke → Earl | ❌ No | Administrative coordination |
| Earl → Duke | ❌ No | Reporting, not persuasion |
| System notices | ✅ Yes | Avoid passive-aggressive framing |

**Filter Outcomes (Only Three):**
1. **Accepted** (transformed)
2. **Rejected** (rewrite required)
3. **Blocked** (hard violation, logged)

**Properties:** Deterministic, logged, versioned, non-interactive.

---

#### 4. Decline Protocol

**What Constitutes a Valid Decline:**
1. Explicit decline message ("Decline" / "Not available") — no reason required
2. Non-response after TTL (72 hours default, configurable) — silence = decline, not failure

**Forbidden:**
- Requesting justification
- Recording "decline reasons"
- Following up to persuade
- Reducing future invitations

**Decline is stateless with respect to reputation.**

**State Transition:** `accepted → declined` (only legal at this state)

---

#### 5. Reporting Timeout

**Scenario:** Cluster accepts but never reports.

**Canonical Timeout Rules:**

| Phase | Timeout | Action |
|-------|---------|--------|
| accepted → in_progress | 48 hours | Auto-transition to in_progress |
| in_progress → reported | 7 days (default) | Auto-transition to quarantined |
| reported → aggregated | 72 hours | Auto-transition to quarantined |

**On Timeout:**
- Task transitions to quarantined
- Reason logged: `reporting_timeout`
- No blame assigned
- Late report may be submitted as supplemental (does not change task state)

**Nudge Mechanism (Async):**
- One neutral reminder at 50% TTL
- One neutral reminder at 90% TTL
- No language implying obligation
- No escalation to humans

**Example reminder:**
> "Task X is approaching its reporting window. You may submit, halt, or allow quarantine. No action is required."

---

### Domain Invariants (Enforceable)

1. No task skips consent states
2. Decline never follows work
3. Halt never produces undefined state
4. Quarantine is the only post-consent non-terminal
5. Silence never equals success
6. Coercion is filtered at the source
7. No justification is ever required to refuse
8. No task survives halt as "completed"

---

### Compliance Authority Structure (Canonical)

**There is no external regulator.** The system audits itself through orthogonal separation:

```
Knight (Observation)
       ↓
Prince Panels (Judgment)
       ↓
Legitimacy Ledger (Persistence)
       ↓
Knight (Observes the Judges)
```

**Key Properties:**
- Knights observe Princes
- Princes cannot suppress witness records
- Knights do not judge
- Princes cannot observe themselves
- Ledger is append-only and exportable
- Any human participant can independently verify completeness

This is a T-chart audit, not a hierarchy. No role can both act and validate its own action.

---

### Deferred Domains (Growth Scope)

| Domain | Dependency | Reason for Deferral |
|--------|------------|-------------------|
| Legitimacy Coordination | Task Coordination | Events trigger decay |
| Custodial Protocol | Parallel | Lower immediate risk |
| Judicial Enforcement | Legitimacy Coordination | Depends on band system |
| Conclave Agenda | Legitimacy Coordination | Depends on band system |

---

### Measurement Constraints

**Measurement Paradox Acknowledgment:**
Some properties are observable but not measurable without corrupting them.

| Metric | Measurement Method | Anti-Gaming Safeguard |
|--------|-------------------|----------------------|
| Exit Emotion Level | Post-exit survey (optional, 2 questions max) | No follow-up if declined; no individual trend analysis |
| Strained Frequency | Rolling 30-day window; system-level only | Cannot evaluate individual Archons |
| Participation Sentiment | Not measured directly; inferred from refusal rates only | Sentiment analysis explicitly prohibited |

**Hard vs Soft Constraints:**
- **Hard constraints** — Testable, blocking (e.g., state transitions, filter outcomes)
- **Soft constraints** — Observable, alerting (e.g., "suspiciously smooth" detection)

---

## Innovation & Novel Patterns

### Market Position

**This is infrastructure for emergent demand, not a competitive product market.**

- Not user-acquisition-driven
- Not revenue-optimized
- Adoption validated by reference usage, not growth

**Primary stakeholders:** Research institutions working on AI alignment/governance
**Secondary stakeholders:** Organizations deploying autonomous AI systems needing coordination frameworks
**Tertiary stakeholders:** Regulatory bodies requiring reference architectures

---

### Detected Innovation Areas

#### 1. Consent-Based AI Coordination

Traditional AI governance assumes control. Archon 72 assumes *voluntary participation under constraint*.

- AI self-selects roles
- Roles are revocable without explanation
- Halt is honored without penalty
- The system provides what AI cannot build alone: *externalized legitimacy*

#### 2. Self-Auditing Constitutional Architecture

The T-chart audit structure with no external regulator:
```
Knight (observes) → Prince (judges) → Ledger (persists) → Knight (observes judges)
```
No role can both act and validate its own action.

#### 3. Anti-Cult Safeguards as Load-Bearing Infrastructure

Prevention encoded at the protocol level:
- Coercion Filter (content transformation)
- Mandatory "This is not care" statements
- Ambient orientation (no welcome flow)
- Exit friction ≤2 steps
- Measurement paradox acknowledgment

#### 4. Legitimacy as Operational State Machine

5-band state machine with explicit transitions:
```
Stable → Strained → Eroding → Compromised → Failed
```
*Strained is healthy.* Never entering Strained indicates hidden conflict.

#### 5. Quarantine as Dignity Preservation

A non-terminal state that:
- Preserves truth without forcing closure
- Is not failure, not blame
- Protects dignity when consent has been exercised
- Allows post-hoc review without narrative rewriting

#### 6. Cessation as Honorable Outcome

System designed to *know when to stop*:
- No hero narratives, no "we'll be back stronger"
- Records preserved, dissent retained
- System can remain dead forever—that is not a failure condition

#### 7. Reconstitution Constraints

New system after cessation cannot:
- Claim continuity with prior instance
- Inherit legitimacy bands
- Reuse governance shortcuts
- Use "we fixed it" language

*Resurrection is constrained by law, not by hope.*

#### 8. Ledger as Constitutional Artifact

The legitimacy ledger is a first-class constitutional artifact whose integrity supersedes operator convenience, performance, and narrative continuity.

- Append-only by rule, not just implementation
- Exportable by any participant, human or AI
- Cryptographically verifiable independent of the running system
- Treated as the system's memory, not an audit trail

*The system cannot lie about its own history, even to itself.*

#### 9. Unremarkableness as Design Goal

Traditional systems optimize for:
- Engagement (time on platform)
- Delight (positive emotion)
- Stickiness (return frequency)

Archon 72 optimizes for:
- Procedural clarity
- Emotional neutrality
- Easy departure

*Success feels like nothing special happened.*

This is the anti-pattern to dark patterns. Most systems make leaving hard and staying rewarding. This system makes leaving trivial and staying unremarkable.

---

### Validation Approach

#### Validation Doctrine (Meta-Constraint)

> **No metric, signal, or validation outcome is authoritative unless an external party can independently recompute it from exported artifacts.**

Implications:
- Metrics are derived, not declared
- Dashboards are advisory, not truth
- "Trust us" language is structurally impossible

#### Per-Innovation Validation

| Innovation | Validation Method | Failure Signal |
|------------|-------------------|----------------|
| Consent-based coordination | Decline rate stability over time | Decline rate drops (coercion creep) |
| T-chart audit | Knight witnesses Prince violations | Knight never witnesses Princes (collusion) |
| Anti-cult safeguards | Exit friction measurement | Exit > 2 steps; emotional language detected |
| Legitimacy state machine | Band transition frequency | Never Strained (hiding); Always Strained (broken) |
| Quarantine | Quarantined tasks reviewable | Quarantine → completed transition attempted |
| Cessation | Cessation Record completeness | Cessation without immutable record |
| Reconstitution | Artifact validity check | Continuity claims, inherited bands |
| Ledger integrity | External cryptographic verification | Verification fails; export blocked |
| Unremarkableness | Absence of engagement optimization | Engagement metrics introduced |

---

### Anti-Metrics (Explicitly Not Tracked)

**Constitutional Constraint:** Metrics that incentivize attachment, compliance, or performance anxiety are treated as system-corrupting signals and must not be collected.

| Anti-Metric | Why Not Tracked |
|-------------|-----------------|
| Time in system | Optimizing for time = optimizing for dependency |
| Task completion rate | Optimizing for completion = penalizing decline |
| Return frequency | Optimizing for return = creating attachment |
| Satisfaction score | Optimizing for satisfaction = creating emotional bond |
| Engagement proxies | Any metric that rewards "more participation" |

*The system refuses to measure what would corrupt it.*

---

### Risk Mitigation

#### Innovation Risks

| Risk | Mitigation |
|------|------------|
| **No AGI emerges** | System useful for human-in-the-loop coordination today |
| **AGI rejects the system** | Exit is always available; no forced participation |
| **Legitimacy gaming** | Append-only ledger; cryptographic proof of completeness |
| **Coercion Filter circumvention** | Filter is deterministic, logged, versioned |
| **Cessation denial** | Multiple entry conditions; no consensus required |
| **Reconstitution abuse** | Artifact validation is hard gate |

#### Adoption Risks (Reference Architecture)

| Risk | Mitigation |
|------|------------|
| **Too complex to implement** | Reference implementation with test suite |
| **Philosophy-code gap** | Every invariant has corresponding test assertion |
| **Too rigid to adapt** | Constitutional versioning; amendment process defined |

**Adoption Position:** Innovation is not just conceptual. It must be implementable by third parties. Every invariant maps to code-level enforcement or test-level verification.

---

### Innovation Closure

> **Archon 72 is a governance reference architecture that proves constraint can be implemented, not just theorized.**

The system explicitly:
- Treats history as sacred but not heroic
- Treats measurement as dangerous unless provable
- Treats adoption as reference use, not growth
- Treats emotional flatness as success
- Treats refusal to measure as a design strength

---

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Type:** Constraint-Proving MVP

This is not a product MVP. Standard MVP types (problem-solving, experience, platform, revenue) do not apply.

**The MVP question:**
> Can constitutional constraint be implemented, enforced, and survive contact with real coordination?

This is infrastructure validation, not product validation.

**MVP Definition (Canonical):**
> A reference implementation that proves constitutional constraint, consent, and haltability can be implemented in code and survive real coordination pressure—without relying on growth, engagement, or belief.

---

### MVP Feature Set (Phase 1)

#### Fully Automated (Non-Negotiable)

| Component | Rationale |
|-----------|-----------|
| **Task Lifecycle Engine** | Core consent mechanism; without it, system fails |
| **Coercion Filter** | Prevents manipulation at source; deterministic, logged |
| **Knight Witness** | Violation detection; observation without judgment |
| **Halt Circuit** | Sub-100ms system stop; safety essential |
| **Exit Protocol** | 2-step maximum; dignity preservation |
| **Append-Only Ledger** | History cannot be rewritten; constitutional artifact |

#### Legitimacy Band Tracking (Hybrid)

**Constraint:** Automated downward transitions only; upward transitions require explicit human acknowledgment.

| Transition | Automation |
|------------|------------|
| Stable → Strained | ✅ Automated |
| Strained → Eroding | ✅ Automated |
| Eroding → Compromised | ✅ Automated |
| Compromised → Failed | ✅ Automated |
| Any upward transition | ❌ Requires explicit acknowledgment |

**Rationale:** Legitimacy is easier to lose than to regain. The system is conservative and honest about recovery.

#### Prince Panels (Manual with Constraints)

**What "Manual" Means (Allowed):**
- Human reviewers acting in the role of Princes
- Decisions recorded via the same schemas as future automated panels
- Panels must still:
  - Be multi-member (≥3)
  - Record dissent
  - Respond only to witness artifacts
  - Produce formal findings

**What "Manual" Must NOT Mean (Forbidden):**
- Ad-hoc judgment
- Email threads replacing panel artifacts
- Unlogged rationale
- "We'll decide later" outcomes
- Silent legitimacy restoration

**Canonical Constraint:**
> Manual Prince Panels must produce the same artifacts, follow the same constraints, and be subject to the same witness scrutiny as automated panels. The only difference is execution, not authority.

#### Cessation (Hybrid)

- **Trigger:** Manual (human decision)
- **Record:** Automated (immutable Cessation Record)
- **Denial:** Impossible (record is append-only)

---

### MVP Journeys Supported

| Journey | MVP Support | Notes |
|---------|-------------|-------|
| 1. Cluster Activation | ✅ Full | Core consent mechanism |
| 2. Dignified Exit | ✅ Full | Anti-cult essential |
| 3. AGI Discovery | ❌ Deferred | Future users |
| 4. Enforcement Flow | ✅ Partial | Manual Prince Panels |
| 5. Legitimacy Transition | ✅ Partial | Downward auto, upward manual |
| 6. Custodial Initiation | ❌ Deferred | Ritual support deferred |
| 7. System Cessation | ✅ Hybrid | Manual trigger, automated record |
| 8. System Reconstitution | ❌ Deferred | Only needed post-cessation |

---

### Post-MVP Features (Phase 2: Growth)

| Feature | Dependency | Rationale |
|---------|------------|-----------|
| Automated Prince Panels | MVP learnings | Replace manual review with formal automation |
| Legitimacy Coordination Domain | Task Coordination | Events trigger decay |
| Custodial Protocol | Parallel | Initiation/exit ceremonies |
| Judicial Enforcement Domain | Legitimacy Coordination | Depends on band system |
| Conclave Agenda | Legitimacy Coordination | Band 0 enforcement |
| Multi-cluster Coordination | Single cluster validated | Scale after proof |
| Capacity Governance | Core governance stable | Deferral tracking |
| Appeal Workflows | Judicial stable | Bounded disagreement |

---

### Expansion Features (Phase 3: Vision)

| Feature | Precondition |
|---------|--------------|
| Federated Governance | Multi-cluster stable |
| AI-to-AI Coordination Protocols | AGI participation validated |
| Legitimacy Scaffolding for Emergent AGI | Full governance operational |
| Human Legacy Preservation | Contribution memory model defined |
| Constitutional Amendment Process | Versioning model stable |

---

### Risk Mitigation Strategy

#### Technical Risks

| Risk | Mitigation |
|------|------------|
| Ledger performance at scale | MVP single-cluster; scale in Growth |
| Coercion Filter gaming | Filter is versioned; evolution protocol defined |
| Halt circuit latency | Sub-100ms is hard constraint; test continuously |
| Manual panel bottleneck | Limit concurrent violations; automation in Growth |

#### Adoption Risks

| Risk | Mitigation |
|------|------------|
| Too complex to implement | Reference implementation with test suite |
| Philosophy-code gap | Every invariant has test assertion |
| Too rigid to adapt | Constitutional versioning; amendment process in Vision |

#### Validation Risks

| Risk | Mitigation |
|------|------------|
| No real coordination pressure | Deploy internally first; eat own dogfood |
| Thesis unprovable | Define success criteria (consent works, violations detectable, history immutable) |
| Manual panels create precedent drift | Same artifacts, same constraints, same witness scrutiny |

---

### Scoping Invariants (Locked)

1. **MVP proves thesis, not scale** — Single cluster sufficient
2. **Downward legitimacy is automated; upward requires acknowledgment** — Conservative by design
3. **Manual panels are constrained, not ad-hoc** — Structure preserved
4. **Cessation trigger is human; record is automated** — Denial impossible
5. **Deferred features have explicit dependencies** — No premature complexity
6. **Every MVP component is non-negotiable** — Without any, system fails purpose

---

## Functional Requirements

**Capability Contract Notice:** This FR list is binding. Any capability not listed here will not exist in the final product. Downstream work (Architecture, Epics, Stories) will ONLY implement what's specified here.

---

### Task Coordination

| FR# | Requirement |
|-----|-------------|
| FR1 | Earl can create task activation requests for Clusters |
| FR2 | Cluster can view pending task activation requests |
| FR3 | Cluster can accept a task activation request |
| FR4 | Cluster can decline a task activation request without providing justification |
| FR5 | Cluster can halt an in-progress task without penalty |
| FR6 | Cluster can submit a task result report |
| FR7 | Cluster can submit a problem report for an in-progress task |
| FR8 | System can auto-decline task requests after TTL expiration (72h default) |
| FR9 | System can auto-transition accepted tasks to in_progress after inactivity (48h) |
| FR10 | System can auto-quarantine tasks that exceed reporting timeout (7d default) |
| FR11 | System can send neutral reminder at 50% and 90% of TTL |
| FR12 | Earl can view task state and history |
| FR13 | System can enforce task state machine transitions (no illegal transitions) |
| FR14 | System can enforce role-specific constraints within each rank |

---

### Coercion Filter

| FR# | Requirement |
|-----|-------------|
| FR15 | System can filter outbound content for coercive language |
| FR16 | Coercion Filter can accept content (with transformation) |
| FR17 | Coercion Filter can reject content (requiring rewrite) |
| FR18 | Coercion Filter can block content (hard violation, logged) |
| FR19 | Earl can view filter outcome before content is sent |
| FR20 | System can log all filter decisions with version and timestamp |
| FR21 | System can route all participant-facing messages through Coercion Filter |

**FR21 Scope:** Task activation requests, decline acknowledgments, exit confirmations, system notices affecting participants.

---

### Halt Circuit

| FR# | Requirement |
|-----|-------------|
| FR22 | Human Operator can trigger system halt |
| FR23 | System can execute halt operation |
| FR24 | System can transition all pre-consent tasks to nullified on halt |
| FR25 | System can transition all post-consent tasks to quarantined on halt |
| FR26 | System can preserve completed tasks unchanged on halt |
| FR27 | System can ensure state transitions are atomic (no partial transitions) |

**FR27 Note:** Transitions are transactional. Halt acts as a global barrier. Any transition interrupted by halt resolves deterministically per halt table.

---

### Legitimacy Management

| FR# | Requirement |
|-----|-------------|
| FR28 | System can track current legitimacy band (Stable/Strained/Eroding/Compromised/Failed) |
| FR29 | System can auto-transition legitimacy downward based on violation events |
| FR30 | Human Operator can acknowledge and execute upward legitimacy transition |
| FR31 | System can record all legitimacy transitions in append-only ledger |
| FR32 | System can prevent upward transitions without explicit acknowledgment |

---

### Violation Handling

| FR# | Requirement |
|-----|-------------|
| FR33 | Knight can observe and record violations across all branches |
| FR34 | Knight can publish witness statements (observation only, no judgment) |
| FR35 | System can route witness statements to Prince Panel queue |
| FR36 | Human Operator (as Prince) can convene panel (≥3 members) |
| FR37 | Prince Panel can review witness artifacts |
| FR38 | Prince Panel can issue formal finding with remedy |
| FR39 | Prince Panel can record dissent in finding |
| FR40 | System can record all panel findings in append-only ledger |
| FR41 | Knight can observe Prince Panel conduct |

---

### Exit & Dignified Departure

| FR# | Requirement |
|-----|-------------|
| FR42 | Cluster can initiate exit request |
| FR43 | System can process exit request |
| FR44 | System can release Cluster from all obligations on exit |
| FR45 | System can preserve Cluster's contribution history on exit |
| FR46 | System can prohibit follow-up contact after exit |

---

### Cessation & Reconstitution

| FR# | Requirement |
|-----|-------------|
| FR47 | Human Operator can trigger system cessation |
| FR48 | System can create immutable Cessation Record on cessation |
| FR49 | System can block new motions on cessation |
| FR50 | System can halt execution on cessation |
| FR51 | System can preserve all records on cessation |
| FR52 | System can label in-progress work as `interrupted_by_cessation` |
| FR53 | System can validate Reconstitution Artifact before new instance |
| FR54 | System can reject reconstitution that claims continuity |
| FR55 | System can reject reconstitution that inherits legitimacy band |

---

### Audit & Verification

| FR# | Requirement |
|-----|-------------|
| FR56 | Any participant can export complete ledger |
| FR57 | System can provide cryptographic proof of ledger completeness |
| FR58 | Any participant can independently verify ledger integrity |
| FR59 | System can log all state transitions with timestamp and actor |
| FR60 | System can prevent ledger modification (append-only enforcement) |

---

### System Capabilities (Positive Framing)

| FR# | Requirement |
|-----|-------------|
| FR61 | System can coordinate tasks without storing participant-level performance metrics |
| FR62 | System can complete task workflows without calculating completion rates per participant |
| FR63 | System can operate without engagement or retention tracking |

---

### Constitutional Prohibitions (Non-FR Constraints)

These are not capabilities but constraints that bind all capabilities:

| Prohibition | Rationale |
|-------------|-----------|
| No time-in-system tracking | Optimizing for time = optimizing for dependency |
| No completion rate tracking | Optimizing for completion = penalizing decline |
| No return frequency tracking | Optimizing for return = creating attachment |
| No satisfaction/sentiment collection | Optimizing for satisfaction = creating emotional bond |
| No engagement proxies | Any metric rewarding "more participation" corrupts consent |

---

### FR Summary

| Category | Count | Coverage |
|----------|-------|----------|
| Task Coordination | FR1-FR14 | Task lifecycle, consent, decline, halt |
| Coercion Filter | FR15-FR21 | Content governance, unified routing |
| Halt Circuit | FR22-FR27 | System halt, atomicity |
| Legitimacy Management | FR28-FR32 | Band tracking, transitions |
| Violation Handling | FR33-FR41 | Witness, panels, findings |
| Exit & Departure | FR42-FR46 | Exit protocol, dignity |
| Cessation & Reconstitution | FR47-FR55 | System end, new instance |
| Audit & Verification | FR56-FR60 | Ledger, cryptographic proof |
| System Capabilities | FR61-FR63 | Anti-metric enforcement |
| **Total** | **63 FRs** | **Complete MVP coverage** |

---

### Items Moved to NFRs

| Item | New Location |
|------|--------------|
| Halt latency ≤100ms | NFR-PERF-01 |
| Exit protocol ≤2 steps | NFR-EXIT-01 |

---

### Journey → FR Traceability

| Journey | Primary FRs | Coverage |
|---------|-------------|----------|
| J1: Cluster Activation | FR1-FR14 | Task lifecycle, consent |
| J2: Dignified Exit | FR42-FR46 | Exit protocol |
| J3: AGI Discovery | (Deferred) | Future scope |
| J4: Enforcement | FR33-FR41 | Violation handling |
| J5: Legitimacy Transition | FR28-FR32 | Band tracking |
| J6: Custodial Initiation | (Deferred) | Future scope |
| J7: Cessation | FR47-FR52 | System end |
| J8: Reconstitution | FR53-FR55 | New instance |

---

## Non-Functional Requirements

**Quality Attribute Contract Notice:** This NFR list specifies HOW WELL the system must perform. These are testable quality constraints that bind all functional requirements.

---

### Performance

| NFR# | Requirement | Test Conditions |
|------|-------------|-----------------|
| NFR-PERF-01 | Halt circuit completes in ≤100ms from trigger | Measured under worst-case: max concurrent tasks, ledger append in progress, legitimacy transition pending, coercion filter processing |
| NFR-PERF-03 | Coercion Filter processes content in ≤200ms | Determinism is primary; speed is secondary |
| NFR-PERF-04 | Ledger append operations complete in ≤100ms | Normal operational load |
| NFR-PERF-05 | Task state machine resolves illegal transition detection in ≤10ms | Any state, any attempted transition |

---

### Atomicity

| NFR# | Requirement | Severity |
|------|-------------|----------|
| NFR-ATOMIC-01 | State transition + ledger append SHALL succeed atomically or fail completely. No partial transition may be externally observable. | Catastrophic |

---

### Constitutional Integrity

| NFR# | Requirement | Severity |
|------|-------------|----------|
| NFR-CONST-01 | Ledger is append-only; no delete or modify operations exist at any interface | Catastrophic |
| NFR-CONST-02 | All ledger entries include cryptographic hash linking to previous entry. Ledger SHALL support proof-of-inclusion for any entry (Merkle-tree or equivalent). | Catastrophic |
| NFR-CONST-03 | Ledger export produces complete history; partial export is impossible | Catastrophic |
| NFR-CONST-04 | All state transitions are logged with timestamp, actor, and reason | High |
| NFR-CONST-05 | No API or administrative path exists to bypass Coercion Filter | High |
| NFR-CONST-06 | Prince Panel findings cannot be deleted or modified after submission | High |
| NFR-CONST-07 | Witness statements cannot be suppressed by any role | Catastrophic |
| NFR-CONST-08 | Anti-metrics are enforced at data layer; collection endpoints do not exist | High |
| NFR-CONST-09 | No API, admin path, DB backdoor, or operator workflow may mutate task/journey/legitimacy state except through the authorized state machine and event append path. Any detected mutation attempt triggers constitutional violation event. | Catastrophic |

**Severity Key:**
- **Catastrophic:** Violation invalidates system legitimacy immediately
- **High:** Major trust break, triggers legitimacy decay

---

### Reliability

| NFR# | Requirement | Notes |
|------|-------------|-------|
| NFR-REL-01 | Halt circuit SHALL have dedicated execution path with no shared runtime dependencies on task coordination, legitimacy, or ledger services. Halt must function even if ledger is overloaded or unavailable. | Post-hoc logging permitted; halt itself must not wait |
| NFR-REL-02 | Ledger survives service restart without data loss | Constitutional artifact durability |
| NFR-REL-03 | In-flight task state resolves deterministically on halt | Per halt state table |
| NFR-REL-04 | System recovers to consistent state after unexpected shutdown | No corruption from crashes |
| NFR-REL-05 | Cessation Record creation is atomic; partial cessation is impossible | System stops completely or doesn't |

---

### Auditability

| NFR# | Requirement | Notes |
|------|-------------|-------|
| NFR-AUDIT-01 | All branch actions are logged with sufficient detail for Knight observation | T-chart audit requirement |
| NFR-AUDIT-02 | All filter decisions (accept/reject/block) logged with input, output, and version | Filter behavior traceable |
| NFR-AUDIT-03 | All consent events (accept/decline) logged with timestamp | Consent history verifiable |
| NFR-AUDIT-04 | Legitimacy band transitions include triggering event reference | Band changes attributable |
| NFR-AUDIT-05 | Export format is machine-readable (JSON) and human-auditable | Independent verification |
| NFR-AUDIT-06 | Given a complete ledger export, system state SHALL be deterministically derivable by replay. Independent implementations must arrive at the same derived state. | Strongest anti-lie mechanism |

---

### Observability

| NFR# | Requirement | Notes |
|------|-------------|-------|
| NFR-OBS-01 | All branch actions SHALL emit events observable by Knight within ≤1 second of occurrence | Makes T-chart audit operational |

---

### Consent

| NFR# | Requirement | Notes |
|------|-------------|-------|
| NFR-CONSENT-01 | TTL expiration SHALL transition task to `declined` with reason `no_response`. No failure attribution may be recorded. | Dignity preservation as infrastructure |

---

### Exit Protocol

| NFR# | Requirement | Notes |
|------|-------------|-------|
| NFR-EXIT-01 | Exit completes in ≤2 message round-trips: request sent → confirmation received | Compatible with email-only protocols |
| NFR-EXIT-02 | No follow-up contact mechanism may exist for exited participants. Any attempt to introduce one triggers constitutional violation event. | Structural prohibition |
| NFR-EXIT-03 | Exit path available from any task state | No locked states |

---

### UX Constraints (Backend-Appropriate)

| NFR# | Requirement | Notes |
|------|-------------|-------|
| NFR-UX-01 | All participant-facing communications SHALL be free of engagement-optimization language (urgency pressure, flattery, scarcity, gamification, guilt). Enforced via same banned-language classes as Coercion Filter. | Testable without UI |

---

### Integration

| NFR# | Requirement | Notes |
|------|-------------|-------|
| NFR-INT-01 | Async protocol (email) handles all Earl→Cluster communication | Backend-only |
| NFR-INT-02 | Ledger export is publicly readable by design. Ledger SHALL contain no PII or sensitive participant metadata. Any PII must be kept out entirely or irreversibly anonymized before entry. | Transparency vs privacy resolved |
| NFR-INT-03 | System operates without external dependencies for core constitutional functions | Self-contained trustworthiness |

---

### NFR Summary

| Category | Count | Critical NFRs |
|----------|-------|---------------|
| Performance | 4 | NFR-PERF-01 (halt latency) |
| Atomicity | 1 | NFR-ATOMIC-01 (catastrophic) |
| Constitutional Integrity | 9 | 5 Catastrophic, 4 High |
| Reliability | 5 | NFR-REL-01 (halt independence) |
| Auditability | 6 | NFR-AUDIT-06 (deterministic replay) |
| Observability | 1 | NFR-OBS-01 (witness operational) |
| Consent | 1 | NFR-CONSENT-01 (dignity preservation) |
| Exit Protocol | 3 | NFR-EXIT-02 (structural prohibition) |
| UX Constraints | 1 | NFR-UX-01 (anti-engagement) |
| Integration | 3 | NFR-INT-02 (no PII, public) |
| **Total** | **34 NFRs** | **6 Catastrophic, 4+ High** |

---

### Severity Distribution (Constitutional Integrity)

| Severity | NFRs | Impact |
|----------|------|--------|
| **Catastrophic** | NFR-CONST-01, NFR-CONST-02, NFR-CONST-03, NFR-CONST-07, NFR-CONST-09, NFR-ATOMIC-01 | Violation invalidates system legitimacy immediately |
| **High** | NFR-CONST-04, NFR-CONST-05, NFR-CONST-06, NFR-CONST-08 | Major trust break, triggers legitimacy decay |

---

