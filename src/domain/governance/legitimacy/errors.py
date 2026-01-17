"""Error types for legitimacy band domain.

This module defines domain-specific exceptions for legitimacy band
operations, following the project convention of using specific
exception types rather than generic ValueError/RuntimeError.
"""


class LegitimacyError(Exception):
    """Base exception for legitimacy domain errors."""

    pass


class InvalidTransitionError(LegitimacyError):
    """Raised when an invalid band transition is attempted.

    This includes attempting to transition from FAILED,
    skipping bands on restoration, or other rule violations.
    """

    pass


class TerminalBandError(LegitimacyError):
    """Raised when attempting to transition from the FAILED band.

    FAILED is a terminal state that requires reconstitution,
    not normal band transitions.
    """

    pass


class AcknowledgmentRequiredError(LegitimacyError):
    """Raised when upward transition is attempted without acknowledgment.

    All upward (restoration) transitions require explicit human
    acknowledgment per NFR-CONST-04.
    """

    pass
