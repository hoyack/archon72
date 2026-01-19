-- Migration: Create Petition Migration Mapping Table
-- Story: petition-0-3-story-7-2-cessation-petition-migration (AC6)
-- Date: 2026-01-19
-- Constitutional Constraints: CT-11, CT-12, FR-9.1, FR-9.4
--
-- This creates the mapping table for tracking Story 7.2 petition migrations
-- to the new petition_submissions schema. FR-9.4 mandates ID preservation.

-- ============================================================================
-- STEP 1: Create Mapping Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS petition_migration_mapping (
    -- Story 7.2 petition ID (existing petition_id from legacy events)
    legacy_petition_id UUID PRIMARY KEY,

    -- New petition submission ID (same value as legacy per FR-9.4)
    new_submission_id UUID NOT NULL,

    -- When this petition was migrated
    migrated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Co-signer count at migration time (for reference/audit)
    co_signer_count INT NOT NULL DEFAULT 0,

    -- Migration source (for audit trail)
    migration_source TEXT NOT NULL DEFAULT 'cessation_migration_script',

    -- Foreign key to petition_submissions
    CONSTRAINT fk_migration_new_submission
        FOREIGN KEY (new_submission_id)
        REFERENCES petition_submissions(id)
        ON DELETE CASCADE
);

-- ============================================================================
-- STEP 2: Create Indexes
-- ============================================================================

-- Index for looking up by new submission ID (reverse lookup)
CREATE INDEX idx_petition_migration_new_id
    ON petition_migration_mapping(new_submission_id);

-- Index for migration timestamp (for monitoring/audit)
CREATE INDEX idx_petition_migration_at
    ON petition_migration_mapping(migrated_at);

-- ============================================================================
-- STEP 3: Comments for Documentation
-- ============================================================================

COMMENT ON TABLE petition_migration_mapping IS
    'Tracks Story 7.2 petition migrations to petition_submissions (FR-9.1, FR-9.4)';

COMMENT ON COLUMN petition_migration_mapping.legacy_petition_id IS
    'Original petition_id from Story 7.2 event-sourced petitions';

COMMENT ON COLUMN petition_migration_mapping.new_submission_id IS
    'Corresponding ID in petition_submissions (FR-9.4: SAME as legacy)';

COMMENT ON COLUMN petition_migration_mapping.migrated_at IS
    'When migration occurred (audit trail CT-12)';

COMMENT ON COLUMN petition_migration_mapping.co_signer_count IS
    'Number of co-signers at migration time (reference only)';

COMMENT ON COLUMN petition_migration_mapping.migration_source IS
    'Script/process that performed the migration (audit trail CT-11)';

-- ============================================================================
-- STEP 4: Unique Constraint Enforcement
-- ============================================================================

-- Ensure new_submission_id is also unique (1:1 mapping)
CREATE UNIQUE INDEX idx_petition_migration_unique_new
    ON petition_migration_mapping(new_submission_id);
