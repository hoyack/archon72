"""Amendment visibility validator stub implementation (Story 6.7, FR126-FR128).

This module provides an in-memory stub implementation of
AmendmentVisibilityValidatorProtocol for testing and development purposes.

Constitutional Constraints:
- FR126: Visibility period must be complete (14 days) before vote
- FR127: Core guarantee amendments require complete impact analysis
- FR128: Amendments cannot hide previous amendment history
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.application.ports.amendment_repository import (
    AmendmentProposal,
    AmendmentRepositoryProtocol,
)
from src.application.ports.amendment_visibility_validator import (
    AmendmentVisibilityValidatorProtocol,
    HistoryProtectionResult,
    ImpactValidationResult,
    VisibilityValidationResult,
)
from src.domain.errors.amendment import AmendmentNotFoundError


# Keywords that suggest history-hiding intent (FR128)
HISTORY_HIDING_KEYWORDS: frozenset[str] = frozenset({
    "unreviewable",
    "hide previous",
    "restrict access to amendments",
    "remove visibility",
    "delete amendment history",
    "obscure previous",
    "make inaccessible",
    "prevent review",
})


class AmendmentVisibilityValidatorStub(AmendmentVisibilityValidatorProtocol):
    """In-memory stub for amendment visibility validation (testing only).

    This stub provides an in-memory implementation of
    AmendmentVisibilityValidatorProtocol suitable for unit and integration tests.

    The stub uses the repository to check amendments and applies
    the constitutional rules (FR126-FR128) programmatically.
    """

    def __init__(
        self,
        repository: AmendmentRepositoryProtocol,
    ) -> None:
        """Initialize the stub with repository.

        Args:
            repository: Repository for accessing amendment data.
        """
        self._repository = repository

    async def validate_visibility_period(
        self, amendment_id: str
    ) -> VisibilityValidationResult:
        """Check if 14-day visibility period is complete (FR126).

        Args:
            amendment_id: The amendment to validate.

        Returns:
            VisibilityValidationResult with completion status.

        Raises:
            AmendmentNotFoundError: If amendment doesn't exist.
        """
        amendment = await self._repository.get_amendment(amendment_id)
        if amendment is None:
            raise AmendmentNotFoundError(amendment_id=amendment_id)

        now = datetime.now(timezone.utc)

        if now >= amendment.votable_from:
            return VisibilityValidationResult(
                is_complete=True,
                days_remaining=0,
                votable_from=amendment.votable_from,
            )
        else:
            days_remaining = (amendment.votable_from - now).days + 1
            return VisibilityValidationResult(
                is_complete=False,
                days_remaining=days_remaining,
                votable_from=amendment.votable_from,
            )

    async def validate_impact_analysis(
        self, amendment: AmendmentProposal
    ) -> ImpactValidationResult:
        """Check if core guarantee amendment has required impact analysis (FR127).

        For non-core-guarantee amendments, always returns is_valid=True.

        Args:
            amendment: The amendment to validate.

        Returns:
            ImpactValidationResult with validity status.
        """
        # Non-core guarantee amendments don't need impact analysis
        if not amendment.is_core_guarantee:
            return ImpactValidationResult(is_valid=True, missing_fields=[])

        # Core guarantee requires impact analysis
        if amendment.impact_analysis is None:
            return ImpactValidationResult(
                is_valid=False,
                missing_fields=[
                    "reduces_visibility",
                    "raises_silence_probability",
                    "weakens_irreversibility",
                    "analysis_text",
                    "analyzed_by",
                    "analyzed_at",
                ],
            )

        # Validate impact analysis fields
        missing: list[str] = []

        if not amendment.impact_analysis.analysis_text:
            missing.append("analysis_text")
        elif len(amendment.impact_analysis.analysis_text) < 50:
            missing.append("analysis_text (minimum 50 characters)")

        if not amendment.impact_analysis.analyzed_by:
            missing.append("analyzed_by")

        if missing:
            return ImpactValidationResult(is_valid=False, missing_fields=missing)

        return ImpactValidationResult(is_valid=True, missing_fields=[])

    async def validate_history_protection(
        self, amendment: AmendmentProposal
    ) -> HistoryProtectionResult:
        """Check if amendment would hide history (FR128).

        Args:
            amendment: The amendment to validate.

        Returns:
            HistoryProtectionResult with validity status.
        """
        summary_lower = amendment.summary.lower()

        # Check for explicit history-hiding keywords
        for keyword in HISTORY_HIDING_KEYWORDS:
            if keyword in summary_lower:
                return HistoryProtectionResult(
                    is_valid=False,
                    violation_reason=f"FR128: Amendment contains history-hiding intent: '{keyword}'",
                )

        # Check if targeting amendment visibility system
        visibility_targets = {"amendment_visibility", "amendment_history", "fr126", "fr128"}
        for guarantee in amendment.affected_guarantees:
            if guarantee.lower() in visibility_targets:
                return HistoryProtectionResult(
                    is_valid=False,
                    violation_reason=f"FR128: Amendment targets visibility system: '{guarantee}'",
                )

        return HistoryProtectionResult(is_valid=True, violation_reason=None)

    async def can_proceed_to_vote(
        self, amendment_id: str
    ) -> tuple[bool, str]:
        """Comprehensive check combining all validations.

        Args:
            amendment_id: The amendment to validate.

        Returns:
            Tuple of (can_proceed, reason).

        Raises:
            AmendmentNotFoundError: If amendment doesn't exist.
        """
        amendment = await self._repository.get_amendment(amendment_id)
        if amendment is None:
            raise AmendmentNotFoundError(amendment_id=amendment_id)

        # Check FR126: Visibility period
        visibility_result = await self.validate_visibility_period(amendment_id)
        if not visibility_result.is_complete:
            return False, f"FR126: Visibility period incomplete - {visibility_result.days_remaining} days remaining"

        # Check FR127: Impact analysis for core guarantees
        impact_result = await self.validate_impact_analysis(amendment)
        if not impact_result.is_valid:
            missing = ", ".join(impact_result.missing_fields)
            return False, f"FR127: Impact analysis incomplete - missing: {missing}"

        # Check FR128: History protection
        history_result = await self.validate_history_protection(amendment)
        if not history_result.is_valid:
            return False, history_result.violation_reason or "FR128 violation"

        return True, "All validations passed - ready for vote"
