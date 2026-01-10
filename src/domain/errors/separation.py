"""Separation violation errors for Archon 72 (Story 8.2, FR52).

This module provides exception classes for operational-constitutional
separation violations.

Constitutional Constraint (FR52):
- Operational metrics (uptime, latency, errors) NEVER enter event store
- Constitutional events (votes, deliberations, halts) NEVER go to ops storage

Why This Matters:
- CT-12: Witnessing creates accountability - operational noise dilutes this
- CT-11: Silent failure destroys legitimacy - mixing data creates confusion
- CT-13: Integrity outranks availability - constitutional record must be pure
"""

from typing import Optional

from src.domain.errors.constitutional import ConstitutionalViolationError


class SeparationViolationError(ConstitutionalViolationError):
    """Base error for operational-constitutional separation violations.

    Raised when data is routed to the wrong storage target, violating
    the FR52 separation constraint.

    All separation violations are constitutional violations and MUST
    be treated with the same severity.
    """

    pass


class OperationalToEventStoreError(SeparationViolationError):
    """Raised when operational data attempts to enter the event store.

    This is a HARD violation of FR52 - operational metrics like uptime,
    latency, and error rates MUST NEVER pollute the constitutional event store.

    Attributes:
        data_type: The operational data type that was incorrectly routed.
        intended_target: The target storage that was incorrectly attempted.
        correct_target: The correct storage target for this data type.
    """

    def __init__(
        self,
        data_type: str,
        intended_target: Optional[str] = None,
        correct_target: Optional[str] = None,
    ) -> None:
        """Initialize OperationalToEventStoreError.

        Args:
            data_type: The operational data type that was incorrectly routed.
            intended_target: Optional target that was incorrectly attempted.
            correct_target: Optional correct target for this data.
        """
        self.data_type = data_type
        self.intended_target = intended_target or "event_store"
        self.correct_target = correct_target or "prometheus"

        message = (
            f"FR52 Violation: Operational data '{data_type}' cannot be written to "
            f"event store. Operational metrics MUST use Prometheus/operational "
            f"storage, not the constitutional event store."
        )
        super().__init__(message)


class ConstitutionalToOperationalError(SeparationViolationError):
    """Raised when constitutional data is incorrectly routed to operational storage.

    Constitutional events MUST be witnessed and stored in the event store.
    Routing them to operational storage (Prometheus, logs) violates FR52
    and breaks the witnessing chain required by CT-12.

    Attributes:
        data_type: The constitutional data type that was incorrectly routed.
        intended_target: The target storage that was incorrectly attempted.
        correct_target: The correct storage target for this data type.
    """

    def __init__(
        self,
        data_type: str,
        intended_target: Optional[str] = None,
        correct_target: Optional[str] = None,
    ) -> None:
        """Initialize ConstitutionalToOperationalError.

        Args:
            data_type: The constitutional data type that was incorrectly routed.
            intended_target: Optional target that was incorrectly attempted.
            correct_target: Optional correct target for this data.
        """
        self.data_type = data_type
        self.intended_target = intended_target or "operational_db"
        self.correct_target = correct_target or "event_store"

        message = (
            f"FR52 Violation: Constitutional event '{data_type}' cannot be written to "
            f"operational storage. Constitutional events MUST be witnessed and stored "
            f"in the event store, not operational storage."
        )
        super().__init__(message)
