-- Migration 032: Create Orphan Petition Detection Tables (Story 8.3, FR-8.5)
--
-- This migration creates tables for tracking orphan petition detection results
-- to support dashboard visibility and historical trend analysis.
--
-- Constitutional Requirements:
-- - FR-8.5: System SHALL identify petitions stuck in RECEIVED state
-- - NFR-7.1: 100% of orphans must be detected
-- - CT-12: Witnessing creates accountability -> Audit trail required
-- - AC6: Comprehensive audit trail for all governance actions
--
-- Tables:
-- 1. orphan_detection_runs: Records of each detection scan
-- 2. orphaned_petitions: Snapshot of orphans found in each run
--
-- Author: Story 8.3 Implementation
-- Date: 2026-01-22

-- ============================================================================
-- Table 1: orphan_detection_runs
-- ============================================================================
-- Tracks each execution of the orphan detection job with summary metrics.
-- Provides historical trend data for dashboard visualization.

CREATE TABLE IF NOT EXISTS orphan_detection_runs (
    -- Primary key
    detection_id UUID PRIMARY KEY,

    -- Detection metadata
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    threshold_hours DECIMAL(10, 2) NOT NULL DEFAULT 24.0,

    -- Summary metrics
    orphan_count INTEGER NOT NULL DEFAULT 0,
    oldest_orphan_age_hours DECIMAL(10, 2),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for time-series queries (dashboard trends)
CREATE INDEX idx_orphan_detection_runs_detected_at
    ON orphan_detection_runs(detected_at DESC);

-- Index for orphan count queries (alerting)
CREATE INDEX idx_orphan_detection_runs_orphan_count
    ON orphan_detection_runs(orphan_count)
    WHERE orphan_count > 0;

COMMENT ON TABLE orphan_detection_runs IS
    'Story 8.3, FR-8.5: Tracks orphan petition detection scan executions with summary metrics';

COMMENT ON COLUMN orphan_detection_runs.detection_id IS
    'Unique identifier for this detection run';

COMMENT ON COLUMN orphan_detection_runs.detected_at IS
    'Timestamp when the detection scan ran (UTC)';

COMMENT ON COLUMN orphan_detection_runs.threshold_hours IS
    'Threshold used for orphan detection (default: 24 hours)';

COMMENT ON COLUMN orphan_detection_runs.orphan_count IS
    'Number of orphaned petitions found in this scan';

COMMENT ON COLUMN orphan_detection_runs.oldest_orphan_age_hours IS
    'Age of the oldest orphan in hours, NULL if no orphans found';

-- ============================================================================
-- Table 2: orphaned_petitions
-- ============================================================================
-- Snapshot of individual petitions identified as orphaned in each detection run.
-- Provides detail view for operator investigation and remediation.

CREATE TABLE IF NOT EXISTS orphaned_petitions (
    -- Composite primary key (detection run + petition)
    detection_id UUID NOT NULL REFERENCES orphan_detection_runs(detection_id) ON DELETE CASCADE,
    petition_id UUID NOT NULL,

    -- Orphan metadata
    petition_created_at TIMESTAMPTZ NOT NULL,
    age_hours DECIMAL(10, 2) NOT NULL,
    petition_type VARCHAR(50) NOT NULL,
    co_signer_count INTEGER NOT NULL DEFAULT 0,

    -- Reprocessing tracking
    reprocessed BOOLEAN NOT NULL DEFAULT FALSE,
    reprocessed_at TIMESTAMPTZ,
    reprocessed_by VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (detection_id, petition_id)
);

-- Index for petition lookup (find all detection runs where petition appeared)
CREATE INDEX idx_orphaned_petitions_petition_id
    ON orphaned_petitions(petition_id);

-- Index for reprocessing status queries
CREATE INDEX idx_orphaned_petitions_reprocessed
    ON orphaned_petitions(reprocessed, detection_id)
    WHERE reprocessed = FALSE;

-- Index for age-based queries (find oldest orphans)
CREATE INDEX idx_orphaned_petitions_age
    ON orphaned_petitions(age_hours DESC);

COMMENT ON TABLE orphaned_petitions IS
    'Story 8.3, FR-8.5: Individual petitions identified as orphaned in each detection run';

COMMENT ON COLUMN orphaned_petitions.detection_id IS
    'FK to orphan_detection_runs, which detection run found this orphan';

COMMENT ON COLUMN orphaned_petitions.petition_id IS
    'UUID of the orphaned petition';

COMMENT ON COLUMN orphaned_petitions.petition_created_at IS
    'When the petition was created/entered RECEIVED state (UTC)';

COMMENT ON COLUMN orphaned_petitions.age_hours IS
    'Age of the petition in hours at detection time';

COMMENT ON COLUMN orphaned_petitions.petition_type IS
    'Type of petition (GENERAL, CESSATION, GRIEVANCE, COLLABORATION)';

COMMENT ON COLUMN orphaned_petitions.co_signer_count IS
    'Number of co-signers on the petition (context for priority)';

COMMENT ON COLUMN orphaned_petitions.reprocessed IS
    'Whether this orphan has been manually reprocessed';

COMMENT ON COLUMN orphaned_petitions.reprocessed_at IS
    'When manual reprocessing was triggered (UTC)';

COMMENT ON COLUMN orphaned_petitions.reprocessed_by IS
    'Operator/agent who triggered manual reprocessing';

-- ============================================================================
-- Grants
-- ============================================================================
-- Grant read access to application role for queries
-- Grant write access for detection job and reprocessing service

-- TODO: Replace 'archon_app' with actual application role name
-- GRANT SELECT ON orphan_detection_runs TO archon_app;
-- GRANT INSERT, UPDATE ON orphan_detection_runs TO archon_app;
-- GRANT SELECT ON orphaned_petitions TO archon_app;
-- GRANT INSERT, UPDATE ON orphaned_petitions TO archon_app;

-- ============================================================================
-- Migration Verification
-- ============================================================================
-- Verify tables were created successfully

DO $$
BEGIN
    -- Verify orphan_detection_runs table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'orphan_detection_runs'
    ) THEN
        RAISE EXCEPTION 'Migration 032 failed: orphan_detection_runs table not created';
    END IF;

    -- Verify orphaned_petitions table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'orphaned_petitions'
    ) THEN
        RAISE EXCEPTION 'Migration 032 failed: orphaned_petitions table not created';
    END IF;

    RAISE NOTICE 'Migration 032 completed successfully: Orphan detection tables created';
END $$;
