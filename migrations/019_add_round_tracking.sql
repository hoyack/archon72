-- Migration 019: Add round tracking columns for deadlock detection
-- Story 2B.3: Deadlock Detection & Auto-Escalation
-- FR-11.10: System SHALL auto-ESCALATE after 3 rounds without supermajority
-- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
-- AT-1: Every petition terminates in exactly one of Three Fates

-- ==========================================================
-- Add columns for round tracking and deadlock state
-- ==========================================================

-- Add round_count column (starts at 1, increments on each retry)
ALTER TABLE deliberation_sessions
ADD COLUMN round_count INTEGER NOT NULL DEFAULT 1;

-- Add votes_by_round to track vote distributions from each round
-- Each element is a JSON object like {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}
ALTER TABLE deliberation_sessions
ADD COLUMN votes_by_round JSONB[] NOT NULL DEFAULT '{}';

-- Add is_deadlocked flag to indicate deadlock-triggered escalation
ALTER TABLE deliberation_sessions
ADD COLUMN is_deadlocked BOOLEAN NOT NULL DEFAULT FALSE;

-- Add deadlock_reason for audit trail (e.g., "DEADLOCK_MAX_ROUNDS_EXCEEDED")
ALTER TABLE deliberation_sessions
ADD COLUMN deadlock_reason TEXT;

-- Add timeout tracking columns (Story 2B.2)
ALTER TABLE deliberation_sessions
ADD COLUMN timeout_job_id UUID;

ALTER TABLE deliberation_sessions
ADD COLUMN timeout_at TIMESTAMPTZ;

ALTER TABLE deliberation_sessions
ADD COLUMN timed_out BOOLEAN NOT NULL DEFAULT FALSE;

-- ==========================================================
-- Constraints for round tracking invariants
-- ==========================================================

-- Round count must be positive
ALTER TABLE deliberation_sessions
ADD CONSTRAINT check_round_count_positive CHECK (round_count >= 1);

-- Deadlock reason must be set if is_deadlocked is true
ALTER TABLE deliberation_sessions
ADD CONSTRAINT check_deadlock_has_reason CHECK (
    (is_deadlocked = TRUE AND deadlock_reason IS NOT NULL) OR
    (is_deadlocked = FALSE)
);

-- Deadlocked sessions must have ESCALATE outcome
ALTER TABLE deliberation_sessions
ADD CONSTRAINT check_deadlock_has_escalate CHECK (
    (is_deadlocked = TRUE AND outcome = 'ESCALATE') OR
    (is_deadlocked = FALSE)
);

-- Deadlocked sessions must be COMPLETE
ALTER TABLE deliberation_sessions
ADD CONSTRAINT check_deadlock_is_complete CHECK (
    (is_deadlocked = TRUE AND phase = 'COMPLETE') OR
    (is_deadlocked = FALSE)
);

-- Timed out sessions must have ESCALATE outcome
ALTER TABLE deliberation_sessions
ADD CONSTRAINT check_timeout_has_escalate CHECK (
    (timed_out = TRUE AND outcome = 'ESCALATE') OR
    (timed_out = FALSE)
);

-- Timed out sessions must be COMPLETE
ALTER TABLE deliberation_sessions
ADD CONSTRAINT check_timeout_is_complete CHECK (
    (timed_out = TRUE AND phase = 'COMPLETE') OR
    (timed_out = FALSE)
);

-- Timeout_at must be set with timeout_job_id
ALTER TABLE deliberation_sessions
ADD CONSTRAINT check_timeout_consistency CHECK (
    (timeout_job_id IS NOT NULL AND timeout_at IS NOT NULL) OR
    (timeout_job_id IS NULL AND timeout_at IS NULL)
);

-- ==========================================================
-- Indexes for new columns
-- ==========================================================

-- Index for finding deadlocked sessions
CREATE INDEX idx_deliberation_sessions_deadlocked
    ON deliberation_sessions(is_deadlocked)
    WHERE is_deadlocked = TRUE;

-- Index for finding timed out sessions
CREATE INDEX idx_deliberation_sessions_timed_out
    ON deliberation_sessions(timed_out)
    WHERE timed_out = TRUE;

-- Index for sessions with scheduled timeouts
CREATE INDEX idx_deliberation_sessions_timeout_scheduled
    ON deliberation_sessions(timeout_at)
    WHERE timeout_job_id IS NOT NULL AND phase != 'COMPLETE';

-- Index for finding sessions by round count (deadlock analysis)
CREATE INDEX idx_deliberation_sessions_high_rounds
    ON deliberation_sessions(round_count)
    WHERE round_count > 1 AND phase != 'COMPLETE';

-- ==========================================================
-- Comments for documentation
-- ==========================================================

COMMENT ON COLUMN deliberation_sessions.round_count IS
'Current voting round (starts at 1, increments on 1-1-1 split retries) (FR-11.10)';

COMMENT ON COLUMN deliberation_sessions.votes_by_round IS
'Vote distributions from each completed round for audit trail (NFR-6.5)';

COMMENT ON COLUMN deliberation_sessions.is_deadlocked IS
'True if session terminated due to deadlock (FR-11.10, CT-11)';

COMMENT ON COLUMN deliberation_sessions.deadlock_reason IS
'Reason code for deadlock (e.g., DEADLOCK_MAX_ROUNDS_EXCEEDED)';

COMMENT ON COLUMN deliberation_sessions.timeout_job_id IS
'UUID of scheduled timeout job (Story 2B.2, FR-11.9)';

COMMENT ON COLUMN deliberation_sessions.timeout_at IS
'Timestamp when timeout will fire (Story 2B.2, FR-11.9)';

COMMENT ON COLUMN deliberation_sessions.timed_out IS
'True if session terminated due to timeout (Story 2B.2, HC-7)';
