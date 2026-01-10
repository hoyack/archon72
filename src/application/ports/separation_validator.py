"""Separation Validator Port - FR52 Operational-Constitutional Separation.

This port defines the interface for classifying data as either:
- CONSTITUTIONAL: Belongs in the event store (witnessed events)
- OPERATIONAL: Belongs in Prometheus/operational storage (metrics)

Constitutional Constraint (FR52):
- Operational metrics (uptime, latency, errors) NEVER enter event store
- Constitutional events (votes, deliberations, halts) NEVER go to ops storage
- This is a HARD separation - not a preference, a constitutional constraint

Why This Matters:
- CT-12: Witnessing creates accountability - operational noise would dilute this
- CT-11: Silent failure destroys legitimacy - mixing data creates confusion
- CT-13: Integrity outranks availability - constitutional record must be pure
"""

from enum import Enum
from typing import Protocol, runtime_checkable


class DataClassification(Enum):
    """Classification of data for storage routing.

    Used to determine whether data should be stored in:
    - Event store (CONSTITUTIONAL)
    - Prometheus/operational storage (OPERATIONAL)
    - Requires manual classification (UNKNOWN)
    """

    CONSTITUTIONAL = "constitutional"
    OPERATIONAL = "operational"
    UNKNOWN = "unknown"


@runtime_checkable
class SeparationValidatorPort(Protocol):
    """Port for validating operational-constitutional data separation.

    This port enables the enforcement of FR52 - ensuring operational
    metrics never pollute the constitutional event store.

    Implementations must classify data types and provide helper methods
    for routing decisions.
    """

    def classify_data(self, data_type: str) -> DataClassification:
        """Classify a data type as constitutional, operational, or unknown.

        Args:
            data_type: The type identifier for the data (e.g., "vote_cast",
                "uptime_recorded", "halt_triggered").

        Returns:
            DataClassification indicating where this data should be stored.
        """
        ...

    def is_constitutional(self, data_type: str) -> bool:
        """Check if a data type is constitutional (event store eligible).

        Args:
            data_type: The type identifier to check.

        Returns:
            True if the data type belongs in the constitutional event store.
        """
        ...

    def is_operational(self, data_type: str) -> bool:
        """Check if a data type is operational (Prometheus/ops storage).

        Args:
            data_type: The type identifier to check.

        Returns:
            True if the data type belongs in operational storage.
        """
        ...

    def get_allowed_event_types(self) -> set[str]:
        """Get all constitutional event types allowed in event store.

        Returns:
            Set of event type strings that are permitted in the event store.
            Any event type NOT in this set should be rejected by the event store.
        """
        ...
