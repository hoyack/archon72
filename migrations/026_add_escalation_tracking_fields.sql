-- Migration 026: Add escalation tracking fields to petition_submissions
-- Story 6.1: King Escalation Queue (FR-5.4)
--
-- This migration adds fields to track escalation metadata for petitions
-- that have been escalated to Kings for review.
--
-- Constitutional Constraints:
-- - FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
-- - CT-13: Halt check first pattern
-- - D8: Keyset pagination compliance (index on escalated_to_realm, escalated_at)
-- - RULING-3: Realm-scoped data access
--
-- Fields Added:
-- - escalation_source: What triggered the escalation (DELIBERATION, CO_SIGNER_THRESHOLD, KNIGHT_RECOMMENDATION)
-- - escalated_at: When the petition was escalated (for FIFO ordering)
-- - escalated_to_realm: Target King's realm (for realm filtering)
--
-- Index:
-- - idx_petition_escalation_queue: Efficient querying for King escalation queue
--   WHERE clause ensures index only applies to ESCALATED petitions

-- Add escalation_source column
ALTER TABLE petition_submissions
ADD COLUMN escalation_source TEXT;

-- Add escalated_at column
ALTER TABLE petition_submissions
ADD COLUMN escalated_at TIMESTAMPTZ;

-- Add escalated_to_realm column
ALTER TABLE petition_submissions
ADD COLUMN escalated_to_realm TEXT;

-- Add index for efficient escalation queue queries
-- This index supports:
-- - Filtering by realm (escalated_to_realm = 'governance')
-- - FIFO ordering (ORDER BY escalated_at ASC)
-- - Keyset pagination (WHERE escalated_at > cursor_time)
-- Partial index only on ESCALATED petitions to save space
CREATE INDEX idx_petition_escalation_queue
ON petition_submissions (escalated_to_realm, escalated_at, id)
WHERE state = 'ESCALATED' AND escalated_to_realm IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN petition_submissions.escalation_source IS 'What triggered escalation: DELIBERATION, CO_SIGNER_THRESHOLD, or KNIGHT_RECOMMENDATION (Story 6.1, FR-5.4)';
COMMENT ON COLUMN petition_submissions.escalated_at IS 'When petition was escalated (UTC timestamp, for FIFO ordering) (Story 6.1, FR-5.4)';
COMMENT ON COLUMN petition_submissions.escalated_to_realm IS 'Target Kings realm for escalation (e.g., governance) (Story 6.1, FR-5.4, RULING-3)';
COMMENT ON INDEX idx_petition_escalation_queue IS 'Efficient King escalation queue queries with realm filtering and FIFO ordering (Story 6.1, D8)';
