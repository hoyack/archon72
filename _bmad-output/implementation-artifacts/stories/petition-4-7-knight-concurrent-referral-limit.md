# Story 4.7: Knight Concurrent Referral Limit

## Story

**As a** system
**I want to** enforce max concurrent referrals per Knight
**So that** no Knight is overwhelmed and workload is fairly distributed

## Status

| Field | Value |
|-------|-------|
| Story ID | petition-4-7-knight-concurrent-referral-limit |
| Epic | Petition Epic 4: Knight Referral Workflow |
| Status | done |
| Priority | P1 |
| Started | 2026-01-20 |
| Completed | 2026-01-20 |

## Requirements Traceability

| Requirement | Description | Priority |
|-------------|-------------|----------|
| FR-4.7 | System SHALL enforce max concurrent referrals per Knight | P1 |
| NFR-7.3 | Referral load balancing - max concurrent per Knight configurable | P1 |
| CT-12 | Every action that affects an Archon must be witnessed | CRITICAL |

## Acceptance Criteria

### AC1: Knight Eligibility Check
**Given** a Knight in a realm with `knight_capacity` limit
**When** eligibility is checked for new referral assignment
**Then** Knight is eligible if active referrals < knight_capacity
**And** Knight is ineligible if active referrals >= knight_capacity
**And** eligibility result includes current count and max allowed

### AC2: Fair Distribution via Least-Loaded Selection
**Given** multiple Knights with varying workloads
**When** a new referral needs assignment
**Then** the Knight with lowest current workload is selected
**And** Knights at capacity are excluded
**And** results are sorted by workload ascending

### AC3: Deferral When All Knights at Capacity
**Given** all Knights in a realm are at capacity
**When** referral assignment is attempted
**Then** assignment is deferred (returns failure result)
**And** referral remains in PENDING status
**And** ReferralDeferredEvent is emitted with witness hash (CT-12)
**And** deferral reason includes Knight count and capacity

### AC4: Successful Assignment with Witnessing
**Given** an eligible Knight is available
**When** referral is assigned to that Knight
**Then** referral transitions to ASSIGNED status
**And** ReferralAssignedEvent is emitted with witness hash (CT-12)
**And** event includes workload before/after and realm capacity
**And** assignment is persisted atomically

### AC5: Preferred Knight Support
**Given** a preferred Knight is specified
**When** preferred Knight is eligible
**Then** assignment goes to preferred Knight
**When** preferred Knight is not eligible or not found
**Then** fallback to least-loaded eligible Knight

### AC6: Realm Workload Summary
**Given** a realm with multiple Knights
**When** workload summary is requested
**Then** returns dict mapping Knight UUID to active referral count
**And** all Knights in realm are included
**And** raises error if realm not found

## Technical Design

### Components

1. **KnightConcurrentLimitProtocol** - Port interface
   - `check_knight_eligibility(knight_id, realm_id)` -> KnightEligibilityResult
   - `find_eligible_knights(realm_id, limit)` -> list[UUID]
   - `assign_to_eligible_knight(referral_id, realm_id, preferred_knight_id)` -> AssignmentResult
   - `get_knight_workload(knight_id)` -> int
   - `get_realm_workload_summary(realm_id)` -> dict[UUID, int]

2. **KnightConcurrentLimitService** - Main service implementation
   - Implements fair assignment via least-loaded selection
   - Coordinates with realm registry for capacity limits
   - Emits witnessed events for all assignments/deferrals

3. **KnightRegistryProtocol** - Knight lookup protocol
   - `get_knights_in_realm(realm_id)` -> list[UUID]
   - `is_knight(archon_id)` -> bool
   - `get_knight_realm(knight_id)` -> UUID | None

4. **Domain Events**
   - `ReferralAssignedEvent` - Emitted on successful assignment
   - `ReferralDeferredEvent` - Emitted when assignment deferred

5. **Domain Errors**
   - `KnightAtCapacityError` - Knight at max concurrent limit
   - `NoEligibleKnightsError` - All Knights at capacity
   - `KnightNotFoundError` - Knight does not exist
   - `KnightNotInRealmError` - Knight not in specified realm
   - `ReferralAlreadyAssignedError` - Referral already has Knight

### Assignment Flow

```
Referral Assignment Request
    ↓
Check if referral is PENDING
    ↓ (no: return error)
Get realm knight_capacity
    ↓
Try preferred Knight (if specified)
    ↓ (not eligible: fallback)
Find least-loaded eligible Knight
    ↓ (none found: defer)
   /                    \
DEFER                 ASSIGN
  ↓                      ↓
Emit ReferralDeferred   Update referral (ASSIGNED)
Event (CT-12)             ↓
  ↓                   Emit ReferralAssigned
Return deferred       Event (CT-12)
result                    ↓
                      Return success result
```

### Integration Points

- **RealmRegistryProtocol**: Provides knight_capacity per realm
- **ReferralRepositoryProtocol**: Persists referral assignments, counts active referrals
- **ContentHashServiceProtocol**: Generates BLAKE3 witness hashes
- **EventWriterProtocol**: Emits witnessed domain events

## Tasks

- [x] Create story file
- [x] Create KnightConcurrentLimitProtocol port interface
- [x] Create KnightRegistryProtocol port interface
- [x] Create domain errors for concurrent limit violations
- [x] Create ReferralAssignedEvent and ReferralDeferredEvent
- [x] Implement KnightConcurrentLimitService
- [x] Create KnightRegistryStub for testing
- [x] Create KnightConcurrentLimitStub for testing
- [x] Write unit tests (17 passing)
- [x] Write integration tests (19 passing)
- [x] Update __init__.py exports
- [x] Update status files

## Test Plan

### Unit Tests (17 tests)
- `test_check_eligibility_knight_under_capacity`
- `test_check_eligibility_knight_at_capacity`
- `test_check_eligibility_knight_not_found`
- `test_check_eligibility_knight_not_in_realm`
- `test_find_eligible_returns_sorted_by_workload`
- `test_find_eligible_excludes_at_capacity`
- `test_find_eligible_respects_limit`
- `test_find_eligible_empty_when_all_at_capacity`
- `test_assign_to_least_loaded_knight`
- `test_assign_uses_preferred_when_eligible`
- `test_assign_falls_back_from_ineligible_preferred`
- `test_assign_defers_when_all_at_capacity`
- `test_assign_emits_assigned_event_with_witness`
- `test_assign_emits_deferred_event_with_witness`
- `test_assign_fails_for_already_assigned`
- `test_get_knight_workload`
- `test_get_realm_workload_summary`

### Integration Tests (19 tests)
- `test_eligibility_check_integration`
- `test_find_eligible_knights_integration`
- `test_assignment_updates_referral_status`
- `test_assignment_persists_knight_id`
- `test_deferral_keeps_pending_status`
- `test_workload_increases_after_assignment`
- `test_re_eligibility_after_referral_completed`
- `test_fair_distribution_across_knights`
- `test_capacity_enforcement_across_assignments`
- `test_workload_summary_integration`

## Dependencies

- Story 4.2: ReferralExecutionService (creates referrals in PENDING)
- Story 0.6: RealmRegistryProtocol (provides knight_capacity)
- Story 0.5: ContentHashServiceProtocol (witness hashing)

## Notes

- Active referrals include ASSIGNED and IN_REVIEW statuses only
- COMPLETED and EXPIRED referrals don't count against capacity
- Deferred referrals can be retried when Knight capacity frees up
- The realm's knight_capacity is configurable per realm (NFR-7.3)
- All assignments/deferrals are witnessed with BLAKE3 hashes (CT-12)
