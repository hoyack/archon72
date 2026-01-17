"""Determination enumeration.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the possible determinations a Prince Panel can make.
"""

from enum import Enum


class Determination(Enum):
    """Panel determination after reviewing witness statement.

    Attributes:
        VIOLATION_FOUND: Panel determined a violation occurred
        NO_VIOLATION: Panel determined no violation occurred
        INSUFFICIENT_EVIDENCE: Panel could not make determination
    """

    VIOLATION_FOUND = "violation_found"
    """Panel determined a violation occurred."""

    NO_VIOLATION = "no_violation"
    """Panel determined no violation occurred."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    """Panel could not make determination due to insufficient evidence."""
