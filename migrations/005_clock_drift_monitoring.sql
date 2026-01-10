-- Migration: Clock drift monitoring for time authority (FR6, FR7)
-- Story: 1.5 Dual Time Authority & Sequence Numbers
-- Date: 2026-01-06
--
-- Constitutional Constraints:
--   FR6: Events must have dual timestamps (local + authority)
--   FR7: Sequence numbers must be monotonically increasing and unique
--   CT-12: Witnessing creates accountability → drift logged for investigation
--
-- Note:
--   Clock drift does NOT invalidate events. Sequence is authoritative (FR7).
--   This migration adds monitoring to help investigate time sync issues.
--   Drift warnings are informational only (AC4).

-- ============================================================================
-- TASK 3.2: Create clock drift warnings table
-- ============================================================================

-- Table to store clock drift warnings for investigation
CREATE TABLE IF NOT EXISTS clock_drift_warnings (
    id BIGSERIAL PRIMARY KEY,

    -- Reference to the event that triggered the warning
    event_id UUID NOT NULL REFERENCES events(event_id),

    -- The timestamps that were compared
    local_timestamp TIMESTAMPTZ NOT NULL,
    authority_timestamp TIMESTAMPTZ NOT NULL,

    -- Calculated drift (in seconds, positive or negative)
    drift_seconds NUMERIC(10, 3) NOT NULL,

    -- When the warning was logged
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index on event_id for looking up warnings by event
CREATE INDEX IF NOT EXISTS idx_clock_drift_event_id
    ON clock_drift_warnings (event_id);

-- Index on logged_at for time-range queries and cleanup
CREATE INDEX IF NOT EXISTS idx_clock_drift_logged_at
    ON clock_drift_warnings (logged_at);

-- Index on drift_seconds for finding severe drift cases
CREATE INDEX IF NOT EXISTS idx_clock_drift_drift_seconds
    ON clock_drift_warnings (drift_seconds);

-- ============================================================================
-- TASK 3.2, 3.3: Create clock drift logging function and trigger
-- ============================================================================

-- Configuration: default drift threshold in seconds
-- This matches the Python TimeAuthorityService default (5 seconds per AC4)
DO $$
BEGIN
    -- Create a configuration table if it doesn't exist
    -- This allows runtime configuration of the drift threshold
    CREATE TABLE IF NOT EXISTS constitutional_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- Insert default drift threshold if not exists
    INSERT INTO constitutional_config (key, value, description)
    VALUES (
        'clock_drift_threshold_seconds',
        '5.0',
        'FR6/AC4: Clock drift threshold in seconds before warning is logged'
    )
    ON CONFLICT (key) DO NOTHING;
END $$;

-- Function to log clock drift on event insert
-- This implements AC4: Clock drift warning when drift > threshold
CREATE OR REPLACE FUNCTION log_clock_drift()
RETURNS TRIGGER AS $$
DECLARE
    drift_seconds NUMERIC;
    drift_threshold NUMERIC;
BEGIN
    -- Get threshold from config (default 5 seconds)
    SELECT COALESCE(
        (SELECT value::NUMERIC FROM constitutional_config
         WHERE key = 'clock_drift_threshold_seconds'),
        5.0
    ) INTO drift_threshold;

    -- Calculate drift in seconds (authority - local)
    -- Positive = authority ahead, Negative = authority behind
    drift_seconds := EXTRACT(EPOCH FROM (NEW.authority_timestamp - NEW.local_timestamp));

    -- Log if absolute drift exceeds threshold (AC4)
    IF ABS(drift_seconds) > drift_threshold THEN
        INSERT INTO clock_drift_warnings (
            event_id,
            local_timestamp,
            authority_timestamp,
            drift_seconds
        ) VALUES (
            NEW.event_id,
            NEW.local_timestamp,
            NEW.authority_timestamp,
            drift_seconds  -- Store signed value for direction analysis
        );

        -- Note: We do NOT raise an exception or reject the event.
        -- Per FR7 and AC3, sequence is authoritative - timestamps are informational.
        -- This warning is for time sync investigation only.
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to check clock drift after event insert
-- AFTER INSERT so the event is already committed (we never reject for drift)
DROP TRIGGER IF EXISTS log_clock_drift_on_insert ON events;
CREATE TRIGGER log_clock_drift_on_insert
    AFTER INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION log_clock_drift();

-- ============================================================================
-- COMMENTS for documentation
-- ============================================================================

COMMENT ON TABLE clock_drift_warnings IS
    'FR6/AC4: Clock drift warnings for time sync investigation. Informational only.';

COMMENT ON COLUMN clock_drift_warnings.event_id IS
    'Reference to the event that triggered the drift warning';

COMMENT ON COLUMN clock_drift_warnings.local_timestamp IS
    'Timestamp from event source when drift was detected';

COMMENT ON COLUMN clock_drift_warnings.authority_timestamp IS
    'Timestamp from time authority (database) when drift was detected';

COMMENT ON COLUMN clock_drift_warnings.drift_seconds IS
    'Calculated drift in seconds (positive = authority ahead, negative = behind)';

COMMENT ON COLUMN clock_drift_warnings.logged_at IS
    'When the warning was logged';

COMMENT ON FUNCTION log_clock_drift() IS
    'FR6/AC4: Logs clock drift warnings when threshold exceeded. Does NOT reject events.';

COMMENT ON TRIGGER log_clock_drift_on_insert ON events IS
    'FR6/AC4: Monitors clock drift after event insertion';

-- ============================================================================
-- TASK 3.4: Query helpers for clock drift analysis
-- ============================================================================

-- View for easy drift analysis
CREATE OR REPLACE VIEW clock_drift_summary AS
SELECT
    DATE_TRUNC('hour', logged_at) AS hour,
    COUNT(*) AS warning_count,
    AVG(ABS(drift_seconds)) AS avg_drift_seconds,
    MAX(ABS(drift_seconds)) AS max_drift_seconds,
    MIN(ABS(drift_seconds)) AS min_drift_seconds
FROM clock_drift_warnings
GROUP BY DATE_TRUNC('hour', logged_at)
ORDER BY hour DESC;

COMMENT ON VIEW clock_drift_summary IS
    'FR6: Hourly summary of clock drift warnings for monitoring';
