-- Migration 031: Create legitimacy alert state and history tables
-- Story 8.2: Legitimacy Decay Alerting
-- FR-8.3, NFR-7.2
--
-- Purpose: Store legitimacy alert state and history to enable alert
-- lifecycle management, flap detection, and historical analysis.
--
-- Constitutional Compliance:
-- - FR-8.3: System SHALL alert on decay below 0.85 threshold
-- - NFR-7.2: Alert delivery within 1 minute of trigger
-- - CT-12: Witnessing creates accountability (alert events are witnessed)

-- ============================================================================
-- Table: legitimacy_alert_state
-- ============================================================================
-- Tracks current alert state across service restarts.
-- Implements single active alert constraint to prevent duplicate alerts.

CREATE TABLE IF NOT EXISTS legitimacy_alert_state (
    -- Primary Key
    alert_id UUID PRIMARY KEY,

    -- Alert State
    is_active BOOLEAN NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('WARNING', 'CRITICAL')),

    -- Timing
    triggered_at TIMESTAMPTZ NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Flap Detection
    consecutive_breaches INT NOT NULL DEFAULT 1 CHECK (consecutive_breaches >= 1),

    -- Cycle Tracking
    triggered_cycle_id TEXT NOT NULL,
    triggered_score DECIMAL(5, 4) NOT NULL CHECK (triggered_score >= 0.0 AND triggered_score <= 1.0),

    -- Single Row Constraint
    -- This ensures only one alert can be active at a time
    CONSTRAINT single_alert_state CHECK (alert_id = alert_id)
);

-- Ensure only one row exists (enforces single active alert)
CREATE UNIQUE INDEX idx_single_alert_state ON legitimacy_alert_state ((is_active)) WHERE is_active = true;

-- Index for querying current alert state
CREATE INDEX idx_alert_state_active ON legitimacy_alert_state(is_active) WHERE is_active = true;

-- ============================================================================
-- Table: legitimacy_alert_history
-- ============================================================================
-- Historical record of all legitimacy alerts for analysis and auditing.
-- Stores both TRIGGERED and RECOVERED events.

CREATE TABLE IF NOT EXISTS legitimacy_alert_history (
    -- Primary Key
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Alert Identification
    alert_id UUID NOT NULL,  -- Links to alert_state.alert_id

    -- Event Type
    event_type TEXT NOT NULL CHECK (event_type IN ('TRIGGERED', 'RECOVERED')),

    -- Cycle Tracking
    cycle_id TEXT NOT NULL,

    -- Alert Details (for TRIGGERED events)
    severity TEXT CHECK (severity IN ('WARNING', 'CRITICAL')),
    score DECIMAL(5, 4) NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
    threshold DECIMAL(5, 4) CHECK (threshold >= 0.0 AND threshold <= 1.0),
    stuck_petition_count INT CHECK (stuck_petition_count >= 0),

    -- Recovery Details (for RECOVERED events)
    previous_score DECIMAL(5, 4) CHECK (previous_score >= 0.0 AND previous_score <= 1.0),
    alert_duration_seconds INT CHECK (alert_duration_seconds > 0),

    -- Audit Fields
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT triggered_requires_severity CHECK (
        event_type != 'TRIGGERED' OR (severity IS NOT NULL AND threshold IS NOT NULL AND stuck_petition_count IS NOT NULL)
    ),
    CONSTRAINT recovered_requires_duration CHECK (
        event_type != 'RECOVERED' OR (previous_score IS NOT NULL AND alert_duration_seconds IS NOT NULL)
    )
);

-- Index for querying alert history by cycle
CREATE INDEX idx_alert_history_cycle ON legitimacy_alert_history(cycle_id);

-- Index for time-series queries (dashboard, trends)
CREATE INDEX idx_alert_history_occurred ON legitimacy_alert_history(occurred_at DESC);

-- Index for querying history by alert_id (lifecycle tracking)
CREATE INDEX idx_alert_history_alert_id ON legitimacy_alert_history(alert_id);

-- Index for querying by event type
CREATE INDEX idx_alert_history_event_type ON legitimacy_alert_history(event_type);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE legitimacy_alert_state IS
'Current legitimacy alert state (Story 8.2, FR-8.3). Tracks active alert and flap detection.';

COMMENT ON COLUMN legitimacy_alert_state.alert_id IS
'Unique identifier for the current alert';

COMMENT ON COLUMN legitimacy_alert_state.is_active IS
'Whether an alert is currently active. Only one row can have is_active=true at a time.';

COMMENT ON COLUMN legitimacy_alert_state.severity IS
'Alert severity: WARNING (< 0.85) or CRITICAL (< 0.70)';

COMMENT ON COLUMN legitimacy_alert_state.triggered_at IS
'When the current alert was first triggered (UTC)';

COMMENT ON COLUMN legitimacy_alert_state.last_updated IS
'When this state was last updated (UTC)';

COMMENT ON COLUMN legitimacy_alert_state.consecutive_breaches IS
'Count of consecutive cycles below threshold (for flap detection)';

COMMENT ON COLUMN legitimacy_alert_state.triggered_cycle_id IS
'Cycle ID when alert was triggered (e.g., "2026-W04")';

COMMENT ON COLUMN legitimacy_alert_state.triggered_score IS
'Legitimacy score that triggered the alert';

COMMENT ON TABLE legitimacy_alert_history IS
'Historical record of legitimacy alerts (Story 8.2, FR-8.3). Stores TRIGGERED and RECOVERED events.';

COMMENT ON COLUMN legitimacy_alert_history.alert_id IS
'Links to alert_state.alert_id for lifecycle tracking';

COMMENT ON COLUMN legitimacy_alert_history.event_type IS
'Type of event: TRIGGERED (alert fired) or RECOVERED (alert resolved)';

COMMENT ON COLUMN legitimacy_alert_history.cycle_id IS
'Governance cycle identifier when event occurred';

COMMENT ON COLUMN legitimacy_alert_history.severity IS
'Alert severity (WARNING or CRITICAL). Required for TRIGGERED events, NULL for RECOVERED.';

COMMENT ON COLUMN legitimacy_alert_history.score IS
'Legitimacy score at time of event';

COMMENT ON COLUMN legitimacy_alert_history.threshold IS
'Threshold that was breached (0.85 or 0.70). Required for TRIGGERED events, NULL for RECOVERED.';

COMMENT ON COLUMN legitimacy_alert_history.stuck_petition_count IS
'Count of petitions not fated within SLA. Required for TRIGGERED events, NULL for RECOVERED.';

COMMENT ON COLUMN legitimacy_alert_history.previous_score IS
'Score when alert was triggered. Required for RECOVERED events, NULL for TRIGGERED.';

COMMENT ON COLUMN legitimacy_alert_history.alert_duration_seconds IS
'Duration alert was active in seconds. Required for RECOVERED events, NULL for TRIGGERED.';

COMMENT ON COLUMN legitimacy_alert_history.occurred_at IS
'When this event occurred (UTC)';

-- ============================================================================
-- Validation
-- ============================================================================

-- Verify tables created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'legitimacy_alert_state'
    ) THEN
        RAISE EXCEPTION 'Migration 031 failed: legitimacy_alert_state table not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'legitimacy_alert_history'
    ) THEN
        RAISE EXCEPTION 'Migration 031 failed: legitimacy_alert_history table not created';
    END IF;
END $$;
