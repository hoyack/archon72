# Archon 72 Governance Documentation

> **Archon 72 is a coordination system, not a control system.**

This documentation defines the governance architecture that enables human-in-the-loop execution while maintaining separation of powers across the 72 Archons.

## Core Principle

**Archons do not execute. AI agents do not execute. Earls do not execute.**

Execution happens in Clusters, which are:
- Human participants
- Supervised by humans
- Instrumented by the system
- Constrained by the plan

This keeps Archon 72 out of automation fantasy and out of liability traps.

---

## Documentation Index

### Architecture

| Document | Description |
|----------|-------------|
| [Aegis Network](./aegis-network.md) | What the network is, why it matters, operational model |
| [Cluster Schema](./cluster-schema.md) | Human execution unit schema and critical runtime rules |
| [Task Lifecycle](./task-lifecycle.md) | The 10 states a task moves through |
| [Enforcement Flow](./enforcement-flow.md) | Knight → Prince → King violation handling |
| [The Legislative Branch (Kings)](./legislative-branch.md) | Intent definition, Realms, Motions, WHAT vs HOW separation |
| [The Executive Branch (Presidents)](./executive-branch.md) | Planning HOW, Portfolios, Execution Plans, composite contributions |
| [The Administrative Branch (Dukes)](./administrative-branch.md) | Program coordination, Earl activation, capacity reality |
| [The Custodial Branch (Marquis)](./custodial-branch.md) | Meaning, initiation, memory, exit—non-governing stewardship |
| [The Judicial Branch (Princes)](./judicial-branch.md) | Legibility enforcement, panels, three axes of review |
| [Conclave Agenda Control](./conclave-agenda.md) | Constitutional mechanism preventing suppression by omission |
| [Legitimacy System](./legitimacy-system.md) | Banded state machine for procedural erosion visibility |
| [Capacity Governance](./capacity-governance.md) | Making scarcity visible and prioritization accountable |
| [Appeal & Cessation](./appeal-cessation.md) | Bounded disagreement, retry prevention, dignified shutdown |
| [Governance Glossary](./glossary.md) | Definitions for core governance terms |

### Contracts (Earl ↔ Cluster)

| Document | Description |
|----------|-------------|
| [Task Activation Request](./task-activation-request.md) | Earl → Cluster: Call for participation |
| [Task Result Artifact](./task-result-artifact.md) | Cluster → Earl: Deliverables and status |

### JSON Schemas

| Schema | Description |
|--------|-------------|
| [cluster-schema.json](./schemas/cluster-schema.json) | Aegis Cluster definition |
| [task-activation-request.json](./schemas/task-activation-request.json) | Task activation contract |
| [task-result-artifact.json](./schemas/task-result-artifact.json) | Result submission contract |
| [motion.json](./schemas/motion.json) | Legislative Motion (WHAT, not HOW) |
| [execution-plan.json](./schemas/execution-plan.json) | Execution Plan (HOW, preserving intent) |
| [execution-program.json](./schemas/execution-program.json) | Execution Program (coordinated work container) |
| [custodial-office.json](./schemas/custodial-office.json) | Custodial Office (meaning, initiation, memory, exit) |
| [judicial-finding.json](./schemas/judicial-finding.json) | Judicial Finding from Prince panel |
| [judicial-panel.json](./schemas/judicial-panel.json) | Prince panel composition and process |
| [conclave-agenda.json](./schemas/conclave-agenda.json) | Conclave agenda with quotas and bands |
| [legitimacy-ledger.json](./schemas/legitimacy-ledger.json) | Append-only legitimacy state and events |
| [capacity-ledger.json](./schemas/capacity-ledger.json) | Capacity declarations, claims, and deferrals |
| [appeal-cessation.json](./schemas/appeal-cessation.json) | Appeal requests, outcomes, cessation, final records |

### Examples

| Example | Description |
|---------|-------------|
| [cluster-17-example.json](./examples/cluster-17-example.json) | Research & Analysis cluster |
| [task-activation-example.json](./examples/task-activation-example.json) | Sample activation request |
| [task-result-example.json](./examples/task-result-example.json) | Sample result artifact |
| [motion-example.json](./examples/motion-example.json) | Single-realm policy motion (King Bael) |
| [cross-realm-motion-example.json](./examples/cross-realm-motion-example.json) | Cross-realm ethical motion with co-sponsors |
| [execution-plan-example.json](./examples/execution-plan-example.json) | Execution plan with portfolio contributions |
| [composite-execution-plan-example.json](./examples/composite-execution-plan-example.json) | Multi-portfolio plan with blocker resolution |
| [execution-program-example.json](./examples/execution-program-example.json) | Program with Earl assignments and cluster participation |
| [complex-execution-program-example.json](./examples/complex-execution-program-example.json) | Program with cluster refusal, blocker, and escalation |
| [marquis-office-mapping-example.json](./examples/marquis-office-mapping-example.json) | Canonical Marquis → Custodial Office assignments |
| [custodial-interaction-example.json](./examples/custodial-interaction-example.json) | Initiation, ritual, exit, and violation detection |
| [judicial-finding-example.json](./examples/judicial-finding-example.json) | Sample judicial finding with dissent |
| [conclave-agenda-example.json](./examples/conclave-agenda-example.json) | Sample agenda with quotas and deferrals |
| [legitimacy-ledger-example.json](./examples/legitimacy-ledger-example.json) | Sample ledger with band transition |
| [capacity-ledger-example.json](./examples/capacity-ledger-example.json) | Sample capacity state with deferrals |
| [appeal-request-example.json](./examples/appeal-request-example.json) | Sample appeal with revised plan basis |
| [cessation-declaration-example.json](./examples/cessation-declaration-example.json) | Sample cessation with dissent preserved |

---

## Quick Reference

### Who Does What

| Role | Authority | Prohibition |
|------|-----------|-------------|
| **King** | Defines intent (WHAT) | Cannot define execution (HOW), act outside Realm |
| **President** | Creates plans | Cannot execute |
| **Duke** | Manages programs | Cannot execute |
| **Earl** | Activates tasks | Cannot compel, change scope, bypass consent |
| **Cluster** | Executes work | Cannot be commanded (only activated) |
| **Knight** | Witnesses violations | Cannot propose, debate, judge, enforce |
| **Prince** | Enforces legibility (panels only) | Cannot witness, execute, prescribe outcomes, punish |
| **Marquis** | Stewards meaning, initiation, memory, exit | Cannot govern, influence votes, promise outcomes |

### The Golden Rules

1. **No silent assignment** - Tasks require explicit acceptance
2. **Refusal is penalty-free** - Declining cannot reduce cluster standing
3. **Steward is accountable** - All decisions are logged
4. **Earl cannot bypass steward** - No routing around refusal
5. **Failure is allowed; silence is not** - Must report status
6. **Princes enforce legibility, not outcomes** - They cannot prescribe what should happen
7. **Panels, not individuals** - Single Prince never decides alone
8. **No suppression by omission** - Agenda must surface hard truths (Band 0 cannot be skipped)
9. **Failure is allowed; denial is not** - System may operate while strained, but must acknowledge it
10. **Scarcity must be visible** - Capacity constraints and deferrals leave fingerprints
11. **One appeal, then done** - Persistence is not rewarded; outcomes become final
12. **Stopping is honorable** - Cessation is a governance outcome, not a hidden collapse
13. **Kings define WHAT, not HOW** - Intent only; execution is Executive branch domain
14. **No King outside their Realm** - Domain boundaries are absolute
15. **King authority ends at ratification** - Post-ratification, Kings have no execution authority
16. **Advisory must be acknowledged** - Kings may disagree but may not ignore Marquis input
17. **Presidents plan HOW, not WHAT** - Transform intent without altering meaning
18. **All portfolios must respond** - Contribution or No-Action Attestation required; silence is invalid
19. **President authority ends at handoff** - No supervision of execution
20. **Critical blockers must escalate** - Cannot self-resolve; must go to Conclave
21. **Dukes coordinate, not command** - Reality visibility, not obedience
22. **Earls activate, not compel** - Request, not command; refusal is valid
23. **Programs are descriptive, not prescriptive** - Track reality, don't force it
24. **A smoothly running administration is suspicious** - Visible halts are healthy
25. **Custodians steward, not govern** - Meaning and memory, not decisions
26. **Exit is always available** - No locked doors, no shame
27. **This system is not care** - No therapy, no absolution, no salvation
28. **A custodial branch that creates devotion is corrupt** - No gurus, no mysteries

### Task State Machine

```
authorized → activated → routed → accepted → in_progress → reported → aggregated → completed
                                     ↓                          ↓
                                 declined                   quarantined → nullified
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.9.0 | 2026-01-16 | Added Custodial Branch documentation, 14 Marquis, Offices, initiation/exit protocols |
| 1.8.0 | 2026-01-16 | Added Administrative Branch documentation, 23 Dukes, 6 Earls, Execution Programs |
| 1.7.0 | 2026-01-16 | Added Executive Branch documentation, 11 Presidents, Portfolios, Execution Plans |
| 1.6.0 | 2026-01-16 | Added Legislative Branch documentation, 9 Kings, Realms, Motions, WHAT/HOW separation |
| 1.5.0 | 2026-01-16 | Added Appeal & Cessation documentation, exit logic, final records |
| 1.4.0 | 2026-01-16 | Added Capacity Governance documentation, capacity ledger, deferral tracking |
| 1.3.0 | 2026-01-16 | Added Legitimacy System documentation, banded decay model, append-only ledger |
| 1.2.0 | 2026-01-16 | Added Conclave Agenda Control documentation, priority bands, realm quotas |
| 1.1.0 | 2026-01-16 | Added Judicial Branch documentation, panel schemas |
| 1.0.0 | 2026-01-16 | Initial governance documentation |

---

## Related Documents

- [Archon Governance Schema](../archons-base.json) - The 72 Archon definitions
- [Rank Matrix](../../config/permissions/rank-matrix.yaml) - Branch permissions and prohibitions
- [PRD: Governance Requirements](../_bmad-output/planning-artifacts/gov-requirements.md) - Original requirements
