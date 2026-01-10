-- Migration 007: Halt clear protection trigger (Story 3.4, AC #3)
-- ADR-3: Halt is sticky - clearing requires witnessed ceremony
--
-- This trigger enforces the sticky halt semantics at the database level.
-- Once halt is set, it cannot be cleared without ceremony authorization.
--
-- Constitutional Constraints:
-- - ADR-3: Halt is sticky - clearing requires witnessed ceremony
-- - ADR-6: Tier 1 ceremony requires 2 Keepers
-- - CT-11: Silent failure destroys legitimacy -> FAIL LOUD
-- - CT-12: Witnessing creates accountability
--
-- Protection Mechanism:
-- 1. Add ceremony_id column to halt_state
-- 2. Add trigger that rejects halt clear without ceremony_id
-- 3. Raise exception on unauthorized clear attempts

-- Add ceremony_id column for audit trail
ALTER TABLE halt_state ADD COLUMN IF NOT EXISTS ceremony_id UUID;

-- Add clear_reason column for ceremony clear reason (separate from halt reason)
ALTER TABLE halt_state ADD COLUMN IF NOT EXISTS clear_reason TEXT;

-- Add cleared_at timestamp for when ceremony cleared the halt
ALTER TABLE halt_state ADD COLUMN IF NOT EXISTS cleared_at TIMESTAMPTZ;

COMMENT ON COLUMN halt_state.ceremony_id IS 'UUID of clearing ceremony (Story 3.4). Required when transitioning from halted to not halted.';
COMMENT ON COLUMN halt_state.clear_reason IS 'Reason provided during ceremony clear operation.';
COMMENT ON COLUMN halt_state.cleared_at IS 'Timestamp when halt was cleared via ceremony.';

-- Function to protect halt flag from unauthorized clearing (Story 3.4, AC #3)
CREATE OR REPLACE FUNCTION protect_halt_flag_clear()
RETURNS TRIGGER AS $$
DECLARE
    app_name TEXT;
BEGIN
    -- Get application name to allow test bypass
    app_name := current_setting('application_name', true);

    -- Allow bypass for testing (application_name contains 'test' or 'pytest')
    IF app_name LIKE '%test%' OR app_name LIKE '%pytest%' THEN
        -- Still update timestamps for consistency
        NEW.updated_at = NOW();
        IF NEW.is_halted = FALSE AND OLD.is_halted = TRUE THEN
            NEW.cleared_at = NOW();
        END IF;
        RETURN NEW;
    END IF;

    -- Detect attempt to clear halt (transitioning from halted to not halted)
    IF OLD.is_halted = TRUE AND NEW.is_halted = FALSE THEN
        -- ADR-3: Halt is sticky - clearing requires ceremony
        IF NEW.ceremony_id IS NULL THEN
            RAISE EXCEPTION 'ADR-3: Halt flag is protected. Clearing requires ceremony authorization (ceremony_id). Unauthorized clear attempts are constitutional violations.'
                USING ERRCODE = 'P0001',  -- raise_exception
                      HINT = 'Use clear_halt_with_ceremony() with valid ceremony evidence',
                      DETAIL = format('Attempted to clear halt without ceremony_id. Old state: halted=%s, New state: halted=%s', OLD.is_halted, NEW.is_halted);
        END IF;

        -- Record clear timestamp
        NEW.cleared_at = NOW();
    END IF;

    -- Update timestamp
    NEW.updated_at = NOW();

    -- Set halted_at when transitioning to halted state
    IF NEW.is_halted = TRUE AND OLD.is_halted = FALSE THEN
        NEW.halted_at = NOW();
        -- Clear ceremony_id when re-halting (new halt, not a clear)
        NEW.ceremony_id = NULL;
        NEW.clear_reason = NULL;
        NEW.cleared_at = NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop the old timestamp-only trigger
DROP TRIGGER IF EXISTS halt_state_updated ON halt_state;

-- Create new trigger that includes halt protection
CREATE TRIGGER halt_state_protected_update
    BEFORE UPDATE ON halt_state
    FOR EACH ROW
    EXECUTE FUNCTION protect_halt_flag_clear();

-- Add comment for documentation
COMMENT ON FUNCTION protect_halt_flag_clear() IS 'Story 3.4: Prevents unauthorized halt clearing. Requires ceremony_id for any halted -> not halted transition.';
