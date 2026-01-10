-- Migration: Witness Attribution Validation
-- Story: 1.4 Witness Attribution - Atomic (FR4-FR5, RT-1)
-- Date: 2026-01-06
--
-- Constitutional Constraints:
--   CT-12: Witnessing creates accountability
--   FR4: Events must have atomic witness attribution
--   FR5: No unwitnessed events can exist
--
-- Note: witness_id and witness_signature columns already exist in events table
-- (created in migration 001). This migration adds validation triggers.

-- ============================================================================
-- TASK 5: Witness Attribution Validation Trigger (AC4)
-- ============================================================================

-- Function to validate witness attribution on insert
CREATE OR REPLACE FUNCTION validate_witness_attribution()
RETURNS TRIGGER AS $$
BEGIN
    -- FR5: witness_id must be present and non-empty
    IF NEW.witness_id IS NULL OR NEW.witness_id = '' THEN
        RAISE EXCEPTION 'FR5: Witness attribution required - witness_id missing';
    END IF;

    -- FR5: witness_signature must be present and non-empty
    IF NEW.witness_signature IS NULL OR NEW.witness_signature = '' THEN
        RAISE EXCEPTION 'FR5: Witness attribution required - witness_signature missing';
    END IF;

    -- FR4: Validate witness_id format (must start with WITNESS:)
    IF NOT NEW.witness_id LIKE 'WITNESS:%' THEN
        RAISE EXCEPTION 'FR4: Invalid witness_id format - must start with WITNESS:';
    END IF;

    -- FR4: Validate witness signature length (Ed25519 = 64 bytes = ~88 base64 chars)
    -- Base64 encoding of 64 bytes produces 86-88 chars depending on padding
    IF length(NEW.witness_signature) < 80 OR length(NEW.witness_signature) > 100 THEN
        RAISE EXCEPTION 'FR4: Invalid witness signature - unexpected length (expected 80-100 chars, got %)', length(NEW.witness_signature);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for witness validation (BEFORE INSERT)
DROP TRIGGER IF EXISTS validate_witness_attribution_on_insert ON events;
CREATE TRIGGER validate_witness_attribution_on_insert
    BEFORE INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION validate_witness_attribution();

-- ============================================================================
-- COMMENTS for documentation
-- ============================================================================

COMMENT ON FUNCTION validate_witness_attribution() IS 'FR4/FR5: Validates witness attribution on event insert - ensures witness_id format and signature presence';
COMMENT ON TRIGGER validate_witness_attribution_on_insert ON events IS 'FR4/FR5: Validates witness attribution before event insert';
