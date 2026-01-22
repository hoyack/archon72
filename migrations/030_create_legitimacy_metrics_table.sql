-- Migration 030: Create legitimacy_metrics table
-- Story 8.1: Legitimacy Decay Metric Computation
-- FR-8.1, FR-8.2, NFR-1.5
--
-- Purpose: Store legitimacy decay metrics computed per governance cycle
-- to track petition system responsiveness and health.
--
-- Constitutional Compliance:
-- - FR-8.1: System SHALL compute legitimacy decay metric per cycle
-- - FR-8.2: Decay formula: (fated_petitions / total_petitions) within SLA
-- - NFR-1.5: Metric computation completes within 60 seconds
-- - CT-12: Witnessing creates accountability (immutable records)

-- ============================================================================
-- Table: legitimacy_metrics
-- ============================================================================

CREATE TABLE IF NOT EXISTS legitimacy_metrics (
    -- Primary Key
    metrics_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Cycle Identification
    cycle_id TEXT NOT NULL UNIQUE,  -- Format: YYYY-Wnn (e.g., "2026-W04")
    cycle_start TIMESTAMPTZ NOT NULL,
    cycle_end TIMESTAMPTZ NOT NULL,

    -- Petition Counts (FR-8.1)
    total_petitions INT NOT NULL CHECK (total_petitions >= 0),
    fated_petitions INT NOT NULL CHECK (fated_petitions >= 0),

    -- Legitimacy Score (FR-8.2)
    legitimacy_score DECIMAL(5, 4) CHECK (legitimacy_score >= 0.0 AND legitimacy_score <= 1.0),

    -- Timing Metrics (FR-8.2)
    average_time_to_fate DECIMAL(12, 2),  -- seconds
    median_time_to_fate DECIMAL(12, 2),   -- seconds

    -- Audit Fields
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT fated_petitions_le_total CHECK (fated_petitions <= total_petitions),
    CONSTRAINT valid_cycle_period CHECK (cycle_end > cycle_start)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for querying metrics by cycle_id (primary lookup)
CREATE INDEX idx_legitimacy_metrics_cycle_id ON legitimacy_metrics(cycle_id);

-- Index for time-series queries (dashboard, trends)
CREATE INDEX idx_legitimacy_metrics_cycle_start ON legitimacy_metrics(cycle_start DESC);

-- Index for health monitoring (alert queries)
CREATE INDEX idx_legitimacy_metrics_score ON legitimacy_metrics(legitimacy_score)
WHERE legitimacy_score IS NOT NULL;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE legitimacy_metrics IS
'Legitimacy decay metrics per governance cycle (Story 8.1, FR-8.1, FR-8.2). Tracks petition responsiveness.';

COMMENT ON COLUMN legitimacy_metrics.cycle_id IS
'Governance cycle identifier (format: YYYY-Wnn, e.g., "2026-W04")';

COMMENT ON COLUMN legitimacy_metrics.total_petitions IS
'Count of petitions received during this cycle';

COMMENT ON COLUMN legitimacy_metrics.fated_petitions IS
'Count of petitions that reached terminal state within SLA during this cycle';

COMMENT ON COLUMN legitimacy_metrics.legitimacy_score IS
'Ratio of fated to total petitions (0.0 to 1.0). NULL if no petitions. Formula: fated_petitions / total_petitions (FR-8.2)';

COMMENT ON COLUMN legitimacy_metrics.average_time_to_fate IS
'Mean duration from RECEIVED to terminal state in seconds. NULL if no fated petitions.';

COMMENT ON COLUMN legitimacy_metrics.median_time_to_fate IS
'Median duration from RECEIVED to terminal state in seconds. NULL if no fated petitions.';

COMMENT ON COLUMN legitimacy_metrics.computed_at IS
'Timestamp when these metrics were computed (UTC)';

-- ============================================================================
-- Validation
-- ============================================================================

-- Verify table created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'legitimacy_metrics'
    ) THEN
        RAISE EXCEPTION 'Migration 030 failed: legitimacy_metrics table not created';
    END IF;
END $$;
