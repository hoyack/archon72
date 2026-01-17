"""Unit tests for Duke Service port (Epic 4, Story 4.1).

Tests:
- ExecutionDomain model creation
- ResourceAllocation model creation
- ProgressReport model creation
- StatusReport model creation
- DomainStatus and ResourceType enums
- Immutability of frozen dataclasses

Constitutional Constraints:
- FR-GOV-11: Duke Authority - Own execution domains, allocate resources, track progress
- FR-GOV-13: No reinterpretation of intent, no suppression of failure signals
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


class TestDomainStatusEnum:
    """Test DomainStatus enum."""

    def test_all_statuses_defined(self) -> None:
        """All domain statuses are defined."""
        from src.application.ports.duke_service import DomainStatus

        expected = {"available", "owned", "executing", "blocked", "completed"}
        actual = {s.value for s in DomainStatus}
        assert actual == expected


class TestResourceTypeEnum:
    """Test ResourceType enum."""

    def test_all_resource_types_defined(self) -> None:
        """All resource types are defined."""
        from src.application.ports.duke_service import ResourceType

        expected = {"compute", "memory", "agents", "storage", "network", "time"}
        actual = {r.value for r in ResourceType}
        assert actual == expected


class TestTaskProgressStatusEnum:
    """Test TaskProgressStatus enum."""

    def test_all_progress_statuses_defined(self) -> None:
        """All progress statuses are defined."""
        from src.application.ports.duke_service import TaskProgressStatus

        expected = {"not_started", "in_progress", "blocked", "completed", "failed"}
        actual = {s.value for s in TaskProgressStatus}
        assert actual == expected


class TestExecutionDomain:
    """Test ExecutionDomain dataclass."""

    def test_create_domain(self) -> None:
        """ExecutionDomain.create() produces valid domain."""
        from src.application.ports.duke_service import (
            DomainStatus,
            ExecutionDomain,
        )

        now = datetime.now(timezone.utc)
        domain = ExecutionDomain.create(
            domain_id="domain-001",
            name="Test Domain",
            description="A test execution domain",
            boundaries=["scope-1", "scope-2"],
            timestamp=now,
        )

        assert domain.domain_id == "domain-001"
        assert domain.name == "Test Domain"
        assert domain.status == DomainStatus.AVAILABLE
        assert domain.boundaries == ("scope-1", "scope-2")
        assert domain.owner_archon_id is None
        assert domain.created_at == now

    def test_domain_is_frozen(self) -> None:
        """ExecutionDomain is immutable."""
        from src.application.ports.duke_service import ExecutionDomain

        domain = ExecutionDomain.create(
            domain_id="domain-001",
            name="Test Domain",
            description="A test domain",
            boundaries=[],
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            domain.name = "Modified"  # type: ignore

    def test_domain_to_dict(self) -> None:
        """ExecutionDomain serializes to dictionary."""
        from src.application.ports.duke_service import ExecutionDomain

        domain = ExecutionDomain.create(
            domain_id="domain-001",
            name="Test Domain",
            description="A test domain",
            boundaries=["scope-1"],
            timestamp=datetime.now(timezone.utc),
        )

        d = domain.to_dict()

        assert d["domain_id"] == "domain-001"
        assert d["name"] == "Test Domain"
        assert d["status"] == "available"
        assert d["boundaries"] == ["scope-1"]


class TestResourceAllocation:
    """Test ResourceAllocation dataclass."""

    def test_create_allocation(self) -> None:
        """ResourceAllocation.create() produces valid allocation."""
        from src.application.ports.duke_service import (
            ResourceAllocation,
            ResourceType,
        )

        task_id = uuid4()
        now = datetime.now(timezone.utc)
        allocation = ResourceAllocation.create(
            task_id=task_id,
            resource_type=ResourceType.COMPUTE,
            amount=4,
            unit="cores",
            allocated_by="duke-archon-001",
            timestamp=now,
            constraints=["max-4-cores"],
        )

        assert allocation.task_id == task_id
        assert allocation.resource_type == ResourceType.COMPUTE
        assert allocation.amount == 4
        assert allocation.unit == "cores"
        assert allocation.allocated_by == "duke-archon-001"
        assert allocation.constraints == ("max-4-cores",)
        assert allocation.allocated_at == now

    def test_allocation_is_frozen(self) -> None:
        """ResourceAllocation is immutable."""
        from src.application.ports.duke_service import (
            ResourceAllocation,
            ResourceType,
        )

        allocation = ResourceAllocation.create(
            task_id=uuid4(),
            resource_type=ResourceType.MEMORY,
            amount=8,
            unit="GB",
            allocated_by="duke-001",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            allocation.amount = 16  # type: ignore

    def test_allocation_with_expiry(self) -> None:
        """ResourceAllocation can have expiry time."""
        from src.application.ports.duke_service import (
            ResourceAllocation,
            ResourceType,
        )

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=1)
        allocation = ResourceAllocation.create(
            task_id=uuid4(),
            resource_type=ResourceType.TIME,
            amount=60,
            unit="minutes",
            allocated_by="duke-001",
            timestamp=now,
            expires_at=expires,
        )

        assert allocation.expires_at == expires


class TestProgressReport:
    """Test ProgressReport dataclass."""

    def test_create_progress_report(self) -> None:
        """ProgressReport.create() produces valid report."""
        from src.application.ports.duke_service import (
            ProgressReport,
            TaskProgressStatus,
        )

        task_id = uuid4()
        now = datetime.now(timezone.utc)
        report = ProgressReport.create(
            task_id=task_id,
            status=TaskProgressStatus.IN_PROGRESS,
            percent_complete=45.5,
            metrics={"throughput": 100.0, "latency_ms": 50.0},
            reported_by="duke-archon-001",
            timestamp=now,
        )

        assert report.task_id == task_id
        assert report.status == TaskProgressStatus.IN_PROGRESS
        assert report.percent_complete == 45.5
        assert report.metrics["throughput"] == 100.0
        assert report.reported_by == "duke-archon-001"
        assert report.reported_at == now

    def test_progress_report_with_blockers(self) -> None:
        """ProgressReport can include blockers."""
        from src.application.ports.duke_service import (
            ProgressReport,
            TaskProgressStatus,
        )

        report = ProgressReport.create(
            task_id=uuid4(),
            status=TaskProgressStatus.BLOCKED,
            percent_complete=30.0,
            metrics={},
            reported_by="duke-001",
            timestamp=datetime.now(timezone.utc),
            blockers=["Waiting for resource", "Dependency failed"],
        )

        assert report.status == TaskProgressStatus.BLOCKED
        assert len(report.blockers) == 2
        assert "Waiting for resource" in report.blockers

    def test_progress_report_is_frozen(self) -> None:
        """ProgressReport is immutable."""
        from src.application.ports.duke_service import (
            ProgressReport,
            TaskProgressStatus,
        )

        report = ProgressReport.create(
            task_id=uuid4(),
            status=TaskProgressStatus.IN_PROGRESS,
            percent_complete=50.0,
            metrics={},
            reported_by="duke-001",
            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            report.percent_complete = 100.0  # type: ignore


class TestStatusReport:
    """Test StatusReport dataclass."""

    def test_create_status_report(self) -> None:
        """StatusReport.create() produces valid report."""
        from src.application.ports.duke_service import (
            StatusReport,
            TaskProgressStatus,
        )

        task_id = uuid4()
        motion_ref = uuid4()
        now = datetime.now(timezone.utc)
        report = StatusReport.create(
            task_id=task_id,
            domain_id="domain-001",
            status=TaskProgressStatus.COMPLETED,
            summary="Task completed successfully",
            details={"output": "result", "artifacts": ["file1", "file2"]},
            reported_by="duke-archon-001",
            timestamp=now,
            motion_ref=motion_ref,
        )

        assert report.task_id == task_id
        assert report.domain_id == "domain-001"
        assert report.status == TaskProgressStatus.COMPLETED
        assert report.summary == "Task completed successfully"
        assert report.motion_ref == motion_ref
        assert report.reported_at == now

    def test_status_report_to_dict(self) -> None:
        """StatusReport serializes to dictionary."""
        from src.application.ports.duke_service import (
            StatusReport,
            TaskProgressStatus,
        )

        task_id = uuid4()
        report = StatusReport.create(
            task_id=task_id,
            domain_id="domain-001",
            status=TaskProgressStatus.FAILED,
            summary="Task failed",
            details={"error": "Something went wrong"},
            reported_by="duke-001",
            timestamp=datetime.now(timezone.utc),
        )

        d = report.to_dict()

        assert d["task_id"] == str(task_id)
        assert d["domain_id"] == "domain-001"
        assert d["status"] == "failed"
        assert d["summary"] == "Task failed"


class TestRequestAndResultDataclasses:
    """Test request and result dataclasses."""

    def test_domain_ownership_request(self) -> None:
        """DomainOwnershipRequest holds request data."""
        from src.application.ports.duke_service import DomainOwnershipRequest

        request = DomainOwnershipRequest(
            duke_id="duke-archon-001",
            domain_id="domain-001",
        )

        assert request.duke_id == "duke-archon-001"
        assert request.domain_id == "domain-001"

    def test_resource_allocation_request(self) -> None:
        """ResourceAllocationRequest holds allocation request data."""
        from src.application.ports.duke_service import (
            ResourceAllocationRequest,
            ResourceType,
        )

        task_id = uuid4()
        request = ResourceAllocationRequest(
            duke_id="duke-001",
            task_id=task_id,
            resource_type=ResourceType.AGENTS,
            amount=3,
            unit="agents",
            constraints=["max-priority"],
        )

        assert request.duke_id == "duke-001"
        assert request.task_id == task_id
        assert request.resource_type == ResourceType.AGENTS
        assert request.amount == 3
