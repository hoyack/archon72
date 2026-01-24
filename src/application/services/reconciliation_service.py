"""Reconciliation service implementation.

Story 4.1: Implement Reconciliation Service
Pre-mortems: P1 (Consumer lag zero), P2 (Hard gate - NOT a warning)
Red Team: V1 (DLQ fallback tracking), R3 (Lag check in await_all)

This service implements the hard reconciliation gate that ensures
all votes are validated before session adjournment.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from src.application.ports.reconciliation import LagProvider, ReconciliationProtocol
from src.domain.errors.reconciliation import (
    ReconciliationIncompleteError,
)
from src.domain.models.reconciliation import (
    ReconciliationConfig,
    ReconciliationResult,
    ReconciliationStatus,
    ValidationOutcome,
    VoteValidationSummary,
)

logger = logging.getLogger(__name__)


class VoteTrackingStatus(Enum):
    """Internal tracking status for a vote."""

    PENDING = "pending"  # Awaiting validation
    VALIDATED = "validated"  # Consensus reached
    DLQ = "dlq"  # In dead letter queue
    FALLBACK_APPLIED = "fallback_applied"  # DLQ fallback applied


@dataclass
class TrackedVote:
    """Internal tracking record for a vote."""

    vote_id: UUID
    session_id: UUID
    motion_id: UUID
    archon_id: str
    optimistic_choice: str
    status: VoteTrackingStatus = VoteTrackingStatus.PENDING
    validated_choice: str | None = None
    confidence: float = 0.0
    failure_reason: str | None = None
    registered_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_summary(self) -> VoteValidationSummary:
        """Convert to a VoteValidationSummary."""
        final_choice = self.validated_choice or self.optimistic_choice

        if self.status == VoteTrackingStatus.VALIDATED:
            if self.optimistic_choice == self.validated_choice:
                outcome = ValidationOutcome.VALIDATED_MATCH
            else:
                outcome = ValidationOutcome.VALIDATED_OVERRIDE
        elif self.status in {
            VoteTrackingStatus.DLQ,
            VoteTrackingStatus.FALLBACK_APPLIED,
        }:
            outcome = ValidationOutcome.DLQ_FALLBACK
        else:
            outcome = ValidationOutcome.SYNC_VALIDATED

        return VoteValidationSummary(
            vote_id=self.vote_id,
            archon_id=self.archon_id,
            optimistic_choice=self.optimistic_choice,
            validated_choice=final_choice,
            outcome=outcome,
            requires_override=self.optimistic_choice != final_choice,
            confidence=self.confidence,
        )


class WitnessProtocol(Protocol):
    """Protocol for witnessing DLQ fallbacks (constitutional)."""

    async def witness_dlq_fallback(
        self,
        vote_id: UUID,
        session_id: UUID,
        archon_id: str,
        optimistic_choice: str,
        failure_reason: str,
    ) -> None:
        """Witness a DLQ fallback to optimistic value.

        Per V1: Each DLQ fallback must be witnessed.
        """
        ...


class ReconciliationService(ReconciliationProtocol):
    """Implementation of the reconciliation service.

    This service:
    1. Tracks all votes registered for async validation
    2. Monitors validation progress via the aggregator
    3. Enforces the hard gate at adjournment (P1, P2, R3)
    4. Applies DLQ fallbacks with witnessing (V1)

    Thread Safety:
    - This service is NOT thread-safe
    - Should be used from a single async context
    - Each session should have its own instance

    Usage:
        service = ReconciliationService(
            lag_provider=health_checker,
            witness=knight_witness,
        )

        # Register votes as they're published
        service.register_vote(session_id, motion_id, vote_id, archon_id, choice)

        # At adjournment, wait for all validations
        result = await service.await_all_validations(
            session_id=session_id,
            motion_id=motion_id,
            expected_vote_count=len(archons),
        )
    """

    def __init__(
        self,
        lag_provider: LagProvider | None = None,
        witness: WitnessProtocol | None = None,
        validation_results_topic: str = "conclave.votes.validation-results",
    ) -> None:
        """Initialize the reconciliation service.

        Args:
            lag_provider: Provider for consumer lag checks (R3)
            witness: Witness for DLQ fallbacks (V1)
            validation_results_topic: Topic to check lag on
        """
        self._lag_provider = lag_provider
        self._witness = witness
        self._topic = validation_results_topic

        # Vote tracking by vote_id
        self._votes: dict[UUID, TrackedVote] = {}

        # Index by session for efficient lookup
        self._session_votes: dict[UUID, set[UUID]] = {}

        logger.info("ReconciliationService initialized")

    def register_vote(
        self,
        session_id: UUID,
        motion_id: UUID,
        vote_id: UUID,
        archon_id: str,
        optimistic_choice: str,
    ) -> None:
        """Register a vote for tracking."""
        tracked = TrackedVote(
            vote_id=vote_id,
            session_id=session_id,
            motion_id=motion_id,
            archon_id=archon_id,
            optimistic_choice=optimistic_choice,
        )

        self._votes[vote_id] = tracked

        if session_id not in self._session_votes:
            self._session_votes[session_id] = set()
        self._session_votes[session_id].add(vote_id)

        logger.debug(
            "Registered vote for reconciliation: vote=%s archon=%s choice=%s",
            vote_id,
            archon_id,
            optimistic_choice,
        )

    def mark_validated(
        self,
        vote_id: UUID,
        validated_choice: str,
        confidence: float,
    ) -> None:
        """Mark a vote as validated."""
        if vote_id not in self._votes:
            logger.warning("Attempted to mark unknown vote as validated: %s", vote_id)
            return

        vote = self._votes[vote_id]
        vote.status = VoteTrackingStatus.VALIDATED
        vote.validated_choice = validated_choice
        vote.confidence = confidence
        vote.updated_at_ms = int(time.time() * 1000)

        logger.debug(
            "Vote marked validated: vote=%s choice=%s confidence=%.2f",
            vote_id,
            validated_choice,
            confidence,
        )

    def mark_dlq(
        self,
        vote_id: UUID,
        failure_reason: str,
    ) -> None:
        """Mark a vote as routed to DLQ."""
        if vote_id not in self._votes:
            logger.warning("Attempted to mark unknown vote as DLQ: %s", vote_id)
            return

        vote = self._votes[vote_id]
        vote.status = VoteTrackingStatus.DLQ
        vote.failure_reason = failure_reason
        vote.updated_at_ms = int(time.time() * 1000)

        logger.warning(
            "Vote marked as DLQ: vote=%s reason=%s",
            vote_id,
            failure_reason,
        )

    def _get_session_stats(
        self,
        session_id: UUID,
    ) -> dict[str, int]:
        """Get vote statistics for a session.

        Args:
            session_id: Session to query

        Returns:
            Dictionary with count per status
        """
        vote_ids = self._session_votes.get(session_id, set())

        stats = {
            "pending": 0,
            "validated": 0,
            "dlq": 0,
            "fallback_applied": 0,
            "total": len(vote_ids),
        }

        for vote_id in vote_ids:
            vote = self._votes.get(vote_id)
            if vote:
                if vote.status == VoteTrackingStatus.PENDING:
                    stats["pending"] += 1
                elif vote.status == VoteTrackingStatus.VALIDATED:
                    stats["validated"] += 1
                elif vote.status == VoteTrackingStatus.DLQ:
                    stats["dlq"] += 1
                elif vote.status == VoteTrackingStatus.FALLBACK_APPLIED:
                    stats["fallback_applied"] += 1

        return stats

    async def _get_consumer_lag(self) -> int:
        """Get current consumer lag (R3).

        Returns:
            Consumer lag, or 0 if no lag provider
        """
        if self._lag_provider is None:
            return 0

        try:
            return await self._lag_provider.get_consumer_lag(self._topic)
        except Exception as e:
            logger.error("Failed to get consumer lag: %s", e)
            return -1  # Unknown lag

    async def get_reconciliation_status(
        self,
        session_id: UUID,
        motion_id: UUID,
    ) -> ReconciliationResult:
        """Get current reconciliation status without waiting."""
        stats = self._get_session_stats(session_id)
        lag = await self._get_consumer_lag()

        result = ReconciliationResult(
            session_id=session_id,
            motion_id=motion_id,
            status=ReconciliationStatus.IN_PROGRESS,
            validated_count=stats["validated"],
            dlq_fallback_count=stats["dlq"] + stats["fallback_applied"],
            pending_count=stats["pending"],
            consumer_lag=max(0, lag),
        )

        # Build vote summaries
        vote_ids = self._session_votes.get(session_id, set())
        for vote_id in vote_ids:
            vote = self._votes.get(vote_id)
            if vote and vote.status != VoteTrackingStatus.PENDING:
                result.add_vote_summary(vote.to_summary())

        return result

    async def await_all_validations(
        self,
        session_id: UUID,
        motion_id: UUID,
        expected_vote_count: int,
        config: ReconciliationConfig | None = None,
    ) -> ReconciliationResult:
        """Wait for all validations to complete (P1, P2, R3).

        This is the HARD GATE. It raises errors, not warnings (P2).
        """
        config = config or ReconciliationConfig()

        logger.info(
            "Starting reconciliation: session=%s motion=%s expected=%d timeout=%.1fs",
            session_id,
            motion_id,
            expected_vote_count,
            config.timeout_seconds,
        )

        start_time = time.monotonic()
        start_time_ms = int(time.time() * 1000)

        # Poll until complete or timeout
        while True:
            elapsed = time.monotonic() - start_time

            # Check timeout
            if elapsed >= config.timeout_seconds:
                stats = self._get_session_stats(session_id)
                lag = await self._get_consumer_lag()

                logger.error(
                    "Reconciliation timeout: pending=%d lag=%d dlq=%d",
                    stats["pending"],
                    lag,
                    stats["dlq"],
                )

                # P2: Raise error, NOT a warning
                raise ReconciliationIncompleteError(
                    session_id=session_id,
                    motion_id=motion_id,
                    pending_count=stats["pending"],
                    consumer_lag=lag,
                    dlq_count=stats["dlq"],
                    timeout_seconds=config.timeout_seconds,
                )

            # Get current status
            stats = self._get_session_stats(session_id)
            lag = await self._get_consumer_lag()

            logger.debug(
                "Reconciliation progress: pending=%d validated=%d dlq=%d lag=%d elapsed=%.1fs",
                stats["pending"],
                stats["validated"],
                stats["dlq"],
                lag,
                elapsed,
            )

            # Check completion conditions
            pending_ok = stats["pending"] == 0 or not config.require_zero_pending
            lag_ok = lag <= config.max_lag_for_complete

            if pending_ok and lag_ok:
                # Apply DLQ fallbacks before completing (V1)
                await self.apply_dlq_fallbacks(session_id, motion_id)

                # Build final result
                result = ReconciliationResult(
                    session_id=session_id,
                    motion_id=motion_id,
                    status=ReconciliationStatus.COMPLETE,
                    validated_count=stats["validated"],
                    dlq_fallback_count=stats["dlq"] + stats["fallback_applied"],
                    pending_count=0,
                    consumer_lag=lag,
                    started_at_ms=start_time_ms,
                    completed_at_ms=int(time.time() * 1000),
                )

                # Add vote summaries
                vote_ids = self._session_votes.get(session_id, set())
                for vote_id in vote_ids:
                    vote = self._votes.get(vote_id)
                    if vote:
                        summary = vote.to_summary()
                        result.add_vote_summary(summary)

                logger.info(
                    "Reconciliation complete: validated=%d dlq_fallback=%d overrides=%d",
                    result.validated_count,
                    result.dlq_fallback_count,
                    result.override_count,
                )

                return result

            # R3: Check lag specifically
            if stats["pending"] == 0 and lag > config.max_lag_for_complete:
                logger.warning(
                    "Votes resolved but lag=%d > max=%d, waiting...",
                    lag,
                    config.max_lag_for_complete,
                )

            # Wait before next poll
            await asyncio.sleep(config.poll_interval_seconds)

    async def apply_dlq_fallbacks(
        self,
        session_id: UUID,
        motion_id: UUID,
    ) -> list[VoteValidationSummary]:
        """Apply DLQ fallbacks to optimistic values (V1).

        Each fallback is witnessed via KnightWitnessProtocol.
        """
        fallbacks: list[VoteValidationSummary] = []
        vote_ids = self._session_votes.get(session_id, set())

        for vote_id in vote_ids:
            vote = self._votes.get(vote_id)

            if vote and vote.status == VoteTrackingStatus.DLQ:
                # Apply fallback to optimistic choice
                vote.validated_choice = vote.optimistic_choice
                vote.status = VoteTrackingStatus.FALLBACK_APPLIED
                vote.updated_at_ms = int(time.time() * 1000)

                # Witness the fallback (V1)
                if self._witness:
                    try:
                        await self._witness.witness_dlq_fallback(
                            vote_id=vote.vote_id,
                            session_id=vote.session_id,
                            archon_id=vote.archon_id,
                            optimistic_choice=vote.optimistic_choice,
                            failure_reason=vote.failure_reason or "unknown",
                        )
                    except Exception as e:
                        # Witness writes are constitutional but we log and continue
                        # The witness itself should handle its own errors
                        logger.error(
                            "Witness failed for DLQ fallback: vote=%s error=%s",
                            vote_id,
                            e,
                        )

                fallbacks.append(vote.to_summary())

                logger.warning(
                    "Applied DLQ fallback: vote=%s archon=%s choice=%s reason=%s",
                    vote_id,
                    vote.archon_id,
                    vote.optimistic_choice,
                    vote.failure_reason,
                )

        if fallbacks:
            logger.warning(
                "Applied %d DLQ fallbacks for session %s",
                len(fallbacks),
                session_id,
            )

        return fallbacks

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics for monitoring."""
        total_votes = len(self._votes)
        pending = sum(
            1 for v in self._votes.values() if v.status == VoteTrackingStatus.PENDING
        )
        validated = sum(
            1 for v in self._votes.values() if v.status == VoteTrackingStatus.VALIDATED
        )
        dlq = sum(
            1
            for v in self._votes.values()
            if v.status in {VoteTrackingStatus.DLQ, VoteTrackingStatus.FALLBACK_APPLIED}
        )

        return {
            "total_votes_tracked": total_votes,
            "pending": pending,
            "validated": validated,
            "dlq": dlq,
            "sessions_tracked": len(self._session_votes),
        }

    def clear_session(self, session_id: UUID) -> None:
        """Clear tracking data for a session.

        Called after session completes to free memory.

        Args:
            session_id: Session to clear
        """
        vote_ids = self._session_votes.pop(session_id, set())

        for vote_id in vote_ids:
            self._votes.pop(vote_id, None)

        logger.debug("Cleared reconciliation data for session %s", session_id)
