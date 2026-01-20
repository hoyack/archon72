"""Consensus resolver stub for testing (Story 2A.6, FR-11.5, FR-11.6).

This module provides a configurable stub implementation of the
ConsensusResolverProtocol for use in testing.

WARNING: This stub is NOT for production use.
Production implementation is in src/application/services/consensus_resolver_service.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import UUID

from src.application.ports.consensus_resolver import ConsensusResolverProtocol
from src.domain.errors.deliberation import ConsensusNotReachedError
from src.domain.models.consensus_result import (
    CONSENSUS_ALGORITHM_VERSION,
    REQUIRED_VOTE_COUNT,
    SUPERMAJORITY_THRESHOLD,
    ConsensusResult,
    ConsensusStatus,
    VoteValidationResult,
    VoteValidationStatus,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)


class ConsensusResolverOperation(Enum):
    """Operations tracked by the stub."""

    VALIDATE_VOTES = "validate_votes"
    RESOLVE_CONSENSUS = "resolve_consensus"
    CAN_REACH_CONSENSUS = "can_reach_consensus"


@dataclass
class ResolverCall:
    """Record of a call to the stub."""

    operation: ConsensusResolverOperation
    session_id: UUID
    petition_id: UUID
    votes: dict[UUID, DeliberationOutcome]


class ConsensusResolverStub(ConsensusResolverProtocol):
    """Configurable stub for ConsensusResolverProtocol.

    This stub supports multiple operation modes for testing different scenarios:
    - default: Uses real supermajority logic
    - force_unanimous: Always returns unanimous consensus
    - force_split: Always returns 2-1 split consensus
    - force_invalid: Always returns invalid votes result
    - force_no_consensus: Always raises ConsensusNotReachedError

    Usage:
        # Default mode - real logic
        stub = ConsensusResolverStub()

        # Force unanimous result
        stub = ConsensusResolverStub.force_unanimous(outcome=DeliberationOutcome.ACKNOWLEDGE)

        # Force 2-1 split
        stub = ConsensusResolverStub.force_split(
            outcome=DeliberationOutcome.REFER,
            dissenter_index=2
        )

        # Check call history
        assert len(stub.calls) == 1
        assert stub.calls[0].operation == ConsensusResolverOperation.RESOLVE_CONSENSUS
    """

    def __init__(self) -> None:
        """Initialize stub in default mode."""
        self._calls: list[ResolverCall] = []
        self._force_unanimous: bool = False
        self._force_split: bool = False
        self._forced_outcome: Optional[DeliberationOutcome] = None
        self._forced_dissenter_index: int = 2  # Default to third archon
        self._force_invalid: bool = False
        self._force_invalid_status: VoteValidationStatus = VoteValidationStatus.MISSING_VOTES
        self._force_no_consensus: bool = False

    @classmethod
    def force_unanimous(
        cls,
        outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
    ) -> ConsensusResolverStub:
        """Create stub that always returns unanimous consensus.

        Args:
            outcome: The outcome all archons will vote for.

        Returns:
            Configured stub instance.
        """
        stub = cls()
        stub._force_unanimous = True
        stub._forced_outcome = outcome
        return stub

    @classmethod
    def force_split(
        cls,
        outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
        dissenter_index: int = 2,
    ) -> ConsensusResolverStub:
        """Create stub that always returns 2-1 split consensus.

        Args:
            outcome: The outcome that will win (2 votes).
            dissenter_index: Index (0-2) of the archon who dissents.

        Returns:
            Configured stub instance.
        """
        stub = cls()
        stub._force_split = True
        stub._forced_outcome = outcome
        stub._forced_dissenter_index = dissenter_index
        return stub

    @classmethod
    def force_invalid(
        cls,
        status: VoteValidationStatus = VoteValidationStatus.MISSING_VOTES,
    ) -> ConsensusResolverStub:
        """Create stub that always returns invalid votes.

        Args:
            status: The validation status to return.

        Returns:
            Configured stub instance.
        """
        stub = cls()
        stub._force_invalid = True
        stub._force_invalid_status = status
        return stub

    @classmethod
    def force_no_consensus(cls) -> ConsensusResolverStub:
        """Create stub that always raises ConsensusNotReachedError.

        Returns:
            Configured stub instance.
        """
        stub = cls()
        stub._force_no_consensus = True
        return stub

    @property
    def calls(self) -> list[ResolverCall]:
        """Get list of calls made to the stub."""
        return self._calls.copy()

    def reset(self) -> None:
        """Reset call history."""
        self._calls.clear()

    def validate_votes(
        self,
        session: DeliberationSession,
        votes: dict[UUID, DeliberationOutcome],
    ) -> VoteValidationResult:
        """Validate votes - stub implementation.

        Args:
            session: The deliberation session.
            votes: Map of archon_id to their vote.

        Returns:
            VoteValidationResult based on stub configuration.
        """
        self._calls.append(
            ResolverCall(
                operation=ConsensusResolverOperation.VALIDATE_VOTES,
                session_id=session.session_id,
                petition_id=session.petition_id,
                votes=dict(votes),
            )
        )

        if self._force_invalid:
            if self._force_invalid_status == VoteValidationStatus.MISSING_VOTES:
                return VoteValidationResult.missing_votes(
                    (session.assigned_archons[0],)
                )
            elif self._force_invalid_status == VoteValidationStatus.UNAUTHORIZED_VOTER:
                return VoteValidationResult.unauthorized_voter(
                    (UUID("00000000-0000-0000-0000-000000000001"),)
                )
            else:
                return VoteValidationResult.invalid_outcome("Forced invalid outcome")

        # Default: use real validation logic
        assigned_set = set(session.assigned_archons)
        voter_set = set(votes.keys())

        unauthorized = voter_set - assigned_set
        if unauthorized:
            return VoteValidationResult.unauthorized_voter(tuple(unauthorized))

        missing = assigned_set - voter_set
        if missing:
            return VoteValidationResult.missing_votes(tuple(missing))

        return VoteValidationResult.valid()

    def resolve_consensus(
        self,
        session: DeliberationSession,
        votes: dict[UUID, DeliberationOutcome],
    ) -> ConsensusResult:
        """Resolve consensus - stub implementation.

        Args:
            session: The deliberation session.
            votes: Map of archon_id to their vote.

        Returns:
            ConsensusResult based on stub configuration.

        Raises:
            ConsensusNotReachedError: If force_no_consensus mode is enabled.
        """
        self._calls.append(
            ResolverCall(
                operation=ConsensusResolverOperation.RESOLVE_CONSENSUS,
                session_id=session.session_id,
                petition_id=session.petition_id,
                votes=dict(votes),
            )
        )

        if self._force_no_consensus:
            raise ConsensusNotReachedError(
                message="Forced no consensus (stub)",
                votes_received=len(votes),
                votes_required=SUPERMAJORITY_THRESHOLD,
            )

        archon_list = list(session.assigned_archons)
        outcome = self._forced_outcome or DeliberationOutcome.ACKNOWLEDGE

        if self._force_unanimous:
            return ConsensusResult(
                session_id=session.session_id,
                petition_id=session.petition_id,
                status=ConsensusStatus.UNANIMOUS,
                winning_outcome=outcome.value,
                vote_distribution={outcome.value: 3},
                majority_archon_ids=tuple(archon_list),
                dissent_archon_id=None,
                algorithm_version=CONSENSUS_ALGORITHM_VERSION,
            )

        if self._force_split:
            dissenter = archon_list[self._forced_dissenter_index]
            majority = [a for a in archon_list if a != dissenter]
            # Find a different outcome for dissenter
            other_outcomes = [o for o in DeliberationOutcome if o != outcome]
            dissent_outcome = other_outcomes[0] if other_outcomes else outcome

            return ConsensusResult(
                session_id=session.session_id,
                petition_id=session.petition_id,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome=outcome.value,
                vote_distribution={
                    outcome.value: 2,
                    dissent_outcome.value: 1,
                },
                majority_archon_ids=tuple(majority),
                dissent_archon_id=dissenter,
                algorithm_version=CONSENSUS_ALGORITHM_VERSION,
            )

        # Default: use real supermajority logic
        vote_counts: dict[DeliberationOutcome, list[UUID]] = {}
        for archon_id, vote_outcome in votes.items():
            if vote_outcome not in vote_counts:
                vote_counts[vote_outcome] = []
            vote_counts[vote_outcome].append(archon_id)

        vote_distribution = {
            o.value: len(v) for o, v in vote_counts.items()
        }

        # Find winner
        for outcome_key, voters in vote_counts.items():
            if len(voters) >= SUPERMAJORITY_THRESHOLD:
                if len(voters) == REQUIRED_VOTE_COUNT:
                    return ConsensusResult(
                        session_id=session.session_id,
                        petition_id=session.petition_id,
                        status=ConsensusStatus.UNANIMOUS,
                        winning_outcome=outcome_key.value,
                        vote_distribution=vote_distribution,
                        majority_archon_ids=tuple(voters),
                        dissent_archon_id=None,
                        algorithm_version=CONSENSUS_ALGORITHM_VERSION,
                    )
                else:
                    # Find dissenter
                    dissent_id = None
                    for o, v in vote_counts.items():
                        if o != outcome_key and len(v) == 1:
                            dissent_id = v[0]
                            break
                    return ConsensusResult(
                        session_id=session.session_id,
                        petition_id=session.petition_id,
                        status=ConsensusStatus.ACHIEVED,
                        winning_outcome=outcome_key.value,
                        vote_distribution=vote_distribution,
                        majority_archon_ids=tuple(voters),
                        dissent_archon_id=dissent_id,
                        algorithm_version=CONSENSUS_ALGORITHM_VERSION,
                    )

        raise ConsensusNotReachedError(
            message="No outcome achieved 2-of-3 supermajority",
            votes_received=len(votes),
            votes_required=SUPERMAJORITY_THRESHOLD,
        )

    def can_reach_consensus(
        self,
        votes: dict[UUID, DeliberationOutcome],
    ) -> bool:
        """Check if consensus can be reached - stub implementation.

        Args:
            votes: Map of archon_id to their vote.

        Returns:
            True if votes can achieve 2-of-3 majority.
        """
        # Note: We don't have session here, so create a minimal call record
        self._calls.append(
            ResolverCall(
                operation=ConsensusResolverOperation.CAN_REACH_CONSENSUS,
                session_id=UUID("00000000-0000-0000-0000-000000000000"),
                petition_id=UUID("00000000-0000-0000-0000-000000000000"),
                votes=dict(votes),
            )
        )

        if len(votes) != REQUIRED_VOTE_COUNT:
            return False

        vote_counts: dict[DeliberationOutcome, int] = {}
        for outcome in votes.values():
            vote_counts[outcome] = vote_counts.get(outcome, 0) + 1

        return any(count >= SUPERMAJORITY_THRESHOLD for count in vote_counts.values())
