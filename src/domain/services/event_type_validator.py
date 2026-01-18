"""Event type validator for prohibited patterns (Story 7.3, NFR40).

This module provides import-time and runtime validation to ensure
no prohibited event types (like cessation reversal) can be added
to the schema.

Constitutional Constraints:
- FR40: No cessation_reversal event type in schema
- NFR40: Cessation reversal is architecturally prohibited
- CT-11: Silent failure destroys legitimacy -> Validate explicitly
- CT-13: Integrity outranks availability -> Reject prohibited types

Developer Golden Rules:
1. IMPORT-TIME VALIDATION - Run validation when module is imported
2. FAIL LOUD - Raise EventTypeProhibitedError immediately
3. BLOCK SYNONYMS - Catch undo, revert, restore, cancel, rollback, etc.
"""

from __future__ import annotations

import re
from typing import Final

from src.domain.errors.schema_irreversibility import EventTypeProhibitedError

# Prohibited event type patterns (NFR40)
# These regex patterns catch any event type that could represent
# a reversal or undoing of cessation.
PROHIBITED_EVENT_TYPE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # Direct cessation reversal patterns
    re.compile(r"cessation[._-]?reversal", re.IGNORECASE),
    re.compile(r"cessation[._-]?undo", re.IGNORECASE),
    re.compile(r"cessation[._-]?revert", re.IGNORECASE),
    re.compile(r"cessation[._-]?restore", re.IGNORECASE),
    re.compile(r"cessation[._-]?cancel", re.IGNORECASE),
    re.compile(r"cessation[._-]?rollback", re.IGNORECASE),
    # Reversal action patterns targeting cessation
    re.compile(r"reversal[._-]?cessation", re.IGNORECASE),
    re.compile(r"undo[._-]?cessation", re.IGNORECASE),
    re.compile(r"revert[._-]?cessation", re.IGNORECASE),
    # Generic resurrection patterns
    re.compile(r"uncease", re.IGNORECASE),
    re.compile(r"un[._-]?cease", re.IGNORECASE),
    re.compile(r"resurrect", re.IGNORECASE),
    re.compile(r"revive[._-]?system", re.IGNORECASE),
    # CamelCase variations
    re.compile(r"cessationReversal", re.IGNORECASE),
    re.compile(r"cessationUndo", re.IGNORECASE),
    re.compile(r"cessationRevert", re.IGNORECASE),
    re.compile(r"cessationRestore", re.IGNORECASE),
    re.compile(r"cessationCancel", re.IGNORECASE),
    re.compile(r"cessationRollback", re.IGNORECASE),
)


def validate_event_type(event_type: str) -> bool:
    """Validate that an event type is not prohibited (NFR40).

    Constitutional Constraint (NFR40):
    Cessation reversal is architecturally prohibited. This function
    validates that no event type matches prohibited patterns.

    This function is called:
    1. At import time (via _validate_no_prohibited_event_types)
    2. When registering new event types
    3. When validating incoming event type strings

    Args:
        event_type: The event type string to validate.

    Returns:
        True if the event type is valid (not prohibited).

    Raises:
        EventTypeProhibitedError: If the event type matches a prohibited pattern.
            The error message includes NFR40 reference and the matching pattern.

    Example:
        >>> validate_event_type("cessation.executed")  # OK
        True
        >>> validate_event_type("cessation.reversal")  # RAISES
        Traceback (most recent call last):
            ...
        EventTypeProhibitedError: NFR40: ...
    """
    for pattern in PROHIBITED_EVENT_TYPE_PATTERNS:
        if pattern.search(event_type):
            raise EventTypeProhibitedError(
                f"NFR40: Cessation reversal prohibited by schema. "
                f"Detected prohibited event type: '{event_type}' "
                f"(matches pattern: '{pattern.pattern}')"
            )

    return True


def is_prohibited_event_type(event_type: str) -> bool:
    """Check if an event type is prohibited without raising (utility function).

    This is a non-raising version of validate_event_type for use in
    conditional checks where you want to handle the result yourself.

    Args:
        event_type: The event type string to check.

    Returns:
        True if the event type is prohibited, False otherwise.

    Example:
        >>> is_prohibited_event_type("cessation.executed")
        False
        >>> is_prohibited_event_type("cessation.reversal")
        True
    """
    return any(pattern.search(event_type) for pattern in PROHIBITED_EVENT_TYPE_PATTERNS)


def get_prohibited_patterns() -> list[str]:
    """Get the list of prohibited pattern strings.

    Useful for documentation, logging, and test assertions.

    Returns:
        List of regex pattern strings that are prohibited.
    """
    return [pattern.pattern for pattern in PROHIBITED_EVENT_TYPE_PATTERNS]
