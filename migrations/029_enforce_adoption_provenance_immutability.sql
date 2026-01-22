-- Migration 029: Enforce Adoption Provenance Immutability (Story 6.6, FR-5.7, NFR-6.2)
--
-- Constitutional Constraints:
-- - FR-5.7: Adopted Motion SHALL include source_petition_ref (immutable) [P0]
-- - NFR-6.2: Adoption provenance immutability
-- - Story 6.6 AC: Immutability enforced at database level (trigger or constraint)
--
-- This migration adds a trigger to prevent modification of adoption provenance
-- fields once they are set. This provides database-level enforcement of the
-- constitutional requirement that "the link between Motion and source petition
-- cannot be altered."
--
-- Fields Protected:
-- - adopted_as_motion_id: Cannot be changed once set
-- - adopted_by_king_id: Cannot be changed once set
-- - adopted_at: Cannot be changed once set
--
-- Author: Story 6.6 - Adoption Provenance Immutability
-- Date: 2026-01-22

-- Create trigger function to prevent modification of adoption provenance
CREATE OR REPLACE FUNCTION prevent_adoption_provenance_modification()
RETURNS TRIGGER AS $$
BEGIN
    -- If adoption fields are already set (not NULL), prevent any modification
    IF OLD.adopted_as_motion_id IS NOT NULL THEN
        -- Prevent changing adopted_as_motion_id
        IF NEW.adopted_as_motion_id IS DISTINCT FROM OLD.adopted_as_motion_id THEN
            RAISE EXCEPTION 'IMMUTABLE_FIELD: Cannot modify adopted_as_motion_id once set (FR-5.7, NFR-6.2)'
                USING ERRCODE = '23502',  -- not_null_violation used as marker
                      DETAIL = format('Petition %s: attempted to change adopted_as_motion_id from %s to %s',
                                     OLD.id, OLD.adopted_as_motion_id, NEW.adopted_as_motion_id),
                      HINT = 'Adoption provenance is immutable per Story 6.6';
        END IF;

        -- Prevent changing adopted_by_king_id
        IF NEW.adopted_by_king_id IS DISTINCT FROM OLD.adopted_by_king_id THEN
            RAISE EXCEPTION 'IMMUTABLE_FIELD: Cannot modify adopted_by_king_id once set (FR-5.7, NFR-6.2)'
                USING ERRCODE = '23502',
                      DETAIL = format('Petition %s: attempted to change adopted_by_king_id from %s to %s',
                                     OLD.id, OLD.adopted_by_king_id, NEW.adopted_by_king_id),
                      HINT = 'Adoption provenance is immutable per Story 6.6';
        END IF;

        -- Prevent changing adopted_at
        IF NEW.adopted_at IS DISTINCT FROM OLD.adopted_at THEN
            RAISE EXCEPTION 'IMMUTABLE_FIELD: Cannot modify adopted_at once set (FR-5.7, NFR-6.2)'
                USING ERRCODE = '23502',
                      DETAIL = format('Petition %s: attempted to change adopted_at from %s to %s',
                                     OLD.id, OLD.adopted_at, NEW.adopted_at),
                      HINT = 'Adoption provenance is immutable per Story 6.6';
        END IF;
    END IF;

    -- Allow the update if no provenance fields were modified
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to petition_submissions table
CREATE TRIGGER enforce_adoption_provenance_immutability
    BEFORE UPDATE ON petition_submissions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_adoption_provenance_modification();

-- Add comment explaining the trigger
COMMENT ON TRIGGER enforce_adoption_provenance_immutability ON petition_submissions IS
'Enforces immutability of adoption provenance fields (adopted_as_motion_id, adopted_by_king_id, adopted_at) once set. Per Story 6.6, FR-5.7, NFR-6.2: the link between Motion and source petition cannot be altered.';

COMMENT ON FUNCTION prevent_adoption_provenance_modification() IS
'Trigger function that prevents modification of adoption provenance fields. Raises IMMUTABLE_FIELD error if an update attempts to change adopted_as_motion_id, adopted_by_king_id, or adopted_at after they have been set.';
