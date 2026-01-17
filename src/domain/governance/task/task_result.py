"""TaskResult domain value object.

Story: consent-gov-2.4: Task Result Submission

This module defines the TaskResult frozen dataclass for representing
completed task work submitted by a Cluster.

Per AC7: Result includes structured output matching task spec expectations.

Constitutional Guarantees:
- Result is immutable once created
- Cluster attribution is always present
- Timestamp is always recorded

References:
- FR6: Cluster can submit a task result report
- AC7: Result includes structured output matching task spec expectations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


def _utc_now() -> datetime:
    """Return current UTC time with timezone info.

    This replaces deprecated datetime.utcnow() which returns naive datetime.
    """
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class TaskResult:
    """Immutable result of completed task work.

    Per FR6: Cluster can submit a task result report.
    Per AC7: Result includes structured output matching task spec expectations.

    This is a domain value object representing the result submitted by a
    Cluster for a completed task. It is immutable and captures:
    - Which task the result is for
    - Which Cluster submitted it
    - The structured output
    - When it was submitted

    Attributes:
        task_id: ID of the task this result is for.
        cluster_id: ID of the Cluster that submitted this result.
        output: Structured output matching task spec expectations.
        submitted_at: When the result was submitted.
    """

    task_id: UUID
    cluster_id: str
    output: dict[str, Any] = field(default_factory=dict)
    submitted_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Validate TaskResult fields.

        Ensures cluster_id is non-empty.
        """
        if not self.cluster_id or not self.cluster_id.strip():
            from src.domain.errors.constitutional import ConstitutionalViolationError
            raise ConstitutionalViolationError(
                "FR6: TaskResult requires non-empty cluster_id"
            )

    @classmethod
    def create(
        cls,
        *,
        task_id: UUID,
        cluster_id: str,
        output: dict[str, Any],
        timestamp: datetime,
    ) -> "TaskResult":
        """Factory method to create a TaskResult.

        Args:
            task_id: ID of the task this result is for.
            cluster_id: ID of the Cluster submitting the result.
            output: Structured output data.
            timestamp: Submission timestamp.

        Returns:
            New TaskResult instance.
        """
        return cls(
            task_id=task_id,
            cluster_id=cluster_id,
            output=output,
            submitted_at=timestamp,
        )

    def validate_against_spec(self, task_spec: dict[str, Any]) -> bool:
        """Validate result structure matches task spec expectations.

        Per AC7: Result includes structured output matching task spec.

        This method validates that the output structure conforms to what
        the task specification expects. Currently performs basic validation;
        can be extended for schema validation.

        Args:
            task_spec: Task specification with expected output schema.

        Returns:
            True if validation passes.

        Raises:
            ValueError: If validation fails.
        """
        # Basic validation - ensure output is non-empty if spec requires it
        expected_fields = task_spec.get("expected_output_fields", [])

        for field_name in expected_fields:
            if field_name not in self.output:
                raise ValueError(
                    f"FR6: Missing required output field: {field_name}"
                )

        return True

    def to_event_payload(self) -> dict[str, Any]:
        """Convert to event payload format.

        Returns:
            Dictionary suitable for event emission.
        """
        return {
            "task_id": str(self.task_id),
            "cluster_id": self.cluster_id,
            "output": self.output,
            "submitted_at": self.submitted_at.isoformat(),
        }

    def __hash__(self) -> int:
        """Custom hash for frozen dataclass with dict field.

        Since output is a mutable dict, we need custom hashing.
        We hash only the immutable fields for safety.
        """
        return hash((self.task_id, self.cluster_id, self.submitted_at))
