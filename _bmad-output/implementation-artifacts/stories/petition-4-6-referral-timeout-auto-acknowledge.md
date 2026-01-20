# Story 4.6: Referral Timeout Auto-Acknowledge

## Story

**As a** system
**I want to** auto-ACKNOWLEDGE petitions when referral times out
**So that** no petition is indefinitely stuck in referral

## Status

| Field | Value |
|-------|-------|
| Story ID | petition-4-6-referral-timeout-auto-acknowledge |
| Epic | Petition Epic 4: Knight Referral Workflow |
| Status | done |
| Priority | P0 |
| Started | 2026-01-20 |
| Completed | 2026-01-20 |

## Requirements Traceability

| Requirement | Description | Priority |
|-------------|-------------|----------|
| FR-4.5 | System SHALL auto-ACKNOWLEDGE on referral timeout (reason: EXPIRED) | P0 |
| NFR-3.4 | Referral timeout reliability: 100% timeouts fire | CRITICAL |
| NFR-4.4 | Referral deadline persistence: Survives scheduler restart | CRITICAL |
| CT-12 | Every action that affects an Archon must be witnessed | CRITICAL |

## Acceptance Criteria

### AC1: Timeout Job Triggers Expiration
**Given** a referral deadline has passed
**When** the timeout job fires
**Then** the referral status transitions to EXPIRED
**And** the petition is acknowledged with:
- `reason_code` = EXPIRED
- `rationale` = "Referral to {realm} expired without Knight response"
**And** a `ReferralExpired` event is emitted
**And** a `PetitionAcknowledged` event is emitted
**And** 100% of timeouts fire reliably (NFR-3.4)

### AC2: Completed Referral No-Op
**Given** the Knight submits recommendation before timeout
**When** the deadline job fires
**Then** the job is no-op (referral already COMPLETED)
**And** no events are emitted
**And** job is marked as completed

### AC3: Already Expired No-Op
**Given** a referral is already in EXPIRED status
**When** the timeout job fires (duplicate delivery)
**Then** the job is no-op (idempotent)
**And** no duplicate events are emitted

### AC4: Witness Hash Generation (CT-12)
**Given** a referral timeout occurs
**When** auto-acknowledge executes
**Then** a witness hash is generated using BLAKE3
**And** the hash is included in both events
**And** the hash covers referral_id, petition_id, realm_id, expired_at

### AC5: Petition State Transition
**Given** a petition is in REFERRED state
**When** referral timeout triggers auto-acknowledge
**Then** petition state transitions to ACKNOWLEDGED
**And** fate_reason is set to "EXPIRED"
**And** the transition is atomic with referral expiration

## Technical Design

### Components

1. **ReferralTimeoutService** - New service to handle timeout job processing
   - Implements job handler for `referral_timeout` job type
   - Coordinates referral expiration and auto-acknowledge
   - Integrates with AcknowledgmentExecutionService

2. **ReferralTimeoutProtocol** - Port interface
   - `process_timeout(job: ScheduledJob) -> ReferralTimeoutResult`
   - `handle_expired_referral(referral_id: UUID) -> bool`

### Event Flow

```
Timeout Job Fires
    ↓
ReferralTimeoutService.process_timeout()
    ↓
Check referral status (skip if terminal)
    ↓
Referral.with_expired() → EXPIRED
    ↓
ReferralRepository.save(expired_referral)
    ↓
Emit ReferralExpiredEvent (CT-12)
    ↓
AcknowledgmentExecutionService.execute(
    petition_id=...,
    reason_code=EXPIRED,
    rationale="Referral to {realm} expired..."
)
    ↓
PetitionAcknowledgedEvent emitted
    ↓
JobScheduler.mark_completed(job_id)
```

### Integration Points

- **ReferralExecutionService**: Creates timeout jobs (Story 4.2)
- **AcknowledgmentExecutionService**: Executes auto-acknowledge (Story 3.2)
- **JobSchedulerProtocol**: Manages job lifecycle
- **ContentHashProtocol**: Generates witness hashes

## Tasks

- [x] Create story file
- [x] Create ReferralTimeoutProtocol port interface
- [x] Implement ReferralTimeoutService
- [x] Add ReferralTimeoutResult model
- [x] Write unit tests (18 passing)
- [x] Write integration tests (18 passing)
- [x] Update __init__.py exports
- [x] Update status files

## Test Plan

### Unit Tests
- `test_process_timeout_expires_pending_referral`
- `test_process_timeout_expires_assigned_referral`
- `test_process_timeout_expires_in_review_referral`
- `test_process_timeout_noop_for_completed_referral`
- `test_process_timeout_noop_for_already_expired`
- `test_process_timeout_generates_witness_hash`
- `test_process_timeout_emits_referral_expired_event`
- `test_process_timeout_triggers_auto_acknowledge`
- `test_process_timeout_sets_correct_rationale`
- `test_process_timeout_marks_job_completed`
- `test_process_timeout_handles_referral_not_found`
- `test_process_timeout_handles_petition_not_found`
- `test_witness_hash_includes_required_fields`
- `test_rationale_includes_realm_name`

### Integration Tests
- `test_timeout_flow_end_to_end`
- `test_timeout_with_job_scheduler_integration`
- `test_timeout_atomicity_referral_and_petition`
- `test_timeout_idempotency_duplicate_jobs`
- `test_timeout_concurrent_with_recommendation`
- `test_timeout_event_ordering`

## Dependencies

- Story 4.2: ReferralExecutionService (schedules timeout jobs)
- Story 3.2: AcknowledgmentExecutionService (executes auto-acknowledge)
- Story 0.4: JobSchedulerProtocol (job infrastructure)

## Notes

- EXPIRED acknowledgments are exempt from archon count validation (single system actor)
- Auto-acknowledge bypasses dwell time enforcement (FR-3.5 exemption for system actions)
- The timeout job payload contains: referral_id, petition_id, realm_id, deadline
