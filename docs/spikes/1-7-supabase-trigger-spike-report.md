# Spike Report: 1-7 Supabase DB-Level Hash Trigger

**Story:** 1.7 - Supabase Trigger Spike (SR-3)
**Date:** 2026-01-06
**Status:** COMPLETE
**Decision:** GO

## Executive Summary

This spike validates that DB-level hash enforcement in Supabase/PostgreSQL is viable and performant. The implementation uses standard PostgreSQL features (pgcrypto, PL/pgSQL triggers) with no Supabase-specific dependencies, meeting the DEB-001 portability constraint.

**Key Finding:** Hash computation and verification triggers add **<1ms average overhead** per insert, well below the 10ms target. The approach is recommended for production.

## Performance Results

### Benchmark Summary

| Metric | 100 Inserts | 1000 Inserts | Target |
|--------|-------------|--------------|--------|
| Average | 0.43ms | 0.33ms | <10ms |
| P50 | 0.36ms | 0.30ms | - |
| P95 | 0.53ms | 0.52ms | - |
| P99 | 1.48ms | 0.63ms | <20ms |
| Max | 7.52ms | 6.61ms | - |

### Large Payload Performance

| Payload Size | Insert Time | Status |
|--------------|-------------|--------|
| 100KB | 17.6ms | PASS |

**Note:** 100KB payloads take longer due to JSON serialization but are still acceptable. Production events are expected to be <10KB.

## Implementation Details

### Trigger Architecture

Three BEFORE INSERT triggers on `events_spike` table:

1. **spike_compute_hash_trigger** → `spike_compute_content_hash()`
   - Computes SHA-256 hash using pgcrypto `digest()`
   - Hash input: `event_type|canonical_json(payload)|prev_hash`
   - Sets `content_hash` on NEW record

2. **spike_verify_hash_trigger** → `spike_verify_content_hash()`
   - Recomputes hash from event data
   - Verifies computed hash matches `content_hash`
   - Raises exception on mismatch (FR82 violation)

3. **spike_chain_verify_trigger** → `spike_verify_hash_chain_on_insert()`
   - Validates `prev_hash` links to previous event's `content_hash`
   - First event must have genesis hash (64 zeros)
   - Raises exception on chain break (FR82 violation)

### Canonical JSON Serialization

A custom PL/pgSQL function `spike_canonical_jsonb()` provides deterministic JSON serialization:

- Recursively processes JSONB
- Sorts object keys alphabetically
- Preserves array order
- Handles all JSON types (object, array, string, number, boolean, null)

**Validation:** Python and PostgreSQL implementations produce identical hashes for:
- Simple key-value pairs
- Nested objects (5 levels deep)
- Arrays with mixed types
- Unicode content (CJK, emoji, special chars)
- Empty objects/arrays

### pgcrypto Usage

```sql
-- Enable extension (pre-installed in Supabase)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- SHA-256 hash computation
SELECT encode(digest(hash_input::bytea, 'sha256'), 'hex');
```

## Edge Cases Tested

| Test Case | Result | Notes |
|-----------|--------|-------|
| Empty payload `{}` | PASS | Hash computed correctly |
| Deeply nested JSON (5 levels) | PASS | Canonical serialization works |
| Array payloads | PASS | Array order preserved |
| Unicode (Basic) | PASS | UTF-8 handled correctly |
| Unicode (CJK characters) | PASS | Multi-byte chars ok |
| Unicode (Emoji) | PASS | Emoji encoded correctly |
| Special JSON chars (`\"`, `\\`, `\n`, `\t`) | PASS | Escaping handled |
| 100KB payload | PASS | 17.6ms latency |
| Invalid prev_hash | REJECT | FR82 exception raised |
| Chain break attempt | REJECT | FR82 exception raised |

## Supabase-Specific Findings

### Confirmed Compatible

1. **pgcrypto Extension:** Pre-installed in Supabase, no setup required
2. **BEFORE INSERT Triggers:** Execute within transaction, atomic with insert
3. **PL/pgSQL Functions:** Full support, no limitations discovered
4. **Transaction Isolation:** Triggers respect transaction boundaries

### Considerations for Production

1. **Connection Pooling (PgBouncer):**
   - Supabase uses transaction-mode pooling
   - Triggers execute within transaction context
   - No issues expected (validated in test environment)

2. **Row Level Security (RLS):**
   - RLS policies evaluated AFTER triggers
   - Trigger functions should use `SECURITY DEFINER`
   - Hash computation independent of RLS

3. **Realtime Publications:**
   - Triggers fire BEFORE publication capture
   - No impact on trigger behavior

### No Blocking Issues Found

The spike discovered no Supabase-specific limitations that would prevent DB-level hash enforcement.

## Recommendation

### GO Decision

**Proceed with DB-level hash enforcement for production.**

Rationale:
1. Performance exceeds requirements (0.3-0.4ms vs 10ms target)
2. Canonical JSON serialization validated across edge cases
3. Hash chain verification works as expected
4. No Supabase-specific blockers discovered
5. Implementation uses standard Postgres only (DEB-001 compliant)

### Production Implementation Notes

1. **Migrate spike functions to production schema:**
   - Remove `spike_` prefix from function/trigger names
   - Apply to main `events` table instead of `events_spike`

2. **Security considerations:**
   - Use `SECURITY DEFINER` for hash computation function
   - Limit function ownership to dedicated service role

3. **Monitoring recommendations:**
   - Track trigger execution time in Postgres logs
   - Alert if P99 exceeds 5ms

4. **Rollback plan:**
   - If issues discovered, triggers can be disabled without data loss
   - Hash verification can be moved to application layer as fallback

## Files Created

```
migrations/spike_001_hash_trigger.sql      # Spike migration with all functions
tests/integration/test_hash_trigger_spike.py  # 16 integration tests
docs/spikes/1-7-supabase-trigger-spike-report.md  # This report
```

## Test Results Summary

```
tests/integration/test_hash_trigger_spike.py
======================== 16 passed in 6.12s ========================

Tests:
- test_pgcrypto_extension_available
- test_spike_table_exists
- test_spike_triggers_exist
- test_trigger_computes_content_hash
- test_hash_matches_python_computation
- test_canonical_json_key_order
- test_hash_verification_passes
- test_hash_chain_verification
- test_invalid_prev_hash_rejected
- test_benchmark_100_inserts
- test_benchmark_1000_inserts
- test_large_payload_100kb
- test_unicode_payloads
- test_empty_payload
- test_nested_json_payload
- test_array_payload
```

## References

- [ADR-001: Event Store Implementation](/_bmad-output/planning-artifacts/architecture.md)
- [Story 1.7: Supabase Trigger Spike](/_bmad-output/implementation-artifacts/stories/1-7-supabase-trigger-spike.md)
- [PostgreSQL pgcrypto Documentation](https://www.postgresql.org/docs/current/pgcrypto.html)
- [DEB-001: Postgres Portability Constraint](/_bmad-output/planning-artifacts/architecture.md)
