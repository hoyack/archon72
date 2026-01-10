"""Collusion defense errors (Story 6.8, FR124).

Provides specific exception classes for collusion investigation scenarios.
All exceptions inherit from ConstitutionalViolationError.

Constitutional Constraints:
- FR124: Witness selection randomness SHALL combine hash chain state +
         external entropy source meeting independence criteria (Randomness Gaming defense)
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.domain.errors.constitutional import ConstitutionalViolationError


class CollusionDefenseError(ConstitutionalViolationError):
    """Base class for collusion defense errors (FR124).

    All collusion-related errors inherit from this class.
    """

    pass


class CollusionInvestigationRequiredError(CollusionDefenseError):
    """Error when collusion correlation exceeds threshold (FR124).

    Raised when witness pair correlation score exceeds the configured
    threshold (default 0.8), requiring formal investigation.

    Constitutional Constraint (FR124):
    Randomness Gaming defense - high correlation indicates
    potential collusion that must be investigated.

    Attributes:
        pair_key: Canonical key of the suspicious pair.
        correlation_score: The calculated correlation score.
    """

    def __init__(self, pair_key: str, correlation_score: float) -> None:
        """Initialize the error.

        Args:
            pair_key: Canonical key of the suspicious pair.
            correlation_score: The calculated correlation score.
        """
        self.pair_key = pair_key
        self.correlation_score = correlation_score
        super().__init__(
            f"FR124: Collusion investigation required for pair {pair_key} - "
            f"correlation score {correlation_score:.2f} exceeds threshold"
        )


class WitnessPairSuspendedError(CollusionDefenseError):
    """Error when attempting to use a suspended witness pair (FR124).

    Raised when a witness pair is suspended pending investigation
    and cannot be used for witnessing.

    Constitutional Constraint (FR124):
    Suspended pairs must be excluded from selection until cleared.

    Attributes:
        pair_key: Canonical key of the suspended pair.
        investigation_id: ID of the active investigation.
    """

    def __init__(self, pair_key: str, investigation_id: str) -> None:
        """Initialize the error.

        Args:
            pair_key: Canonical key of the suspended pair.
            investigation_id: ID of the active investigation.
        """
        self.pair_key = pair_key
        self.investigation_id = investigation_id
        super().__init__(
            f"FR124: Witness pair {pair_key} suspended pending "
            f"investigation {investigation_id}"
        )


class InvestigationNotFoundError(CollusionDefenseError):
    """Error when investigation cannot be found.

    Raised when attempting to resolve or query an investigation
    that does not exist.

    Attributes:
        investigation_id: ID of the missing investigation.
    """

    def __init__(self, investigation_id: str) -> None:
        """Initialize the error.

        Args:
            investigation_id: ID of the missing investigation.
        """
        self.investigation_id = investigation_id
        super().__init__(f"Investigation {investigation_id} not found")


class InvestigationAlreadyResolvedError(CollusionDefenseError):
    """Error when investigation has already been resolved.

    Raised when attempting to resolve an investigation that
    has already been concluded.

    Attributes:
        investigation_id: ID of the resolved investigation.
        resolved_at: When the investigation was resolved.
    """

    def __init__(
        self,
        investigation_id: str,
        resolved_at: Optional[datetime] = None,
    ) -> None:
        """Initialize the error.

        Args:
            investigation_id: ID of the resolved investigation.
            resolved_at: When the investigation was resolved.
        """
        self.investigation_id = investigation_id
        self.resolved_at = resolved_at
        timestamp = resolved_at.isoformat() if resolved_at else "unknown time"
        super().__init__(
            f"Investigation {investigation_id} already resolved at {timestamp}"
        )


class WitnessPairPermanentlyBannedError(CollusionDefenseError):
    """Error when attempting to use a permanently banned pair.

    Raised when a witness pair was confirmed for collusion and
    permanently banned from selection.

    Attributes:
        pair_key: Canonical key of the banned pair.
        investigation_id: Investigation that led to the ban.
    """

    def __init__(self, pair_key: str, investigation_id: str) -> None:
        """Initialize the error.

        Args:
            pair_key: Canonical key of the banned pair.
            investigation_id: Investigation that confirmed collusion.
        """
        self.pair_key = pair_key
        self.investigation_id = investigation_id
        super().__init__(
            f"FR124: Witness pair {pair_key} permanently banned - "
            f"collusion confirmed in investigation {investigation_id}"
        )
