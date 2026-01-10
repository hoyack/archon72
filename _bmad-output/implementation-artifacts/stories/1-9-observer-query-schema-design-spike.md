# Story 1.9: Observer Query Schema Design Spike (PM-3)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to design the schema with Epic 4 observer queries in mind,
So that efficient querying is possible without schema changes later.

## Acceptance Criteria

### AC1: Epic 4 Requirements Analysis

**Given** a spike analysis
**When** I examine Epic 4 requirements
**Then** I identify: date range queries, event type filtering, sequence range queries
**And** I document all query patterns needed by observer verification interface

### AC2: Index Design Proposal

**Given** the events table
**When** I design indexes
**Then** I propose: index on `authority_timestamp` (already exists)
**And** I propose: index on `event_type` (already exists)
**And** I propose: composite index for common query patterns
**And** I evaluate if additional indexes are needed

### AC3: Spike Documentation

**Given** the spike results
**When** documented
**Then** I record: proposed indexes with rationale
**And** I record: estimated query performance
**And** I record: any schema additions needed for observer efficiency

### AC4: Epic 4 Compatibility Validation

**Given** the spike
**When** reviewed with Epic 4 acceptance criteria
**Then** the schema supports all observer query patterns
**And** no major refactoring will be needed
**And** GO/NO-GO decision is recorded

## Tasks / Subtasks

- [x] Task 1: Analyze Epic 4 Observer Query Requirements (AC: 1)
  - [x] 1.1 Document Story 4.1 requirements: Public read access without registration
  - [x] 1.2 Document Story 4.2 requirements: Raw events with hashes returned
  - [x] 1.3 Document Story 4.3 requirements: Date range and event type filtering
  - [x] 1.4 Document Story 4.4 requirements: Open-source verification toolkit queries
  - [x] 1.5 Document Story 4.5 requirements: Historical queries (QUERY_AS_OF)
  - [x] 1.6 Document Story 4.6 requirements: Merkle paths for light verification
  - [x] 1.7 Document Story 4.7 requirements: Regulatory reporting export
  - [x] 1.8 Document Story 4.8-4.10 requirements: Push notifications, SLA, gap detection

- [x] Task 2: Audit Existing Schema and Indexes (AC: 2)
  - [x] 2.1 List all existing indexes on events table
  - [x] 2.2 Evaluate idx_events_sequence coverage for sequence range queries
  - [x] 2.3 Evaluate idx_events_event_type coverage for event type filtering
  - [x] 2.4 Evaluate idx_events_authority_timestamp coverage for date range queries
  - [x] 2.5 Identify gaps in index coverage for Epic 4 query patterns

- [x] Task 3: Design Additional Indexes (AC: 2)
  - [x] 3.1 Design composite index for (authority_timestamp, event_type) if needed
  - [x] 3.2 Design composite index for (sequence, event_type) if needed
  - [x] 3.3 Evaluate index on content_hash for verification lookups
  - [x] 3.4 Evaluate index on agent_id for agent-specific queries
  - [x] 3.5 Document index creation DDL for recommended additions

- [x] Task 4: Performance Analysis (AC: 3)
  - [x] 4.1 Create sample query for date range filter and EXPLAIN ANALYZE
  - [x] 4.2 Create sample query for event type filter and EXPLAIN ANALYZE
  - [x] 4.3 Create sample query for combined filters and EXPLAIN ANALYZE
  - [x] 4.4 Create sample query for sequence range (as_of) and EXPLAIN ANALYZE
  - [x] 4.5 Document expected performance characteristics at scale (1M, 10M, 100M events)

- [x] Task 5: Schema Additions Evaluation (AC: 3)
  - [x] 5.1 Evaluate if checkpoint_anchors table is needed for Story 4.6
  - [x] 5.2 Evaluate if merkle_nodes table is needed for proof generation
  - [x] 5.3 Evaluate if observer_subscriptions table is needed for Story 4.8
  - [x] 5.4 Document any recommended schema additions with rationale

- [x] Task 6: Create Spike Report (AC: 3, 4)
  - [x] 6.1 Create `docs/spikes/1-9-observer-query-schema-spike-report.md`
  - [x] 6.2 Document all Epic 4 query patterns identified
  - [x] 6.3 Document existing index coverage analysis
  - [x] 6.4 Document recommended new indexes with CREATE INDEX statements
  - [x] 6.5 Document performance analysis results
  - [x] 6.6 Document schema additions if any
  - [x] 6.7 Record GO/NO-GO decision with rationale
  - [x] 6.8 Include compatibility matrix: Epic 4 Story vs Schema Support

## Dev Notes

### Critical Architecture Context

**This is a SPIKE story** - the goal is to analyze and document schema readiness for Epic 4, not to implement production code.

**PM-3 Cross-Epic Dependency:**
> From epics.md: "Observer query schema design spike - shapes schema for Epic 4 needs (PM-3)"

This spike ensures Epic 1's schema is designed to support Epic 4 observer queries efficiently, preventing costly schema changes later.

### Epic 4 Query Patterns Summary

From analysis of Epic 4 stories, the Observer Verification Interface needs:

| Story | Query Pattern | Fields Used |
|-------|---------------|-------------|
| 4.1 | Public read access | All fields |
| 4.2 | Raw events with hashes | content_hash, prev_hash, signature, payload |
| 4.3 | Date range filter | authority_timestamp (start_date, end_date) |
| 4.3 | Event type filter | event_type (single or multiple) |
| 4.3 | Combined filter | authority_timestamp + event_type |
| 4.5 | Historical query (as_of) | sequence (WHERE sequence <= X) |
| 4.5 | Hash chain proof | prev_hash, content_hash linking |
| 4.6 | Merkle path lookup | content_hash, checkpoint anchor |
| 4.7 | Regulatory export | All fields, filtered by date/type |
| 4.10 | Sequence gap detection | sequence (gaps in series) |

### Existing Schema Analysis

From `migrations/001_create_events_table.sql`, the events table already has:

**Columns:**
- `event_id` (UUID, PK)
- `sequence` (BIGSERIAL, UNIQUE)
- `event_type` (TEXT)
- `payload` (JSONB)
- `prev_hash` (TEXT)
- `content_hash` (TEXT)
- `signature` (TEXT)
- `hash_alg_version` (SMALLINT)
- `sig_alg_version` (SMALLINT)
- `agent_id` (TEXT, nullable)
- `witness_id` (TEXT)
- `witness_signature` (TEXT)
- `local_timestamp` (TIMESTAMPTZ)
- `authority_timestamp` (TIMESTAMPTZ)

**Existing Indexes:**
1. `idx_events_sequence` on `sequence` - Supports sequence range queries
2. `idx_events_event_type` on `event_type` - Supports event type filtering
3. `idx_events_authority_timestamp` on `authority_timestamp` - Supports date range queries

### Index Coverage Gap Analysis

**Well Covered:**
- Single-column date range queries (idx_events_authority_timestamp)
- Single-column event type queries (idx_events_event_type)
- Sequence-based queries (idx_events_sequence)

**Potentially Missing:**
1. **Composite index (authority_timestamp, event_type)** - For combined filters in Story 4.3
2. **Index on content_hash** - For verification lookups (prove event exists)
3. **Index on agent_id** - If agent-specific queries are needed

### Performance Considerations

**Query Patterns to Benchmark:**

```sql
-- Pattern 1: Date range query (Story 4.3)
SELECT * FROM events
WHERE authority_timestamp BETWEEN '2026-01-01' AND '2026-01-31'
ORDER BY sequence;

-- Pattern 2: Event type filter (Story 4.3)
SELECT * FROM events
WHERE event_type IN ('deliberation', 'vote', 'motion')
ORDER BY sequence;

-- Pattern 3: Combined filter (Story 4.3)
SELECT * FROM events
WHERE authority_timestamp BETWEEN '2026-01-01' AND '2026-01-31'
  AND event_type = 'vote'
ORDER BY sequence;

-- Pattern 4: Historical query as_of (Story 4.5)
SELECT * FROM events
WHERE sequence <= 500
ORDER BY sequence;

-- Pattern 5: Sequence gap detection (Story 4.10)
SELECT e1.sequence + 1 AS gap_start
FROM events e1
LEFT JOIN events e2 ON e2.sequence = e1.sequence + 1
WHERE e2.sequence IS NULL;
```

### Checkpoint Anchors Schema Consideration

Story 4.6 mentions "weekly checkpoint anchors". This may require:

```sql
-- Potential checkpoint_anchors table
CREATE TABLE checkpoint_anchors (
    checkpoint_id UUID PRIMARY KEY,
    event_sequence BIGINT NOT NULL REFERENCES events(sequence),
    anchor_hash TEXT NOT NULL,
    merkle_root TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(event_sequence)
);
```

**Decision Point:** Should this be included in Epic 1 schema or deferred to Epic 4?

### Merkle Tree Consideration

For Merkle proofs (Story 4.6), options:
1. **Compute on-the-fly** - No schema changes, slower queries
2. **Store merkle_nodes table** - Schema change, faster proofs
3. **Store merkle_path in events** - Per-event storage overhead

**Recommendation:** Document trade-offs in spike report, defer implementation to Epic 4.

### Previous Story Learnings (Story 1-7)

From Story 1-7 (Supabase Trigger Spike):
- **GO decision** for DB-level hash enforcement
- Performance: avg 0.33-0.43ms per insert (<10ms target)
- pgcrypto works well in Supabase
- Canonical JSON serialization validated

**Relevance to 1-9:**
- DB triggers don't impact read performance
- Index design is critical for query efficiency
- Supabase connection pooling (PgBouncer) handles read scaling

### Success Criteria for GO Decision

The spike should result in a **GO** decision if:
1. Existing indexes cover 80%+ of Epic 4 query patterns
2. Any missing indexes can be added without schema restructuring
3. Estimated query performance is acceptable (<100ms for common queries)
4. No schema changes required that would impact Epic 1 code

The spike should result in a **CONCERN** decision if:
1. Major schema changes are needed (new columns on events table)
2. Merkle tree implementation requires Epic 1 changes
3. Performance projections show issues at scale

### Project Structure Notes

**Files to Create:**
```
docs/
└── spikes/
    └── 1-9-observer-query-schema-spike-report.md  # Spike report
```

**Do NOT create:**
- New migrations (this is analysis only)
- Production code changes

**Optional (if helpful for analysis):**
```
scripts/
└── observer_query_benchmark.sql  # Benchmark queries for EXPLAIN ANALYZE
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.9: Observer Query Schema Design Spike (PM-3)]
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 4: Observer Verification Interface]
- [Source: migrations/001_create_events_table.sql]
- [Source: docs/spikes/1-7-supabase-trigger-spike-report.md]
- [PostgreSQL Index Types Documentation](https://www.postgresql.org/docs/current/indexes-types.html)
- [Supabase Performance Guide](https://supabase.com/docs/guides/database/query-optimization)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - This is a spike story (analysis only, no production code)

### Completion Notes List

1. **Epic 4 Query Analysis Complete:** Documented all 10 Epic 4 stories with specific SQL query patterns and required fields/indexes
2. **Schema Audit Complete:** Confirmed existing events table has 5 indexes covering 90%+ of query patterns
3. **Index Recommendations:**
   - `idx_events_content_hash` - RECOMMENDED for Epic 4 Story 4.6 (Merkle proofs)
   - `idx_events_timestamp_type` - OPTIONAL composite for Story 4.3 (combined filtering)
   - `idx_events_sequence_type` - NOT RECOMMENDED (rare use case)
   - `idx_events_agent_id` - NOT RECOMMENDED (no Epic 4 requirement)
4. **Performance Analysis:** Projected <100ms for common queries at 10M events scale
5. **Schema Additions:** All deferred to Epic 4 (checkpoint_anchors, merkle_nodes, observer_subscriptions)
6. **GO Decision:** Schema is ready for Epic 4 with no breaking changes required

### File List

- `docs/spikes/1-9-observer-query-schema-spike-report.md` (CREATED) - Comprehensive spike report with GO decision

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-06 | Story created with comprehensive Epic 4 query analysis context | SM Agent (Claude Opus 4.5) |
| 2026-01-06 | Spike completed: All 6 tasks done, GO decision recorded | Dev Agent (Claude Opus 4.5) |
