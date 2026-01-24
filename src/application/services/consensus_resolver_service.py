"""Consensus resolver service implementation (Story 2A.6, FR-11.5, FR-11.6, Story 3.6).

This module implements the 2-of-3 supermajority consensus resolution
algorithm for the Three Fates deliberation system.

Constitutional Constraints:
- AT-6: Deliberation is collective judgment, not unilateral decision
- NFR-10.3: Consensus determinism - 100% reproducible
- CT-12: Witnessing creates accountability
- FR-3.6: System SHALL track acknowledgment rate metrics per Marquis
"""

from __future__ import annotations

from uuid import UUID

import structlog

from src.application.ports.acknowledgment_rate_metrics import (
    AcknowledgmentRateMetricsProtocol,
)
from src.application.ports.consensus_resolver import ConsensusResolverProtocol
from src.domain.errors.deliberation import ConsensusNotReachedError
from src.domain.models.consensus_result import (
    CONSENSUS_ALGORITHM_VERSION,
    REQUIRED_VOTE_COUNT,
    SUPERMAJORITY_THRESHOLD,
    ConsensusResult,
    ConsensusStatus,
    VoteValidationResult,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)

logger = structlog.get_logger(__name__)


class ConsensusResolverService(ConsensusResolverProtocol):
    """Implementation of 2-of-3 supermajority consensus resolution (FR-11.5, FR-11.6, FR-3.6).

    This service implements a deterministic algorithm for resolving
    consensus from archon votes. The algorithm is stateless and pure -
    given the same inputs, it always produces the same outputs (NFR-10.3).

    Optionally records acknowledgment rate metrics per FR-3.6.

    Constitutional Constraints:
    - AT-6: Requires 2-of-3 agreement for any outcome
    - NFR-10.3: Deterministic, reproducible results
    - CT-12: Complete attribution for witnessing
    - FR-3.6: System SHALL track acknowledgment rate metrics per Marquis
    """

    def __init__(
        self,
        metrics_collector: AcknowledgmentRateMetricsProtocol | None = None,
    ) -> None:
        """Initialize the consensus resolver service.

        Args:
            metrics_collector: Optional metrics collector for tracking
                acknowledgment rate metrics per FR-3.6.
        """
        self._log = logger.bind(component="consensus_resolver")
        self._metrics_collector = metrics_collector

    def validate_votes(
        self,
        session: DeliberationSession,
        votes: dict[UUID, DeliberationOutcome],
    ) -> VoteValidationResult:
        """Validate votes before consensus resolution (FR-11.5).

        Validates that:
        - All 3 assigned archons have voted
        - All voters are assigned to the session
        - All votes reference valid outcomes

        Args:
            session: The deliberation session with assigned archons.
            votes: Map of archon_id to their vote.

        Returns:
            VoteValidationResult indicating whether votes are valid.
        """
        log = self._log.bind(
            session_id=str(session.session_id),
            petition_id=str(session.petition_id),
            vote_count=len(votes),
        )

        active_set = set(session.current_active_archons)
        voter_set = set(votes.keys())

        # Check for unauthorized voters
        unauthorized = voter_set - active_set
        if unauthorized:
            log.warning(
                "unauthorized_voters_detected",
                unauthorized_count=len(unauthorized),
            )
            return VoteValidationResult.unauthorized_voter(tuple(unauthorized))

        # Check for missing votes
        missing = active_set - voter_set
        if missing:
            log.info(
                "missing_votes_detected",
                missing_count=len(missing),
            )
            return VoteValidationResult.missing_votes(tuple(missing))

        # Validate all outcomes are valid DeliberationOutcome values
        valid_outcomes = {outcome.value for outcome in DeliberationOutcome}
        for archon_id, vote in votes.items():
            if vote.value not in valid_outcomes:
                log.warning(
                    "invalid_outcome_detected",
                    archon_id=str(archon_id),
                    outcome=str(vote),
                )
                return VoteValidationResult.invalid_outcome(
                    f"Invalid outcome '{vote}' from archon {archon_id}"
                )

        log.debug("votes_validated_successfully")
        return VoteValidationResult.valid()

    def resolve_consensus(
        self,
        session: DeliberationSession,
        votes: dict[UUID, DeliberationOutcome],
    ) -> ConsensusResult:
        """Resolve 2-of-3 supermajority consensus from votes (FR-11.5, FR-11.6).

        Applies the supermajority algorithm to determine if consensus is
        reached. The algorithm is deterministic: given the same session
        and votes, it always produces the same result (NFR-10.3).

        Algorithm:
        1. Validate votes (must pass validation first)
        2. Count votes per outcome
        3. Check if any outcome has >= 2 votes
        4. Identify majority archons and any dissenter

        Args:
            session: The deliberation session with assigned archons.
            votes: Map of archon_id to their vote (must have exactly 3 votes).

        Returns:
            ConsensusResult with outcome, vote distribution, and attribution.

        Raises:
            ValueError: If votes are invalid (call validate_votes first).
            ConsensusNotReachedError: If no outcome achieves 2-of-3 majority.
        """
        log = self._log.bind(
            session_id=str(session.session_id),
            petition_id=str(session.petition_id),
        )

        # Step 1: Validate votes
        validation = self.validate_votes(session, votes)
        if not validation.is_valid:
            log.error(
                "vote_validation_failed",
                status=validation.status.value,
                error=validation.error_message,
            )
            raise ValueError(
                f"Vote validation failed: {validation.error_message}. "
                f"Status: {validation.status.value}"
            )

        # Step 2: Count votes per outcome
        vote_counts: dict[DeliberationOutcome, list[UUID]] = {}
        for archon_id, outcome in votes.items():
            if outcome not in vote_counts:
                vote_counts[outcome] = []
            vote_counts[outcome].append(archon_id)

        # Create distribution dict for result
        vote_distribution = {
            outcome.value: len(voters) for outcome, voters in vote_counts.items()
        }

        log.debug(
            "votes_counted",
            distribution=vote_distribution,
        )

        # Step 3: Find outcome with supermajority (>= 2 votes)
        winning_outcome: DeliberationOutcome | None = None
        majority_archon_ids: list[UUID] = []
        dissent_archon_id: UUID | None = None

        for outcome, voters in vote_counts.items():
            if len(voters) >= SUPERMAJORITY_THRESHOLD:
                winning_outcome = outcome
                majority_archon_ids = voters
                break

        # Step 4: Determine consensus status and identify dissenter
        if winning_outcome is None:
            # No supermajority - this is an edge case (all 3 vote differently)
            log.warning(
                "consensus_not_reached",
                distribution=vote_distribution,
            )
            raise ConsensusNotReachedError(
                message="No outcome achieved 2-of-3 supermajority",
                votes_received=len(votes),
                votes_required=SUPERMAJORITY_THRESHOLD,
            )

        # Check if unanimous (3-0) or split (2-1)
        if len(majority_archon_ids) == REQUIRED_VOTE_COUNT:
            status = ConsensusStatus.UNANIMOUS
            log.info(
                "consensus_unanimous",
                outcome=winning_outcome.value,
            )
        else:
            status = ConsensusStatus.ACHIEVED
            # Find the dissenting archon
            for outcome, voters in vote_counts.items():
                if outcome != winning_outcome and len(voters) == 1:
                    dissent_archon_id = voters[0]
                    break
            log.info(
                "consensus_achieved_with_dissent",
                outcome=winning_outcome.value,
                dissent_archon_id=str(dissent_archon_id) if dissent_archon_id else None,
            )

        result = ConsensusResult(
            session_id=session.session_id,
            petition_id=session.petition_id,
            status=status,
            winning_outcome=winning_outcome.value,
            vote_distribution=vote_distribution,
            majority_archon_ids=tuple(majority_archon_ids),
            dissent_archon_id=dissent_archon_id,
            algorithm_version=CONSENSUS_ALGORITHM_VERSION,
        )

        # Record acknowledgment rate metrics (FR-3.6)
        if self._metrics_collector is not None:
            archon_votes = {
                archon_id: outcome.value for archon_id, outcome in votes.items()
            }
            self._metrics_collector.record_deliberation_completion(archon_votes)
            log.debug(
                "recorded_acknowledgment_rate_metrics",
                archon_count=len(archon_votes),
            )

        return result

    def can_reach_consensus(
        self,
        votes: dict[UUID, DeliberationOutcome],
    ) -> bool:
        """Check if votes can mathematically reach consensus (helper method).

        With 3 archons and multiple possible outcomes, consensus is always
        reachable unless all 3 archons vote for different outcomes.

        Args:
            votes: Map of archon_id to their vote.

        Returns:
            True if votes can achieve 2-of-3 majority, False otherwise.
        """
        if len(votes) != REQUIRED_VOTE_COUNT:
            return False

        # Count votes per outcome
        vote_counts: dict[DeliberationOutcome, int] = {}
        for outcome in votes.values():
            vote_counts[outcome] = vote_counts.get(outcome, 0) + 1

        # Check if any outcome has >= 2 votes
        return any(count >= SUPERMAJORITY_THRESHOLD for count in vote_counts.values())
