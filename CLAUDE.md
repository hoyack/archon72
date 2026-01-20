# Archon 72 Conclave Backend - Project Context

## Current Focus: Petition System Implementation

**Priority**: Complete all Petition System stories before moving to other work.

When `/workflow-status` is invoked, check `_bmad-output/planning-artifacts/bmm-workflow-status.yaml` and focus on the `petition_system` section.

### Petition System Progress (10 Epics, 71 Stories)

| Epic | Name | Priority | Status |
|------|------|----------|--------|
| 0 | Foundation & Migration | P0 | DONE (7/7) |
| 1 | Petition Intake & State Machine | P0 | DONE (8/8) |
| 2A | Core Deliberation Protocol | P0-CRITICAL | DONE (8/8) |
| 2B | Deliberation Edge Cases & Guarantees | P0 | BACKLOG (0/8) |
| 3 | Acknowledgment Execution | P1 | BACKLOG (0/6) |
| 4 | Knight Referral Workflow | P1 | BACKLOG (0/7) |
| 5 | Co-signing & Auto-Escalation | P0 | BACKLOG (0/8) |
| 6 | King Escalation & Adoption Bridge | P0 | BACKLOG (0/6) |
| 7 | Observer Engagement | P2 | BACKLOG (0/6) |
| 8 | Legitimacy Metrics & Governance | P1 | BACKLOG (0/7) |

**Current**: 23/71 stories complete (32%)
**Next Epic**: 2B - Deliberation Edge Cases & Guarantees
**Next Story**: petition-2b-1-dissent-recording-service

### Workflow Commands

- `/workflow-status` - Check Petition System progress, identify next story
- `/bmad:bmm:workflows:create-story` - Create next story from backlog
- `/bmad:bmm:workflows:dev-story` - Implement a ready-for-dev story

### Key Architecture

- **Tech Stack**: Python 3.11+, FastAPI, Supabase (PostgreSQL 16), Redis, SQLAlchemy 2.0, CrewAI
- **Pattern**: Hexagonal/Clean Architecture (`src/api`, `src/application`, `src/domain`, `src/infrastructure`)
- **Three Fates**: Marquis-rank Archon AI agents deliberate via CrewAI multi-agent orchestration
- **Dispositions**: ACKNOWLEDGE, REFER (to Knight), ESCALATE (to King)

### Source Documents

- PRD: `_bmad-output/planning-artifacts/petition-system-prd.md` (70 FRs, 53 NFRs)
- Epics: `_bmad-output/planning-artifacts/petition-system-epics.md`
- Architecture: `_bmad-output/planning-artifacts/architecture.md`
- Sprint Status: `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Completed Systems (Do Not Revisit)

- Consent-Gov System: 10 epics, 35 stories - COMPLETE
- Core Governance: 11 epics, 83 stories - COMPLETE
