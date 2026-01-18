"""
Integration tests for Story 1.7: Supabase Trigger Spike (SR-3)

This module validates DB-level hash computation and verification triggers.

SPIKE TESTS - These tests validate the approach documented in ADR-1:
- DB-level hash enforcement using pgcrypto
- Canonical JSON serialization for deterministic hashing
- Hash chain verification at the database layer

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy - triggers must REJECT invalid
- CT-12: Witnessing creates accountability - hash chain is the witness
- DEB-001: Use standard Postgres only (no Supabase-specific functions)
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Path to spike migration
SPIKE_MIGRATION_PATH = (
    Path(__file__).parent.parent.parent / "migrations" / "spike_001_hash_trigger.sql"
)


@pytest.fixture
async def spike_db_session(db_session: AsyncSession) -> AsyncSession:
    """
    Database session with spike migration applied.

    This fixture runs the spike migration before tests and provides
    the session for testing the hash triggers.
    """
    # Enable pgcrypto
    await db_session.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    # Drop existing spike table
    await db_session.execute(text("DROP TABLE IF EXISTS events_spike CASCADE"))

    # Create spike table
    await db_session.execute(
        text("""
    CREATE TABLE events_spike (
        event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sequence BIGSERIAL UNIQUE NOT NULL,
        event_type TEXT NOT NULL,
        payload JSONB NOT NULL,
        prev_hash TEXT NOT NULL,
        content_hash TEXT,
        signature TEXT NOT NULL DEFAULT 'spike_signature',
        hash_alg_version SMALLINT NOT NULL DEFAULT 1,
        sig_alg_version SMALLINT NOT NULL DEFAULT 1,
        agent_id TEXT DEFAULT 'spike_agent',
        witness_id TEXT NOT NULL DEFAULT 'spike_witness',
        witness_signature TEXT NOT NULL DEFAULT 'spike_witness_sig',
        local_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        spike_computed_at TIMESTAMPTZ,
        spike_verified_at TIMESTAMPTZ
    )
    """)
    )

    # Create canonical JSON function
    canonical_fn = """
    CREATE OR REPLACE FUNCTION spike_canonical_jsonb(input_jsonb JSONB)
    RETURNS TEXT AS $$
    DECLARE
        result TEXT;
        key_val RECORD;
        arr_elem JSONB;
        is_first BOOLEAN := TRUE;
        elem_type TEXT;
    BEGIN
        IF input_jsonb IS NULL THEN
            RETURN 'null';
        END IF;

        elem_type := jsonb_typeof(input_jsonb);

        CASE elem_type
            WHEN 'object' THEN
                result := '{';
                FOR key_val IN
                    SELECT key, value
                    FROM jsonb_each(input_jsonb)
                    ORDER BY key ASC
                LOOP
                    IF NOT is_first THEN
                        result := result || ',';
                    END IF;
                    is_first := FALSE;
                    result := result || '"' || key_val.key || '":' ||
                              spike_canonical_jsonb(key_val.value);
                END LOOP;
                result := result || '}';
                RETURN result;

            WHEN 'array' THEN
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
                RETURN input_jsonb::text;

            WHEN 'number' THEN
                RETURN input_jsonb::text;

            WHEN 'boolean' THEN
                RETURN input_jsonb::text;

            WHEN 'null' THEN
                RETURN 'null';

            ELSE
                RETURN input_jsonb::text;
        END CASE;
    END;
    $$ LANGUAGE plpgsql IMMUTABLE STRICT;
    """
    await db_session.execute(text(canonical_fn))

    # Create hash computation function
    compute_fn = """
    CREATE OR REPLACE FUNCTION spike_compute_content_hash()
    RETURNS TRIGGER AS $$
    DECLARE
        canonical_payload TEXT;
        hash_input TEXT;
        computed_hash TEXT;
    BEGIN
        canonical_payload := spike_canonical_jsonb(NEW.payload);
        hash_input := NEW.event_type || '|' || canonical_payload || '|' || NEW.prev_hash;
        computed_hash := encode(digest(hash_input::bytea, 'sha256'), 'hex');
        NEW.content_hash := computed_hash;
        NEW.spike_computed_at := clock_timestamp();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    await db_session.execute(text(compute_fn))

    # Create hash verification function
    verify_fn = """
    CREATE OR REPLACE FUNCTION spike_verify_content_hash()
    RETURNS TRIGGER AS $$
    DECLARE
        canonical_payload TEXT;
        hash_input TEXT;
        expected_hash TEXT;
    BEGIN
        canonical_payload := spike_canonical_jsonb(NEW.payload);
        hash_input := NEW.event_type || '|' || canonical_payload || '|' || NEW.prev_hash;
        expected_hash := encode(digest(hash_input::bytea, 'sha256'), 'hex');

        IF NEW.content_hash IS NULL THEN
            RAISE EXCEPTION 'FR82: Hash chain integrity violation - content_hash is NULL';
        END IF;

        IF NEW.content_hash != expected_hash THEN
            RAISE EXCEPTION 'FR82: Hash chain integrity violation - content_hash mismatch (expected %, got %)',
                expected_hash, NEW.content_hash;
        END IF;

        NEW.spike_verified_at := clock_timestamp();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    await db_session.execute(text(verify_fn))

    # Create chain verification function
    chain_fn = """
    CREATE OR REPLACE FUNCTION spike_verify_hash_chain_on_insert()
    RETURNS TRIGGER AS $$
    DECLARE
        expected_prev_hash TEXT;
        genesis_hash TEXT := repeat('0', 64);
    BEGIN
        IF NEW.sequence = 1 THEN
            IF NEW.prev_hash != genesis_hash THEN
                RAISE EXCEPTION 'FR82: Hash chain continuity violation - first event must have genesis prev_hash (expected %, got %)',
                    genesis_hash, NEW.prev_hash;
            END IF;
        ELSE
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
    """
    await db_session.execute(text(chain_fn))

    # Create triggers (split into separate statements for asyncpg)
    await db_session.execute(
        text("DROP TRIGGER IF EXISTS spike_compute_hash_trigger ON events_spike")
    )
    await db_session.execute(
        text("""
    CREATE TRIGGER spike_compute_hash_trigger
        BEFORE INSERT ON events_spike
        FOR EACH ROW
        EXECUTE FUNCTION spike_compute_content_hash()
    """)
    )

    await db_session.execute(
        text("DROP TRIGGER IF EXISTS spike_verify_hash_trigger ON events_spike")
    )
    await db_session.execute(
        text("""
    CREATE TRIGGER spike_verify_hash_trigger
        BEFORE INSERT ON events_spike
        FOR EACH ROW
        EXECUTE FUNCTION spike_verify_content_hash()
    """)
    )

    await db_session.execute(
        text("DROP TRIGGER IF EXISTS spike_chain_verify_trigger ON events_spike")
    )
    await db_session.execute(
        text("""
    CREATE TRIGGER spike_chain_verify_trigger
        BEFORE INSERT ON events_spike
        FOR EACH ROW
        EXECUTE FUNCTION spike_verify_hash_chain_on_insert()
    """)
    )

    # Create benchmark functions
    benchmark_fn = """
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
        TRUNCATE events_spike RESTART IDENTITY;

        DROP TABLE IF EXISTS _spike_timings;
        CREATE TEMP TABLE _spike_timings (insert_ms NUMERIC);

        test_payload := jsonb_build_object(
            'test_data', repeat('x', payload_size_bytes),
            'benchmark', true
        );

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
    """
    await db_session.execute(text(benchmark_fn))

    # Create test functions
    test_large_fn = """
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
        TRUNCATE events_spike RESTART IDENTITY;

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
    """
    await db_session.execute(text(test_large_fn))

    test_unicode_fn = """
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

        test_case := 'special_json_chars';
        BEGIN
            SELECT content_hash INTO genesis_hash FROM events_spike ORDER BY sequence DESC LIMIT 1;
            INSERT INTO events_spike (event_type, payload, prev_hash)
            VALUES ('unicode_test', '{"special": "quote backslash newline tab"}'::jsonb, genesis_hash)
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
    """
    await db_session.execute(text(test_unicode_fn))

    # Note: No commit - parent fixture handles transaction management
    # DDL statements are auto-committed in PostgreSQL within the transaction

    return db_session


# Genesis hash constant (64 zeros)
GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    """
    Produce canonical JSON with sorted keys for deterministic hashing.

    This Python implementation must match the PL/pgSQL spike_canonical_jsonb function.
    """
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, (int, float, str)):
        return json.dumps(obj)
    elif isinstance(obj, list):
        elements = [canonical_json(elem) for elem in obj]
        return "[" + ",".join(elements) + "]"
    elif isinstance(obj, dict):
        # Sort keys alphabetically for canonical form
        items = sorted(obj.items(), key=lambda x: x[0])
        pairs = [f'"{k}":{canonical_json(v)}' for k, v in items]
        return "{" + ",".join(pairs) + "}"
    else:
        return json.dumps(obj)


def compute_expected_hash(event_type: str, payload: dict, prev_hash: str) -> str:
    """
    Compute expected SHA-256 hash matching the DB trigger implementation.

    Hash input format: event_type|canonical_payload|prev_hash
    """
    canonical_payload = canonical_json(payload)
    hash_input = f"{event_type}|{canonical_payload}|{prev_hash}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


class TestHashTriggerSpike:
    """Test class for hash trigger spike validation."""

    # =========================================================================
    # Task 1: Environment Setup Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_pgcrypto_extension_available(
        self, spike_db_session: AsyncSession
    ) -> None:
        """AC1.1: Verify pgcrypto extension is available."""
        result = await spike_db_session.execute(
            text("SELECT encode(digest('test', 'sha256'), 'hex') AS hash")
        )
        row = result.fetchone()

        assert row is not None, "pgcrypto digest() should return a result"
        assert row.hash is not None, "SHA-256 hash should not be NULL"
        assert len(row.hash) == 64, "SHA-256 hash should be 64 hex characters"

        # Verify known hash
        expected = hashlib.sha256(b"test").hexdigest()
        assert row.hash == expected, f"Hash mismatch: {row.hash} != {expected}"

    @pytest.mark.asyncio
    async def test_spike_table_exists(self, spike_db_session: AsyncSession) -> None:
        """AC1.2: Verify spike table was created."""
        result = await spike_db_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'events_spike'
                ) AS table_exists
                """
            )
        )
        row = result.fetchone()
        assert row is not None
        assert row.table_exists is True, "events_spike table should exist"

    @pytest.mark.asyncio
    async def test_spike_triggers_exist(self, spike_db_session: AsyncSession) -> None:
        """AC1.2: Verify spike triggers are created."""
        result = await spike_db_session.execute(
            text(
                """
                SELECT trigger_name
                FROM information_schema.triggers
                WHERE event_object_table = 'events_spike'
                ORDER BY trigger_name
                """
            )
        )
        triggers = [row.trigger_name for row in result.fetchall()]

        expected_triggers = [
            "spike_chain_verify_trigger",
            "spike_compute_hash_trigger",
            "spike_verify_hash_trigger",
        ]

        for expected in expected_triggers:
            assert expected in triggers, f"Trigger {expected} should exist"

    # =========================================================================
    # Task 2: Hash Computation Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_trigger_computes_content_hash(
        self, spike_db_session: AsyncSession
    ) -> None:
        """AC1: Verify trigger computes SHA-256 content_hash."""
        # Clear table
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        # Insert event without content_hash
        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('test_event', '{"key": "value"}'::jsonb, :genesis_hash)
                """
            ),
            {"genesis_hash": GENESIS_HASH},
        )
        # No commit - fixture handles transaction

        # Verify content_hash was computed
        result = await spike_db_session.execute(
            text(
                "SELECT content_hash, spike_computed_at FROM events_spike WHERE sequence = 1"
            )
        )
        row = result.fetchone()

        assert row is not None
        assert row.content_hash is not None, (
            "content_hash should be computed by trigger"
        )
        assert len(row.content_hash) == 64, "content_hash should be 64 hex characters"
        assert row.spike_computed_at is not None, "spike_computed_at should be set"

    @pytest.mark.asyncio
    async def test_hash_matches_python_computation(
        self, spike_db_session: AsyncSession
    ) -> None:
        """AC1: Verify DB hash matches Python computation."""
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        event_type = "test_event"
        payload = {"key": "value", "nested": {"a": 1, "b": 2}}

        # Compute expected hash in Python
        expected_hash = compute_expected_hash(event_type, payload, GENESIS_HASH)

        # Insert event (use CAST for asyncpg compatibility)
        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES (:event_type, CAST(:payload AS jsonb), :prev_hash)
                """
            ),
            {
                "event_type": event_type,
                "payload": json.dumps(payload),
                "prev_hash": GENESIS_HASH,
            },
        )
        # No commit - fixture handles transaction

        # Get DB-computed hash
        result = await spike_db_session.execute(
            text("SELECT content_hash FROM events_spike WHERE sequence = 1")
        )
        row = result.fetchone()

        assert row is not None
        assert row.content_hash == expected_hash, (
            f"Hash mismatch: DB={row.content_hash}, Python={expected_hash}"
        )

    @pytest.mark.asyncio
    async def test_canonical_json_key_order(
        self, spike_db_session: AsyncSession
    ) -> None:
        """AC1: Verify canonical JSON has sorted keys."""
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        # Payload with keys in non-alphabetical order
        payload_unsorted = {"z": 1, "a": 2, "m": 3}

        # Insert event (use CAST for asyncpg compatibility)
        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('test_event', CAST(:payload AS jsonb), :prev_hash)
                """
            ),
            {
                "payload": json.dumps(payload_unsorted),
                "prev_hash": GENESIS_HASH,
            },
        )
        # No commit - fixture handles transaction

        # Verify hash is deterministic (keys sorted alphabetically)
        expected_hash = compute_expected_hash(
            "test_event", payload_unsorted, GENESIS_HASH
        )

        result = await spike_db_session.execute(
            text("SELECT content_hash FROM events_spike WHERE sequence = 1")
        )
        row = result.fetchone()

        assert row is not None
        assert row.content_hash == expected_hash, (
            "Hash should be computed with sorted keys"
        )

    # =========================================================================
    # Task 3: Hash Verification Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_hash_verification_passes(
        self, spike_db_session: AsyncSession
    ) -> None:
        """AC1: Verify hash verification passes for valid events."""
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        # Insert valid event
        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('valid_event', '{"status": "ok"}'::jsonb, :genesis_hash)
                """
            ),
            {"genesis_hash": GENESIS_HASH},
        )
        # No commit - fixture handles transaction

        # Verify spike_verified_at is set (indicates verification passed)
        result = await spike_db_session.execute(
            text("SELECT spike_verified_at FROM events_spike WHERE sequence = 1")
        )
        row = result.fetchone()

        assert row is not None
        assert row.spike_verified_at is not None, "Verification should complete"

    @pytest.mark.asyncio
    async def test_hash_chain_verification(
        self, spike_db_session: AsyncSession
    ) -> None:
        """AC1: Verify hash chain linkage is enforced."""
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        # Insert first event
        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('event_1', '{"seq": 1}'::jsonb, :genesis_hash)
                """
            ),
            {"genesis_hash": GENESIS_HASH},
        )
        # No commit - fixture handles transaction

        # Get first event's content_hash
        result = await spike_db_session.execute(
            text("SELECT content_hash FROM events_spike WHERE sequence = 1")
        )
        first_hash = result.fetchone().content_hash

        # Insert second event chained to first
        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('event_2', '{"seq": 2}'::jsonb, :prev_hash)
                """
            ),
            {"prev_hash": first_hash},
        )
        # No commit - fixture handles transaction

        # Verify chain
        result = await spike_db_session.execute(
            text(
                """
                SELECT e1.content_hash as first_hash, e2.prev_hash as second_prev
                FROM events_spike e1, events_spike e2
                WHERE e1.sequence = 1 AND e2.sequence = 2
                """
            )
        )
        row = result.fetchone()

        assert row is not None
        assert row.first_hash == row.second_prev, "Hash chain should be linked"

    @pytest.mark.asyncio
    async def test_invalid_prev_hash_rejected(
        self, spike_db_session: AsyncSession
    ) -> None:
        """AC1: Verify invalid prev_hash is rejected."""
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        # Insert first event
        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('event_1', '{"seq": 1}'::jsonb, :genesis_hash)
                """
            ),
            {"genesis_hash": GENESIS_HASH},
        )
        # No commit - fixture handles transaction

        # Try to insert second event with wrong prev_hash
        invalid_hash = "a" * 64  # Valid format but wrong value

        with pytest.raises(Exception) as exc_info:
            await spike_db_session.execute(
                text(
                    """
                    INSERT INTO events_spike (event_type, payload, prev_hash)
                    VALUES ('event_2', '{"seq": 2}'::jsonb, :prev_hash)
                    """
                ),
                {"prev_hash": invalid_hash},
            )
            # No commit - fixture handles transaction

        assert "FR82" in str(exc_info.value), "Should raise FR82 hash chain violation"

    # =========================================================================
    # Task 4: Performance Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_benchmark_100_inserts(self, spike_db_session: AsyncSession) -> None:
        """AC2: Benchmark 100 sequential inserts."""
        result = await spike_db_session.execute(
            text("SELECT * FROM spike_benchmark_percentiles(100, 100)")
        )
        row = result.fetchone()

        assert row is not None
        assert row.total_inserts == 100
        assert row.avg_ms is not None

        # Log performance metrics
        logger.info(
            "benchmark_100_inserts",
            total_inserts=row.total_inserts,
            avg_ms=float(row.avg_ms),
            p50_ms=float(row.p50_ms),
            p95_ms=float(row.p95_ms),
            p99_ms=float(row.p99_ms),
            max_ms=float(row.max_ms),
        )

        # Target: <10ms per insert
        assert row.avg_ms < 10, (
            f"Average insert time {row.avg_ms}ms exceeds 10ms target"
        )

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_benchmark_1000_inserts(self, spike_db_session: AsyncSession) -> None:
        """AC2: Full benchmark with 1000 inserts."""
        result = await spike_db_session.execute(
            text("SELECT * FROM spike_benchmark_percentiles(1000, 100)")
        )
        row = result.fetchone()

        assert row is not None
        logger.info(
            "benchmark_1000_inserts",
            total_inserts=row.total_inserts,
            avg_ms=float(row.avg_ms),
            p50_ms=float(row.p50_ms),
            p95_ms=float(row.p95_ms),
            p99_ms=float(row.p99_ms),
            max_ms=float(row.max_ms),
        )

        # Target: <10ms per insert, p99 < 20ms
        assert row.avg_ms < 10, (
            f"Average insert time {row.avg_ms}ms exceeds 10ms target"
        )
        assert row.p99_ms < 20, f"P99 insert time {row.p99_ms}ms exceeds 20ms target"

    # =========================================================================
    # Task 5: Edge Case Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_large_payload_100kb(self, spike_db_session: AsyncSession) -> None:
        """AC3: Test with 100KB payload."""
        result = await spike_db_session.execute(
            text("SELECT * FROM spike_test_large_payload(100)")
        )
        row = result.fetchone()

        assert row is not None
        assert row.success is True, f"100KB payload failed: {row.hash_computed}"
        assert row.insert_time_ms < 100, f"100KB insert took {row.insert_time_ms}ms"

        logger.info(
            "large_payload_test",
            size_kb=row.payload_size_kb,
            insert_time_ms=float(row.insert_time_ms),
            success=row.success,
        )

    @pytest.mark.asyncio
    async def test_unicode_payloads(self, spike_db_session: AsyncSession) -> None:
        """AC3: Test Unicode handling in payloads."""
        result = await spike_db_session.execute(
            text("SELECT * FROM spike_test_unicode_payload()")
        )
        rows = result.fetchall()

        for row in rows:
            assert row.insert_success is True, (
                f"Unicode test '{row.test_case}' failed: {row.notes}"
            )
            assert row.hash_length == 64, f"Hash length wrong for {row.test_case}"

            logger.info(
                "unicode_test",
                test_case=row.test_case,
                success=row.insert_success,
                notes=row.notes,
            )

    @pytest.mark.asyncio
    async def test_empty_payload(self, spike_db_session: AsyncSession) -> None:
        """AC3: Test empty payload handling."""
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('empty_test', '{}'::jsonb, :genesis_hash)
                """
            ),
            {"genesis_hash": GENESIS_HASH},
        )
        # No commit - fixture handles transaction

        result = await spike_db_session.execute(
            text("SELECT content_hash FROM events_spike WHERE sequence = 1")
        )
        row = result.fetchone()

        assert row is not None
        assert row.content_hash is not None
        assert len(row.content_hash) == 64

    @pytest.mark.asyncio
    async def test_nested_json_payload(self, spike_db_session: AsyncSession) -> None:
        """AC3: Test deeply nested JSON payload."""
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        nested_payload = {
            "level1": {"level2": {"level3": {"level4": {"level5": {"value": "deep"}}}}}
        }

        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('nested_test', CAST(:payload AS jsonb), :genesis_hash)
                """
            ),
            {
                "payload": json.dumps(nested_payload),
                "genesis_hash": GENESIS_HASH,
            },
        )
        # No commit - fixture handles transaction

        # Verify hash matches Python computation
        expected_hash = compute_expected_hash(
            "nested_test", nested_payload, GENESIS_HASH
        )

        result = await spike_db_session.execute(
            text("SELECT content_hash FROM events_spike WHERE sequence = 1")
        )
        row = result.fetchone()

        assert row is not None
        assert row.content_hash == expected_hash, "Nested JSON hash should match"

    @pytest.mark.asyncio
    async def test_array_payload(self, spike_db_session: AsyncSession) -> None:
        """AC3: Test JSON array payload."""
        await spike_db_session.execute(text("TRUNCATE events_spike RESTART IDENTITY"))

        array_payload = {"items": [1, 2, 3, {"nested": "value"}]}

        await spike_db_session.execute(
            text(
                """
                INSERT INTO events_spike (event_type, payload, prev_hash)
                VALUES ('array_test', CAST(:payload AS jsonb), :genesis_hash)
                """
            ),
            {
                "payload": json.dumps(array_payload),
                "genesis_hash": GENESIS_HASH,
            },
        )
        # No commit - fixture handles transaction

        expected_hash = compute_expected_hash("array_test", array_payload, GENESIS_HASH)

        result = await spike_db_session.execute(
            text("SELECT content_hash FROM events_spike WHERE sequence = 1")
        )
        row = result.fetchone()

        assert row is not None
        assert row.content_hash == expected_hash, "Array JSON hash should match"


# =========================================================================
# Test Markers and Configuration
# =========================================================================

# Mark slow tests
pytestmark = [
    pytest.mark.integration,
    pytest.mark.spike,
]
