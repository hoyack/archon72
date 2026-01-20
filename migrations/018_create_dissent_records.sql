-- Migration 018: Create dissent_records table
-- Story 2B.1: Dissent Recording Service
-- FR-11.8: System SHALL record dissent opinions in 2-1 votes
-- CT-12: Witnessing creates accountability - dissent is witnessed
-- AT-6: Deliberation is collective judgment - minority voice preserved
-- NFR-6.5: Audit trail completeness - complete reconstruction possible

-- Create dissent_records table
CREATE TABLE dissent_records (
    -- Primary key
    dissent_id UUID PRIMARY KEY,

    -- Foreign key to deliberation session
    session_id UUID NOT NULL REFERENCES deliberation_sessions(session_id),

    -- Foreign key to petition (denormalized for query efficiency)
    petition_id UUID NOT NULL REFERENCES petition_submissions(id),

    -- Dissenting archon
    dissent_archon_id UUID NOT NULL,

    -- What the dissenter voted for
    dissent_disposition deliberation_outcome NOT NULL,

    -- The dissenter's reasoning text
    dissent_rationale TEXT NOT NULL,

    -- Blake3 hash of rationale for integrity verification (32 bytes)
    rationale_hash BYTEA NOT NULL,

    -- The winning outcome (what they dissented against)
    majority_disposition deliberation_outcome NOT NULL,

    -- When dissent was recorded
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ==========================================================
    -- Domain invariant constraints (FR-11.8, CT-12)
    -- ==========================================================

    -- Dissent disposition must differ from majority (by definition)
    CONSTRAINT check_dissent_differs_from_majority CHECK (
        dissent_disposition != majority_disposition
    ),

    -- Rationale hash must be exactly 32 bytes (Blake3)
    CONSTRAINT check_rationale_hash_length CHECK (
        length(rationale_hash) = 32
    ),

    -- One dissent per session (2-1 vote has exactly one dissenter)
    CONSTRAINT unique_dissent_per_session UNIQUE (session_id),

    -- One dissent per petition (same logic)
    CONSTRAINT unique_dissent_per_petition UNIQUE (petition_id)
);

-- ==========================================================
-- Indexes for query patterns (NFR-3.2: <50ms queries)
-- ==========================================================

-- Index for finding dissents by archon (AC-6)
CREATE INDEX idx_dissent_records_archon
    ON dissent_records(dissent_archon_id);

-- Index for finding dissents by archon with timestamp (pagination)
CREATE INDEX idx_dissent_records_archon_recorded
    ON dissent_records(dissent_archon_id, recorded_at DESC);

-- Index for petition lookups (AC-5) - unique constraint covers this
-- CREATE INDEX idx_dissent_records_petition_id ON dissent_records(petition_id);

-- Index for session lookups - unique constraint covers this
-- CREATE INDEX idx_dissent_records_session_id ON dissent_records(session_id);

-- ==========================================================
-- Comments for documentation
-- ==========================================================

COMMENT ON TABLE dissent_records IS
'Dissent records from 2-1 deliberation votes (Story 2B.1, FR-11.8)';

COMMENT ON COLUMN dissent_records.dissent_id IS
'UUIDv7 unique identifier for the dissent record';

COMMENT ON COLUMN dissent_records.session_id IS
'Foreign key to deliberation_sessions - one dissent per session';

COMMENT ON COLUMN dissent_records.petition_id IS
'Foreign key to petition_submissions - denormalized for query efficiency';

COMMENT ON COLUMN dissent_records.dissent_archon_id IS
'UUID of the archon who dissented (minority voice in 2-1 vote)';

COMMENT ON COLUMN dissent_records.dissent_disposition IS
'What the dissenter voted for (ACKNOWLEDGE, REFER, or ESCALATE)';

COMMENT ON COLUMN dissent_records.dissent_rationale IS
'Full text of the dissenter''s reasoning';

COMMENT ON COLUMN dissent_records.rationale_hash IS
'Blake3 hash (32 bytes) of rationale for integrity verification';

COMMENT ON COLUMN dissent_records.majority_disposition IS
'The winning outcome that the dissenter disagreed with';

COMMENT ON COLUMN dissent_records.recorded_at IS
'UTC timestamp when dissent was recorded';
