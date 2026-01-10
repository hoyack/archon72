# Story 8.9: Operational Runbooks (FR145-FR147)

Status: done

## Story

As a **system operator**,
I want runbooks for all operational procedures,
So that I can respond consistently to incidents.

## Acceptance Criteria

### AC1: Core Operational Runbooks Library
**Given** the runbook library
**When** I access it
**Then** runbooks exist for:
  - Startup procedures
  - Shutdown procedures
  - Scaling procedures
  - Backup procedures
  - Recovery procedures
**And** each runbook follows the standard template

### AC2: Epic-Specific Runbooks
**Given** the runbook requirements from all epics
**When** I examine the library
**Then** each epic's required runbook is included:
  - Epic 0: "Developer Environment Setup"
  - Epic 1: "Event Store Operations & Recovery"
  - Epic 2: "Agent Deliberation Monitoring"
  - Epic 3: "Halt & Fork Recovery Procedures"
  - Epic 4: "Observer API Operations"
  - Epic 5: "Keeper Operations & Key Rotation"
  - Epic 6: "Breach Detection & Escalation"
  - Epic 7: "Cessation Procedures & Post-Cessation Access"
  - Epic 8: "Operational Monitoring & Incident Response"
**And** Epic 9's "Emergence Audit Procedures" runbook is deferred (backlog)

### AC3: Runbook Structure Compliance
**Given** a runbook
**When** I examine it
**Then** it includes:
  - Trigger conditions (when to use)
  - Pre-requisites and preconditions
  - Step-by-step procedures
  - Verification checkpoints
  - Escalation paths
  - Rollback procedures (where applicable)
**And** it is version controlled with last-updated date

### AC4: Constitutional vs Operational Separation
**Given** the runbook library
**When** I review the procedures
**Then** constitutional operations are clearly distinguished from operational ones
**And** constitutional procedures reference governance requirements
**And** operational procedures do not bypass constitutional constraints

### AC5: Runbook Accessibility
**Given** an incident requiring a runbook
**When** an operator needs to access it
**Then** runbooks are available at `docs/operations/runbooks/`
**And** an index provides quick navigation
**And** runbooks are accessible during system outages (static markdown)

## Tasks / Subtasks

- [x] **Task 1: Create Runbook Template and Index** (AC: 3, 5)
  - [x] Create `docs/operations/runbooks/index.md`
    - [x] Table of all runbooks with links
    - [x] Quick reference section by scenario
    - [x] Emergency contacts placeholder
  - [x] Create `docs/operations/runbooks/TEMPLATE.md`
    - [x] Standard sections: Purpose, Prerequisites, Trigger Conditions, Procedure Steps, Verification, Escalation, Rollback, References
    - [x] Markdown checklists for procedure steps

- [x] **Task 2: Create Core Operational Runbooks** (AC: 1)
  - [x] Create `docs/operations/runbooks/startup.md`
    - [x] Service startup order (DB → Redis → API)
    - [x] Health check verification
    - [x] Pre-operational verification reference
  - [x] Create `docs/operations/runbooks/shutdown.md`
    - [x] Graceful shutdown procedure
    - [x] Queue draining steps
    - [x] Halt state considerations
  - [x] Create `docs/operations/runbooks/scaling.md`
    - [x] Horizontal scaling procedures
    - [x] Redis cluster considerations
    - [x] Load balancer updates
  - [x] Create `docs/operations/runbooks/backup.md`
    - [x] Database backup procedures
    - [x] Event store snapshot timing
    - [x] Redis persistence verification
  - [x] Create `docs/operations/runbooks/recovery.md`
    - [x] General recovery flowchart
    - [x] References to specific epic runbooks
    - [x] Disaster recovery scenarios

- [x] **Task 3: Create Epic 0-2 Runbooks** (AC: 2)
  - [x] Create `docs/operations/runbooks/epic-0-dev-environment.md`
    - [x] `make dev` setup
    - [x] HSM stub configuration
    - [x] Pre-commit hook setup
    - [x] Troubleshooting common issues
  - [x] Create `docs/operations/runbooks/epic-1-event-store.md`
    - [x] Hash chain verification procedures
    - [x] Event store recovery from backup
    - [x] Sequence gap investigation
    - [x] Witness attribution troubleshooting
  - [x] Create `docs/operations/runbooks/epic-2-deliberation.md`
    - [x] 72-agent monitoring procedures
    - [x] Heartbeat failure response
    - [x] Context bundle verification
    - [x] Dissent health monitoring

- [x] **Task 4: Create Epic 3-5 Runbooks** (AC: 2)
  - [x] Create `docs/operations/runbooks/epic-3-halt-fork.md`
    - [x] Halt signal handling
    - [x] Fork detection response
    - [x] Dual-channel halt verification
    - [x] 48-hour recovery waiting period
    - [x] Rollback to checkpoint procedures
  - [x] Create `docs/operations/runbooks/epic-4-observer.md`
    - [x] Observer API health monitoring
    - [x] 99.9% SLA tracking
    - [x] Push notification troubleshooting
    - [x] Verification toolkit support
  - [x] Create `docs/operations/runbooks/epic-5-keeper.md`
    - [x] Override logging verification
    - [x] Key rotation procedures
    - [x] Keeper availability checks
    - [x] Independence attestation procedures

- [x] **Task 5: Create Epic 6-8 Runbooks** (AC: 2)
  - [x] Create `docs/operations/runbooks/epic-6-breach.md`
    - [x] Breach declaration procedures
    - [x] 7-day escalation monitoring
    - [x] Witness selection verification
    - [x] Collusion detection response
  - [x] Create `docs/operations/runbooks/epic-7-cessation.md`
    - [x] Pre-cessation checklist
    - [x] Cessation execution procedures
    - [x] Post-cessation read-only access
    - [x] Final deliberation preservation
    - [x] Legal documentation requirements
  - [x] Create `docs/operations/runbooks/epic-8-monitoring.md`
    - [x] Operational metrics monitoring
    - [x] Constitutional health vs operational health
    - [x] Complexity budget tracking
    - [x] Failure mode response procedures
    - [x] Early warning handling

- [x] **Task 6: Create Incident Response Runbook** (AC: 2, 4)
  - [x] Create `docs/operations/runbooks/incident-response.md`
    - [x] Incident classification (Operational vs Constitutional)
    - [x] Severity levels and response times
    - [x] Communication templates
    - [x] Post-incident review process
    - [x] Reference to ADR-10 (Constitutional Health)

- [x] **Task 7: Update Existing Operations Documentation** (AC: 5)
  - [x] Update `docs/operations/external-monitoring-setup.md`
    - [x] Cross-reference to relevant runbooks
    - [x] Ensure alignment with Epic 8 monitoring
  - [x] Create `docs/operations/README.md`
    - [x] Overview of operations documentation
    - [x] Quick links to runbooks
    - [x] On-call contact information placeholder

- [x] **Task 8: Validation and Review** (AC: 1, 2, 3, 4, 5)
  - [x] Verify all 9 epic runbooks are created
  - [x] Verify all 5 core operational runbooks are created
  - [x] Verify all runbooks follow template structure
  - [x] Verify constitutional/operational separation is clear
  - [x] Verify runbook index is complete and navigable
  - [x] Run markdown linting on all runbooks

## Dev Notes

### Relevant Architecture Patterns and Constraints

**FR145-FR147 Requirements (Mission-Critical Capabilities):**
From the architecture and epics analysis:
- FR145: System SHALL provide operational runbooks for all critical procedures
- FR146: Runbooks SHALL include verification steps and escalation paths
- FR147: Constitutional and operational procedures SHALL be clearly distinguished

**Epic Runbook Requirements (from epics.md):**
| Epic | Runbook Title | Focus |
|------|--------------|-------|
| 0 | Developer Environment Setup | Dev onboarding, HSM stub, pre-commit |
| 1 | Event Store Operations & Recovery | Hash chain, witnesses, DR |
| 2 | Agent Deliberation Monitoring | 72 agents, heartbeats, context bundles |
| 3 | Halt & Fork Recovery Procedures | Dual-channel halt, 48-hour recovery |
| 4 | Observer API Operations | 99.9% SLA, verification toolkit |
| 5 | Keeper Operations & Key Rotation | Override logging, key ceremonies |
| 6 | Breach Detection & Escalation | 7-day escalation, witness randomness |
| 7 | Cessation Procedures & Post-Cessation Access | Irreversibility, read-only access |
| 8 | Operational Monitoring & Incident Response | Metrics separation, complexity budget |
| 9 | Emergence Audit Procedures | (Deferred to Epic 9) |

**ADR-10 (Constitutional Health + Operational Governance):**
Critical separation between:
- **Constitutional metrics**: breach count, override rate, dissent health, witness coverage
- **Operational metrics**: uptime, latency, errors, resource utilization

Runbooks must maintain this separation in all procedures.

### Source Tree Components to Touch

**Files to Create:**
```
docs/operations/README.md
docs/operations/runbooks/index.md
docs/operations/runbooks/TEMPLATE.md
docs/operations/runbooks/startup.md
docs/operations/runbooks/shutdown.md
docs/operations/runbooks/scaling.md
docs/operations/runbooks/backup.md
docs/operations/runbooks/recovery.md
docs/operations/runbooks/epic-0-dev-environment.md
docs/operations/runbooks/epic-1-event-store.md
docs/operations/runbooks/epic-2-deliberation.md
docs/operations/runbooks/epic-3-halt-fork.md
docs/operations/runbooks/epic-4-observer.md
docs/operations/runbooks/epic-5-keeper.md
docs/operations/runbooks/epic-6-breach.md
docs/operations/runbooks/epic-7-cessation.md
docs/operations/runbooks/epic-8-monitoring.md
docs/operations/runbooks/incident-response.md
```

**Files to Modify:**
```
docs/operations/external-monitoring-setup.md  # Add runbook cross-references
```

### Testing Standards Summary

This is a **documentation story** - no code tests required.

**Validation Criteria:**
- All runbooks exist and are non-empty
- All runbooks follow the TEMPLATE.md structure
- Index references all runbooks correctly
- Markdown linting passes (no broken links, valid formatting)
- Constitutional/operational distinction is explicit in each runbook

### Project Structure Notes

**Runbook Directory Structure:**
```
docs/
└── operations/
    ├── README.md                    # Operations overview
    ├── external-monitoring-setup.md # Existing file
    └── runbooks/
        ├── index.md                 # Navigation hub
        ├── TEMPLATE.md              # Standard structure
        ├── startup.md               # Core: Startup
        ├── shutdown.md              # Core: Shutdown
        ├── scaling.md               # Core: Scaling
        ├── backup.md                # Core: Backup
        ├── recovery.md              # Core: Recovery
        ├── epic-0-dev-environment.md
        ├── epic-1-event-store.md
        ├── epic-2-deliberation.md
        ├── epic-3-halt-fork.md
        ├── epic-4-observer.md
        ├── epic-5-keeper.md
        ├── epic-6-breach.md
        ├── epic-7-cessation.md
        ├── epic-8-monitoring.md
        └── incident-response.md
```

### Previous Story Intelligence (8-8: Pre-mortem Operational Failures Prevention)

**Learnings from Story 8-8:**
1. **Failure mode registry** - VAL-1 through VAL-5 and PV-001 through PV-003 are documented
2. **Early warning system** - Threshold-based alerts with recommended actions
3. **Constitutional event protection** - FR107 ensures constitutional events never shed
4. **Severity levels** - CRITICAL, HIGH, MEDIUM, LOW, INFO defined
5. **File structure** - Operations docs go in `docs/operations/`

**Runbooks should reference:**
- Early warning alerts from failure prevention service
- Load shedding decisions
- Query performance SLA (30 seconds for <10k events)
- Pattern violation detection

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
docs(story-8.9): Create operational runbooks library (FR145-FR147)
```

### Critical Implementation Notes

**RUNBOOK TEMPLATE STRUCTURE:**
```markdown
# [Runbook Title]

Last Updated: YYYY-MM-DD
Version: 1.0
Owner: [Team/Role]

## Purpose

[Brief description of when and why to use this runbook]

## Prerequisites

- [ ] Prerequisite 1
- [ ] Prerequisite 2

## Trigger Conditions

When to execute this runbook:
- Condition 1
- Condition 2

## Procedure

### Step 1: [Step Name]

- [ ] Action 1
- [ ] Action 2

**Verification:**
- Expected outcome: [description]
- Command to verify: `[command]`

### Step 2: [Step Name]
...

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| [condition] | [role] | [info] |

## Rollback

If procedure fails:
1. Step 1
2. Step 2

## References

- [Related documentation]
- [ADR references]
```

**CONSTITUTIONAL VS OPERATIONAL DISTINCTION:**

Each runbook must clearly label:
- 🔵 **OPERATIONAL** - Affects system performance/availability
- 🔴 **CONSTITUTIONAL** - Affects governance/integrity guarantees

Example:
```markdown
## Step 3: Verify System Health

### 🔵 Operational Check
- [ ] API responding to health endpoint
- [ ] Database connections healthy
- [ ] Redis connectivity verified

### 🔴 Constitutional Check
- [ ] Halt state is clear
- [ ] Hash chain integrity verified
- [ ] Witness attribution functional
```

**SEVERITY LEVEL REFERENCE:**

| Severity | Response | Runbook Examples |
|----------|----------|------------------|
| **CRITICAL** | Page immediately, halt system | Signature failure, halt signal |
| **HIGH** | Page immediately | Fork detected, breach declared |
| **MEDIUM** | Alert on-call, 15 min response | Heartbeat missed, witness pool low |
| **LOW** | Next business day | Override logged, capacity warning |
| **INFO** | No alert, log only | Routine operations |

### Dependencies

No code dependencies. Documentation-only story.

**Documentation Tools:**
- Markdown (standard)
- Mermaid (for flowcharts if needed)
- Git (version control)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic-8] - Runbook requirements
- [Source: _bmad-output/planning-artifacts/epics.md#FR145-FR147] - Mission-critical capabilities
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-10] - Constitutional Health separation
- [Source: _bmad-output/project-context.md#Alert-Severity-Levels] - Alert severity reference
- [Source: docs/operations/external-monitoring-setup.md] - Existing operations doc

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Documentation-only story

### Completion Notes List

1. Created comprehensive runbook library with 17 runbooks (4,245 lines total)
2. All 5 core operational runbooks created: startup, shutdown, scaling, backup, recovery
3. All 9 epic-specific runbooks created (Epic 0-8)
4. Incident response cross-cutting runbook created
5. Template and index created for navigation and consistency
6. Constitutional vs Operational distinction clearly marked in all runbooks
7. Updated external-monitoring-setup.md with runbook cross-references
8. Created docs/operations/README.md as navigation hub
9. All acceptance criteria (AC1-AC5) satisfied
10. FR145-FR147 (Mission-Critical Capabilities) fully implemented

### File List

**Created:**
- docs/operations/README.md
- docs/operations/runbooks/index.md
- docs/operations/runbooks/TEMPLATE.md
- docs/operations/runbooks/startup.md
- docs/operations/runbooks/shutdown.md
- docs/operations/runbooks/scaling.md
- docs/operations/runbooks/backup.md
- docs/operations/runbooks/recovery.md
- docs/operations/runbooks/epic-0-dev-environment.md
- docs/operations/runbooks/epic-1-event-store.md
- docs/operations/runbooks/epic-2-deliberation.md
- docs/operations/runbooks/epic-3-halt-fork.md
- docs/operations/runbooks/epic-4-observer.md
- docs/operations/runbooks/epic-5-keeper.md
- docs/operations/runbooks/epic-6-breach.md
- docs/operations/runbooks/epic-7-cessation.md
- docs/operations/runbooks/epic-8-monitoring.md
- docs/operations/runbooks/incident-response.md

**Modified:**
- docs/operations/external-monitoring-setup.md (added runbook cross-reference)

