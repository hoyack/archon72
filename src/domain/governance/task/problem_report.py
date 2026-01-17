"""ProblemReport domain value object.

Story: consent-gov-2.4: Task Result Submission

This module defines the ProblemCategory enumeration and ProblemReport
frozen dataclass for representing issues reported during task execution.

Per AC8: Problem report includes categorized issue type and description.

Constitutional Guarantees:
- Problem report is immutable once created
- Cluster attribution is always present
- Category and description are always recorded
- NO state transition occurs (task remains IN_PROGRESS)

References:
- FR7: Cluster can submit a problem report for an in-progress task
- AC8: Problem report includes categorized issue type and description
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError


class ProblemCategory(str, Enum):
    """Categories for problem reports.

    Used to classify issues encountered during task execution.
    Per AC8: Problem report includes categorized issue type.

    Categories:
    - BLOCKED: External blocker preventing progress
    - UNCLEAR_SPEC: Task specification is ambiguous or incomplete
    - RESOURCE_UNAVAILABLE: Required resource is not available
    - TECHNICAL_ISSUE: Technical problem encountered during execution
    - OTHER: Other issue not covered by specific categories
    """

    BLOCKED = "blocked"
    """External blocker preventing progress."""

    UNCLEAR_SPEC = "unclear_spec"
    """Task specification is ambiguous or incomplete."""

    RESOURCE_UNAVAILABLE = "resource_unavailable"
    """Required resource is not available."""

    TECHNICAL_ISSUE = "technical_issue"
    """Technical problem encountered during execution."""

    OTHER = "other"
    """Other issue not covered by specific categories."""


@dataclass(frozen=True)
class ProblemReport:
    """Immutable problem report for in-progress task.

    Per FR7: Cluster can submit a problem report for an in-progress task.
    Per AC8: Problem report includes categorized issue type and description.

    This is a domain value object representing a problem reported by a
    Cluster for an in-progress task. It is immutable and captures:
    - Which task the problem is for
    - Which Cluster reported it
    - The category of the problem
    - A description of the issue
    - When it was reported

    IMPORTANT: Problem reports do NOT trigger state transitions.
    The task remains IN_PROGRESS. This allows:
    - Cluster to continue working
    - Duke/Earl to be notified
    - Escalation to occur if needed

    Attributes:
        task_id: ID of the task this report is for.
        cluster_id: ID of the Cluster that reported this problem.
        category: Category of the problem.
        description: Description of the problem.
        reported_at: When the problem was reported.
    """

    task_id: UUID
    cluster_id: str
    category: ProblemCategory
    description: str
    reported_at: datetime

    def __post_init__(self) -> None:
        """Validate ProblemReport fields.

        Ensures cluster_id and description are non-empty.
        """
        if not self.cluster_id or not self.cluster_id.strip():
            raise ConstitutionalViolationError(
                "FR7: ProblemReport requires non-empty cluster_id"
            )
        if not self.description or not self.description.strip():
            raise ConstitutionalViolationError(
                "FR7: ProblemReport requires non-empty description"
            )

    @classmethod
    def create(
        cls,
        *,
        task_id: UUID,
        cluster_id: str,
        category: ProblemCategory,
        description: str,
        timestamp: datetime,
    ) -> "ProblemReport":
        """Factory method to create a ProblemReport.

        Args:
            task_id: ID of the task this report is for.
            cluster_id: ID of the Cluster reporting the problem.
            category: Category of the problem.
            description: Description of the problem.
            timestamp: Report timestamp.

        Returns:
            New ProblemReport instance.
        """
        return cls(
            task_id=task_id,
            cluster_id=cluster_id,
            category=category,
            description=description,
            reported_at=timestamp,
        )

    def to_event_payload(self) -> dict[str, Any]:
        """Convert to event payload format.

        Returns:
            Dictionary suitable for event emission.
        """
        return {
            "task_id": str(self.task_id),
            "cluster_id": self.cluster_id,
            "category": self.category.value,
            "description": self.description,
            "reported_at": self.reported_at.isoformat(),
        }
