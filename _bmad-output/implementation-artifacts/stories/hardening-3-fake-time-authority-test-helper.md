# Story HARDENING-3: FakeTimeAuthority Test Helper

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **QA engineer**,
I want **a FakeTimeAuthority test helper with documented usage patterns**,
So that **time-dependent tests are reliable and not flaky**.

## Acceptance Criteria

1. **AC1: FakeTimeAuthority Class Exists**
   - **Given** the test helper module
   - **When** imported
   - **Then** `FakeTimeAuthority` class is available implementing `TimeAuthorityProtocol`

2. **AC2: Controllable Time**
   - **Given** a `FakeTimeAuthority` instance
   - **When** `now()` or `utcnow()` is called
   - **Then** returns the controlled time value set by the test

3. **AC3: Time Advancement**
   - **Given** a `FakeTimeAuthority` instance
   - **When** `advance(seconds)` or `advance(timedelta)` is called
   - **Then** subsequent `now()` calls return the advanced time

4. **AC4: Time Freeze Pattern**
   - **Given** a test needs frozen time
   - **When** `FakeTimeAuthority(frozen_at=datetime(...))` is used
   - **Then** `now()` always returns exactly that datetime

5. **AC5: Monotonic Clock Simulation**
   - **Given** a `FakeTimeAuthority` instance
   - **When** `monotonic()` is called multiple times
   - **Then** returns monotonically increasing values (never goes backward)

6. **AC6: Pytest Fixture Available**
   - **Given** a test file
   - **When** using `@pytest.fixture` or `conftest.py`
   - **Then** `fake_time_authority` fixture is available project-wide

7. **AC7: Usage Documentation**
   - **Given** a developer writing time-dependent tests
   - **When** looking for guidance
   - **Then** docstrings and/or docs explain common patterns

## Tasks / Subtasks

- [x] Task 1: Create FakeTimeAuthority class (AC: 1, 2, 4, 5)
  - [x] Create `tests/helpers/fake_time_authority.py`
  - [x] Implement `TimeAuthorityProtocol` interface
  - [x] Add `frozen_at` constructor parameter for frozen time
  - [x] Add internal `_current_time` tracking

- [x] Task 2: Implement time advancement (AC: 3)
  - [x] Add `advance(seconds: int | float)` method
  - [x] Add `advance(delta: timedelta)` overload
  - [x] Add `set_time(dt: datetime)` for explicit setting

- [x] Task 3: Implement monotonic simulation (AC: 5)
  - [x] Track monotonic counter internally
  - [x] Ensure `monotonic()` never returns smaller value than previous
  - [x] Tie monotonic advancement to `advance()` calls

- [x] Task 4: Create pytest fixture (AC: 6)
  - [x] Add fixture to `tests/conftest.py`
  - [x] Make fixture return fresh `FakeTimeAuthority` for each test
  - [x] Add fixture variant with frozen time at test start

- [x] Task 5: Write usage documentation (AC: 7)
  - [x] Document frozen time pattern in class docstring
  - [x] Document advancing time pattern
  - [x] Document integration with service injection
  - [x] Add examples in docstrings

- [x] Task 6: Update existing flaky tests (AC: 2, 3)
  - [x] Identify tests using `freezegun` or datetime mocking
  - [x] No migration needed - existing tests already use protocol injection or are not time-dependent
  - [x] All tests pass consistently

- [x] Task 7: Add validation tests (AC: 1-6)
  - [x] Test `FakeTimeAuthority` class itself
  - [x] Test fixture behavior
  - [x] Test edge cases (advance negative time, etc.)

## Dev Notes

- **Source:** Gov Epic 8 Retrospective Action Item #3 (2026-01-15)
- **Owner:** Dana (QA Engineer)
- **Priority:** Medium (blocks new feature work per retrospective)

### Technical Context

The retrospective identified time-dependent test flakiness:

> **Time-Dependent Test Flakiness**
> - Error escalation tests required careful mocking
> - Time dependencies caused initial flakiness
> - Cost several hours to isolate and fix

Current tests use various approaches:
- `freezegun` library
- `unittest.mock.patch` on `datetime.now`
- Direct `datetime.now()` calls (bad)

A unified `FakeTimeAuthority` will:
- Provide consistent interface
- Support dependency injection pattern
- Make tests deterministic
- Enable proper isolation

### Implementation Approach

```python
# Example usage pattern
from tests.helpers.fake_time_authority import FakeTimeAuthority

def test_timeout_detection():
    fake_time = FakeTimeAuthority(frozen_at=datetime(2026, 1, 15, 10, 0, 0))
    service = SuppressionDetectionService(time_authority=fake_time)

    # Simulate time passing
    fake_time.advance(seconds=3600)  # 1 hour later

    result = service.check_timeout(acknowledgment)
    assert result.is_timed_out
```

### Team Agreement (from retrospective)

> Time-dependent tests must use `FakeTimeAuthority` or `freezegun`

### Relationship to HARDENING-1

This story (HARDENING-3) creates the test helper that HARDENING-1 depends on:
- HARDENING-1 requires all services to accept `TimeAuthorityProtocol`
- HARDENING-3 provides the fake implementation for tests
- Recommend completing HARDENING-3 before or in parallel with HARDENING-1

### Project Structure Notes

- Helper: `tests/helpers/fake_time_authority.py` (new)
- Fixture: `tests/conftest.py` (modify)
- Protocol: `src/application/ports/time_authority.py` (from HARDENING-1)

### References

- [Source: _bmad-output/implementation-artifacts/retrospectives/gov-epic-8-retro-2026-01-15.md#Action Items]
- [Source: _bmad-output/implementation-artifacts/retrospectives/gov-epic-8-retro-2026-01-15.md#Challenge Themes]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation was straightforward with no blockers.

### Completion Notes List

1. **FakeTimeAuthority Implementation Complete** - Full implementation of `TimeAuthorityProtocol` with:
   - Frozen time pattern via `frozen_at` constructor parameter
   - Time advancement via `advance(seconds=N)` and `advance(delta=timedelta(...))`
   - Explicit time setting via `set_time(dt)`
   - Monotonic clock simulation tied to advance() calls
   - Reset functionality for test cleanup
   - Comprehensive docstrings with usage examples

2. **Pytest Fixtures Added** - Two fixtures in `tests/conftest.py`:
   - `fake_time_authority` - Fresh instance at 2026-01-01T00:00:00 UTC
   - `frozen_time_authority` - Frozen at 2026-01-15T10:00:00 UTC

3. **Validation Tests** - 43 tests covering all acceptance criteria:
   - Protocol compliance (AC1)
   - Controllable time (AC2)
   - Time advancement (AC3)
   - Frozen time pattern (AC4)
   - Monotonic clock simulation (AC5)
   - Pytest fixtures (AC6)
   - Edge cases (negative time, zero advance, microseconds, years)

4. **Migration Analysis** - Investigated existing tests:
   - No `freezegun` usage found in codebase (only comments)
   - Existing `datetime.now()` calls are for test data creation, not time-dependent behavior
   - Time-dependent services already use `TimeAuthorityProtocol` injection (from HARDENING-1)
   - No migration needed

### File List

**Created:**
- `tests/helpers/__init__.py` - Package init with FakeTimeAuthority export
- `tests/helpers/fake_time_authority.py` - Main implementation (180 lines)
- `tests/unit/helpers/__init__.py` - Test package init
- `tests/unit/helpers/test_fake_time_authority.py` - Validation tests (43 tests)

**Modified:**
- `tests/conftest.py` - Added `fake_time_authority` and `frozen_time_authority` fixtures
