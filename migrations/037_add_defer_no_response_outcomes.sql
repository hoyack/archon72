-- Migration 037: Add DEFER and NO_RESPONSE dispositions
-- Expands deliberation outcomes and petition states to support defer/no-response.

-- Add new deliberation outcomes
ALTER TYPE deliberation_outcome ADD VALUE IF NOT EXISTS 'DEFER';
ALTER TYPE deliberation_outcome ADD VALUE IF NOT EXISTS 'NO_RESPONSE';

-- Add new petition terminal states
ALTER TYPE petition_state_enum ADD VALUE IF NOT EXISTS 'DEFERRED';
ALTER TYPE petition_state_enum ADD VALUE IF NOT EXISTS 'NO_RESPONSE';

-- Update comments for clarity
COMMENT ON COLUMN petition_submissions.state IS
'Petition state: RECEIVED, DELIBERATING, ACKNOWLEDGED, REFERRED, ESCALATED, DEFERRED, NO_RESPONSE';

COMMENT ON COLUMN deliberation_sessions.outcome IS
'Final outcome: ACKNOWLEDGE, REFER, ESCALATE, DEFER, or NO_RESPONSE (Five Fates)';

COMMENT ON COLUMN dissent_records.dissent_disposition IS
'What the dissenter voted for (ACKNOWLEDGE, REFER, ESCALATE, DEFER, or NO_RESPONSE)';

COMMENT ON COLUMN dissent_records.majority_disposition IS
'What the majority voted for (ACKNOWLEDGE, REFER, ESCALATE, DEFER, or NO_RESPONSE)';
