"""Unit tests for TaskResult domain model.

Story: consent-gov-2.4: Task Result Submission

Tests the TaskResult value object for:
- Immutability (frozen dataclass)
- Structured output matching task spec (AC7)
- Cluster attribution (AC9)
- Timestamp tracking

References:
- FR6: Cluster can submit a task result report
- AC7: Result includes structured output matching task spec expectations
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestTaskResultDomainModel:
    """Tests for TaskResult domain value object."""

    def test_task_result_can_be_imported(self) -> None:
        """Verify TaskResult can be imported from domain."""
        from src.domain.governance.task.task_result import TaskResult

        assert TaskResult is not None

    def test_task_result_is_frozen(self) -> None:
        """Verify TaskResult is immutable."""
        from src.domain.governance.task.task_result import TaskResult

        result = TaskResult(
            task_id=uuid4(),
            cluster_id="cluster-1",
            output={"status": "done"},
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.cluster_id = "cluster-2"  # type: ignore[misc]

    def test_task_result_fields(self) -> None:
        """Verify TaskResult has all required fields."""
        from src.domain.governance.task.task_result import TaskResult

        task_id = uuid4()
        cluster_id = "cluster-1"
        output = {"completion": "done", "artifacts": ["file1.txt"]}
        submitted_at = datetime.now(timezone.utc)

        result = TaskResult(
            task_id=task_id,
            cluster_id=cluster_id,
            output=output,
            submitted_at=submitted_at,
        )

        assert result.task_id == task_id
        assert result.cluster_id == cluster_id
        assert result.output == output
        assert result.submitted_at == submitted_at

    def test_task_result_output_can_be_complex(self) -> None:
        """Verify output can contain complex nested structures."""
        from src.domain.governance.task.task_result import TaskResult

        output = {
            "status": "complete",
            "artifacts": [
                {"name": "report.pdf", "size": 1024},
                {"name": "data.json", "size": 512},
            ],
            "metrics": {
                "time_elapsed": 300,
                "items_processed": 42,
            },
        }

        result = TaskResult(
            task_id=uuid4(),
            cluster_id="cluster-1",
            output=output,
            submitted_at=datetime.now(timezone.utc),
        )

        assert result.output["artifacts"][0]["name"] == "report.pdf"
        assert result.output["metrics"]["items_processed"] == 42


class TestTaskResultValidation:
    """Tests for TaskResult validation behavior."""

    def test_task_result_requires_non_empty_cluster_id(self) -> None:
        """Verify TaskResult requires non-empty cluster_id.

        Per FR6: cluster_id is required for task result attribution.
        """
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.governance.task.task_result import TaskResult

        with pytest.raises(ConstitutionalViolationError):
            TaskResult(
                task_id=uuid4(),
                cluster_id="",  # Empty cluster_id
                output={"status": "done"},
                submitted_at=datetime.now(timezone.utc),
            )

    def test_task_result_requires_non_whitespace_cluster_id(self) -> None:
        """Verify TaskResult rejects whitespace-only cluster_id."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.governance.task.task_result import TaskResult

        with pytest.raises(ConstitutionalViolationError):
            TaskResult(
                task_id=uuid4(),
                cluster_id="   ",  # Whitespace-only cluster_id
                output={"status": "done"},
                submitted_at=datetime.now(timezone.utc),
            )

    def test_task_result_create_factory(self) -> None:
        """Verify TaskResult.create() factory method works."""
        from src.domain.governance.task.task_result import TaskResult

        task_id = uuid4()
        cluster_id = "cluster-1"
        output = {"done": True}
        now = datetime.now(timezone.utc)

        result = TaskResult.create(
            task_id=task_id,
            cluster_id=cluster_id,
            output=output,
            timestamp=now,
        )

        assert result.task_id == task_id
        assert result.cluster_id == cluster_id
        assert result.output == output
        assert result.submitted_at == now

    def test_task_result_validate_against_spec_exists(self) -> None:
        """Verify validate_against_spec method exists."""
        from src.domain.governance.task.task_result import TaskResult

        result = TaskResult(
            task_id=uuid4(),
            cluster_id="cluster-1",
            output={"status": "done"},
            submitted_at=datetime.now(timezone.utc),
        )

        assert hasattr(result, "validate_against_spec")
        assert callable(result.validate_against_spec)

    def test_task_result_to_event_payload(self) -> None:
        """Verify TaskResult can be converted to event payload."""
        from src.domain.governance.task.task_result import TaskResult

        task_id = uuid4()
        cluster_id = "cluster-1"
        output = {"status": "complete"}
        submitted_at = datetime.now(timezone.utc)

        result = TaskResult(
            task_id=task_id,
            cluster_id=cluster_id,
            output=output,
            submitted_at=submitted_at,
        )

        payload = result.to_event_payload()

        assert payload["task_id"] == str(task_id)
        assert payload["cluster_id"] == cluster_id
        assert payload["output"] == output
        assert "submitted_at" in payload


class TestTaskResultEquality:
    """Tests for TaskResult equality and hashing."""

    def test_task_result_equality(self) -> None:
        """Verify TaskResult equality based on fields."""
        from src.domain.governance.task.task_result import TaskResult

        task_id = uuid4()
        cluster_id = "cluster-1"
        output = {"status": "done"}
        submitted_at = datetime.now(timezone.utc)

        result1 = TaskResult(
            task_id=task_id,
            cluster_id=cluster_id,
            output=output,
            submitted_at=submitted_at,
        )
        result2 = TaskResult(
            task_id=task_id,
            cluster_id=cluster_id,
            output=output,
            submitted_at=submitted_at,
        )

        assert result1 == result2

    def test_task_result_inequality(self) -> None:
        """Verify TaskResult inequality when fields differ."""
        from src.domain.governance.task.task_result import TaskResult

        task_id = uuid4()
        submitted_at = datetime.now(timezone.utc)

        result1 = TaskResult(
            task_id=task_id,
            cluster_id="cluster-1",
            output={"status": "done"},
            submitted_at=submitted_at,
        )
        result2 = TaskResult(
            task_id=task_id,
            cluster_id="cluster-2",  # Different cluster
            output={"status": "done"},
            submitted_at=submitted_at,
        )

        assert result1 != result2

    def test_task_result_hashable(self) -> None:
        """Verify TaskResult can be used in sets (hashable)."""
        from src.domain.governance.task.task_result import TaskResult

        result = TaskResult(
            task_id=uuid4(),
            cluster_id="cluster-1",
            output={"status": "done"},
            submitted_at=datetime.now(timezone.utc),
        )

        # Should be hashable (frozen dataclass with custom __hash__)
        h = hash(result)
        assert isinstance(h, int)

        # Should be usable in set
        s = {result}
        assert len(s) == 1
