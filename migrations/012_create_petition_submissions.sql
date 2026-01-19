-- Migration: Create Petition Submissions Schema
-- Story: petition-0-2-petition-domain-model-base-schema
-- Date: 2026-01-19
-- Constitutional Constraints: CT-11, CT-12, FR-2.2, HP-2
--
-- This creates the petition submissions table for the Three Fates
-- deliberation system. This is SEPARATE from the existing petition
-- table (Story 7.2 co-signing petitions).

-- ============================================================================
-- STEP 1: Create Enums
-- ============================================================================

CREATE TYPE petition_type_enum AS ENUM (
    'GENERAL',      -- General governance petition
    'CESSATION',    -- Request for system cessation review
    'GRIEVANCE',    -- Complaint about system behavior
    'COLLABORATION' -- Request for inter-realm collaboration
);

CREATE TYPE petition_state_enum AS ENUM (
    'RECEIVED',     -- Initial state after submission
    'DELIBERATING', -- Three Fates deliberation in progress
    'ACKNOWLEDGED', -- Petition acknowledged (no further action)
    'REFERRED',     -- Referred to Knight for review
    'ESCALATED'     -- Escalated to King for adoption
);

-- ============================================================================
-- STEP 2: Create Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS petition_submissions (
    id UUID PRIMARY KEY,
    type petition_type_enum NOT NULL,
    text TEXT NOT NULL,
    submitter_id UUID,  -- Nullable: anonymous submissions allowed initially
    state petition_state_enum NOT NULL DEFAULT 'RECEIVED',
    content_hash BYTEA,  -- 32 bytes for Blake3 (HP-2)
    realm TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraint: Text max 10,000 characters (FR requirement)
    CONSTRAINT petition_text_length CHECK (char_length(text) <= 10000)
);

-- ============================================================================
-- STEP 3: Create Indexes
-- ============================================================================

CREATE INDEX idx_petition_submissions_state ON petition_submissions(state);
CREATE INDEX idx_petition_submissions_type ON petition_submissions(type);
CREATE INDEX idx_petition_submissions_realm ON petition_submissions(realm);
CREATE INDEX idx_petition_submissions_created_at ON petition_submissions(created_at);

-- ============================================================================
-- STEP 4: Create Updated_At Trigger
-- ============================================================================

CREATE OR REPLACE FUNCTION update_petition_submissions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER petition_submissions_updated_at_trigger
    BEFORE UPDATE ON petition_submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_petition_submissions_updated_at();

-- ============================================================================
-- STEP 5: Comments for Documentation
-- ============================================================================

COMMENT ON TABLE petition_submissions IS 'Petition submissions for Three Fates deliberation (FR-2.2)';
COMMENT ON COLUMN petition_submissions.id IS 'UUIDv7 primary key';
COMMENT ON COLUMN petition_submissions.type IS 'Petition type: GENERAL, CESSATION, GRIEVANCE, COLLABORATION';
COMMENT ON COLUMN petition_submissions.text IS 'Petition content (max 10,000 chars)';
COMMENT ON COLUMN petition_submissions.submitter_id IS 'UUID of submitter (nullable for anonymous)';
COMMENT ON COLUMN petition_submissions.state IS 'Petition state: RECEIVED, DELIBERATING, ACKNOWLEDGED, REFERRED, ESCALATED';
COMMENT ON COLUMN petition_submissions.content_hash IS 'Blake3 hash for duplicate detection (HP-2)';
COMMENT ON COLUMN petition_submissions.realm IS 'Routing realm for petition processing';
COMMENT ON COLUMN petition_submissions.created_at IS 'Submission timestamp (UTC)';
COMMENT ON COLUMN petition_submissions.updated_at IS 'Last modification timestamp (UTC)';
