-- Migration 025: Add co_signer_count column to petition_submissions
-- Story 5.8: Co-Signer Count Scalability
-- Constitutional: NFR-2.2 (100k+ co-signers), FR-6.4 (atomic increment)
--
-- This migration adds a counter column for O(1) read performance at scale.
-- Without this, counting 100k+ co-signers would require O(n) COUNT(*) scans.
--
-- Pattern: Counter Column with Atomic Increment
-- - Increment atomically in same transaction as co-sign INSERT
-- - Read is O(1) column lookup instead of O(n) COUNT(*)
-- - Periodic verification ensures counter accuracy
--
-- CRITICAL: PostgresCoSignRepository.create() depends on this column!

-- ============================================================================
-- STEP 1: Add counter column
-- ============================================================================

ALTER TABLE petition_submissions
ADD COLUMN co_signer_count INTEGER NOT NULL DEFAULT 0;

-- ============================================================================
-- STEP 2: Add non-negative constraint
-- ============================================================================

ALTER TABLE petition_submissions
ADD CONSTRAINT chk_petition_submissions_cosigner_count_non_negative
    CHECK (co_signer_count >= 0);

-- ============================================================================
-- STEP 3: Backfill existing counts (if any co_signs exist)
-- ============================================================================
-- This updates any petitions that already have co-signers
-- to have accurate counts. Safe for production since it only
-- updates based on actual data.

UPDATE petition_submissions ps
SET co_signer_count = (
    SELECT COUNT(*)
    FROM co_signs cs
    WHERE cs.petition_id = ps.id
);

-- ============================================================================
-- STEP 4: Documentation
-- ============================================================================

COMMENT ON COLUMN petition_submissions.co_signer_count IS
    'Pre-computed co-signer count for O(1) reads (NFR-2.2). '
    'Incremented atomically on each co-sign (FR-6.4). '
    'Use count_verification_service for periodic consistency checks.';

COMMENT ON CONSTRAINT chk_petition_submissions_cosigner_count_non_negative
    ON petition_submissions IS
    'Ensures co_signer_count is never negative (data integrity)';

-- ============================================================================
-- STEP 5: Index for queries filtering by co_signer_count
-- ============================================================================
-- Supports queries like:
-- - Finding petitions above escalation threshold
-- - Dashboard queries for popular petitions
-- - Verification queries that may scan by count

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_petition_submissions_cosigner_count
    ON petition_submissions (co_signer_count DESC)
    WHERE co_signer_count > 0;

COMMENT ON INDEX idx_petition_submissions_cosigner_count IS
    'Partial index for petitions with co-signers. Supports threshold checks and popularity queries (NFR-2.2).';
