-- Migration: 016_create_rate_limit_buckets.sql
-- Story: petition-1-4-submitter-rate-limiting
-- Purpose: PostgreSQL time-bucket counters for per-submitter rate limiting (D4)
-- References: FR-1.5, HC-4, NFR-5.1
--
-- Architecture Decision D4: Rate Limiting Strategy
-- - Minute buckets summed over last hour for sliding window
-- - Persistent and distributed-safe via PostgreSQL
-- - Bounded by periodic TTL cleanup (buckets older than 2 hours)
-- - Rate-limit blocks surfaced to client via D7 error format

-- Rate limit bucket table for per-submitter tracking
CREATE TABLE IF NOT EXISTS petition_rate_limit_buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Submitter identity (FK to users table when available)
    submitter_id UUID NOT NULL,

    -- Minute bucket timestamp (truncated to minute boundary)
    bucket_minute TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Count of submissions in this minute bucket
    count INTEGER NOT NULL DEFAULT 1 CHECK (count > 0),

    -- Audit timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Unique constraint for UPSERT operations
    -- Allows INSERT ... ON CONFLICT (submitter_id, bucket_minute) DO UPDATE
    CONSTRAINT uq_rate_limit_bucket UNIQUE (submitter_id, bucket_minute)
);

-- Add table comment for documentation
COMMENT ON TABLE petition_rate_limit_buckets IS
    'Time-bucket counters for per-submitter rate limiting (D4). '
    'Minute buckets summed over sliding window (default 60 min). '
    'Story: petition-1-4-submitter-rate-limiting. Refs: FR-1.5, HC-4, NFR-5.1.';

COMMENT ON COLUMN petition_rate_limit_buckets.submitter_id IS
    'UUID of the submitter being rate-limited';

COMMENT ON COLUMN petition_rate_limit_buckets.bucket_minute IS
    'Minute boundary timestamp (truncated to minute precision)';

COMMENT ON COLUMN petition_rate_limit_buckets.count IS
    'Number of submissions recorded in this minute bucket';

-- Index for efficient sliding window queries
-- Pattern: SELECT SUM(count) FROM ... WHERE submitter_id = $1 AND bucket_minute > NOW() - INTERVAL '60 minutes'
CREATE INDEX IF NOT EXISTS idx_rate_limit_submitter_minute
    ON petition_rate_limit_buckets(submitter_id, bucket_minute DESC);

-- Index for TTL cleanup operations
-- Pattern: DELETE FROM ... WHERE bucket_minute < NOW() - INTERVAL '2 hours'
CREATE INDEX IF NOT EXISTS idx_rate_limit_bucket_cleanup
    ON petition_rate_limit_buckets(bucket_minute);
