-- Migration 020: Create transcript_contents table
-- Story 2B.5: Transcript Preservation & Hash-Referencing
-- FR-11.7: Hash-referenced preservation requirement
-- CT-12: Witnessing creates accountability - hash enables verification
-- NFR-6.5: Audit trail completeness - transcripts retrievable by hash
-- NFR-4.2: Hash guarantees immutability (append-only semantic)
-- NFR-10.4: Witness completeness - 100% utterances witnessed

-- Create transcript_contents table (content-addressed storage)
CREATE TABLE transcript_contents (
    -- Primary key is the content hash itself (content-addressed)
    content_hash BYTEA PRIMARY KEY,

    -- The transcript content (UTF-8 text)
    content TEXT NOT NULL,

    -- Size of content in bytes (for validation)
    content_size INTEGER NOT NULL,

    -- When the transcript was stored
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Optional storage path for filesystem-backed implementations
    storage_path TEXT,

    -- ==========================================================
    -- Domain invariant constraints (FR-11.7, NFR-4.2)
    -- ==========================================================

    -- Content hash must be exactly 32 bytes (Blake3)
    CONSTRAINT check_content_hash_length CHECK (
        length(content_hash) = 32
    ),

    -- Content size must match actual content
    CONSTRAINT check_content_size_matches CHECK (
        length(content::bytea) = content_size
    ),

    -- Content cannot be empty
    CONSTRAINT check_content_not_empty CHECK (
        content != ''
    ),

    -- Content size must be positive
    CONSTRAINT check_content_size_positive CHECK (
        content_size > 0
    )
);

-- ==========================================================
-- Append-only protection trigger (NFR-4.2)
-- Transcripts are immutable once stored
-- ==========================================================

CREATE OR REPLACE FUNCTION prevent_transcript_modification()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent updates to any column
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'transcript_contents is append-only: updates not allowed (NFR-4.2)';
    END IF;

    -- Prevent deletes
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'transcript_contents is append-only: deletes not allowed (NFR-4.2)';
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_transcript_immutability
    BEFORE UPDATE OR DELETE ON transcript_contents
    FOR EACH ROW
    EXECUTE FUNCTION prevent_transcript_modification();

-- ==========================================================
-- Indexes for query patterns (NFR-3.2: <50ms queries)
-- ==========================================================

-- Index for finding transcripts by storage time (for audit queries)
CREATE INDEX idx_transcript_contents_stored_at
    ON transcript_contents(stored_at DESC);

-- Index for finding transcripts by size (for capacity queries)
CREATE INDEX idx_transcript_contents_size
    ON transcript_contents(content_size DESC);

-- ==========================================================
-- Comments for documentation
-- ==========================================================

COMMENT ON TABLE transcript_contents IS
'Content-addressed transcript storage (Story 2B.5, FR-11.7). Immutable once written.';

COMMENT ON COLUMN transcript_contents.content_hash IS
'Blake3 hash (32 bytes) of content - serves as primary key for content-addressing';

COMMENT ON COLUMN transcript_contents.content IS
'Full UTF-8 text content of the transcript';

COMMENT ON COLUMN transcript_contents.content_size IS
'Size of content in bytes - stored for validation and capacity tracking';

COMMENT ON COLUMN transcript_contents.stored_at IS
'UTC timestamp when transcript was first stored';

COMMENT ON COLUMN transcript_contents.storage_path IS
'Optional filesystem path for hybrid storage implementations';

COMMENT ON TRIGGER enforce_transcript_immutability ON transcript_contents IS
'Enforces append-only semantic per NFR-4.2 - no updates or deletes allowed';
