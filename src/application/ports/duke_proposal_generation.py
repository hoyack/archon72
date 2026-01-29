"""Port interface for Duke Proposal generation.

Each Administrative Duke reads a finalized Executive RFP and produces a
complete implementation proposal covering how to accomplish the RFP's
requirements from their domain expertise perspective.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.duke_proposal import DukeProposal
    from src.domain.models.rfp import RFPDocument


class DukeProposalGeneratorProtocol(ABC):
    """Protocol for generating a Duke's implementation proposal for an RFP.

    Each Duke applies their unique domain expertise to propose HOW to
    accomplish the RFP's requirements. The proposal covers the entire
    RFP scope (not per-epic).
    """

    @abstractmethod
    async def generate_proposal(
        self,
        rfp: RFPDocument,
        duke_archon_id: str,
        duke_name: str,
        duke_domain: str,
        duke_role: str,
        duke_backstory: str,
        duke_personality: str,
    ) -> DukeProposal:
        """Generate a complete implementation proposal for the given RFP.

        Args:
            rfp: The finalized Executive RFP document
            duke_archon_id: UUID of the Duke archon
            duke_name: Name of the Duke (e.g., "Agares")
            duke_domain: Domain expertise (e.g., "Market Disruption")
            duke_role: Full role title from archons-base.json
            duke_backstory: Duke's backstory for persona grounding
            duke_personality: Personality traits (if available)

        Returns:
            DukeProposal with tactics, risks, resources, coverage, etc.
        """
        ...
