-- Migration: 021_create_acknowledgment_reason_enum
-- Story: 3.1 - Acknowledgment Reason Code Enumeration
-- FR-3.2: System SHALL require reason_code from enumerated values
-- FR-3.3: System SHALL require rationale text for REFUSED and NO_ACTION_WARRANTED
-- FR-3.4: System SHALL require reference_petition_id for DUPLICATE

BEGIN;

-- Create the enum type for acknowledgment reason codes
-- These codes are used when petitions receive the ACKNOWLEDGED fate
CREATE TYPE acknowledgment_reason_enum AS ENUM (
    'ADDRESSED',           -- Concern has been or will be addressed by existing governance action
    'NOTED',               -- Input has been recorded for future consideration
    'DUPLICATE',           -- Petition duplicates an existing or resolved petition (requires reference_petition_id)
    'OUT_OF_SCOPE',        -- Matter falls outside governance jurisdiction
    'REFUSED',             -- Petition violates policy or norms (requires rationale)
    'NO_ACTION_WARRANTED', -- After review, no action is appropriate (requires rationale)
    'WITHDRAWN',           -- Petitioner withdrew the petition
    'EXPIRED'              -- Referral timeout with no Knight response
);

-- Add comment for documentation and future maintainers
COMMENT ON TYPE acknowledgment_reason_enum IS
    'Acknowledgment reason codes per FR-3.2. REFUSED and NO_ACTION_WARRANTED require rationale (FR-3.3). DUPLICATE requires reference_petition_id (FR-3.4).';

COMMIT;

-- Rollback command (for reference):
-- DROP TYPE IF EXISTS acknowledgment_reason_enum;
