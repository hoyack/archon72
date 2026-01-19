-- Migration: Create Job Queue Infrastructure
-- Story: petition-0-4-job-queue-infrastructure
-- Date: 2026-01-19
-- Constitutional Constraints: CT-11, CT-12, HP-1, HC-6, NFR-7.5, FM-7.1
--
-- This creates the job queue infrastructure for deadline monitoring,
-- supporting referral timeouts and deliberation timeouts in the
-- Three Fates petition system.

-- ============================================================================
-- STEP 1: Create Job Status Enum
-- ============================================================================

CREATE TYPE job_status_enum AS ENUM (
    'pending',     -- Job scheduled, waiting for execution time
    'processing',  -- Job claimed by worker, execution in progress
    'completed',   -- Job successfully executed
    'failed'       -- Job failed (will be retried or moved to DLQ)
);

-- ============================================================================
-- STEP 2: Create Scheduled Jobs Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id UUID PRIMARY KEY,
    job_type TEXT NOT NULL,                           -- e.g., 'referral_timeout', 'deliberation_timeout'
    payload JSONB NOT NULL,                           -- Job-specific data (petition_id, etc.)
    scheduled_for TIMESTAMPTZ NOT NULL,               -- When to execute
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),    -- When job was scheduled
    attempts INT NOT NULL DEFAULT 0,                  -- Number of execution attempts
    last_attempt_at TIMESTAMPTZ,                      -- Last execution attempt timestamp
    status job_status_enum NOT NULL DEFAULT 'pending' -- Current job status
);

-- ============================================================================
-- STEP 3: Create Dead Letter Queue Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id UUID PRIMARY KEY,
    original_job_id UUID NOT NULL,                    -- Reference to original job ID
    job_type TEXT NOT NULL,                           -- Copied from scheduled_jobs
    payload JSONB NOT NULL,                           -- Copied from scheduled_jobs
    failure_reason TEXT NOT NULL,                     -- Why the job ultimately failed
    failed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),     -- When job was moved to DLQ
    attempts INT NOT NULL                             -- Total attempts before failure
);

-- ============================================================================
-- STEP 4: Create Performance Indexes
-- ============================================================================

-- Primary polling index: Find pending jobs due for execution
-- Used by SELECT FOR UPDATE SKIP LOCKED query
CREATE INDEX idx_scheduled_jobs_status_scheduled
    ON scheduled_jobs(status, scheduled_for)
    WHERE status = 'pending';

-- Dead letter queue monitoring: Find oldest failures for alerting (HC-6)
CREATE INDEX idx_dead_letter_created
    ON dead_letter_queue(failed_at);

-- Additional useful indexes
CREATE INDEX idx_scheduled_jobs_job_type
    ON scheduled_jobs(job_type);

CREATE INDEX idx_dead_letter_job_type
    ON dead_letter_queue(job_type);

-- ============================================================================
-- STEP 5: Comments for Documentation (CT-11: All components documented)
-- ============================================================================

COMMENT ON TABLE scheduled_jobs IS
    'Job queue for deadline monitoring (HP-1). Supports referral/deliberation timeouts.';
COMMENT ON COLUMN scheduled_jobs.id IS
    'UUIDv7 primary key for job identification';
COMMENT ON COLUMN scheduled_jobs.job_type IS
    'Job type identifier: referral_timeout, deliberation_timeout, escalation_check';
COMMENT ON COLUMN scheduled_jobs.payload IS
    'JSONB payload with job-specific data (petition_id, deadline details, etc.)';
COMMENT ON COLUMN scheduled_jobs.scheduled_for IS
    'Timestamp when job should be executed (UTC)';
COMMENT ON COLUMN scheduled_jobs.created_at IS
    'Timestamp when job was scheduled (UTC)';
COMMENT ON COLUMN scheduled_jobs.attempts IS
    'Number of execution attempts (max 3 before DLQ)';
COMMENT ON COLUMN scheduled_jobs.last_attempt_at IS
    'Timestamp of last execution attempt (UTC)';
COMMENT ON COLUMN scheduled_jobs.status IS
    'Job status: pending, processing, completed, failed';

COMMENT ON TABLE dead_letter_queue IS
    'Dead letter queue for failed jobs (HC-6). Triggers alerting when depth > 0.';
COMMENT ON COLUMN dead_letter_queue.id IS
    'UUIDv7 primary key for DLQ entry';
COMMENT ON COLUMN dead_letter_queue.original_job_id IS
    'Reference to the original scheduled_jobs.id';
COMMENT ON COLUMN dead_letter_queue.job_type IS
    'Copied job type for independent querying';
COMMENT ON COLUMN dead_letter_queue.payload IS
    'Copied payload for debugging and retry analysis';
COMMENT ON COLUMN dead_letter_queue.failure_reason IS
    'Detailed reason for job failure';
COMMENT ON COLUMN dead_letter_queue.failed_at IS
    'Timestamp when job was moved to DLQ (UTC)';
COMMENT ON COLUMN dead_letter_queue.attempts IS
    'Total execution attempts before failure';
