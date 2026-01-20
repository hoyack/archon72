-- Migration: 022_create_acknowledgments_table
-- Story: 3.2 - Acknowledgment Execution Service
-- FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
-- FR-3.3: System SHALL require rationale for REFUSED/NO_ACTION_WARRANTED
-- FR-3.4: System SHALL require reference_petition_id for DUPLICATE
-- NFR-3.2: Fate assignment atomicity (100% single-fate)
-- CT-12: Every action that affects an Archon must be witnessed

BEGIN;

-- Create the acknowledgments table
-- Stores the formal acknowledgment record when a petition receives ACKNOWLEDGED fate
CREATE TABLE acknowledgments (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference to the acknowledged petition (one-to-one relationship)
    petition_id UUID NOT NULL REFERENCES petition_submissions(id) ON DELETE RESTRICT,

    -- Reason code from the enum created in migration 021
    reason_code acknowledgment_reason_enum NOT NULL,

    -- Rationale text (required for REFUSED and NO_ACTION_WARRANTED per FR-3.3)
    rationale TEXT,

    -- Reference to original petition (required for DUPLICATE per FR-3.4)
    reference_petition_id UUID REFERENCES petition_submissions(id),

    -- Archons who voted ACKNOWLEDGE (minimum 2 for supermajority per FR-11.5)
    acknowledging_archon_ids INTEGER[] NOT NULL,

    -- When the acknowledgment was executed
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Blake3 witness hash for CT-12 compliance
    witness_hash TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ==========================================================================
    -- Constraints
    -- ==========================================================================

    -- Ensure at least 2 archons voted ACKNOWLEDGE (FR-11.5 supermajority)
    CONSTRAINT ck_acknowledgments_min_archons
        CHECK (array_length(acknowledging_archon_ids, 1) >= 2),

    -- Ensure rationale is provided for REFUSED and NO_ACTION_WARRANTED (FR-3.3)
    CONSTRAINT ck_acknowledgments_rationale_required
        CHECK (
            (reason_code NOT IN ('REFUSED', 'NO_ACTION_WARRANTED'))
            OR (rationale IS NOT NULL AND length(trim(rationale)) > 0)
        ),

    -- Ensure reference_petition_id is provided for DUPLICATE (FR-3.4)
    CONSTRAINT ck_acknowledgments_reference_required
        CHECK (
            (reason_code != 'DUPLICATE')
            OR (reference_petition_id IS NOT NULL)
        ),

    -- Ensure witness_hash is not empty (CT-12)
    CONSTRAINT ck_acknowledgments_witness_hash
        CHECK (length(trim(witness_hash)) > 0),

    -- One acknowledgment per petition (NFR-3.2 fate atomicity)
    CONSTRAINT uq_acknowledgments_petition
        UNIQUE (petition_id)
);

-- ==========================================================================
-- Indexes
-- ==========================================================================

-- Index for queries by reason code (e.g., finding all REFUSED acknowledgments)
CREATE INDEX idx_acknowledgments_reason_code
    ON acknowledgments(reason_code);

-- Index for time-based queries (e.g., acknowledgments in last 24 hours)
CREATE INDEX idx_acknowledgments_acknowledged_at
    ON acknowledgments(acknowledged_at);

-- Index for finding acknowledgments by reference (for DUPLICATE tracking)
CREATE INDEX idx_acknowledgments_reference_petition
    ON acknowledgments(reference_petition_id)
    WHERE reference_petition_id IS NOT NULL;

-- ==========================================================================
-- Comments
-- ==========================================================================

COMMENT ON TABLE acknowledgments IS
    'Formal acknowledgment records for petitions that receive ACKNOWLEDGED fate. '
    'Per FR-3.1, captures reason code, rationale, and voting archons. '
    'CT-12 compliance via witness_hash.';

COMMENT ON COLUMN acknowledgments.reason_code IS
    'Enumerated reason for acknowledgment per FR-3.2';

COMMENT ON COLUMN acknowledgments.rationale IS
    'Explanation text required for REFUSED/NO_ACTION_WARRANTED per FR-3.3';

COMMENT ON COLUMN acknowledgments.reference_petition_id IS
    'For DUPLICATE acknowledgments, points to the canonical petition per FR-3.4';

COMMENT ON COLUMN acknowledgments.acknowledging_archon_ids IS
    'IDs of the 2+ archons who voted ACKNOWLEDGE per FR-11.5 supermajority';

COMMENT ON COLUMN acknowledgments.witness_hash IS
    'Blake3 hash for CT-12 witnessing compliance';

COMMIT;

-- ==========================================================================
-- Rollback (for reference)
-- ==========================================================================
-- DROP TABLE IF EXISTS acknowledgments;
