-- Migration: Create ledger schema for consent-based governance events
-- Story: consent-gov-1.2: Append-Only Ledger Port & Adapter
-- Date: 2026-01-16
--
-- Constitutional Constraints:
--   NFR-CONST-01: Append-only enforcement - NO update/delete allowed
--   AD-1: Event sourcing as canonical model
--   AD-8: Same DB, schema isolation (ledger.* separate from public.*)
--   AD-11: Global monotonic sequence via IDENTITY column
--   AD-15: Branch derived from event_type at write-time
--
-- Architectural Decisions:
--   - ledger.* schema isolates governance events from public.* tables
--   - Sequence is GENERATED ALWAYS AS IDENTITY for monotonic ordering
--   - Branch is derived from event_type.split('.')[0] via trigger
--   - Hash fields (prev_hash, hash) will be added in story consent-gov-1-3

-- ============================================================================
-- TASK 1: Create ledger schema (AC5 - Schema Isolation)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS ledger;

COMMENT ON SCHEMA ledger IS 'Consent-based governance event ledger. Append-only, immutable. Write access: GovernanceLedgerAdapter only.';

-- ============================================================================
-- TASK 2: Create governance_events table (AC1, AC3, AC4)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ledger.governance_events (
    -- Global monotonic sequence (AC4, AD-11)
    -- GENERATED ALWAYS AS IDENTITY ensures database-assigned sequence
    sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Event identification
    event_id UUID NOT NULL UNIQUE,

    -- Event classification (branch.noun.verb pattern per AD-5)
    event_type TEXT NOT NULL,

    -- Branch derived from event_type (AD-15)
    -- Populated by trigger, not trusted from client
    branch TEXT NOT NULL,

    -- Schema version for deterministic replay (AD-17)
    schema_version TEXT NOT NULL,

    -- Timestamp when event occurred (UTC)
    timestamp TIMESTAMPTZ NOT NULL,

    -- Actor attribution (archon or officer ID)
    actor_id TEXT NOT NULL,

    -- Request correlation ID for tracing
    trace_id TEXT NOT NULL,

    -- Domain-specific event data
    payload JSONB NOT NULL,

    -- Ledger write timestamp (authority time)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraint: event_type must match branch.noun.verb pattern
    CONSTRAINT chk_event_type_format CHECK (
        event_type ~ '^[a-z]+\.[a-z]+\.[a-z_]+$'
    ),

    -- Constraint: branch must match first segment of event_type
    CONSTRAINT chk_branch_matches_event_type CHECK (
        branch = split_part(event_type, '.', 1)
    ),

    -- Constraint: schema_version must be semver format
    CONSTRAINT chk_schema_version_format CHECK (
        schema_version ~ '^\d+\.\d+\.\d+$'
    )
);

-- ============================================================================
-- TASK 3: Create indexes for efficient queries (AC3)
-- ============================================================================

-- Index on event_id for lookups
CREATE INDEX IF NOT EXISTS idx_governance_events_event_id
    ON ledger.governance_events (event_id);

-- Composite index on branch + sequence for branch-filtered queries
CREATE INDEX IF NOT EXISTS idx_governance_events_branch_sequence
    ON ledger.governance_events (branch, sequence);

-- Index on event_type for type-filtered queries
CREATE INDEX IF NOT EXISTS idx_governance_events_event_type
    ON ledger.governance_events (event_type);

-- Index on timestamp for time-range queries
CREATE INDEX IF NOT EXISTS idx_governance_events_timestamp
    ON ledger.governance_events (timestamp);

-- Index on actor_id for actor-based queries
CREATE INDEX IF NOT EXISTS idx_governance_events_actor_id
    ON ledger.governance_events (actor_id);

-- ============================================================================
-- TASK 4: Create append-only enforcement triggers (AC2, NFR-CONST-01)
-- ============================================================================

-- Function to prevent event modification
CREATE OR REPLACE FUNCTION ledger.prevent_governance_event_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'NFR-CONST-01: Append-only violation on ledger.governance_events - UPDATE prohibited. Events are immutable.';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'NFR-CONST-01: Append-only violation on ledger.governance_events - DELETE prohibited. Events are permanent.';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger for UPDATE prevention
DROP TRIGGER IF EXISTS prevent_governance_event_update ON ledger.governance_events;
CREATE TRIGGER prevent_governance_event_update
    BEFORE UPDATE ON ledger.governance_events
    FOR EACH ROW
    EXECUTE FUNCTION ledger.prevent_governance_event_modification();

-- Trigger for DELETE prevention
DROP TRIGGER IF EXISTS prevent_governance_event_delete ON ledger.governance_events;
CREATE TRIGGER prevent_governance_event_delete
    BEFORE DELETE ON ledger.governance_events
    FOR EACH ROW
    EXECUTE FUNCTION ledger.prevent_governance_event_modification();

-- TRUNCATE prevention via REVOKE
REVOKE TRUNCATE ON ledger.governance_events FROM PUBLIC;

-- ============================================================================
-- TASK 5: Create branch derivation trigger (AD-15)
-- ============================================================================

-- Function to derive and validate branch from event_type
CREATE OR REPLACE FUNCTION ledger.derive_branch_from_event_type()
RETURNS TRIGGER AS $$
DECLARE
    derived_branch TEXT;
BEGIN
    -- Derive branch from event_type (first segment before '.')
    derived_branch := split_part(NEW.event_type, '.', 1);

    -- Validate event_type has correct format
    IF derived_branch = '' OR derived_branch = NEW.event_type THEN
        RAISE EXCEPTION 'AD-5: Invalid event_type format. Expected branch.noun.verb pattern, got: %', NEW.event_type;
    END IF;

    -- Override any client-provided branch value
    -- Per AD-15: Branch is derived at write-time, NEVER trusted from caller
    NEW.branch := derived_branch;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to derive branch before insert
DROP TRIGGER IF EXISTS derive_branch_before_insert ON ledger.governance_events;
CREATE TRIGGER derive_branch_before_insert
    BEFORE INSERT ON ledger.governance_events
    FOR EACH ROW
    EXECUTE FUNCTION ledger.derive_branch_from_event_type();

-- ============================================================================
-- TASK 6: Comments for documentation
-- ============================================================================

COMMENT ON TABLE ledger.governance_events IS
    'Consent-based governance event ledger (AD-1, NFR-CONST-01). Append-only, immutable. Each event represents a governance action with full audit trail.';

COMMENT ON COLUMN ledger.governance_events.sequence IS
    'Global monotonic sequence number (AD-11). Assigned by database, provides total ordering.';

COMMENT ON COLUMN ledger.governance_events.event_id IS
    'Unique event identifier (UUID). Generated by application.';

COMMENT ON COLUMN ledger.governance_events.event_type IS
    'Event classification following branch.noun.verb pattern (AD-5). E.g., executive.task.accepted';

COMMENT ON COLUMN ledger.governance_events.branch IS
    'Governance branch derived from event_type (AD-15). Never trusted from caller.';

COMMENT ON COLUMN ledger.governance_events.schema_version IS
    'Semver for deterministic replay (AD-17). Format: X.Y.Z';

COMMENT ON COLUMN ledger.governance_events.timestamp IS
    'When the event occurred (UTC). From event source, not database.';

COMMENT ON COLUMN ledger.governance_events.actor_id IS
    'ID of archon or officer that caused the event. Required for accountability (CT-12).';

COMMENT ON COLUMN ledger.governance_events.trace_id IS
    'Request correlation ID for distributed tracing.';

COMMENT ON COLUMN ledger.governance_events.payload IS
    'Domain-specific event data (JSONB). Structure varies by event_type.';

COMMENT ON COLUMN ledger.governance_events.created_at IS
    'Ledger write timestamp (database authority time).';

COMMENT ON FUNCTION ledger.prevent_governance_event_modification() IS
    'NFR-CONST-01: Prevents UPDATE and DELETE on governance_events table.';

COMMENT ON FUNCTION ledger.derive_branch_from_event_type() IS
    'AD-15: Derives branch from event_type at write-time. Never trusts client-provided branch.';
