-- Migration 006: Create halt_state table (Story 3.3, Task 2)
-- ADR-3: Partition Behavior + Halt Durability
--
-- This table stores the system halt state as a singleton row.
-- The DB halt flag is the canonical source of truth.
--
-- Constitutional Constraints:
-- - CT-11: Silent failure destroys legitimacy -> DB is authoritative
-- - CT-12: Witnessing creates accountability -> crisis_event_id links to trigger
-- - CT-13: Integrity outranks availability -> DB is canonical
--
-- Singleton Pattern:
-- - Only one row exists (id = fixed UUID)
-- - Upsert operations ensure atomicity
-- - Constraint prevents multiple rows

-- Create halt_state table
CREATE TABLE IF NOT EXISTS halt_state (
    -- Fixed UUID for singleton pattern (only one row allowed)
    id UUID PRIMARY KEY DEFAULT '00000000-0000-0000-0000-000000000001'::uuid,

    -- Whether the system is currently halted
    is_halted BOOLEAN NOT NULL DEFAULT FALSE,

    -- Human-readable reason for halt (e.g., "FR17: Fork detected")
    reason TEXT,

    -- UUID of the ConstitutionalCrisisEvent that triggered halt
    -- Links halt to its audit trail
    crisis_event_id UUID,

    -- When the halt was triggered (NULL if not halted)
    halted_at TIMESTAMPTZ,

    -- Last update timestamp (auto-updated by trigger)
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Enforce singleton pattern: only the fixed UUID row is allowed
    CONSTRAINT single_halt_row CHECK (id = '00000000-0000-0000-0000-000000000001'::uuid),

    -- Reason is required when halted
    CONSTRAINT halt_reason_required CHECK (
        (is_halted = FALSE) OR (is_halted = TRUE AND reason IS NOT NULL)
    )
);

-- Create index on is_halted for fast halt checks
CREATE INDEX IF NOT EXISTS idx_halt_state_is_halted ON halt_state(is_halted);

-- Insert the initial singleton row (not halted)
INSERT INTO halt_state (id, is_halted, reason, crisis_event_id, halted_at)
VALUES ('00000000-0000-0000-0000-000000000001'::uuid, FALSE, NULL, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_halt_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();

    -- Set halted_at when transitioning to halted state
    IF NEW.is_halted = TRUE AND OLD.is_halted = FALSE THEN
        NEW.halted_at = NOW();
    END IF;

    -- Clear halted_at when transitioning to not halted
    IF NEW.is_halted = FALSE AND OLD.is_halted = TRUE THEN
        NEW.halted_at = NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamps
DROP TRIGGER IF EXISTS halt_state_updated ON halt_state;
CREATE TRIGGER halt_state_updated
    BEFORE UPDATE ON halt_state
    FOR EACH ROW
    EXECUTE FUNCTION update_halt_state_timestamp();

-- Add comment for documentation
COMMENT ON TABLE halt_state IS 'Singleton table for system halt state (ADR-3: Dual-channel halt, DB is canonical)';
COMMENT ON COLUMN halt_state.is_halted IS 'Whether the system is currently halted';
COMMENT ON COLUMN halt_state.reason IS 'Human-readable reason for halt (e.g., FR17: Fork detected)';
COMMENT ON COLUMN halt_state.crisis_event_id IS 'UUID of the ConstitutionalCrisisEvent that triggered halt';
COMMENT ON COLUMN halt_state.halted_at IS 'Timestamp when halt was triggered';
COMMENT ON COLUMN halt_state.updated_at IS 'Last modification timestamp (auto-updated)';
