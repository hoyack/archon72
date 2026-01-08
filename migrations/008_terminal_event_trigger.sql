-- Migration: Terminal Event Enforcement (FR43, NFR40)
-- Story: 7.6 Cessation as Final Recorded Event
-- Date: 2026-01-09
--
-- Constitutional Constraints:
--   FR43: Cessation as final recorded event (not silent disappearance)
--   NFR40: Cessation reversal is architecturally prohibited
--   CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
--   CT-12: Witnessing creates accountability → Terminal event must be witnessed
--   CT-13: Integrity outranks availability → Permanent termination
--
-- Requirements:
--   AC3: DB-level write rejection after cessation
--   AC4: prev_hash cannot reference cessation event
--
-- Developer Golden Rules:
--   1. TERMINAL EVENT - is_terminal marks end of event stream
--   2. DB ENFORCEMENT - Terminal constraint enforced at DB level, not just app
--   3. NO REVERSAL - No event type can undo cessation (NFR40)

-- ============================================================================
-- TASK 1: Create terminal event detection function
-- ============================================================================

-- Function to check if a terminal event exists in the event store
CREATE OR REPLACE FUNCTION get_terminal_event()
RETURNS TABLE (
    event_id UUID,
    sequence BIGINT,
    content_hash TEXT,
    execution_timestamp TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.event_id,
        e.sequence,
        e.content_hash,
        (e.payload->>'execution_timestamp')::TIMESTAMPTZ
    FROM events e
    WHERE e.payload->>'is_terminal' = 'true'
    ORDER BY e.sequence DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- TASK 2: Create trigger function to enforce terminal event constraint
-- ============================================================================

-- Function to prevent writes after terminal event (FR43, NFR40)
CREATE OR REPLACE FUNCTION enforce_terminal_event_constraint()
RETURNS TRIGGER AS $$
DECLARE
    terminal_seq BIGINT;
    terminal_hash TEXT;
BEGIN
    -- Check if any terminal event exists
    SELECT sequence, content_hash INTO terminal_seq, terminal_hash
    FROM events
    WHERE payload->>'is_terminal' = 'true'
    LIMIT 1;

    -- If terminal event exists, reject ALL new inserts (AC3)
    IF terminal_seq IS NOT NULL THEN
        RAISE EXCEPTION 'NFR40: Cannot write after terminal cessation event. System terminated at sequence %. No events may be appended after cessation.',
            terminal_seq
        USING ERRCODE = 'P0001',
              HINT = 'The system has been permanently terminated via cessation. This is architecturally irreversible.';
    END IF;

    -- Additional check: prevent prev_hash from referencing terminal event's content_hash (AC4)
    -- This handles edge case where someone tries to append directly to terminal event
    -- Note: This check is redundant with above but provides defense in depth
    IF NEW.prev_hash IS NOT NULL THEN
        SELECT sequence INTO terminal_seq
        FROM events
        WHERE content_hash = NEW.prev_hash
          AND payload->>'is_terminal' = 'true';

        IF terminal_seq IS NOT NULL THEN
            RAISE EXCEPTION 'FR43: Cannot append after terminal event. prev_hash references cessation event at sequence %.',
                terminal_seq
            USING ERRCODE = 'P0002',
                  HINT = 'Events cannot chain from the terminal cessation event. The event stream has permanently ended.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TASK 3: Create trigger on events table
-- ============================================================================

-- Drop existing trigger if it exists (for idempotent migrations)
DROP TRIGGER IF EXISTS enforce_terminal_event ON events;

-- Create BEFORE INSERT trigger to check terminal state
-- This runs BEFORE the hash chain verification trigger
CREATE TRIGGER enforce_terminal_event
    BEFORE INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION enforce_terminal_event_constraint();

-- ============================================================================
-- TASK 4: Create index for efficient terminal event lookup
-- ============================================================================

-- Partial index on is_terminal for fast terminal event detection
-- Only indexes rows where is_terminal = 'true' (should be 0 or 1 rows)
CREATE INDEX IF NOT EXISTS idx_events_terminal
    ON events ((payload->>'is_terminal'))
    WHERE payload->>'is_terminal' = 'true';

-- ============================================================================
-- TASK 5: Create helper function for terminal state check (used by app layer)
-- ============================================================================

-- Simple boolean function for application layer to check terminal state
CREATE OR REPLACE FUNCTION is_system_terminated()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM events
        WHERE payload->>'is_terminal' = 'true'
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- COMMENTS for documentation
-- ============================================================================

COMMENT ON FUNCTION get_terminal_event() IS 'FR43: Returns the terminal cessation event if one exists, NULL otherwise.';
COMMENT ON FUNCTION enforce_terminal_event_constraint() IS 'NFR40: Prevents any writes after a terminal cessation event has been recorded.';
COMMENT ON FUNCTION is_system_terminated() IS 'FR43: Returns TRUE if a terminal cessation event exists, FALSE otherwise.';
COMMENT ON TRIGGER enforce_terminal_event ON events IS 'FR43, NFR40: Enforces that no events can be written after cessation.';
COMMENT ON INDEX idx_events_terminal IS 'FR43: Partial index for fast terminal event lookup.';

-- ============================================================================
-- VERIFICATION QUERIES (for manual testing)
-- ============================================================================

-- Uncomment to verify migration:
-- SELECT is_system_terminated(); -- Should return FALSE initially
-- SELECT * FROM get_terminal_event(); -- Should return empty initially
