-- ============================================================================
-- SPIKE MIGRATION: DB-Level Hash Computation and Verification
-- Story: 1.7 Supabase Trigger Spike (SR-3)
-- Status: EXPERIMENTAL - GO decision made (see docs/spikes/1-7-supabase-trigger-spike-report.md)
-- Date: 2026-01-06
-- Decision: GO - Approved for production implementation
--
-- Purpose: Validate that Postgres triggers can compute and verify SHA-256
--          content hashes, narrowing the trust boundary per ADR-1.
--
-- Constitutional Constraints:
--   CT-11: Silent failure destroys legitimacy - triggers must REJECT invalid
--   CT-12: Witnessing creates accountability - hash chain is the witness
--   DEB-001: Use standard Postgres only (no Supabase-specific functions)
--
-- Dependencies:
--   - pgcrypto extension (standard Postgres, pre-enabled in Supabase)
--
-- ============================================================================

-- ============================================================================
-- TASK 1: Enable pgcrypto extension (AC1 - Subtask 1.1)
-- ============================================================================

-- pgcrypto is usually pre-enabled in Supabase, but ensure it exists
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Verify pgcrypto is available by testing digest function
DO $$
BEGIN
    -- Test SHA-256 hash computation
    IF encode(digest('test', 'sha256'), 'hex') IS NULL THEN
        RAISE EXCEPTION 'pgcrypto extension not working - digest() returned NULL';
    END IF;
    RAISE NOTICE 'pgcrypto extension verified: SHA-256 digest working';
END;
$$;

-- ============================================================================
-- TASK 1: Create spike test table (AC1 - Subtask 1.2)
-- ============================================================================

-- Create a separate spike table to avoid modifying production events table
-- This mirrors the events table structure but is isolated for testing
DROP TABLE IF EXISTS events_spike CASCADE;

CREATE TABLE events_spike (
    -- Primary identifier
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Sequence for ordering (append-only)
    sequence BIGSERIAL UNIQUE NOT NULL,

    -- Event type classification
    event_type TEXT NOT NULL,

    -- Event payload (JSONB for structured data)
    payload JSONB NOT NULL,

    -- Hash chain fields
    prev_hash TEXT NOT NULL,
    content_hash TEXT, -- Will be computed by trigger

    -- Signature fields (simplified for spike)
    signature TEXT NOT NULL DEFAULT 'spike_signature',

    -- Algorithm versioning
    hash_alg_version SMALLINT NOT NULL DEFAULT 1,
    sig_alg_version SMALLINT NOT NULL DEFAULT 1,

    -- Agent attribution
    agent_id TEXT DEFAULT 'spike_agent',

    -- Witness attribution (simplified for spike)
    witness_id TEXT NOT NULL DEFAULT 'spike_witness',
    witness_signature TEXT NOT NULL DEFAULT 'spike_witness_sig',

    -- Timestamps
    local_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Spike metadata
    spike_computed_at TIMESTAMPTZ,
    spike_verified_at TIMESTAMPTZ
);

-- Index on sequence for efficient ordering queries
CREATE INDEX IF NOT EXISTS idx_events_spike_sequence ON events_spike (sequence);

COMMENT ON TABLE events_spike IS 'SPIKE: Isolated test table for hash trigger validation. Do NOT use for production.';

-- ============================================================================
-- TASK 2: Canonical JSON Serialization Function (AC1 - Subtask 2.3)
-- ============================================================================

-- Function to produce canonical JSON with sorted keys
-- This is critical for deterministic hash computation
CREATE OR REPLACE FUNCTION spike_canonical_jsonb(input_jsonb JSONB)
RETURNS TEXT AS $$
DECLARE
    result TEXT;
    key_val RECORD;
    arr_elem JSONB;
    is_first BOOLEAN := TRUE;
    elem_type TEXT;
BEGIN
    -- Handle NULL
    IF input_jsonb IS NULL THEN
        RETURN 'null';
    END IF;

    -- Get the type of the JSONB value
    elem_type := jsonb_typeof(input_jsonb);

    -- Handle different JSONB types
    CASE elem_type
        WHEN 'object' THEN
            -- For objects, iterate keys in sorted order
            result := '{';
            FOR key_val IN
                SELECT key, value
                FROM jsonb_each(input_jsonb)
                ORDER BY key ASC  -- Canonical: sorted by key
            LOOP
                IF NOT is_first THEN
                    result := result || ',';
                END IF;
                is_first := FALSE;
                -- Recursively canonicalize nested values
                result := result || '"' || key_val.key || '":' ||
                          spike_canonical_jsonb(key_val.value);
            END LOOP;
            result := result || '}';
            RETURN result;

        WHEN 'array' THEN
            -- For arrays, maintain order but canonicalize elements
            result := '[';
            FOR arr_elem IN
                SELECT value FROM jsonb_array_elements(input_jsonb)
            LOOP
                IF NOT is_first THEN
                    result := result || ',';
                END IF;
                is_first := FALSE;
                result := result || spike_canonical_jsonb(arr_elem);
            END LOOP;
            result := result || ']';
            RETURN result;

        WHEN 'string' THEN
            -- Strings: return as JSON string (with quotes)
            RETURN input_jsonb::text;

        WHEN 'number' THEN
            -- Numbers: return as-is
            RETURN input_jsonb::text;

        WHEN 'boolean' THEN
            -- Booleans: return as-is
            RETURN input_jsonb::text;

        WHEN 'null' THEN
            RETURN 'null';

        ELSE
            -- Fallback for unknown types
            RETURN input_jsonb::text;
    END CASE;
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;

COMMENT ON FUNCTION spike_canonical_jsonb(JSONB) IS 'SPIKE: Produces canonical JSON with sorted keys for deterministic hashing';

-- ============================================================================
-- TASK 2: Hash Computation Function (AC1 - Subtasks 2.1, 2.2)
-- ============================================================================

-- Function to compute content_hash from event data
-- Hash input: event_type | canonical_payload | prev_hash
CREATE OR REPLACE FUNCTION spike_compute_content_hash()
RETURNS TRIGGER AS $$
DECLARE
    canonical_payload TEXT;
    hash_input TEXT;
    computed_hash TEXT;
BEGIN
    -- Step 1: Canonicalize the payload JSON (sorted keys)
    canonical_payload := spike_canonical_jsonb(NEW.payload);

    -- Step 2: Build deterministic hash input
    -- Format: event_type|canonical_payload|prev_hash
    -- Using pipe delimiter to prevent ambiguity
    hash_input := NEW.event_type || '|' || canonical_payload || '|' || NEW.prev_hash;

    -- Step 3: Compute SHA-256 hash using pgcrypto
    computed_hash := encode(digest(hash_input::bytea, 'sha256'), 'hex');

    -- Step 4: Assign computed hash to the event
    NEW.content_hash := computed_hash;

    -- Step 5: Record computation timestamp for spike analysis
    NEW.spike_computed_at := clock_timestamp();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION spike_compute_content_hash() IS 'SPIKE: Computes SHA-256 content_hash from event_type, payload, and prev_hash';

-- Create the BEFORE INSERT trigger for hash computation (AC1 - Subtask 2.4)
DROP TRIGGER IF EXISTS spike_compute_hash_trigger ON events_spike;
CREATE TRIGGER spike_compute_hash_trigger
    BEFORE INSERT ON events_spike
    FOR EACH ROW
    EXECUTE FUNCTION spike_compute_content_hash();

COMMENT ON TRIGGER spike_compute_hash_trigger ON events_spike IS 'SPIKE: Computes content_hash before insert';

-- ============================================================================
-- TASK 3: Hash Verification Function (AC1 - Subtasks 3.1, 3.2, 3.3)
-- ============================================================================

-- Function to verify that provided content_hash matches computed hash
-- This is for scenarios where application provides a hash and DB must verify
CREATE OR REPLACE FUNCTION spike_verify_content_hash()
RETURNS TRIGGER AS $$
DECLARE
    canonical_payload TEXT;
    hash_input TEXT;
    expected_hash TEXT;
BEGIN
    -- Only verify if content_hash was provided by application
    -- (In spike_compute_content_hash, we set it, so this would verify the computation)

    -- Step 1: Canonicalize the payload JSON
    canonical_payload := spike_canonical_jsonb(NEW.payload);

    -- Step 2: Build expected hash input
    hash_input := NEW.event_type || '|' || canonical_payload || '|' || NEW.prev_hash;

    -- Step 3: Compute expected SHA-256 hash
    expected_hash := encode(digest(hash_input::bytea, 'sha256'), 'hex');

    -- Step 4: Verify hash matches
    IF NEW.content_hash IS NULL THEN
        RAISE EXCEPTION 'FR82: Hash chain integrity violation - content_hash is NULL';
    END IF;

    IF NEW.content_hash != expected_hash THEN
        RAISE EXCEPTION 'FR82: Hash chain integrity violation - content_hash mismatch (expected %, got %)',
            expected_hash, NEW.content_hash;
    END IF;

    -- Step 5: Record verification timestamp for spike analysis
    NEW.spike_verified_at := clock_timestamp();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION spike_verify_content_hash() IS 'SPIKE: Verifies content_hash matches computed value';

-- Create the AFTER hash computation trigger for verification
-- This runs after spike_compute_content_hash to verify the computation
DROP TRIGGER IF EXISTS spike_verify_hash_trigger ON events_spike;
CREATE TRIGGER spike_verify_hash_trigger
    BEFORE INSERT ON events_spike
    FOR EACH ROW
    EXECUTE FUNCTION spike_verify_content_hash();

-- Ensure verify runs after compute by alphabetical ordering
-- Postgres executes BEFORE triggers in alphabetical order by name
-- "spike_compute..." < "spike_verify..." so compute runs first

-- ============================================================================
-- TASK 3: Hash Chain Verification (existing pattern from 002_hash_chain_verification.sql)
-- ============================================================================

-- Reuse the existing hash chain verification pattern for the spike table
CREATE OR REPLACE FUNCTION spike_verify_hash_chain_on_insert()
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
        FROM events_spike
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

-- This trigger must run AFTER content_hash is computed but verifies prev_hash chain
DROP TRIGGER IF EXISTS spike_chain_verify_trigger ON events_spike;
CREATE TRIGGER spike_chain_verify_trigger
    BEFORE INSERT ON events_spike
    FOR EACH ROW
    EXECUTE FUNCTION spike_verify_hash_chain_on_insert();

COMMENT ON FUNCTION spike_verify_hash_chain_on_insert() IS 'SPIKE: Verifies prev_hash links to previous event content_hash';

-- ============================================================================
-- TASK 4: Benchmark Helper Functions (AC2)
-- ============================================================================

-- Function to run sequential insert benchmark
CREATE OR REPLACE FUNCTION spike_benchmark_inserts(
    num_inserts INTEGER DEFAULT 1000,
    payload_size_bytes INTEGER DEFAULT 100
)
RETURNS TABLE (
    total_inserts INTEGER,
    total_time_ms NUMERIC,
    avg_time_per_insert_ms NUMERIC,
    min_time_ms NUMERIC,
    max_time_ms NUMERIC
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    i INTEGER;
    test_payload JSONB;
    prev_hash TEXT;
    genesis_hash TEXT := repeat('0', 64);
    insert_times NUMERIC[];
    single_start TIMESTAMP;
    single_end TIMESTAMP;
BEGIN
    -- Clear spike table for fresh benchmark
    TRUNCATE events_spike RESTART IDENTITY;

    -- Generate test payload of specified size
    test_payload := jsonb_build_object(
        'test_data', repeat('x', payload_size_bytes),
        'benchmark', true,
        'iteration', 0
    );

    -- Initialize timing array
    insert_times := ARRAY[]::NUMERIC[];

    -- Run benchmark
    start_time := clock_timestamp();

    FOR i IN 1..num_inserts LOOP
        -- Get prev_hash (genesis for first, last content_hash for rest)
        IF i = 1 THEN
            prev_hash := genesis_hash;
        ELSE
            SELECT content_hash INTO prev_hash
            FROM events_spike
            WHERE sequence = i - 1;
        END IF;

        -- Time individual insert
        single_start := clock_timestamp();

        INSERT INTO events_spike (
            event_type,
            payload,
            prev_hash
        ) VALUES (
            'benchmark_event',
            test_payload || jsonb_build_object('iteration', i),
            prev_hash
        );

        single_end := clock_timestamp();

        -- Record timing (in milliseconds)
        insert_times := array_append(insert_times,
            EXTRACT(MILLISECOND FROM (single_end - single_start)) +
            EXTRACT(SECOND FROM (single_end - single_start)) * 1000
        );
    END LOOP;

    end_time := clock_timestamp();

    -- Calculate statistics
    total_inserts := num_inserts;
    total_time_ms := EXTRACT(MILLISECOND FROM (end_time - start_time)) +
                     EXTRACT(SECOND FROM (end_time - start_time)) * 1000;
    avg_time_per_insert_ms := total_time_ms / num_inserts;

    -- Calculate min/max from array
    SELECT MIN(t), MAX(t) INTO min_time_ms, max_time_ms
    FROM unnest(insert_times) AS t;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION spike_benchmark_inserts(INTEGER, INTEGER) IS 'SPIKE: Benchmarks insert latency with hash triggers';

-- Function to calculate percentiles from benchmark
CREATE OR REPLACE FUNCTION spike_benchmark_percentiles(
    num_inserts INTEGER DEFAULT 1000,
    payload_size_bytes INTEGER DEFAULT 100
)
RETURNS TABLE (
    total_inserts INTEGER,
    avg_ms NUMERIC,
    p50_ms NUMERIC,
    p95_ms NUMERIC,
    p99_ms NUMERIC,
    max_ms NUMERIC
) AS $$
DECLARE
    i INTEGER;
    test_payload JSONB;
    prev_hash TEXT;
    genesis_hash TEXT := repeat('0', 64);
    single_start TIMESTAMP;
    single_end TIMESTAMP;
BEGIN
    -- Clear spike table for fresh benchmark
    TRUNCATE events_spike RESTART IDENTITY;

    -- Create temp table for timing data
    DROP TABLE IF EXISTS _spike_timings;
    CREATE TEMP TABLE _spike_timings (insert_ms NUMERIC);

    -- Generate test payload
    test_payload := jsonb_build_object(
        'test_data', repeat('x', payload_size_bytes),
        'benchmark', true
    );

    -- Run benchmark
    FOR i IN 1..num_inserts LOOP
        IF i = 1 THEN
            prev_hash := genesis_hash;
        ELSE
            SELECT content_hash INTO prev_hash
            FROM events_spike
            WHERE sequence = i - 1;
        END IF;

        single_start := clock_timestamp();

        INSERT INTO events_spike (
            event_type,
            payload,
            prev_hash
        ) VALUES (
            'benchmark_event',
            test_payload || jsonb_build_object('iteration', i),
            prev_hash
        );

        single_end := clock_timestamp();

        INSERT INTO _spike_timings VALUES (
            EXTRACT(MILLISECOND FROM (single_end - single_start)) +
            EXTRACT(SECOND FROM (single_end - single_start)) * 1000
        );
    END LOOP;

    -- Calculate percentiles
    total_inserts := num_inserts;

    SELECT
        AVG(insert_ms),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY insert_ms),
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY insert_ms),
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY insert_ms),
        MAX(insert_ms)
    INTO avg_ms, p50_ms, p95_ms, p99_ms, max_ms
    FROM _spike_timings;

    DROP TABLE _spike_timings;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION spike_benchmark_percentiles(INTEGER, INTEGER) IS 'SPIKE: Calculates insert latency percentiles';

-- ============================================================================
-- TASK 5: Edge Case Test Functions (AC3)
-- ============================================================================

-- Function to test large payloads
CREATE OR REPLACE FUNCTION spike_test_large_payload(size_kb INTEGER)
RETURNS TABLE (
    payload_size_kb INTEGER,
    insert_time_ms NUMERIC,
    hash_computed TEXT,
    success BOOLEAN
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    test_payload JSONB;
    genesis_hash TEXT := repeat('0', 64);
    result_hash TEXT;
BEGIN
    -- Clear table
    TRUNCATE events_spike RESTART IDENTITY;

    -- Generate large payload
    test_payload := jsonb_build_object(
        'large_data', repeat('x', size_kb * 1024),
        'size_kb', size_kb
    );

    payload_size_kb := size_kb;

    BEGIN
        start_time := clock_timestamp();

        INSERT INTO events_spike (
            event_type,
            payload,
            prev_hash
        ) VALUES (
            'large_payload_test',
            test_payload,
            genesis_hash
        )
        RETURNING content_hash INTO result_hash;

        end_time := clock_timestamp();

        insert_time_ms := EXTRACT(MILLISECOND FROM (end_time - start_time)) +
                          EXTRACT(SECOND FROM (end_time - start_time)) * 1000;
        hash_computed := result_hash;
        success := TRUE;
    EXCEPTION WHEN OTHERS THEN
        insert_time_ms := -1;
        hash_computed := SQLERRM;
        success := FALSE;
    END;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to test Unicode payloads
CREATE OR REPLACE FUNCTION spike_test_unicode_payload()
RETURNS TABLE (
    test_case TEXT,
    insert_success BOOLEAN,
    hash_length INTEGER,
    notes TEXT
) AS $$
DECLARE
    genesis_hash TEXT := repeat('0', 64);
    result_hash TEXT;
BEGIN
    TRUNCATE events_spike RESTART IDENTITY;

    -- Test 1: Basic Unicode
    test_case := 'basic_unicode';
    BEGIN
        INSERT INTO events_spike (event_type, payload, prev_hash)
        VALUES ('unicode_test', '{"message": "Hello"}'::jsonb, genesis_hash)
        RETURNING content_hash INTO result_hash;
        insert_success := TRUE;
        hash_length := length(result_hash);
        notes := 'Basic Unicode passed';
    EXCEPTION WHEN OTHERS THEN
        insert_success := FALSE;
        hash_length := 0;
        notes := SQLERRM;
    END;
    RETURN NEXT;

    -- Test 2: CJK Characters
    test_case := 'cjk_characters';
    BEGIN
        SELECT content_hash INTO genesis_hash FROM events_spike WHERE sequence = 1;
        INSERT INTO events_spike (event_type, payload, prev_hash)
        VALUES ('unicode_test', '{"message": "Hello World"}'::jsonb, genesis_hash)
        RETURNING content_hash INTO result_hash;
        insert_success := TRUE;
        hash_length := length(result_hash);
        notes := 'CJK characters passed';
    EXCEPTION WHEN OTHERS THEN
        insert_success := FALSE;
        hash_length := 0;
        notes := SQLERRM;
    END;
    RETURN NEXT;

    -- Test 3: Emoji
    test_case := 'emoji';
    BEGIN
        SELECT content_hash INTO genesis_hash FROM events_spike ORDER BY sequence DESC LIMIT 1;
        INSERT INTO events_spike (event_type, payload, prev_hash)
        VALUES ('unicode_test', '{"emoji": "test emoji"}'::jsonb, genesis_hash)
        RETURNING content_hash INTO result_hash;
        insert_success := TRUE;
        hash_length := length(result_hash);
        notes := 'Emoji passed';
    EXCEPTION WHEN OTHERS THEN
        insert_success := FALSE;
        hash_length := 0;
        notes := SQLERRM;
    END;
    RETURN NEXT;

    -- Test 4: Special JSON characters
    test_case := 'special_json_chars';
    BEGIN
        SELECT content_hash INTO genesis_hash FROM events_spike ORDER BY sequence DESC LIMIT 1;
        INSERT INTO events_spike (event_type, payload, prev_hash)
        VALUES ('unicode_test', '{"special": "quote\" backslash\\ newline\n tab\t"}'::jsonb, genesis_hash)
        RETURNING content_hash INTO result_hash;
        insert_success := TRUE;
        hash_length := length(result_hash);
        notes := 'Special JSON chars passed';
    EXCEPTION WHEN OTHERS THEN
        insert_success := FALSE;
        hash_length := 0;
        notes := SQLERRM;
    END;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS for documentation
-- ============================================================================

COMMENT ON TABLE events_spike IS 'SPIKE: Test table for hash trigger validation - Story 1.7';

-- ============================================================================
-- End of spike migration
-- ============================================================================
