-- Migration 034: Create adoption ratio metrics and alerts tables
-- Story 8.6: Adoption Ratio Monitoring
-- PREVENT-7, ASM-7
--
-- Purpose: Store adoption ratio metrics and alerts per realm per governance
-- cycle to detect excessive petition-to-Motion conversion patterns.
--
-- Constitutional Compliance:
-- - PREVENT-7: Alert when adoption ratio exceeds 50%
-- - ASM-7: Monitor adoption vs organic ratio to detect budget contention
-- - CT-11: Silent failure destroys legitimacy (all operations logged)
-- - CT-12: Witnessing creates accountability (alert events are witnessed)

-- ============================================================================
-- Table: adoption_ratio_metrics
-- ============================================================================
-- Stores computed adoption ratio metrics per realm per governance cycle.
-- Used to track escalation-to-adoption patterns and detect "rubber-stamping".

CREATE TABLE IF NOT EXISTS adoption_ratio_metrics (
    -- Primary Key
    metrics_id UUID PRIMARY KEY,

    -- Realm and Cycle Identification
    realm_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,  -- Format: YYYY-Wnn (e.g., "2026-W04")

    -- Adoption Metrics
    escalation_count INT NOT NULL CHECK (escalation_count >= 0),
    adoption_count INT NOT NULL CHECK (adoption_count >= 0),
    adoption_ratio DECIMAL(5, 4) CHECK (adoption_ratio >= 0.0 AND adoption_ratio <= 1.0),

    -- Adopting Kings (JSONB array of UUID strings)
    adopting_kings JSONB NOT NULL DEFAULT '[]',

    -- Audit Fields
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint: one record per realm/cycle
    CONSTRAINT unique_realm_cycle_metrics UNIQUE (realm_id, cycle_id),

    -- Ratio consistency: adoption_count <= escalation_count
    CONSTRAINT adoption_not_exceed_escalation CHECK (adoption_count <= escalation_count),

    -- Ratio computation consistency
    CONSTRAINT ratio_requires_escalations CHECK (
        (escalation_count = 0 AND adoption_ratio IS NULL) OR
        (escalation_count > 0 AND adoption_ratio IS NOT NULL)
    )
);

-- Index for querying metrics by realm (current state lookup)
CREATE INDEX idx_adoption_metrics_realm ON adoption_ratio_metrics(realm_id);

-- Index for querying metrics by cycle (cross-realm analysis)
CREATE INDEX idx_adoption_metrics_cycle ON adoption_ratio_metrics(cycle_id);

-- Index for time-series queries (dashboard, trends)
CREATE INDEX idx_adoption_metrics_computed ON adoption_ratio_metrics(computed_at DESC);

-- Index for threshold breach queries (alert generation)
CREATE INDEX idx_adoption_metrics_ratio ON adoption_ratio_metrics(adoption_ratio DESC)
    WHERE adoption_ratio IS NOT NULL;

-- ============================================================================
-- Table: adoption_ratio_alerts
-- ============================================================================
-- Stores active and historical adoption ratio alerts for monitoring and audit.
-- An alert is created when adoption ratio exceeds 50% threshold (PREVENT-7).

CREATE TABLE IF NOT EXISTS adoption_ratio_alerts (
    -- Primary Key
    alert_id UUID PRIMARY KEY,

    -- Realm and Cycle Identification
    realm_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,  -- Cycle when alert was created

    -- Adoption Metrics (snapshot at alert creation)
    adoption_count INT NOT NULL CHECK (adoption_count >= 0),
    escalation_count INT NOT NULL CHECK (escalation_count > 0),  -- Must have escalations
    adoption_ratio DECIMAL(5, 4) NOT NULL CHECK (adoption_ratio > 0.50 AND adoption_ratio <= 1.0),
    threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.50 CHECK (threshold >= 0.0 AND threshold <= 1.0),

    -- Adopting Kings (JSONB array of UUID strings)
    adopting_kings JSONB NOT NULL DEFAULT '[]',

    -- Alert Classification
    severity TEXT NOT NULL CHECK (severity IN ('WARN', 'CRITICAL')),
    trend_delta DECIMAL(5, 4),  -- Change from previous cycle (positive = increasing)

    -- Alert Lifecycle
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'RESOLVED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT resolved_requires_timestamp CHECK (
        status != 'RESOLVED' OR resolved_at IS NOT NULL
    ),
    CONSTRAINT active_no_resolved_timestamp CHECK (
        status != 'ACTIVE' OR resolved_at IS NULL
    )
);

-- Index for active alert lookup per realm (only one active alert per realm)
CREATE UNIQUE INDEX idx_adoption_alert_active_realm ON adoption_ratio_alerts(realm_id)
    WHERE status = 'ACTIVE';

-- Index for querying all active alerts (dashboard)
CREATE INDEX idx_adoption_alerts_active ON adoption_ratio_alerts(status)
    WHERE status = 'ACTIVE';

-- Index for querying alerts by realm (history)
CREATE INDEX idx_adoption_alerts_realm ON adoption_ratio_alerts(realm_id);

-- Index for querying alerts by cycle
CREATE INDEX idx_adoption_alerts_cycle ON adoption_ratio_alerts(cycle_id);

-- Index for time-series queries (dashboard, trends)
CREATE INDEX idx_adoption_alerts_created ON adoption_ratio_alerts(created_at DESC);

-- Index for severity-based queries
CREATE INDEX idx_adoption_alerts_severity ON adoption_ratio_alerts(severity);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE adoption_ratio_metrics IS
'Adoption ratio metrics per realm per cycle (Story 8.6, PREVENT-7). Tracks escalation-to-adoption patterns.';

COMMENT ON COLUMN adoption_ratio_metrics.metrics_id IS
'Unique identifier for this metrics record';

COMMENT ON COLUMN adoption_ratio_metrics.realm_id IS
'Realm identifier';

COMMENT ON COLUMN adoption_ratio_metrics.cycle_id IS
'Governance cycle identifier (format: YYYY-Wnn, e.g., "2026-W04")';

COMMENT ON COLUMN adoption_ratio_metrics.escalation_count IS
'Count of petitions escalated to this realm this cycle';

COMMENT ON COLUMN adoption_ratio_metrics.adoption_count IS
'Count of petitions adopted by this realm''s King this cycle';

COMMENT ON COLUMN adoption_ratio_metrics.adoption_ratio IS
'Computed ratio: adoption_count / escalation_count. NULL if no escalations.';

COMMENT ON COLUMN adoption_ratio_metrics.adopting_kings IS
'JSONB array of King UUIDs who performed adoptions this cycle';

COMMENT ON COLUMN adoption_ratio_metrics.computed_at IS
'When these metrics were computed (UTC)';

COMMENT ON TABLE adoption_ratio_alerts IS
'Adoption ratio alerts (Story 8.6, PREVENT-7). Created when adoption ratio exceeds 50%.';

COMMENT ON COLUMN adoption_ratio_alerts.alert_id IS
'Unique identifier for this alert';

COMMENT ON COLUMN adoption_ratio_alerts.realm_id IS
'Realm with excessive adoption ratio';

COMMENT ON COLUMN adoption_ratio_alerts.cycle_id IS
'Governance cycle when alert was created';

COMMENT ON COLUMN adoption_ratio_alerts.adoption_count IS
'Number of adoptions in the cycle (snapshot)';

COMMENT ON COLUMN adoption_ratio_alerts.escalation_count IS
'Number of escalations in the cycle (snapshot)';

COMMENT ON COLUMN adoption_ratio_alerts.adoption_ratio IS
'Computed ratio at alert creation (must exceed threshold)';

COMMENT ON COLUMN adoption_ratio_alerts.threshold IS
'Threshold that was exceeded (default: 0.50)';

COMMENT ON COLUMN adoption_ratio_alerts.adopting_kings IS
'JSONB array of King UUIDs who performed adoptions';

COMMENT ON COLUMN adoption_ratio_alerts.severity IS
'Alert severity: WARN (50-70%) or CRITICAL (>70%)';

COMMENT ON COLUMN adoption_ratio_alerts.trend_delta IS
'Change from previous cycle (positive = increasing). NULL if no previous data.';

COMMENT ON COLUMN adoption_ratio_alerts.status IS
'Alert status: ACTIVE or RESOLVED';

COMMENT ON COLUMN adoption_ratio_alerts.created_at IS
'When the alert was created (UTC)';

COMMENT ON COLUMN adoption_ratio_alerts.resolved_at IS
'When the alert was resolved (UTC). NULL if still active.';

-- ============================================================================
-- Validation
-- ============================================================================

-- Verify tables created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'adoption_ratio_metrics'
    ) THEN
        RAISE EXCEPTION 'Migration 034 failed: adoption_ratio_metrics table not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'adoption_ratio_alerts'
    ) THEN
        RAISE EXCEPTION 'Migration 034 failed: adoption_ratio_alerts table not created';
    END IF;
END $$;
