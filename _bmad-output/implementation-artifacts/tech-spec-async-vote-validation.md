---
title: 'Async Vote Validation with Kafka'
slug: 'async-vote-validation-kafka'
created: '2026-01-23'
status: 'ready-for-review'
stepsCompleted: [1, 2, 3]
tech_stack:
  - Kafka (Redpanda for local dev)
  - Avro + Schema Registry
  - Python confluent-kafka / aiokafka
  - fastavro
files_to_modify:
  - src/application/services/conclave_service.py
  - src/application/services/reconciliation_service.py (new)
  - src/application/ports/vote_publisher.py (new)
  - src/application/ports/kafka_health.py (new)
  - src/application/ports/reconciliation.py (new)
  - src/infrastructure/adapters/kafka/vote_publisher.py (new)
  - src/infrastructure/adapters/kafka/kafka_health_checker.py (new)
  - src/infrastructure/adapters/kafka/avro_serializer.py (new)
  - src/workers/validator_worker.py (new)
  - src/workers/consensus_aggregator.py (new)
  - src/workers/error_handler.py (new)
  - src/workers/validation_dispatcher.py (new)
  - src/domain/errors/reconciliation.py (new)
  - src/domain/models/reconciliation.py (new)
  - scripts/run_conclave.py
  - scripts/create_kafka_topics.py (new)
  - docker-compose.yml
  - .env.example
  - schemas/conclave/votes/*.avsc (new)
code_patterns:
  - Hexagonal architecture (ports/adapters)
  - Async/await for all I/O
  - Fallback hierarchy for resilience
  - Constitutional operations (no try/except on witness)
  - State reconstruction from Kafka replay
  - Per-validator partitioning (split-brain mitigation)
  - Session-bounded replay (V2 mitigation)
test_patterns:
  - Unit tests with mocked Kafka producer/consumer
  - Integration tests with Redpanda (testcontainers)
  - Invariant assertions in critical paths
  - Fallback path tests (Kafka down → sync)
  - State reconstruction tests (kill/restart aggregator)
adrs:
  - ADR-001: Message Infrastructure (Kafka/Redpanda)
  - ADR-002: Aggregator State Storage (In-memory + Kafka replay)
  - ADR-003: Topic Design & Partitioning (Stage-per-topic)
  - ADR-004: Worker Deployment Model (Single process Phase 1-2)
  - ADR-005: Error Handling Strategy (Category-specific with DLQ)
pre_mortem:
  - P1: Consumer lag health check (HALT on lag > 0 at timeout)
  - P2: Hard reconciliation gate (ReconciliationIncompleteError)
  - P3: Schema Registry health check
  - P4: Kafka-based state reconstruction (no Redis)
  - P5: Constitutional witness writes (no try/except)
  - P6: Tally recomputation with invariant assertion
  - P7: Worker presence check (consumer group members > 0)
red_team:
  - V1: DLQ fallback to optimistic + ReconciliationResult tracking
  - V2: Session-bounded replay with header filtering
  - V3: Witness SPOF (accepted per CT-11/CT-13)
  - R1: Producer acks=all with send_and_wait()
  - R2: Schema Registry health required for publish
  - R3: Zero consumer lag before adjourn
  - Round 7: Split-brain mitigation via per-validator keying
---

# Tech-Spec: Async Vote Validation with Kafka

**Created:** 2026-01-23

## Overview

### Problem Statement

Synchronous dual-LLM vote validation blocks the Conclave deliberation pipeline, adding **9,216+ LLM calls** that execute sequentially. At 2-15s per call, this adds **5-115 hours** to session runtime. This is architecturally untenable.

Additionally, the current sync approach doesn't meet governance requirements:
- **No immutable audit trail**: Validation results aren't durably recorded
- **No event replay**: Can't replay validation for forensics/compliance
- **Not AGI-scale ready**: The problem compounds as archon count grows

### Solution

Implement async vote validation using Kafka (Redpanda for local dev) with **optimistic voting and deferred reconciliation**:

1. **Optimistic capture**: Parse vote immediately via regex, publish to Kafka, continue to next archon
2. **Async validation**: Worker consumers invoke validator LLMs in parallel
3. **Consensus aggregation**: Track validator agreement, retry on disagreement
4. **Reconciliation gate**: Block only at session adjournment to apply any vote overrides

The sync validation code becomes the fallback when `ENABLE_ASYNC_VALIDATION=false` or Kafka is unhealthy.

### Scope

**In Scope (Phase 1-2):**

1. Redpanda docker-compose addition (infrastructure)
2. Topic creation script with Avro schemas (infrastructure)
3. `KafkaVotePublisher` adapter (new file)
4. `KafkaHealthChecker` with full health definition (new file)
5. `ValidatorWorker` as single-process consumer (new file)
6. `ConsensusAggregator` with Kafka-based state reconstruction (new file)
7. `ReconciliationService` with hard `await_all_validations()` gate (new file)
8. Modifications to `ConclaveService._get_archon_vote()` to publish
9. Modifications to `ConclaveService.adjourn()` to gate on reconciliation
10. Environment variables documented in `.env.example`
11. Integration test proving the round-trip works

**Out of Scope:**

- Kubernetes HPA (only matters in K8s deployment)
- Prometheus metrics (important but not blocking)
- Multi-tenant topic prefixes (future-proofing)
- Pluggable validator registry (over-engineering for now)

---

## Pre-mortem Analysis: Critical Failure Modes

*Conducted 2026-01-23. These are the most likely failure modes for distributed systems—every one has happened in production somewhere.*

| ID | Failure Scenario | Root Cause | Prevention (P0) |
|----|-----------------|------------|-----------------|
| **P1** | Votes published but never consumed | Validator worker crashed silently, no consumer lag alerting | Consumer lag health check in `await_all_validations()`. Lag > 0 after timeout = HALT session |
| **P2** | Reconciliation gate timed out, session proceeded | Timeout caught as warning, not error | `await_all_validations()` raises `ReconciliationIncompleteError`, cannot be suppressed |
| **P3** | Schema Registry down during publish | Producer silently failed, votes dropped | Schema Registry health in Kafka health check. Unhealthy = sync fallback |
| **P4** | Consensus aggregator state lost | Redis restart orphaned in-flight validations | Aggregator state reconstructable from Kafka replay. No Redis for critical path |
| **P5** | Validator disagreement logged but not witnessed | `try/except` swallowed `KnightWitnessProtocol` error | Witness writes are constitutional operations. No `try/except` allowed |
| **P6** | Vote override applied but tally not recomputed | `vote.choice` mutated but `motion.tally_votes()` not called | Explicit recompute + invariant assertion: `sum == len(votes)` |
| **P7** | Async enabled but workers never started | Consumer group empty, but broker reachable | Health check requires active consumer group members |

### P0 Requirements from Pre-mortem

| Requirement | Implementation |
|-------------|----------------|
| **Hard reconciliation gate** | `await_all_validations()` raises `ReconciliationIncompleteError`, caller cannot suppress |
| **Full Kafka health check** | Healthy = broker + schema registry + consumer group active |
| **State reconstruction** | Aggregator replays Kafka topics on startup, no Redis for critical state |
| **Witness writes propagate** | No `try/except` around `KnightWitnessProtocol` calls in validation path |
| **Tally recompute on override** | `motion.tally_votes()` called + invariant assertion |
| **Worker presence check** | Health check fails if consumer group has 0 members |
| **Sync fallback auto-activates** | When `KafkaHealthStatus.should_fallback_to_sync` is True |

---

## Context for Development

### Codebase Patterns

**Hexagonal Architecture:**
- Domain models in `src/domain/models/conclave.py`
- Application services in `src/application/services/`
- Infrastructure adapters in `src/infrastructure/adapters/`
- Ports (protocols) in `src/application/ports/`

**Existing Sync Validation:**
- `ConclaveService._validate_vote_consensus()` at line 1074
- `ConclaveService._request_vote_validation()` at line 1108
- `ConclaveService._parse_validation_json()` at line 1166
- `ConclaveService._record_vote_validation_failure()` at line 1190

**Fallback Hierarchy:**
```
ENABLE_ASYNC_VALIDATION=true + Kafka healthy  -> async path
ENABLE_ASYNC_VALIDATION=true + Kafka down     -> sync fallback + warning log
ENABLE_ASYNC_VALIDATION=false                 -> sync path (current behavior)
```

**Constitutional Constraints:**
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> All validation events witnessed
- D12: Constitutional operations cannot be retried -> Witness writes are final

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `src/application/services/conclave_service.py` | Existing sync validation logic to integrate with |
| `src/domain/models/conclave.py` | `VoteChoice`, `Vote`, `Motion` domain models |
| `src/application/ports/knight_witness.py` | `KnightWitnessProtocol` for witnessed events |
| `docs/spikes/conclave_vote_update.md` | Sync validation spike (implemented) |
| `docs/spikes/Conclave async vote validation spike.md` | Full async architecture proposal |
| `_bmad-output/project-context.md` | Project rules and patterns |

### Technical Decisions

**TD-1: Redpanda over Kafka for local dev**
- Single binary, Kafka-compatible
- Simpler ops than full Kafka
- Production can use Confluent Cloud or self-hosted Kafka

**TD-2: Avro schemas with Schema Registry**
- Forward/backward compatible schema evolution
- Type-safe serialization
- Required for Kafka best practices

**TD-3: Kafka-based state reconstruction (NOT Redis)**
- Aggregator state must be reconstructable from Kafka topics
- On startup, replay `validation-results` topic to rebuild in-flight state
- Redis acceptable for caching/metrics, NOT for critical governance state
- Per pre-mortem P4: Redis restart cannot orphan validations

**TD-4: Sync fallback path preserved**
- Existing `_validate_vote_consensus()` becomes fallback
- No feature removal, only addition
- Toggle via `ENABLE_ASYNC_VALIDATION` env var
- Auto-fallback when Kafka unhealthy (per P7)

**TD-5: Constitutional operation semantics**
- Witness writes in validation path have no `try/except`
- Failures propagate up the call stack
- If witness fails, vote validation fails, session halts
- This is intentional: unwitnessed validation failure is worse than halt

---

## Architecture Decision Records

### ADR-ASYNC-001: Message Infrastructure for Vote Validation

**Status:** Accepted
**Decision:** Apache Kafka (via Redpanda)

**Options Considered:**

| Option | Audit Trail | Event Replay | Consumer Groups | Ops Complexity |
|--------|-------------|--------------|-----------------|----------------|
| Kafka (Redpanda) | Native | Native | Native | Medium |
| Redis Streams | Configurable | XRANGE (awkward) | Native | Low |
| PostgreSQL + Outbox | Outbox table | SELECT | Build it | Low |
| In-Memory asyncio.Queue | None | None | N/A | None |

**Rationale:**

1. **Governance requirements are non-negotiable.** Immutable audit trail (CT-12) and event replay are P0. Only Kafka and PostgreSQL satisfy both natively.
2. **PostgreSQL lacks consumer groups.** Building coordination on LISTEN/NOTIFY is reinventing Kafka poorly.
3. **Redis Streams fail pre-mortem P4.** State reconstruction from Redis is fragile.
4. **Redpanda eliminates ops complexity.** Single binary, Kafka-compatible, no ZooKeeper.
5. **AGI-scale readiness.** Kafka scales horizontally when archon count grows to 10,000+.

**Consequences:**

- New infrastructure dependency (Redpanda in docker-compose)
- Team must learn Kafka consumer patterns
- Schema Registry adds deployment artifact (Avro schemas)
- Sync fallback path must remain for Kafka-down scenarios
- **Must implement circuit breaker for Kafka health → sync fallback activation**

---

### ADR-ASYNC-002: State Storage for Consensus Aggregator

**Status:** Accepted
**Decision:** In-memory + Kafka replay

**Options Considered:**

| Option | Durability | Reconstruction | Complexity |
|--------|------------|----------------|------------|
| Redis | AOF gaps | Lost on restart | Low |
| PostgreSQL | ACID | Query on startup | Medium |
| Kafka compacted topic | Replicated | Replay on startup | Low |
| **In-memory + Kafka replay** | Process-bound | Replay on startup | Low |

**Rationale:**

1. **Kafka is already the source of truth.** `validation-results` topic contains all data needed.
2. **Replay on startup is simple.** Seek to beginning, replay messages, rebuild state.
3. **No additional infrastructure.** Redis for critical state rejected in pre-mortem P4.
4. **Graceful degradation.** Aggregator crash → restart → state reconstructed.

**Implementation Pattern (Idempotent Replay):**

```python
class ConsensusAggregator:
    def __init__(self):
        self._pending: dict[str, PendingValidation] = {}
        self._complete: set[str] = set()  # Prevents re-processing finalized votes

    async def startup(self) -> None:
        """Reconstruct state from Kafka. Idempotent."""
        async for msg in self._consumer.replay_from_beginning():
            vote_id = msg.value.vote_id

            if msg.topic == "conclave.votes.validation-results":
                if vote_id not in self._complete:  # Idempotent guard
                    self._accumulate_result(msg.value)

            elif msg.topic == "conclave.votes.validated":
                self._complete.add(vote_id)
                self._pending.pop(vote_id, None)
```

**Consequences:**

- Aggregator startup includes replay phase (adds seconds, not minutes)
- Must handle duplicate messages idempotently (Kafka at-least-once)
- In-memory state size bounded: ~4,608 votes × ~2KB = ~10MB max per session

---

### ADR-ASYNC-003: Topic Design and Partitioning

**Status:** Accepted
**Decision:** Stage-per-topic with `vote_id` partitioning

**Topic Configuration:**

| Topic | Partitions | Retention | Compaction | Key | Purpose |
|-------|------------|-----------|------------|-----|---------|
| `conclave.votes.pending-validation` | 6 | 7 days | None | `vote_id` | Votes awaiting validation |
| `conclave.votes.validation-results` | 6 | 30 days | None | `vote_id` | Individual validator responses |
| `conclave.votes.validated` | 6 | 90 days | Compact | `vote_id` | Final consensus results |
| `conclave.votes.dead-letter` | 1 | Infinite | None | `vote_id` | Failed validations for review |
| `conclave.witness.events` | 3 | Infinite | None | `session_id` | Witnessed governance events |

**Rationale:**

1. **Clear data flow.** Each topic = workflow stage: `pending → results → validated`
2. **Independent consumer groups.** No interference between workers and aggregator.
3. **Partition by `vote_id`.** All messages for single vote colocate → ordering preserved for retries.
4. **Compaction strategy differs.** `validated` compacts (final state). `results` retains all attempts for audit.

---

### ADR-ASYNC-004: Worker Deployment Model

**Status:** Accepted
**Decision:** Single process per worker type (Phase 1-2), K8s HPA (Phase 3)

**docker-compose Configuration:**

```yaml
services:
  validator-worker:
    command: python -m src.workers.validator_worker
    deploy:
      replicas: 2  # One per validator archon (Furcas, Orias)

  consensus-aggregator:
    command: python -m src.workers.consensus_aggregator
    deploy:
      replicas: 1  # Singleton - state reconstruction handles restarts
```

**Rationale:**

1. **2 validator workers** - One per validator archon. Each handles its validator's queue independently.
2. **1 aggregator** - Singleton with in-memory state. ADR-002 ensures crash recovery via replay.
3. **Isolated failure domain** - Worker crash doesn't bring down Conclave service.
4. **Phase 3 adds HPA** - Scale based on `kafka_consumer_lag` metric.

---

### ADR-ASYNC-005: Error Handling Strategy

**Status:** Accepted
**Decision:** Category-specific handling with dead-letter queue

**Error Categories and Actions:**

| Category | Examples | Action | Behavior |
|----------|----------|--------|----------|
| **Transient** | Network timeout, LLM rate limit | `RETRY` | Exponential backoff (1s, 2s, 4s), max 3 attempts |
| **Permanent** | Invalid vote format, unknown archon | `DEAD_LETTER` | Route to DLQ, continue processing |
| **Constitutional** | Witness write failure | `PROPAGATE` | Halt everything (TD-5) |
| **Duplicate** | Already-processed vote (idempotent) | `SKIP` | Safe to ignore |

**Implementation:**

```python
class ErrorAction(Enum):
    RETRY = "retry"           # Transient - try again with backoff
    DEAD_LETTER = "dlq"       # Permanent - route to DLQ, continue processing
    PROPAGATE = "propagate"   # Constitutional - halt everything
    SKIP = "skip"             # Idempotent duplicate - safe to ignore

class ValidationErrorHandler:
    async def handle(self, error: Exception, vote: PendingVote) -> ErrorAction:
        if isinstance(error, (TimeoutError, RateLimitError)):
            if vote.attempt < self._max_retries:
                return ErrorAction.RETRY
            return ErrorAction.DEAD_LETTER

        if isinstance(error, (InvalidVoteError, UnknownArchonError)):
            return ErrorAction.DEAD_LETTER

        if isinstance(error, WitnessWriteError):
            return ErrorAction.PROPAGATE  # Caller must handle - constitutional

        if isinstance(error, DuplicateVoteError):
            return ErrorAction.SKIP  # Idempotent - already processed

        # Unknown error - fail safe to DLQ
        return ErrorAction.DEAD_LETTER
```

**Consequences:**

- Dead-letter consumer needed for alerting (Phase 3)
- Retry backoff: 1s, 2s, 4s (exponential, max 3)
- Constitutional errors bypass all retry logic
- `SKIP` handles Kafka at-least-once delivery guarantee

---

## Complete ADR Registry

| ADR | Title | Status | Decision |
|-----|-------|--------|----------|
| **001** | Message Infrastructure | Accepted | Kafka (Redpanda) |
| **002** | Aggregator State Storage | Accepted | In-memory + Kafka replay |
| **003** | Topic Design & Partitioning | Accepted | Stage-per-topic, key by `vote_id` |
| **004** | Worker Deployment Model | Accepted | Single process (Phase 1-2), K8s HPA (Phase 3) |
| **005** | Error Handling Strategy | Accepted | Category-specific with DLQ |

---

## Component to ADR Mapping

| Component | ADR/Pre-mortem | File Path |
|-----------|----------------|-----------|
| Redpanda docker-compose | ADR-001, ADR-004 | `docker-compose.yml` |
| Topic creation script | ADR-003 | `scripts/create_kafka_topics.py` |
| Avro schemas | ADR-001, ADR-003 | `schemas/conclave/votes/*.avsc` |
| KafkaVotePublisher | ADR-001 | `src/infrastructure/adapters/kafka/vote_publisher.py` |
| KafkaHealthChecker | ADR-001, P3, P7 | `src/infrastructure/adapters/kafka/kafka_health_checker.py` |
| ValidatorWorker | ADR-001, ADR-004 | `src/workers/validator_worker.py` |
| ConsensusAggregator | ADR-002, ADR-004 | `src/workers/consensus_aggregator.py` |
| Kafka replay on startup | ADR-002 | In aggregator `startup()` |
| ValidationErrorHandler | ADR-005 | `src/workers/error_handler.py` |
| ReconciliationService | P1, P2 | `src/application/services/reconciliation_service.py` |
| ReconciliationIncompleteError | P2 | `src/domain/errors/reconciliation.py` |
| Witness write propagation | P5, ADR-005 | No try/except in validation path |
| Tally recompute on override | P6 | `motion.tally_votes()` + invariant |
| Sync fallback + circuit breaker | ADR-001 | In `ConclaveService._collect_vote()` |
| Dead-letter topic consumer | ADR-003, ADR-005 | Phase 3 (alerting) |

---

## Implementation Patterns (from Pre-mortem)

### Pattern 1: Hard Reconciliation Gate

```python
async def await_all_validations(self, session_id: str, timeout: int) -> None:
    """Block until all validations complete. Raises on incomplete."""
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        pending = await self._get_pending_count(session_id)
        lag = await self._get_consumer_lag("conclave.votes.pending-validation")

        if pending == 0 and lag == 0:
            return  # Success

        await asyncio.sleep(5)

    # HARD FAILURE - not a warning
    raise ReconciliationIncompleteError(
        f"Session {session_id} has {pending} unvalidated votes, "
        f"consumer lag={lag}. Cannot adjourn."
    )
```

### Pattern 2: Full Kafka Health Check

```python
@dataclass
class KafkaHealthStatus:
    broker_reachable: bool
    schema_registry_reachable: bool
    consumer_group_active: bool
    consumer_lag: int

    @property
    def healthy(self) -> bool:
        return (
            self.broker_reachable
            and self.schema_registry_reachable
            and self.consumer_group_active
        )

    @property
    def should_fallback_to_sync(self) -> bool:
        return not self.healthy
```

### Pattern 3: State Reconstruction from Kafka

```python
class ConsensusAggregator:
    async def startup(self) -> None:
        """Rebuild state by replaying topics. Called on every start."""
        self._consumer.seek_to_beginning()

        async for msg in self._consumer:
            if msg.topic == "conclave.votes.validation-results":
                self._apply_validation_result(msg.value, replay=True)
            elif msg.topic == "conclave.votes.validated":
                self._mark_complete(msg.value.vote_id)

        logger.info(
            "aggregator_state_rebuilt pending=%d complete=%d",
            len(self._pending), len(self._complete),
        )
```

### Pattern 4: Constitutional Witness Writes

```python
def _record_vote_validation_failure(
    self, archon: ArchonProfile, motion: Motion
) -> None:
    """Record witnessed event. MUST NOT be caught."""
    # NO try/except - this is a constitutional operation (D12)
    self._knight_witness.record_event(
        event_type=WitnessEventType.VOTE_VALIDATION_NON_CONSENSUS,
        description=f"Validators could not reach consensus on {archon.name}'s vote",
        participants=[archon.name, *self._validator_names],
        target_id=str(motion.motion_id),
        target_type="motion",
        severity=WitnessSeverity.HIGH,
    )
    # If this throws, validation fails, session halts. Intentional.
```

### Pattern 5: Tally Recomputation with Invariant

```python
def _apply_override_and_recompute(
    self, motion: Motion, override: VoteOverride
) -> bool:
    """Apply override and recompute tally. Returns True if result changed."""
    vote = motion.get_vote(override.archon_id)
    vote.choice = override.validated_choice

    old_passed = motion.passed
    motion.tally_votes()

    # Invariant assertion
    total = motion.final_ayes + motion.final_nays + motion.final_abstentions
    assert total == len(motion.votes), (
        f"Tally invariant violated: {total} != {len(motion.votes)}"
    )

    return motion.passed != old_passed
```

---

## Implementation Plan

### Phase 1: Infrastructure Foundation

| Task | File | Description | ADR/Pre-mortem |
|------|------|-------------|----------------|
| 1.1 | `docker-compose.yml` | Add Redpanda + Schema Registry services | ADR-001 |
| 1.2 | `scripts/create_kafka_topics.py` | Topic creation with retention/partitioning | ADR-003 |
| 1.3 | `schemas/conclave/votes/pending_validation.avsc` | Avro schema for pending votes | ADR-001, ADR-003 |
| 1.4 | `schemas/conclave/votes/validation_result.avsc` | Avro schema for validator responses | ADR-001, ADR-003 |
| 1.5 | `schemas/conclave/votes/validated.avsc` | Avro schema for final consensus | ADR-001, ADR-003 |
| 1.6 | `.env.example` | Add Kafka/validation env vars | - |

### Phase 2: Core Implementation

| Task | File | Description | ADR/Pre-mortem |
|------|------|-------------|----------------|
| 2.1 | `src/application/ports/vote_publisher.py` | `VotePublisherProtocol` interface | Hexagonal |
| 2.2 | `src/application/ports/kafka_health.py` | `KafkaHealthProtocol` interface | P3, P7 |
| 2.3 | `src/application/ports/reconciliation.py` | `ReconciliationProtocol` interface | P1, P2 |
| 2.4 | `src/infrastructure/adapters/kafka/vote_publisher.py` | `KafkaVotePublisher` adapter | ADR-001, R1 |
| 2.5 | `src/infrastructure/adapters/kafka/kafka_health_checker.py` | `KafkaHealthChecker` with full health | P3, P7 |
| 2.6 | `src/infrastructure/adapters/kafka/avro_serializer.py` | Avro serialization with Schema Registry | ADR-001 |
| 2.7 | `src/workers/validator_worker.py` | Consumer that invokes validator LLMs | ADR-004 |
| 2.8 | `src/workers/consensus_aggregator.py` | State machine with Kafka replay | ADR-002, V2 |
| 2.9 | `src/workers/error_handler.py` | `ValidationErrorHandler` | ADR-005 |
| 2.10 | `src/workers/validation_dispatcher.py` | Per-validator request routing | Round 7 |
| 2.11 | `src/application/services/reconciliation_service.py` | `ReconciliationService` with hard gate | P1, P2, V1 |
| 2.12 | `src/domain/errors/reconciliation.py` | `ReconciliationIncompleteError` | P2 |
| 2.13 | `src/domain/models/reconciliation.py` | `ReconciliationResult` dataclass | V1 |
| 2.14 | `src/application/services/conclave_service.py` | Modify `_get_archon_vote()` to publish | - |
| 2.15 | `src/application/services/conclave_service.py` | Modify `adjourn()` to gate on reconciliation | P1, P2 |
| 2.16 | `scripts/run_conclave.py` | Wire async validation toggle + health check | - |

### Phase 3: Testing & Hardening (Deferred)

| Task | Description | Priority |
|------|-------------|----------|
| 3.1 | Integration tests with Redpanda testcontainer | P1 |
| 3.2 | Fallback test: Kafka down → sync path | P1 |
| 3.3 | State reconstruction test: kill/restart aggregator | P1 |
| 3.4 | Dead-letter consumer for alerting | P2 |
| 3.5 | Prometheus metrics for consumer lag | P2 |
| 3.6 | K8s HPA based on lag metric | P3 |

---

## Interface Definitions

### VotePublisherProtocol

```python
# src/application/ports/vote_publisher.py
from typing import Protocol
from src.domain.models.conclave import Vote, Motion

class VotePublisherProtocol(Protocol):
    """Port for publishing votes to validation queue."""

    async def publish_for_validation(
        self,
        vote: Vote,
        motion: Motion,
        session_id: str,
    ) -> None:
        """
        Publish vote to pending-validation topic.

        MUST await broker acknowledgment (acks=all).
        MUST include session_id in headers.
        """
        ...

    async def close(self) -> None:
        """Flush and close producer."""
        ...
```

### KafkaHealthProtocol

```python
# src/application/ports/kafka_health.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class KafkaHealthStatus:
    broker_reachable: bool
    schema_registry_reachable: bool
    consumer_group_active: bool
    consumer_lag: int

    @property
    def healthy(self) -> bool:
        return (
            self.broker_reachable
            and self.schema_registry_reachable
            and self.consumer_group_active
        )

    @property
    def should_fallback_to_sync(self) -> bool:
        return not self.healthy


class KafkaHealthProtocol(Protocol):
    """Port for Kafka health checks."""

    async def check_health(self) -> KafkaHealthStatus:
        """
        Check all Kafka dependencies.

        Returns status with:
        - broker_reachable: Can connect to bootstrap servers
        - schema_registry_reachable: Can GET /subjects
        - consumer_group_active: Consumer group has >0 members
        - consumer_lag: Sum of partition lag
        """
        ...
```

### ReconciliationProtocol

```python
# src/application/ports/reconciliation.py
from typing import Protocol
from src.domain.models.reconciliation import ReconciliationResult

class ReconciliationProtocol(Protocol):
    """Port for vote reconciliation at session end."""

    async def await_all_validations(
        self,
        session_id: str,
        timeout_seconds: int = 300,
    ) -> ReconciliationResult:
        """
        Block until all validations complete.

        Raises ReconciliationIncompleteError if:
        - Timeout exceeded with pending votes
        - Consumer lag > 0 at timeout

        Returns ReconciliationResult with counts.
        """
        ...

    async def get_overrides(
        self,
        session_id: str,
    ) -> list["VoteOverride"]:
        """
        Get votes where validated choice differs from optimistic.

        These require tally recomputation.
        """
        ...
```

---

## Acceptance Criteria

### AC-1: Infrastructure

- [ ] `docker-compose up` starts Redpanda + Schema Registry
- [ ] `scripts/create_kafka_topics.py` creates all 5 topics with correct config
- [ ] Avro schemas validate against Schema Registry
- [ ] `.env.example` documents all new environment variables

### AC-2: Async Publishing

- [ ] When `ENABLE_ASYNC_VALIDATION=true` and Kafka healthy:
  - `_get_archon_vote()` publishes to `pending-validation` topic
  - Vote ID appears in topic within 1 second
  - Headers include `session_id` and `published_at`
- [ ] When Kafka unhealthy:
  - Falls back to sync validation
  - Warning logged: `"kafka_unhealthy falling_back_to_sync"`

### AC-3: Validation Workers

- [ ] `ValidatorWorker` consumes from `pending-validation`
- [ ] Invokes correct validator LLM based on assignment
- [ ] Produces to `validation-results` with validator response
- [ ] Handles errors per ADR-005 (RETRY/DEAD_LETTER/PROPAGATE/SKIP)

### AC-4: Consensus Aggregation

- [ ] `ConsensusAggregator` tracks validation results per vote
- [ ] On startup, replays Kafka filtering by `session_id` header (V2)
- [ ] When both validators agree: publishes to `validated`
- [ ] When validators disagree: retries up to 3 times
- [ ] After max retries without consensus: routes to DLQ

### AC-5: Reconciliation Gate

- [ ] `ReconciliationService.await_all_validations()` blocks until:
  - All pending validations complete (pending_count == 0)
  - Consumer lag is zero
- [ ] Returns `ReconciliationResult` with `validated_count`, `dlq_fallback_count`, `pending_count`
- [ ] Raises `ReconciliationIncompleteError` if timeout exceeded
- [ ] Error is NOT caught by caller - propagates to halt session

### AC-6: Vote Override Application

- [ ] Overrides (validated != optimistic) trigger `motion.tally_votes()`
- [ ] Invariant assertion: `ayes + nays + abstains == len(votes)`
- [ ] Changed outcomes are logged and witnessed

### AC-7: Constitutional Operations

- [ ] Witness writes in validation path have NO try/except
- [ ] `WitnessWriteError` propagates up, halting session
- [ ] Test: inject witness failure → session halts (not warns)

### AC-8: Health Check

- [ ] `KafkaHealthChecker` checks:
  - Broker connectivity (metadata request)
  - Schema Registry (GET /subjects)
  - Consumer group members > 0
  - Consumer lag (admin client)
- [ ] `should_fallback_to_sync` returns True when any check fails

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_ASYNC_VALIDATION` | No | `false` | Enable async vote validation via Kafka |
| `KAFKA_BOOTSTRAP_SERVERS` | When async | `localhost:9092` | Kafka/Redpanda broker addresses |
| `SCHEMA_REGISTRY_URL` | When async | `http://localhost:8081` | Confluent Schema Registry URL |
| `KAFKA_CONSUMER_GROUP` | When async | `conclave-validators` | Consumer group for validator workers |
| `VOTE_VALIDATION_TIMEOUT` | No | `300` | Seconds to wait for validations at adjourn |
| `VOTE_VALIDATION_MAX_RETRIES` | No | `3` | Max retry attempts on validator disagreement |
| `WITNESS_ARCHON_ID` | Yes | - | Archon ID for witness validator (Furcas) |
| `SECRETARY_TEXT_ARCHON_ID` | Yes | - | Archon ID for secretary validator (Orias) |

---

## Sequence Diagrams

### Happy Path: Async Vote Validation

```
ConclaveService              KafkaVotePublisher       ValidatorWorker(x2)       ConsensusAggregator
     |                              |                        |                         |
     |--publish_for_validation()--->|                        |                         |
     |                              |--send(pending-val)---->|                         |
     |                              |                        |                         |
     |  (continues to next archon)  |                        |--invoke LLM------------>|
     |                              |                        |                         |
     |                              |                        |<--validation result-----|
     |                              |                        |                         |
     |                              |                        |--send(val-results)----->|
     |                              |                        |                         |
     |                              |                        |         (both agree)    |
     |                              |                        |                         |
     |                              |                        |<--consensus reached-----|
     |                              |                        |                         |
     |                              |                        |--send(validated)------->|
     |                              |                        |                         |
     |                              |                        |                         |
  (at adjourn)                      |                        |                         |
     |                              |                        |                         |
     |----------------await_all_validations()--------------->|                         |
     |                              |                        |                         |
     |<---------------ReconciliationResult-------------------|                         |
```

### Fallback Path: Kafka Unhealthy

```
ConclaveService              KafkaHealthChecker       Existing Sync Path
     |                              |                        |
     |--check_health()------------->|                        |
     |                              |                        |
     |<--{healthy: false}-----------|                        |
     |                              |                        |
     |  (fallback decision)         |                        |
     |                              |                        |
     |--_validate_vote_consensus()------------------------>|
     |                              |                        |
     |<--consensus result----------------------------------|
```

### Error Path: Reconciliation Incomplete

```
ConclaveService              ReconciliationService
     |                              |
  (at adjourn)                      |
     |                              |
     |--await_all_validations()---->|
     |                              |
     |                       (timeout, pending > 0)
     |                              |
     |<--raise ReconciliationIncompleteError--|
     |                              |
  (session HALTS - not caught)      |
```

## Additional Context

### Dependencies

**New Python packages:**
- `confluent-kafka` (Kafka client - preferred over kafka-python for performance)
- `fastavro` (Avro serialization)

**New infrastructure:**
- Redpanda container in docker-compose
- Schema Registry (bundled with Redpanda)

### Testing Strategy

**Unit Tests:**
- Mock `KafkaProducer` for publish tests
- Mock `KafkaConsumer` for worker tests
- Test consensus logic with deterministic inputs
- Test `KafkaHealthStatus` combinations

**Integration Tests:**
- Redpanda in Docker (testcontainers pattern)
- End-to-end: publish vote -> validate -> reconcile
- Fallback test: Kafka down -> sync path activates
- State reconstruction test: kill aggregator mid-session, restart, verify recovery

**Invariant Tests:**
- Tally invariant: `ayes + nays + abstains == len(votes)`
- Reconciliation invariant: `pending == 0 && lag == 0` before adjourn

### Notes

- Validator archon IDs: `WITNESS_ARCHON_ID` (Furcas) + `SECRETARY_TEXT_ARCHON_ID` (Orias)
- Queue naturally clears during debate rounds (~18 min each)
- Final gate at adjournment ensures 100% validation before transcript generation
- No Redis for critical governance state (caching/metrics only)

---

## Red Team Analysis

*Conducted 2026-01-23. Adversarial review of the async validation architecture.*

### Vulnerabilities Identified

| ID | Attack Vector | Impact | Mitigation |
|----|---------------|--------|------------|
| **V1** | DLQ votes have undefined reconciliation behavior | Votes in dead-letter queue are neither validated nor rejected - reconciliation outcome undefined | Fallback to optimistic (regex-parsed) value. `ReconciliationResult` tracks `dlq_fallback_count` separately from `validated_count`. Witness the fallback. |
| **V2** | Unbounded replay on aggregator startup | Aggregator replays ALL messages from beginning - stale session data pollutes current state | Session-bounded replay. Publish `session_id` header on every message. Aggregator filters on current session during replay. |
| **V3** | Witness service SPOF | If witness is down, all validations fail (constitutional) | Accepted by design. CT-11: "Silent failure destroys legitimacy". CT-13 requires witnessed state changes. This is intentional. |

### V1 Implementation: ReconciliationResult Dataclass

```python
@dataclass
class ReconciliationResult:
    """Outcome of vote reconciliation."""
    validated_count: int          # LLM-validated votes
    dlq_fallback_count: int       # Fell back to optimistic (regex) value
    pending_count: int            # Still in-flight (should be 0 at completion)

    @property
    def complete(self) -> bool:
        """True if no votes are pending (may include DLQ fallbacks)."""
        return self.pending_count == 0

    @property
    def fully_validated(self) -> bool:
        """True if complete AND no fallbacks were required."""
        return self.complete and self.dlq_fallback_count == 0
```

### V2 Implementation: Session Header Filtering

```python
# Publisher adds session context
headers = {
    "session_id": session_id,
    "published_at": datetime.utcnow().isoformat(),
}

# Aggregator filters during replay
async def startup(self, session_id: str) -> None:
    """Reconstruct state for CURRENT SESSION ONLY."""
    async for msg in self._consumer.replay_from_beginning():
        if msg.headers.get("session_id") != session_id:
            continue  # Ignore stale session data

        if msg.topic == "conclave.votes.validation-results":
            self._apply_validation_result(msg.value)
        elif msg.topic == "conclave.votes.validated":
            self._mark_complete(msg.value.vote_id)
```

---

### Hardening Requirements

| ID | Requirement | Implementation |
|----|-------------|----------------|
| **R1** | Producer must use `acks=all` | `AIOKafkaProducer(acks="all", enable_idempotence=True)` + `send_and_wait()` instead of fire-and-forget |
| **R2** | Schema Registry health required for publish | Block vote publish if schema registry unreachable |
| **R3** | Consumer lag must be zero before adjourn | `KafkaHealthStatus.consumer_lag` checked in `await_all_validations()` |

### R1 Implementation: Producer Configuration

```python
producer = AIOKafkaProducer(
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    acks="all",                            # All in-sync replicas must acknowledge
    enable_idempotence=True,               # Exactly-once semantics
    max_in_flight_requests_per_connection=5,
    retries=3,
)

# Publisher must await acknowledgment
async def publish(self, vote: PendingVote) -> None:
    """Publish vote and AWAIT broker acknowledgment."""
    await self._producer.send_and_wait(  # NOT send() fire-and-forget
        topic="conclave.votes.pending-validation",
        key=vote.vote_id.encode(),
        value=self._serialize(vote),
        headers=self._build_headers(vote),
    )
```

---

### Round 7: Split-Brain Validator Attack

**Attack Vector:** Malicious or confused validator produces inconsistent results across message boundaries. Example: Furcas says AYE for partition 0, NAY for partition 1 of the same vote.

**Impact:** Consensus never reached, session halts or DLQ accumulates.

**Mitigation:** `ValidationDispatcher` produces to per-validator partitions with explicit keying:

```python
class ValidationDispatcher:
    """Routes validation requests to per-validator partitions."""

    async def dispatch(self, vote: PendingVote) -> None:
        """Send validation request to EACH validator with explicit keying."""
        for validator_id in [WITNESS_ARCHON_ID, SECRETARY_TEXT_ARCHON_ID]:
            await self._producer.send_and_wait(
                topic="conclave.votes.validation-requests",
                key=f"{vote.vote_id}:{validator_id}".encode(),  # Explicit composite key
                value=self._serialize(ValidationRequest(vote, validator_id)),
                headers={"validator_id": validator_id},
            )
```

This ensures each validator's request is keyed separately, preventing cross-partition inconsistency from affecting consensus determination.

---

## Red Team Summary

| Finding | Severity | Status |
|---------|----------|--------|
| V1: DLQ undefined | High | Mitigated (fallback + tracking) |
| V2: Unbounded replay | Medium | Mitigated (session filtering) |
| V3: Witness SPOF | Low | Accepted (by design per CT-11/CT-13) |
| R1: acks=all | P0 | Required for implementation |
| R2: Schema Registry health | P0 | Required for implementation |
| R3: Zero lag before adjourn | P0 | Required for implementation |
| Round 7: Split-brain | Medium | Mitigated (per-validator keying) |
