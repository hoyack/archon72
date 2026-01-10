-- Migration: Hash Chain Verification (FR2, FR82-FR85)
-- Story: 1.2 Hash Chain Implementation
-- Date: 2026-01-06
--
-- Constitutional Constraints:
--   CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
--   CT-12: Witnessing creates accountability → Hash chain creates verifiable history
--   CT-13: Integrity outranks availability → Reject invalid hashes, never degrade
--
-- Requirements:
--   FR2: Events must be hash-chained
--   FR82: Hash chain continuity must be verified at DB level
--   FR83: Algorithm version must be tracked
--   FR84: Chain integrity violation triggers halt
--   FR85: Hash algorithm version tracking

-- ============================================================================
-- TASK 4: Create hash chain verification trigger (AC4)
-- ============================================================================

-- Genesis hash constant: 64 zeros representing "no previous event"
-- This is used for the first event in any chain (sequence 1)

-- Function to verify hash chain on insert
CREATE OR REPLACE FUNCTION verify_hash_chain_on_insert()
RETURNS TRIGGER AS $$
DECLARE
    expected_prev_hash TEXT;
    genesis_hash TEXT := repeat('0', 64);
BEGIN
    -- For first event (sequence 1), prev_hash must be genesis
    IF NEW.sequence = 1 THEN
        IF NEW.prev_hash != genesis_hash THEN
            RAISE EXCEPTION 'FR82: Hash chain continuity violation - first event must have genesis prev_hash (expected %, got %)',
                genesis_hash, NEW.prev_hash;
        END IF;
    ELSE
        -- For subsequent events, prev_hash must match previous event's content_hash
        SELECT content_hash INTO expected_prev_hash
        FROM events
        WHERE sequence = NEW.sequence - 1;

        IF expected_prev_hash IS NULL THEN
            RAISE EXCEPTION 'FR82: Hash chain continuity violation - previous event (sequence %) not found', NEW.sequence - 1;
        END IF;

        IF NEW.prev_hash != expected_prev_hash THEN
            RAISE EXCEPTION 'FR82: Hash chain continuity violation - prev_hash mismatch (expected %, got %)',
                expected_prev_hash, NEW.prev_hash;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to verify hash chain on every insert
DROP TRIGGER IF EXISTS verify_hash_chain_on_insert ON events;
CREATE TRIGGER verify_hash_chain_on_insert
    BEFORE INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION verify_hash_chain_on_insert();

-- ============================================================================
-- TASK 5: Create hash chain verification function (AC5)
-- ============================================================================

-- Function to verify chain integrity over a range
-- Returns a single row with validation results
-- FIX (2026-01-09): When start_seq > 1, fetch predecessor's content_hash first
-- to properly validate the first event in the range against its actual predecessor
CREATE OR REPLACE FUNCTION verify_chain(start_seq BIGINT, end_seq BIGINT)
RETURNS TABLE (
    is_valid BOOLEAN,
    broken_at_sequence BIGINT,
    expected_hash TEXT,
    actual_hash TEXT
) AS $$
DECLARE
    current_event RECORD;
    prev_content_hash TEXT;
    genesis_hash TEXT := repeat('0', 64);
BEGIN
    -- Initialize return values
    is_valid := TRUE;
    broken_at_sequence := NULL;
    expected_hash := NULL;
    actual_hash := NULL;

    -- FIX: If start_seq > 1, fetch the predecessor's content_hash first
    -- This ensures we validate the first event in range against its actual predecessor
    IF start_seq > 1 THEN
        SELECT e.content_hash INTO prev_content_hash
        FROM events e
        WHERE e.sequence = start_seq - 1;

        -- If predecessor doesn't exist, that's an error for ranges starting > 1
        IF prev_content_hash IS NULL THEN
            is_valid := FALSE;
            broken_at_sequence := start_seq;
            expected_hash := '(predecessor sequence ' || (start_seq - 1) || ' not found)';
            actual_hash := '(cannot verify range without predecessor)';
            RETURN NEXT;
            RETURN;
        END IF;
    END IF;

    -- Iterate through events in sequence order
    FOR current_event IN
        SELECT e.sequence, e.prev_hash, e.content_hash
        FROM events e
        WHERE e.sequence >= start_seq AND e.sequence <= end_seq
        ORDER BY e.sequence
    LOOP
        IF current_event.sequence = 1 THEN
            -- First event should have genesis hash
            IF current_event.prev_hash != genesis_hash THEN
                is_valid := FALSE;
                broken_at_sequence := current_event.sequence;
                expected_hash := genesis_hash;
                actual_hash := current_event.prev_hash;
                RETURN NEXT;
                RETURN;
            END IF;
        ELSIF prev_content_hash IS NOT NULL THEN
            -- Subsequent events (or first in range when start_seq > 1) should chain correctly
            IF current_event.prev_hash != prev_content_hash THEN
                is_valid := FALSE;
                broken_at_sequence := current_event.sequence;
                expected_hash := prev_content_hash;
                actual_hash := current_event.prev_hash;
                RETURN NEXT;
                RETURN;
            END IF;
        END IF;

        -- Store current event's content_hash for next iteration
        prev_content_hash := current_event.content_hash;
    END LOOP;

    -- Return valid result (no break found)
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS for documentation
-- ============================================================================

COMMENT ON FUNCTION verify_hash_chain_on_insert() IS 'FR82: Verifies hash chain continuity on every insert. Rejects events with invalid prev_hash.';
COMMENT ON FUNCTION verify_chain(BIGINT, BIGINT) IS 'FR82: Verifies hash chain integrity over a sequence range. Returns is_valid=TRUE if chain is intact, FALSE with details if broken.';
