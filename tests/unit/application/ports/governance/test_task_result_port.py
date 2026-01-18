"""Unit tests for TaskResultPort interface.

Story: consent-gov-2.4: Task Result Submission

Tests the TaskResultPort abstract interface for:
- submit_result() method definition (AC1)
- submit_problem_report() method definition (AC2)
- Cluster authorization validation (AC9)

References:
- FR6: Cluster can submit a task result report
- FR7: Cluster can submit a problem report for an in-progress task
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    pass


class TestTaskResultPortInterface:
    """Tests to verify TaskResultPort interface contract."""

    def test_task_result_port_exists(self) -> None:
        """Verify TaskResultPort can be imported."""
        from src.application.ports.governance.task_result_port import (
            TaskResultPort,
        )

        assert TaskResultPort is not None

    def test_task_result_port_is_abstract(self) -> None:
        """Verify TaskResultPort cannot be instantiated directly."""
        from src.application.ports.governance.task_result_port import (
            TaskResultPort,
        )

        with pytest.raises(TypeError):
            TaskResultPort()  # type: ignore[abstract]

    def test_submit_result_method_exists(self) -> None:
        """Verify submit_result method is defined."""
        from src.application.ports.governance.task_result_port import (
            TaskResultPort,
        )

        assert hasattr(TaskResultPort, "submit_result")
        assert callable(getattr(TaskResultPort, "submit_result", None))

    def test_submit_problem_report_method_exists(self) -> None:
        """Verify submit_problem_report method is defined."""
        from src.application.ports.governance.task_result_port import (
            TaskResultPort,
        )

        assert hasattr(TaskResultPort, "submit_problem_report")
        assert callable(getattr(TaskResultPort, "submit_problem_report", None))


class TestTaskResultDataClasses:
    """Tests for TaskResult port data classes."""

    def test_task_result_value_exists(self) -> None:
        """Verify TaskResultValue can be imported."""
        from src.application.ports.governance.task_result_port import (
            TaskResultValue,
        )

        assert TaskResultValue is not None

    def test_task_result_value_is_frozen(self) -> None:
        """Verify TaskResultValue is immutable."""
        from datetime import datetime, timezone

        from src.application.ports.governance.task_result_port import (
            TaskResultValue,
        )

        result = TaskResultValue(
            task_id=uuid4(),
            cluster_id="cluster-1",
            output={"status": "done"},
            submitted_at=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.cluster_id = "cluster-2"  # type: ignore[misc]

    def test_task_result_value_fields(self) -> None:
        """Verify TaskResultValue has required fields."""
        from datetime import datetime, timezone

        from src.application.ports.governance.task_result_port import (
            TaskResultValue,
        )

        task_id = uuid4()
        cluster_id = "cluster-1"
        output = {"completion": "done", "artifacts": ["file1.txt"]}
        submitted_at = datetime.now(timezone.utc)

        result = TaskResultValue(
            task_id=task_id,
            cluster_id=cluster_id,
            output=output,
            submitted_at=submitted_at,
        )

        assert result.task_id == task_id
        assert result.cluster_id == cluster_id
        assert result.output == output
        assert result.submitted_at == submitted_at


class TestProblemReportDataClasses:
    """Tests for ProblemReport port data classes."""

    def test_problem_category_exists(self) -> None:
        """Verify ProblemCategory enum can be imported."""
        from src.application.ports.governance.task_result_port import (
            ProblemCategory,
        )

        assert ProblemCategory is not None

    def test_problem_category_values(self) -> None:
        """Verify ProblemCategory has required values."""
        from src.application.ports.governance.task_result_port import (
            ProblemCategory,
        )

        assert ProblemCategory.BLOCKED.value == "blocked"
        assert ProblemCategory.UNCLEAR_SPEC.value == "unclear_spec"
        assert ProblemCategory.RESOURCE_UNAVAILABLE.value == "resource_unavailable"
        assert ProblemCategory.TECHNICAL_ISSUE.value == "technical_issue"
        assert ProblemCategory.OTHER.value == "other"

    def test_problem_report_value_exists(self) -> None:
        """Verify ProblemReportValue can be imported."""
        from src.application.ports.governance.task_result_port import (
            ProblemReportValue,
        )

        assert ProblemReportValue is not None

    def test_problem_report_value_is_frozen(self) -> None:
        """Verify ProblemReportValue is immutable."""
        from datetime import datetime, timezone

        from src.application.ports.governance.task_result_port import (
            ProblemCategory,
            ProblemReportValue,
        )

        report = ProblemReportValue(
            task_id=uuid4(),
            cluster_id="cluster-1",
            category=ProblemCategory.BLOCKED,
            description="External API down",
            reported_at=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            report.description = "Changed"  # type: ignore[misc]

    def test_problem_report_value_fields(self) -> None:
        """Verify ProblemReportValue has required fields."""
        from datetime import datetime, timezone

        from src.application.ports.governance.task_result_port import (
            ProblemCategory,
            ProblemReportValue,
        )

        task_id = uuid4()
        cluster_id = "cluster-1"
        category = ProblemCategory.TECHNICAL_ISSUE
        description = "Database connection timeout"
        reported_at = datetime.now(timezone.utc)

        report = ProblemReportValue(
            task_id=task_id,
            cluster_id=cluster_id,
            category=category,
            description=description,
            reported_at=reported_at,
        )

        assert report.task_id == task_id
        assert report.cluster_id == cluster_id
        assert report.category == category
        assert report.description == description
        assert report.reported_at == reported_at


class TestResultSubmissionResult:
    """Tests for ResultSubmissionResult data class."""

    def test_result_submission_result_exists(self) -> None:
        """Verify ResultSubmissionResult can be imported."""
        from src.application.ports.governance.task_result_port import (
            ResultSubmissionResult,
        )

        assert ResultSubmissionResult is not None

    def test_result_submission_result_fields(self) -> None:
        """Verify ResultSubmissionResult has required fields."""
        from datetime import datetime, timezone

        from src.application.ports.governance.task_result_port import (
            ResultSubmissionResult,
            TaskResultValue,
        )

        task_id = uuid4()
        result_value = TaskResultValue(
            task_id=task_id,
            cluster_id="cluster-1",
            output={"done": True},
            submitted_at=datetime.now(timezone.utc),
        )

        submission = ResultSubmissionResult(
            success=True,
            result=result_value,
            new_status="reported",
            message="Task result submitted successfully",
        )

        assert submission.success is True
        assert submission.result == result_value
        assert submission.new_status == "reported"
        assert submission.message == "Task result submitted successfully"


class TestTaskResultErrors:
    """Tests for TaskResult port error types."""

    def test_unauthorized_result_error_exists(self) -> None:
        """Verify UnauthorizedResultError can be imported."""
        from src.application.ports.governance.task_result_port import (
            UnauthorizedResultError,
        )

        assert UnauthorizedResultError is not None

    def test_unauthorized_result_error_fields(self) -> None:
        """Verify UnauthorizedResultError captures required info."""
        from src.application.ports.governance.task_result_port import (
            UnauthorizedResultError,
        )

        task_id = uuid4()
        error = UnauthorizedResultError(
            cluster_id="wrong-cluster",
            task_id=task_id,
            message="Only assigned Cluster can submit results",
        )

        assert error.cluster_id == "wrong-cluster"
        assert error.task_id == task_id
        assert "Only assigned Cluster" in str(error)

    def test_invalid_result_state_error_exists(self) -> None:
        """Verify InvalidResultStateError can be imported."""
        from src.application.ports.governance.task_result_port import (
            InvalidResultStateError,
        )

        assert InvalidResultStateError is not None

    def test_invalid_result_state_error_fields(self) -> None:
        """Verify InvalidResultStateError captures required info."""
        from src.application.ports.governance.task_result_port import (
            InvalidResultStateError,
        )

        task_id = uuid4()
        error = InvalidResultStateError(
            task_id=task_id,
            current_state="accepted",
            operation="submit_result",
        )

        assert error.task_id == task_id
        assert error.current_state == "accepted"
        assert error.operation == "submit_result"
        assert "accepted" in str(error)
