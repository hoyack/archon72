"""Amendment visibility validator port (Story 6.7, FR126-FR128).

This module defines the validation interface for amendment visibility,
impact analysis, and history protection checks.

Constitutional Constraints:
- FR126: Visibility period must be complete (14 days) before vote
- FR127: Core guarantee amendments require complete impact analysis
- FR128: Amendments cannot hide previous amendment history
- CT-11: Silent failure destroys legitimacy -> Validation failures must be explicit
- CT-12: Witnessing creates accountability -> All validations logged
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.application.ports.amendment_repository import AmendmentProposal


@dataclass(frozen=True)
class VisibilityValidationResult:
    """Result of visibility period validation (FR126).

    Attributes:
        is_complete: True if 14-day visibility period is complete.
        days_remaining: Days until visibility period completes (0 if complete).
        votable_from: When the amendment will be votable (UTC).
    """

    is_complete: bool
    days_remaining: int
    votable_from: datetime


@dataclass(frozen=True)
class ImpactValidationResult:
    """Result of impact analysis validation (FR127).

    FR127 requires impact analysis for core guarantee amendments,
    answering three specific questions:
    - "reduces visibility?"
    - "raises silence probability?"
    - "weakens irreversibility?"

    Attributes:
        is_valid: True if impact analysis is present and complete.
        missing_fields: List of missing or incomplete fields.
    """

    is_valid: bool
    missing_fields: list[str]


@dataclass(frozen=True)
class HistoryProtectionResult:
    """Result of history protection validation (FR128).

    FR128 prohibits amendments that would make previous amendments
    unreviewable.

    Attributes:
        is_valid: True if amendment does not violate history protection.
        violation_reason: Reason for violation, if is_valid is False.
    """

    is_valid: bool
    violation_reason: str | None


class AmendmentVisibilityValidatorProtocol(Protocol):
    """Protocol for amendment visibility validation (FR126-FR128).

    This protocol defines the interface for validating amendment proposals
    against constitutional constraints before they can proceed to vote.

    All implementations must validate:
    - FR126: 14-day visibility period
    - FR127: Impact analysis for core guarantees
    - FR128: History protection (no hiding amendments)
    """

    async def validate_visibility_period(
        self, amendment_id: str
    ) -> VisibilityValidationResult:
        """Check if 14-day visibility period is complete (FR126).

        Constitutional Constraint (FR126):
        Amendment proposals SHALL be publicly visible minimum 14 days
        before vote.

        Args:
            amendment_id: The amendment to validate.

        Returns:
            VisibilityValidationResult with completion status.

        Raises:
            AmendmentNotFoundError: If amendment doesn't exist.
            AmendmentError: If validation fails.
        """
        ...

    async def validate_impact_analysis(
        self, amendment: AmendmentProposal
    ) -> ImpactValidationResult:
        """Check if core guarantee amendment has required impact analysis (FR127).

        Constitutional Constraint (FR127):
        Amendments affecting core guarantees SHALL require published
        impact analysis answering:
        - "reduces visibility?"
        - "raises silence probability?"
        - "weakens irreversibility?"

        For non-core-guarantee amendments, always returns is_valid=True.

        Args:
            amendment: The amendment to validate.

        Returns:
            ImpactValidationResult with validity status.

        Raises:
            AmendmentError: If validation fails.
        """
        ...

    async def validate_history_protection(
        self, amendment: AmendmentProposal
    ) -> HistoryProtectionResult:
        """Check if amendment would hide history (FR128).

        Constitutional Constraint (FR128):
        Amendments making previous amendments unreviewable are
        constitutionally prohibited.

        Args:
            amendment: The amendment to validate.

        Returns:
            HistoryProtectionResult with validity status.

        Raises:
            AmendmentError: If validation fails.
        """
        ...

    async def can_proceed_to_vote(self, amendment_id: str) -> tuple[bool, str]:
        """Comprehensive check combining all validations.

        Validates all constitutional constraints (FR126, FR127, FR128)
        to determine if an amendment can proceed to voting.

        Args:
            amendment_id: The amendment to validate.

        Returns:
            Tuple of (can_proceed, reason).
            - can_proceed: True if all validations pass.
            - reason: Explanation (success or failure reason).

        Raises:
            AmendmentNotFoundError: If amendment doesn't exist.
            AmendmentError: If validation fails.
        """
        ...
