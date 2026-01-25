---
stepsCompleted: [1, 2]
inputDocuments:
  - _bmad-output/implementation-artifacts/tech-spec-async-vote-validation.md
status: ready-for-implementation
total_stories: 20
phase_1_stories: 9
phase_2_stories: 8
phase_3_stories: 3
---

# Async Vote Validation - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **Async Vote Validation with Kafka**, decomposing the tech spec requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

```
FR-AVV-1: System MUST publish votes to Kafka pending-validation topic when ENABLE_ASYNC_VALIDATION=true and Kafka is healthy
FR-AVV-2: System MUST fall back to synchronous validation when Kafka is unhealthy (circuit breaker pattern)
FR-AVV-3: Validator workers MUST consume pending votes and invoke assigned validator LLMs (Furcas, Orias)
FR-AVV-4: Consensus aggregator MUST track validator responses and determine agreement/disagreement
FR-AVV-5: Reconciliation service MUST block session adjournment until all validations complete
FR-AVV-6: System MUST apply vote overrides and recompute tallies when validated differs from optimistic
FR-AVV-7: System MUST witness all validation failures via KnightWitnessProtocol (constitutional)
FR-AVV-8: Health checker MUST verify broker, schema registry, consumer group, and lag status
FR-AVV-9: System MUST reconstruct aggregator state from Kafka replay on startup (no Redis)
FR-AVV-10: System MUST route failed validations to dead-letter queue after max retries
```

### Non-Functional Requirements

```
NFR-AVV-1: Consumer lag MUST be zero before session can adjourn (P1)
NFR-AVV-2: Reconciliation gate MUST raise ReconciliationIncompleteError, not warn (P2)
NFR-AVV-3: Schema Registry health MUST be verified before publishing (P3)
NFR-AVV-4: Aggregator state MUST be reconstructable from Kafka only, no Redis for critical path (P4)
NFR-AVV-5: Witness writes MUST NOT be wrapped in try/except - failures propagate (P5)
NFR-AVV-6: Tally recomputation MUST assert invariant: ayes + nays + abstains == len(votes) (P6)
NFR-AVV-7: Health check MUST verify consumer group has active members (P7)
NFR-AVV-8: Producer MUST use acks=all with send_and_wait() for durability (R1)
NFR-AVV-9: Schema Registry health MUST be required for vote publish (R2)
NFR-AVV-10: Consumer lag MUST be checked in await_all_validations() (R3)
NFR-AVV-11: Replay MUST filter by session_id header to prevent stale data pollution (V2)
NFR-AVV-12: Validation requests MUST use per-validator keying to prevent split-brain (Round 7)
NFR-AVV-13: DLQ votes MUST fall back to optimistic value with ReconciliationResult tracking (V1)
```

### Additional Requirements (from ADRs)

```
ADR-001: Use Kafka (Redpanda for local dev) for message infrastructure
ADR-002: Use in-memory state + Kafka replay for aggregator (no external state store)
ADR-003: Stage-per-topic design with vote_id partitioning
ADR-004: Single process per worker type (Phase 1-2), K8s HPA deferred to Phase 3
ADR-005: Category-specific error handling (RETRY, DEAD_LETTER, PROPAGATE, SKIP)
```

### FR Coverage Map

| FR/NFR | Epic | Story |
|--------|------|-------|
| FR-AVV-1 | Epic 2 | 2.1 |
| FR-AVV-2 | Epic 2 | 2.2 |
| FR-AVV-3 | Epic 3 | 3.1 |
| FR-AVV-4 | Epic 3 | 3.2 |
| FR-AVV-5 | Epic 4 | 4.1 |
| FR-AVV-6 | Epic 4 | 4.2 |
| FR-AVV-7 | Epic 4 | 4.3 |
| FR-AVV-8 | Epic 2 | 2.2 |
| FR-AVV-9 | Epic 3 | 3.2 |
| FR-AVV-10 | Epic 3 | 3.3 |
| NFR-AVV-1 through NFR-AVV-13 | Distributed across stories |

## Epic List

| Epic | Title | Stories | Priority | Phase |
|------|-------|---------|----------|-------|
| **Epic 1** | Infrastructure Foundation | 4 | P0 | Phase 1 |
| **Epic 2** | Async Publishing & Health | 5 | P0 | Phase 1 |
| **Epic 3** | Validation Workers & Aggregation | 4 | P0 | Phase 2 |
| **Epic 4** | Reconciliation & Integration | 4 | P0 | Phase 2 |
| **Epic 5** | Testing & Hardening | 3 | P1 | Phase 3 |

## Story Dependency Graph

```
Epic 1 (Foundation) ─────────────────────────────────────────────
├── 1.1 Redpanda docker-compose
├── 1.2 Topic creation ──────────────┐
├── 1.3 Avro schemas ────────────────┤
└── 1.4 Environment variables        │
                                     ▼
Epic 2 (Publishing) ─────────────────────────────────────────────
├── 2.3 Avro serializer ◄────────────┘
├── 2.2 Health checker
├── 2.2.1 Circuit breaker ◄── 2.2
├── 2.2.2 Startup health gate ◄── 2.2
└── 2.1 Vote publisher ◄── 2.2, 2.2.1, 2.3

Epic 3 (Workers) ────────────────────────────────────────────────
├── 3.4 Error handler
├── 3.3 Validation dispatcher ◄── 2.1
├── 3.1 Validator worker ◄── 3.3, 3.4
└── 3.2 Consensus aggregator ◄── 3.1

Epic 4 (Integration) ────────────────────────────────────────────
├── 4.1 Reconciliation service ◄── 3.2
├── 4.2 Vote override ◄── 4.1
├── 4.3 ConclaveService publish ◄── 2.1, 2.2 [PREREQ: vote parser fix merged]
└── 4.4 ConclaveService adjourn ◄── 4.1, 4.2, 4.3

Epic 5 (Testing) ────────────────────────────────────────────────
├── 5.1 Integration tests ◄── 4.4
├── 5.2 Fallback path tests ◄── 2.2.1
└── 5.3 State reconstruction tests ◄── 3.2
```

## Phase Deployment Strategy

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| **Phase 1** | Kafka infra + async publish | Votes publish to Kafka, fall through to sync (workers not yet built) |
| **Phase 2** | Worker pool + reconciliation gate | Full async validation pipeline operational |
| **Phase 3** | Production hardening | K8s HPA, Prometheus metrics, DLQ alerting |

**Phase 1 is independently deployable** - validates Kafka infrastructure without code changes to validation logic.

---

## Epic 1: Infrastructure Foundation

**Goal:** Establish Kafka/Redpanda infrastructure, schemas, and environment configuration required for async vote validation.

**ADRs:** ADR-001, ADR-003
**Pre-mortems:** P3, P7

### Story 1.1: Add Redpanda to Docker Compose

As a **developer**,
I want **Redpanda and Schema Registry running in docker-compose**,
So that **I have local Kafka-compatible infrastructure for async validation**.

**Acceptance Criteria:**

**Given** docker-compose.yml exists
**When** I run `docker-compose up`
**Then** Redpanda broker starts on port 9092
**And** Schema Registry starts on port 8081
**And** Both services pass health checks

**Technical Notes:**
- File: `docker-compose.yml`
- ADR-001: Redpanda over Kafka for local dev
- ADR-004: 2 validator workers, 1 aggregator in compose

---

### Story 1.2: Create Kafka Topics Script

As a **developer**,
I want **a script that creates all required Kafka topics with correct configuration**,
So that **topics are consistently created with proper partitioning and retention**.

**Acceptance Criteria:**

**Given** Redpanda is running
**When** I run `python scripts/create_kafka_topics.py`
**Then** 5 topics are created:
  - `conclave.votes.pending-validation` (6 partitions, 7d retention)
  - `conclave.votes.validation-results` (6 partitions, 30d retention)
  - `conclave.votes.validated` (6 partitions, 90d retention, compacted)
  - `conclave.votes.dead-letter` (1 partition, infinite retention)
  - `conclave.witness.events` (3 partitions, infinite retention)

**Technical Notes:**
- File: `scripts/create_kafka_topics.py`
- ADR-003: Topic design and partitioning

---

### Story 1.3: Define Avro Schemas

As a **developer**,
I want **Avro schemas for all vote validation messages**,
So that **messages are type-safe and schema-evolvable**.

**Acceptance Criteria:**

**Given** Schema Registry is running
**When** schemas are registered
**Then** `pending_validation.avsc` defines vote pending validation structure
**And** `validation_result.avsc` defines validator response structure
**And** `validated.avsc` defines final consensus structure
**And** All schemas pass Schema Registry validation

**Technical Notes:**
- Files: `schemas/conclave/votes/*.avsc`
- ADR-001: Avro + Schema Registry for type safety

---

### Story 1.4: Document Environment Variables

As a **developer**,
I want **all new environment variables documented in .env.example**,
So that **configuration is discoverable and self-documenting**.

**Acceptance Criteria:**

**Given** .env.example exists
**When** I review async validation config
**Then** These variables are documented:
  - `ENABLE_ASYNC_VALIDATION`
  - `KAFKA_BOOTSTRAP_SERVERS`
  - `SCHEMA_REGISTRY_URL`
  - `KAFKA_CONSUMER_GROUP`
  - `VOTE_VALIDATION_TIMEOUT`
  - `VOTE_VALIDATION_MAX_RETRIES`

**Technical Notes:**
- File: `.env.example`

---

## Epic 2: Async Publishing & Health

**Goal:** Implement vote publishing to Kafka with health checks and sync fallback.

**ADRs:** ADR-001, ADR-005
**Pre-mortems:** P3, P7
**Red Team:** R1, R2

### Story 2.1: Implement VotePublisher Port and Adapter

As a **Conclave service**,
I want **to publish votes to Kafka for async validation**,
So that **validation can happen in parallel without blocking deliberation**.

**Acceptance Criteria:**

**Given** `ENABLE_ASYNC_VALIDATION=true` and Kafka is healthy
**When** `_get_archon_vote()` captures a vote
**Then** Vote is published to `pending-validation` topic
**And** Headers include `session_id` and `published_at`
**And** Producer uses `acks=all` with `send_and_wait()` (R1)

**Given** Vote publish fails
**When** Error is transient (network timeout)
**Then** Publisher retries with exponential backoff
**And** After max retries, falls back to sync validation

**Technical Notes:**
- Port: `src/application/ports/vote_publisher.py`
- Adapter: `src/infrastructure/adapters/kafka/vote_publisher.py`
- NFR-AVV-8 (R1): acks=all required

---

### Story 2.2: Implement Kafka Health Checker

As a **Conclave service**,
I want **comprehensive Kafka health checking**,
So that **I can fall back to sync validation when Kafka is unhealthy**.

**Acceptance Criteria:**

**Given** Health check is invoked
**When** All checks pass
**Then** `KafkaHealthStatus.healthy` returns True
**And** `should_fallback_to_sync` returns False

**Given** Any check fails (broker, schema registry, consumer group)
**When** Health is evaluated
**Then** `should_fallback_to_sync` returns True
**And** Warning logged: `"kafka_unhealthy falling_back_to_sync"`

**Given** Consumer group has 0 members (P7)
**When** Health is evaluated
**Then** `consumer_group_active` is False
**And** System falls back to sync

**Technical Notes:**
- Port: `src/application/ports/kafka_health.py`
- Adapter: `src/infrastructure/adapters/kafka/kafka_health_checker.py`
- P3: Schema Registry health check
- P7: Worker presence check

---

### Story 2.2.1: Implement Circuit Breaker for Kafka

As a **Conclave service**,
I want **a circuit breaker that tracks Kafka failures**,
So that **repeated failures trigger fast fallback without retry overhead**.

**Acceptance Criteria:**

**Given** Circuit is CLOSED (healthy)
**When** 3 consecutive publish failures occur
**Then** Circuit opens
**And** Subsequent publishes immediately fall back to sync (no Kafka attempt)

**Given** Circuit is OPEN
**When** 30 seconds have elapsed
**Then** Circuit moves to HALF-OPEN
**And** Next publish attempts Kafka
**And** Success → CLOSED, Failure → OPEN

**Given** Circuit state changes
**When** Transition occurs
**Then** State change is logged with metrics

**Technical Notes:**
- File: `src/infrastructure/adapters/kafka/circuit_breaker.py`
- Pattern: Circuit breaker (Hystrix-style)
- Depends on: Story 2.2 (Health checker)

---

### Story 2.2.2: Implement Startup Health Gate

As a **Conclave service**,
I want **async validation to require healthy Kafka at session start**,
So that **sessions don't start with async enabled if workers aren't running**.

**Acceptance Criteria:**

**Given** `ENABLE_ASYNC_VALIDATION=true`
**When** Conclave session begins
**Then** Full health check runs (broker + schema + consumers)
**And** If healthy, async validation proceeds
**And** If unhealthy, `ENABLE_ASYNC_VALIDATION` is overridden to `false` for this session
**And** Warning logged: `"async_validation_disabled_at_startup reason=<component>"`

**Given** Startup health gate fails
**When** Session proceeds with sync fallback
**Then** No further Kafka attempts are made for this session
**And** Circuit breaker is initialized to OPEN state

**Technical Notes:**
- Integrated into `scripts/run_conclave.py` session startup
- Depends on: Story 2.2 (Health checker)

---

### Story 2.3: Implement Avro Serializer

As a **vote publisher**,
I want **Avro serialization with Schema Registry integration**,
So that **messages are type-safe and schema-validated**.

**Acceptance Criteria:**

**Given** Schema Registry is healthy
**When** Vote is serialized
**Then** Message conforms to registered Avro schema
**And** Schema ID is included in message header

**Given** Schema Registry is unhealthy (R2)
**When** Serialization is attempted
**Then** `SchemaRegistryUnavailableError` is raised
**And** System falls back to sync validation

**Technical Notes:**
- File: `src/infrastructure/adapters/kafka/avro_serializer.py`
- NFR-AVV-9 (R2): Schema Registry health required

---

## Epic 3: Validation Workers & Aggregation

**Goal:** Implement consumer workers that invoke validators and aggregate consensus.

**ADRs:** ADR-002, ADR-004, ADR-005
**Pre-mortems:** P4, P5
**Red Team:** V2, Round 7

### Story 3.1: Implement Validator Worker

As a **validation worker**,
I want **to consume pending votes and invoke my assigned validator LLM**,
So that **votes are validated asynchronously in parallel**.

**Acceptance Criteria:**

**Given** Worker starts with `VALIDATOR_ARCHON_ID=<furcas_id>`
**When** Message arrives on `validation-requests`
**Then** Worker ONLY processes messages where header `validator_id` matches its assigned archon
**And** Messages for other validators are skipped (not consumed from that partition)

**Given** Worker processes a validation request
**When** Validator LLM is invoked
**Then** Produces validation result to `validation-results`
**And** Result includes `validator_id` in headers

**Given** Witness write fails (P5)
**When** Error is WitnessWriteError
**Then** ErrorAction.PROPAGATE is returned
**And** Worker does NOT catch the error (constitutional)

**Technical Notes:**
- File: `src/workers/validator_worker.py`
- File: `src/workers/error_handler.py`
- ADR-004: 2 workers, one per validator (Furcas, Orias)
- ADR-005: Error handling strategy
- Round 7: Each worker instance dedicated to exactly one validator

---

### Story 3.2: Implement Consensus Aggregator

As a **consensus aggregator**,
I want **to track validator responses and determine consensus**,
So that **validated votes can be recorded when both validators agree**.

**Acceptance Criteria:**

**Given** Both validators return same choice
**When** Aggregator processes second result
**Then** Consensus is reached
**And** Final result published to `validated` topic

**Given** Validators disagree
**When** Aggregator processes results
**Then** Retry is scheduled up to 3 times
**And** After max retries, routes to DLQ

**Given** Aggregator restarts (P4)
**When** Startup sequence runs
**Then** State is reconstructed from Kafka replay
**And** Only current session_id messages are processed (V2)

**Given** Message is replayed (duplicate `vote_id` + `validator_id`)
**When** Aggregator already has result for this (vote, validator) pair
**Then** Message is skipped (idempotent - ADR-005 SKIP)
**And** No state mutation occurs

**Technical Notes:**
- File: `src/workers/consensus_aggregator.py`
- ADR-002: In-memory + Kafka replay
- ADR-005: SKIP action for idempotent duplicate handling
- NFR-AVV-4 (P4): No Redis for critical path
- NFR-AVV-11 (V2): Session-bounded replay

---

### Story 3.3: Implement Validation Dispatcher

As a **validation system**,
I want **per-validator request routing with explicit keying**,
So that **split-brain scenarios are prevented (Round 7)**.

**Acceptance Criteria:**

**Given** Vote needs validation
**When** Dispatcher routes request
**Then** Separate messages sent to each validator
**And** Key format is `{vote_id}:{validator_id}`
**And** Headers include `validator_id`

**Technical Notes:**
- File: `src/workers/validation_dispatcher.py`
- Round 7: Split-brain mitigation via per-validator keying

---

### Story 3.4: Implement Error Handler

As a **validation worker**,
I want **category-specific error handling**,
So that **transient errors retry, permanent errors DLQ, and constitutional errors propagate**.

**Acceptance Criteria:**

**Given** TimeoutError or RateLimitError
**When** Error handler evaluates
**Then** Returns RETRY (if under max attempts)
**And** Returns DEAD_LETTER (if at max attempts)

**Given** WitnessWriteError
**When** Error handler evaluates
**Then** Returns PROPAGATE (constitutional - halt everything)

**Given** DuplicateVoteError
**When** Error handler evaluates
**Then** Returns SKIP (idempotent - safe to ignore)

**Technical Notes:**
- File: `src/workers/error_handler.py`
- ADR-005: Error handling strategy

---

## Epic 4: Reconciliation & Integration

**Goal:** Implement reconciliation gate and integrate async validation into Conclave service.

**Pre-mortems:** P1, P2, P5, P6
**Red Team:** V1, R3

### Story 4.1: Implement Reconciliation Service

As a **Conclave service**,
I want **a hard reconciliation gate at session adjournment**,
So that **sessions cannot complete with unvalidated votes**.

**Acceptance Criteria:**

**Given** Session is adjourning
**When** `await_all_validations()` is called
**Then** Blocks until:
  - `pending_count == 0` (all votes dispatched)
  - `consumer_lag == 0` (all messages consumed)
  - `dlq_count` is known (may be > 0)
**And** Returns `ReconciliationResult(validated_count, dlq_fallback_count, pending_count=0)`

**Given** Timeout exceeded with pending votes (P1, P2)
**When** Gate evaluates
**Then** Raises `ReconciliationIncompleteError` (NOT a warning)
**And** Error propagates up (session HALTS)

**Given** DLQ votes exist (V1)
**When** Reconciliation completes
**Then** DLQ votes fall back to optimistic value
**And** `dlq_fallback_count` tracked in result
**And** Each fallback is witnessed via KnightWitnessProtocol
**And** `ReconciliationResult.fully_validated` returns False

**Technical Notes:**
- Port: `src/application/ports/reconciliation.py`
- Service: `src/application/services/reconciliation_service.py`
- Domain: `src/domain/models/reconciliation.py` (ReconciliationResult)
- Error: `src/domain/errors/reconciliation.py` (ReconciliationIncompleteError)

---

### Story 4.2: Implement Vote Override Application

As a **reconciliation service**,
I want **to apply vote overrides when validated differs from optimistic**,
So that **tallies are accurate based on validated votes**.

**Acceptance Criteria:**

**Given** Validated choice differs from optimistic
**When** Override is applied
**Then** `motion.tally_votes()` is called
**And** Invariant assertion: `ayes + nays + abstains == len(votes)` (P6)
**And** Changed outcome is logged and witnessed

**Technical Notes:**
- P6: Tally recomputation with invariant

---

### Story 4.3: Modify ConclaveService for Async Publishing

As a **Conclave service**,
I want **`_get_archon_vote()` to publish votes for async validation**,
So that **votes are captured optimistically and validated in parallel**.

**Prerequisite:** Vote parser fix (enhanced `_parse_vote()` with FOR/AYE/NAY patterns) must be merged. The regex-based optimistic parsing MUST use the SAME patterns as the fixed parser.

**Acceptance Criteria:**

**Given** `ENABLE_ASYNC_VALIDATION=true` and Kafka healthy
**When** Vote is captured
**Then** Vote is published to `pending-validation` via ValidationDispatcher
**And** Optimistic (regex-parsed) choice is recorded immediately using enhanced `_parse_vote()`
**And** Deliberation continues to next archon without blocking

**Given** Kafka unhealthy (circuit breaker OPEN)
**When** Vote is captured
**Then** Falls back to sync `_validate_vote_consensus()`
**And** Warning logged: `"circuit_breaker_open falling_back_to_sync"`

**Given** Startup health gate failed
**When** Vote is captured
**Then** Sync path is used for entire session
**And** No Kafka publish attempted

**Technical Notes:**
- File: `src/application/services/conclave_service.py` (modify `_get_archon_vote()`)
- Depends on: Story 2.1, 2.2, 2.2.1
- PREREQ: Vote parser fix from `conclave_vote_update.md` spike must be merged

---

### Story 4.4: Modify ConclaveService for Reconciliation Gate

As a **Conclave service**,
I want **`adjourn()` to gate on reconciliation**,
So that **sessions cannot complete with unvalidated votes**.

**Acceptance Criteria:**

**Given** Session is adjourning with async validation enabled
**When** `adjourn()` is called
**Then** `await_all_validations()` is invoked
**And** Vote overrides are applied
**And** Tallies are recomputed
**And** Only then does transcript generation proceed

**Given** Reconciliation fails
**When** `ReconciliationIncompleteError` is raised
**Then** Error is NOT caught (P2)
**And** Session HALTS

**Technical Notes:**
- File: `src/application/services/conclave_service.py` (modify `adjourn()`)
- File: `scripts/run_conclave.py` (wire health check and toggle)

---

## Epic 5: Testing & Hardening

**Goal:** Comprehensive testing of async validation paths including failure scenarios.

### Story 5.1: Integration Tests with Redpanda

As a **developer**,
I want **integration tests using Redpanda testcontainer**,
So that **async validation is tested end-to-end**.

**Acceptance Criteria:**

**Given** Redpanda testcontainer is running
**When** Integration test runs
**Then** Vote publish → validate → reconcile round-trip completes
**And** Consumer lag reaches zero
**And** ReconciliationResult is correct

**Technical Notes:**
- Pattern: testcontainers for Redpanda
- Tests full async pipeline

---

### Story 5.2: Fallback Path Tests

As a **developer**,
I want **tests proving sync fallback activates when Kafka is down**,
So that **resilience is validated**.

**Acceptance Criteria:**

**Given** Kafka health returns unhealthy
**When** Vote is captured
**Then** Sync `_validate_vote_consensus()` is invoked
**And** Warning logged: `"kafka_unhealthy falling_back_to_sync"`
**And** Session completes successfully

**Technical Notes:**
- Mock Kafka health to return unhealthy
- Verify sync path activates

---

### Story 5.3: State Reconstruction Tests

As a **developer**,
I want **tests proving aggregator state reconstruction works**,
So that **aggregator crash/restart is resilient**.

**Acceptance Criteria:**

**Given** Aggregator has in-flight validations
**When** Aggregator is killed and restarted
**Then** State is reconstructed from Kafka replay
**And** Only current session_id messages are processed
**And** Validation continues to completion

**Technical Notes:**
- Kill aggregator mid-session
- Restart and verify state reconstruction
- Verify session_id filtering (V2)

---

## Summary

| Epic | Stories | Priority | Phase |
|------|---------|----------|-------|
| Epic 1: Infrastructure Foundation | 4 | P0 | Phase 1 |
| Epic 2: Async Publishing & Health | 5 | P0 | Phase 1 |
| Epic 3: Validation Workers & Aggregation | 4 | P0 | Phase 2 |
| Epic 4: Reconciliation & Integration | 4 | P0 | Phase 2 |
| Epic 5: Testing & Hardening | 3 | P1 | Phase 3 |

**Total Stories:** 20
**P0 Stories:** 17 (Phase 1: 9, Phase 2: 8)
**P1 Stories:** 3 (Phase 3)

## Phase Deliverables

| Phase | Stories | Outcome |
|-------|---------|---------|
| **Phase 1** | 1.1-1.4, 2.1-2.3, 2.2.1, 2.2.2 | Kafka infra operational, votes publish to Kafka, sync fallback works |
| **Phase 2** | 3.1-3.4, 4.1-4.4 | Full async validation pipeline, reconciliation gate enforced |
| **Phase 3** | 5.1-5.3 | Production hardening, comprehensive test coverage |
