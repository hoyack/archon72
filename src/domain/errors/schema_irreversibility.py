"""Schema irreversibility errors (Story 7.3, FR40, NFR40).

This module defines exceptions for schema irreversibility violations.
These errors represent constitutional violations that CANNOT be silently ignored.

Constitutional Constraints:
- FR40: No cessation_reversal event type in schema
- NFR40: Cessation reversal is architecturally prohibited
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-13: Integrity outranks availability -> System terminates permanently

All errors in this module inherit from ConstitutionalViolationError because
schema irreversibility is a FUNDAMENTAL constitutional constraint.
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class SchemaIrreversibilityError(ConstitutionalViolationError):
    """Raised when attempting to write events after system cessation.

    Constitutional Constraint (NFR40):
    Once a CESSATION_EXECUTED event is written, the system is permanently
    terminated. ANY attempt to write additional events is a violation of
    the schema irreversibility constraint.

    This error MUST NOT be caught or suppressed. It indicates the system
    is in a terminal state and no further writes are permitted.

    Examples:
        - Attempting to write any event after CESSATION_EXECUTED
        - Attempting to modify system state after cessation

    Usage:
        raise SchemaIrreversibilityError(
            "NFR40: Cannot write events after cessation. "
            f"System terminated at seq {terminal_seq}"
        )
    """

    pass


class EventTypeProhibitedError(ConstitutionalViolationError):
    """Raised when a prohibited event type is detected.

    Constitutional Constraint (NFR40):
    Certain event types are architecturally prohibited to prevent
    reversal of permanent system states (like cessation).

    Prohibited patterns include:
    - cessation_reversal, cessation.reversal
    - cessation_undo, cessation.undo
    - cessation_revert, cessation.revert
    - cessation_restore, cessation.restore
    - cessation_cancel, cessation.cancel
    - cessation_rollback, cessation.rollback
    - uncease, resurrect

    This error is raised at import time or during event type validation
    to prevent prohibited types from entering the system.

    Examples:
        - Attempting to register "cessation.reversal" event type
        - Import-time detection of prohibited event type constant

    Usage:
        raise EventTypeProhibitedError(
            "NFR40: Cessation reversal prohibited by schema. "
            f"Detected prohibited event type: {event_type}"
        )
    """

    pass


class TerminalEventViolationError(ConstitutionalViolationError):
    """Raised when attempting to write after a terminal event.

    Constitutional Constraint (FR40):
    A terminal event (is_terminal=True) marks the end of the event stream.
    No events may be written after a terminal event.

    This error is semantically similar to SchemaIrreversibilityError but
    specifically indicates the violation was detected by the terminal
    event detection mechanism rather than direct cessation check.

    Examples:
        - Writing event when is_system_terminated() returns True
        - Attempting to append to terminated event stream

    Usage:
        raise TerminalEventViolationError(
            "NFR40: Write rejected - terminal event detected. "
            f"System terminated at {timestamp}"
        )
    """

    pass


class CessationReversalAttemptError(ConstitutionalViolationError):
    """Raised when a cessation reversal is explicitly attempted.

    Constitutional Constraint (NFR40):
    Cessation is PERMANENT and IRREVERSIBLE by design. Any attempt to
    "undo", "revert", "cancel", or "reverse" a cessation is a fundamental
    constitutional violation.

    This error may be raised when:
    - An API endpoint receives a cessation reversal request
    - A service method attempts to clear cessation state
    - Any code path attempts to "un-cease" the system

    Examples:
        - API call to /v1/cessation/revert
        - Internal call to clear_cessation_state()
        - Attempt to set system state back to "active" after cessation

    Usage:
        raise CessationReversalAttemptError(
            "NFR40: Cessation reversal is architecturally prohibited. "
            "Cessation is permanent and irreversible by design."
        )
    """

    pass
