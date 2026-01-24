-- Migration 033: Create META Petition Queue Table (Story 8.5, FR-10.4)
--
-- This migration creates the queue table for META petitions awaiting
-- High Archon review. META petitions bypass normal Three Fates deliberation
-- and route directly to the High Archon.
--
-- Constitutional Requirements:
-- - FR-10.4: META petitions (about petition system) SHALL route to High Archon [P2]
-- - META-1: Prevents deadlock from system-about-system petitions
-- - CT-12: Witnessing creates accountability -> Audit trail required
-- - CT-13: Explicit consent -> High Archon explicitly handles META petitions
--
-- Author: Story 8.5 Implementation
-- Date: 2026-01-22

-- ============================================================================
-- Table: meta_petition_queue
-- ============================================================================
-- Tracks META petitions awaiting High Archon review. When a petition is
-- submitted with type=META, it bypasses deliberation and enters this queue.
--
-- Queue workflow:
-- 1. META petition submitted -> enqueued with status=PENDING
-- 2. High Archon reviews queue via GET /api/v1/governance/meta-petitions
-- 3. High Archon resolves via POST /api/v1/governance/meta-petitions/{id}/resolve
-- 4. Status changes to RESOLVED with disposition recorded

CREATE TABLE IF NOT EXISTS meta_petition_queue (
    -- Primary key
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key to petition (petition_submissions table)
    petition_id UUID NOT NULL,

    -- Submitter information (denormalized for query efficiency)
    submitter_id UUID,

    -- Queue status
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RESOLVED')),

    -- Enqueue metadata
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Resolution metadata (populated when status='RESOLVED')
    resolved_at TIMESTAMPTZ,
    resolved_by UUID,  -- High Archon who resolved
    disposition TEXT CHECK (disposition IN ('ACKNOWLEDGE', 'CREATE_ACTION', 'FORWARD')),
    rationale TEXT,
    forward_target TEXT,  -- Required if disposition='FORWARD'

    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ensure each petition appears only once in the queue
    CONSTRAINT unique_petition_in_meta_queue UNIQUE (petition_id)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for pending queue queries (sorted by enqueue time for FIFO)
-- AC3: Queue returns sorted by received_at (oldest first)
CREATE INDEX idx_meta_petition_queue_pending
    ON meta_petition_queue(enqueued_at ASC)
    WHERE status = 'PENDING';

-- Index for resolved queue queries (most recent first)
CREATE INDEX idx_meta_petition_queue_resolved
    ON meta_petition_queue(resolved_at DESC)
    WHERE status = 'RESOLVED';

-- Index for looking up queue entry by petition_id
CREATE INDEX idx_meta_petition_queue_petition_id
    ON meta_petition_queue(petition_id);

-- Index for High Archon resolution audit trail
CREATE INDEX idx_meta_petition_queue_resolved_by
    ON meta_petition_queue(resolved_by)
    WHERE resolved_by IS NOT NULL;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE meta_petition_queue IS
    'Story 8.5, FR-10.4: Queue for META petitions awaiting High Archon review';

COMMENT ON COLUMN meta_petition_queue.queue_id IS
    'Unique identifier for this queue entry';

COMMENT ON COLUMN meta_petition_queue.petition_id IS
    'UUID of the META petition (references petition_submissions.id)';

COMMENT ON COLUMN meta_petition_queue.submitter_id IS
    'UUID of petition submitter (denormalized for query efficiency)';

COMMENT ON COLUMN meta_petition_queue.status IS
    'Queue status: PENDING (awaiting review) or RESOLVED (High Archon acted)';

COMMENT ON COLUMN meta_petition_queue.enqueued_at IS
    'When the META petition was routed to High Archon queue (UTC)';

COMMENT ON COLUMN meta_petition_queue.resolved_at IS
    'When High Archon resolved the petition (UTC), NULL if PENDING';

COMMENT ON COLUMN meta_petition_queue.resolved_by IS
    'UUID of the High Archon who resolved, NULL if PENDING';

COMMENT ON COLUMN meta_petition_queue.disposition IS
    'High Archon disposition: ACKNOWLEDGE, CREATE_ACTION, or FORWARD';

COMMENT ON COLUMN meta_petition_queue.rationale IS
    'High Archon rationale for the disposition (required for resolution)';

COMMENT ON COLUMN meta_petition_queue.forward_target IS
    'Target governance body when disposition=FORWARD';

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_meta_petition_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_meta_petition_queue_updated_at
    BEFORE UPDATE ON meta_petition_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_meta_petition_queue_updated_at();

-- ============================================================================
-- Migration Verification
-- ============================================================================

DO $$
BEGIN
    -- Verify table was created
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'meta_petition_queue'
    ) THEN
        RAISE EXCEPTION 'Migration 033 failed: meta_petition_queue table not created';
    END IF;

    -- Verify indexes exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_meta_petition_queue_pending'
    ) THEN
        RAISE EXCEPTION 'Migration 033 failed: pending queue index not created';
    END IF;

    RAISE NOTICE 'Migration 033 completed successfully: META petition queue table created';
END $$;
