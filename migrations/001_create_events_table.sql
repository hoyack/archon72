-- Migration: Create events table with append-only enforcement
-- Story: 1.1 Event Store Schema & Append-Only Enforcement (FR1, FR102-FR104)
-- Date: 2026-01-06
--
-- Constitutional Constraints:
--   CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
--   CT-12: Witnessing creates accountability → Unwitnessed actions are invalid
--   CT-13: Integrity outranks availability → Availability may be sacrificed
--
-- Requirements:
--   FR1: Events must be witnessed
--   FR102: Append-only enforcement - UPDATE, DELETE, TRUNCATE prohibited
--   FR103: Hash chaining (implemented in future story 1.2)
--   FR104: Signature verification (implemented in future story 1.3)

-- ============================================================================
-- TASK 1: Create events table schema (AC1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS events (
    -- Primary identifier
    event_id UUID PRIMARY KEY,

    -- Sequence for ordering (append-only)
    sequence BIGSERIAL UNIQUE NOT NULL,

    -- Event type classification
    event_type TEXT NOT NULL,

    -- Event payload (JSONB for structured data)
    payload JSONB NOT NULL,

    -- Hash chain fields (FR103)
    prev_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,

    -- Signature fields (FR104)
    signature TEXT NOT NULL,

    -- Algorithm versioning for future upgrades
    hash_alg_version SMALLINT NOT NULL DEFAULT 1,
    sig_alg_version SMALLINT NOT NULL DEFAULT 1,

    -- Agent attribution (nullable for system events)
    agent_id TEXT,

    -- Witness attribution (FR1 - required for validity)
    witness_id TEXT NOT NULL,
    witness_signature TEXT NOT NULL,

    -- Dual timestamps (local + authority)
    local_timestamp TIMESTAMPTZ NOT NULL,
    authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index on sequence for efficient ordering queries
CREATE INDEX IF NOT EXISTS idx_events_sequence ON events (sequence);

-- Index on event_type for filtering
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);

-- Index on authority_timestamp for time-range queries
CREATE INDEX IF NOT EXISTS idx_events_authority_timestamp ON events (authority_timestamp);

-- ============================================================================
-- TASK 2: Create append-only enforcement triggers (AC2, AC3, AC4)
-- ============================================================================

-- Function to prevent event modification (FR102)
CREATE OR REPLACE FUNCTION prevent_event_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'FR102: Append-only violation - UPDATE prohibited';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'FR102: Append-only violation - DELETE prohibited';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger for UPDATE prevention (AC2)
DROP TRIGGER IF EXISTS prevent_event_update ON events;
CREATE TRIGGER prevent_event_update
    BEFORE UPDATE ON events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_event_modification();

-- Trigger for DELETE prevention (AC3)
DROP TRIGGER IF EXISTS prevent_event_delete ON events;
CREATE TRIGGER prevent_event_delete
    BEFORE DELETE ON events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_event_modification();

-- TRUNCATE prevention (AC4)
-- PostgreSQL triggers don't fire on TRUNCATE, so we use REVOKE
-- This is the recommended approach per Dev Notes
REVOKE TRUNCATE ON events FROM PUBLIC;

-- Additionally, create an event trigger for extra protection
-- This catches TRUNCATE attempts and raises an explicit error
CREATE OR REPLACE FUNCTION prevent_truncate_events()
RETURNS event_trigger AS $$
DECLARE
    obj record;
BEGIN
    FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
        IF obj.object_identity = 'public.events' AND obj.command_tag = 'TRUNCATE TABLE' THEN
            RAISE EXCEPTION 'FR102: Append-only violation - TRUNCATE prohibited';
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Note: Event triggers require superuser privileges to create
-- In production Supabase, use REVOKE TRUNCATE instead
-- DROP EVENT TRIGGER IF EXISTS prevent_events_truncate;
-- CREATE EVENT TRIGGER prevent_events_truncate
--     ON ddl_command_end
--     WHEN TAG IN ('TRUNCATE')
--     EXECUTE FUNCTION prevent_truncate_events();

-- ============================================================================
-- COMMENTS for documentation
-- ============================================================================

COMMENT ON TABLE events IS 'Constitutional event store (FR1, FR102-FR104). Append-only, immutable.';
COMMENT ON COLUMN events.event_id IS 'Unique identifier for the event (UUID)';
COMMENT ON COLUMN events.sequence IS 'Monotonic sequence number for ordering';
COMMENT ON COLUMN events.event_type IS 'Type classification of the event';
COMMENT ON COLUMN events.payload IS 'Structured event data (JSONB)';
COMMENT ON COLUMN events.prev_hash IS 'Hash of previous event for chain verification';
COMMENT ON COLUMN events.content_hash IS 'Hash of this event content';
COMMENT ON COLUMN events.signature IS 'Cryptographic signature of the event';
COMMENT ON COLUMN events.hash_alg_version IS 'Version of hash algorithm used';
COMMENT ON COLUMN events.sig_alg_version IS 'Version of signature algorithm used';
COMMENT ON COLUMN events.agent_id IS 'ID of the agent that created the event (nullable for system events)';
COMMENT ON COLUMN events.witness_id IS 'ID of the witness that attested the event';
COMMENT ON COLUMN events.witness_signature IS 'Signature of the witness';
COMMENT ON COLUMN events.local_timestamp IS 'Timestamp from the event source';
COMMENT ON COLUMN events.authority_timestamp IS 'Timestamp from the time authority (database)';

COMMENT ON FUNCTION prevent_event_modification() IS 'FR102: Prevents UPDATE and DELETE on events table';
COMMENT ON TRIGGER prevent_event_update ON events IS 'FR102: Blocks UPDATE operations';
COMMENT ON TRIGGER prevent_event_delete ON events IS 'FR102: Blocks DELETE operations';
