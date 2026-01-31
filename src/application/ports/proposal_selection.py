"""Port interface for the Duke Proposal Selection Pipeline.

The 11 Executive Presidents review, score, rank, and deliberate on
Duke implementation proposals to select a winning proposal for execution.

Pipeline Position:
    Legislative (Motion) -> Executive (RFP) -> Administrative (Duke Proposals)
      -> Executive (Proposal Selection) <- THIS
      -> Administrative (Execution)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.duke_proposal import DukeProposal
    from src.domain.models.proposal_selection import (
        ProposalNovelty,
        ProposalScore,
        SelectionDeliberation,
    )


@dataclass
class SelectionContext:
    """Context for the proposal selection pipeline."""

    cycle_id: str
    motion_id: str
    rfp_id: str
    mandate_id: str
    motion_title: str
    evaluation_criteria: list[dict] = field(default_factory=list)
    iteration_number: int = 1
    max_iterations: int = 3
    finalist_count: int = 5
    minimum_score_threshold: float = 4.0


class ProposalScorerProtocol(ABC):
    """Protocol for scoring Duke proposals.

    Implementations provide LLM-powered scoring, novelty detection,
    and panel deliberation capabilities.
    """

    @abstractmethod
    async def score_proposal(
        self,
        president_name: str,
        president_role: str,
        president_backstory: str,
        proposal: DukeProposal,
        context: SelectionContext,
    ) -> ProposalScore:
        """One President scores one Duke proposal.

        Args:
            president_name: Name of the scoring President
            president_role: Role title of the President
            president_backstory: President's backstory for persona grounding
            proposal: The Duke proposal to score
            context: Selection pipeline context

        Returns:
            ProposalScore with 6 dimension scores and qualitative feedback
        """
        ...

    @abstractmethod
    async def batch_score_proposals(
        self,
        president_name: str,
        president_role: str,
        president_backstory: str,
        proposals: list[DukeProposal],
        context: SelectionContext,
    ) -> list[ProposalScore]:
        """One President scores all proposals sequentially.

        Args:
            president_name: Name of the scoring President
            president_role: Role title of the President
            president_backstory: President's backstory for persona grounding
            proposals: List of Duke proposals to score
            context: Selection pipeline context

        Returns:
            List of ProposalScore (one per proposal)
        """
        ...

    @abstractmethod
    async def detect_novelty(
        self,
        proposals: list[DukeProposal],
        context: SelectionContext,
    ) -> list[ProposalNovelty]:
        """Detect novelty across the field of proposals.

        Args:
            proposals: All Duke proposals to analyze for novelty
            context: Selection pipeline context

        Returns:
            List of ProposalNovelty (one per proposal)
        """
        ...

    @abstractmethod
    async def run_deliberation(
        self,
        panelist_names: list[str],
        panelist_roles: list[str],
        panelist_backstories: list[str],
        finalist_proposals: list[DukeProposal],
        rankings_summary: str,
        context: SelectionContext,
    ) -> SelectionDeliberation:
        """Run panel deliberation on finalist proposals.

        Args:
            panelist_names: Names of all participating Presidents
            panelist_roles: Role titles of all participating Presidents
            panelist_backstories: Backstories for persona grounding
            finalist_proposals: Top-N proposals for deliberation
            rankings_summary: Formatted summary of rankings for context
            context: Selection pipeline context

        Returns:
            SelectionDeliberation with recommendation and votes
        """
        ...


class ProposalSelectionError(Exception):
    """Base exception for proposal selection errors."""


class ScoringError(ProposalSelectionError):
    """Error during proposal scoring."""


class DeliberationError(ProposalSelectionError):
    """Error during panel deliberation."""
