"""Async vote validation models and pipeline."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional, Protocol

from src.domain.models.conclave import VoteChoice
from src.domain.errors.agent import AgentInvocationError

class KafkaPublisherProtocol(Protocol):
    """Protocol for publishing audit events."""

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish a message to a topic."""
        ...


class ReconciliationTimeoutError(RuntimeError):
    """Raised when async validation drain and reconciliation times out."""

    def __init__(self, message: str, pending_count: int, timeout_seconds: float) -> None:
        super().__init__(message)
        self.pending_count = pending_count
        self.timeout_seconds = timeout_seconds


class WitnessRuling(Enum):
    """Witness adjudication outcome."""

    CONFIRMED = "CONFIRMED"
    RETORT = "RETORT"


DeliberatorType = Literal["text_analysis", "json_validation", "witness_confirm"]


@dataclass
class DeliberatorResult:
    """Result from a single deliberator."""

    deliberator_type: DeliberatorType
    validator_archon_id: str
    vote_choice: Optional[VoteChoice]
    confidence: float
    raw_response: str
    parse_success: bool
    latency_ms: int
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdjudicationResult:
    """Result from witness adjudication phase."""

    consensus: bool
    final_vote: VoteChoice
    ruling: WitnessRuling
    retort_reason: Optional[str]
    witness_statement: str
    deliberator_agreement: dict[str, VoteChoice | str]


@dataclass
class VoteValidationJob:
    """Tracks all tasks for a single vote's validation pipeline."""

    vote_id: str
    session_id: str
    motion_id: str
    archon_id: str
    archon_name: str
    optimistic_choice: VoteChoice
    vote_payload: dict[str, Any]

    deliberator_results: dict[str, DeliberatorResult] = field(default_factory=dict)
    adjudication_result: Optional[AdjudicationResult] = None
    completed: asyncio.Event = field(default_factory=asyncio.Event)
    error: Optional[str] = None

    @property
    def override_required(self) -> bool:
        """True if validated vote differs from optimistic."""
        if not self.adjudication_result:
            return False
        return self.adjudication_result.final_vote != self.optimistic_choice


class AsyncVoteValidator:
    """Manages async vote validation with bounded concurrency."""

    def __init__(
        self,
        voting_concurrency: int,
        secretary_text_id: str,
        secretary_json_id: str,
        witness_id: str,
        orchestrator: Any,
        kafka_publisher: KafkaPublisherProtocol | None = None,
        task_timeout_seconds: int = 60,
        max_attempts: int = 3,
        backoff_base_seconds: float = 2.0,
        backoff_max_seconds: float = 30.0,
    ) -> None:
        self._concurrency = voting_concurrency if voting_concurrency > 0 else 1000000
        self.semaphore = asyncio.Semaphore(self._concurrency)
        self.secretary_text_id = secretary_text_id
        self.secretary_json_id = secretary_json_id
        self.witness_id = witness_id
        self.orchestrator = orchestrator
        self.kafka_publisher = kafka_publisher
        self.task_timeout_seconds = max(0, int(task_timeout_seconds))
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_base_seconds = max(0.0, float(backoff_base_seconds))
        self.backoff_max_seconds = max(
            self.backoff_base_seconds, float(backoff_max_seconds)
        )

        self.pending_jobs: dict[str, VoteValidationJob] = {}
        self.completed_jobs: dict[str, VoteValidationJob] = {}
        self.completed_queue: asyncio.Queue[VoteValidationJob] = asyncio.Queue()

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
        vote_payload: dict[str, Any],
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

        if self.kafka_publisher:
            await self.kafka_publisher.publish(
                "conclave.votes.validation-started",
                {
                    "vote_id": vote_id,
                    "archon_id": archon_id,
                    "optimistic": optimistic_choice.value,
                },
            )

        asyncio.create_task(self._run_validation_pipeline(job))

    async def _run_validation_pipeline(self, job: VoteValidationJob) -> None:
        """Run the full validation pipeline for a single vote."""
        try:
            phase1_tasks = [
                self._run_deliberator(job, "text_analysis", self.secretary_text_id),
                self._run_deliberator(job, "json_validation", self.secretary_json_id),
                self._run_deliberator(job, "witness_confirm", self.witness_id),
            ]
            await asyncio.gather(*phase1_tasks, return_exceptions=True)
            job.adjudication_result = await self._witness_adjudicate(job)

            if self.kafka_publisher:
                await self.kafka_publisher.publish(
                    "conclave.votes.adjudication-results",
                    {
                        "vote_id": job.vote_id,
                        "session_id": job.session_id,
                        "motion_id": job.motion_id,
                        "archon_id": job.archon_id,
                        "final_vote": job.adjudication_result.final_vote.value,
                        "consensus": job.adjudication_result.consensus,
                        "ruling": job.adjudication_result.ruling.value,
                        "retort_reason": job.adjudication_result.retort_reason,
                    },
                )
                await self.kafka_publisher.publish(
                    "conclave.votes.validated",
                    self._serialize_validated_vote(job),
                )
                await self.kafka_publisher.publish(
                    "conclave.witness.statements",
                    self._serialize_witness_statement(job),
                )
                if job.adjudication_result.ruling == WitnessRuling.RETORT:
                    await self.kafka_publisher.publish(
                        "conclave.witness.retorts",
                        {
                            "vote_id": job.vote_id,
                            "session_id": job.session_id,
                            "motion_id": job.motion_id,
                            "archon_id": job.archon_id,
                            "retort_reason": job.adjudication_result.retort_reason,
                            "witness_statement": job.adjudication_result.witness_statement,
                        },
                    )
        except Exception as exc:
            job.error = str(exc)
        finally:
            job.completed.set()
            self.pending_jobs.pop(job.vote_id, None)
            self.completed_jobs[job.vote_id] = job
            await self.completed_queue.put(job)
            self.total_completed += 1
            if job.override_required:
                self.total_overrides += 1

    async def _run_deliberator(
        self,
        job: VoteValidationJob,
        deliberator_type: DeliberatorType,
        validator_id: str,
    ) -> DeliberatorResult:
        """Run a single deliberator task, respecting concurrency limit."""
        start_time = asyncio.get_event_loop().time()
        error_message: str | None = None
        result_payload: dict[str, Any] | None = None

        try:
            result_payload = await self._execute_with_retries(
                lambda: self._with_semaphore(
                    self.orchestrator.execute_validation_task(
                        task_type=deliberator_type,
                        validator_archon_id=validator_id,
                        vote_payload=job.vote_payload,
                    )
                )
            )
        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__

        latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        if result_payload:
            deliberator_result = DeliberatorResult(
                deliberator_type=deliberator_type,
                validator_archon_id=validator_id,
                vote_choice=self._parse_vote_choice(result_payload.get("vote_choice")),
                confidence=result_payload.get("confidence", 0.0),
                raw_response=result_payload.get("raw_response", ""),
                parse_success=result_payload.get("parse_success", False),
                latency_ms=latency_ms,
                metadata=result_payload.get("metadata", {}),
            )
        else:
            deliberator_result = DeliberatorResult(
                deliberator_type=deliberator_type,
                validator_archon_id=validator_id,
                vote_choice=None,
                confidence=0.0,
                raw_response="",
                parse_success=False,
                latency_ms=latency_ms,
                error=error_message,
            )

        job.deliberator_results[deliberator_type] = deliberator_result

        if self.kafka_publisher:
            await self.kafka_publisher.publish(
                "conclave.votes.deliberation-results",
                {
                    "vote_id": job.vote_id,
                    "deliberator_type": deliberator_type,
                    "vote_choice": (
                        deliberator_result.vote_choice.value
                        if deliberator_result.vote_choice
                        else None
                    ),
                    "latency_ms": latency_ms,
                    "error": deliberator_result.error,
                },
            )

        return deliberator_result

    async def _witness_adjudicate(self, job: VoteValidationJob) -> AdjudicationResult:
        """Witness reviews deliberator results and issues final ruling."""
        deliberator_votes: dict[str, VoteChoice] = {
            dtype: result.vote_choice
            for dtype, result in job.deliberator_results.items()
            if result.vote_choice is not None
        }

        unique_votes = set(deliberator_votes.values())
        if len(unique_votes) == 1 and unique_votes:
            consensus_vote = next(iter(unique_votes))
            return AdjudicationResult(
                consensus=True,
                final_vote=consensus_vote,
                ruling=WitnessRuling.CONFIRMED,
                retort_reason=None,
                witness_statement=(
                    f"All deliberators unanimously validated vote as "
                    f"{consensus_vote.value}."
                ),
                deliberator_agreement={
                    k: v.value for k, v in deliberator_votes.items()
                },
            )

        if len(unique_votes) == 2 and len(deliberator_votes) == 3:
            from collections import Counter

            vote_counts = Counter(deliberator_votes.values())
            majority_vote, count = vote_counts.most_common(1)[0]
            if count >= 2:
                return AdjudicationResult(
                    consensus=True,
                    final_vote=majority_vote,
                    ruling=WitnessRuling.CONFIRMED,
                    retort_reason=None,
                    witness_statement=(
                        f"Majority ({count}/3) validated vote as "
                        f"{majority_vote.value}."
                    ),
                    deliberator_agreement={
                        k: v.value for k, v in deliberator_votes.items()
                    },
                )

        adjudication_response = await self._execute_with_retries(
            lambda: self._with_semaphore(
                self.orchestrator.execute_witness_adjudication(
                    witness_archon_id=self.witness_id,
                    vote_payload=job.vote_payload,
                    deliberator_results={
                        dtype: {
                            "vote_choice": result.vote_choice.value
                            if result.vote_choice
                            else None,
                            "confidence": result.confidence,
                            "metadata": result.metadata,
                        }
                        for dtype, result in job.deliberator_results.items()
                    },
                )
            ),
        )

        final_vote = self._parse_vote_choice(adjudication_response.get("final_vote"))
        ruling = (
            WitnessRuling.RETORT
            if adjudication_response.get("retort")
            else WitnessRuling.CONFIRMED
        )

        return AdjudicationResult(
            consensus=not adjudication_response.get("retort", False),
            final_vote=final_vote or VoteChoice.ABSTAIN,
            ruling=ruling,
            retort_reason=adjudication_response.get("retort_reason"),
            witness_statement=adjudication_response.get("witness_statement", ""),
            deliberator_agreement={
                k: v.value for k, v in deliberator_votes.items()
            },
        )

    def _is_retryable(self, exc: Exception) -> bool:
        if isinstance(exc, asyncio.TimeoutError):
            return True
        message = str(exc).lower()
        if isinstance(exc, AgentInvocationError):
            if "timed out" in message:
                return True
        if "too many concurrent requests" in message:
            return True
        if "rate limit" in message or "429" in message:
            return True
        return False

    def _backoff_delay(self, attempt: int) -> float:
        if self.backoff_base_seconds <= 0:
            return 0.0
        delay = min(
            self.backoff_base_seconds * (2 ** (attempt - 1)),
            self.backoff_max_seconds,
        )
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter

    async def _execute_with_retries(self, coro_factory: Any) -> Any:
        """Execute a coroutine with timeouts and retries."""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                if self.task_timeout_seconds > 0:
                    return await asyncio.wait_for(
                        coro_factory(),
                        timeout=self.task_timeout_seconds,
                    )
                return await coro_factory()
            except Exception as exc:
                last_exc = exc
                if self._is_retryable(exc) and attempt < self.max_attempts:
                    delay = self._backoff_delay(attempt)
                    if delay:
                        await asyncio.sleep(delay)
                    continue
                raise

        if last_exc:
            raise last_exc

    async def _with_semaphore(self, coro: Any) -> Any:
        async with self.semaphore:
            return await coro

    async def drain(self, timeout: float = 300.0) -> list[VoteValidationJob]:
        """Wait for all pending validations to complete."""
        if not self.pending_jobs:
            return list(self.completed_jobs.values())

        pending_events = [job.completed for job in self.pending_jobs.values()]

        try:
            await asyncio.wait_for(
                asyncio.gather(*[event.wait() for event in pending_events]),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise ReconciliationTimeoutError(
                message=(
                    f"Validation drain timed out after {timeout}s; "
                    f"{len(self.pending_jobs)} jobs still pending."
                ),
                pending_count=len(self.pending_jobs),
                timeout_seconds=timeout,
            ) from exc

        return list(self.completed_jobs.values())

    def get_stats(self) -> dict[str, int]:
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

    def _serialize_validated_vote(self, job: VoteValidationJob) -> dict[str, Any]:
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

    def _serialize_witness_statement(self, job: VoteValidationJob) -> dict[str, Any]:
        """Serialize witness statement to Kafka message format."""
        return {
            "vote_id": job.vote_id,
            "witness_archon_id": self.witness_id,
            "ruling": job.adjudication_result.ruling.value,
            "statement_text": job.adjudication_result.witness_statement,
            "retort_reason": job.adjudication_result.retort_reason,
            "deliberator_agreement": job.adjudication_result.deliberator_agreement,
        }
