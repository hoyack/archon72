# Story HARDENING-2: Branch Conflict Rules YAML Consolidation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **branch conflict rules consolidated to a single YAML source of truth**,
So that **rules are maintainable and cannot drift between code and configuration**.

## Acceptance Criteria

1. **AC1: Single Source of Truth**
   - **Given** branch conflict rules
   - **When** the system needs to check for role collapse
   - **Then** rules are loaded ONLY from `config/permissions/rank-matrix.yaml`

2. **AC2: No Inline Rules in Python**
   - **Given** any Python source file
   - **When** scanned for hardcoded `BranchConflictRule` definitions
   - **Then** zero instances are found (rules loaded from YAML only)

3. **AC3: YAML Schema Enhanced**
   - **Given** `config/permissions/rank-matrix.yaml` branch_conflicts section
   - **When** enhanced
   - **Then** includes: `prd_ref`, `severity` (critical/major), and `description` for each rule

4. **AC4: Runtime Loading**
   - **Given** the `RoleCollapseDetectionService`
   - **When** initialized
   - **Then** loads branch conflict rules from YAML at runtime (not compile-time constants)

5. **AC5: Loader Validates Schema**
   - **Given** a malformed branch_conflicts entry
   - **When** loading is attempted
   - **Then** raises `ConfigurationError` with specific validation message

6. **AC6: Tests Use Same Source**
   - **Given** test cases for role collapse detection
   - **When** testing rules
   - **Then** tests validate against the actual YAML rules (not duplicated test fixtures)

## Tasks / Subtasks

- [ ] Task 1: Enhance YAML schema with severity and prd_ref (AC: 3)
  - [ ] Add `severity: critical|major` to each branch_conflicts entry
  - [ ] Add `prd_ref` citation to each entry
  - [ ] Add `description` field for human-readable explanation

- [ ] Task 2: Create BranchConflictRulesLoader (AC: 1, 4, 5)
  - [ ] Create `src/infrastructure/adapters/config/branch_conflict_rules_loader.py`
  - [ ] Parse YAML branch_conflicts section
  - [ ] Validate schema (required fields, valid severity values)
  - [ ] Return `list[BranchConflictRule]`

- [ ] Task 3: Remove inline rules from role_collapse_detection_service.py (AC: 2)
  - [ ] Delete `BRANCH_CONFLICT_RULES` constant (lines 80-100+)
  - [ ] Inject `BranchConflictRulesLoader` through constructor
  - [ ] Load rules from YAML at service initialization

- [ ] Task 4: Update RoleCollapseDetectionService constructor (AC: 4)
  - [ ] Add `rules_loader: BranchConflictRulesLoaderProtocol` parameter
  - [ ] Call loader to get rules during `__init__`
  - [ ] Store rules as instance attribute

- [ ] Task 5: Create pre-commit hook to prevent inline rules (AC: 2)
  - [ ] Add grep-based check for hardcoded BranchConflictRule lists
  - [ ] Allow only the dataclass definition, not instantiation lists

- [ ] Task 6: Update tests to use YAML source (AC: 6)
  - [ ] Remove duplicated rule fixtures from tests
  - [ ] Load actual rules from YAML in tests
  - [ ] Add test for YAML schema validation

- [ ] Task 7: Document configuration change (AC: 3)
  - [ ] Update architecture docs to reference YAML as source
  - [ ] Add inline comments in YAML explaining each rule

## Dev Notes

- **Source:** Gov Epic 8 Retrospective Action Item #2 (2026-01-15)
- **Owner:** Elena (Junior Dev)
- **Priority:** Medium (blocks new feature work per retrospective)

### Technical Context

The retrospective identified that branch conflict rules exist in TWO places:

1. **`config/permissions/rank-matrix.yaml`** (lines 249-261):
   ```yaml
   branch_conflicts:
     - branches: ["legislative", "executive"]
       rule: "Same Archon cannot define WHAT and HOW for same motion"
   ```

2. **`src/application/services/role_collapse_detection_service.py`** (lines 80-100+):
   ```python
   BRANCH_CONFLICT_RULES: list[BranchConflictRule] = [
       BranchConflictRule(
           branches=frozenset({"legislative", "executive"}),
           rule="Same Archon cannot define WHAT and HOW for same motion",
           ...
       ),
   ]
   ```

This dual-source creates:
- **Maintenance burden** - must update both places
- **Drift risk** - sources can become inconsistent
- **Testing confusion** - which source is authoritative?

### Implementation Approach

1. **YAML-first:** Enhance YAML to include all rule metadata
2. **Loader pattern:** Create a dedicated loader that validates and parses
3. **Dependency injection:** Services receive rules through constructor
4. **Schema validation:** Fail fast on invalid configuration

### Current Rules (from both sources)

| Branches | Severity | PRD Reference |
|----------|----------|---------------|
| legislative ↔ executive | CRITICAL | PRD §2.1 |
| executive ↔ judicial | CRITICAL | PRD §2.1 |
| advisory ↔ judicial | MAJOR | FR-GOV-18 |
| legislative ↔ judicial | CRITICAL | PRD §2.1 (inferred) |

### Team Agreement (from retrospective)

> Configuration lives in YAML, code loads it - no dual-source patterns

### Project Structure Notes

- Config: `config/permissions/rank-matrix.yaml` (existing)
- Loader: `src/infrastructure/adapters/config/branch_conflict_rules_loader.py` (new)
- Service: `src/application/services/role_collapse_detection_service.py` (modify)
- Tests: `tests/unit/application/services/test_role_collapse_detection.py` (modify)

### References

- [Source: _bmad-output/implementation-artifacts/retrospectives/gov-epic-8-retro-2026-01-15.md#Action Items]
- [Source: config/permissions/rank-matrix.yaml#branch_conflicts]
- [Source: src/application/services/role_collapse_detection_service.py:80-100]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

1. Enhanced `config/permissions/rank-matrix.yaml` with:
   - `id` field for unique rule identification
   - `severity` field (critical/major/info)
   - `prd_ref` field for traceability
   - `description` field with extended documentation
   - Added missing administrative↔judicial rule (was in code but not YAML)

2. Created `BranchConflictRulesLoader` at `src/infrastructure/adapters/config/branch_conflict_rules_loader.py`:
   - `BranchConflictRule` dataclass with `frozenset[str]` branches
   - `BranchConflictSeverity` class for severity constants
   - `YamlBranchConflictRulesLoader` implementation
   - `BranchConflictRulesLoaderProtocol` for dependency injection
   - Full schema validation with specific error messages

3. Refactored `RoleCollapseDetectionService`:
   - Removed `BRANCH_CONFLICT_RULES` constant
   - Removed `find_conflict_rule()` module-level function
   - Added `rules_loader` parameter to constructor (defaults to YAML loader)
   - Added `_find_conflict_rule()` instance method
   - Added `_create_violation()` instance method for YAML rule adaptation
   - Added `RoleCollapseSeverity.from_string()` for severity conversion

4. Fixed HARDENING-1 compliance gap in `BranchActionTrackerAdapter`:
   - Added `time_authority` parameter to constructor
   - Added `_get_current_time()` method
   - Updated `record_branch_action()` and `get_archon_history()` to use timestamps

5. Created pre-commit hook `scripts/check_no_inline_branch_conflict_rules.py`:
   - Detects `BranchConflictRule(` instantiations
   - Detects `BRANCH_CONFLICT_RULES =` constant definitions
   - Allows loader file and test files as exceptions

6. Updated tests with 49 passing:
   - Added `rules_loader` fixture
   - Updated service fixture to inject loader
   - Rewrote `TestBranchConflictMatrix` to test YAML rules via loader
   - Fixed timestamp parameters per HARDENING-1

### File List

Created:
- `src/infrastructure/adapters/config/branch_conflict_rules_loader.py`
- `scripts/check_no_inline_branch_conflict_rules.py`

Modified:
- `config/permissions/rank-matrix.yaml` (enhanced schema)
- `src/application/services/role_collapse_detection_service.py` (removed inline rules)
- `src/infrastructure/adapters/government/branch_action_tracker_adapter.py` (HARDENING-1 fix)
- `tests/unit/application/services/test_role_collapse_detection.py`
- `.pre-commit-config.yaml`
