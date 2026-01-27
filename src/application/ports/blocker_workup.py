"""Port interface for E2.5 Blocker Workup (peer review + disposition).

Defines the protocol for Plan Owner to cross-review blockers from all
contributing portfolios and produce a PeerReviewSummary with:
- Duplicate detection
- Conflict identification
- Coverage gap analysis
- Disposition rationale

Constitutional Compliance:
- CT-11: All LLM calls logged, failures reported
- CT-12: Blocker dispositions traceable to source portfolios
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.executive_planning import (
        BlockerPacket,
        BlockerWorkupResult,
        PortfolioIdentity,
        RatifiedIntentPacket,
    )


@dataclass
class BlockerWorkupContext:
    """Context for E2.5 blocker workup deliberation."""

    cycle_id: str
    motion_id: str
    motion_title: str
    motion_text: str
    constraints: list[str]
    plan_owner_portfolio_id: str
    affected_portfolios: list[str]
    portfolio_labels: dict[str, str]  # portfolio_id -> human-readable label


class BlockerWorkupError(Exception):
    """Base error for blocker workup failures."""


class BlockerWorkupProtocol(ABC):
    """Protocol for LLM-powered E2.5 blocker workup.

    The Plan Owner (or designated reviewer) cross-reviews all blockers
    raised during E2 Portfolio Drafting to:
    1. Detect duplicate blockers across portfolios
    2. Identify conflicting blocker dispositions
    3. Find coverage gaps (areas with no portfolio claiming ownership)
    4. Provide rationale for each blocker's disposition

    This is a deliberative phase that may adjust blocker dispositions
    before E3 Integration.
    """

    @abstractmethod
    async def run_workup(
        self,
        packet: RatifiedIntentPacket,
        blocker_packet: BlockerPacket,
        plan_owner: PortfolioIdentity,
        context: BlockerWorkupContext,
    ) -> BlockerWorkupResult:
        """Run E2.5 blocker workup for cross-review and disposition.

        The Plan Owner analyzes all blockers and produces:
        - PeerReviewSummary with duplicates, conflicts, gaps, rationale
        - Final blocker list (possibly with adjusted dispositions)
        - Generated artifacts (ConclaveQueueItems, DiscoveryTaskStubs)

        Args:
            packet: The ratified intent packet being planned
            blocker_packet: All blockers from E2 portfolio drafting
            plan_owner: Identity of the Plan Owner portfolio
            context: Additional context for the workup

        Returns:
            BlockerWorkupResult with peer review and final artifacts

        Raises:
            BlockerWorkupError: If workup fails
        """

    @abstractmethod
    async def validate_dispositions(
        self,
        blocker_packet: BlockerPacket,
        context: BlockerWorkupContext,
    ) -> list[str]:
        """Validate blocker dispositions against workup rules.

        Checks:
        - INTENT_AMBIGUITY blockers have ESCALATE_NOW disposition
        - DEFER_DOWNSTREAM blockers have verification_tasks
        - MITIGATE_IN_EXECUTIVE blockers have mitigation_notes
        - No circular dependencies between blockers

        Args:
            blocker_packet: The blockers to validate
            context: Workup context

        Returns:
            List of validation error messages (empty if all valid)
        """

    @abstractmethod
    async def detect_duplicates(
        self,
        blocker_packet: BlockerPacket,
    ) -> list[list[str]]:
        """Detect duplicate blockers across portfolios.

        Uses semantic similarity to identify blockers that describe
        the same underlying issue raised by different portfolios.

        Args:
            blocker_packet: The blockers to analyze

        Returns:
            List of duplicate groups (each group is a list of blocker IDs)
        """

    @abstractmethod
    async def identify_conflicts(
        self,
        blocker_packet: BlockerPacket,
    ) -> list[dict[str, str]]:
        """Identify conflicting blocker dispositions.

        Finds cases where:
        - Same issue has different dispositions across portfolios
        - Blockers have incompatible escalation conditions
        - Mitigation notes contradict each other

        Args:
            blocker_packet: The blockers to analyze

        Returns:
            List of conflict records with blocker_ids and conflict_type
        """

    @abstractmethod
    async def find_coverage_gaps(
        self,
        packet: RatifiedIntentPacket,
        blocker_packet: BlockerPacket,
        context: BlockerWorkupContext,
    ) -> list[str]:
        """Find areas of the motion not covered by any blocker or contribution.

        Analyzes the motion intent against the blockers raised to identify
        aspects that may have been overlooked by all portfolios.

        Args:
            packet: The ratified intent packet
            blocker_packet: The blockers raised
            context: Workup context with affected portfolios

        Returns:
            List of coverage gap descriptions
        """
