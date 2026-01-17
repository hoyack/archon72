"""Unit tests for ProblemReport domain model.

Story: consent-gov-2.4: Task Result Submission

Tests the ProblemReport value object for:
- Immutability (frozen dataclass)
- ProblemCategory enum (AC8)
- Description field (AC8)
- Cluster attribution (AC9)
- Timestamp tracking

References:
- FR7: Cluster can submit a problem report for an in-progress task
- AC8: Problem report includes categorized issue type and description
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestProblemCategoryEnum:
    """Tests for ProblemCategory enumeration."""

    def test_problem_category_can_be_imported(self) -> None:
        """Verify ProblemCategory can be imported from domain."""
        from src.domain.governance.task.problem_report import ProblemCategory

        assert ProblemCategory is not None

    def test_problem_category_has_required_values(self) -> None:
        """Verify ProblemCategory has all required categories."""
        from src.domain.governance.task.problem_report import ProblemCategory

        assert ProblemCategory.BLOCKED.value == "blocked"
        assert ProblemCategory.UNCLEAR_SPEC.value == "unclear_spec"
        assert ProblemCategory.RESOURCE_UNAVAILABLE.value == "resource_unavailable"
        assert ProblemCategory.TECHNICAL_ISSUE.value == "technical_issue"
        assert ProblemCategory.OTHER.value == "other"

    def test_problem_category_is_string_enum(self) -> None:
        """Verify ProblemCategory is a string enum for serialization."""
        from src.domain.governance.task.problem_report import ProblemCategory

        # Should be usable as string
        assert str(ProblemCategory.BLOCKED) == "ProblemCategory.BLOCKED"
        assert ProblemCategory.BLOCKED.value == "blocked"


class TestProblemReportDomainModel:
    """Tests for ProblemReport domain value object."""

    def test_problem_report_can_be_imported(self) -> None:
        """Verify ProblemReport can be imported from domain."""
        from src.domain.governance.task.problem_report import ProblemReport

        assert ProblemReport is not None

    def test_problem_report_is_frozen(self) -> None:
        """Verify ProblemReport is immutable."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )

        report = ProblemReport(
            task_id=uuid4(),
            cluster_id="cluster-1",
            category=ProblemCategory.BLOCKED,
            description="External API down",
            reported_at=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            report.description = "Changed"  # type: ignore[misc]

    def test_problem_report_fields(self) -> None:
        """Verify ProblemReport has all required fields."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )

        task_id = uuid4()
        cluster_id = "cluster-1"
        category = ProblemCategory.TECHNICAL_ISSUE
        description = "Database connection timeout"
        reported_at = datetime.now(timezone.utc)

        report = ProblemReport(
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


class TestProblemReportFactory:
    """Tests for ProblemReport factory method."""

    def test_problem_report_create_factory(self) -> None:
        """Verify ProblemReport.create() factory method works."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )

        task_id = uuid4()
        cluster_id = "cluster-1"
        category = ProblemCategory.UNCLEAR_SPEC
        description = "Task requirements are ambiguous"
        now = datetime.now(timezone.utc)

        report = ProblemReport.create(
            task_id=task_id,
            cluster_id=cluster_id,
            category=category,
            description=description,
            timestamp=now,
        )

        assert report.task_id == task_id
        assert report.cluster_id == cluster_id
        assert report.category == category
        assert report.description == description
        assert report.reported_at == now


class TestProblemReportEventPayload:
    """Tests for ProblemReport event payload conversion."""

    def test_problem_report_to_event_payload(self) -> None:
        """Verify ProblemReport can be converted to event payload."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )

        task_id = uuid4()
        cluster_id = "cluster-1"
        category = ProblemCategory.RESOURCE_UNAVAILABLE
        description = "Required file not found"
        reported_at = datetime.now(timezone.utc)

        report = ProblemReport(
            task_id=task_id,
            cluster_id=cluster_id,
            category=category,
            description=description,
            reported_at=reported_at,
        )

        payload = report.to_event_payload()

        assert payload["task_id"] == str(task_id)
        assert payload["cluster_id"] == cluster_id
        assert payload["category"] == "resource_unavailable"
        assert payload["description"] == description
        assert "reported_at" in payload


class TestProblemReportEquality:
    """Tests for ProblemReport equality and hashing."""

    def test_problem_report_equality(self) -> None:
        """Verify ProblemReport equality based on fields."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )

        task_id = uuid4()
        cluster_id = "cluster-1"
        category = ProblemCategory.BLOCKED
        description = "API timeout"
        reported_at = datetime.now(timezone.utc)

        report1 = ProblemReport(
            task_id=task_id,
            cluster_id=cluster_id,
            category=category,
            description=description,
            reported_at=reported_at,
        )
        report2 = ProblemReport(
            task_id=task_id,
            cluster_id=cluster_id,
            category=category,
            description=description,
            reported_at=reported_at,
        )

        assert report1 == report2

    def test_problem_report_inequality(self) -> None:
        """Verify ProblemReport inequality when fields differ."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )

        task_id = uuid4()
        reported_at = datetime.now(timezone.utc)

        report1 = ProblemReport(
            task_id=task_id,
            cluster_id="cluster-1",
            category=ProblemCategory.BLOCKED,
            description="API timeout",
            reported_at=reported_at,
        )
        report2 = ProblemReport(
            task_id=task_id,
            cluster_id="cluster-1",
            category=ProblemCategory.TECHNICAL_ISSUE,  # Different category
            description="API timeout",
            reported_at=reported_at,
        )

        assert report1 != report2

    def test_problem_report_hashable(self) -> None:
        """Verify ProblemReport can be hashed."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )

        report = ProblemReport(
            task_id=uuid4(),
            cluster_id="cluster-1",
            category=ProblemCategory.OTHER,
            description="Miscellaneous issue",
            reported_at=datetime.now(timezone.utc),
        )

        # Should be hashable (frozen dataclass with no mutable fields)
        h = hash(report)
        assert isinstance(h, int)

        # Should be usable in set
        s = {report}
        assert len(s) == 1


class TestProblemReportValidation:
    """Tests for ProblemReport validation behavior."""

    def test_problem_report_requires_non_empty_description(self) -> None:
        """Verify ProblemReport requires non-empty description."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )
        from src.domain.errors.constitutional import ConstitutionalViolationError

        with pytest.raises(ConstitutionalViolationError):
            ProblemReport(
                task_id=uuid4(),
                cluster_id="cluster-1",
                category=ProblemCategory.BLOCKED,
                description="",  # Empty description
                reported_at=datetime.now(timezone.utc),
            )

    def test_problem_report_requires_non_empty_cluster_id(self) -> None:
        """Verify ProblemReport requires non-empty cluster_id."""
        from src.domain.governance.task.problem_report import (
            ProblemCategory,
            ProblemReport,
        )
        from src.domain.errors.constitutional import ConstitutionalViolationError

        with pytest.raises(ConstitutionalViolationError):
            ProblemReport(
                task_id=uuid4(),
                cluster_id="",  # Empty cluster_id
                category=ProblemCategory.BLOCKED,
                description="API down",
                reported_at=datetime.now(timezone.utc),
            )
