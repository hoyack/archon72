# Story HARDENING-1: TimeAuthorityService Mandatory Injection

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **TimeAuthorityService injection to be mandatory across all services**,
So that **timestamps are consistent, testable, and auditable throughout the system**.

## Acceptance Criteria

1. **AC1: No Direct datetime Calls**
   - **Given** any production code file in `src/`
   - **When** scanned for `datetime.now()` or `datetime.utcnow()` calls
   - **Then** zero instances are found (excluding TimeAuthorityService itself)

2. **AC2: TimeAuthorityProtocol Required**
   - **Given** any service constructor that requires timestamps
   - **When** instantiated
   - **Then** `TimeAuthorityProtocol` must be a required parameter (not optional with default)

3. **AC3: Constructor Validation**
   - **Given** a service that requires time authority
   - **When** instantiated without `time_authority` parameter
   - **Then** raises `TypeError` with clear message about missing time authority

4. **AC4: Protocol Defines Interface**
   - **Given** `TimeAuthorityProtocol` in `src/application/ports/`
   - **When** reviewed
   - **Then** it defines: `now() -> datetime`, `utcnow() -> datetime`, `monotonic() -> float`

5. **AC5: All Services Updated**
   - **Given** the 197 files currently using direct datetime calls
   - **When** refactored
   - **Then** all use injected `TimeAuthorityProtocol` instead

6. **AC6: Knight Witnessed**
   - **Given** any timestamp-related operation
   - **When** recorded in events
   - **Then** timestamps come from TimeAuthorityService (auditable, consistent)

## Tasks / Subtasks

- [ ] Task 1: Create TimeAuthorityProtocol Port (AC: 4)
  - [ ] Define protocol in `src/application/ports/time_authority.py`
  - [ ] Methods: `now()`, `utcnow()`, `monotonic()`
  - [ ] Export in `src/application/ports/__init__.py`

- [ ] Task 2: Update TimeAuthorityService to implement protocol (AC: 4)
  - [ ] Make `TimeAuthorityService` implement `TimeAuthorityProtocol`
  - [ ] Ensure existing functionality preserved

- [ ] Task 3: Create pre-commit hook to detect datetime.now() (AC: 1)
  - [ ] Add grep-based check in pre-commit config
  - [ ] Exclude `time_authority_service.py` from check
  - [ ] Fail on any direct datetime calls

- [ ] Task 4: Refactor high-priority services (AC: 2, 3, 5)
  - [ ] Government services (gov-epic-4, 6, 8 files)
  - [ ] Flow orchestrator service
  - [ ] Advisory acknowledgment service
  - [ ] Role collapse detection service

- [ ] Task 5: Refactor remaining services (AC: 5)
  - [ ] Domain models (use factory methods with time authority)
  - [ ] Infrastructure adapters
  - [ ] API routes (inject through dependency)

- [ ] Task 6: Update all tests to use FakeTimeAuthority (AC: 1, 6)
  - [ ] Create FakeTimeAuthority fixture (see HARDENING-3)
  - [ ] Update all test files to inject fake

- [ ] Task 7: Verify zero datetime.now() calls remain (AC: 1)
  - [ ] Run `grep -r "datetime\.now\|datetime\.utcnow" src/`
  - [ ] Ensure only TimeAuthorityService appears

## Dev Notes

- **Source:** Gov Epic 8 Retrospective Action Item #1 (2026-01-15)
- **Owner:** Charlie (Senior Dev)
- **Priority:** Medium (blocks new feature work per retrospective)

### Technical Context

The retrospective identified that `TimeAuthorityService` was made optional to maintain velocity during Gov Epic 8. This created technical debt:

1. **197 files** currently use `datetime.now()` or `datetime.utcnow()` directly
2. **Inconsistent timestamps** - different services may get different times
3. **Test flakiness** - time-dependent tests are hard to control
4. **Audit trail gaps** - timestamps not provably from single source

### Implementation Approach

1. **Protocol-first:** Define the contract before refactoring
2. **Pre-commit enforcement:** Prevent regression immediately
3. **Batch refactoring:** Group similar files together
4. **Test isolation:** Ensure tests use FakeTimeAuthority (HARDENING-3 dependency)

### Team Agreement (from retrospective)

> No `datetime.now()` calls in production code - always inject time authority

### Project Structure Notes

- Port: `src/application/ports/time_authority.py`
- Service: `src/application/services/time_authority_service.py` (existing)
- Tests: `tests/unit/application/test_time_authority_service.py` (existing)

### References

- [Source: _bmad-output/implementation-artifacts/retrospectives/gov-epic-8-retro-2026-01-15.md#Action Items]
- [Source: docs/conclave-prd.md] - CT-3: Ordering via sequence numbers only (time is unreliable)
- [Source: _bmad-output/planning-artifacts/architecture.md] - Time authority design

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
