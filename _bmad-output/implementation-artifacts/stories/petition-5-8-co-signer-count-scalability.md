# Story 5.8: Co-Signer Count Scalability

## Story

**ID:** petition-5-8-co-signer-count-scalability
**Epic:** Petition Epic 5: Co-signing & Auto-Escalation
**Priority:** P0

As a **system**,
I want to support 100,000+ co-signers per petition,
So that popular petitions can accumulate mass support without performance degradation.

## Acceptance Criteria

### AC1: Count Query Performance at Scale
**Given** a petition with 100,000 co-signers
**When** count queries are executed (GET `/api/v1/petitions/{id}/cosigners/count`)
**Then** response latency remains < 100ms p99
**And** the count is accurate (matches actual co-sign records)
**And** count retrieval uses optimized path (not COUNT(*) scan)

### AC2: Co-sign Insertion Performance at Scale
**Given** a petition with 100,000 co-signers
**When** a new co-sign insertion is executed
**Then** insertion latency remains < 150ms p99
**And** co_signer_count is atomically incremented
**And** escalation threshold check is not affected by count volume

### AC3: Counter Column on petition_submissions Table
**Given** the petition_submissions table
**When** a migration adds co_signer_count column
**Then** the column is INTEGER NOT NULL DEFAULT 0
**And** existing petitions get count 0 (safe migration)
**And** the counter is atomically updated with each co-sign

### AC4: Load Test with 100k Co-signers
**Given** a load test scenario with 100,000 co-sign requests
**When** the test completes
**Then** all co-signs are persisted correctly
**And** count is accurate (matches inserted count)
**And** no database timeouts occur
**And** no deadlocks or lock contention errors occur

### AC5: Count Consistency Verification
**Given** the counter column approach
**When** periodic verification runs
**Then** counter value equals SELECT COUNT(*) FROM co_signs WHERE petition_id = ?
**And** any discrepancy triggers MEDIUM alert
**And** discrepancy is logged with structured logging

### AC6: Index Optimization for Count Queries
**Given** the existing idx_co_signs_petition_id index
**When** count queries or verification runs
**Then** queries use index scan (not sequential scan)
**And** EXPLAIN shows efficient query plan

## References

- **NFR-2.2:** Co-signers per petition: 100,000+ [CRITICAL]
- **FR-6.4:** System SHALL increment co-signer count atomically [P0]
- **FR-6.5:** System SHALL check escalation threshold on each co-sign [P0]
- **CT-12:** Witnessing creates accountability
- **Story 5.7:** Co-Signer Deduplication Enforcement (completed - PostgreSQL repo exists)

## Tasks/Subtasks

### Task 1: Create Migration for co_signer_count Column
- [x] Create migration `025_add_cosigner_count_to_petition_submissions.sql`
  - [x] Add `co_signer_count INTEGER NOT NULL DEFAULT 0`
  - [x] Add CHECK constraint `co_signer_count >= 0`
  - [x] Include comment explaining column purpose (NFR-2.2 optimization)
- [x] Run migration locally to verify
- [x] Update any existing integration tests that assume schema

### Task 2: Update PostgresCoSignRepository for Counter
- [x] Verify `src/infrastructure/adapters/persistence/co_sign_repository.py`
  - [x] The `create()` method already increments co_signer_count (line 142-149)
  - [x] Verify RETURNING clause works correctly
- [x] Update `get_count()` to read from petition_submissions.co_signer_count instead of COUNT(*)
- [x] Add docstring noting counter vs. count query difference

### Task 3: Update CoSignRepositoryStub for Counter Pattern
- [x] Verify `src/infrastructure/stubs/co_sign_repository_stub.py` matches production pattern
  - [x] `_counts` dict already simulates counter column behavior
  - [x] Verify `get_count()` returns counter value
- [x] Ensure stub and production have identical semantics

### Task 4: Add Count Consistency Verification Service
- [x] Create `src/application/services/co_sign_count_verification_service.py`
  - [x] Method `verify_count(petition_id: UUID) -> CountVerificationResult`
  - [x] Compare counter value vs. SELECT COUNT(*)
  - [x] Log discrepancy with structured logging (level: WARNING)
  - [x] Return CountVerificationResult with is_consistent flag
- [x] Add port definition in `src/application/ports/co_sign_count_verification.py`

### Task 5: Write Load Test for 100k Co-signers
- [x] Create `tests/load/test_co_sign_scalability_load.py`
  - [x] Test inserting 100k co-signers (can be 1k in CI, 100k manual)
  - [x] Measure insertion latency (p50, p95, p99)
  - [x] Measure count query latency
  - [x] Verify no deadlocks or errors
  - [x] Skip by default with `@pytest.mark.load` marker
- [x] Create load test configuration in `tests/load/conftest.py`

### Task 6: Write Integration Tests for Counter Accuracy
- [x] Create `tests/integration/test_co_sign_count_scalability_integration.py`
  - [x] Test counter increments correctly on each co-sign
  - [x] Test counter equals actual count after N insertions
  - [x] Test counter not affected by duplicate attempts
  - [x] Test concurrent insertions maintain accurate count
- [x] Add tests to existing `test_co_sign_persistence_integration.py`

### Task 7: Write Unit Tests for Verification Service
- [x] Create `tests/unit/application/services/test_co_sign_count_verification_service.py`
  - [x] Test verify_count returns True when consistent
  - [x] Test verify_count returns False when discrepant
  - [x] Test logging on discrepancy
- [x] Create stub for verification service testing (mock session factory)

### Task 8: Database Index Verification
- [x] Verify `idx_co_signs_petition_id` exists (migration 024)
- [x] Write test that confirms query plan uses index (documentation tests)
- [x] Add EXPLAIN ANALYZE test for count verification query (manual verification SQL)

### Task 9: Update API Response to Include Count
- [x] Verify `src/api/routes/co_sign.py` returns count efficiently (already returns co_signer_count)
- [x] Ensure count comes from counter column, not computed (via RETURNING from atomic increment)
- [x] Add response time logging for monitoring (NFR-1.3 latency tracking in place)

## Dev Notes

### Architecture Context
- **Counter column is the scalability solution** - COUNT(*) doesn't scale to 100k rows
- **Atomic increment in same transaction** - Already implemented in PostgresCoSignRepository
- **Verification service for consistency checks** - Catch any drift between counter and actual count
- **Load testing validates NFR-2.2** - Must handle 100k co-signers per petition

### Critical Discovery: Missing Migration
The `petition_submissions` table (migration 012) does **NOT** have a `co_signer_count` column.
However, `PostgresCoSignRepository.create()` references it in the UPDATE statement.

**This story MUST:**
1. Create migration 025 to add the column
2. Backfill existing petitions with accurate counts
3. Ensure atomic increment semantics

### Existing Code Analysis

**PostgresCoSignRepository (Story 5.7):**
```python
# Line 142-149 in co_sign_repository.py
result = await session.execute(
    text("""
        UPDATE petition_submissions
        SET co_signer_count = co_signer_count + 1
        WHERE id = :petition_id
        RETURNING co_signer_count
    """),
    {"petition_id": petition_id},
)
```
This code assumes the column exists - it will fail without migration 025!

**CoSignRepositoryStub:**
- Uses `_counts: dict[UUID, int]` to simulate counter column
- Initialized to 0 when petition added via `add_valid_petition()`
- Incremented atomically in `create()` method

### Migration Strategy

**Migration 025 must:**
```sql
-- Add counter column
ALTER TABLE petition_submissions
ADD COLUMN co_signer_count INTEGER NOT NULL DEFAULT 0;

-- Add constraint
ALTER TABLE petition_submissions
ADD CONSTRAINT chk_cosigner_count_non_negative CHECK (co_signer_count >= 0);

-- Backfill from co_signs table (for any existing data)
UPDATE petition_submissions ps
SET co_signer_count = (
    SELECT COUNT(*) FROM co_signs cs WHERE cs.petition_id = ps.id
);

-- Add comment
COMMENT ON COLUMN petition_submissions.co_signer_count IS
    'Pre-computed co-signer count for O(1) reads (NFR-2.2). Incremented atomically on co-sign.';
```

### Performance Considerations

| Operation | Without Counter | With Counter |
|-----------|-----------------|--------------|
| Get count | O(n) COUNT(*) | O(1) column read |
| Insert co-sign | O(1) | O(1) + counter increment |
| Verify count | N/A | Periodic O(n) verification |

**Why counter column over materialized view:**
- Simpler implementation
- Atomic updates in same transaction
- No refresh lag
- Works with existing PostgreSQL setup

### Previous Story Learnings (5.7)
- PostgresCoSignRepository pattern established
- AlreadySignedError with enhanced details
- RFC 7807 error responses
- LEGIT-1 logging for fraud detection
- Constraint violation handling (error code 23505)

### Project Context Rules
- HALT CHECK FIRST pattern (CT-13)
- Structured logging with structlog (no f-strings)
- Absolute imports only
- Type hints on all functions
- RFC 7807 error responses (D7)
- Never retry constitutional operations (D12)

### Index Verification SQL
```sql
-- Verify index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'co_signs'
AND indexname = 'idx_co_signs_petition_id';

-- Verify query uses index
EXPLAIN ANALYZE
SELECT COUNT(*) FROM co_signs WHERE petition_id = '00000000-0000-0000-0000-000000000001';
-- Should show "Index Only Scan" or "Index Scan"
```

## File List

### Migrations
- `migrations/025_add_cosigner_count_to_petition_submissions.sql` - NEW

### Domain Layer
- No changes (counter is infrastructure concern)

### Application Layer
- `src/application/ports/co_sign_count_verification.py` - NEW port
- `src/application/services/co_sign_count_verification_service.py` - NEW service

### Infrastructure Layer
- `src/infrastructure/adapters/persistence/co_sign_repository.py` - Update get_count()
- `src/infrastructure/stubs/co_sign_repository_stub.py` - Verify consistency

### API Layer
- `src/api/routes/co_sign.py` - Verify count returned efficiently

### Tests
- `tests/unit/application/services/test_co_sign_count_verification_service.py` - NEW
- `tests/integration/test_co_sign_count_scalability_integration.py` - NEW
- `tests/load/test_co_sign_scalability_load.py` - NEW (manual/CI-skip)
- `tests/load/conftest.py` - NEW load test config

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [x] Inline comments added for complex logic
- [x] N/A - minimal documentation impact (infrastructure/optimization change, no external API changes)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-20 | Story created from Epic 5.8 with comprehensive context | Create-Story Workflow |
| 2026-01-20 | All 9 tasks completed, unit/integration/load tests written | Dev-Story Workflow |
| 2026-01-20 | Code review complete - 6 issues fixed (2 major, 2 medium, 2 low) | Code Review |

## Status

**Status:** Done

---

_Ultimate context engine analysis completed - comprehensive developer guide created_
