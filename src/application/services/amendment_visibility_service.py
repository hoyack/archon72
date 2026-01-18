"""Amendment visibility service (Story 6.7, FR126-FR128).

Provides constitutional amendment visibility enforcement,
impact analysis validation, and history protection.

Constitutional Constraints:
- FR126: Amendment proposals SHALL be publicly visible minimum 14 days before vote
- FR127: Core guarantee amendments require published impact analysis
         ("reduces visibility? raises silence probability? weakens irreversibility?")
- FR128: Amendments making previous amendments unreviewable are prohibited
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> Events must be witnessed
- CT-15: Legitimacy requires consent -> 14-day period ensures informed consent

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All amendment events must be witnessed
3. FAIL LOUD - Failed event write = operation failure
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.application.ports.amendment_repository import (
    AmendmentProposal,
    AmendmentRepositoryProtocol,
)
from src.application.ports.amendment_visibility_validator import (
    AmendmentVisibilityValidatorProtocol,
)
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.amendment import (
    AmendmentHistoryProtectionError,
    AmendmentImpactAnalysisMissingError,
    AmendmentNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.amendment import (
    VISIBILITY_PERIOD_DAYS,
    AmendmentImpactAnalysis,
    AmendmentProposedEventPayload,
    AmendmentRejectedEventPayload,
    AmendmentStatus,
    AmendmentType,
    AmendmentVoteBlockedEventPayload,
)

# System agent ID for amendment visibility service
AMENDMENT_VISIBILITY_SYSTEM_AGENT_ID: str = "SYSTEM:amendment_visibility"

# Keywords that suggest history-hiding intent (FR128)
HISTORY_HIDING_KEYWORDS: frozenset[str] = frozenset(
    {
        "unreviewable",
        "hide previous",
        "restrict access to amendments",
        "remove visibility",
        "delete amendment history",
        "obscure previous",
        "make inaccessible",
        "prevent review",
    }
)

# Targets that indicate amendments affecting visibility system itself
VISIBILITY_TARGETS: frozenset[str] = frozenset(
    {
        "amendment_visibility",
        "amendment_history",
        "fr126",
        "fr128",
    }
)


@dataclass(frozen=True)
class AmendmentProposalRequest:
    """Request to propose a new amendment.

    Attributes:
        amendment_id: Unique identifier for this amendment.
        amendment_type: Constitutional tier (Tier 2 or Tier 3).
        title: Brief description of the amendment.
        summary: Full amendment text/summary.
        proposer_id: Who is submitting the amendment (attribution).
        is_core_guarantee: True if this affects core guarantees.
        impact_analysis: Required if is_core_guarantee is True (FR127).
        affected_guarantees: Which guarantees are affected.
    """

    amendment_id: str
    amendment_type: AmendmentType
    title: str
    summary: str
    proposer_id: str
    is_core_guarantee: bool
    impact_analysis: AmendmentImpactAnalysis | None = None
    affected_guarantees: tuple[str, ...] = ()


@dataclass(frozen=True)
class VoteEligibilityResult:
    """Result of vote eligibility check (FR126).

    Constitutional Constraint (FR126):
    Amendment proposals SHALL be publicly visible
    minimum 14 days before vote.

    Attributes:
        is_eligible: True if 14-day visibility period is complete.
        days_remaining: Days until the amendment becomes votable.
        votable_from: When the amendment will be votable (UTC).
        reason: Explanation of eligibility status.
    """

    is_eligible: bool
    days_remaining: int
    votable_from: datetime
    reason: str


@dataclass(frozen=True)
class AmendmentSummary:
    """Summary of an amendment for observer queries (AC5).

    Attributes:
        amendment_id: Unique identifier.
        title: Brief description.
        proposed_at: When submitted.
        visible_from: When visibility period started.
        days_until_votable: Days remaining until vote can occur.
        is_core_guarantee: Affects core guarantees.
        has_impact_analysis: Impact analysis present (for core guarantees).
        proposer_id: Attribution of who proposed.
    """

    amendment_id: str
    title: str
    proposed_at: datetime
    visible_from: datetime
    days_until_votable: int
    is_core_guarantee: bool
    has_impact_analysis: bool
    proposer_id: str


@dataclass(frozen=True)
class AmendmentWithStatus:
    """Amendment with full visibility status.

    Attributes:
        proposal: The amendment proposal.
        is_votable: True if visibility period complete.
        days_remaining: Days until votable (0 if already votable).
        visibility_status: Human-readable status.
    """

    proposal: AmendmentProposal
    is_votable: bool
    days_remaining: int
    visibility_status: str


class AmendmentVisibilityService:
    """Service for amendment visibility enforcement (FR126-FR128, ADR-6).

    Provides:
    1. Amendment proposal with visibility period calculation (FR126)
    2. Vote eligibility checking (FR126)
    3. Impact analysis validation (FR127)
    4. History protection validation (FR128)
    5. Pending amendment queries for observers (AC5)

    Constitutional Pattern:
    1. HALT CHECK FIRST at every public operation (CT-11)
    2. Validate against FR126/FR127/FR128 constraints
    3. Create witnessed events for all operations (CT-12)

    Example:
        service = AmendmentVisibilityService(
            halt_checker=halt_checker,
            repository=repo,
            validator=validator,
        )

        # Propose amendment (starts 14-day visibility)
        proposal = await service.propose_amendment(request)

        # Check vote eligibility
        result = await service.check_vote_eligibility(amendment_id)

        # Query pending for observers
        pending = await service.get_pending_amendments()
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        repository: AmendmentRepositoryProtocol,
        validator: AmendmentVisibilityValidatorProtocol,
    ) -> None:
        """Initialize the amendment visibility service.

        Args:
            halt_checker: For CT-11 halt check before operations.
            repository: For storing and querying amendments.
            validator: For validating visibility/impact/history constraints.
        """
        self._halt_checker = halt_checker
        self._repository = repository
        self._validator = validator

    async def propose_amendment(
        self,
        proposal: AmendmentProposalRequest,
    ) -> tuple[AmendmentProposal, AmendmentProposedEventPayload]:
        """Submit a constitutional amendment proposal (FR126-FR128).

        FR126: Sets votable_from to 14 days from now.
        FR127: Requires impact analysis for core guarantee amendments.
        FR128: Rejects amendments that would hide history.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Validate FR128 (history protection)
        3. Validate FR127 (impact analysis for core guarantees)
        4. Calculate votable_from (FR126: 14 days)
        5. Save proposal
        6. Create event payload for witnessing (CT-12)

        Args:
            proposal: The amendment proposal request.

        Returns:
            Tuple of (AmendmentProposal, AmendmentProposedEventPayload).

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            AmendmentHistoryProtectionError: If FR128 violated.
            AmendmentImpactAnalysisMissingError: If FR127 violated.
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - amendment proposal blocked")

        # FR128: Check history protection
        if self._contains_history_hiding_intent(
            proposal.summary, proposal.affected_guarantees
        ):
            raise AmendmentHistoryProtectionError(amendment_id=proposal.amendment_id)

        # FR127: Require impact analysis for core guarantees
        if proposal.is_core_guarantee and proposal.impact_analysis is None:
            raise AmendmentImpactAnalysisMissingError(
                amendment_id=proposal.amendment_id,
                affected_guarantees=proposal.affected_guarantees,
            )

        # FR126: Calculate visibility period (14 days from now)
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        # Create proposal entity
        amendment = AmendmentProposal(
            amendment_id=proposal.amendment_id,
            amendment_type=proposal.amendment_type,
            title=proposal.title,
            summary=proposal.summary,
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id=proposal.proposer_id,
            is_core_guarantee=proposal.is_core_guarantee,
            impact_analysis=proposal.impact_analysis,
            affected_guarantees=proposal.affected_guarantees,
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )

        # Save to repository
        await self._repository.save_amendment(amendment)

        # Create event payload for witnessing (CT-12)
        event_payload = AmendmentProposedEventPayload(
            amendment_id=amendment.amendment_id,
            amendment_type=amendment.amendment_type,
            title=amendment.title,
            summary=amendment.summary,
            proposed_at=amendment.proposed_at,
            visible_from=amendment.visible_from,
            votable_from=amendment.votable_from,
            proposer_id=amendment.proposer_id,
            is_core_guarantee=amendment.is_core_guarantee,
            impact_analysis=amendment.impact_analysis,
            affected_guarantees=amendment.affected_guarantees,
        )

        return amendment, event_payload

    async def check_vote_eligibility(
        self,
        amendment_id: str,
    ) -> tuple[VoteEligibilityResult, AmendmentVoteBlockedEventPayload | None]:
        """Check if amendment can proceed to vote (FR126).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get amendment from repository
        3. Check if 14-day visibility period complete
        4. If incomplete, create vote blocked event (CT-12)

        Args:
            amendment_id: The amendment to check.

        Returns:
            Tuple of (VoteEligibilityResult, Optional blocked event payload).

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            AmendmentNotFoundError: If amendment doesn't exist.
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - vote eligibility check blocked")

        # Get amendment
        amendment = await self._repository.get_amendment(amendment_id)
        if amendment is None:
            raise AmendmentNotFoundError(amendment_id=amendment_id)

        now = datetime.now(timezone.utc)

        # Check if visibility period is complete
        if now >= amendment.votable_from:
            return VoteEligibilityResult(
                is_eligible=True,
                days_remaining=0,
                votable_from=amendment.votable_from,
                reason="Visibility period complete",
            ), None

        # Calculate days remaining
        days_remaining = (amendment.votable_from - now).days + 1

        # Create blocked event payload (CT-12)
        blocked_payload = AmendmentVoteBlockedEventPayload(
            amendment_id=amendment_id,
            blocked_reason=f"FR126: Amendment visibility period incomplete - {days_remaining} days remaining",
            days_remaining=days_remaining,
            votable_from=amendment.votable_from,
            blocked_at=now,
        )

        return VoteEligibilityResult(
            is_eligible=False,
            days_remaining=days_remaining,
            votable_from=amendment.votable_from,
            reason=f"FR126: Amendment visibility period incomplete - {days_remaining} days remaining",
        ), blocked_payload

    async def validate_amendment_submission(
        self,
        proposal: AmendmentProposalRequest,
    ) -> list[str]:
        """Validate amendment before submission (FR127, FR128).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Check FR127 (impact analysis for core guarantees)
        3. Check FR128 (history protection)
        4. Return list of validation errors

        Args:
            proposal: The amendment proposal to validate.

        Returns:
            List of validation errors (empty if valid).

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - validation blocked")

        errors: list[str] = []

        # FR128: Check history protection
        if self._contains_history_hiding_intent(
            proposal.summary, proposal.affected_guarantees
        ):
            errors.append("FR128: Amendment history cannot be made unreviewable")

        # FR127: Check impact analysis for core guarantees
        if proposal.is_core_guarantee:
            if proposal.impact_analysis is None:
                errors.append(
                    "FR127: Core guarantee amendment requires impact analysis"
                )
            else:
                # Validate impact analysis completeness
                analysis_errors = self._validate_impact_analysis(
                    proposal.impact_analysis
                )
                errors.extend(analysis_errors)

        return errors

    async def get_pending_amendments(self) -> list[AmendmentSummary]:
        """Get all pending amendments for observer queries (AC5).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Query pending amendments
        3. Calculate days remaining for each
        4. Return summaries

        Returns:
            List of AmendmentSummary for pending amendments.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - query blocked")

        pending = await self._repository.list_pending_amendments()
        now = datetime.now(timezone.utc)

        summaries: list[AmendmentSummary] = []
        for amendment in pending:
            if now >= amendment.votable_from:
                days_remaining = 0
            else:
                days_remaining = (amendment.votable_from - now).days + 1

            summaries.append(
                AmendmentSummary(
                    amendment_id=amendment.amendment_id,
                    title=amendment.title,
                    proposed_at=amendment.proposed_at,
                    visible_from=amendment.visible_from,
                    days_until_votable=days_remaining,
                    is_core_guarantee=amendment.is_core_guarantee,
                    has_impact_analysis=amendment.impact_analysis is not None,
                    proposer_id=amendment.proposer_id,
                )
            )

        return summaries

    async def get_amendment_with_visibility_status(
        self,
        amendment_id: str,
    ) -> AmendmentWithStatus:
        """Get amendment with full visibility status (AC5).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get amendment
        3. Calculate visibility status

        Args:
            amendment_id: The amendment to retrieve.

        Returns:
            AmendmentWithStatus with full context.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            AmendmentNotFoundError: If amendment doesn't exist.
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - query blocked")

        amendment = await self._repository.get_amendment(amendment_id)
        if amendment is None:
            raise AmendmentNotFoundError(amendment_id=amendment_id)

        now = datetime.now(timezone.utc)

        if now >= amendment.votable_from:
            is_votable = True
            days_remaining = 0
            visibility_status = "Visibility period complete - ready for vote"
        else:
            is_votable = False
            days_remaining = (amendment.votable_from - now).days + 1
            visibility_status = (
                f"In visibility period - {days_remaining} days remaining"
            )

        return AmendmentWithStatus(
            proposal=amendment,
            is_votable=is_votable,
            days_remaining=days_remaining,
            visibility_status=visibility_status,
        )

    async def reject_amendment(
        self,
        amendment_id: str,
        rejection_reason: str,
    ) -> AmendmentRejectedEventPayload:
        """Reject an amendment (FR128 or other validation failure).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Update status to rejected
        3. Create rejection event payload (CT-12)

        Args:
            amendment_id: The amendment to reject.
            rejection_reason: Reason for rejection.

        Returns:
            AmendmentRejectedEventPayload for witnessing.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            AmendmentNotFoundError: If amendment doesn't exist.
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - rejection blocked")

        # Verify amendment exists
        amendment = await self._repository.get_amendment(amendment_id)
        if amendment is None:
            raise AmendmentNotFoundError(amendment_id=amendment_id)

        # Update status
        await self._repository.update_status(amendment_id, AmendmentStatus.REJECTED)

        now = datetime.now(timezone.utc)

        # Create rejection event (CT-12)
        return AmendmentRejectedEventPayload(
            amendment_id=amendment_id,
            rejection_reason=rejection_reason,
            rejected_at=now,
        )

    def _contains_history_hiding_intent(
        self,
        summary: str,
        affected_guarantees: tuple[str, ...],
    ) -> bool:
        """Check if amendment would hide history (FR128).

        FR128: Amendments making previous amendments
        unreviewable are constitutionally prohibited.

        Args:
            summary: Amendment summary text.
            affected_guarantees: Which guarantees are affected.

        Returns:
            True if amendment appears to hide history.
        """
        summary_lower = summary.lower()

        # Check for explicit history-hiding keywords
        for keyword in HISTORY_HIDING_KEYWORDS:
            if keyword in summary_lower:
                return True

        # Check if targeting amendment visibility system
        for guarantee in affected_guarantees:
            if guarantee.lower() in VISIBILITY_TARGETS:
                return True

        return False

    def _validate_impact_analysis(
        self,
        impact_analysis: AmendmentImpactAnalysis,
    ) -> list[str]:
        """Validate FR127 impact analysis completeness.

        FR127 requires answering:
        - "reduces visibility?"
        - "raises silence probability?"
        - "weakens irreversibility?"

        Args:
            impact_analysis: The impact analysis to validate.

        Returns:
            List of missing/invalid fields (empty if valid).
        """
        errors: list[str] = []

        # Note: The booleans are always present in a dataclass,
        # but we validate the analysis text and attribution

        if not impact_analysis.analysis_text or len(impact_analysis.analysis_text) < 50:
            errors.append("FR127: Impact analysis text must be at least 50 characters")

        if not impact_analysis.analyzed_by:
            errors.append("FR127: Impact analysis must have attribution")

        return errors
