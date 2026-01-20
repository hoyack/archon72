-- Migration 024: Create co_signs table
-- Story 5.1: Co-Sign Domain Model & Schema
-- Constitutional: FR-6.2 (unique constraint), NFR-3.5 (0 duplicates), NFR-6.4 (attribution)
--
-- This table stores co-signatures (support signatures) from Seekers on petitions.
-- The unique constraint on (petition_id, signer_id) is CRITICAL for preventing
-- duplicate signatures (NFR-3.5: 0 duplicate signatures ever exist).

CREATE TABLE co_signs (
    -- Primary key (UUIDv7)
    cosign_id UUID PRIMARY KEY,

    -- Petition relationship (FR-6.2)
    -- ON DELETE CASCADE ensures co-signs are removed when petition is deleted
    petition_id UUID NOT NULL REFERENCES petition_submissions(id) ON DELETE CASCADE,

    -- Signer identity (NFR-6.4 - full signer list queryable)
    signer_id UUID NOT NULL,

    -- Timestamp (UTC timezone-aware)
    signed_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Identity verification status (Story 5.3 - NFR-5.2)
    -- Default FALSE, set to TRUE after identity verification
    identity_verified BOOLEAN NOT NULL DEFAULT FALSE,

    -- Content hash for witness integrity (CT-12)
    -- BLAKE3 produces 32-byte (256-bit) hashes
    content_hash BYTEA NOT NULL,

    -- Witness event reference (set after witnessing)
    -- NULL until the co-sign event is witnessed
    witness_event_id UUID,

    -- CRITICAL: Unique constraint (FR-6.2, NFR-3.5)
    -- Ensures 0 duplicate signatures ever exist
    -- This is the PRIMARY mechanism for enforcing the constitutional requirement
    CONSTRAINT uq_co_signs_petition_signer UNIQUE (petition_id, signer_id),

    -- Validate content_hash is BLAKE3 (32 bytes)
    CONSTRAINT chk_co_signs_content_hash_length CHECK (octet_length(content_hash) = 32)
);

-- Index for co-signer count queries (FR-6.4, FR-6.5)
-- Optimizes: SELECT COUNT(*) FROM co_signs WHERE petition_id = ?
-- Critical for escalation threshold checking (Story 5.5)
CREATE INDEX idx_co_signs_petition_id ON co_signs(petition_id);

-- Index for SYBIL-1 rate limiting queries (FR-6.6)
-- Optimizes: SELECT COUNT(*) FROM co_signs WHERE signer_id = ? AND signed_at > ?
-- Critical for anti-Sybil rate limiting (Story 5.4)
CREATE INDEX idx_co_signs_signer_id ON co_signs(signer_id);

-- Index for time-based queries
-- Optimizes: SELECT * FROM co_signs WHERE signed_at > ? ORDER BY signed_at
CREATE INDEX idx_co_signs_signed_at ON co_signs(signed_at);

-- Documentation
COMMENT ON TABLE co_signs IS 'Petition co-signatures from Seekers (FR-6.2, NFR-3.5, NFR-6.4). Each row represents a unique support signature.';
COMMENT ON COLUMN co_signs.cosign_id IS 'Unique identifier for this co-signature (UUIDv7)';
COMMENT ON COLUMN co_signs.petition_id IS 'Reference to the petition being co-signed (FK to petition_submissions)';
COMMENT ON COLUMN co_signs.signer_id IS 'UUID of the Seeker adding their support';
COMMENT ON COLUMN co_signs.signed_at IS 'When the co-signature was recorded (UTC timezone-aware)';
COMMENT ON COLUMN co_signs.identity_verified IS 'Whether signer identity was verified (Story 5.3, NFR-5.2)';
COMMENT ON COLUMN co_signs.content_hash IS 'BLAKE3 hash for witness integrity (CT-12, 32 bytes)';
COMMENT ON COLUMN co_signs.witness_event_id IS 'Reference to witness event (set after witnessing, CT-12)';
COMMENT ON CONSTRAINT uq_co_signs_petition_signer ON co_signs IS 'FR-6.2, NFR-3.5: No duplicate (petition_id, signer_id) pairs - CONSTITUTIONAL REQUIREMENT';
COMMENT ON CONSTRAINT chk_co_signs_content_hash_length ON co_signs IS 'Validates BLAKE3 hash is exactly 32 bytes';
