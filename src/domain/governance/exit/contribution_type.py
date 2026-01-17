"""Contribution type enumeration for consent-based governance.

Story: consent-gov-7.3: Contribution Preservation

Defines the types of contributions a Cluster can make to the system.
These are tracked for attribution purposes on exit.

Constitutional Truths Honored:
- FR45: System can preserve Cluster's contribution history on exit
- NFR-INT-02: Public data only, no PII → attribution uses UUIDs only
"""

from __future__ import annotations

from enum import Enum


class ContributionType(Enum):
    """Type of contribution made by a Cluster.

    Per FR45: Contribution history is preserved on exit.
    Per NFR-INT-02: All data is public, no PII.

    Contribution types track WHAT the Cluster contributed,
    not WHO they are. Attribution is by Cluster ID (UUID) only.

    Values:
        TASK_COMPLETED: Cluster completed an assigned task.
        TASK_REPORTED: Cluster reported task results.
        DELIBERATION_PARTICIPATED: Cluster participated in deliberation.
    """

    TASK_COMPLETED = "task_completed"
    TASK_REPORTED = "task_reported"
    DELIBERATION_PARTICIPATED = "deliberation_participated"

    def __str__(self) -> str:
        """Return string representation."""
        return self.value
