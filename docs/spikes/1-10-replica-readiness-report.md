# Spike Report: 1-10 Replica Configuration Readiness

**Story:** 1.10 - Replica Configuration Preparation (FR8, FR94-FR95)
**Date:** 2026-01-06
**Status:** COMPLETE
**Decision:** READY FOR REPLICATION

## Executive Summary

This spike assesses whether the current events table schema can support 3 geographic replicas via PostgreSQL logical replication. The analysis confirms that **the schema is fully compatible with replication** with no blocking features identified.

**Key Finding:** The events table schema is well-designed for replication. UUID primary key and BIGSERIAL sequence are ideal for replica synchronization. No schema modifications required.

---

## 1. Schema Replication Compatibility Assessment (AC1)

### Events Table Schema Analysis

From `migrations/001_create_events_table.sql`:

| Feature | Value | Replication Impact | Status |
|---------|-------|-------------------|--------|
| **Primary Key** | `event_id UUID` | UUID is globally unique, no conflicts across replicas | COMPATIBLE |
| **Sequence** | `sequence BIGSERIAL UNIQUE` | Standard PostgreSQL sequence, replicates correctly | COMPATIBLE |
| **Table Type** | Standard table | Not UNLOGGED, not TEMP | COMPATIBLE |
| **Indexes** | B-tree (3 indexes) | Standard indexes replicate automatically | COMPATIBLE |
| **Triggers** | BEFORE UPDATE/DELETE | Replicate via logical replication | COMPATIBLE |
| **REVOKE TRUNCATE** | Applied | Permission-based, works with replication | COMPATIBLE |

### Detailed Feature Analysis

#### 1.1 UUID Primary Key (event_id)

**Assessment:** REPLICATION-SAFE

UUIDs are ideal for distributed systems because:
- Globally unique - no conflicts when generated on different replicas
- No coordination required between nodes for ID generation
- PostgreSQL `gen_random_uuid()` works independently on each node

```sql
event_id UUID PRIMARY KEY  -- Ideal for replication
```

#### 1.2 BIGSERIAL Sequence (sequence)

**Assessment:** COMPATIBLE WITH SINGLE-WRITER

The sequence column uses BIGSERIAL which:
- Is managed by PostgreSQL's sequence mechanism
- Replicates correctly via logical replication
- Works perfectly with our single-writer architecture (ADR-1)

```sql
sequence BIGSERIAL UNIQUE NOT NULL  -- Single source of truth from Writer
```

**Note:** Since we use single canonical Writer (ADR-1), sequence generation is centralized on the primary. Replicas receive already-sequenced events.

#### 1.3 No Replication-Blocking Features

Verified NONE of these blocking features exist:

| Blocking Feature | Present? | Notes |
|-----------------|----------|-------|
| UNLOGGED table | NO | Table is fully logged |
| Temporary table | NO | Permanent table |
| GENERATED ALWAYS columns | NO | Only DEFAULT values |
| Foreign tables | NO | Local table only |
| Partitioned without replica identity | NO | Not partitioned |
| System columns in primary key | NO | Uses UUID |

#### 1.4 Trigger Compatibility

The append-only enforcement triggers are compatible:

```sql
-- These triggers replicate correctly
TRIGGER prevent_event_update BEFORE UPDATE
TRIGGER prevent_event_delete BEFORE DELETE
```

Logical replication replicates:
- INSERT operations (primary use case for append-only)
- Triggers fire on primary, replicas receive final row state

#### 1.5 Index Compatibility

All indexes use standard B-tree and replicate automatically:

```sql
idx_events_sequence ON events (sequence)           -- B-tree, COMPATIBLE
idx_events_event_type ON events (event_type)       -- B-tree, COMPATIBLE
idx_events_authority_timestamp ON events (authority_timestamp)  -- B-tree, COMPATIBLE
```

---

## 2. Read/Write Path Separation (AC2)

### Single-Writer Architecture (ADR-1)

From `_bmad-output/planning-artifacts/architecture.md`:

> "Single canonical Writer (constitutionally required). Read-only replicas via managed Postgres replication (Supabase/underlying PG). Failover is ceremony-based: watchdog detection + human approval + witnessed promotion."

### Write Path (Primary Only)

```
┌─────────────────┐      ┌──────────────────┐
│ EventWriter     │─────▶│ PostgreSQL       │
│ Service         │      │ Primary (Writer) │
└─────────────────┘      └──────────────────┘
                                  │
                     Logical Replication
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ Replica 1        │   │ Replica 2        │   │ Replica 3        │
│ (Geographic A)   │   │ (Geographic B)   │   │ (Geographic C)   │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

**Key Points:**
- All mutations (INSERT) go to primary Writer only
- Single Writer is constitutionally required (CT-12 witnessing)
- No multi-master writes - prevents split-brain

### Read Path (Replicas Acceptable)

```
┌─────────────────┐      ┌──────────────────┐
│ Observer API    │─────▶│ Any Replica      │
│ (Epic 4)        │      │ (Read-only)      │
└─────────────────┘      └──────────────────┘
```

**Eventual Consistency Acceptable For:**
- Observer verification queries (Epic 4)
- Historical queries (QUERY_AS_OF)
- Regulatory exports
- Public audit access

**NOT Acceptable For:**
- Write operations (always primary)
- Real-time halt state (must check primary or Redis)
- Signature verification during write (primary only)

---

## 3. Replication Topology Recommendation

### Supabase Read Replicas

Supabase provides built-in read replica support:
- Managed PostgreSQL logical replication
- Connection pooling handles routing
- Automatic failover detection (but manual promotion per our constitution)

### Geographic Distribution

Recommended for FR8 (3 replicas):

| Replica | Region | Purpose |
|---------|--------|---------|
| Primary | US East | Write operations, authoritative |
| Replica 1 | US West | Read scaling, west coast users |
| Replica 2 | EU Central | Read scaling, EU compliance |
| Replica 3 | APAC | Read scaling, disaster recovery |

### Replication Lag Considerations

- Expected lag: <100ms under normal conditions
- Observer API can tolerate up to 1 second lag
- Halt propagation uses Redis (immediate), not replica polling

---

## 4. Event Replicator Interface Design (AC3)

### Port Interface

The `EventReplicatorPort` will provide:

```python
class EventReplicatorPort(ABC):
    @abstractmethod
    async def propagate_event(self, event_id: UUID) -> ReplicationReceipt:
        """Notify replicas of new event (optional optimization)."""
        ...

    @abstractmethod
    async def verify_replicas(self) -> VerificationResult:
        """Verify all replicas are consistent with primary."""
        ...
```

### Receipt and Result Types

```python
@dataclass(frozen=True)
class ReplicationReceipt:
    event_id: UUID
    replica_ids: list[str]
    status: ReplicationStatus  # PENDING | CONFIRMED | FAILED
    timestamp: datetime

@dataclass(frozen=True)
class VerificationResult:
    head_hash_match: bool
    signature_valid: bool
    schema_version_match: bool
    errors: list[str]
```

### Stub Behavior (Epic 1)

For Epic 1, the stub will:
- Return success for `propagate_event()` (no replicas configured)
- Return positive verification for `verify_replicas()` (single-node mode)
- Log all operations for traceability

---

## 5. Compatibility Matrix

| PostgreSQL Feature | Supabase Support | Schema Compatible | Notes |
|--------------------|------------------|-------------------|-------|
| Logical Replication | Yes | Yes | Built-in support |
| Read Replicas | Yes (Pro+) | Yes | Connection pooling included |
| UUID Generation | Yes | Yes | `gen_random_uuid()` |
| BIGSERIAL | Yes | Yes | Standard sequence |
| B-tree Indexes | Yes | Yes | Replicate automatically |
| Triggers | Yes | Yes | Fire on primary, state replicates |
| REVOKE TRUNCATE | Yes | Yes | Permission-based |

---

## 6. Recommendations

### Immediate (This Story)

1. **Create EventReplicatorPort interface** - Abstract port for replication operations
2. **Create EventReplicatorStub** - Stub returning success (no replicas in Epic 1)
3. **No schema changes required** - Schema is already replication-ready

### Future (Deployment Phase)

1. **Enable Supabase Read Replicas** - When ready for production
2. **Configure connection routing** - Primary for writes, any replica for reads
3. **Implement real EventReplicator** - Wire to Supabase replication APIs
4. **Add replica health monitoring** - Alert on lag > 1 second

---

## 7. Conclusion

**Decision: READY FOR REPLICATION**

The events table schema is fully compatible with PostgreSQL logical replication and Supabase read replicas. No schema modifications are required.

| Criterion | Status | Notes |
|-----------|--------|-------|
| UUID primary key | PASS | Globally unique |
| BIGSERIAL sequence | PASS | Works with single-writer |
| No blocking features | PASS | Standard PostgreSQL table |
| Single-writer architecture | PASS | ADR-1 enforced |
| Read path separation | PASS | Eventual consistency acceptable |

**Next Steps:**
1. Implement `EventReplicatorPort` interface
2. Implement `EventReplicatorStub` for Epic 1
3. Enable Supabase replicas during deployment phase

---

## References

- [Story 1.10: Replica Configuration Preparation](_bmad-output/implementation-artifacts/stories/1-10-replica-configuration-preparation.md)
- [Events Table Migration](migrations/001_create_events_table.sql)
- [Architecture ADR-1](_bmad-output/planning-artifacts/architecture.md)
- [Story 1.9 Schema GO Decision](docs/spikes/1-9-observer-query-schema-spike-report.md)
- [Supabase Read Replicas](https://supabase.com/docs/guides/platform/read-replicas)
- [PostgreSQL Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)
