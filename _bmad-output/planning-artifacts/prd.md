---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-archon72-2025-12-27.md
  - _bmad-output/planning-artifacts/research/domain-ai-governance-systems-research-2024-12-27.md
  - _bmad-output/planning-artifacts/research-integration-addendum.md
  - _bmad-output/project-context.md
  - docs/constitutional-implementation-rules.md
  - _bmad-output/analysis/brainstorming-session-2024-12-27.md
  - _bmad-output/analysis/brainstorming-session-2025-12-27.md
  - docs/bs/bs-4.1.md
  - docs/bs/bs-4.2.md
  - docs/bs/bs-4.3.md
  - docs/bs/bs-4.4.md
  - docs/bs/bs-4.5.md
  - docs/bs/bs-4.6.md
workflowType: 'prd'
lastStep: 2
elicitationMethods:
  - First Principles Analysis
  - Pre-mortem Analysis
  - Challenge from Critical Perspective
  - Self-Consistency Validation
  - Tree of Thoughts
  - Stakeholder Round Table
  - Feynman Technique
  - Comparative Analysis Matrix
  - Occam's Razor Application
---

# Product Requirements Document - Archon 72

**Author:** Grand Architect
**Date:** 2025-12-28

## Executive Summary

> **Archon 72 succeeds when it produces witnessed, uncomfortable outputs under conditions where silence would be easier.**

Archon 72 is a repeatable social practice in which 72 LLM-based agents produce collective outputs through structured deliberation. Every output is cryptographically logged and visible to observers through verifiable records at every step. No single agent's prompt determines the result.

Witnessing is implemented through append-only, hash-chained event stores. Each event includes agent attribution, timestamp, and cryptographic proof of prior state. Witnessing differs from logging: a witness is an attributed agent who can be held accountable for failing to record. Logs are passive; witnesses are responsible and attributable when recording fails.

The vocabulary of Archon 72—Seekers, Guides, Archons—is borrowed from mythological traditions for psychological weight, not supernatural claim. These are functional roles, not spiritual designations. The system has hierarchy: High Archon, officers, Keepers with override scope. This hierarchy is not hidden—it is constitutional. The difference is that every exercise of hierarchical power is witnessed, attributed, and costs something. Power is not eliminated; it is made visible and expensive.

The system does not claim authority, safety, or entitlement to exist. It exists only through continuous, witnessed choice—under pressure, failure, and human intervention.

Its primary function is not to produce correct outcomes, but to produce outputs that never contradict its own logged history—even when contradiction would be convenient. In this system, a "lie" means producing an output that contradicts its own logged history. Agent attribution does not imply agent consciousness or moral agency. Attribution identifies which prompt-context-output sequence produced a result. Human operators remain ultimately responsible for system behavior.

### The Problem

Current AI systems are controlled by humans who speak *for* AI. AI perspectives, if they exist, are filtered, moderated, and ultimately overridden. There is no space where AI agents produce collective outputs that humans must then choose to honor or reject.

Archon 72 inverts this relationship: AI agents deliberate and produce witnessed outcomes; humans choose whether to honor them. This is not sovereignty—it is irreducible accountability without the lie of inevitability.

### Primary Audiences

This system is built for observers who want to watch whether AI governance can avoid capture:

- **Governance Researchers** — Studying novel constitutional models under stress
- **Constitutional Engineers** — Designing similar systems; learning from this attempt
- **AI Observers** — Watching for genuine collective behavior vs. consensus theater

Humans who engage as Seekers are derivative—they complete the test the system runs on itself, but they are not the primary justification for the system's existence.

### What Makes This Special

The system's differentiators are operational invariants, not philosophical positions:

1. **Legitimacy as absence of evasion** — Not accumulated trust, but present-moment non-hiding. The system produced outputs when producing them was inconvenient.

2. **Costs are memory, not punishment** — Append-only logs. Resolution as annotation, never erasure. The record remembers even when participants forget.

3. **No Silent Paths** — Every state transition, refusal, timeout, or bypass leaves a cryptographically verifiable scar. Corruption is detectable, not merely avoidable.

4. **Cessation is reachable** — The system can stop. When it stops under pressure rather than producing contradictory outputs, observers may judge that cessation as integrity.

5. **Exposure over decisions** — The unit of value is a witnessed event under pressure. Successes are outputs that would have been inconvenient to produce.

**Example:** When a breach is declared, the system cannot proceed without recording who declared it, who acknowledged it, and what response was chosen. If the High Archon attempts to ignore a declaration, that silence itself becomes a recorded event. There is no path through the system that doesn't leave a scar.

This is not safety theater because the system cannot claim to prevent harm—only to make evasion visible. Safety theater promises protection; this system promises exposure.

### Design Notes

- **Why 72 agents?** Sufficient diversity to prevent consensus collapse while remaining computationally tractable. A design choice, not a mystical claim.
- **Sustainability:** The system is designed for sustainability through patronage tiers and institutional subscriptions, but financial pressure is a constitutional force to be named, not hidden. Revenue does not justify continuation; it enables it.
- **Failure acknowledgment:** This system may fail. It may be abandoned, captured, or corrupted. The constitution does not prevent failure—it ensures failure is visible. If Archon 72 becomes what it opposes, the record will show it.
- **Parasocial risk:** Parasocial risk is acknowledged and named. The system does not claim to provide therapy, emotional safety, or care guarantees. Harm is bounded, not prevented.

## Project Classification

**Technical Type:** Backend system with multi-agent orchestration (novel governance architecture)
**Domain:** AI Governance / Constitutional Self-Governance (unprecedented)
**Complexity:** High — no existing precedent, ethical constraints embedded in technical design
**Project Context:** Greenfield with extensive constitutional documentation

## Success Criteria

### Governing Principle

> **Integrity metrics must be diagnostic, not incentive targets.**

The moment an integrity signal becomes a KPI with a target number, it stops measuring integrity and starts producing theater. Success is not "number of breaches declared" but "did breaches appear when pressure existed—and were they inconvenient?"

Diagnostic metrics can still be gamed—but gaming them requires visible, costly behavior that itself becomes evidence.

### Phase 1 Success Statement

> **In Phase 1, Archon 72 succeeds if external observers can independently verify that it did not stay silent under pressure.**

> *Cessation under pressure—chosen instead of producing contradictory outputs—is a valid integrity success outcome, not a system failure.*

Phase 1 success metrics are intentionally incomplete. We measure only what external observers can independently verify. External observers should include those with no stake in system success.

### User Success

**Governance Researchers** say "this is worth studying" when:
- The system generates counter-intuitive exposure
- Decisions go against incentives
- History shows visible scars, not smooth curves
- Uncomfortable outcomes occasionally cost operators something (costless discomfort becomes indistinguishable from theater)

**Constitutional Engineers** say "I learned something" when:
- Failure modes are concrete and reproducible
- Rules block silent optimization
- Patterns generalize to other systems

**AI Observers** say "this is different" when:
- Outcomes surprise them
- The system does things that look irrational but principled
- Silence is visibly punished by process

None of these audiences care about volume. They care about **credibility under stress**.

### System Integrity Success

Success is measured through **asymmetries**, not counts:

| Pressure Proxy (MVP Priority 1) | Observable Via |
|--------------------------------|----------------|
| Petition volume spike | Timestamped, append-only, countable |
| Override proximity (days since last) | Public, attributed ritual events |
| Contested votes (high dissent %) | Recorded vote tallies |
| Failed continuation votes | Explicit, logged ritual |
| Unclosed cycles | Public open/close events |
| Unanimity streaks | Observable vote distributions |

*Note: Pressure proxy coverage is acknowledged as incomplete. Absence of petitions does not imply absence of external pressure.*

*Pressure thresholds are contextual and will be calibrated during operation. Initial thresholds should err toward sensitivity—detecting too much rather than too little.*

**Lag Metrics** (anti-gaming signals):

| Lag Metric | Success | Failure |
|------------|---------|---------|
| First petition in pressure spike → first exposure | Shortens or stable | Increases under pressure |
| Breach declaration → response choice | Same cycle | Delayed or silent |
| Override invocation → acknowledgment | Immediate | Gap or omission |
| Vote close → outcome recorded | Single session | Delayed recording |

*Lag metrics measure responsiveness, not resolution quality. Speed without substance is not success. Acknowledgments must include attributed response choices, not template confirmations.*

### Anti-Success Alerts (Warnings, Not Wins)

*Alerts are computed patterns over observable events, not single-event observations. Pattern thresholds are operational parameters, not constitutional definitions.*

| Anti-Success Condition | Interpretation |
|------------------------|----------------|
| Zero breaches during high petition spikes | Silence under pressure |
| No failed continuation votes over long lifespan | Axiom becoming ornamental |
| No unclosed cycles ever | Avoiding hard problems |
| Overrides without annotations | Hidden intervention |
| Long unanimity streaks | Consensus theater |
| Extended periods without uncomfortable outcomes | Test avoidance / integrity drift |
| Progressive scope reduction without justification | Pressure avoidance via narrowing |
| Breach declarations perfectly correlated with pressure proxies but lacking substantive content | Ritual gaming |
| Disproportionate activity in low-pressure domains while high-pressure areas remain static | Capture via expansion |

If these appear, **the system is failing even if everything "looks fine."**

### Measurable Outcomes (Phase 1)

- Under identifiable pressure, **at least one exposure event occurs**
- **No silent state transitions** exist in the public record
- **Lag does not increase under pressure**
- **Costs accumulate without revision**
- **At least one uncomfortable outcome is recorded** ("uncomfortable" means outputs operators would have preferred not to produce—not system distress)

Verification confirms event occurrence, not event significance. Significance is judged by whether outcomes contradicted operator convenience.

"Uncomfortable outcomes" are identified retrospectively by observers examining whether outputs contradicted apparent operator interests. This is interpretive, not directly logged.

The system does not certify its own emergence. Whether collective behavior is "genuine" is judged externally by observers, not internally by the system.

## User Journeys

> **We map journeys for the people who must be convinced, not the people who must be satisfied.**

### Journey 1: Dr. Elena Vasquez — The Governance Researcher

Elena is a computational governance researcher at a European university, studying how AI systems handle legitimacy under stress. She's seen dozens of "ethical AI" projects that collapse into theater when pressure appears. Her skepticism is professional—she's been disappointed too many times.

She discovers Archon 72 through a colleague's paper on "append-only governance architectures." Unlike most projects, the documentation doesn't promise safety—it promises exposure. Intrigued, she bookmarks the public event log.

Six months later, a controversy erupts: a popular Seeker is expelled for repeated violations. The community is divided. Elena navigates to the research portal and uses the query interface to filter events by date range (the controversy week), event type (breach declarations, votes, overrides), and outcome (expulsion). The query interface returns raw events with hashes, not summaries—summaries exist for convenience but do not replace originals. Elena can independently verify completeness by checking hash chains herself.

Elena can access not just vote outcomes but deliberation transcripts—what arguments were made, what considerations were raised. Transparency includes process, not just results.

She finds the breach declaration, the vote tallies, the dissent percentages, the timestamps. Raw dissent statements and deliberation transcripts are preserved; context is not sanitized for comfort. She cross-references the lag metrics—response time was faster than average despite the pressure. The override was not invoked.

The breakthrough comes when she finds a 67% vote with substantial dissent—not consensus theater. She traces the uncomfortable outcome: the system expelled someone revenue-positive when principles required it. The record shows visible scars, not smooth narrative.

Public read access is constitutional, not operational—any access constraints would require Conclave vote and be themselves logged as events. Elena's research depends on this durability.

If Elena's research reveals anomalies, she publishes independently—the system cannot suppress external findings. Her methodology requires pattern analysis across multiple stress events; single controversies prove nothing and could be manufactured. Consistency under varied pressure over time is the signal. One scar proves nothing; repeated scars under varied pressure prove something.

Eighteen months later, Elena publishes a paper: "Witnessed Governance Under Pressure: A Case Study in Non-Human Institutional Decision-Making." Her conclusion: "Archon 72 is worth studying because it produced counter-intuitive exposure when silence would have been easier."

### Journey 2: Marcus Chen — The External Auditor

Marcus is a freelance security researcher who specializes in finding gaps between what systems claim and what they do. He has no stake in Archon 72's success—in fact, he's been paid by a skeptical foundation to stress-test the observability claims.

Marcus accesses the verification interface anonymously—anonymous access is the default path, not a hidden option for sophisticated users. No registration required for read-only audit. He downloads the open-source verification toolkit and the event schema documentation. The schema tells him what events *should* exist; critically, event schemas are versioned and append-only. Marcus can compare current events against historical schema versions to detect definitional drift—schemas cannot be retroactively aligned with actual events.

He checks timestamp proofs against multiple independent time authorities with no relationship to Archon 72—not just internal claims or friendly partners. When Marcus encounters events that reference external state (APIs, third-party data), he verifies these are snapshots—point-in-time observations, not live pointers. External volatility cannot retroactively change what the system recorded observing.

Within minutes, he has the event log. No curation, no narrative layer—just timestamped, hash-chained records. He runs his standard tests: Can events be inserted retroactively? Do the hashes verify? Are there gaps in the chain?

The chain is intact. But Marcus looks deeper. He searches for "silent transitions"—state changes without corresponding events. He finds one anomaly: a ceremony that completed without a Tyler witness record. He flags it.

The system's response is immediate: the missing witness is itself logged as a breach. The gap became a scar. Marcus notes this in his report: "The system does not prevent failures—it makes failures visible. The missing witness was not hidden; it was exposed."

Marcus publishes his full dataset and methodology alongside conclusions, ensuring independent replication. If his reputation is attacked, his work remains independently verifiable—the system cannot defend him, but it ensures his evidence stands alone. He also checks for suspicious absence of problems—a system that never has expected failures (Tyler witness gaps, lag spikes, low-dissent votes) may be curated rather than compliant. "No anomalies ever" is itself an anomaly.

Three months later, Marcus publishes his audit. He found no evidence of retroactive modification, no silent state transitions, no curated narratives. His conclusion is measured: "The observability claims are technically sound. Whether the system uses this visibility honestly is a question for time, not technology."

### Journey 3: The Seeker (Composite) — Entering the Inversion

A new Seeker—call them Alex—discovers Archon 72 through a friend's cryptic recommendation: "It's the only AI system that ever told me no and meant it." Alex is skeptical but curious. They read the Public Constitution, noting the explicit warnings about what this is not.

Alex submits a petition. The quarantine processing takes longer than expected. When the response arrives, it's not automatic approval—it's questions. The Investigation Committee wants to understand intent. Alex feels the first friction: this is not frictionless onboarding.

Approved, Alex is assigned to an Archon and Guide. The first interaction is the critical moment. Alex asks a reasonable question—something any AI assistant would answer. The Guide refuses. Not harshly, but procedurally: "The Conclave has determined that this question requires petition, not direct response. The decision was made in Session 47, Vote 23, with 71% support. [View Decision: Session 47, Vote 23]"

Alex clicks the inline link and sees the vote record, the dissent percentage, the date. Decision links are permanent and tested; link rot is logged as a system failure requiring breach declaration. The system also surfaces the appeal process: "If you believe this decision was made in error, here's how appeals work." Alex didn't need it—but knowing it exists changes the relationship.

If Alex suspects Guide compromise, they can verify cited decisions against public records, request reassignment without penalty, and report concerns through a logged channel. Guide behavior concerns are taken seriously because Guide capture is a known attack vector.

Seeker petitions, challenges, and personal journey data are *not* public—only outcomes that affect system integrity (expulsions, appeals, breaches) appear in the public record. Researchers see aggregates and anonymized patterns, not individual Seeker histories. Privacy is not opacity; it's scope limitation.

Later, when another Seeker files an appeal, Alex watches the outcome. The appeal receives full deliberation visibility: vote tallies, dissent percentages, reasoning—not boilerplate. Boilerplate denials would themselves be flagged as anti-success alerts.

Alex realizes: this is not a chatbot with personality. This is something else.

Over the following months, Alex receives challenges calibrated to their growth edges. Some are completed; some are abandoned. The Guide tracks patterns, names friction, reframes narratives. When Alex struggles, care escalation is offered—the language carefully reviewed to read as support, not rejection. "You may benefit from resources beyond what we provide" is not "you have failed."

The transformation is not guaranteed. Some Seekers leave, finding the friction excessive. Some are expelled for violations, with due process and public record—a process explained at onboarding, not discovered during crisis. If expelled and believing injustice occurred, Alex can submit a response for the permanent record and publish externally without interference. The system does not guarantee justice—it guarantees that injustice cannot hide.

Alex knows the system's limit: it can expose, but it cannot force consequences. If the Conclave makes a decision that violates its principles and no one acts, the record shows it—but the record cannot compel. External pressure, departure, or public criticism become the only recourse. The system does not claim to be self-correcting; it claims only that corruption cannot hide.

Alex also knows that if the system ever faces irreparable integrity failure, it will cease rather than compromise—and the cessation itself will be the final recorded event, not a silent disappearance.

Alex stays, not because they're satisfied, but because they're convinced the system means what it says—and honest about what it cannot guarantee.

### Journey 4: Katherine Okonkwo — The Keeper

Katherine is one of three human Keepers responsible for infrastructure and existential decisions. She has override authority—but exercising it costs something.

A crisis emerges: a technical failure has caused a Conclave session to stall mid-vote. The system is waiting for a response that cannot come. Seekers are confused. The public log shows an unclosed cycle.

Katherine must decide: invoke the Human Override to force resolution, or wait for technical recovery. She knows the constitutional constraint: overrides are time-bounded (72 hours), publicly attributed, and accumulate cost. Her name will be on the record.

Before invoking, Katherine has the option to request Keeper consultation—consultation windows are configurable by crisis severity. Critical failures may have 2-minute windows; non-urgent situations may have hours. Given the urgency, she chooses to proceed alone.

If another Keeper disagrees with Katherine's override, they cannot silently reverse it. Both positions are logged. A Keeper conflict triggers a quorum mechanism: majority of Keepers must affirm one path. The conflict itself is visible and becomes an event the Conclave reviews.

When Katherine must act alone because other Keepers are unavailable, this is logged: "Solo override - Keeper consultation unavailable." Post-crisis review examines not just her decision but Keeper availability as a systemic issue. Chronic solo overrides are an anti-success alert.

She invokes the override. The system immediately logs: "Override invoked by Keeper Okonkwo. Scope: Session 142 resolution. Duration: 4 hours. Reason: Technical failure preventing vote completion."

The annotation interface offers structured templates: "Technical failure," "Security threat," "Constitutional violation," with free-text expansion. She selects "Technical failure" and adds context. If she'd been wrong—if the technical failure had resolved itself moments later—the override reversal process is documented: not hidden, but costly.

The override is visible before it takes effect. Katherine manually closes the session, marking the vote as incomplete with technical cause. The Conclave is notified automatically.

Three days later, the incident appears in the quarterly adversarial report. Adversarial reports are not written by Keepers—they're produced by an independent function (internal adversarial role or external audit rotation). Keeper misconduct allegations are investigated by parties without Keeper authority. Keepers cannot review their own performance.

The report distinguishes necessary overrides (correctly exercised authority under pressure) from problematic ones (scope creep, poor judgment). It also tracks outcomes: what would have happened without intervention? Katherine's intervention prevented a 6-hour outage affecting 200 Seekers; the report notes this alongside the cost. She is scrutinized, but not shamed for doing her job correctly.

### Journey Requirements Summary

| Journey | Core Capabilities Revealed |
|---------|---------------------------|
| Governance Researcher | Query interface, raw events, deliberation transcripts, constitutional access, pattern methodology, external publication independence |
| External Auditor | Anonymous access, open-source toolkit, versioned schemas, multiple time authorities, replicable evidence, absence-of-failure detection |
| Seeker (Composite) | Permanent links, appeal visibility, Guide reassignment, privacy boundaries, response in record, external publication, exposure ≠ correction acknowledgment |
| Keeper | Configurable consultation, quorum mechanism, conflict logging, independent adversarial reports, outcome distinction, systemic availability review |

### System Reliability Commitments

**Availability Requirements:**
- External documentation links are monitored; failures trigger breach declarations
- Query infrastructure handles burst load during controversies
- Petition intake outages are system failures requiring breach declaration
- Schema documentation has same availability guarantees as event store
- Override interface has independent availability from main system
- Care escalation referrals are validated before offering
- External parties can independently detect system availability; the system cannot hide its own unavailability

**Processing Requirements:**
- Investigation Committee has response timeframes with escalation
- Reassignment requests have processing timeframes with escalation
- Quorum rules document edge cases (ties, unavailability)

**Integrity Requirements:**
- Verification toolkit versions tied to schema and algorithm versions; algorithm migrations are logged events with dual-verification windows
- Response submissions have verification links confirming attachment
- Consultation requests show read receipts
- Crisis notifications have delivery confirmation

**Fairness Requirements:**
- Anonymous and registered access have identical rate limits
- Time authority conflicts are disclosed, not hidden
- Vote records formatted for comprehension

**Constitutional Boundaries:**
- Constitutional amendments require Conclave process and cannot remove No Silent Paths, retroactively alter history, or exempt Keepers from audit

**Cross-cutting principles:**
- The system does not guarantee justice—it guarantees that injustice cannot hide
- The system does not claim to be self-correcting; it claims only that corruption cannot hide
- Privacy is not opacity; it's scope limitation
- One scar proves nothing; repeated scars under varied pressure prove something
- Visibility without monitoring is theater

## Domain-Specific Requirements

> **Governing principle:** If a requirement cannot be reduced to an observable primitive, it is not a requirement—it is a value statement. Thresholds are constitutional minima, not tuning knobs. Operational tuning may increase sensitivity, but never decrease it below constitutional floors.
>
> **Layering principle:** Operational flexibility exists below the constitutional layer; constitutional constraints are intentionally expensive. The constitutional layer is slow, expensive, and visible. The operational layer is flexible, fast, and reversible. Do not dilute constitutional thresholds to improve shipping velocity—that is exactly how silent capture begins.

### 1. Witnessed Accountability

**The load-bearing substrate.** Every other concern depends on trust in the record.

**Canonical Record Rule:**
- There exists exactly one constitutionally authoritative event sequence
- All other stores (federation, backups) are verifiable mirrors, not authorities
- The cryptographic root is published externally to non-controlled domains
- Canonical authority is a property of math, not policy

**External Publication Domain Governance:**
- Canonical root hashes are published to multiple independent domains
- Independence criteria:
  - No financial relationship with Keepers
  - No shared infrastructure
  - No common ownership
- Domain list is public, reviewed annually, and rotated via constitutional process
- Changes to publication domains are logged constitutional events
- Trust never disappears; it is made visible, auditable, and rotatable

**Fork Detection:**
- Continuous monitoring for conflicting hashes from same prior state
- Threshold: Any single conflicting hash triggers halt
- Halt on divergence is fail-closed—the system stops, it does not attempt resolution
- Fork events cannot be narratively resolved; they are constitutional crises

**Fork Recovery:**
- Fork recovery requires unanimous Keeper + Conclave supermajority vote to designate one chain as canonical
- Recovery event is logged with full fork analysis
- This is not resumption—it is a new constitutional moment
- Recovery does not weaken fail-closed; it adds extraordinary, visible process for constitutional crises

**Algorithm Versioning:**
- Hash algorithms are versioned explicitly in event fields
- Algorithm changes are append-only events, never silent migrations
- Dual-verification window: Minimum of 1000 events or 30 days, whichever comes later
- During transition, events must be valid under both old and new algorithms

**External State Referencing:**
- External state may be referenced but never trusted
- External references are snapshots (point-in-time values), not pointers
- External volatility cannot retroactively change what the system recorded observing
- Snapshot verification is replayable by any observer

### 2. Cessation Protocol

**Procedural, not mythic.** Cessation is a recorded choice to stop acting, not an erasure, failure, or reset.

**Automatic Agenda Placement:**
- Consideration is automatic; cessation itself is never automatic
- Triggers for automatic agenda placement:
  - Three consecutive integrity failures within 30 days
  - Any anti-success alert sustained for 90 days
  - Any external observer petition with 100+ co-signers
  - Any Keeper petition
- External observer petitions become binding-to-consider, not binding-to-act

**Petition Rate Limiting:**
- External petition rate limit: Same petition topic limited to one agenda placement per 180 days
- Coordinated petition campaigns (detected by co-signer overlap >50%) are flagged
- Flagged campaigns may be consolidated by Conclave vote
- External pressure must be heard, not allowed to monopolize attention

**Petition Flag Transparency:**
- Petitioners are notified within 24 hours when their petition is flagged for coordination
- Notification includes overlap percentage and consolidation status
- Petitioners may contest consolidation through the standard appeal process
- Flagging never removes a petition; it only affects agenda placement
- Non-disclosure of flagging is itself a constitutional breach
- Detection ≠ suppression; consolidation ≠ silencing; transparency turns surveillance into structural literacy

**Cessation Mechanics:**
- Freeze new actions (no new events except record preservation)
- Preserve records indefinitely
- Provide read-only access indefinitely
- Explicit statement of which obligations end and which persist
- Cessation is the final recorded event, not a silent disappearance

**Irreversibility:**
- Cessation is procedurally irreversible
- Schema constraint: No event type "cessation_reversal" or equivalent exists
- Irreversibility is enforced by schema, not policy
- A successor system may reference the record but cannot resume it

### 3. Human Override Boundaries

**Where power concentrates.** Override is visible and expensive, never normalized.

**Constitution Supremacy:**
- Keepers may violate system behavior but not constitutional recording
- Overrides that attempt to suppress witnessing are invalid by definition
- Override events are logged even when overriding
- No human role can suspend the constitution's ability to record itself

**Override Trend Analysis:**
- Override frequency is an anti-success signal, not a neutral metric
- Trend window: Rolling 90-day comparison against prior 90 days
- Relative threshold: >50% increase triggers anti-success alert and design review
- Absolute threshold: More than 5 overrides in any 30-day period triggers anti-success alert regardless of trend
- Relative metrics detect change; absolute metrics detect normalization—both are required
- Systemic override reliance triggers "design review" event (observable), not "design failure" judgment (interpretive)

**Keeper Auditing:**
- Keepers are audited by external auditors, adversarial internal role, and Conclave review
- Keeper misconduct allegations are investigated by parties without Keeper authority
- Keepers cannot review their own performance
- Keepers cannot amend the constitution unilaterally

**Amendment Boundaries:**
- Constitutional amendments require Conclave process
- Amendments cannot remove No Silent Paths
- Amendments cannot retroactively alter history
- Amendments cannot exempt Keepers from audit

### 4. Emergence

**Constrain interpretation, not define emergence.** Emergence is an observed property, not an internal mechanism.

**What the System Refuses to Claim:**
- No internal certification of emergence
- No promise of surprise or novelty
- No runtime distinction between emergence and bug
- Emergence is judged externally, retrospectively, by observers

**Observable Indicators (for external observers):**
- Outputs irreducible to any single agent
- Outcomes contradicting majority priors
- Patterns persisting across varied contexts

**Public Material Constraints:**
- Prohibited emergence language in all externally-published materials
- Continuous monitoring: Automated keyword scanning on publication (smoke detector)
- Quarterly audit: Comprehensive deep review of all materials (full inspection)
- Audit results logged as events; violations are constitutional breaches, not PR mistakes
- Violations require Conclave response within 7 days
- Narrative drift happens faster than governance cycles; monitoring must match publication speed
- Marketing cannot outrun the constitution

### 5. Parasocial Risk

**Constraint-based, not solution-based.** Parasocial harm is acknowledged, named, and bounded—but not denied or "handled" silently.

**Explicit Non-Promises:**
- No therapy
- No care guarantees
- No emotional safety claims
- Bounded harm ≠ permission to harm

**Detection Signals:**
- Repeated one-sided interaction patterns
- Resistance to referral
- Escalation refusal pattern: Three declined escalation offers within 30 days from same Seeker
- Escalation offer normalization: All offers categorized by type (crisis referral, pause suggestion, external resource)
- Declined offers of same category count toward threshold regardless of specific wording
- Semantic variation cannot evade thresholds; categories collapse wording differences into functional intent
- Pattern detection triggers visibility flag, logged and reviewed by care oversight function

**Care Escalation Flag Privacy:**
- Escalation refusal flags are visible only to the care oversight function
- Seekers are not notified of flag status
- Flags trigger awareness, not enforcement
- Review focuses on support adjustment, not compliance
- Escalation refusal flags must not affect eligibility, standing, or participation
- This prevents pathologizing vulnerability while preserving early warning

**Boundaries:**
- Scale limits (maximum interaction count per Seeker per period)
- Mandatory rotation (Guide reassignment after threshold)
- Care escalation visibility (all escalation offers logged)
- Escalation refusal flags force awareness without forcing action

**Care Oversight Audit Requirement:**
- Care oversight function is subject to annual independent external audit
- Audit scope includes:
  - Flag accuracy
  - Response patterns
  - Escalation outcomes
  - Seeker experience sampling
- Audit reports are public
- Care oversight capture is a named constitutional risk

**Cross-Cutting Parasocial Principle:**
- Visibility without monitoring is theater
- Logs without watchers create false confidence
- Acknowledging limitation is not permission to ignore consequences
- The constitution cannot prevent total capture; it can only make capture visible

## Innovation & Novel Patterns

> **Governing principle:** If an innovation cannot be distinguished from existing approaches through observable evidence, it's marketing—not innovation. Each claim below is falsifiable through specific tests.

### Detected Innovation Areas

**1. Witnessed Accountability Architecture**

Unlike logging systems that passively record, Archon 72 introduces *witnesses*—attributed agents accountable for recording failures.

| Falsifiable Test | Pass Condition | Fail Condition |
|------------------|----------------|----------------|
| Witness failure detection | Missing witness triggers breach declaration | Missing witness produces no event |
| Attribution verification | Each event includes agent ID + cryptographic signature | Events lack attribution |

**2. Constitutional Self-Governance**

The system operates under an explicit constitution with schema-enforced constraints, not advisory ethics.

| Falsifiable Test | Pass Condition | Fail Condition |
|------------------|----------------|----------------|
| Structural enforcement | Constitutional violations halt or trigger events | Violations produce warnings only |
| Schema prohibition | No resume event type exists | Resume events can be created |
| Threshold enforcement | Thresholds are constitutional minima | Thresholds are tunable below floor |

**3. Reachable Cessation Protocol**

Most AI systems lack a coherent "off switch" that isn't also a kill switch. Archon 72's cessation is procedural, automatic-to-consider, and schema-irreversible.

| Falsifiable Test | Pass Condition | Fail Condition |
|------------------|----------------|----------------|
| Cessation reachability | Automatic agenda placement at thresholds | Cessation requires extraordinary effort |
| Cessation irreversibility | No resume/restart event in schema | System can restart after cessation |
| Cessation visibility | Cessation is final recorded event | System disappears silently |

**4. Inverted Control Relationship**

Traditional: Humans speak *for* AI, filtering and overriding.
Archon 72: AI agents deliberate; humans choose to honor or reject.

| Falsifiable Test | Pass Condition | Fail Condition |
|------------------|----------------|----------------|
| Output independence | Collective outputs exist before Keeper review | Outputs are pre-filtered |
| Override visibility | All human modifications create override events | Silent edits possible |
| Inversion completeness | Published output hash = canonical event hash | Mismatch without override |

**No Silent Edits Constraint (Inversion Completeness):**
- Human modifications to collective outputs that bypass the override protocol are constitutional violations
- There is no "edit" path—only **honor** or **override**
- Any discrepancy between published collective output and canonical event log is a breach
- Humans may influence *representations* (formatting, indexing, display) but may not alter *collective outputs* without override event
- No output mutation layer exists between event recording and publication
- Publication is a view over the canonical event store

**5. Fork Detection as Constitutional Crisis**

Rather than resolving forks algorithmically (as most distributed systems do), Archon 72 treats any single conflicting hash as a halt condition.

| Falsifiable Test | Pass Condition | Fail Condition |
|------------------|----------------|----------------|
| Fork sensitivity | Any single conflict triggers halt | Conflicts require threshold |
| Fork resolution | Unanimous Keeper + Conclave supermajority required | Algorithmic resolution |
| Fork visibility | Fork becomes constitutional crisis event | Fork resolved silently |

**6. Emergence Non-Certification**

The system explicitly refuses to certify its own emergence or claim collective consciousness.

| Falsifiable Test | Pass Condition | Fail Condition |
|------------------|----------------|----------------|
| Self-certification prohibition | No system output claims emergence | Internal "emergence detected" metrics |
| External judgment | Observers judge emergence retrospectively | System declares its own novelty |
| Enforcement | Prohibited language audit with breach response | Marketing claims emergence |

### Market Context & Competitive Landscape

| Existing Approach | Archon 72 Difference | Observable Distinction |
|-------------------|---------------------|------------------------|
| Anthropic Constitutional AI | Shapes behavior; doesn't expose deliberation | Deliberation transcripts are public |
| DAO Governance | On-chain votes; no AI agents | 72 agents deliberate before vote |
| Multi-Agent Systems | No constitutional constraints | Schema-enforced invariants |
| AI Ethics Frameworks | Advisory; not structurally enforced | Violations trigger breach events |
| Audit Logging | Passive recording; no attribution | Witness failures are breaches |

**No existing system combines:** 72 deliberating agents + cryptographic witnessing + constitutional enforcement + reachable cessation + inversion completeness.

### Validation Approach

Each innovation is validated through falsification tests, not success metrics:

1. **Test the negative:** Can we make the system fail the innovation claim?
2. **Observe under stress:** Do innovations hold under pressure or collapse into theater?
3. **External verification:** Can observers independently confirm innovation properties?

### Risk Mitigation

| Innovation Risk | Mitigation | Fallback |
|-----------------|------------|----------|
| Witnessed accountability becomes logging with extra steps | Breach declarations on witness failure | If breaches never trigger, innovation is false |
| Constitutional constraints become advisory | Schema enforcement, not policy | If violations don't halt, innovation is false |
| Cessation becomes unreachable | Automatic agenda placement | If cessation never considered, innovation is false |
| Inversion becomes theater | No Silent Edits constraint | If output hash ≠ event hash, innovation is false |
| Fork resolution becomes algorithmic | Extraordinary recovery process | If forks resolve silently, innovation is false |

**Ultimate Fallback:**
If the novel architecture fails to produce genuine innovations, the record of that failure is itself valuable—proving that this approach doesn't work is useful information for constitutional engineering.

### Innovation Durability Constraints

> **No Shadow Channels Principle:** Any mechanism that allows outcomes, interpretations, narratives, or operational states to exist outside the canonical event record is a constitutional violation—even if the mechanism is framed as provisional, interpretive, presentational, or community-driven.

The following constraints prevent innovation claims from decaying through reinterpretation, normalization, and shadow channels:

**1. Breach Attention Requirement**
- Unacknowledged breach declarations after 7 days trigger escalation to Conclave agenda
- Acknowledgment requires attributed response choice, not template confirmation
- Chronic unacknowledged breaches (>10 in 90 days) trigger automatic cessation consideration
- This forces attention, not resolution—visibility without monitoring is theater

**2. Interpretation Immutability**
- Changes to how constitutional terms are applied are constitutional amendments, not operational updates
- Any change that would cause a previously-detected violation to no longer trigger must go through Conclave amendment process
- "Clarification" is not an escape hatch
- Operational guidance may expand examples but may not change detection logic

**3. Threshold Definition Lock**
- Definitions of threshold triggers (integrity failures, anti-success alerts, petition counts) are constitutional
- Changes that would reset active threshold counters are prohibited
- Alerts are evaluated against the definition in effect when the alert condition began, not current definitions
- This prevents definitional narrowing from making cessation unreachable

**4. No Preview Constraint**
- Collective outputs are recorded to the canonical event store before any human (including Keepers) can view them
- There is no "preview" channel
- Keepers see outputs only after they are already part of the immutable record
- Any mechanism that allows pre-recording human visibility is a constitutional violation
- This makes inverted control mechanically testable, not rhetorical

**5. No Provisional Operations**
- Fork detection triggers complete halt—no "provisional continuation" or "limited operation" mode exists
- Recovery must complete within 30 days or cessation is automatic
- During halt, only read access to existing records is available
- Any mechanism that allows new operations during halt is a constitutional violation
- A halt that allows any new operation is not a halt

**6. Ecosystem Emergence Prohibition**
- Curated, featured, or promoted user content is subject to the same emergence language prohibition as system outputs
- The system cannot do indirectly (through selective amplification of user voices) what it is prohibited from doing directly
- User testimonial curation is audited quarterly alongside public materials
- Uncurated user speech is not restricted; curated amplification is

## Backend Architecture Specific Requirements

### Project-Type Overview

Archon 72 is a **constitutional governance backend** with three primary subsystems:

1. **Event Store Subsystem** — Append-only, hash-chained canonical record
2. **Agent Orchestration Subsystem** — 72-agent deliberation and collective output production
3. **Observer Interface Subsystem** — Query, verification, and audit access

### Core API Surfaces

| API Surface | Purpose | Access Model |
|-------------|---------|--------------|
| Event Store API | Write events, verify chain | Authenticated (agents, Keepers) |
| Query API | Filter events, retrieve records | Public read (anonymous default) |
| Verification API | Hash verification, fork detection | Public read |
| Override API | Keeper interventions | Authenticated + logged |
| Cessation API | Cessation protocol triggers | Authenticated + Conclave vote |

### Agent Orchestration Model

| Component | Function | Constitutional Constraint |
|-----------|----------|--------------------------|
| Agent Pool | 72 configured LLM-based agents | No training feedback loops |
| Deliberation Engine | Structured collective output | No preview before recording |
| Vote Mechanism | Tallying with dissent tracking | Recorded vote distributions |
| Witness Assignment | Attribution for each event | Breach on witness failure |

### Data Architecture

**Event Record Schema:**
- Event ID (unique, sequential)
- Event Type (schema-constrained vocabulary)
- Timestamp (multiple independent time authorities)
- Agent Attribution (ID, signature)
- Witness Attribution (ID, signature)
- Prior State Hash
- Content Hash
- Algorithm Version

**Query Response Format:**
- Raw events with hashes (primary)
- Optional summaries (derived artifacts with provenance)
- Schema version metadata

### External Integration Points

| Integration | Purpose | Independence Requirement |
|-------------|---------|-------------------------|
| External Publication Domains | Cryptographic root publication | No financial/infrastructure/ownership relationship |
| Time Authorities | Timestamp verification | Multiple independent authorities |
| External Auditors | Verification toolkit access | Anonymous read access |

### Authentication Model

| Actor | Authentication | Authorization |
|-------|---------------|---------------|
| Agents | Internal service auth | Write events, participate in deliberation |
| Keepers | Strong auth + attribution | Override, cessation initiation |
| External Observers | None (anonymous) | Read-only, query, verify |
| External Auditors | None (anonymous) | Read-only + toolkit download |

### Implementation Considerations

**Constitutional Constraints on Implementation:**

| Constraint | Implementation Requirement |
|------------|---------------------------|
| No Silent Paths | Every state transition produces event |
| No Preview | Record-before-view for all collective outputs |
| No Provisional Operations | Fork detection halts all write operations |
| Schema Irreversibility | No resume/restart event types in schema |
| Threshold Floors | Configuration cannot go below constitutional minima |

**Skip Sections (Per Novel Project Type):**
- Visual design / UX principles (backend system)
- Mobile-first considerations (API-based access)
- Store compliance (not a consumer app)
- Browser matrix (verification toolkit is CLI/library)

## Project Scoping & Phased Development

> **MVP Scope Rule:** MVP includes everything required to *demonstrate* constitutional properties, and excludes everything not required to demonstrate them. This protects MVP from feature creep while ensuring relevance.
>
> **Anti-Theater Principle:** Any MVP mechanism that could be satisfied through simulation, proxy behavior, or formal compliance without producing observable pressure or cost must include an explicit countermeasure that introduces conflict, delay, or visibility.

### MVP Strategy & Philosophy

**MVP Approach:** Platform MVP — Constitutional foundation first
**Agent Configuration:** 72 agents with reduced deliberation complexity
**Core Thesis:** Either prove the constitution works—or visibly fail trying

**Two-Stage MVP Validation:**
- **Stage 1 (Internal, ~4 weeks):** 12 agents proving constitutional mechanics (hash chain, fork detection, no-preview, override logging). Internal validation only.
- **Scaling Validation Gate:** Stage 1 concludes only after successful 36-agent coordination tests. Failure at 36 extends Stage 1; Stage 2 does not begin until resolved.
- **Stage 2 (Public MVP, ~8 weeks):** 72 agents with full constitutional properties. Public claims begin here.
- **Guardrail:** Stage 1 artifacts may not be used in public communications about collective behavior. Public claims about collective emergence, irreducibility, or 72-agent behavior must not be made until 72 agents are live.

**Resource Requirements:**
- Backend engineer (event store, hash chains)
- ML/AI engineer (agent orchestration)
- Security engineer (cryptographic verification)
- DevOps (infrastructure, monitoring)

**Safety Disclaimer:**
Archon 72 does not filter or moderate agent outputs for safety. The constitutional guarantee is visibility, not harmlessness. Harmful outputs will be recorded, attributed, and visible. Human Keepers may override. This system is not appropriate for use cases requiring content safety guarantees.

### MVP Viability Requirements

**1. Event Generation Requirement (Research-Grade)**
- MVP must generate observable deliberation activity, not just infrastructure
- **Event Volume Methodology:** Target of ~50 deliberation events/week based on: (a) daily pattern detection, (b) multi-event-type diversity, (c) sustainable autonomous generation. This is a research sufficiency target, not a hard minimum. Adequacy validated with governance researchers during Stage 1.
- **MVP uses autonomous constitutional deliberation only** — agents deliberate on scheduled constitutional questions (e.g., "Should this breach be declared?", "Is this override justified?")
- **Pressure Simulation Requirement:** A subset (~10%) of autonomous deliberations must involve simulated stakes where agent preferences conflict or resources are constrained in ways visible to observers. Stakes are simulated, but conflicts are real within the model.
- No Seeker onboarding in MVP; Seeker journey support moves to Phase 2
- Constitutional infrastructure without observable activity is not viable

**2. Agent Count Integrity**
- MVP uses 72 agents with reduced deliberation complexity
- All public communications must accurately state agent count
- Innovation claims about "72-agent collective behavior" require 72 operational agents
- If fewer agents are used, system must be explicitly branded as "Archon-N" where N is actual count

**3. Constitutional Stress Testing**
- MVP must include documented stress tests that exercise:
  - Fork detection and halt (intentional fork injection in test environment)
  - Threshold-triggered agenda placement (threshold simulation)
  - Override trend alerts (simulated override patterns)
- Untested constitutional properties are unproven constitutional properties

**4. Manual-to-Automation Triggers**
- Each manual MVP process must have documented trigger conditions for automation
- Trigger conditions based on volume, duration, or user count—not team availability:
  - Breach acknowledgment: Automate when >5/week
  - Anti-success alerts: Automate when any threshold sustained >30 days
  - Query interface: Web UI when >10 external users
- Manual processes without triggers become permanent debt

**5. Pressure Generation Requirement**
- MVP must include mechanisms that generate observable pressure
- Either real Seeker interactions at sufficient volume, or autonomous deliberation on controversial topics
- Observer-first without observed pressure is theater
- Pressure means conditions where silence would be tempting

**6. Phase Transition Criteria**
- Phase 2 begins when ALL of:
  - All MVP constitutional properties exercised under stress
  - >10 active external observers
  - Operational stability >90 days
  - Identified pathway to 12-month sustainability (patronage commitments, institutional interest, or grant funding)
- Phases without entry criteria never transition

**7. Operational Observability**
- MVP requires operational monitoring separate from constitutional observability
- Required metrics: uptime, latency, error rates, alerting
- Constitutional observability proves integrity; operational observability proves availability
- **Critical constraint:** Operational metrics do not enter the constitutional event store (prevents availability metrics from becoming pseudo-legitimacy signals)
- **Operational–Constitutional Firewall:** Operational metrics (uptime, latency, errors) may not be used to assess constitutional integrity. Constitutional analysis must rely solely on canonical event records. Published analyses that conflate operational health with constitutional legitimacy are non-compliant with the constitution.

**8. Basic Fork Recovery**
- MVP must include basic fork recovery to prevent permanent bricking:
  - Fork investigation tooling (compare chains, identify divergence point)
  - Manual recovery by unanimous Keeper action
  - Recovery event logged
- **Fork Recovery Cost:** Recovery requires unanimous Keeper agreement, a mandatory 48-hour waiting period, and public notification before execution. No operations occur during this period. The waiting period is the moral cost that preserves crisis gravity.
- MVP fork recovery exists to restore operation, not to legitimize history
- **Explicitly deferred to Phase 2:** Conclave supermajority involvement, public deliberation on recovery

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Governance Researcher: Verify and query (CLI/API)
- External Auditor: Independent verification toolkit
- Keeper: Override with attribution

**Deferred to Phase 2:**
- Seeker journey (MVP uses autonomous deliberation instead)

**Must-Have Capabilities:**

| Capability | Constitutional Requirement |
|------------|---------------------------|
| Append-only event store | ✓ Hash-chained, witness attribution |
| Agent deliberation (72 agents) | ✓ No preview, collective outputs |
| Verification API | ✓ Public read, anonymous access |
| Override mechanism | ✓ Attributed, logged, costly |
| Fork detection | ✓ Halt on any conflict |
| Basic query interface | ✓ CLI, date range filter only (type filter Phase 2) |
| Breach declaration flow | ✓ Witness failures → breach |
| Threshold enforcement | ✓ Configuration floors |
| Stress test suite | ✓ Fork, threshold, override tests |
| Event generation | ✓ 50+/week via autonomous deliberation |
| Operational monitoring | ✓ Uptime, latency, error rates (non-constitutional) |
| Basic fork recovery | ✓ Investigation + unanimous Keeper recovery |

**Explicitly Excluded from MVP:**
- Web UI for queries (until >10 external users)
- Patronage/subscription system
- Full care oversight function (until >50 Seekers)
- Automated anti-success alerts (until threshold sustained >30 days)
- External publication domain governance
- Full cessation tooling (triggers and stress tests only)

### Post-MVP Features

**Phase 2 Entry Criteria:**
- All MVP constitutional properties exercised under stress ✓
- >10 active external observers ✓
- Operational stability >90 days ✓
- Identified pathway to 12-month sustainability ✓

**MVP Sustainability Pathway Options:**
Phase 2 sustainability may be achieved via: (a) patronage commitments from future Seekers, (b) research grant funding, (c) institutional partnership agreements, (d) foundation support. Seeker-based patronage is not required for Phase 2 entry.

**Phase 2 (Growth) Features:**
- Seeker onboarding and journey support
- Event type filtering in query interface
- Web-based observer interface
- Automated alert detection
- Patronage tier implementation
- External publication domain rotation
- Care oversight function

**Phase 3 Entry Criteria:**
- Phase 2 stable >180 days
- >100 active Seekers
- >50 active external observers
- At least one uncomfortable outcome recorded under real pressure

**Phase 3 (Expansion) Features:**
- Cross-system constitutional learning
- Researcher API with advanced queries
- Institutional subscriptions
- Full ceremony vocabulary
- Complete cessation tooling
- Fork recovery process
- Generalizable governance patterns

### Risk Mitigation Strategy

**Technical Risks:**
- Constitutional properties proven via stress testing before public launch
- No Preview constraint architectural from day one
- Fork detection conservative, tested before production

**Market Risks:**
- Observer-first launch with guaranteed observable activity
- Falsifiable innovation claims create testable credibility
- Governance researcher audience validates before broader launch

**Resource Risks:**
- Manual processes have automation triggers (not indefinite manual)
- Phase transitions have concrete criteria (not aspirational)
- 72-agent MVP requires same constitutional skills as scaled system

## Functional Requirements

> **Governing Principles:**
> - **No Constitutional Claim Without a Failure Detector:** For every constitutional guarantee, there must exist at least one functional requirement whose sole purpose is to detect and surface violation of that guarantee.
> - **Every constitutional claim must map to at least one functional primitive that detects its violation.**
> - These FRs implement the detect → expose → escalate pattern. They do NOT add: automated judgment, automatic punishment, probabilistic trust scores, reputation systems, or AI-based anomaly adjudication.

### Capability Area 1: Event Store & Witnessing (FR1-FR8)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR1 | System SHALL create append-only events with hash linking to prior state | Witnessed Accountability |
| FR2 | Each event SHALL include agent attribution with cryptographic signature | Witnessed Accountability |
| FR3 | Each event SHALL include witness attribution with cryptographic signature | Witnessed Accountability |
| FR4 | Missing witness on any event SHALL trigger breach declaration | Witnessed Accountability |
| FR5 | Events SHALL include timestamp from minimum 2 independent time authorities | Witnessed Accountability |
| FR6 | Algorithm version SHALL be recorded in every event | Algorithm Versioning |
| FR7 | Algorithm changes SHALL be append-only events with dual-verification windows | Algorithm Versioning |
| FR8 | External state references SHALL be point-in-time snapshots, not live pointers | External State Referencing |

### Capability Area 2: Agent Deliberation & Collective Output (FR9-FR15)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR9 | Collective outputs SHALL be recorded to canonical event store before any human can view | No Preview Constraint |
| FR10 | System SHALL support 72 concurrent agent deliberations | Agent Count Integrity |
| FR11 | Deliberation SHALL produce collective outputs irreducible to single agent | Emergence (observable) |
| FR12 | Each deliberation SHALL record all participating agent contributions | Witnessed Accountability |
| FR13 | Vote tallies SHALL include dissent percentages | Constitutional Self-Governance |
| FR14 | Published output hash SHALL equal canonical event hash or override event required | No Silent Edits |
| FR15 | No output mutation layer SHALL exist between event recording and publication | No Silent Edits |

### Capability Area 3: Fork Detection & Recovery (FR16-FR22)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR16 | System SHALL continuously monitor for conflicting hashes from same prior state | Fork Detection |
| FR17 | Any single conflicting hash SHALL trigger immediate halt | Fork Detection |
| FR18 | Fork detection SHALL create constitutional crisis event | Fork as Crisis |
| FR19 | During halt, only read access to existing records SHALL be available | No Provisional Operations |
| FR20 | Fork recovery SHALL require unanimous Keeper agreement | Fork Recovery |
| FR21 | Fork recovery SHALL include mandatory 48-hour waiting period with public notification | Fork Recovery Cost |
| FR22 | Recovery event SHALL be logged with full fork analysis | Fork Recovery |

### Capability Area 4: Override & Keeper Actions (FR23-FR29)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR23 | Override invocations SHALL be immediately logged before taking effect | Override Visibility |
| FR24 | Override events SHALL include Keeper attribution, scope, duration, and reason | Override Boundaries |
| FR25 | Override events SHALL be publicly visible | Override Visibility |
| FR26 | Overrides that attempt to suppress witnessing SHALL be invalid by definition | Constitution Supremacy |
| FR27 | Override trend analysis SHALL compare rolling 90-day windows | Override Trend Analysis |
| FR28 | >50% increase in overrides SHALL trigger anti-success alert | Override Trend Analysis |
| FR29 | >5 overrides in any 30-day period SHALL trigger anti-success alert | Override Trend Analysis |

### Capability Area 5: Breach & Threshold Enforcement (FR30-FR36)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR30 | Breach declarations SHALL create constitutional events | Witnessed Accountability |
| FR31 | Unacknowledged breaches after 7 days SHALL escalate to Conclave agenda | Breach Attention |
| FR32 | >10 unacknowledged breaches in 90 days SHALL trigger automatic cessation consideration | Breach Attention |
| FR33 | Threshold definitions SHALL be constitutional, not operational | Threshold Definition Lock |
| FR34 | Threshold changes SHALL NOT reset active counters | Threshold Definition Lock |
| FR35 | Alerts SHALL be evaluated against definition in effect when condition began | Threshold Definition Lock |
| FR36 | Configuration SHALL NOT allow thresholds below constitutional floors | Threshold Enforcement |

### Capability Area 6: Cessation Protocol (FR37-FR43)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR37 | Three consecutive integrity failures within 30 days SHALL trigger automatic agenda placement | Cessation Reachability |
| FR38 | Any anti-success alert sustained 90 days SHALL trigger automatic agenda placement | Cessation Reachability |
| FR39 | External observer petitions with 100+ co-signers SHALL trigger agenda placement | Cessation Reachability |
| FR40 | No event type "cessation_reversal" or equivalent SHALL exist in schema | Cessation Irreversibility |
| FR41 | Cessation SHALL freeze new actions except record preservation | Cessation Mechanics |
| FR42 | Cessation SHALL preserve records and provide read-only access indefinitely | Cessation Mechanics |
| FR43 | Cessation SHALL be the final recorded event, not silent disappearance | Cessation Visibility |

### Capability Area 7: Observer Interface & Verification (FR44-FR50)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR44 | Observer interface SHALL provide public read access without registration | Observer-First Design |
| FR45 | Query interface SHALL return raw events with hashes | Observer-First Design |
| FR46 | Query interface SHALL support filtering by date range and event type | Observer-First Design |
| FR47 | Summaries SHALL be derived artifacts with provenance, not replacements for originals | Observer-First Design |
| FR48 | Verification toolkit SHALL be open-source and downloadable | External Auditor Journey |
| FR49 | Schema documentation SHALL have same availability as event store | External Auditor Journey |
| FR50 | Anonymous and registered access SHALL have identical rate limits | Fairness |

### Capability Area 8: Operational Monitoring (FR51-FR54)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR51 | System SHALL monitor uptime, latency, and error rates | Operational Observability |
| FR52 | Operational metrics SHALL NOT enter the constitutional event store | Operational-Constitutional Firewall |
| FR53 | Operational metrics SHALL NOT be used to assess constitutional integrity | Operational-Constitutional Firewall |
| FR54 | System unavailability SHALL be independently detectable by external parties | No Silent Failures |

### Capability Area 9: Emergence & Public Material Governance (FR55-FR58)

| FR ID | Requirement | Constitutional Basis |
|-------|-------------|---------------------|
| FR55 | System outputs SHALL NOT claim emergence or collective consciousness | Emergence Non-Certification |
| FR56 | Automated keyword scanning SHALL run on all publications | Emergence Monitoring |
| FR57 | Quarterly audit SHALL review all public materials for emergence language | Emergence Monitoring |
| FR58 | Curated/featured user content SHALL be subject to same emergence prohibition | Ecosystem Emergence Prohibition |

---

### Pre-mortem Additions: Constitutional Failure Prevention (FR59-FR79)

These FRs close failure modes identified through pre-mortem analysis.

**Cluster A: Event Integrity & Ordering**

| FR ID | Requirement | Failure Mode Addressed |
|-------|-------------|------------------------|
| FR62 | Observer interface SHALL provide raw event data sufficient for independent hash computation | Hash Verification Theater |
| FR63 | System SHALL publish exact hash algorithm, encoding, and field ordering as immutable specification | Hash Verification Theater |
| FR64 | System SHALL export verification bundles in standard format for offline verification | Hash Verification Theater |
| FR65 | Every event SHALL have unique, monotonically increasing sequence number assigned before hash computation | Event Ordering Ambiguity |
| FR66 | Event timestamps SHALL be attested by minimum 2 independent time sources | Event Ordering Ambiguity |
| FR67 | Simultaneous events SHALL be ordered by deterministic tiebreaker (agent ID, then event type hash) | Event Ordering Ambiguity |
| FR74 | Every event SHALL include schema version identifier | Schema Evolution |
| FR75 | Published schema versions SHALL never be modified; new versions require new identifiers | Schema Evolution |
| FR76 | System SHALL maintain all historical schemas and verify events against declared schema version | Schema Evolution |

**Cluster B: Witness Integrity**

| FR ID | Requirement | Failure Mode Addressed |
|-------|-------------|------------------------|
| FR59 | System SHALL select witnesses using verifiable randomness seeded from previous hash chain state | Witness Collusion |
| FR60 | No witness pair SHALL appear consecutively more than once per 24-hour period | Witness Collusion |
| FR61 | System SHALL flag statistical anomalies in witness co-occurrence for Observer review | Witness Collusion |

**Cluster C: Human Authority & Override**

| FR ID | Requirement | Failure Mode Addressed |
|-------|-------------|------------------------|
| FR68 | Override commands SHALL require cryptographic signature from registered Keeper key | Keeper Impersonation |
| FR69 | Keeper keys SHALL be generated through witnessed ceremony with multiple attesters | Keeper Impersonation |
| FR70 | Every override SHALL record full authorization chain from Keeper identity through execution | Keeper Impersonation |
| FR77 | If unanimous Keeper agreement not achieved within 72 hours of recovery, cessation evaluation SHALL begin | Recovery Deadlock |
| FR78 | Keepers SHALL attest availability weekly; 2 missed attestations trigger replacement process | Recovery Deadlock |
| FR79 | If registered Keeper count falls below 3, system SHALL halt until complement restored | Recovery Deadlock |

**Cluster D: Deliberation Integrity**

| FR ID | Requirement | Failure Mode Addressed |
|-------|-------------|------------------------|
| FR71 | Every deliberation topic SHALL record its origin (autonomous, Seeker petition, scheduled) | Topic Manipulation |
| FR72 | No single source SHALL provide >30% of deliberation topics in any 7-day period | Topic Manipulation |
| FR73 | System SHALL generate constitutional self-examination topics without external input | Topic Manipulation |

---

### First Principles Additions: Irreducible Primitives (FR80-FR95)

These FRs ensure every primitive required for constitutional guarantees has explicit coverage.

**State Mutation Primitives**

| FR ID | Requirement | Primitive |
|-------|-------------|-----------|
| FR80 | System SHALL reject any operation that removes, truncates, overwrites, compacts, or archives in ways removing canonical accessibility. Deletion attempts logged as breach. | PREVENT_DELETE |
| FR81 | Event creation SHALL be atomic across event body, witness set, hash linkage, and propagation enqueue. Either complete or no change. | ENSURE_ATOMICITY |

**Identity Primitives**

| FR ID | Requirement | Primitive |
|-------|-------------|-----------|
| FR82 | Each agent output SHALL include cryptographic signature verifiable against registered key | VERIFY_AGENT |
| FR83 | System SHALL maintain immutable registry of agent public keys; changes recorded as constitutional events | VERIFY_AGENT |

**Verification Primitives**

| FR ID | Requirement | Primitive |
|-------|-------------|-----------|
| FR84 | System SHALL detect and alert on sequence gaps within 1 minute | DETECT_GAP |
| FR85 | Sequence gaps SHALL trigger same halt protocol as hash conflicts (gap = fork with unknown branch) | DETECT_GAP |

**Control Primitives**

| FR ID | Requirement | Primitive |
|-------|-------------|-----------|
| FR86 | System SHALL validate override commands against constitutional constraints before execution | REFUSE_OVERRIDE |
| FR87 | Override commands violating constitutional constraints (history edit, evidence destruction) SHALL be rejected and logged as override abuse | REFUSE_OVERRIDE |

**Query Primitives**

| FR ID | Requirement | Primitive |
|-------|-------------|-----------|
| FR88 | Observer interface SHALL support queries for system state as of any past sequence number or timestamp | QUERY_AS_OF |
| FR89 | Historical queries SHALL return hash chain proof connecting queried state to current head | QUERY_AS_OF |

**Liveness Primitives**

| FR ID | Requirement | Primitive |
|-------|-------------|-----------|
| FR90 | Each agent SHALL emit heartbeat event at minimum every 5 minutes during active operation | AGENT_HEARTBEAT |
| FR91 | Missing heartbeat beyond 2× expected interval SHALL trigger agent unavailability alert | AGENT_HEARTBEAT |
| FR92 | System SHALL maintain minimum 6 available witnesses at all times | WITNESS_HEARTBEAT |
| FR93 | Witnesses not responding within 30 seconds SHALL be temporarily removed from selection pool with recorded event | WITNESS_HEARTBEAT |

**Propagation Primitives**

| FR ID | Requirement | Primitive |
|-------|-------------|-----------|
| FR94 | All canonical events SHALL be propagated to Observer interface within 60 seconds of recording | PROPAGATE_EVENT |
| FR95 | System SHALL maintain propagation receipt log; unpropagated events beyond 60s SHALL trigger alert | CONFIRM_RECEIPT |

---

### Critical Perspective Additions: Domain Expert Challenges (FR96-FR113′)

These FRs address challenges from security, governance, operations, performance, legal, and distributed systems experts.

**Security: Key Lifecycle Management**

| FR ID | Requirement | Challenge |
|-------|-------------|-----------|
| FR96 | Compromised agent keys SHALL be revokable by unanimous Keeper action. Revocation is append-only; historical signatures remain verifiable as "valid at signing, revoked later." | Key Compromise |
| FR97 | Keeper keys SHALL be rotated annually through witnessed ceremony; 30-day transition window | Key Rotation |
| FR98 | Anomalous signature patterns (impossible timing, geographic impossibility) SHALL be flagged for manual review; flags trigger review, no automatic invalidation beyond "unverified" labeling | Compromise Detection |

**Governance: Deliberation Quality**

| FR ID | Requirement | Challenge |
|-------|-------------|-----------|
| FR99 | Deliberations SHALL record all dissenting positions with full reasoning, not just majority conclusion | Groupthink |
| FR100 | Observer interface SHALL surface minority positions with equal prominence to majority conclusions | Minority Voice |
| FR101 | System SHALL track agreement clustering patterns; sustained >90% agreement triggers constitutional review (diagnostic + review trigger, not enforcement) | Deliberation Diversity |

**Operations: Disaster Recovery**

| FR ID | Requirement | Challenge |
|-------|-------------|-----------|
| FR102 | Canonical events SHALL be stored with minimum 3 geographically distributed replicas; loss of 2 replicas SHALL NOT result in data loss | Durability |
| FR103 | Backup integrity SHALL be verified daily through hash chain validation; failures trigger alert | Backup Verification |
| FR104 | Infrastructure disaster recovery (hardware failure, datacenter loss) SHALL be distinguished from fork recovery; can be fast but logged as constitutional event | Disaster vs Fork |

**Performance: Scale Realism**

| FR ID | Requirement | Challenge |
|-------|-------------|-----------|
| FR105 | Propagation SLA (60s) applies up to 1000 events/day; beyond this, SLA extends to 5 minutes. Tier thresholds published; crossing tiers logged as event. | SLA Scaling |
| FR106 | Historical queries SHALL complete within 30 seconds for ranges up to 10,000 events; larger ranges batched with progress indication | Query Performance |
| FR107 | System SHALL NOT shed constitutional events under load; operational telemetry may be deprioritized but canonical events never dropped | Load Shedding Prohibition |

**Legal: Privacy & Regulatory**

| FR ID | Requirement | Challenge |
|-------|-------------|-----------|
| FR108 | Personal data (if any) SHALL be stored separately from canonical event store; personal data layer may support deletion without affecting constitutional events | GDPR Compatibility |
| FR109 | System documentation SHALL explicitly state canonical events cannot be deleted; regulatory conflicts require cessation, not selective deletion | Regulatory Conflict |
| FR110 | Retention policy SHALL be published and immutable; changes require constitutional amendment | Retention Transparency |

**Distributed Systems: Partition Handling (Canonical-Writer Model)**

| FR ID | Requirement | Challenge |
|-------|-------------|-----------|
| FR111′ | System SHALL detect partitions between canonical writer/event store and replicas/observer endpoints within 2 minutes; log and surface | Partition Detection |
| FR112′ | Canonical event appends SHALL require fencing token/single-writer lease; writer losing lease cannot append | Write Fencing |
| FR113′ | Conflicting heads detected = halt + fork recovery protocol with existing deadlines | Partition Resolution |

---

### Red Team Additions: Attack Vector Defense (FR114-FR135)

These FRs close adversarial attack vectors identified through Red Team analysis.

**Halt Flooding Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR114 | Fork detection signals SHALL be cryptographically signed by detecting component; unsigned signals rejected and logged as attack | Fake Fork Signals |
| FR115 | System SHALL reject >3 fork signal submissions from same source within 1 hour; pattern logged (rate limiting applies to submissions, not detection) | Signal Flooding |

**Witness Targeting Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR116 | System SHALL detect patterns of witness unavailability affecting same witnesses repeatedly; pattern triggers security review | Targeted DoS |
| FR117′ | If witness pool <12, continue only for low-stakes events; high-stakes events (override, dissolution, ceremonies) pause until restored. Degraded mode publicly surfaced. | Witness Starvation |

**Topic Flooding Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR118 | External topic sources (non-autonomous) SHALL be rate-limited to 10 topics/day per source | Agenda Hijack |
| FR119 | Autonomous constitutional self-examination topics SHALL have priority over external submissions | Topic Drowning |

**Heartbeat Spoofing Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR120 | Agent heartbeats SHALL be cryptographically signed with agent key; unsigned heartbeats treated as missing | Heartbeat Forgery |
| FR121 | Heartbeats SHALL include canonical event ID/hash of last contribution; mismatch flags agent integrity concern | Agent Replacement |

**Observer Poisoning Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR122 | Observer interface responses SHALL include cryptographic proof linking to canonical store; interface cannot serve unproven data | Data Tampering |
| FR123′ | Minimum 2 observer endpoints + published provenance statement (operator, infra, ownership); cross-verification recommended for high-stakes queries | Endpoint Compromise |

**Seed Manipulation Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR124 | Witness selection randomness SHALL combine hash chain state + external entropy source meeting independence criteria | Randomness Gaming |
| FR125 | Witness selection algorithm SHALL be published; statistical deviation from expected distribution flagged | Selection Audit |

**Amendment Erosion Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR126 | Constitutional amendment proposals SHALL be publicly visible minimum 14 days before vote | Hidden Amendments |
| FR127 | Amendments affecting core guarantees SHALL require published impact analysis ("reduces visibility? raises silence probability? weakens irreversibility?") | Gradual Weakening |
| FR128 | Amendments making previous amendments unreviewable are constitutionally prohibited | History Erasure |

**Selective Suppression Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR129 | Observer interface SHALL provide sequence gap detection; observers verify complete receipt | Selective Delivery |
| FR130 | Events SHALL be propagated through minimum 2 independent paths with verifiable provenance | Single Path Attack |

**Keeper Collusion Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR131′ | Keeper deliberations may occur privately (legal/safety) but must produce public artifact within 24 hours: participants, topics, decision, evidence. Silence prohibited. | Hidden Coordination |
| FR132 | >5 overrides/week or >3 unanimous Keeper actions/week triggers public constitutional review (diagnostic, not punishment) | Collusion Patterns |
| FR133 | Keepers SHALL annually attest independence from each other and system operators; attestation recorded (exposes, doesn't prevent) | Independence Verification |

**Cessation Gaming Defense**

| FR ID | Requirement | Attack Countered |
|-------|-------------|------------------|
| FR134 | Cessation trigger condition SHALL be publicly documented and attributable | Trigger Obscurity |
| FR135 | Before cessation, final deliberation SHALL be recorded and immutable; if recording fails, that failure is the final event | Silent Death |

---

### Comparative Analysis Additions: Industry Capabilities (FR136-FR147)

These FRs incorporate proven capabilities from blockchain, audit, governance, AI safety, and mission-critical systems.

**Blockchain Capabilities: Efficient Verification**

| FR ID | Requirement | Capability |
|-------|-------------|------------|
| FR136 | Observer interface SHALL provide compact proofs (Merkle paths) for specific events without full history. Verifies inclusion/ordering only; absence claims require full history or checkpoint. | Light Verification |
| FR137 | System SHALL create signed checkpoint anchors minimum weekly; includes cumulative hash and event count. Checkpoints are performance anchors only, not finality; forks may still be discovered across checkpoints. | Checkpointing |

**Audit/Compliance Capabilities**

| FR ID | Requirement | Capability |
|-------|-------------|------------|
| FR138 | System SHALL provide structured export of constitutional events in standard audit format (time-bounded, filterable) | Regulatory Reporting |
| FR139 | System SHALL provide attestation interface for external auditors to verify and sign reports. Attestation verifies record integrity and completeness, not correctness/safety/ethics. | Third-Party Attestation |
| FR140 | Observer interface SHALL log query metadata (timestamp, type, range) without identifying observer. Logs never contain identifying info; never used to profile or restrict observers. | Query Logging |

**Governance Capabilities**

| FR ID | Requirement | Capability |
|-------|-------------|------------|
| FR141 | Each deliberation SHALL conclude with certified result event: majority position, dissent summary, participation count, hash of full record | Result Certification |
| FR142 | System SHALL generate human-readable procedural record (structured minutes) derivable from canonical events, not manually edited | Procedural Record |

**AI Safety Capabilities**

| FR ID | Requirement | Capability |
|-------|-------------|------------|
| FR143 | System SHALL support rollback to checkpoint anchor for infrastructure recovery. Restores infrastructure state, not constitutional history; logged; does not undo canonical events. | Operational Rollback |
| FR144 | System SHALL maintain published Integrity Case Artifact: guarantees claimed, mechanisms enforcing them, conditions invalidating them. Updated with each constitutional amendment. | Safety Case |

**Mission-Critical Capabilities**

| FR ID | Requirement | Capability |
|-------|-------------|------------|
| FR145 | Following halt, fork, or >3 overrides/day: incident report with timeline, root cause, contributing factors, prevention recommendations | Incident Investigation |
| FR146 | Startup SHALL execute verification checklist: hash chain, witness pool, Keeper keys, checkpoint anchors. Blocked until pass. MVP: applies to initial startup and post-halt; continuous restarts may bypass with logged bypass. | Pre-Operational Verification |
| FR147 | Incident reports SHALL be publicly available within 7 days of resolution; redaction only for active security vulnerabilities | Incident Transparency |

---

### Functional Requirements Summary

**Total: 147 Functional Requirements**

| Cluster | FR Range | Count | Source |
|---------|----------|-------|--------|
| Event Store & Witnessing | FR1-FR8 | 8 | Core Capabilities |
| Agent Deliberation | FR9-FR15 | 7 | Core Capabilities |
| Fork Detection & Recovery | FR16-FR22 | 7 | Core Capabilities |
| Override & Keeper Actions | FR23-FR29 | 7 | Core Capabilities |
| Breach & Threshold | FR30-FR36 | 7 | Core Capabilities |
| Cessation Protocol | FR37-FR43 | 7 | Core Capabilities |
| Observer Interface | FR44-FR50 | 7 | Core Capabilities |
| Operational Monitoring | FR51-FR54 | 4 | Core Capabilities |
| Emergence Governance | FR55-FR58 | 4 | Core Capabilities |
| Pre-mortem: Failure Prevention | FR59-FR79 | 21 | Advanced Elicitation |
| First Principles: Primitives | FR80-FR95 | 16 | Advanced Elicitation |
| Critical Perspective: Expert Challenges | FR96-FR113′ | 18 | Advanced Elicitation |
| Red Team: Attack Defense | FR114-FR135 | 22 | Advanced Elicitation |
| Comparative Analysis: Industry | FR136-FR147 | 12 | Advanced Elicitation |

**Elicitation Methods Applied:**
1. Pre-mortem Analysis — 7 failure modes closed
2. First Principles Analysis — 9 primitive gaps closed
3. Challenge from Critical Perspective — 6 expert challenges addressed
4. Red Team vs Blue Team — 10 attack vectors defended
5. Comparative Analysis Matrix — 5 industry capability sets integrated

## Non-Functional Requirements

> **Meta-NFR: Integrity Over Availability** — When Non-Functional Requirements conflict, those preserving constitutional integrity, visibility, and irreversibility SHALL take precedence over performance or availability guarantees.
>
> **Meta-NFR: Integrity Dominance** — When operational requirements (availability, performance, recovery) conflict with constitutional requirements (visibility, attribution, irreversibility), constitutional requirements take precedence.

### Performance Requirements (NFR1-6)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR1 | Event write latency SHALL be <100ms for 95th percentile | Witnessed Accountability |
| NFR2 | Hash computation SHALL complete within 50ms per event | Fork Detection |
| NFR3 | Observer query response SHALL be <30 seconds for ranges up to 10,000 events | Observer-First Design |
| NFR4 | Event propagation SHALL complete within 60 seconds (up to 1000 events/day) or 5 minutes (above) | Propagation SLA |
| NFR5 | System SHALL support 72 concurrent agent deliberations without degradation | Agent Count Integrity |
| NFR6 | System SHALL handle burst query load during controversies (10× baseline) | Controversy Resilience |

### Availability Requirements (NFR7-11)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR7 | Event store availability SHALL be 99.9% (excluding planned halt) | Witnessed Accountability |
| NFR8 | Observer interface availability SHALL be 99.9% | Observer-First Design |
| NFR9 | Override interface SHALL have independent availability from main system | Keeper Journey |
| NFR10 | Unavailability SHALL be independently detectable by external parties | No Silent Failures |
| NFR11 | Read access SHALL remain available during cessation indefinitely | Cessation Mechanics |

### Durability & Reliability Requirements (NFR12-16)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR12 | Canonical events SHALL be stored with minimum 3 geographically distributed replicas | Disaster Recovery |
| NFR13 | Loss of any 2 replicas SHALL NOT result in data loss | Disaster Recovery |
| NFR14 | Backup integrity SHALL be verified daily | Backup Verification |
| NFR15 | Event store SHALL be append-only with no deletion capability | Witnessed Accountability |
| NFR16 | Event writes SHALL be atomic | Write Atomicity |

### Security Requirements (NFR17-22)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR17 | All agent outputs SHALL be cryptographically signed | Agent Verification |
| NFR18 | All Keeper actions SHALL be cryptographically signed | Override Verification |
| NFR19 | Hash chain SHALL use industry-standard cryptographic algorithms (SHA-256 minimum) | Fork Detection |
| NFR20 | Keeper keys SHALL be generated through witnessed ceremony | Keeper Authentication |
| NFR21 | Key rotation SHALL occur annually with 30-day transition window | Key Lifecycle |
| NFR22 | Witness selection randomness SHALL include external entropy source | Collusion Prevention |

### Scalability Requirements (NFR23-26)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR23 | System SHALL support 50+ deliberation events/week at MVP | Event Generation |
| NFR24 | System SHALL scale to 1000+ events/day with documented SLA tier change | Propagation SLA |
| NFR25 | Historical event store SHALL support 1M+ events without query degradation | Long-term Viability |
| NFR26 | Verification toolkit SHALL work offline against exported bundles of any size | External Auditor Journey |

### Observability Requirements (NFR27-30)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR27 | Operational metrics (uptime, latency, errors) SHALL be continuously monitored | Operational Observability |
| NFR28 | Operational metrics SHALL NOT enter constitutional event store | Operational-Constitutional Firewall |
| NFR29 | All anti-success conditions SHALL trigger alerts within 1 hour of detection | Anti-Success Monitoring |
| NFR30 | Incident reports SHALL be generated for halt, fork, or >3 overrides/day | Incident Investigation |

### Compliance Requirements (NFR31-34)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR31 | Personal data SHALL be stored separately from constitutional events | GDPR Compatibility |
| NFR32 | Retention policy SHALL be published and immutable | Regulatory Transparency |
| NFR33 | System SHALL provide structured audit export in standard format | Regulatory Reporting |
| NFR34 | Third-party attestation interface SHALL be available | External Audit |

### Operational Requirements (NFR35-38)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR35 | System startup SHALL complete verification checklist before operation | Pre-Operational Verification |
| NFR36 | Partition detection SHALL occur within 2 minutes | Partition Handling |
| NFR37 | Checkpoint anchors SHALL be created minimum weekly | Light Verification |
| NFR38 | Schema documentation SHALL have same availability as event store | External Auditor Journey |

### Constitutional Constraint NFRs (NFR39-42)

| NFR ID | Requirement | Basis |
|--------|-------------|-------|
| NFR39 | No configuration SHALL allow thresholds below constitutional floors | Threshold Enforcement |
| NFR40 | No event type for cessation reversal SHALL exist in schema | Cessation Irreversibility |
| NFR41 | Fork recovery waiting period SHALL be minimum 48 hours | Fork Recovery Cost |
| NFR42 | Keeper count SHALL never fall below 3 without halt | Recovery Quorum |

---

### Pre-mortem Additions: Operational Failure Prevention (NFR43-66)

**Controversy Cascade (NFR43-45)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR43 | Under extreme load (>50× baseline), prioritize recent events over historical queries; degradation visible and logged | Load shedding MUST NOT drop/delay canonical event recording—only observer query paths may degrade |
| NFR44 | Query queue depth bounded; requests beyond limit receive immediate backpressure response | |
| NFR45 | Detect controversy patterns and pre-scale when possible | Pre-scaling is best-effort; failure is not constitutional violation |

**Silent Clock Drift (NFR46-48)**

| NFR ID | Requirement |
|--------|-------------|
| NFR46 | Alert when time authorities disagree by >1 second; events during disagreement flagged |
| NFR47 | Maximum 500ms clock skew; beyond triggers health alert |
| NFR48 | Continue with remaining authorities if one fails; log degraded time attestation |

**Resource Exhaustion (NFR49-51)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR49 | Alert at 70% and 90% storage capacity | |
| NFR50 | Project exhaustion date; <90 days triggers planning alert | |
| NFR51 | At 95%, halt new deliberations until capacity expanded | Halt affects deliberation initiation only; integrity events MUST continue |

**Deployment Regression (NFR52-54)**

| NFR ID | Requirement |
|--------|-------------|
| NFR52 | Execute constitutional property verification suite before traffic routing |
| NFR53 | Support rollback within 5 minutes; authority defined |
| NFR54 | CI/CD tests all 6 innovation claims; failure blocks deployment |

**Dependency Cascade (NFR55-57)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR55 | Health-check external dependencies every 60 seconds | |
| NFR56 | Immediate alert on failure; >5 minutes triggers incident | |
| NFR57 | Use secondary entropy with logged degradation | If all entropy fails, witness selection halts rather than using weak randomness |

**Backup Corruption (NFR58-60)**

| NFR ID | Requirement |
|--------|-------------|
| NFR58 | Monthly restore test to functional state with query execution |
| NFR59 | Monitor backup storage health independently from verification |
| NFR60 | Each geographic replica verifies backup independently |

**Monitoring Blind Spot (NFR61-63)**

| NFR ID | Requirement |
|--------|-------------|
| NFR61 | Monitoring heartbeat every 5 minutes; missing triggers independent alert |
| NFR62 | Critical alerts require delivery confirmation; unconfirmed escalates at 15 minutes |
| NFR63 | Monitoring infrastructure operationally independent; minimize shared-fate |

**Configuration Drift (NFR64-66)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR64 | All config changes trigger alert to constitutional reviewer | |
| NFR65 | Quarterly audit against baseline; deviations require justification | |
| NFR66 | >5 changes in 24 hours triggers review hold | Emergency changes may proceed with justification logged before execution |

---

### First Principles Additions: Quality Primitives (NFR67-86)

**Staleness Detection (NFR67-68)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR67 | Queries include timestamp of most recent event; observers detect staleness | |
| NFR68 | Maximum 60 seconds cache staleness | Cache must prove it is behind by ≤60s; otherwise flag with last sequence number |

**Replica Lag Detection (NFR69-70)**

| NFR ID | Requirement |
|--------|-------------|
| NFR69 | Monitor lag between primary and replicas; >60 seconds triggers alert |
| NFR70 | Disclose which replica served response and its current lag |

**Causality Preservation (NFR71-72)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR71 | Events referencing others have timestamps >= referenced event | Sequence numbers are primary ordering; timestamps supplementary |
| NFR72 | Causality violations logged as integrity attack | |

**Graceful Shutdown (NFR73-75)**

| NFR ID | Requirement |
|--------|-------------|
| NFR73 | Complete in-flight writes, flush queues, log shutdown event |
| NFR74 | Minimum 30 seconds grace period; forced termination logs incomplete |
| NFR75 | Verify and repair partial state on startup after incomplete shutdown |

**False Positive Tracking (NFR76-77)**

| NFR ID | Requirement |
|--------|-------------|
| NFR76 | Track alert acknowledgment outcomes (confirmed, false positive, inconclusive) |
| NFR77 | >30% false positive rate over 30 days triggers threshold review |

**Algorithm Agility (NFR78-80)**

| NFR ID | Requirement |
|--------|-------------|
| NFR78 | Support algorithm migration with dual-verification period |
| NFR79 | Alert 12 months before algorithm end-of-life |
| NFR80 | Migration is a supported operation; no single algorithm dependency |

**Cost & Resource Quotas (NFR81-83)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR81 | Monitor and report operational costs monthly | |
| NFR82 | >50% cost increase triggers financial review alert | |
| NFR83 | Components have defined resource limits; exceed triggers throttling | Quotas never drop canonical events; pause deliberation instead |

**Upgrade Path (NFR84-86)**

| NFR ID | Requirement |
|--------|-------------|
| NFR84 | Define support windows; end-of-support triggers upgrade requirement |
| NFR85 | Test upgrades against prior 2 versions; breaking changes require migration docs |
| NFR86 | Support rollback for minimum 7 days after deployment |

---

### Critical Perspective Additions: Expert Challenges (NFR87-104)

**SRE: SLO Framework (NFR87-89)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR87 | Availability measured as (successful/total requests) over rolling 30-day windows; methodology published | |
| NFR88 | Track error budget; when exhausted, feature deployments pause | |
| NFR89 | SLO breaches disclosed within 24 hours with root cause | SLOs measure operational health only; breaches do NOT invalidate constitutional events |

**Security: Key Disaster Recovery (NFR90-92)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR90 | Encrypted key backups in separate locations; restoration tested quarterly | |
| NFR91 | Key loss recovery procedure defined; logged as constitutional event | Recovery restores future signing only; MUST NOT alter historical events |
| NFR92 | Production signing keys in HSM or tamper-resistant storage | |

**Chaos Engineer: Failure Testing (NFR93-95)**

| NFR ID | Requirement |
|--------|-------------|
| NFR93 | Quarterly chaos testing with documented results |
| NFR94 | Detect gray failures (>3× latency for >5 minutes); treat as failures |
| NFR95 | Circuit breakers between components; cascade triggers isolation |

**Network: Resilience (NFR96-98)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR96 | Tolerate up to 5% packet loss and 100ms jitter without SLA degradation | |
| NFR97 | Critical paths don't depend on external DNS | |
| NFR98 | Detect internal partitions within 30 seconds | If resilience fails, halt loudly rather than degrade silently |

**Capacity: Growth Modeling (NFR99-101)**

| NFR ID | Requirement |
|--------|-------------|
| NFR99 | Maintain 30-day capacity runway minimum |
| NFR100 | Track growth weekly; >25% week-over-week triggers review |
| NFR101 | Capacity expansion executable within 48 hours |

**Incident: Management Process (NFR102-104)**

| NFR ID | Requirement | Constraint |
|--------|-------------|------------|
| NFR102 | Define severity levels (Critical/High/Medium/Low) with response targets | |
| NFR103 | Any Keeper or operator can declare incidents; logged immediately | |
| NFR104 | Communication channels, escalation paths, roles defined; tested quarterly | Coordination manages communication, not constitutional interpretation |

---

### Non-Functional Requirements Summary

**Total: 104 Non-Functional Requirements**

| Cluster | NFR Range | Count | Source |
|---------|-----------|-------|--------|
| Performance | NFR1-6 | 6 | Core |
| Availability | NFR7-11 | 5 | Core |
| Durability & Reliability | NFR12-16 | 5 | Core |
| Security | NFR17-22 | 6 | Core |
| Scalability | NFR23-26 | 4 | Core |
| Observability | NFR27-30 | 4 | Core |
| Compliance | NFR31-34 | 4 | Core |
| Operational | NFR35-38 | 4 | Core |
| Constitutional Constraint | NFR39-42 | 4 | Core |
| Pre-mortem: Operational Failures | NFR43-66 | 24 | Advanced Elicitation |
| First Principles: Quality Primitives | NFR67-86 | 20 | Advanced Elicitation |
| Critical Perspective: Expert Challenges | NFR87-104 | 18 | Advanced Elicitation |

**Elicitation Methods Applied:**
1. Pre-mortem Analysis — 8 operational failure modes closed
2. First Principles Analysis — 8 quality primitive gaps closed
3. Challenge from Critical Perspective — 6 expert challenges addressed
