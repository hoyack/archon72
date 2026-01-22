"""Acknowledgment reason codes for petition fate assignments.

This module defines the enumeration of valid acknowledgment reason codes
per FR-3.2, along with validation helpers for rationale and reference requirements.

Constitutional Context:
- CT-12: Reason codes enable witnessed acknowledgment events
- CT-14: ACKNOWLEDGED is a terminal fate with mandatory reason code
"""

from src.domain._compat import StrEnum
from uuid import UUID


class AcknowledgmentReasonCode(StrEnum):
    """Enumeration of valid acknowledgment reason codes per FR-3.2.

    Codes are divided into three categories based on validation requirements:

    Rationale Required (FR-3.3):
        - REFUSED: Petition violates policy or norms
        - NO_ACTION_WARRANTED: After review, no action is appropriate

    Reference Required (FR-3.4):
        - DUPLICATE: Petition duplicates an existing or resolved petition

    No Additional Requirements:
        - ADDRESSED: Concern has been or will be addressed
        - NOTED: Input has been recorded for future consideration
        - OUT_OF_SCOPE: Matter falls outside governance jurisdiction
        - WITHDRAWN: Petitioner withdrew the petition
        - EXPIRED: Referral timeout with no Knight response
        - KNIGHT_REFERRAL: Knight recommended ACKNOWLEDGE (Story 4.4, FR-4.6)
    """

    ADDRESSED = "ADDRESSED"
    NOTED = "NOTED"
    DUPLICATE = "DUPLICATE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    REFUSED = "REFUSED"
    NO_ACTION_WARRANTED = "NO_ACTION_WARRANTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    KNIGHT_REFERRAL = "KNIGHT_REFERRAL"  # Story 4.4: Knight recommended ACKNOWLEDGE

    @classmethod
    def requires_rationale(cls, code: "AcknowledgmentReasonCode") -> bool:
        """Check if this reason code requires mandatory rationale.

        Per FR-3.3, REFUSED and NO_ACTION_WARRANTED require rationale text
        to ensure accountability and prevent rubber-stamping.

        Args:
            code: The reason code to check

        Returns:
            True if rationale is required, False otherwise
        """
        return code in {cls.REFUSED, cls.NO_ACTION_WARRANTED}

    @classmethod
    def requires_reference(cls, code: "AcknowledgmentReasonCode") -> bool:
        """Check if this reason code requires a reference petition ID.

        Per FR-3.4, DUPLICATE requires a reference_petition_id pointing
        to the original or resolved petition.

        Args:
            code: The reason code to check

        Returns:
            True if reference is required, False otherwise
        """
        return code == cls.DUPLICATE

    @classmethod
    def from_string(cls, value: str) -> "AcknowledgmentReasonCode":
        """Parse a string into an AcknowledgmentReasonCode.

        Supports case-insensitive matching for flexibility.

        Args:
            value: String representation of the reason code

        Returns:
            The matching AcknowledgmentReasonCode

        Raises:
            InvalidReasonCodeError: If the value is not a valid reason code
        """
        normalized = value.upper().strip()
        try:
            return cls(normalized)
        except ValueError:
            valid_codes = [c.value for c in cls]
            raise InvalidReasonCodeError(
                f"Invalid reason code: '{value}'. "
                f"Valid codes are: {', '.join(valid_codes)}"
            )


class RationaleRequiredError(ValueError):
    """Raised when rationale is required but not provided.

    This error enforces FR-3.3 which mandates rationale text for
    REFUSED and NO_ACTION_WARRANTED reason codes.
    """

    def __init__(self, reason_code: AcknowledgmentReasonCode):
        self.reason_code = reason_code
        super().__init__(
            f"Rationale is required for reason code '{reason_code.value}'. "
            f"Per FR-3.3, acknowledgments with REFUSED or NO_ACTION_WARRANTED "
            f"must include a non-empty rationale explaining the decision."
        )


class ReferenceRequiredError(ValueError):
    """Raised when reference_petition_id is required but not provided.

    This error enforces FR-3.4 which mandates a reference to the original
    petition when using the DUPLICATE reason code.
    """

    def __init__(self):
        super().__init__(
            "Reference petition ID is required for DUPLICATE acknowledgments. "
            "Per FR-3.4, DUPLICATE reason code must include the petition_id "
            "of the original or already-resolved petition."
        )


class InvalidReasonCodeError(ValueError):
    """Raised when an invalid reason code string is provided.

    This error indicates that the provided string does not match
    any of the valid AcknowledgmentReasonCode enum values.
    """

    pass


def validate_acknowledgment_requirements(
    reason_code: AcknowledgmentReasonCode,
    rationale: str | None = None,
    reference_petition_id: UUID | None = None,
) -> None:
    """Validate that all requirements for the given reason code are met.

    This function performs comprehensive validation per FR-3.3 and FR-3.4:
    - REFUSED and NO_ACTION_WARRANTED require non-empty rationale
    - DUPLICATE requires a valid reference_petition_id

    Args:
        reason_code: The acknowledgment reason code
        rationale: Optional rationale text (required for some codes)
        reference_petition_id: Optional reference to another petition (required for DUPLICATE)

    Raises:
        RationaleRequiredError: If rationale is required but not provided or empty
        ReferenceRequiredError: If reference_petition_id is required but not provided
    """
    if AcknowledgmentReasonCode.requires_rationale(reason_code):
        if not rationale or not rationale.strip():
            raise RationaleRequiredError(reason_code)

    if AcknowledgmentReasonCode.requires_reference(reason_code):
        if reference_petition_id is None:
            raise ReferenceRequiredError()
