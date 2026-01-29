"""Port interface for Executive Implementation Dossier generation.

The Executive branch uses this to generate dossier documents from mandates.
Each President contributes requirements and constraints from their portfolio lens.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.rfp import PortfolioContribution, RFPDocument


class RFPContributorProtocol(ABC):
    """Protocol for generating portfolio contributions to a dossier.

    Each President implements this to contribute requirements, constraints,
    and evaluation criteria from their portfolio perspective.
    """

    @abstractmethod
    async def generate_contribution(
        self,
        mandate_id: str,
        motion_title: str,
        motion_text: str,
        portfolio_id: str,
        president_name: str,
        portfolio_domain: str,
        president_id: str = "",
        existing_contributions: list[PortfolioContribution] | None = None,
    ) -> PortfolioContribution:
        """Generate a portfolio contribution to the dossier.

        Args:
            mandate_id: The mandate being addressed
            motion_title: Title of the passed motion
            motion_text: Full text of the passed motion
            portfolio_id: The contributing portfolio's ID
            president_name: Name of the contributing President
            portfolio_domain: Domain expertise of the portfolio
            president_id: UUID of the contributing President (for traceability)
            existing_contributions: Contributions from other Presidents (for cross-reference)

        Returns:
            PortfolioContribution with requirements, constraints, etc.
        """
        ...


class RFPSynthesizerProtocol(ABC):
    """Protocol for synthesizing portfolio contributions into a unified dossier.

    After all Presidents contribute, this merges and resolves conflicts.
    """

    @abstractmethod
    async def synthesize_rfp(
        self,
        rfp_draft: RFPDocument,
        contributions: list[PortfolioContribution],
    ) -> RFPDocument:
        """Synthesize contributions into a unified dossier.

        Args:
            rfp_draft: The draft dossier with basic mandate info
            contributions: All portfolio contributions

        Returns:
            Finalized dossier with merged requirements, resolved conflicts
        """
        ...

    @abstractmethod
    async def identify_conflicts(
        self,
        contributions: list[PortfolioContribution],
    ) -> list[dict]:
        """Identify conflicts between contributions.

        Args:
            contributions: All portfolio contributions

        Returns:
            List of conflict descriptions with conflicting parties
        """
        ...


class RFPDeliberationProtocol(ABC):
    """Protocol for multi-round deliberation between Presidents.

    Enables cross-talk and refinement of contributions.
    """

    @abstractmethod
    async def run_deliberation_round(
        self,
        rfp_draft: RFPDocument,
        contributions: list[PortfolioContribution],
        round_number: int,
        focus_areas: list[str] | None = None,
    ) -> list[PortfolioContribution]:
        """Run a deliberation round where Presidents can refine contributions.

        Args:
            rfp_draft: Current state of the dossier
            contributions: Current contributions from all Presidents
            round_number: Which round of deliberation
            focus_areas: Specific areas to focus discussion on

        Returns:
            Updated contributions after deliberation
        """
        ...
