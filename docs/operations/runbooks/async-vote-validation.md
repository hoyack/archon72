# Async Vote Validation Operations Runbook

**Version:** 1.0
**Date:** 2026-01-23
**Status:** Production Ready

---

## Overview

The Async Vote Validation system decouples vote capture from validation in the Conclave deliberation pipeline. Votes are parsed optimistically (regex) and continue immediately while LLM-based validation runs asynchronously via Kafka.

### Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DELIBERATION PIPELINE                           │
│                         (Critical Path - Unblocked)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  Archon Votes → Parse (Regex) → Optimistic Vote → Continue Next        │
│                       │                                                 │
│                       │ Publish to Kafka                               │
│                       ▼                                                 │
└───────────────────────┬─────────────────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────────────────┐
│                         KAFKA EVENT STREAM                              │
├─────────────────────────────────────────────────────────────────────────┤
│  pending-validation → Validator Workers → validation-results           │
│                              │                                          │
│                              ▼                                          │
│                    Consensus Aggregator                                 │
│                              │                                          │
│              ┌───────────────┼───────────────┐                         │
│              ▼               ▼               ▼                         │
│        validated        dead-letter    witness-events                  │
└─────────────────────────────────────────────────────────────────────────┘
                        │
                        │ Reconciliation Gate (P2)
                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FINALIZATION PHASE                              │
│  Wait for validations → Apply overrides → Generate transcript          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. ValidationDispatcher

**Location:** `src/workers/validation_dispatcher.py`

**Function:** Publishes votes to Kafka for async validation with circuit breaker protection.

**Key Behaviors:**
- Circuit breaker prevents cascade failures
- Falls back to sync validation when OPEN
- Per-validator keying for partition isolation (Round 7)

### 2. ValidatorWorker

**Location:** `src/workers/validator_worker.py`

**Function:** Consumes validation requests, invokes LLM validators, publishes results.

**Scaling:**
- Horizontally scalable via Kubernetes replicas
- Scale based on `kafka_consumer_lag` metric
- Recommended: 2-4 workers per validator

### 3. ConsensusAggregator

**Location:** `src/workers/consensus_aggregator.py`

**Function:** Aggregates validation results, determines consensus, handles retries.

**Key Behaviors:**
- Tracks pending validations per vote_id
- Retries up to `max_attempts` on disagreement
- Publishes to dead-letter on exhausted retries
- Session-bounded filtering (V2)
- Idempotent replay support (P4)

### 4. ReconciliationService

**Location:** `src/application/services/reconciliation_service.py`

**Function:** Tracks vote validation status, provides reconciliation gate.

**Key Methods:**
- `register_vote()` - Track new vote
- `mark_validated()` - Record validation result
- `mark_dlq()` - Record DLQ fallback
- `await_all_validations()` - Block until complete (P2)
- `apply_dlq_fallbacks()` - Apply optimistic values (V1)

### 5. VoteOverrideService

**Location:** `src/application/services/vote_override_service.py`

**Function:** Applies validated choices when different from optimistic, enforces P6.

**P6 Invariant:** `ayes + nays + abstains == total_votes`

---

## Environment Variables

```bash
# Enable async validation (default: false)
ENABLE_ASYNC_VALIDATION=true

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:19092
SCHEMA_REGISTRY_URL=http://localhost:18081

# Validator archon IDs
WITNESS_ARCHON_ID=1b872789-7990-4163-b54b-6bc45746e2f6
SECRETARY_TEXT_ARCHON_ID=43d83b84-243b-49ae-9ff4-c3f510db9982

# Validation settings
VOTE_VALIDATION_MAX_ATTEMPTS=3
VOTE_VALIDATION_TIMEOUT=30

# Reconciliation
RECONCILIATION_TIMEOUT=300
```

---

## Kafka Topics

| Topic | Purpose | Partition Key |
|-------|---------|---------------|
| `conclave.votes.pending-validation` | Raw votes awaiting validation | `motion_id` |
| `conclave.votes.validation-requests` | Individual validator assignments | `validator_id` |
| `conclave.votes.validation-results` | Validator responses | `vote_id` |
| `conclave.votes.validated` | Final consensus results | `session_id` |
| `conclave.votes.dead-letter` | Failed validations | `vote_id` |

---

## Monitoring

### Key Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `conclave_votes_pending_validation_total` | Counter | Votes awaiting validation | N/A |
| `conclave_votes_validated_total` | Counter | Successfully validated votes | N/A |
| `conclave_validation_latency_seconds` | Histogram | Validation latency | p99 > 30s |
| `conclave_consensus_disagreement_total` | Counter | Validator disagreements | > 10/min |
| `conclave_override_total` | Counter | Vote overrides applied | > 5% of votes |
| `conclave_reconciliation_queue_depth` | Gauge | Pending validations | > 100 at adjournment |
| `conclave_circuit_breaker_state` | Gauge | Circuit breaker status | OPEN for > 5 min |

### Health Checks

```bash
# Check Kafka connectivity
curl http://localhost:8000/health/kafka

# Check validation pipeline
curl http://localhost:8000/health/validation

# Check reconciliation status
curl http://localhost:8000/v1/conclave/sessions/{session_id}/reconciliation
```

---

## Operational Procedures

### Starting Async Validation

1. Ensure Kafka/Redpanda is running:
   ```bash
   docker-compose up -d redpanda
   ```

2. Create required topics:
   ```bash
   make kafka-topics
   ```

3. Start workers:
   ```bash
   make workers-start
   ```

4. Enable in ConclaveService:
   ```bash
   export ENABLE_ASYNC_VALIDATION=true
   ```

### Stopping Async Validation

1. Disable new async validations:
   ```bash
   export ENABLE_ASYNC_VALIDATION=false
   ```

2. Wait for queue to drain:
   ```bash
   make kafka-lag-check
   ```

3. Stop workers:
   ```bash
   make workers-stop
   ```

### Circuit Breaker Recovery

When circuit breaker is OPEN:

1. Check Kafka health:
   ```bash
   rpk cluster health
   ```

2. Check consumer lag:
   ```bash
   rpk group describe validation-workers
   ```

3. If Kafka is healthy, circuit will auto-recover after `reset_timeout` (default: 30s)

4. If Kafka is down, system automatically falls back to sync validation

### Handling DLQ Votes

DLQ votes use optimistic (regex-parsed) values with witnessing:

1. Review DLQ entries:
   ```bash
   rpk topic consume conclave.votes.dead-letter --num 10
   ```

2. DLQ fallbacks are automatically witnessed per V1 requirement

3. No manual intervention required unless pattern detected

### Reconciliation Gate Timeout

If reconciliation times out (P2):

1. Check consumer lag:
   ```bash
   rpk group describe consensus-aggregator
   ```

2. Scale workers if needed:
   ```bash
   kubectl scale deployment validator-worker --replicas=8
   ```

3. The system will raise `ReconciliationIncompleteError` (never silently passes)

4. Session cannot complete until all validations finish

---

## Troubleshooting

### High Consumer Lag

**Symptoms:** Lag increasing, validations slow

**Resolution:**
1. Scale validator workers
2. Check LLM endpoint health
3. Review validation timeout settings

### Frequent Circuit Breaker Trips

**Symptoms:** Falling back to sync often

**Resolution:**
1. Check Kafka broker health
2. Review network connectivity
3. Adjust `failure_threshold` if false positives

### P6 Invariant Violations

**Symptoms:** `TallyInvariantError` raised

**Resolution:**
1. This should never happen in normal operation
2. Check for concurrent modifications to motion state
3. Review override application order

### Session Stuck at Adjournment

**Symptoms:** Session won't complete, waiting on reconciliation

**Resolution:**
1. Check reconciliation queue depth
2. Scale workers if needed
3. Review any stuck validators
4. Never bypass the gate (P2)

---

## Testing

### Integration Tests

```bash
# Run async validation integration tests (requires Docker)
pytest tests/integration/test_async_vote_validation.py -v
```

### Fallback Tests

```bash
# Run fallback path unit tests
pytest tests/unit/application/services/test_conclave_fallback.py -v
```

### State Reconstruction Tests

```bash
# Run aggregator reconstruction tests
pytest tests/unit/workers/test_aggregator_reconstruction.py -v
```

---

## References

- [Spike Document](../spikes/Conclave%20async%20vote%20validation%20spike.md)
- [Constitutional Implementation Rules](../constitutional-implementation-rules.md)
- [Conclave Process Documentation](../stages/conclave-process-documentation.md)

---

*Last Updated: 2026-01-23*
