-- Migration 028: Add King Acknowledgment Field (Story 6.5, FR-5.8)
--
-- This migration adds support for King acknowledgments of escalated petitions.
-- Kings can formally decline adoption while providing rationale to respect petitioners.
--
-- Constitutional Constraints:
-- - FR-5.8: King SHALL be able to ACKNOWLEDGE escalation (with rationale) [P0]
-- - Story 6.5: Escalation Acknowledgment by King
-- - RULING-3: Realm-scoped data access (Kings only acknowledge their realm)
--
-- Changes:
-- 1. Add acknowledged_by_king_id column to acknowledgments table
-- 2. Add index for King acknowledgment queries
-- 3. Add CHECK constraint: only one of (acknowledging_archon_ids, acknowledged_by_king_id) can be set
--
-- Author: Claude (Story 6.5)
-- Date: 2026-01-22

-- Step 1: Add acknowledged_by_king_id column
-- This stores the King UUID when a King acknowledges an escalated petition
-- NULL for Marquis/system acknowledgments, non-NULL for King acknowledgments
ALTER TABLE acknowledgments
ADD COLUMN acknowledged_by_king_id UUID NULL;

-- Step 2: Add index for King acknowledgment queries
-- Enables efficient queries like "which petitions did this King acknowledge?"
CREATE INDEX idx_acknowledgments_king_id
ON acknowledgments (acknowledged_by_king_id)
WHERE acknowledged_by_king_id IS NOT NULL;

-- Step 3: Add comment for documentation
COMMENT ON COLUMN acknowledgments.acknowledged_by_king_id IS
'King UUID for King acknowledgments (Story 6.5, FR-5.8). NULL for Marquis/system acknowledgments. Mutually exclusive with acknowledging_archon_ids having values.';

-- Step 4: Add CHECK constraint to ensure mutual exclusivity
-- Either acknowledging_archon_ids has values (Marquis acknowledgment)
-- OR acknowledged_by_king_id is set (King acknowledgment)
-- But not both, and not neither (except for system codes)
ALTER TABLE acknowledgments
ADD CONSTRAINT chk_acknowledgment_source
CHECK (
    -- Case 1: Marquis acknowledgment (archon_ids not empty, no king_id)
    (cardinality(acknowledging_archon_ids) >= 2 AND acknowledged_by_king_id IS NULL)
    OR
    -- Case 2: King acknowledgment (king_id set, archon_ids empty)
    (acknowledged_by_king_id IS NOT NULL AND cardinality(acknowledging_archon_ids) = 0)
    OR
    -- Case 3: System acknowledgment (both empty, for EXPIRED/KNIGHT_REFERRAL)
    (cardinality(acknowledging_archon_ids) = 0 AND acknowledged_by_king_id IS NULL)
);

-- Verification query (commented out for production)
-- SELECT
--     COUNT(*) FILTER (WHERE acknowledged_by_king_id IS NOT NULL) as king_acks,
--     COUNT(*) FILTER (WHERE cardinality(acknowledging_archon_ids) >= 2) as marquis_acks,
--     COUNT(*) FILTER (WHERE cardinality(acknowledging_archon_ids) = 0 AND acknowledged_by_king_id IS NULL) as system_acks
-- FROM acknowledgments;
