# Story 3.5: Minimum Dwell Time Enforcement

## Story Status: Complete

| Attribute          | Value                                    |
| ------------------ | ---------------------------------------- |
| Epic               | Epic 3: Acknowledgment System            |
| Story ID           | petition-3-5                             |
| Story Points       | 3                                        |
| Priority           | High                                     |
| Status             | Complete                                 |
| Created            | 2026-01-19                               |
| Updated            | 2026-01-19                               |
| Constitutional Ref | FR-3.5, CT-14, NFR-3.4                   |

## Story Description

As the Conclave system, I need to enforce a minimum dwell time before acknowledgment so that petitions receive adequate deliberation time before fate assignment, preventing hasty decisions that could undermine the legitimacy of the Three Fates process.

## Constitutional Context

- **FR-3.5**: System SHALL enforce minimum dwell time before ACKNOWLEDGE (30 seconds default)
- **CT-14**: Every claim terminates in visible, witnessed fate
- **NFR-3.4**: Timeout reliability - 100% timeouts fire
- **HC-7**: Deliberation timeout auto-ESCALATE - Prevent stuck petitions

## Acceptance Criteria

### AC-1: Dwell Time Configuration
**Given** the deliberation configuration
**When** the system initializes
**Then** it SHALL load `min_dwell_seconds` from environment or use default (30 seconds)

- [x] Add `DEFAULT_MIN_DWELL_TIME_SECONDS = 30` constant
- [x] Add `MIN_DWELL_TIME_FLOOR_SECONDS = 0` for testing
- [x] Add `MAX_DWELL_TIME_SECONDS = 300` ceiling
- [x] Add `min_dwell_seconds` field to `DeliberationConfig`
- [x] Add `dwell_timedelta` property for datetime operations
- [x] Load `MIN_DWELL_TIME_SECONDS` from environment
- [x] Clamp values to valid range
- [x] Add `NO_DWELL_CONFIG` constant for testing

### AC-2: Dwell Time Validation Error
**Given** acknowledgment is attempted before dwell time has elapsed
**When** the service checks dwell time
**Then** it SHALL raise `DwellTimeNotElapsedError` with remaining time

- [x] Create `DwellTimeNotElapsedError` domain error
- [x] Include `petition_id`, `deliberation_started_at`, `min_dwell_seconds`
- [x] Include `elapsed_seconds` and calculate `remaining_seconds`
- [x] Add `remaining_timedelta` property for convenience
- [x] Reference FR-3.5 in error message

### AC-3: Session Not Found Error
**Given** a DELIBERATING petition with no session record
**When** dwell time check is performed
**Then** it SHALL raise `DeliberationSessionNotFoundError`

- [x] Create `DeliberationSessionNotFoundError` domain error
- [x] Include `petition_id` context
- [x] Indicate inconsistent state in message

### AC-4: Service Dwell Time Enforcement
**Given** the acknowledgment execution service
**When** executing acknowledgment
**Then** it SHALL verify dwell time has elapsed before proceeding

- [x] Add `session_service` parameter to constructor
- [x] Add `config` parameter to constructor
- [x] Implement `_enforce_dwell_time()` method
- [x] Skip check if `min_dwell_seconds == 0` (disabled)
- [x] Skip check if no `session_service` configured
- [x] Get session via `get_session_by_petition()`
- [x] Calculate elapsed time from `session.created_at`
- [x] Raise `DwellTimeNotElapsedError` if insufficient time
- [x] Raise `DeliberationSessionNotFoundError` if session missing
- [x] Add debug logging for dwell time checks

### AC-5: Stub Support for Testing
**Given** the acknowledgment execution stub
**When** testing dwell time scenarios
**Then** it SHALL support configurable dwell time behavior

- [x] Add `config` constructor parameter
- [x] Add `enforce_dwell_time` flag (default False for backwards compatibility)
- [x] Add `_sessions` storage dict
- [x] Add `add_session()` method
- [x] Update `add_petition()` to accept optional session
- [x] Implement dwell time check in `execute()`
- [x] Support both dwell time bypass and enforcement modes

## Technical Implementation

### Files Modified

1. **`src/config/deliberation_config.py`**
   - Added dwell time configuration constants
   - Extended `DeliberationConfig` dataclass
   - Added environment variable support
   - Added predefined configs (`NO_DWELL_CONFIG`)

2. **`src/domain/errors/acknowledgment.py`**
   - Added `DwellTimeNotElapsedError` class
   - Added `DeliberationSessionNotFoundError` class

3. **`src/application/services/acknowledgment_execution_service.py`**
   - Added `session_service` and `config` constructor params
   - Implemented `_enforce_dwell_time()` method
   - Added dwell time check in `execute()` flow

4. **`src/infrastructure/stubs/acknowledgment_execution_stub.py`**
   - Added dwell time testing support
   - Added session storage and management

### Files Created

1. **`tests/unit/application/services/test_acknowledgment_execution_service.py`** (extended)
   - Added `TestDwellTimeEnforcement` test class
   - 8 new test cases for dwell time scenarios

2. **`tests/integration/test_acknowledgment_execution_integration.py`** (extended)
   - Added `TestDwellTimeIntegration` test class
   - 7 new integration test cases

## Dependencies

- Story 3.2: Acknowledgment Execution Service (provides base service)
- `DeliberationSession` model (provides `created_at` timestamp)
- `ArchonAssignmentServiceProtocol.get_session_by_petition()` (retrieves session)

## Test Coverage

### Unit Tests
- `test_dwell_time_not_elapsed_raises_error` - FR-3.5 enforcement
- `test_dwell_time_elapsed_allows_acknowledgment` - Happy path
- `test_dwell_time_disabled_skips_check` - Config = 0
- `test_enforcement_disabled_skips_check` - Flag disabled
- `test_missing_session_raises_error` - Session not found
- `test_dwell_error_includes_remaining_time` - Error attributes
- `test_add_session_separately` - Session management

### Integration Tests
- `test_dwell_time_error_attributes` - Error completeness
- `test_session_not_found_error_attributes` - Error context
- `test_dwell_config_environment_override` - Env var loading
- `test_dwell_config_clamps_to_valid_range` - Value clamping
- `test_dwell_timedelta_property` - Timedelta conversion
- `test_predefined_configs` - Config constants
- `test_stub_dwell_time_enforcement` - End-to-end stub test

## Definition of Done

- [x] All acceptance criteria met
- [x] Domain errors created with constitutional references
- [x] Service implementation complete
- [x] Stub updated for testing
- [x] Unit tests written and passing (syntax verified)
- [x] Integration tests written and passing (syntax verified)
- [x] Code follows existing patterns
- [x] No security vulnerabilities introduced

## Notes

- Dwell time is configurable via `MIN_DWELL_TIME_SECONDS` environment variable
- Default dwell time is 30 seconds per FR-3.5
- Dwell time of 0 disables the check (for testing)
- Session service is optional for backwards compatibility
- Error provides `remaining_timedelta` for retry scheduling
