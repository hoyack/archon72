# Conclave Async Vote Validation Architecture

**Spike Document v1.1**
**Date:** 2026-01-23
**Author:** Claude (with Brandon)
**Status:** ✅ IMPLEMENTED

---

## Implementation Status

| Epic | Status | Stories |
|------|--------|---------|
| Epic 1: Infrastructure Foundation | ✅ Complete | 1.1-1.4 |
| Epic 2: Async Publishing & Health | ✅ Complete | 2.1-2.4 |
| Epic 3: Validation Workers & Aggregation | ✅ Complete | 3.1-3.4 |
| Epic 4: Reconciliation & Integration | ✅ Complete | 4.1-4.4 |
| Epic 5: Testing & Hardening | ✅ Complete | 5.1-5.3 |

### Key Components Implemented

| Component | Location | Description |
|-----------|----------|-------------|
| `ValidationDispatcher` | `src/workers/validation_dispatcher.py` | Kafka vote publishing with circuit breaker |
| `ValidatorWorker` | `src/workers/validator_worker.py` | LLM-based vote validation |
| `ConsensusAggregator` | `src/workers/consensus_aggregator.py` | Multi-validator consensus |
| `ReconciliationService` | `src/application/services/reconciliation_service.py` | Vote tracking & DLQ fallback |
| `VoteOverrideService` | `src/application/services/vote_override_service.py` | P6 tally invariant enforcement |
| `ConclaveService` | `src/application/services/conclave_service.py` | Modified for async path |
| `CircuitBreaker` | `src/infrastructure/adapters/kafka/circuit_breaker.py` | CLOSED/OPEN/HALF_OPEN states |

### Pre-mortems Addressed

| ID | Risk | Mitigation | Status |
|----|------|------------|--------|
| P2 | Reconciliation soft-failure | Hard gate with `ReconciliationIncompleteError` | ✅ |
| P4 | Redis SPOF | In-memory state with Kafka replay | ✅ |
| P5 | Witness write silent failure | Constitutional errors propagate | ✅ |
| P6 | Tally invariant violation | `VoteOverrideService` enforces sum = total | ✅ |
| V1 | DLQ fallback unwitnessed | All DLQ fallbacks are witnessed | ✅ |
| V2 | Stale message replay | Session-bounded filtering via session_id header | ✅ |
| R3 | Consumer lag at adjournment | Reconciliation gate waits for lag = 0 | ✅ |
| Round 7 | Split-brain validators | Per-validator keying for partition isolation | ✅ |

### Test Coverage

| Test Suite | Location | Coverage |
|------------|----------|----------|
| Integration (Redpanda) | `tests/integration/test_async_vote_validation.py` | Full round-trip, DLQ, overrides |
| Fallback Paths | `tests/unit/application/services/test_conclave_fallback.py` | Circuit breaker, sync fallback |
| State Reconstruction | `tests/unit/workers/test_aggregator_reconstruction.py` | P4 replay, V2 filtering, idempotency |

---

## Executive Summary

This document proposes an asynchronous vote validation architecture for the Archon 72 Conclave system. The current synchronous dual-LLM validation blocks the deliberation pipeline, adding ~9,216 LLM calls that execute sequentially. By moving validation to an async queue, we decouple vote capture from validation, allowing deliberation to proceed at full speed while validation runs in parallel.

**Key Decision:** Use **Apache Kafka** over RabbitMQ for its immutable audit trail, event replay capability, and alignment with the Conclave's governance transparency requirements.

---

## Table of Contents

1. [Current State & Problems](#1-current-state--problems)
2. [Async Architecture Proposal](#2-async-architecture-proposal)
3. [Technology Choice: Kafka](#3-technology-choice-kafka)
4. [Topic & Schema Design](#4-topic--schema-design)
5. [Producer/Consumer Architecture](#5-producerconsumer-architecture)
6. [Reconciliation Flow](#6-reconciliation-flow)
7. [AGI Readiness Considerations](#7-agi-readiness-considerations)
8. [Implementation Plan](#8-implementation-plan)
9. [Environment Configuration](#9-environment-configuration)
10. [Appendix: Archon IDs for Validators](#appendix-archon-ids-for-validators)

---

## 1. Current State & Problems

### 1.1 What Was Fixed

The original vote parser used substring matching that didn't recognize King archon vote formats:

```python
# OLD: Failed on "Vote: FOR" (Kings use this format per system_prompt)
if "vote aye" in content_lower:
    return VoteChoice.AYE
```

**Result:** 87.3% mismatch rate for executive_director votes (503/576 votes misparsed as ABSTAIN).

### 1.2 Parser Fix Applied

Enhanced `_parse_vote()` in `src/application/services/conclave_service.py` to accept:
- `Vote: FOR|NAY|ABSTAIN` (King system_prompt format)
- `I VOTE AYE|NAY` / `I ABSTAIN` (Conclave prompt format)
- Bare tokens with markdown stripping

### 1.3 Dual Validation Added (Synchronous)

Two LLM validators (Furcas + Secretary Text) must reach consensus on each vote:

```
WITNESS_ARCHON_ID=1b872789-7990-4163-b54b-6bc45746e2f6  # Furcas (Knight-Witness)
SECRETARY_TEXT_ARCHON_ID=43d83b84-243b-49ae-9ff4-c3f510db9982  # Orias
```

### 1.4 The Problem: Blocking Pipeline

| Metric | Value |
|--------|-------|
| Archons | 72 |
| Motions (typical) | 64 |
| Validators per vote | 2 |
| Max retry attempts | 3 |
| **Total validation calls** | **9,216 - 27,648** |
| Avg LLM latency | 2-15s |
| **Added pipeline time** | **5-115 hours** |

This is unacceptable. Validation must be decoupled from the critical path.

---

## 2. Async Architecture Proposal

### 2.1 Core Principle: Optimistic Voting with Deferred Validation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DELIBERATION PIPELINE                           │
│                         (Critical Path - Unblocked)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │  Archon  │───▶│  Parse   │───▶│ Optimistic│───▶│ Continue to Next │  │
│  │  Votes   │    │  (Regex) │    │   Vote   │    │     Archon       │  │
│  └──────────┘    └────┬─────┘    └──────────┘    └──────────────────┘  │
│                       │                                                 │
│                       │ Publish                                         │
│                       ▼                                                 │
└───────────────────────┬─────────────────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────────────────┐
│                         KAFKA EVENT STREAM                              │
│                         (Async Validation)                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐ │
│  │ pending-        │───▶│ Validator       │───▶│ validation-results  │ │
│  │ validation      │    │ Workers (2+)    │    │                     │ │
│  └─────────────────┘    └─────────────────┘    └──────────┬──────────┘ │
│                                                           │            │
│                                                           ▼            │
│                         ┌─────────────────────────────────────────┐    │
│                         │ Consensus Aggregator                    │    │
│                         │ - Wait for both validators              │    │
│                         │ - Determine agreement                   │    │
│                         │ - Retry on disagreement                 │    │
│                         └──────────────────┬──────────────────────┘    │
│                                            │                           │
│                    ┌───────────────────────┼───────────────────────┐   │
│                    ▼                       ▼                       ▼   │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐│
│  │ validated-votes     │  │ non-consensus       │  │ witness-events   ││
│  │ (consensus reached) │  │ (retry exhausted)   │  │ (audit trail)    ││
│  └─────────────────────┘  └─────────────────────┘  └──────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                        │
                        │ Reconciliation Gate
                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FINALIZATION PHASE                              │
│                         (Blocks only at end)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │ Wait for all     │───▶│ Apply overrides  │───▶│ Generate final   │  │
│  │ validations      │    │ if validated ≠   │    │ transcript &     │  │
│  │ to complete      │    │ optimistic       │    │ checkpoint       │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Behaviors

| Phase | Blocking? | Description |
|-------|-----------|-------------|
| Vote capture | No | Parse immediately, publish to Kafka, continue |
| Validation | No | Workers process async, results accumulate |
| Deliberation rounds | No | Uses optimistic votes, validation catches up |
| Session adjournment | **Yes** | Wait for validation queue to drain |
| Transcript generation | **Yes** | Apply any vote overrides before finalizing |

### 2.3 Queue Clearing Strategy

Validation queue naturally clears during:
- **Debate rounds**: 72 archons × ~15s = ~18 min per round
- **Between motions**: Procedural overhead, seconding, etc.
- **Inter-phase transitions**: Roll call, call to order, etc.

By the time the session reaches adjournment, most validations will have completed. Final gate ensures 100% completion before output.

---

## 3. Technology Choice: Kafka

### 3.1 Why Kafka Over RabbitMQ

| Requirement | Kafka | RabbitMQ |
|-------------|-------|----------|
| **Immutable audit trail** | ✅ Native (log-based) | ❌ Messages deleted after ack |
| **Event replay** | ✅ Configurable retention | ❌ Not designed for replay |
| **Governance transparency** | ✅ Complete history | ❌ Point-in-time only |
| **Horizontal scaling** | ✅ Partition-based | ⚠️ Queue-based (limited) |
| **Consumer groups** | ✅ Native | ⚠️ Requires plugins |
| **Event sourcing** | ✅ First-class pattern | ❌ Not idiomatic |
| **AGI-ready** | ✅ Handles massive throughput | ⚠️ Bottlenecks at scale |

### 3.2 Kafka Alignment with Conclave Principles

The Conclave governance model emphasizes:
- **Witness Layer**: All actions must be observed and recorded
- **Transparency**: Nothing should be hidden or deletable
- **Audit Trail**: Immutable record of all decisions

Kafka's append-only log is philosophically aligned with these principles. Every vote, validation attempt, consensus decision, and override is permanently recorded.

### 3.3 Deployment Options

| Option | Pros | Cons |
|--------|------|------|
| **Self-hosted Kafka** | Full control, local to Ollama cluster | Ops overhead |
| **Confluent Cloud** | Managed, scalable | External dependency, cost |
| **Redpanda** | Kafka-compatible, simpler ops | Less ecosystem maturity |
| **Amazon MSK** | AWS-managed | Cloud lock-in |

**Recommendation:** Start with **Redpanda** for local development (single binary, Kafka-compatible), migrate to Confluent or self-hosted Kafka for production.

---

## 4. Topic & Schema Design

### 4.1 Topic Taxonomy

```
conclave.                           # Namespace
├── votes.
│   ├── pending-validation          # Raw votes awaiting validation
│   ├── validation-requests         # Individual validator task assignments
│   ├── validation-results          # Validator responses
│   ├── validated                   # Final consensus results
│   └── overrides                   # Corrections applied to optimistic votes
├── consensus.
│   ├── attempts                    # Retry tracking
│   └── failures                    # Non-consensus events
├── witness.
│   ├── events                      # All witnessed events (KnightWitness)
│   └── statements                  # Published witness statements
└── sessions.
    ├── state                       # Session checkpoints
    └── transcripts                 # Final transcripts (compacted)
```

### 4.2 Message Schemas (Avro)

#### `conclave.votes.pending-validation`

```json
{
  "type": "record",
  "name": "PendingVoteValidation",
  "namespace": "io.archon72.conclave.votes",
  "fields": [
    {"name": "vote_id", "type": "string", "doc": "UUID of the vote"},
    {"name": "session_id", "type": "string"},
    {"name": "motion_id", "type": "string"},
    {"name": "archon_id", "type": "string", "doc": "Voter archon ID"},
    {"name": "archon_name", "type": "string"},
    {"name": "aegis_rank", "type": "string"},
    {"name": "motion_title", "type": "string"},
    {"name": "motion_text", "type": "string"},
    {"name": "raw_vote_content", "type": "string", "doc": "Full LLM response"},
    {"name": "optimistic_choice", "type": {"type": "enum", "name": "VoteChoice", "symbols": ["AYE", "NAY", "ABSTAIN"]}},
    {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"},
    {"name": "validator_ids", "type": {"type": "array", "items": "string"}}
  ]
}
```

#### `conclave.votes.validation-results`

```json
{
  "type": "record",
  "name": "ValidationResult",
  "namespace": "io.archon72.conclave.votes",
  "fields": [
    {"name": "vote_id", "type": "string"},
    {"name": "validator_id", "type": "string"},
    {"name": "validator_name", "type": "string"},
    {"name": "attempt", "type": "int"},
    {"name": "validated_choice", "type": ["null", "VoteChoice"], "default": null},
    {"name": "raw_response", "type": "string"},
    {"name": "parse_success", "type": "boolean"},
    {"name": "latency_ms", "type": "long"},
    {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"},
    {"name": "error", "type": ["null", "string"], "default": null}
  ]
}
```

#### `conclave.votes.validated`

```json
{
  "type": "record",
  "name": "ValidatedVote",
  "namespace": "io.archon72.conclave.votes",
  "fields": [
    {"name": "vote_id", "type": "string"},
    {"name": "session_id", "type": "string"},
    {"name": "motion_id", "type": "string"},
    {"name": "archon_id", "type": "string"},
    {"name": "optimistic_choice", "type": "VoteChoice"},
    {"name": "validated_choice", "type": "VoteChoice"},
    {"name": "consensus_reached", "type": "boolean"},
    {"name": "attempts_required", "type": "int"},
    {"name": "override_required", "type": "boolean", "doc": "True if validated != optimistic"},
    {"name": "validator_agreement", "type": {"type": "map", "values": "VoteChoice"}},
    {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"}
  ]
}
```

### 4.3 Partitioning Strategy

| Topic | Partition Key | Rationale |
|-------|---------------|-----------|
| `pending-validation` | `motion_id` | Votes for same motion processed together |
| `validation-requests` | `validator_id` | Each validator has dedicated partition |
| `validation-results` | `vote_id` | Results for same vote colocated |
| `validated` | `session_id` | Session-level aggregation |
| `witness.events` | `session_id` | Chronological per-session ordering |

---

## 5. Producer/Consumer Architecture

### 5.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONCLAVE SERVICE                                │
│                         (Producer)                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ConclaveService._collect_vote()                                        │
│      │                                                                  │
│      ├──▶ _parse_vote() ──▶ optimistic_choice                          │
│      │                                                                  │
│      └──▶ _publish_for_validation()                                    │
│               │                                                         │
│               └──▶ KafkaProducer.send("conclave.votes.pending-validation")
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         VALIDATION DISPATCHER                           │
│                         (Consumer + Producer)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Consumer Group: validation-dispatcher                                  │
│  Consumes: conclave.votes.pending-validation                           │
│  Produces: conclave.votes.validation-requests                          │
│                                                                         │
│  Logic:                                                                 │
│    for each pending vote:                                               │
│      for each validator_id in vote.validator_ids:                       │
│        publish ValidationRequest to validation-requests                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         VALIDATOR WORKER POOL                           │
│                         (Consumer + Producer)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Consumer Group: validator-workers                                      │
│  Consumes: conclave.votes.validation-requests                          │
│  Produces: conclave.votes.validation-results                           │
│                                                                         │
│  Worker per validator_id:                                               │
│    - Invoke LLM via orchestrator.invoke(validator_id, context)         │
│    - Parse JSON response                                                │
│    - Publish ValidationResult                                           │
│                                                                         │
│  Scaling: N workers per validator (horizontal)                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         CONSENSUS AGGREGATOR                            │
│                         (Consumer + Producer)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Consumer Group: consensus-aggregator                                   │
│  Consumes: conclave.votes.validation-results                           │
│  Produces:                                                              │
│    - conclave.votes.validated (on consensus)                           │
│    - conclave.votes.validation-requests (on retry)                     │
│    - conclave.consensus.failures (on exhausted retries)                │
│    - conclave.witness.events (all outcomes)                            │
│                                                                         │
│  State Store: RocksDB (Kafka Streams) or Redis                         │
│    - Tracks pending validations per vote_id                            │
│    - Tracks attempt count                                               │
│                                                                         │
│  Logic:                                                                 │
│    on ValidationResult:                                                 │
│      accumulate in state store                                          │
│      if all validators responded:                                       │
│        if unanimous:                                                    │
│          publish ValidatedVote                                          │
│        else if attempts < max:                                          │
│          republish ValidationRequests (retry)                          │
│        else:                                                            │
│          publish ConsensusFailure                                       │
│          publish WitnessEvent                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         RECONCILIATION SERVICE                          │
│                         (Consumer)                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Consumer Group: reconciliation-service                                 │
│  Consumes:                                                              │
│    - conclave.votes.validated                                          │
│    - conclave.consensus.failures                                       │
│                                                                         │
│  State Store: Session vote cache (Redis or in-memory)                  │
│                                                                         │
│  Logic:                                                                 │
│    on ValidatedVote:                                                    │
│      if override_required:                                              │
│        update session vote in cache                                     │
│        publish to conclave.votes.overrides                             │
│                                                                         │
│    on ConsensusFailure:                                                 │
│      mark vote as ABSTAIN with validation_failed reason                │
│      publish WitnessEvent                                               │
│                                                                         │
│  API:                                                                   │
│    await_all_validations(session_id) -> blocks until queue drained     │
│    get_overrides(session_id) -> returns vote corrections               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Worker Scaling

```yaml
# Kubernetes HPA example
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: validator-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: validator-worker
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: External
    external:
      metric:
        name: kafka_consumer_lag
        selector:
          matchLabels:
            topic: conclave.votes.validation-requests
      target:
        type: AverageValue
        averageValue: "100"  # Scale up if lag > 100 messages
```

### 5.3 Backpressure Handling

If validation can't keep up:
1. Consumer lag increases (monitored via Kafka metrics)
2. HPA scales validator workers
3. If still overwhelmed, circuit breaker pauses new validations
4. Optimistic votes continue (fallback to regex-parsed values)
5. Validation resumes when capacity recovers

---

## 6. Reconciliation Flow

### 6.1 Session Lifecycle with Async Validation

```
Session Start
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: Call to Order                                                    │
│ Validation queue: empty                                                 │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: Roll Call                                                        │
│ Validation queue: empty                                                 │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: New Business (Motion 1)                                          │
│                                                                         │
│   Debate Round 1: 72 archons speak (~18 min)                           │
│       └─▶ Validation queue: 0 votes (no voting yet)                    │
│                                                                         │
│   Debate Round 2: 72 archons speak (~18 min)                           │
│       └─▶ Validation queue: 0 votes                                    │
│                                                                         │
│   Debate Round 3: 72 archons speak (~18 min)                           │
│       └─▶ Validation queue: 0 votes                                    │
│                                                                         │
│   Voting: 72 archons vote (~5 min)                                     │
│       └─▶ Validation queue: 72 votes published                         │
│       └─▶ Validators processing in background                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: New Business (Motion 2)                                          │
│                                                                         │
│   Debate Round 1: 72 archons speak (~18 min)                           │
│       └─▶ Validation queue: ~30 votes remaining from Motion 1          │
│       └─▶ By end of round: ~0 remaining (cleared!)                     │
│                                                                         │
│   ... (continues for all motions)                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: Adjournment (BLOCKING GATE)                                      │
│                                                                         │
│   1. Signal no more votes incoming                                      │
│   2. await reconciliation_service.await_all_validations(session_id)    │
│   3. Apply any overrides to session votes                              │
│   4. Generate final transcript                                          │
│   5. Publish session complete event                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Session End
```

### 6.2 Override Application

```python
async def apply_validation_overrides(self, session: ConclaveSession) -> int:
    """Apply validated vote corrections before finalizing session.
    
    Returns:
        Number of votes overridden.
    """
    overrides = await self._reconciliation_service.get_overrides(session.session_id)
    override_count = 0
    
    for override in overrides:
        motion = session.get_motion(override.motion_id)
        if not motion:
            continue
            
        original_vote = motion.get_vote(override.archon_id)
        if not original_vote:
            continue
            
        if original_vote.choice != override.validated_choice:
            # Record the correction
            session.add_transcript_entry(
                entry_type="procedural",
                content=(
                    f"Vote correction: {override.archon_name}'s vote on "
                    f"'{motion.title}' validated as {override.validated_choice.value} "
                    f"(originally parsed as {original_vote.choice.value})"
                ),
                speaker_id="system",
                speaker_name="Validation System",
                metadata={
                    "event": "vote_override",
                    "motion_id": str(motion.motion_id),
                    "archon_id": override.archon_id,
                    "original": original_vote.choice.value,
                    "validated": override.validated_choice.value,
                },
            )
            
            # Apply the correction
            original_vote.choice = override.validated_choice
            original_vote.reasoning += f"\n\n[Validated: {override.validated_choice.value}]"
            override_count += 1
    
    return override_count
```

### 6.3 Tally Recomputation

After overrides are applied, recompute affected motion tallies:

```python
def recompute_motion_results(self, motion: Motion) -> bool:
    """Recompute motion pass/fail after vote overrides.
    
    Returns:
        True if result changed, False otherwise.
    """
    original_passed = motion.passed
    
    ayes = sum(1 for v in motion.votes if v.choice == VoteChoice.AYE)
    nays = sum(1 for v in motion.votes if v.choice == VoteChoice.NAY)
    
    # Supermajority threshold (abstentions excluded from denominator)
    total_votes = ayes + nays
    if total_votes == 0:
        motion.passed = False
    else:
        ratio = ayes / total_votes
        motion.passed = ratio >= self._config.supermajority_threshold
    
    return motion.passed != original_passed
```

---

## 7. AGI Readiness Considerations

### 7.1 What "AGI Ready" Means for This System

| Dimension | Current Scale | AGI Scale | Design Implication |
|-----------|--------------|-----------|-------------------|
| Archons | 72 | 10,000+ | Partition by archon cohorts |
| Concurrent sessions | 1 | 1,000+ | Session-level isolation |
| Votes per second | ~1 | ~10,000 | Horizontal worker scaling |
| Validators | 2 | N (configurable) | Pluggable validator registry |
| Consensus algorithm | Unanimous | Quorum-based | Configurable threshold |
| Audit retention | 30 days | Permanent | Tiered storage (hot/cold) |

### 7.2 Architectural Principles

#### 7.2.1 Event Sourcing as Foundation

Every state change is an event. Current state is derived by replaying events.

```
Vote cast → PendingVoteValidation event
Validation result → ValidationResult event
Consensus reached → ValidatedVote event
Override applied → VoteOverride event
```

Benefits:
- Complete audit trail (regulatory compliance)
- Time-travel debugging (replay to any point)
- Multi-consumer processing (analytics, ML training, etc.)

#### 7.2.2 Schema Evolution

Use Avro with Schema Registry for forward/backward compatibility:

```json
{
  "type": "record",
  "name": "ValidatedVote",
  "fields": [
    // ... existing fields ...
    
    // New field with default (backward compatible)
    {"name": "confidence_score", "type": ["null", "float"], "default": null},
    
    // Deprecated field (forward compatible)
    {"name": "legacy_field", "type": ["null", "string"], "default": null, "deprecated": true}
  ]
}
```

#### 7.2.3 Multi-Tenancy

Prepare for multiple organizations running Conclaves:

```
conclave.{tenant_id}.votes.pending-validation
conclave.{tenant_id}.votes.validated
conclave.{tenant_id}.witness.events
```

Or use headers for tenant routing with shared topics.

#### 7.2.4 Pluggable Validators

Current: Hardcoded 2 validators (Furcas + Orias)
Future: Validator registry with dynamic assignment

```python
class ValidatorRegistry:
    """Registry of available vote validators."""
    
    async def get_validators(
        self,
        motion_type: MotionType,
        archon_rank: str,
    ) -> list[ValidatorConfig]:
        """Get validators appropriate for this vote context.
        
        Higher-stakes votes (e.g., constitutional motions, executive votes)
        may require more validators or specific validator combinations.
        """
        if motion_type == MotionType.CONSTITUTIONAL:
            return self._get_constitutional_validators()
        elif archon_rank == "executive_director":
            return self._get_executive_validators()
        else:
            return self._get_default_validators()
```

#### 7.2.5 Consensus Algorithm Abstraction

Current: Unanimous agreement required
Future: Configurable quorum

```python
class ConsensusStrategy(Protocol):
    """Strategy for determining consensus among validators."""
    
    def evaluate(
        self,
        results: list[ValidationResult],
        expected_count: int,
    ) -> ConsensusOutcome:
        """Evaluate whether consensus has been reached."""
        ...

class UnanimousConsensus(ConsensusStrategy):
    """All validators must agree."""
    
    def evaluate(self, results, expected_count):
        if len(results) < expected_count:
            return ConsensusOutcome.PENDING
        choices = {r.validated_choice for r in results if r.validated_choice}
        if len(choices) == 1:
            return ConsensusOutcome.REACHED
        return ConsensusOutcome.DISAGREEMENT

class MajorityConsensus(ConsensusStrategy):
    """Majority of validators must agree."""
    
    def evaluate(self, results, expected_count):
        if len(results) < expected_count:
            return ConsensusOutcome.PENDING
        from collections import Counter
        choices = [r.validated_choice for r in results if r.validated_choice]
        most_common, count = Counter(choices).most_common(1)[0]
        if count > len(results) / 2:
            return ConsensusOutcome.REACHED
        return ConsensusOutcome.DISAGREEMENT

class SupermajorityConsensus(ConsensusStrategy):
    """2/3 of validators must agree."""
    # ... implementation
```

### 7.3 Observability for AGI Scale

```yaml
# Prometheus metrics to expose
conclave_votes_pending_validation_total: Counter
conclave_votes_validated_total: Counter{consensus: "reached|failed"}
conclave_validation_latency_seconds: Histogram{validator_id}
conclave_validation_attempts: Histogram{outcome: "success|retry|failure"}
conclave_consensus_disagreement_total: Counter{validator_pair}
conclave_override_total: Counter{original_choice, validated_choice}
conclave_reconciliation_queue_depth: Gauge{session_id}
```

---

## 8. Implementation Plan

### 8.1 Phase 1: Infrastructure Setup (Week 1)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Deploy Redpanda (local dev) | Infra | docker-compose.yml |
| Create Kafka topics | Infra | Topic creation scripts |
| Schema Registry setup | Infra | Avro schemas registered |
| Add kafka-python to deps | Dev | pyproject.toml update |

### 8.2 Phase 2: Producer Integration (Week 2)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Create KafkaVotePublisher | Dev | `src/infrastructure/adapters/kafka/vote_publisher.py` |
| Modify `_collect_vote()` | Dev | Publish after parse |
| Add publish toggle (env var) | Dev | `ENABLE_ASYNC_VALIDATION=true` |
| Unit tests | Dev | Publisher tests |

### 8.3 Phase 3: Consumer Workers (Week 3)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Validation dispatcher | Dev | `src/workers/validation_dispatcher.py` |
| Validator worker | Dev | `src/workers/validator_worker.py` |
| Consensus aggregator | Dev | `src/workers/consensus_aggregator.py` |
| Worker entrypoints | Dev | CLI commands to run workers |

### 8.4 Phase 4: Reconciliation (Week 4)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Reconciliation service | Dev | `src/application/services/reconciliation_service.py` |
| Session finalization gate | Dev | `await_all_validations()` |
| Override application | Dev | Vote correction logic |
| Integration tests | Dev | End-to-end validation flow |

### 8.5 Phase 5: Production Hardening (Week 5-6)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Kubernetes manifests | Infra | Worker deployments |
| HPA configuration | Infra | Auto-scaling |
| Prometheus metrics | Dev | Observability |
| Alerting rules | Infra | PagerDuty integration |
| Load testing | QA | Performance benchmarks |
| Documentation | Dev | Runbook |

---

## 9. Environment Configuration

### 9.1 New Environment Variables

```bash
# .env additions

# ============================================================
# ASYNC VOTE VALIDATION (Kafka)
# ============================================================

# Enable async validation (default: false for backward compatibility)
ENABLE_ASYNC_VALIDATION=true

# Kafka bootstrap servers
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Schema Registry URL (for Avro)
SCHEMA_REGISTRY_URL=http://localhost:8081

# Topic prefix (for multi-tenancy)
KAFKA_TOPIC_PREFIX=conclave

# Consumer group prefix
KAFKA_CONSUMER_GROUP_PREFIX=archon72

# ============================================================
# VALIDATOR CONFIGURATION
# ============================================================

# Primary validator (Knight-Witness)
WITNESS_ARCHON_ID=1b872789-7990-4163-b54b-6bc45746e2f6

# Secondary validator (Secretary Text - Orias)
SECRETARY_TEXT_ARCHON_ID=43d83b84-243b-49ae-9ff4-c3f510db9982

# Max validation attempts before marking as non-consensus
VOTE_VALIDATION_MAX_ATTEMPTS=3

# Validation timeout per attempt (seconds)
VOTE_VALIDATION_TIMEOUT=30

# ============================================================
# RECONCILIATION
# ============================================================

# Max time to wait for validation queue to drain at session end (seconds)
RECONCILIATION_TIMEOUT=300

# Redis URL for reconciliation state (optional, uses in-memory if not set)
RECONCILIATION_REDIS_URL=redis://localhost:6379/0
```

### 9.2 Docker Compose Addition

```yaml
# docker-compose.yml additions

services:
  redpanda:
    image: redpandadata/redpanda:v23.3.5
    container_name: redpanda
    command:
      - redpanda
      - start
      - --smp=1
      - --memory=1G
      - --overprovisioned
      - --kafka-addr=internal://0.0.0.0:9092,external://0.0.0.0:19092
      - --advertise-kafka-addr=internal://redpanda:9092,external://localhost:19092
      - --pandaproxy-addr=internal://0.0.0.0:8082,external://0.0.0.0:18082
      - --advertise-pandaproxy-addr=internal://redpanda:8082,external://localhost:18082
      - --schema-registry-addr=internal://0.0.0.0:8081,external://0.0.0.0:18081
    ports:
      - "18081:18081"  # Schema Registry
      - "18082:18082"  # Pandaproxy
      - "19092:19092"  # Kafka
      - "9644:9644"    # Admin API
    volumes:
      - redpanda-data:/var/lib/redpanda/data
    healthcheck:
      test: ["CMD", "rpk", "cluster", "health"]
      interval: 10s
      timeout: 5s
      retries: 5

  redpanda-console:
    image: redpandadata/console:v2.3.8
    container_name: redpanda-console
    depends_on:
      redpanda:
        condition: service_healthy
    ports:
      - "8080:8080"
    environment:
      KAFKA_BROKERS: redpanda:9092
      SCHEMA_REGISTRY_URL: http://redpanda:8081

  validation-dispatcher:
    build:
      context: .
      dockerfile: Dockerfile.worker
    command: python -m src.workers.validation_dispatcher
    depends_on:
      redpanda:
        condition: service_healthy
    environment:
      KAFKA_BOOTSTRAP_SERVERS: redpanda:9092
      SCHEMA_REGISTRY_URL: http://redpanda:8081
    deploy:
      replicas: 1

  validator-worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    command: python -m src.workers.validator_worker
    depends_on:
      redpanda:
        condition: service_healthy
    environment:
      KAFKA_BOOTSTRAP_SERVERS: redpanda:9092
      SCHEMA_REGISTRY_URL: http://redpanda:8081
      OLLAMA_HOST: ${OLLAMA_HOST}
    deploy:
      replicas: 4  # Scale based on load

  consensus-aggregator:
    build:
      context: .
      dockerfile: Dockerfile.worker
    command: python -m src.workers.consensus_aggregator
    depends_on:
      redpanda:
        condition: service_healthy
    environment:
      KAFKA_BOOTSTRAP_SERVERS: redpanda:9092
      SCHEMA_REGISTRY_URL: http://redpanda:8081
    deploy:
      replicas: 2

volumes:
  redpanda-data:
```

---

## Appendix: Archon IDs for Validators

### Current Validator Configuration

| Role | Archon | UUID | Rationale |
|------|--------|------|-----------|
| **Primary Validator** | Furcas | `1b872789-7990-4163-b54b-6bc45746e2f6` | Knight-Witness branch; constitutional role is to observe and record without participating in governance |
| **Secondary Validator** | Orias | `43d83b84-243b-49ae-9ff4-c3f510db9982` | Marquis of Status & Recognition Building; advisory branch with wisdom/transformation focus |

### Validator Selection Criteria

Ideal validators should:
1. **Not be voters** (avoid self-validation conflicts) — Furcas is in `witness` branch, cannot vote
2. **Have analytical/judicial disposition** — Both have "wise" personality traits
3. **Use different LLM providers** (if possible) — Diversity reduces correlated errors
4. **Have appropriate governance permissions** — Neither has `ratify` permission

### Alternative Validator Candidates

| Archon | Branch | Personality | UUID | Notes |
|--------|--------|-------------|------|-------|
| Vassago | judicial | Good, Benevolent | `83e07040-c1e2-462d-8844-3a793ae7eb8d` | Prince of Discovery & Revelation |
| Orobas | judicial | Faithful, Truthful | `71f9ad05-acb2-46d8-a391-88d86ac55ec8` | Prince of Divination & Loyalty; "never deceives" |
| Botis | judicial | Wise, Reconciling | `89cc33b8-cf98-46d0-8f6f-132e4826e1b6` | Prince of Reconciliation |

**Note:** Judicial branch archons can deliberate and ratify, so using them as validators creates a conflict. Furcas (witness branch) is the cleanest choice for primary validator.

---

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Claude | Initial spike document |
| 1.1 | 2026-01-23 | Claude | Updated status to IMPLEMENTED, added implementation summary |

---

*End of Document*