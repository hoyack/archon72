-- Migration 027: Add petition adoption tracking fields (Story 6.3, FR-5.7, NFR-6.2)
--
-- Constitutional Constraints:
-- - FR-5.5: King SHALL be able to ADOPT petition (creates Motion) [P0]
-- - FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]
-- - NFR-6.2: Adoption provenance immutability (unique constraint)
-- - NFR-4.5: Budget consumption durability (fields survive restart)
--
-- This migration adds three fields to track petition adoption by Kings:
-- 1. adopted_as_motion_id: Back-reference to Motion created from this petition
-- 2. adopted_at: Timestamp when adoption occurred
-- 3. adopted_by_king_id: King who performed the adoption
--
-- Immutability is enforced via:
-- - Unique constraint on adopted_as_motion_id (one petition → one motion)
-- - Application logic prevents overwriting once set
--
-- Author: Story 6.3 - Petition Adoption Creates Motion
-- Date: 2026-01-22

-- Add adoption tracking columns
-- These fields remain NULL until/unless a King adopts the petition
ALTER TABLE petition_submissions
ADD COLUMN adopted_as_motion_id UUID,
ADD COLUMN adopted_at TIMESTAMPTZ,
ADD COLUMN adopted_by_king_id UUID;

-- Unique constraint: One petition can only be adopted once (NFR-6.2)
-- This enforces immutable provenance: adopted_as_motion_id cannot be changed
-- The partial index excludes NULL values for efficiency
ALTER TABLE petition_submissions
ADD CONSTRAINT unique_petition_adoption
UNIQUE (adopted_as_motion_id);

-- Index for back-reference queries: Motion → Petition lookup
-- Used when displaying Motion provenance or validating adoption history
-- Partial index for efficiency (only adopted petitions)
CREATE INDEX idx_petition_adoption_back_ref
ON petition_submissions (adopted_as_motion_id)
WHERE adopted_as_motion_id IS NOT NULL;

-- Index for King adoption history queries
-- Used for budget consumption reports and adoption metrics
-- Allows efficient queries like "show all petitions adopted by King X"
-- Ordered by adopted_at for chronological browsing
CREATE INDEX idx_petition_adopted_by_king
ON petition_submissions (adopted_by_king_id, adopted_at)
WHERE adopted_by_king_id IS NOT NULL;

-- Comments for future maintainers
COMMENT ON COLUMN petition_submissions.adopted_as_motion_id IS
'UUID of Motion created from this petition. NULL if not adopted. Immutable once set (NFR-6.2).';

COMMENT ON COLUMN petition_submissions.adopted_at IS
'Timestamp when King adopted this petition. NULL if not adopted. UTC timezone.';

COMMENT ON COLUMN petition_submissions.adopted_by_king_id IS
'UUID of King archon who adopted this petition. NULL if not adopted. Immutable once set.';

COMMENT ON CONSTRAINT unique_petition_adoption ON petition_submissions IS
'Enforces immutable provenance: one petition can only create one motion (NFR-6.2, FR-5.7).';
