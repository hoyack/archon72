"""Contact violation domain model for dignified exit.

Story: consent-gov-7.4: Follow-Up Contact Prevention

Records when an attempt was made to contact a blocked Cluster.
These attempts are ALWAYS blocked, and a constitutional violation
event is emitted.

NFR-EXIT-02: Any attempt triggers constitutional violation event.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ContactViolation:
    """Record of attempted contact to a blocked Cluster.

    Contact attempts to exited Clusters are:
    1. Always blocked (structural)
    2. Always recorded (accountability)
    3. Always emit violation event (observability)

    This is a constitutional violation per NFR-EXIT-02.
    The Knight observes all such violations.

    Key Properties:
    - Immutable (frozen dataclass)
    - blocked is always True (structural enforcement)
    - Records the component that attempted contact
    - Enables pattern detection (repeated violations)

    Example:
        violation = ContactViolation(
            violation_id=uuid4(),
            cluster_id=exited_cluster_id,
            attempted_by="MessageRouter",
            attempted_at=time_authority.now(),
            blocked=True,  # Always True
        )
    """

    violation_id: UUID
    """Unique identifier for this violation record."""

    cluster_id: UUID
    """The Cluster that contact was attempted to."""

    attempted_by: str
    """Component or service that attempted contact.

    Examples: 'MessageRouter', 'NotificationService', 'API:/cluster/{id}/message'
    """

    attempted_at: datetime
    """When the contact attempt was made."""

    blocked: bool
    """Whether the contact was blocked. Always True.

    This field exists for explicit documentation in records.
    Contact to exited Clusters is ALWAYS blocked.
    """

    def __post_init__(self) -> None:
        """Validate that blocked is always True.

        Raises:
            ValueError: If blocked is not True.
        """
        if not self.blocked:
            raise ValueError(
                "ContactViolation.blocked must be True. "
                "Contact to exited Clusters is always blocked."
            )
