-- Migration 017: Create deliberation_sessions table
-- Story 2A.1: Deliberation Session Domain Model
-- FR-11.1: System SHALL assign exactly 3 Marquis-rank Archons
-- FR-11.4: Deliberation SHALL follow structured protocol
-- NFR-10.3: Consensus determinism - 100% reproducible
-- NFR-10.5: Concurrent deliberations - 100+ simultaneous sessions

-- Create enum types for deliberation
CREATE TYPE deliberation_phase AS ENUM (
    'ASSESS',
    'POSITION',
    'CROSS_EXAMINE',
    'VOTE',
    'COMPLETE'
);

CREATE TYPE deliberation_outcome AS ENUM (
    'ACKNOWLEDGE',
    'REFER',
    'ESCALATE'
);

-- Create deliberation_sessions table
CREATE TABLE deliberation_sessions (
    -- Primary key
    session_id UUID PRIMARY KEY,

    -- Foreign key to petition (one session per petition)
    petition_id UUID NOT NULL UNIQUE REFERENCES petition_submissions(id),

    -- Assigned archons (exactly 3, ordered)
    assigned_archons UUID[3] NOT NULL,

    -- Current phase in deliberation protocol
    phase deliberation_phase NOT NULL DEFAULT 'ASSESS',

    -- Phase transcripts (phase -> Blake3 hash)
    phase_transcripts JSONB NOT NULL DEFAULT '{}',

    -- Archon votes (archon_id -> outcome)
    votes JSONB NOT NULL DEFAULT '{}',

    -- Final deliberation outcome (NULL until resolved)
    outcome deliberation_outcome,

    -- Dissenting archon in 2-1 vote (NULL if unanimous)
    dissent_archon_id UUID,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Optimistic locking version (NFR-3.2)
    version INTEGER NOT NULL DEFAULT 1,

    -- ==========================================================
    -- Domain invariant constraints (FR-11.1, FR-11.4, AT-6)
    -- ==========================================================

    -- Exactly 3 archons required (FR-11.1)
    CONSTRAINT check_exactly_3_archons CHECK (
        array_length(assigned_archons, 1) = 3
    ),

    -- No duplicate archons (FR-11.1)
    CONSTRAINT check_unique_archons CHECK (
        assigned_archons[1] IS DISTINCT FROM assigned_archons[2] AND
        assigned_archons[2] IS DISTINCT FROM assigned_archons[3] AND
        assigned_archons[1] IS DISTINCT FROM assigned_archons[3]
    ),

    -- Completed sessions must have outcome (FR-11.4 terminal state)
    CONSTRAINT check_completed_has_outcome CHECK (
        (phase = 'COMPLETE' AND outcome IS NOT NULL) OR
        (phase != 'COMPLETE')
    ),

    -- Completed sessions must have completed_at
    CONSTRAINT check_completed_has_timestamp CHECK (
        (phase = 'COMPLETE' AND completed_at IS NOT NULL) OR
        (phase != 'COMPLETE')
    ),

    -- Dissent archon must be one of the assigned archons
    CONSTRAINT check_dissent_is_assigned CHECK (
        dissent_archon_id IS NULL OR
        dissent_archon_id = assigned_archons[1] OR
        dissent_archon_id = assigned_archons[2] OR
        dissent_archon_id = assigned_archons[3]
    ),

    -- Version must be positive
    CONSTRAINT check_version_positive CHECK (version > 0)
);

-- ==========================================================
-- Indexes for query patterns (NFR-10.5: 100+ concurrent)
-- ==========================================================

-- Index for petition lookups (unique constraint already creates this)
-- CREATE INDEX idx_deliberation_sessions_petition_id ON deliberation_sessions(petition_id);

-- Index for finding in-progress sessions by phase
CREATE INDEX idx_deliberation_sessions_phase_active
    ON deliberation_sessions(phase)
    WHERE phase != 'COMPLETE';

-- Index for finding sessions by creation time (timeout detection)
CREATE INDEX idx_deliberation_sessions_created_at
    ON deliberation_sessions(created_at);

-- Index for incomplete sessions by creation time (timeout queries)
CREATE INDEX idx_deliberation_sessions_incomplete_created
    ON deliberation_sessions(created_at)
    WHERE phase != 'COMPLETE';

-- Index for finding sessions by assigned archon
-- (useful for checking archon workload/availability)
CREATE INDEX idx_deliberation_sessions_archon1
    ON deliberation_sessions((assigned_archons[1]));
CREATE INDEX idx_deliberation_sessions_archon2
    ON deliberation_sessions((assigned_archons[2]));
CREATE INDEX idx_deliberation_sessions_archon3
    ON deliberation_sessions((assigned_archons[3]));

-- ==========================================================
-- Comments for documentation
-- ==========================================================

COMMENT ON TABLE deliberation_sessions IS
'Three Fates mini-Conclave deliberation sessions (Story 2A.1, FR-11.1, FR-11.4)';

COMMENT ON COLUMN deliberation_sessions.session_id IS
'UUIDv7 unique identifier for the deliberation session';

COMMENT ON COLUMN deliberation_sessions.petition_id IS
'Foreign key to petition_submissions - one session per petition';

COMMENT ON COLUMN deliberation_sessions.assigned_archons IS
'Exactly 3 Marquis-rank Archon UUIDs (ordered, FR-11.1)';

COMMENT ON COLUMN deliberation_sessions.phase IS
'Current phase: ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE -> COMPLETE (FR-11.4)';

COMMENT ON COLUMN deliberation_sessions.phase_transcripts IS
'Map of phase to Blake3 transcript hash (NFR-10.4 witness completeness)';

COMMENT ON COLUMN deliberation_sessions.votes IS
'Map of archon_id (string) to outcome for consensus resolution';

COMMENT ON COLUMN deliberation_sessions.outcome IS
'Final outcome: ACKNOWLEDGE, REFER, or ESCALATE (Three Fates)';

COMMENT ON COLUMN deliberation_sessions.dissent_archon_id IS
'UUID of dissenting archon in 2-1 vote (NULL if unanimous, FR-11.8)';

COMMENT ON COLUMN deliberation_sessions.version IS
'Optimistic locking version for concurrent access (NFR-3.2)';
