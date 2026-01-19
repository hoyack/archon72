# Story 0.4: Job Queue Infrastructure (Deadline Monitoring)

Status: done

## Story

As a **developer**,
I want a job queue infrastructure for scheduling deadline monitoring jobs,
So that referral timeouts and deliberation timeouts can fire reliably.

## Acceptance Criteria

### AC1: Job Queue Tables (Migration 014)

**Given** no existing job queue tables
**When** I run the migration
**Then** the following tables are created:
  - `scheduled_jobs`:
    - `id` (UUID PRIMARY KEY)
    - `job_type` (TEXT NOT NULL) - e.g., 'referral_timeout', 'deliberation_timeout'
    - `payload` (JSONB NOT NULL) - job-specific data (petition_id, etc.)
    - `scheduled_for` (TIMESTAMPTZ NOT NULL) - when to execute
    - `created_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW())
    - `attempts` (INT NOT NULL DEFAULT 0)
    - `last_attempt_at` (TIMESTAMPTZ)
    - `status` (TEXT NOT NULL DEFAULT 'pending') - pending, processing, completed, failed
  - `dead_letter_queue`:
    - `id` (UUID PRIMARY KEY)
    - `original_job_id` (UUID NOT NULL)
    - `job_type` (TEXT NOT NULL)
    - `payload` (JSONB NOT NULL)
    - `failure_reason` (TEXT NOT NULL)
    - `failed_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW())
    - `attempts` (INT NOT NULL)
**And** appropriate indexes exist for efficient job polling:
  - `idx_scheduled_jobs_status_scheduled` on (status, scheduled_for)
  - `idx_dead_letter_created` on (failed_at)

### AC2: Job Scheduler Port (Protocol)

**Given** the hexagonal architecture pattern
**When** I create the job scheduler abstraction
**Then** a `JobSchedulerProtocol` exists in `src/application/ports/` with:
  - `schedule(job_type: str, payload: dict, run_at: datetime) -> UUID`
  - `cancel(job_id: UUID) -> bool`
  - `get_pending_jobs(limit: int) -> list[ScheduledJob]`
  - `mark_completed(job_id: UUID) -> None`
  - `mark_failed(job_id: UUID, reason: str) -> None`
**And** the protocol follows existing port patterns (CT-11, CT-12)

### AC3: Job Scheduler Stub (Testing)

**Given** the `JobSchedulerProtocol`
**When** I create a test stub
**Then** `JobSchedulerStub` exists in `src/infrastructure/stubs/`
**And** it stores jobs in-memory for unit testing
**And** it tracks scheduled/cancelled/completed jobs

### AC4: Postgres Job Scheduler Adapter

**Given** the `JobSchedulerProtocol`
**When** I create the Postgres implementation
**Then** `PostgresJobScheduler` exists in `src/infrastructure/adapters/scheduling/`
**And** it implements all protocol methods with Supabase/Postgres
**And** it uses optimistic locking (SELECT FOR UPDATE SKIP LOCKED) for job claiming
**And** it respects halt state (no new jobs scheduled during halt)

### AC5: Job Worker Service

**Given** the scheduler infrastructure
**When** I create the worker service
**Then** a `JobWorkerService` exists in `src/application/services/`
**And** it polls for due jobs every 10 seconds
**And** it processes jobs with at-least-once delivery semantics
**And** it moves failed jobs to dead-letter queue after 3 retries
**And** it emits heartbeat metrics on each poll cycle
**And** it checks halt state before processing each job

### AC6: Dead-Letter Alerting (HC-6)

**Given** the dead-letter queue
**When** jobs fail and are moved to the DLQ
**Then** an alert is triggered when dead_letter_queue depth > 0
**And** the alert is logged with structured logging (structlog)
**And** the alert includes: job_id, job_type, failure_reason, attempt_count

### AC7: Integration Tests

**Given** the job queue infrastructure
**When** I run integration tests
**Then** tests verify:
  - Job scheduling and retrieval
  - Job cancellation
  - Job completion marking
  - Failed job retry logic (3 attempts)
  - Dead-letter queue insertion
  - Worker poll cycle execution
  - Halt state respect (no processing during halt)

### AC8: Unit Tests

**Given** the job queue components
**When** I run unit tests
**Then** tests verify:
  - JobSchedulerProtocol method signatures
  - JobSchedulerStub behavior
  - Job domain model validation
  - Worker service logic (with mocked scheduler)

## Tasks / Subtasks

- [ ] Task 1: Create Job Queue Migration (AC: 1)
  - [ ] 1.1 Create `migrations/014_create_job_queue_tables.sql`
  - [ ] 1.2 Create `scheduled_jobs` table with all columns
  - [ ] 1.3 Create `dead_letter_queue` table with all columns
  - [ ] 1.4 Create performance indexes
  - [ ] 1.5 Add COMMENT documentation

- [ ] Task 2: Create ScheduledJob Domain Model (AC: 2)
  - [ ] 2.1 Create `src/domain/models/scheduled_job.py`
  - [ ] 2.2 Define `ScheduledJob` dataclass (frozen, eq=True)
  - [ ] 2.3 Define `JobStatus` enum (PENDING, PROCESSING, COMPLETED, FAILED)
  - [ ] 2.4 Define `DeadLetterJob` dataclass
  - [ ] 2.5 Export from `src/domain/models/__init__.py`

- [ ] Task 3: Create JobSchedulerProtocol (AC: 2)
  - [ ] 3.1 Create `src/application/ports/job_scheduler.py`
  - [ ] 3.2 Define `JobSchedulerProtocol` with all methods
  - [ ] 3.3 Add Constitutional Constraints docstrings (CT-11, CT-12, HP-1)
  - [ ] 3.4 Export from `src/application/ports/__init__.py`

- [ ] Task 4: Create JobSchedulerStub (AC: 3)
  - [ ] 4.1 Create `src/infrastructure/stubs/job_scheduler_stub.py`
  - [ ] 4.2 Implement in-memory job storage
  - [ ] 4.3 Implement all protocol methods
  - [ ] 4.4 Export from `src/infrastructure/stubs/__init__.py`

- [ ] Task 5: Create PostgresJobScheduler Adapter (AC: 4)
  - [ ] 5.1 Create `src/infrastructure/adapters/scheduling/__init__.py`
  - [ ] 5.2 Create `src/infrastructure/adapters/scheduling/postgres_job_scheduler.py`
  - [ ] 5.3 Implement `schedule()` with INSERT
  - [ ] 5.4 Implement `cancel()` with DELETE
  - [ ] 5.5 Implement `get_pending_jobs()` with SELECT FOR UPDATE SKIP LOCKED
  - [ ] 5.6 Implement `mark_completed()` with UPDATE
  - [ ] 5.7 Implement `mark_failed()` with retry logic and DLQ insertion
  - [ ] 5.8 Add halt state checking via HaltCheckerProtocol
  - [ ] 5.9 Export from `src/infrastructure/adapters/__init__.py`

- [ ] Task 6: Create JobWorkerService (AC: 5)
  - [ ] 6.1 Create `src/application/services/job_worker_service.py`
  - [ ] 6.2 Implement poll loop (10 second interval)
  - [ ] 6.3 Implement job dispatcher by job_type
  - [ ] 6.4 Implement heartbeat metric emission
  - [ ] 6.5 Implement halt state check per cycle
  - [ ] 6.6 Add graceful shutdown handling

- [ ] Task 7: Create Dead-Letter Alerting (AC: 6)
  - [ ] 7.1 Add DLQ depth check to PostgresJobScheduler
  - [ ] 7.2 Implement structured alert logging
  - [ ] 7.3 Add DLQ metrics (count, oldest job age)

- [ ] Task 8: Create Unit Tests (AC: 8)
  - [ ] 8.1 Create `tests/unit/domain/models/test_scheduled_job.py`
  - [ ] 8.2 Create `tests/unit/application/ports/test_job_scheduler.py`
  - [ ] 8.3 Create `tests/unit/infrastructure/stubs/test_job_scheduler_stub.py`
  - [ ] 8.4 Create `tests/unit/application/services/test_job_worker_service.py`

- [ ] Task 9: Create Integration Tests (AC: 7)
  - [ ] 9.1 Create `tests/integration/test_job_queue_infrastructure.py`
  - [ ] 9.2 Test job scheduling and retrieval
  - [ ] 9.3 Test job cancellation
  - [ ] 9.4 Test retry and DLQ logic
  - [ ] 9.5 Test worker poll cycle
  - [ ] 9.6 Test halt state behavior

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [ ] N/A - no documentation impact (explain why)

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → All job failures must be logged and alerted
- **CT-12:** Witnessing creates accountability → Job execution must be auditable
- **CT-13:** Reads during halt are permitted → Worker can query jobs but not process new ones

**PRD Requirements:**
- **HP-1:** Hidden Prerequisite - Job Queue for reliable deadline execution
- **HC-6:** Hardening Control - Dead-letter alerting for failed jobs
- **NFR-7.5:** Timeout job monitoring - Heartbeat on scheduler
- **FM-7.1:** Failure Mode - Timeout never fires → Persistent job queue prevents this

**Failure Modes Addressed:**
- FM-7.1: Timeout never fires → This story provides persistent job queue
- FM-4.5: Referral timeout fails → Jobs survive process restart (NFR-4.4)

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Domain | `src/domain/models/scheduled_job.py` | Job domain model |
| Port | `src/application/ports/job_scheduler.py` | Scheduler protocol |
| Service | `src/application/services/job_worker_service.py` | Worker service |
| Stub | `src/infrastructure/stubs/job_scheduler_stub.py` | Test implementation |
| Adapter | `src/infrastructure/adapters/scheduling/postgres_job_scheduler.py` | Postgres impl |
| Migration | `migrations/014_create_job_queue_tables.sql` | Job queue tables |

**Import Rules (CRITICAL):**
```python
# ALLOWED in adapters/
from src.domain.models.scheduled_job import ScheduledJob, JobStatus, DeadLetterJob
from src.application.ports.job_scheduler import JobSchedulerProtocol
from src.application.ports.halt_checker import HaltCheckerProtocol

# FORBIDDEN - Will fail pre-commit hook
from src.api import ...  # VIOLATION!
```

### Job Types for Petition System

The job queue will support these job types (defined later in other stories):
- `referral_timeout` - Knight referral deadline (FR-4.5, Story Epic 4)
- `deliberation_timeout` - Three Fates deliberation deadline (NFR-10.2, Story Epic 2B)
- `escalation_check` - Periodic co-signer count check (Story Epic 5)

For this story, the infrastructure is generic - specific job handlers are implemented in later stories.

### Polling Strategy (10 Second Interval)

From PRD requirements:
- Worker polls for due jobs every 10 seconds
- Uses `SELECT FOR UPDATE SKIP LOCKED` to prevent double-processing
- Multiple workers can run concurrently without conflicts

```sql
-- Job claim query pattern
SELECT * FROM scheduled_jobs
WHERE status = 'pending'
  AND scheduled_for <= NOW()
ORDER BY scheduled_for ASC
LIMIT 10
FOR UPDATE SKIP LOCKED;
```

### Retry Logic (3 Attempts, then DLQ)

1. First attempt: Immediate
2. Second attempt: +30 seconds
3. Third attempt: +60 seconds
4. After 3 failures: Move to dead_letter_queue, emit alert

### Halt State Integration

The job worker MUST respect halt state (ADR-3):
- Before each poll cycle: Check halt state
- If halted: Log "Job worker paused due to system halt" and skip processing
- Heartbeat continues even during halt (to show worker is alive)

### Previous Story Learnings (Story 0.3)

From the cessation petition migration story:
- Follow frozen dataclass pattern with `eq=True` for domain models
- Comprehensive docstrings with FR references
- Protocol classes with clear method signatures
- Stub implementations for unit testing
- Export from `__init__.py` files
- Test both unit and integration levels

### Project Structure Notes

**Existing Patterns to Follow:**
- Ports in `src/application/ports/` with `Protocol` classes
- Stubs in `src/infrastructure/stubs/` with `*Stub` suffix
- Adapters in `src/infrastructure/adapters/{category}/` with descriptive names
- Migrations in `migrations/` with numbered prefix (next is 014)
- Tests mirror source structure

**New Directory:**
- `src/infrastructure/adapters/scheduling/` - New adapter category for job scheduling

### References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 0.4]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#HP-1, HC-6, NFR-7.5, FM-7.1]
- [Source: _bmad-output/planning-artifacts/architecture.md#workers/]
- [Source: _bmad-output/implementation-artifacts/stories/petition-0-3-story-7-2-cessation-petition-migration.md]
- [Source: src/application/ports/petition_submission_repository.py] - Port pattern example
- [Source: src/infrastructure/stubs/petition_submission_repository_stub.py] - Stub pattern example
- [Source: migrations/012_create_petition_submissions.sql] - Migration pattern example

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Story creation phase

### Completion Notes List

*To be filled during implementation*

### File List

**To Create:**
- `migrations/014_create_job_queue_tables.sql`
- `src/domain/models/scheduled_job.py`
- `src/application/ports/job_scheduler.py`
- `src/application/services/job_worker_service.py`
- `src/infrastructure/stubs/job_scheduler_stub.py`
- `src/infrastructure/adapters/scheduling/__init__.py`
- `src/infrastructure/adapters/scheduling/postgres_job_scheduler.py`
- `tests/unit/domain/models/test_scheduled_job.py`
- `tests/unit/application/ports/test_job_scheduler.py`
- `tests/unit/infrastructure/stubs/test_job_scheduler_stub.py`
- `tests/unit/application/services/test_job_worker_service.py`
- `tests/integration/test_job_queue_infrastructure.py`

**To Modify:**
- `src/domain/models/__init__.py` - Export new domain models
- `src/application/ports/__init__.py` - Export new port
- `src/infrastructure/stubs/__init__.py` - Export new stub
- `src/infrastructure/adapters/__init__.py` - Export new adapter

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-19 | Story file created | Claude Opus 4.5 |

---

## Senior Developer Review (AI)

**Review Date:** Pending
**Reviewer:** Pending

### Checklist

- [ ] Code follows existing patterns (port/adapter, protocol classes)
- [ ] Migration follows existing conventions
- [ ] Job scheduling uses optimistic locking
- [ ] Dead-letter alerting implemented
- [ ] Halt state respected
- [ ] Retry logic correct (3 attempts)
- [ ] Tests cover all acceptance criteria

### Notes

*To be filled during review*
