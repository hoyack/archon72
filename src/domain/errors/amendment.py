"""Amendment visibility domain errors (Story 6.7, FR126-FR128).

Provides specific exception classes for amendment visibility failures.
All exceptions inherit from ConstitutionalViolationError as they
represent violations of constitutional requirements.

Constitutional Constraints:
- FR126: Constitutional amendment proposals SHALL be publicly visible
         minimum 14 days before vote
- FR127: Amendments affecting core guarantees SHALL require published
         impact analysis ("reduces visibility? raises silence probability?
         weakens irreversibility?")
- FR128: Amendments making previous amendments unreviewable are
         constitutionally prohibited
"""

from datetime import datetime

from src.domain.errors.constitutional import ConstitutionalViolationError


class AmendmentError(ConstitutionalViolationError):
    """Base class for amendment visibility errors.

    All amendment errors represent constitutional violations
    related to FR126, FR127, or FR128.
    """

    pass


class AmendmentVisibilityIncompleteError(AmendmentError):
    """Raised when vote attempted before visibility period complete (FR126).

    Constitutional Constraint (FR126):
    Constitutional amendment proposals SHALL be publicly visible
    minimum 14 days before vote.

    This error indicates that a vote was attempted on an amendment
    before the required 14-day visibility period was complete.

    Attributes:
        amendment_id: ID of the amendment that blocked the vote.
        days_remaining: Days until the amendment becomes votable.
        votable_from: When the amendment will be votable (UTC).
    """

    def __init__(
        self,
        amendment_id: str,
        days_remaining: int,
        votable_from: datetime,
    ) -> None:
        """Initialize visibility incomplete error.

        Args:
            amendment_id: ID of the amendment
            days_remaining: Days until votable
            votable_from: When the amendment will be votable
        """
        self.amendment_id = amendment_id
        self.days_remaining = days_remaining
        self.votable_from = votable_from

        message = (
            f"FR126: Amendment visibility period incomplete - "
            f"{days_remaining} days remaining"
        )
        super().__init__(message)


class AmendmentImpactAnalysisMissingError(AmendmentError):
    """Raised when core guarantee amendment lacks impact analysis (FR127).

    Constitutional Constraint (FR127):
    Amendments affecting core guarantees SHALL require published
    impact analysis answering:
    - "reduces visibility?"
    - "raises silence probability?"
    - "weakens irreversibility?"

    This error indicates that an amendment affecting core guarantees
    was submitted without the required impact analysis.

    Attributes:
        amendment_id: ID of the amendment missing analysis.
        affected_guarantees: Which constitutional guarantees are affected.
    """

    def __init__(
        self,
        amendment_id: str,
        affected_guarantees: tuple[str, ...] = (),
    ) -> None:
        """Initialize impact analysis missing error.

        Args:
            amendment_id: ID of the amendment
            affected_guarantees: Tuple of affected guarantee names
        """
        self.amendment_id = amendment_id
        self.affected_guarantees = affected_guarantees

        guarantee_list = (
            ", ".join(affected_guarantees) if affected_guarantees else "core guarantees"
        )
        message = (
            f"FR127: Core guarantee amendment requires impact analysis "
            f"(amendment: {amendment_id}, affects: {guarantee_list})"
        )
        super().__init__(message)


class AmendmentHistoryProtectionError(AmendmentError):
    """Raised when amendment would hide history (FR128).

    Constitutional Constraint (FR128):
    Amendments making previous amendments unreviewable are
    constitutionally prohibited.

    This error indicates that an amendment was detected to have
    intent to hide, restrict, or make unreviewable previous
    amendment history.

    Attributes:
        amendment_id: ID of the rejected amendment.
    """

    def __init__(
        self,
        amendment_id: str,
    ) -> None:
        """Initialize history protection error.

        Args:
            amendment_id: ID of the rejected amendment
        """
        self.amendment_id = amendment_id

        message = "FR128: Amendment history cannot be made unreviewable"
        super().__init__(message)


class AmendmentNotFoundError(AmendmentError):
    """Raised when amendment cannot be found.

    This error indicates that an operation was attempted on an
    amendment that does not exist in the repository.

    Attributes:
        amendment_id: ID of the amendment that was not found.
    """

    def __init__(
        self,
        amendment_id: str,
    ) -> None:
        """Initialize amendment not found error.

        Args:
            amendment_id: ID of the amendment that was not found
        """
        self.amendment_id = amendment_id

        message = f"Amendment {amendment_id} not found"
        super().__init__(message)
