"""Port interface for vote reconciliation.

Story 4.1: Implement Reconciliation Service
Pre-mortems: P1 (Consumer lag zero), P2 (Hard gate)
Red Team: V1 (DLQ fallback tracking), R3 (Lag check)

This port defines the interface for the reconciliation service that
ensures all votes are validated before session adjournment.
"""

from abc import ABC, abstractmethod
from typing import Protocol
from uuid import UUID

from src.domain.models.reconciliation import (
    ReconciliationConfig,
    ReconciliationResult,
    VoteValidationSummary,
)


class VoteStateProvider(Protocol):
    """Protocol for accessing vote state during reconciliation.

    This is typically implemented by the ConsensusAggregator.
    """

    def get_pending_vote_ids(self, session_id: UUID) -> list[UUID]:
        """Get IDs of votes still pending validation.

        Args:
            session_id: Session to query

        Returns:
            List of pending vote IDs
        """
        ...

    def get_validated_votes(self, session_id: UUID) -> list[VoteValidationSummary]:
        """Get summaries of validated votes.

        Args:
            session_id: Session to query

        Returns:
            List of vote validation summaries
        """
        ...

    def get_dlq_votes(self, session_id: UUID) -> list[VoteValidationSummary]:
        """Get summaries of votes in DLQ (V1).

        Args:
            session_id: Session to query

        Returns:
            List of DLQ vote summaries
        """
        ...


class LagProvider(Protocol):
    """Protocol for checking consumer lag (R3).

    This is typically implemented by the KafkaHealthChecker.
    """

    async def get_consumer_lag(self, topic: str) -> int:
        """Get total consumer lag for a topic.

        Args:
            topic: Kafka topic name

        Returns:
            Total lag across all partitions (0 = caught up)
        """
        ...


class ReconciliationProtocol(ABC):
    """Abstract protocol for vote reconciliation.

    The reconciliation service is responsible for:
    1. Tracking validation progress for all votes in a session
    2. Waiting for all validations to complete (await_all_validations)
    3. Applying DLQ fallbacks (V1)
    4. Enforcing the hard gate (P2) - raises error, doesn't warn

    Usage:
        reconciler = ReconciliationService(...)

        # At session adjournment
        try:
            result = await reconciler.await_all_validations(
                session_id=session.id,
                motion_id=motion.id,
                config=ReconciliationConfig(timeout_seconds=300),
            )

            if result.has_overrides:
                # Apply overrides and recompute tallies
                await apply_overrides(result)

        except ReconciliationIncompleteError:
            # P2: This propagates up - session HALTS
            raise
    """

    @abstractmethod
    async def await_all_validations(
        self,
        session_id: UUID,
        motion_id: UUID,
        expected_vote_count: int,
        config: ReconciliationConfig | None = None,
    ) -> ReconciliationResult:
        """Wait for all validations to complete.

        This is the main reconciliation gate (P1, P2, R3).

        Blocks until:
        - All expected votes are validated (pending_count == 0)
        - Consumer lag is zero (R3)
        - DLQ votes are accounted for (V1)

        Args:
            session_id: The deliberation session
            motion_id: The motion being voted on
            expected_vote_count: Number of votes expected
            config: Optional configuration (uses defaults if None)

        Returns:
            ReconciliationResult with all vote summaries

        Raises:
            ReconciliationIncompleteError: If timeout with pending votes (P2)
            ReconciliationLagError: If consumer lag non-zero (R3)

        Note:
            Per P2, errors are NOT caught - they propagate to halt the session.
        """
        ...

    @abstractmethod
    async def get_reconciliation_status(
        self,
        session_id: UUID,
        motion_id: UUID,
    ) -> ReconciliationResult:
        """Get current reconciliation status without waiting.

        Useful for monitoring progress during reconciliation.

        Args:
            session_id: The deliberation session
            motion_id: The motion being voted on

        Returns:
            Current ReconciliationResult (may have pending_count > 0)
        """
        ...

    @abstractmethod
    async def apply_dlq_fallbacks(
        self,
        session_id: UUID,
        motion_id: UUID,
    ) -> list[VoteValidationSummary]:
        """Apply DLQ fallbacks to optimistic values (V1).

        For votes that ended up in the DLQ, falls back to the
        optimistic (regex-parsed) choice and records the fallback.

        Each fallback is witnessed via KnightWitnessProtocol.

        Args:
            session_id: The deliberation session
            motion_id: The motion being voted on

        Returns:
            List of summaries for votes that used DLQ fallback
        """
        ...

    @abstractmethod
    def register_vote(
        self,
        session_id: UUID,
        motion_id: UUID,
        vote_id: UUID,
        archon_id: str,
        optimistic_choice: str,
    ) -> None:
        """Register a vote for tracking.

        Called when a vote is published for async validation.
        This tracks the vote so reconciliation knows what to expect.

        Args:
            session_id: The deliberation session
            motion_id: The motion being voted on
            vote_id: The vote identifier
            archon_id: Archon who cast the vote
            optimistic_choice: Initial regex-parsed choice
        """
        ...

    @abstractmethod
    def mark_validated(
        self,
        vote_id: UUID,
        validated_choice: str,
        confidence: float,
    ) -> None:
        """Mark a vote as validated.

        Called when consensus is reached for a vote.

        Args:
            vote_id: The vote identifier
            validated_choice: Final validated choice
            confidence: Validator confidence
        """
        ...

    @abstractmethod
    def mark_dlq(
        self,
        vote_id: UUID,
        failure_reason: str,
    ) -> None:
        """Mark a vote as routed to DLQ.

        Called when a vote fails validation and goes to DLQ.

        Args:
            vote_id: The vote identifier
            failure_reason: Why validation failed
        """
        ...
