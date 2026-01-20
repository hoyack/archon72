-- Migration 023: Create referrals table (Story 4.1, FR-4.1, FR-4.2)
--
-- Constitutional Constraints:
-- - FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
-- - FR-4.2: System SHALL assign referral deadline (3 cycles default)
-- - NFR-3.4: Referral timeout reliability - 100% timeouts fire
-- - NFR-4.4: Referral deadline persistence - survives scheduler restart
--
-- This migration creates the referrals table for tracking Knight referral workflow.

-- Create referral_status enum type
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'referral_status') THEN
        CREATE TYPE referral_status AS ENUM (
            'pending',      -- Awaiting Knight assignment
            'assigned',     -- Knight has been assigned
            'in_review',    -- Knight is actively reviewing
            'completed',    -- Knight submitted recommendation
            'expired'       -- Deadline passed without recommendation
        );
        COMMENT ON TYPE referral_status IS 'Referral lifecycle states (FR-4.1, FR-4.2)';
    END IF;
END
$$;

-- Create referral_recommendation enum type
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'referral_recommendation') THEN
        CREATE TYPE referral_recommendation AS ENUM (
            'acknowledge',  -- Recommend acknowledging the petition
            'escalate'      -- Recommend escalating to King
        );
        COMMENT ON TYPE referral_recommendation IS 'Knight recommendation options (FR-4.6)';
    END IF;
END
$$;

-- Create referrals table
CREATE TABLE IF NOT EXISTS referrals (
    -- Primary key (UUIDv7 for time-ordered IDs)
    id UUID PRIMARY KEY,

    -- Foreign key to petition
    petition_id UUID NOT NULL REFERENCES petition_submissions(id) ON DELETE RESTRICT,

    -- Realm routing (references realms table)
    realm_id UUID NOT NULL REFERENCES realms(id) ON DELETE RESTRICT,

    -- Knight assignment (nullable until assigned)
    assigned_knight_id UUID,

    -- Status tracking
    status referral_status NOT NULL DEFAULT 'pending',

    -- Deadline management (FR-4.2)
    deadline TIMESTAMPTZ NOT NULL,
    extensions_granted INTEGER NOT NULL DEFAULT 0,

    -- Recommendation (FR-4.6)
    recommendation referral_recommendation,
    rationale TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT referrals_extensions_valid CHECK (extensions_granted >= 0 AND extensions_granted <= 2),
    CONSTRAINT referrals_recommendation_requires_rationale CHECK (
        (recommendation IS NULL AND rationale IS NULL) OR
        (recommendation IS NOT NULL AND rationale IS NOT NULL AND LENGTH(TRIM(rationale)) > 0)
    ),
    CONSTRAINT referrals_completed_requires_recommendation CHECK (
        status != 'completed' OR recommendation IS NOT NULL
    ),
    CONSTRAINT referrals_completed_requires_timestamp CHECK (
        status != 'completed' OR completed_at IS NOT NULL
    ),
    CONSTRAINT referrals_assigned_requires_knight CHECK (
        status IN ('pending', 'expired') OR assigned_knight_id IS NOT NULL
    )
);

-- Performance indexes
-- Index for finding pending referrals by deadline (for timeout job)
CREATE INDEX IF NOT EXISTS idx_referrals_status_deadline
    ON referrals (status, deadline)
    WHERE status NOT IN ('completed', 'expired');

-- Index for finding referrals by assigned Knight and status
CREATE INDEX IF NOT EXISTS idx_referrals_knight_id_status
    ON referrals (assigned_knight_id, status)
    WHERE assigned_knight_id IS NOT NULL;

-- Index for finding referrals by realm and status (for load balancing)
CREATE INDEX IF NOT EXISTS idx_referrals_realm_id_status
    ON referrals (realm_id, status);

-- Index for finding referrals by petition
CREATE INDEX IF NOT EXISTS idx_referrals_petition_id
    ON referrals (petition_id);

-- Index for counting concurrent referrals per Knight (FR-4.7)
CREATE INDEX IF NOT EXISTS idx_referrals_knight_concurrent
    ON referrals (assigned_knight_id)
    WHERE status IN ('assigned', 'in_review');

-- Column comments
COMMENT ON TABLE referrals IS 'Knight referral workflow (Story 4.1, FR-4.1, FR-4.2)';
COMMENT ON COLUMN referrals.id IS 'Unique referral identifier (UUIDv7)';
COMMENT ON COLUMN referrals.petition_id IS 'Foreign key to petition being referred';
COMMENT ON COLUMN referrals.realm_id IS 'Target realm for Knight routing';
COMMENT ON COLUMN referrals.assigned_knight_id IS 'Knight assigned to review (nullable until assignment)';
COMMENT ON COLUMN referrals.status IS 'Current referral lifecycle status';
COMMENT ON COLUMN referrals.deadline IS 'Deadline for Knight to complete review (UTC)';
COMMENT ON COLUMN referrals.extensions_granted IS 'Number of deadline extensions granted (max 2 per FR-4.4)';
COMMENT ON COLUMN referrals.recommendation IS 'Knight''s recommendation (ACKNOWLEDGE or ESCALATE)';
COMMENT ON COLUMN referrals.rationale IS 'Knight''s rationale for recommendation (required)';
COMMENT ON COLUMN referrals.created_at IS 'When the referral was created (UTC)';
COMMENT ON COLUMN referrals.completed_at IS 'When the referral was completed/expired (UTC)';
