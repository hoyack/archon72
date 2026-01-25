"""Async vote validation models and pipeline."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Protocol

import structlog

from src.domain.errors.agent import AgentInvocationError
from src.domain.models.conclave import VoteChoice

logger = structlog.get_logger(__name__)


class KafkaPublisherProtocol(Protocol):
    """Protocol for publishing audit events."""

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish a message to a topic."""
        ...


class ReconciliationTimeoutError(RuntimeError):
    """Raised when async validation drain and reconciliation times out."""

    def __init__(
        self, message: str, pending_count: int, timeout_seconds: float
    ) -> None:
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
    vote_choice: VoteChoice | None
    confidence: float
    raw_response: str
    parse_success: bool
    latency_ms: int
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdjudicationResult:
    """Result from witness adjudication phase."""

    consensus: bool
    final_vote: VoteChoice
    ruling: WitnessRuling
    retort_reason: str | None
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
    adjudication_result: AdjudicationResult | None = None
    completed: asyncio.Event = field(default_factory=asyncio.Event)
    error: str | None = None

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

        logger.info(
            "Vote submitted for validation",
            vote_id=vote_id,
            archon_id=archon_id,
            archon_name=archon_name,
            optimistic_choice=optimistic_choice.value,
            pending_count=len(self.pending_jobs),
        )

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
            logger.error(
                "Validation pipeline failed",
                vote_id=job.vote_id,
                archon_name=job.archon_name,
                error=str(exc),
            )
        finally:
            job.completed.set()
            self.pending_jobs.pop(job.vote_id, None)
            self.completed_jobs[job.vote_id] = job
            await self.completed_queue.put(job)
            self.total_completed += 1
            if job.override_required:
                self.total_overrides += 1
                logger.warning(
                    "Vote override required",
                    vote_id=job.vote_id,
                    archon_name=job.archon_name,
                    optimistic=job.optimistic_choice.value,
                    validated=job.adjudication_result.final_vote.value
                    if job.adjudication_result
                    else "unknown",
                )
            else:
                logger.info(
                    "Validation complete",
                    vote_id=job.vote_id,
                    archon_name=job.archon_name,
                    validated_choice=job.adjudication_result.final_vote.value
                    if job.adjudication_result
                    else "unknown",
                    consensus=job.adjudication_result.consensus
                    if job.adjudication_result
                    else False,
                )

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

        # Log deliberator result
        if deliberator_result.error:
            logger.warning(
                "Deliberator failed",
                vote_id=job.vote_id,
                archon_name=job.archon_name,
                deliberator=deliberator_type,
                error=deliberator_result.error,
                latency_ms=latency_ms,
            )
        else:
            logger.debug(
                "Deliberator completed",
                vote_id=job.vote_id,
                archon_name=job.archon_name,
                deliberator=deliberator_type,
                vote_choice=deliberator_result.vote_choice.value
                if deliberator_result.vote_choice
                else None,
                confidence=deliberator_result.confidence,
                latency_ms=latency_ms,
            )

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
        """Determine the validated vote and record the witness ruling.

        3-Archon Protocol (ADR-004):
          - Determination: TWO secretaries must agree on the vote choice.
          - Witness: observes and records agreement/dissent (cannot change outcome).

        Safety rule:
          - Never override to ABSTAIN due to parsing failures. If validation is
            inconclusive, fall back to the optimistic vote (no override).
        """
        secretary_results: dict[str, DeliberatorResult] = {
            dtype: result
            for dtype, result in job.deliberator_results.items()
            if dtype in ("text_analysis", "json_validation")
        }
        secretary_votes: dict[str, VoteChoice] = {
            dtype: result.vote_choice
            for dtype, result in secretary_results.items()
            if result.vote_choice is not None
        }

        witness_result = job.deliberator_results.get("witness_confirm")
        witness_vote = witness_result.vote_choice if witness_result else None

        deliberator_agreement: dict[str, VoteChoice | str] = {
            dtype: choice.value for dtype, choice in secretary_votes.items()
        }
        if witness_vote is not None:
            deliberator_agreement["witness_confirm"] = witness_vote.value

        unique_secretary_votes = set(secretary_votes.values())
        has_secretary_consensus = (
            len(secretary_votes) == 2 and len(unique_secretary_votes) == 1
        )

        if has_secretary_consensus:
            consensus_vote = next(iter(unique_secretary_votes))
            if witness_vote == consensus_vote:
                ruling = WitnessRuling.CONFIRMED
                retort_reason = None
                witness_statement = (
                    f"Witness confirms the secretaries' determination: "
                    f"{consensus_vote.value}."
                )
            else:
                ruling = WitnessRuling.RETORT
                retort_reason = (
                    "witness_unavailable" if witness_vote is None else "witness_dissent"
                )
                witness_statement = (
                    f"Witness retorts the secretaries' determination "
                    f"({consensus_vote.value}). "
                    f"Witness read: {witness_vote.value if witness_vote else 'unknown'}."
                )

            logger.info(
                "Adjudication: secretary consensus reached",
                vote_id=job.vote_id,
                archon_name=job.archon_name,
                final_vote=consensus_vote.value,
                witness_ruling=ruling.value,
                retort_reason=retort_reason,
            )

            return AdjudicationResult(
                consensus=True,
                final_vote=consensus_vote,
                ruling=ruling,
                retort_reason=retort_reason,
                witness_statement=witness_statement,
                deliberator_agreement=deliberator_agreement,
            )

        secretary_text = secretary_votes.get("text_analysis")
        secretary_json = secretary_votes.get("json_validation")
        witness_statement = (
            "Validation retort: no secretary consensus. "
            f"text_analysis={secretary_text.value if secretary_text else 'unknown'}, "
            f"json_validation={secretary_json.value if secretary_json else 'unknown'}. "
            f"Preserving optimistic vote: {job.optimistic_choice.value}."
        )

        logger.warning(
            "Adjudication: no secretary consensus - preserving optimistic vote",
            vote_id=job.vote_id,
            archon_name=job.archon_name,
            text_analysis=secretary_text.value if secretary_text else "unknown",
            json_validation=secretary_json.value if secretary_json else "unknown",
            optimistic_preserved=job.optimistic_choice.value,
        )

        return AdjudicationResult(
            consensus=False,
            final_vote=job.optimistic_choice,
            ruling=WitnessRuling.RETORT,
            retort_reason="no_secretary_consensus",
            witness_statement=witness_statement,
            deliberator_agreement=deliberator_agreement,
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

    async def drain(self, timeout_seconds: float = 300.0) -> list[VoteValidationJob]:
        """Wait for all pending validations to complete."""
        if not self.pending_jobs:
            logger.info(
                "Validation drain: no pending jobs",
                total_completed=self.total_completed,
                overrides_required=self.total_overrides,
            )
            return list(self.completed_jobs.values())

        pending_count = len(self.pending_jobs)
        logger.info(
            "Validation drain started",
            pending_count=pending_count,
            timeout_seconds=timeout_seconds,
        )

        pending_events = [job.completed for job in self.pending_jobs.values()]

        try:
            await asyncio.wait_for(
                asyncio.gather(*[event.wait() for event in pending_events]),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            logger.error(
                "Validation drain timed out",
                pending_count=len(self.pending_jobs),
                timeout_seconds=timeout_seconds,
            )
            raise ReconciliationTimeoutError(
                message=(
                    f"Validation drain timed out after {timeout_seconds}s; "
                    f"{len(self.pending_jobs)} jobs still pending."
                ),
                pending_count=len(self.pending_jobs),
                timeout_seconds=timeout_seconds,
            ) from exc

        # Log summary statistics
        consensus_count = sum(
            1
            for job in self.completed_jobs.values()
            if job.adjudication_result and job.adjudication_result.consensus
        )
        retort_count = sum(
            1
            for job in self.completed_jobs.values()
            if job.adjudication_result
            and job.adjudication_result.ruling == WitnessRuling.RETORT
        )

        logger.info(
            "Validation drain complete",
            total_validated=self.total_completed,
            consensus_reached=consensus_count,
            witness_retorts=retort_count,
            overrides_required=self.total_overrides,
        )

        return list(self.completed_jobs.values())

    def get_stats(self) -> dict[str, int]:
        """Return current validator statistics."""
        return {
            "total_submitted": self.total_submitted,
            "total_completed": self.total_completed,
            "pending": len(self.pending_jobs),
            "overrides_required": self.total_overrides,
        }

    def _parse_vote_choice(self, value: Any) -> VoteChoice | None:
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
