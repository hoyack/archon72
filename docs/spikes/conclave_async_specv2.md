# Conclave Async Vote Validation Architecture

**Spike Document v2.0**
**Date:** 2026-01-24
**Author:** Claude (with Brandon)
**Status:** 📋 SPECIFICATION

---

## Revision Summary (v1.1 → v2.0)

| Change | v1.1 | v2.0 |
|--------|------|------|
| **Validation model** | 2 co-equal validators | 2 deliberators + 1 witness arbiter |
| **Witness role** | Peer validator | Arbiter (reviews deliberators, confirms/retorts) |
| **Concurrency control** | Kafka consumer group scaling | `--voting-concurrency` semaphore |
| **Env vars** | `WITNESS_ARCHON_ID`, `SECRETARY_TEXT_ARCHON_ID` | + `SECRETARY_JSON_ARCHON_ID` |
| **Tasks per vote** | 2 parallel | 3 parallel + 1 sequential adjudication |
| **Kafka role** | Primary orchestration | Audit trail + event sourcing |

---

## Executive Summary

This document specifies an asynchronous vote validation architecture for the Archon 72 Conclave system using a **three-tier validation model**:

1. **Deliberator 1 (Secretary Text)**: Analyzes vote intent from natural language reasoning
2. **Deliberator 2 (Secretary JSON)**: Validates vote structure and consistency via structured output
3. **Witness (Arbiter)**: Reviews deliberator results, confirms consensus or retorts disagreement

Validation runs asynchronously with **bounded concurrency** controlled by a `--voting-concurrency` parameter (default: 8). Votes flow through an in-process asyncio pipeline while Kafka provides the immutable audit trail.

**Key Principle:** Votes are captured optimistically (regex-parsed) and validated asynchronously. The deliberation pipeline never blocks on validation. Reconciliation occurs at session adjournment.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Three-Tier Validation Model](#2-three-tier-validation-model)
3. [Bounded Concurrency Architecture](#3-bounded-concurrency-architecture)
4. [Pipeline Flow](#4-pipeline-flow)
5. [Kafka Audit Trail](#5-kafka-audit-trail)
6. [Component Design](#6-component-design)
7. [Reconciliation & Finalization](#7-reconciliation--finalization)
8. [Error Handling & Edge Cases](#8-error-handling--edge-cases)
9. [Configuration](#9-configuration)
10. [Implementation Plan](#10-implementation-plan)
11. [Pre-Mortems & Mitigations](#11-pre-mortems--mitigations)
12. [AGI Readiness](#12-agi-readiness)
13. [Appendix: Archon IDs](#appendix-archon-ids)

---

## 1. Problem Statement

### 1.1 Current Blocking Behavior

The current synchronous dual-LLM validation blocks the deliberation pipeline:

| Metric | Value |
|--------|-------|
| Archons | 72 |
| Motions (typical session) | 64 |
| Validators per vote | 3 (2 deliberators + 1 witness) |
| Tasks per vote | 4 (3 parallel + 1 adjudication) |
| Max retry attempts | 3 |
| **Total validation calls** | **18,432 - 55,296** |
| Avg LLM latency | 2-15s |
| **Added pipeline time** | **10 - 230 hours** |

### 1.2 Desired Behavior

- Vote capture is **non-blocking**: Parse immediately, continue to next archon
- Validation runs **asynchronously** with bounded parallelism
- Deliberation proceeds using **optimistic votes** (regex-parsed)
- **Reconciliation gate** at session end ensures all validations complete
- Any vote corrections applied **before** final transcript generation

---

## 2. Three-Tier Validation Model

### 2.1 The Three Roles

| Role | Env Var | Archon | Purpose |
|------|---------|--------|---------|
| **Deliberator 1** | `SECRETARY_TEXT_ARCHON_ID` | Orias | Analyzes vote intent from natural language reasoning |
| **Deliberator 2** | `SECRETARY_JSON_ARCHON_ID` | TBD | Validates vote structure/consistency (structured JSON output) |
| **Witness** | `WITNESS_ARCHON_ID` | Furcas | Neutral arbiter who confirms deliberator consensus or flags disagreement |

### 2.2 Why Three Tiers?

| Concern | Two-Tier (v1.1) | Three-Tier (v2.0) |
|---------|-----------------|-------------------|
| **Consensus logic** | External aggregator service | Witness archon (constitutional role) |
| **Tie-breaking** | Retry until unanimous or fail | Witness adjudicates disagreements |
| **Validation diversity** | Same task, different archons | Different task types (text vs JSON) |
| **Audit accountability** | Service logs | Archon-signed witness statements |
| **Constitutional alignment** | Witness is peer validator | Witness fulfills observer/recorder role |

### 2.3 Role Responsibilities

#### Deliberator 1: Text Analysis (`SECRETARY_TEXT_ARCHON_ID`)

```
Input:  Raw LLM vote response (natural language)
Task:   Extract vote intent from prose reasoning
Output: {
  "vote_choice": "AYE" | "NAY" | "ABSTAIN",
  "confidence": 0.0-1.0,
  "reasoning_summary": "...",
  "ambiguity_flags": [...]
}
```

#### Deliberator 2: JSON Validation (`SECRETARY_JSON_ARCHON_ID`)

```
Input:  Raw LLM vote response + motion context
Task:   Validate structural consistency, check for contradictions
Output: {
  "vote_choice": "AYE" | "NAY" | "ABSTAIN",
  "structural_valid": true | false,
  "contradictions": [...],
  "motion_alignment": 0.0-1.0
}
```

#### Witness: Intent Confirmation + Adjudication (`WITNESS_ARCHON_ID`)

**Phase 1 (Parallel):** Initial intent confirmation
```
Input:  Raw LLM vote response
Task:   Independent vote intent read (no deliberator context)
Output: {
  "vote_choice": "AYE" | "NAY" | "ABSTAIN",
  "intent_clear": true | false
}
```

**Phase 2 (Sequential):** Adjudication after deliberators complete
```
Input:  Deliberator 1 result, Deliberator 2 result, Phase 1 result
Task:   Determine consensus, issue ruling
Output: {
  "consensus": true | false,
  "final_vote": "AYE" | "NAY" | "ABSTAIN",
  "ruling": "CONFIRMED" | "RETORT",
  "retort_reason": "..." (if ruling == RETORT),
  "witness_statement": "..." (formal record)
}
```

---

## 3. Bounded Concurrency Architecture

### 3.1 The `--voting-concurrency` Parameter

Controls maximum concurrent LLM calls across all in-flight vote validations.

```bash
python scripts/run_conclave.py --voting-concurrency 8
```

| Setting | Behavior |
|---------|----------|
| `1` | Fully sequential (debugging) |
| `4` | Conservative (laptop/shared Ollama) |
| `8` | Default (dedicated GPU) |
| `16` | Aggressive (multi-GPU cluster) |
| `32+` | AGI-scale (distributed inference) |

### 3.2 Semaphore-Based Concurrency

```python
class AsyncVoteValidator:
    def __init__(self, voting_concurrency: int, ...):
        self.semaphore = asyncio.Semaphore(voting_concurrency)
```

Each LLM call acquires the semaphore before execution:

```python
async def _run_task(self, job, task_type, validator_id):
    async with self.semaphore:  # Blocks if at capacity
        result = await self.orchestrator.execute_validation_task(...)
        return result
```

### 3.3 Concurrency Visualization

With 72 archons voting and `--voting-concurrency=8`:

```
Time ──────────────────────────────────────────────────────────────────────►

Vote 1 Cast ─┬─► [D1] ─────────┐
             ├─► [D2] ─────────┼──► [W-Adj] ──► ✓ Vote 1 Validated
             └─► [W1] ─────────┘
                    │
Vote 2 Cast ────────┼─┬─► [D1] ─────────┐
                    │ ├─► [D2] ─────────┼──► [W-Adj] ──► ✓ Vote 2 Validated
                    │ └─► [W1] ─────────┘
                    │          │
Vote 3 Cast ────────┼──────────┼─┬─► [D1] ─────────┐
                    │          │ ├─► [D2] ─────────┼──► [W-Adj] ──► ✓
                    │          │ └─► [W1] ─────────┘

Active Tasks:  3    6          8     7     5     3     ...
              └────────────────┴─────────────────────────┘
                        Bounded by semaphore(8)
```

### 3.4 Timing Estimates

| Scenario | Calculation | Duration |
|----------|-------------|----------|
| **Sequential (old)** | 72 votes × 4 tasks × 15s | ~72 minutes |
| **Async, concurrency=8** | 72 × 4 × 15s / 8 | ~9 minutes |
| **Async, concurrency=16** | 72 × 4 × 15s / 16 | ~4.5 minutes |

Plus overhead for barrier waits between phases.

---

## 4. Pipeline Flow

### 4.1 Single Vote Validation Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SINGLE VOTE VALIDATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              PHASE 1: Parallel Analysis                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                                                                     │   │
│   │   Vote Cast ──┬──► [Deliberator 1: Text Analysis]  ────┐           │   │
│   │               │                                         │           │   │
│   │               ├──► [Deliberator 2: JSON Validation] ───┼──► Barrier│   │
│   │               │                                         │           │   │
│   │               └──► [Witness: Intent Confirmation]  ────┘           │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│                              PHASE 2: Adjudication                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                                                                     │   │
│   │   All 3 Results ──► [Witness Adjudication] ──► Consensus Decision  │   │
│   │                                                                     │   │
│   │   Outcomes:                                                         │   │
│   │     • CONFIRMED: All agree → final_vote = consensus                │   │
│   │     • CONFIRMED: 2/3 agree → final_vote = majority                 │   │
│   │     • RETORT: All disagree → final_vote = ABSTAIN + witness_reason │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│                              Validated Vote                                 │
│                     (Published to Kafka audit trail)                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Full Session Flow

```
Session Start
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: Call to Order / Roll Call                                        │
│ Validation queue: empty                                                 │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: New Business (Motion 1)                                          │
│                                                                         │
│   Debate Rounds: 72 archons × 3 rounds (~54 min)                       │
│       └─▶ Validation queue: 0 votes (no voting yet)                    │
│                                                                         │
│   Voting: 72 archons vote                                              │
│       └─▶ Each vote immediately submitted to async validator           │
│       └─▶ Validation runs in background (bounded by semaphore)         │
│       └─▶ Optimistic tally used for immediate result display           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: New Business (Motion 2...N)                                      │
│                                                                         │
│   During debate: Previous motion's validations complete in background  │
│   By motion end: Most validations caught up                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE: Adjournment (RECONCILIATION GATE)                                │
│                                                                         │
│   1. await validator.drain() ─────► Block until all validations done   │
│   2. Get all validated results                                          │
│   3. Compare validated vs optimistic                                    │
│   4. Apply overrides where they differ                                  │
│   5. Recompute affected motion tallies                                  │
│   6. Generate final transcript with corrections noted                   │
│   7. Publish session complete event                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
Session End
```

---

## 5. Kafka Audit Trail

### 5.1 Role of Kafka

Kafka serves as the **immutable audit trail**, not the primary orchestration mechanism. All vote validation events are published for:

- Governance transparency (nothing hidden or deletable)
- Event replay (reconstruct any session state)
- Analytics and ML training
- Regulatory compliance

### 5.2 Topic Taxonomy

```
conclave.                           # Namespace
├── votes.
│   ├── cast                        # Raw votes as captured (optimistic)
│   ├── validation-started          # Validation job initiated
│   ├── deliberation-results        # Individual deliberator outputs
│   ├── adjudication-results        # Witness adjudication outcomes
│   ├── validated                   # Final validated votes
│   └── overrides                   # Corrections applied at reconciliation
├── witness.
│   ├── statements                  # Formal witness statements
│   └── retorts                     # Disagreement records
└── sessions.
    ├── checkpoints                 # Session state snapshots
    └── transcripts                 # Final transcripts (compacted)
```

### 5.3 Key Message Schemas

#### `conclave.votes.cast`

```json
{
  "vote_id": "uuid",
  "session_id": "uuid",
  "motion_id": "uuid",
  "archon_id": "uuid",
  "archon_name": "string",
  "aegis_rank": "string",
  "raw_vote_content": "string (full LLM response)",
  "optimistic_choice": "AYE | NAY | ABSTAIN",
  "timestamp": "ISO8601"
}
```

#### `conclave.votes.validated`

```json
{
  "vote_id": "uuid",
  "session_id": "uuid",
  "motion_id": "uuid",
  "archon_id": "uuid",
  "optimistic_choice": "AYE | NAY | ABSTAIN",
  "validated_choice": "AYE | NAY | ABSTAIN",
  "consensus_reached": true,
  "witness_ruling": "CONFIRMED | RETORT",
  "override_required": false,
  "deliberator_results": {
    "text_analysis": {...},
    "json_validation": {...}
  },
  "witness_adjudication": {...},
  "timestamp": "ISO8601"
}
```

#### `conclave.witness.statements`

```json
{
  "statement_id": "uuid",
  "vote_id": "uuid",
  "witness_archon_id": "uuid",
  "ruling": "CONFIRMED | RETORT",
  "statement_text": "string (formal witness record)",
  "retort_reason": "string | null",
  "deliberator_agreement": {
    "text_analysis": "AYE",
    "json_validation": "AYE",
    "witness_confirm": "AYE"
  },
  "timestamp": "ISO8601"
}
```

---

## 6. Component Design

### 6.1 Data Classes

```python
from dataclasses import dataclass, field
from typing import Literal, Optional, Any
from enum import Enum
import asyncio

class VoteChoice(Enum):
    AYE = "AYE"
    NAY = "NAY"
    ABSTAIN = "ABSTAIN"

class WitnessRuling(Enum):
    CONFIRMED = "CONFIRMED"
    RETORT = "RETORT"

@dataclass
class DeliberatorResult:
    """Result from a single deliberator."""
    deliberator_type: Literal["text_analysis", "json_validation", "witness_confirm"]
    validator_archon_id: str
    vote_choice: Optional[VoteChoice]
    confidence: float
    raw_response: str
    parse_success: bool
    latency_ms: int
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

@dataclass
class AdjudicationResult:
    """Result from witness adjudication phase."""
    consensus: bool
    final_vote: VoteChoice
    ruling: WitnessRuling
    retort_reason: Optional[str]
    witness_statement: str
    deliberator_agreement: dict[str, VoteChoice]

@dataclass
class VoteValidationJob:
    """Tracks all tasks for a single vote's validation pipeline."""
    vote_id: str
    session_id: str
    motion_id: str
    archon_id: str
    archon_name: str
    optimistic_choice: VoteChoice
    vote_payload: dict
    
    # Results populated as tasks complete
    deliberator_results: dict[str, DeliberatorResult] = field(default_factory=dict)
    adjudication_result: Optional[AdjudicationResult] = None
    
    # Completion tracking
    completed: asyncio.Event = field(default_factory=asyncio.Event)
    error: Optional[str] = None
    
    @property
    def override_required(self) -> bool:
        """True if validated vote differs from optimistic."""
        if not self.adjudication_result:
            return False
        return self.adjudication_result.final_vote != self.optimistic_choice
```

### 6.2 AsyncVoteValidator

```python
class AsyncVoteValidator:
    """Manages async vote validation with bounded concurrency."""
    
    def __init__(
        self,
        voting_concurrency: int,
        secretary_text_id: str,
        secretary_json_id: str,
        witness_id: str,
        orchestrator: CrewAIAdapter,
        kafka_publisher: Optional[KafkaPublisher] = None,
    ):
        self.semaphore = asyncio.Semaphore(voting_concurrency)
        self.secretary_text_id = secretary_text_id
        self.secretary_json_id = secretary_json_id
        self.witness_id = witness_id
        self.orchestrator = orchestrator
        self.kafka_publisher = kafka_publisher
        
        # Track in-flight jobs
        self.pending_jobs: dict[str, VoteValidationJob] = {}
        self.completed_jobs: dict[str, VoteValidationJob] = {}
        self.completed_queue: asyncio.Queue[VoteValidationJob] = asyncio.Queue()
        
        # Metrics
        self.total_submitted = 0
        self.total_completed = 0
        self.total_overrides = 0
        
    async def submit_vote(
        self,
        vote_id: str,
        session_id: str,
        motion_id: str,
        archon_id: str,
        archon_name: str,
        optimistic_choice: VoteChoice,
        vote_payload: dict,
    ) -> None:
        """Submit a vote for async validation. Returns immediately."""
        job = VoteValidationJob(
            vote_id=vote_id,
            session_id=session_id,
            motion_id=motion_id,
            archon_id=archon_id,
            archon_name=archon_name,
            optimistic_choice=optimistic_choice,
            vote_payload=vote_payload,
        )
        
        self.pending_jobs[vote_id] = job
        self.total_submitted += 1
        
        # Publish to Kafka audit trail
        if self.kafka_publisher:
            await self.kafka_publisher.publish(
                "conclave.votes.validation-started",
                {"vote_id": vote_id, "archon_id": archon_id, "optimistic": optimistic_choice.value}
            )
        
        # Fire off the validation pipeline (non-blocking)
        asyncio.create_task(self._run_validation_pipeline(job))
        
    async def _run_validation_pipeline(self, job: VoteValidationJob) -> None:
        """Run the full validation pipeline for a single vote."""
        try:
            # ═══════════════════════════════════════════════════════════════
            # PHASE 1: Parallel deliberation (3 tasks, bounded by semaphore)
            # ═══════════════════════════════════════════════════════════════
            phase1_tasks = [
                self._run_deliberator(job, "text_analysis", self.secretary_text_id),
                self._run_deliberator(job, "json_validation", self.secretary_json_id),
                self._run_deliberator(job, "witness_confirm", self.witness_id),
            ]
            
            await asyncio.gather(*phase1_tasks, return_exceptions=True)
            
            # ═══════════════════════════════════════════════════════════════
            # PHASE 2: Witness adjudication (sequential, after Phase 1)
            # ═══════════════════════════════════════════════════════════════
            async with self.semaphore:
                job.adjudication_result = await self._witness_adjudicate(job)
            
            # Publish validated result to Kafka
            if self.kafka_publisher:
                await self.kafka_publisher.publish(
                    "conclave.votes.validated",
                    self._serialize_validated_vote(job)
                )
                
                # Publish witness statement
                await self.kafka_publisher.publish(
                    "conclave.witness.statements",
                    self._serialize_witness_statement(job)
                )
            
        except Exception as e:
            job.error = str(e)
            
        finally:
            # Move to completed
            job.completed.set()
            del self.pending_jobs[job.vote_id]
            self.completed_jobs[job.vote_id] = job
            await self.completed_queue.put(job)
            self.total_completed += 1
            
            if job.override_required:
                self.total_overrides += 1
    
    async def _run_deliberator(
        self,
        job: VoteValidationJob,
        deliberator_type: str,
        validator_id: str,
    ) -> DeliberatorResult:
        """Run a single deliberator task, respecting concurrency limit."""
        async with self.semaphore:
            start_time = asyncio.get_event_loop().time()
            
            try:
                result = await self.orchestrator.execute_validation_task(
                    task_type=deliberator_type,
                    validator_archon_id=validator_id,
                    vote_payload=job.vote_payload,
                )
                
                latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                
                deliberator_result = DeliberatorResult(
                    deliberator_type=deliberator_type,
                    validator_archon_id=validator_id,
                    vote_choice=self._parse_vote_choice(result.get("vote_choice")),
                    confidence=result.get("confidence", 0.0),
                    raw_response=result.get("raw_response", ""),
                    parse_success=result.get("parse_success", False),
                    latency_ms=latency_ms,
                    metadata=result.get("metadata", {}),
                )
                
            except Exception as e:
                latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                deliberator_result = DeliberatorResult(
                    deliberator_type=deliberator_type,
                    validator_archon_id=validator_id,
                    vote_choice=None,
                    confidence=0.0,
                    raw_response="",
                    parse_success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                )
            
            job.deliberator_results[deliberator_type] = deliberator_result
            
            # Publish individual deliberation result to Kafka
            if self.kafka_publisher:
                await self.kafka_publisher.publish(
                    "conclave.votes.deliberation-results",
                    {
                        "vote_id": job.vote_id,
                        "deliberator_type": deliberator_type,
                        "vote_choice": deliberator_result.vote_choice.value if deliberator_result.vote_choice else None,
                        "latency_ms": latency_ms,
                    }
                )
            
            return deliberator_result
    
    async def _witness_adjudicate(self, job: VoteValidationJob) -> AdjudicationResult:
        """Witness reviews all deliberator results and issues final ruling."""
        
        # Gather deliberator votes
        deliberator_votes = {
            dtype: result.vote_choice
            for dtype, result in job.deliberator_results.items()
            if result.vote_choice is not None
        }
        
        # Check for consensus
        unique_votes = set(deliberator_votes.values())
        
        if len(unique_votes) == 1:
            # Unanimous agreement
            consensus_vote = list(unique_votes)[0]
            return AdjudicationResult(
                consensus=True,
                final_vote=consensus_vote,
                ruling=WitnessRuling.CONFIRMED,
                retort_reason=None,
                witness_statement=f"All deliberators unanimously validated vote as {consensus_vote.value}.",
                deliberator_agreement={k: v.value for k, v in deliberator_votes.items()},
            )
        
        elif len(unique_votes) == 2 and len(deliberator_votes) == 3:
            # 2/3 majority
            from collections import Counter
            vote_counts = Counter(deliberator_votes.values())
            majority_vote, count = vote_counts.most_common(1)[0]
            
            if count >= 2:
                return AdjudicationResult(
                    consensus=True,
                    final_vote=majority_vote,
                    ruling=WitnessRuling.CONFIRMED,
                    retort_reason=None,
                    witness_statement=f"Majority ({count}/3) validated vote as {majority_vote.value}.",
                    deliberator_agreement={k: v.value for k, v in deliberator_votes.items()},
                )
        
        # No consensus - invoke witness LLM for tie-breaking
        adjudication_response = await self.orchestrator.execute_witness_adjudication(
            witness_archon_id=self.witness_id,
            vote_payload=job.vote_payload,
            deliberator_results={
                dtype: {
                    "vote_choice": result.vote_choice.value if result.vote_choice else None,
                    "confidence": result.confidence,
                    "metadata": result.metadata,
                }
                for dtype, result in job.deliberator_results.items()
            },
        )
        
        # Parse adjudication response
        final_vote = self._parse_vote_choice(adjudication_response.get("final_vote"))
        ruling = WitnessRuling.RETORT if adjudication_response.get("retort") else WitnessRuling.CONFIRMED
        
        return AdjudicationResult(
            consensus=not adjudication_response.get("retort", False),
            final_vote=final_vote or VoteChoice.ABSTAIN,
            ruling=ruling,
            retort_reason=adjudication_response.get("retort_reason"),
            witness_statement=adjudication_response.get("witness_statement", ""),
            deliberator_agreement={k: v.value for k, v in deliberator_votes.items()},
        )
    
    async def drain(self, timeout: float = 300.0) -> list[VoteValidationJob]:
        """Wait for all pending validations to complete."""
        if not self.pending_jobs:
            return list(self.completed_jobs.values())
        
        pending_events = [job.completed for job in self.pending_jobs.values()]
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*[e.wait() for e in pending_events]),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise ReconciliationTimeoutError(
                f"Validation drain timed out after {timeout}s. "
                f"{len(self.pending_jobs)} jobs still pending."
            )
        
        return list(self.completed_jobs.values())
    
    def get_stats(self) -> dict:
        """Return current validator statistics."""
        return {
            "total_submitted": self.total_submitted,
            "total_completed": self.total_completed,
            "pending": len(self.pending_jobs),
            "overrides_required": self.total_overrides,
        }
    
    def _parse_vote_choice(self, value: Any) -> Optional[VoteChoice]:
        """Parse vote choice from various formats."""
        if isinstance(value, VoteChoice):
            return value
        if isinstance(value, str):
            value = value.upper().strip()
            if value in ("AYE", "YES", "FOR", "YEA"):
                return VoteChoice.AYE
            if value in ("NAY", "NO", "AGAINST"):
                return VoteChoice.NAY
            if value in ("ABSTAIN", "PRESENT"):
                return VoteChoice.ABSTAIN
        return None
    
    def _serialize_validated_vote(self, job: VoteValidationJob) -> dict:
        """Serialize job to Kafka message format."""
        return {
            "vote_id": job.vote_id,
            "session_id": job.session_id,
            "motion_id": job.motion_id,
            "archon_id": job.archon_id,
            "optimistic_choice": job.optimistic_choice.value,
            "validated_choice": job.adjudication_result.final_vote.value,
            "consensus_reached": job.adjudication_result.consensus,
            "witness_ruling": job.adjudication_result.ruling.value,
            "override_required": job.override_required,
        }
    
    def _serialize_witness_statement(self, job: VoteValidationJob) -> dict:
        """Serialize witness statement to Kafka message format."""
        return {
            "vote_id": job.vote_id,
            "witness_archon_id": self.witness_id,
            "ruling": job.adjudication_result.ruling.value,
            "statement_text": job.adjudication_result.witness_statement,
            "retort_reason": job.adjudication_result.retort_reason,
            "deliberator_agreement": job.adjudication_result.deliberator_agreement,
        }
```

### 6.3 Integration with ConclaveService

```python
# In ConclaveService.__init__
self._validator: Optional[AsyncVoteValidator] = None

# In ConclaveService.conduct_vote()
async def conduct_vote(self) -> dict:
    """Conduct voting with async validation pipeline."""
    
    # Initialize validator if not exists
    if self._validator is None and self._config.async_validation_enabled:
        self._validator = AsyncVoteValidator(
            voting_concurrency=self._config.voting_concurrency,
            secretary_text_id=self._config.secretary_text_archon_id,
            secretary_json_id=self._config.secretary_json_archon_id,
            witness_id=self._config.witness_archon_id,
            orchestrator=self._orchestrator,
            kafka_publisher=self._kafka_publisher,
        )
    
    motion = self._session.current_motion
    optimistic_tally = {"ayes": 0, "nays": 0, "abstentions": 0}
    
    # Collect votes from all archons
    for idx, archon in enumerate(self._present_archons):
        vote_payload = await self._collect_vote_from_archon(archon, motion)
        optimistic_choice = self._parse_vote(vote_payload["raw_content"])
        
        # Update optimistic tally immediately
        if optimistic_choice == VoteChoice.AYE:
            optimistic_tally["ayes"] += 1
        elif optimistic_choice == VoteChoice.NAY:
            optimistic_tally["nays"] += 1
        else:
            optimistic_tally["abstentions"] += 1
        
        # Submit for async validation (non-blocking)
        if self._validator:
            await self._validator.submit_vote(
                vote_id=f"{self._session.session_id}-{motion.motion_id}-{archon.id}",
                session_id=str(self._session.session_id),
                motion_id=str(motion.motion_id),
                archon_id=archon.id,
                archon_name=archon.name,
                optimistic_choice=optimistic_choice,
                vote_payload=vote_payload,
            )
        
        self._progress_callback("archon_voting", f"{archon.name} cast vote", {
            "archon": archon.name,
            "progress": f"{idx + 1}/{len(self._present_archons)}",
            "pending_validations": self._validator.get_stats()["pending"] if self._validator else 0,
        })
    
    # Return optimistic result (validation continues in background)
    return self._compute_result(optimistic_tally, is_optimistic=True)
```

---

## 7. Reconciliation & Finalization

### 7.1 Reconciliation Gate

At session adjournment, block until all validations complete:

```python
async def adjourn(self) -> None:
    """Adjourn the session with reconciliation gate."""
    
    # ═══════════════════════════════════════════════════════════════════
    # RECONCILIATION GATE: Wait for all validations
    # ═══════════════════════════════════════════════════════════════════
    if self._validator:
        self._progress_callback("reconciliation_started", "Waiting for validations to complete", {
            "pending": self._validator.get_stats()["pending"],
        })
        
        try:
            validated_jobs = await self._validator.drain(
                timeout=self._config.reconciliation_timeout
            )
        except ReconciliationTimeoutError as e:
            # Hard failure - do not proceed with incomplete validation
            raise ReconciliationIncompleteError(str(e))
        
        # Apply overrides
        override_count = await self._apply_validation_overrides(validated_jobs)
        
        self._progress_callback("reconciliation_complete", "All validations complete", {
            "total_votes": len(validated_jobs),
            "overrides_applied": override_count,
        })
    
    # Continue with normal adjournment
    self._session.current_phase = SessionPhase.ADJOURNED
    self._session.ended_at = datetime.now()
```

### 7.2 Override Application

```python
async def _apply_validation_overrides(
    self, 
    validated_jobs: list[VoteValidationJob]
) -> int:
    """Apply validated vote corrections and recompute tallies."""
    
    override_count = 0
    affected_motions: set[str] = set()
    
    for job in validated_jobs:
        if not job.override_required:
            continue
        
        motion = self._session.get_motion(job.motion_id)
        if not motion:
            continue
        
        vote = motion.get_vote(job.archon_id)
        if not vote:
            continue
        
        # Record the correction in transcript
        self._session.add_transcript_entry(
            entry_type="procedural",
            content=(
                f"Vote correction: {job.archon_name}'s vote on '{motion.title}' "
                f"validated as {job.adjudication_result.final_vote.value} "
                f"(originally parsed as {job.optimistic_choice.value}). "
                f"Witness ruling: {job.adjudication_result.ruling.value}"
            ),
            speaker_id="system",
            speaker_name="Validation System",
            metadata={
                "event": "vote_override",
                "vote_id": job.vote_id,
                "motion_id": job.motion_id,
                "archon_id": job.archon_id,
                "original": job.optimistic_choice.value,
                "validated": job.adjudication_result.final_vote.value,
                "witness_statement": job.adjudication_result.witness_statement,
            },
        )
        
        # Apply the correction
        vote.choice = job.adjudication_result.final_vote
        vote.reasoning += f"\n\n[Validated: {job.adjudication_result.final_vote.value}]"
        
        override_count += 1
        affected_motions.add(job.motion_id)
        
        # Publish override to Kafka
        if self._kafka_publisher:
            await self._kafka_publisher.publish(
                "conclave.votes.overrides",
                {
                    "vote_id": job.vote_id,
                    "motion_id": job.motion_id,
                    "archon_id": job.archon_id,
                    "original": job.optimistic_choice.value,
                    "validated": job.adjudication_result.final_vote.value,
                }
            )
    
    # Recompute affected motion tallies
    for motion_id in affected_motions:
        motion = self._session.get_motion(motion_id)
        if motion:
            result_changed = self._recompute_motion_result(motion)
            if result_changed:
                self._session.add_transcript_entry(
                    entry_type="procedural",
                    content=(
                        f"Motion '{motion.title}' result changed after vote validation: "
                        f"{'PASSED' if motion.passed else 'FAILED'}"
                    ),
                    speaker_id="system",
                    speaker_name="Validation System",
                )
    
    return override_count
```

### 7.3 Tally Invariant Enforcement (P6)

Ensure validated tally always sums to total votes:

```python
def _recompute_motion_result(self, motion: Motion) -> bool:
    """Recompute motion pass/fail after vote overrides.
    
    Enforces P6 invariant: ayes + nays + abstentions = total_votes
    """
    original_passed = motion.passed
    
    ayes = sum(1 for v in motion.votes if v.choice == VoteChoice.AYE)
    nays = sum(1 for v in motion.votes if v.choice == VoteChoice.NAY)
    abstentions = sum(1 for v in motion.votes if v.choice == VoteChoice.ABSTAIN)
    
    # P6 invariant check
    total = ayes + nays + abstentions
    if total != len(motion.votes):
        raise TallyInvariantViolation(
            f"Tally sum {total} != vote count {len(motion.votes)}"
        )
    
    # Supermajority threshold (abstentions excluded from denominator)
    voting_votes = ayes + nays
    if voting_votes == 0:
        motion.passed = False
    else:
        ratio = ayes / voting_votes
        motion.passed = ratio >= self._config.supermajority_threshold
    
    return motion.passed != original_passed
```

---

## 8. Error Handling & Edge Cases

### 8.1 Per-Task Timeouts

```python
async def _run_deliberator(self, job, deliberator_type, validator_id):
    async with self.semaphore:
        try:
            result = await asyncio.wait_for(
                self.orchestrator.execute_validation_task(...),
                timeout=self._config.task_timeout_seconds,  # e.g., 60s
            )
        except asyncio.TimeoutError:
            return DeliberatorResult(
                deliberator_type=deliberator_type,
                validator_archon_id=validator_id,
                vote_choice=None,
                confidence=0.0,
                raw_response="",
                parse_success=False,
                latency_ms=self._config.task_timeout_seconds * 1000,
                error="Task timeout",
            )
```

### 8.2 Deliberator Failure Handling

If a deliberator fails completely:

| Scenario | Handling |
|----------|----------|
| 1 deliberator fails | Proceed with 2/3 (witness adjudicates) |
| 2 deliberators fail | Witness decides alone (RETORT + flag) |
| All 3 fail | Fall back to optimistic vote (no override) |
| Witness adjudication fails | Use majority of Phase 1 results |

### 8.3 Circuit Breaker for Kafka

```python
class CircuitBreaker:
    """Prevent cascading failures when Kafka is unavailable."""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = None
    
    async def call(self, coro):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitOpenError("Kafka circuit breaker is open")
        
        try:
            result = await coro
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise
```

### 8.4 Checkpoint/Resume with Pending Validations

```python
def save_checkpoint(self) -> Path:
    """Save session checkpoint including pending validations."""
    checkpoint = {
        "session": self._session.to_dict(),
        "pending_validations": [
            {
                "vote_id": job.vote_id,
                "archon_id": job.archon_id,
                "optimistic_choice": job.optimistic_choice.value,
                "vote_payload": job.vote_payload,
            }
            for job in self._validator.pending_jobs.values()
        ] if self._validator else [],
    }
    # ... save to file
```

---

## 9. Configuration

### 9.1 Environment Variables

```bash
# ============================================================
# THREE-TIER VOTE VALIDATION
# ============================================================

# Enable async validation (default: false for backward compatibility)
ENABLE_ASYNC_VALIDATION=true

# Bounded concurrency for validation tasks
VOTING_CONCURRENCY=8

# Deliberator 1: Text Analysis
SECRETARY_TEXT_ARCHON_ID=43d83b84-243b-49ae-9ff4-c3f510db9982

# Deliberator 2: JSON Validation  
SECRETARY_JSON_ARCHON_ID=<to-be-assigned>

# Witness: Arbiter
WITNESS_ARCHON_ID=1b872789-7990-4163-b54b-6bc45746e2f6

# Validation timeouts
VOTE_VALIDATION_TASK_TIMEOUT=60
VOTE_VALIDATION_MAX_ATTEMPTS=3
RECONCILIATION_TIMEOUT=300

# ============================================================
# KAFKA AUDIT TRAIL
# ============================================================

KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_PREFIX=conclave
KAFKA_ENABLED=true
```

### 9.2 ConclaveConfig Updates

```python
@dataclass
class ConclaveConfig:
    # ... existing fields ...
    
    # Three-tier validation
    async_validation_enabled: bool = False
    voting_concurrency: int = 8
    secretary_text_archon_id: Optional[str] = None
    secretary_json_archon_id: Optional[str] = None
    witness_archon_id: Optional[str] = None
    
    # Timeouts
    task_timeout_seconds: int = 60
    reconciliation_timeout: float = 300.0
    
    # Kafka
    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
```

### 9.3 CLI Arguments

```python
parser.add_argument(
    "--voting-concurrency",
    type=int,
    default=8,
    help="Max concurrent vote validation tasks (default: 8)",
)

parser.add_argument(
    "--async-validation",
    action="store_true",
    help="Enable async three-tier vote validation",
)

parser.add_argument(
    "--reconciliation-timeout",
    type=int,
    default=300,
    help="Max seconds to wait for validation drain at adjournment (default: 300)",
)
```

---

## 10. Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

| Task | Deliverable |
|------|-------------|
| Data classes | `VoteValidationJob`, `DeliberatorResult`, `AdjudicationResult` |
| AsyncVoteValidator | Core class with semaphore-based concurrency |
| Unit tests | Validator logic without LLM calls |

### Phase 2: LLM Integration (Week 2)

| Task | Deliverable |
|------|-------------|
| Orchestrator methods | `execute_validation_task()`, `execute_witness_adjudication()` |
| Prompts for deliberators | Text analysis, JSON validation prompts |
| Witness adjudication prompt | Tie-breaking and retort logic |

### Phase 3: ConclaveService Integration (Week 3)

| Task | Deliverable |
|------|-------------|
| Modify `conduct_vote()` | Async submission with optimistic tally |
| Reconciliation gate | `drain()` call at adjournment |
| Override application | Vote correction and tally recompute |

### Phase 4: Kafka Audit Trail (Week 4)

| Task | Deliverable |
|------|-------------|
| KafkaPublisher | Async producer with circuit breaker |
| Topic creation | Scripts for topic setup |
| Message publishing | All validation events to Kafka |

### Phase 5: Testing & Hardening (Week 5)

| Task | Deliverable |
|------|-------------|
| Integration tests | Full round-trip with Redpanda |
| Checkpoint/resume | Pending validation serialization |
| Load testing | 72 archons × 64 motions benchmark |

---

## 11. Pre-Mortems & Mitigations

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| **P1** | Semaphore starvation | Pipeline blocks | Monitor semaphore wait times, alert on p99 > 30s |
| **P2** | Reconciliation timeout | Session incomplete | Hard gate with `ReconciliationIncompleteError` |
| **P3** | Deliberator LLM hangs | Single vote blocks | Per-task timeout with fallback result |
| **P4** | Kafka unavailable | No audit trail | Circuit breaker, validation continues without audit |
| **P5** | Witness adjudication fails | No final ruling | Use Phase 1 majority, flag for manual review |
| **P6** | Tally invariant violation | Incorrect results | Hard assertion, abort if sum ≠ total |
| **P7** | Checkpoint with pending jobs | Lost validations | Serialize pending jobs, resume on restart |
| **P8** | Memory exhaustion | OOM crash | Limit pending_jobs dict size, backpressure |

---

## 12. AGI Readiness

### 12.1 Scaling Dimensions

| Dimension | Current | AGI Scale | Design Support |
|-----------|---------|-----------|----------------|
| Archons | 72 | 10,000+ | Partition by cohort |
| Concurrent sessions | 1 | 1,000+ | Session-isolated validators |
| Votes/second | ~1 | ~10,000 | Increase `voting-concurrency` |
| Deliberators | 2 | N | Pluggable deliberator registry |

### 12.2 Pluggable Deliberator Registry

```python
class DeliberatorRegistry:
    """Registry for dynamic deliberator assignment."""
    
    def get_deliberators(
        self,
        motion_type: MotionType,
        archon_rank: str,
    ) -> list[DeliberatorConfig]:
        """Get deliberators appropriate for vote context."""
        if motion_type == MotionType.CONSTITUTIONAL:
            return self._get_constitutional_deliberators()  # 5 deliberators
        elif archon_rank in ("king", "executive_director"):
            return self._get_executive_deliberators()  # 3 deliberators
        else:
            return self._get_default_deliberators()  # 2 deliberators
```

### 12.3 Consensus Strategy Abstraction

```python
class ConsensusStrategy(Protocol):
    def evaluate(self, results: list[DeliberatorResult]) -> ConsensusOutcome:
        ...

class UnanimousConsensus(ConsensusStrategy):
    """All deliberators must agree."""

class MajorityConsensus(ConsensusStrategy):
    """Simple majority required."""

class WeightedConsensus(ConsensusStrategy):
    """Weighted by deliberator confidence scores."""
```

---

## Appendix: Archon IDs

### Current Validator Assignment

| Role | Archon | UUID | Branch | Rationale |
|------|--------|------|--------|-----------|
| **Deliberator 1** | Orias | `43d83b84-243b-49ae-9ff4-c3f510db9982` | Advisory | Marquis of Status; wisdom/transformation focus |
| **Deliberator 2** | TBD | TBD | TBD | JSON validation specialist |
| **Witness** | Furcas | `1b872789-7990-4163-b54b-6bc45746e2f6` | Witness | Knight-Witness; constitutional observer role |

### Deliberator 2 Candidates

| Archon | Branch | Personality | UUID | Notes |
|--------|--------|-------------|------|-------|
| Vassago | Judicial | Good, Benevolent | `83e07040-c1e2-462d-8844-3a793ae7eb8d` | Prince of Discovery |
| Orobas | Judicial | Faithful, Truthful | `71f9ad05-acb2-46d8-a391-88d86ac55ec8` | "Never deceives" |
| Botis | Judicial | Wise, Reconciling | `89cc33b8-cf98-46d0-8f6f-132e4826e1b6` | Prince of Reconciliation |

**Note:** Judicial branch can deliberate and ratify, creating potential conflict. Consider advisory or witness branch for Deliberator 2.

---

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Claude | Initial spike document |
| 1.1 | 2026-01-23 | Claude | Implementation status update |
| 2.0 | 2026-01-24 | Claude | Three-tier model, bounded concurrency, witness arbiter |

---

*End of Document*