-- Migration: Create projections schema for governance derived state
-- Story: consent-gov-1.5: Projection Infrastructure
--
-- This migration creates the projections schema and initial projection tables
-- for the consent-based governance system. Projections are derived views that
-- enable efficient querying of current state without replaying all events.
--
-- CQRS-Lite Pattern (AD-9):
-- - Ledger is the single source of truth (write side)
-- - Projections are derived views for efficient reads (read side)
-- - Projections can be rebuilt from ledger replay at any time
--
-- Schema Separation (AD-8):
-- | Schema         | Purpose                    | Write Access          |
-- |----------------|----------------------------|-----------------------|
-- | ledger.*       | Append-only event storage  | Event Store only      |
-- | projections.*  | Derived state views        | Projection services   |
--
-- References:
-- - governance-architecture.md#Projection Architecture
-- - governance-architecture.md#Initial Projection Set (Locked)

-- ============================================================================
-- SCHEMA CREATION
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS projections;

COMMENT ON SCHEMA projections IS 'Derived state views from governance ledger (CQRS-Lite read side). Can be rebuilt from ledger replay.';

-- ============================================================================
-- INFRASTRUCTURE TABLES
-- ============================================================================

-- Projection checkpoint tracking
-- Tracks the last processed event per projection for incremental updates
CREATE TABLE projections.projection_checkpoints (
    projection_name text PRIMARY KEY,
    last_event_id uuid NOT NULL,
    last_hash text NOT NULL,
    last_sequence bigint NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE projections.projection_checkpoints IS 'Tracks last processed event per projection for incremental updates and recovery.';
COMMENT ON COLUMN projections.projection_checkpoints.projection_name IS 'Name of the projection (e.g., task_states, legitimacy_states)';
COMMENT ON COLUMN projections.projection_checkpoints.last_event_id IS 'UUID of the last successfully processed event';
COMMENT ON COLUMN projections.projection_checkpoints.last_hash IS 'Hash of the last processed event for integrity verification';
COMMENT ON COLUMN projections.projection_checkpoints.last_sequence IS 'Ledger sequence number of the last processed event';

-- Projection apply log (idempotency)
-- Records each event application to prevent duplicate processing
CREATE TABLE projections.projection_applies (
    projection_name text NOT NULL,
    event_id uuid NOT NULL,
    event_hash text NOT NULL,
    sequence bigint NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (projection_name, event_id)
);

COMMENT ON TABLE projections.projection_applies IS 'Event application log for idempotency. Prevents duplicate event processing.';
COMMENT ON COLUMN projections.projection_applies.projection_name IS 'Name of the projection that processed the event';
COMMENT ON COLUMN projections.projection_applies.event_id IS 'UUID of the applied event';
COMMENT ON COLUMN projections.projection_applies.event_hash IS 'Hash of the applied event for integrity verification';
COMMENT ON COLUMN projections.projection_applies.sequence IS 'Ledger sequence number of the applied event';

-- Index for querying applied events by sequence (for rebuild verification)
CREATE INDEX idx_projection_applies_sequence ON projections.projection_applies (projection_name, sequence);

-- ============================================================================
-- PROJECTION TABLES
-- ============================================================================

-- 1. Task State Projection
-- Tracks current state of governance tasks (from executive.task.* events)
CREATE TABLE projections.task_states (
    task_id uuid PRIMARY KEY,
    current_state text NOT NULL,
    earl_id text NOT NULL,
    cluster_id text,
    task_type text,
    created_at timestamptz NOT NULL,
    state_entered_at timestamptz NOT NULL,
    last_event_sequence bigint NOT NULL,
    last_event_hash text NOT NULL,
    updated_at timestamptz NOT NULL
);

COMMENT ON TABLE projections.task_states IS 'Task lifecycle state projection. Derived from executive.task.* events.';
COMMENT ON COLUMN projections.task_states.task_id IS 'Unique identifier for the task';
COMMENT ON COLUMN projections.task_states.current_state IS 'Current task state (pending, authorized, activated, accepted, completed, declined, expired)';
COMMENT ON COLUMN projections.task_states.earl_id IS 'ID of the Earl assigned to execute the task';
COMMENT ON COLUMN projections.task_states.cluster_id IS 'Optional cluster grouping for related tasks';
COMMENT ON COLUMN projections.task_states.task_type IS 'Type classification of the task';
COMMENT ON COLUMN projections.task_states.created_at IS 'When the task was first created';
COMMENT ON COLUMN projections.task_states.state_entered_at IS 'When the current state was entered';
COMMENT ON COLUMN projections.task_states.last_event_sequence IS 'Ledger sequence of the last event that updated this record';
COMMENT ON COLUMN projections.task_states.last_event_hash IS 'Hash of the last event that updated this record';

-- Indexes for common query patterns
CREATE INDEX idx_task_states_current_state ON projections.task_states (current_state);
CREATE INDEX idx_task_states_earl_id ON projections.task_states (earl_id);
CREATE INDEX idx_task_states_cluster_id ON projections.task_states (cluster_id) WHERE cluster_id IS NOT NULL;

-- 2. Legitimacy State Projection
-- Tracks legitimacy bands for entities (from legitimacy.* events)
CREATE TABLE projections.legitimacy_states (
    entity_id text PRIMARY KEY,
    entity_type text NOT NULL,
    current_band text NOT NULL,
    band_entered_at timestamptz NOT NULL,
    violation_count int NOT NULL DEFAULT 0,
    last_violation_at timestamptz,
    last_restoration_at timestamptz,
    last_event_sequence bigint NOT NULL,
    updated_at timestamptz NOT NULL
);

COMMENT ON TABLE projections.legitimacy_states IS 'Entity legitimacy band projection. Derived from legitimacy.* events.';
COMMENT ON COLUMN projections.legitimacy_states.entity_id IS 'ID of the entity (archon, officer, system component)';
COMMENT ON COLUMN projections.legitimacy_states.entity_type IS 'Type of entity (archon, officer, system)';
COMMENT ON COLUMN projections.legitimacy_states.current_band IS 'Current legitimacy band (full, provisional, suspended)';
COMMENT ON COLUMN projections.legitimacy_states.band_entered_at IS 'When the current band was entered';
COMMENT ON COLUMN projections.legitimacy_states.violation_count IS 'Total violation count affecting legitimacy';
COMMENT ON COLUMN projections.legitimacy_states.last_violation_at IS 'When the last violation occurred';
COMMENT ON COLUMN projections.legitimacy_states.last_restoration_at IS 'When legitimacy was last restored';

-- Indexes for common query patterns
CREATE INDEX idx_legitimacy_states_current_band ON projections.legitimacy_states (current_band);
CREATE INDEX idx_legitimacy_states_entity_type ON projections.legitimacy_states (entity_type);

-- 3. Panel Registry Projection
-- Tracks Prince panels for violation adjudication (from judicial.panel.* events)
CREATE TABLE projections.panel_registry (
    panel_id uuid PRIMARY KEY,
    panel_status text NOT NULL,
    violation_id uuid NOT NULL,
    prince_ids text[] NOT NULL,
    petitioner_id text,
    convened_at timestamptz,
    finding_issued_at timestamptz,
    finding_outcome text,
    last_event_sequence bigint NOT NULL,
    updated_at timestamptz NOT NULL
);

COMMENT ON TABLE projections.panel_registry IS 'Prince panel registry projection. Derived from judicial.panel.* events.';
COMMENT ON COLUMN projections.panel_registry.panel_id IS 'Unique identifier for the panel';
COMMENT ON COLUMN projections.panel_registry.panel_status IS 'Panel status (pending, convened, deliberating, finding_issued, dissolved)';
COMMENT ON COLUMN projections.panel_registry.violation_id IS 'ID of the violation being adjudicated';
COMMENT ON COLUMN projections.panel_registry.prince_ids IS 'Array of Prince IDs serving on the panel';
COMMENT ON COLUMN projections.panel_registry.petitioner_id IS 'ID of the entity that petitioned for the panel';
COMMENT ON COLUMN projections.panel_registry.convened_at IS 'When the panel was convened';
COMMENT ON COLUMN projections.panel_registry.finding_issued_at IS 'When the finding was issued';
COMMENT ON COLUMN projections.panel_registry.finding_outcome IS 'Outcome of the finding (upheld, overturned, remanded)';

-- Indexes for common query patterns
CREATE INDEX idx_panel_registry_status ON projections.panel_registry (panel_status);
CREATE INDEX idx_panel_registry_violation_id ON projections.panel_registry (violation_id);

-- 4. Petition Index Projection
-- Tracks petitions for exit, dignity, etc. (from petition.* events)
CREATE TABLE projections.petition_index (
    petition_id uuid PRIMARY KEY,
    petition_type text NOT NULL,
    subject_entity_id text NOT NULL,
    petitioner_id text NOT NULL,
    current_status text NOT NULL,
    filed_at timestamptz NOT NULL,
    acknowledged_at timestamptz,
    resolved_at timestamptz,
    resolution_outcome text,
    last_event_sequence bigint NOT NULL,
    updated_at timestamptz NOT NULL
);

COMMENT ON TABLE projections.petition_index IS 'Petition tracking projection. Derived from petition.* events.';
COMMENT ON COLUMN projections.petition_index.petition_id IS 'Unique identifier for the petition';
COMMENT ON COLUMN projections.petition_index.petition_type IS 'Type of petition (exit, dignity_restoration, review)';
COMMENT ON COLUMN projections.petition_index.subject_entity_id IS 'ID of the entity the petition concerns';
COMMENT ON COLUMN projections.petition_index.petitioner_id IS 'ID of the entity filing the petition';
COMMENT ON COLUMN projections.petition_index.current_status IS 'Current status (filed, acknowledged, under_review, resolved)';
COMMENT ON COLUMN projections.petition_index.filed_at IS 'When the petition was filed';
COMMENT ON COLUMN projections.petition_index.acknowledged_at IS 'When the petition was acknowledged';
COMMENT ON COLUMN projections.petition_index.resolved_at IS 'When the petition was resolved';
COMMENT ON COLUMN projections.petition_index.resolution_outcome IS 'Outcome of resolution (granted, denied, withdrawn)';

-- Indexes for common query patterns
CREATE INDEX idx_petition_index_type ON projections.petition_index (petition_type);
CREATE INDEX idx_petition_index_status ON projections.petition_index (current_status);
CREATE INDEX idx_petition_index_subject ON projections.petition_index (subject_entity_id);
CREATE INDEX idx_petition_index_petitioner ON projections.petition_index (petitioner_id);

-- 5. Actor Registry Projection
-- Tracks known actors in the governance system (from actor.* events)
CREATE TABLE projections.actor_registry (
    actor_id text PRIMARY KEY,
    actor_type text NOT NULL,
    branch text NOT NULL,
    rank text,
    display_name text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL,
    deactivated_at timestamptz,
    last_event_sequence bigint NOT NULL,
    updated_at timestamptz NOT NULL
);

COMMENT ON TABLE projections.actor_registry IS 'Actor registry projection. Derived from actor.* events. Used for write-time validation.';
COMMENT ON COLUMN projections.actor_registry.actor_id IS 'Unique identifier for the actor';
COMMENT ON COLUMN projections.actor_registry.actor_type IS 'Type of actor (archon, king, president, duke, earl, prince, marquis, knight)';
COMMENT ON COLUMN projections.actor_registry.branch IS 'Governance branch (legislative, executive, judicial, advisory, witness)';
COMMENT ON COLUMN projections.actor_registry.rank IS 'Optional rank/tier within the actor type';
COMMENT ON COLUMN projections.actor_registry.display_name IS 'Human-readable name for the actor';
COMMENT ON COLUMN projections.actor_registry.active IS 'Whether the actor is currently active';
COMMENT ON COLUMN projections.actor_registry.created_at IS 'When the actor was registered';
COMMENT ON COLUMN projections.actor_registry.deactivated_at IS 'When the actor was deactivated (if applicable)';

-- Indexes for common query patterns
CREATE INDEX idx_actor_registry_type ON projections.actor_registry (actor_type);
CREATE INDEX idx_actor_registry_branch ON projections.actor_registry (branch);
CREATE INDEX idx_actor_registry_active ON projections.actor_registry (active) WHERE active = true;

-- ============================================================================
-- ROLE-BASED ACCESS (Schema Isolation)
-- ============================================================================

-- Note: In production, create a projection_service role with:
-- GRANT ALL ON SCHEMA projections TO projection_service;
-- GRANT ALL ON ALL TABLES IN SCHEMA projections TO projection_service;
-- REVOKE ALL ON SCHEMA ledger FROM projection_service;
-- REVOKE ALL ON ALL TABLES IN SCHEMA ledger FROM projection_service;
--
-- This ensures projections cannot modify the ledger (Constitutional Constraint).
