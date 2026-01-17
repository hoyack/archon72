"""Duke Service Port (Administrative Branch - Senior).

This module defines the abstract protocol for Duke-rank administrative functions.
Dukes own execution domains, allocate resources, track progress, and report status.

Per Government PRD FR-GOV-11: Duke Authority - Own execution domains, allocate
resources, track progress, report status.
Per Government PRD FR-GOV-13: Duke Constraints - No reinterpretation of intent,
no suppression of failure signals.

HARDENING-1: All timestamps must be provided via TimeAuthorityProtocol injection.
Factory methods require explicit timestamp parameters - no datetime.now() calls.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class DomainStatus(Enum):
    """Status of an execution domain."""

    AVAILABLE = "available"  # Domain is available for assignment
    OWNED = "owned"  # Domain is owned by a Duke
    EXECUTING = "executing"  # Tasks are actively executing
    BLOCKED = "blocked"  # Domain execution is blocked
    COMPLETED = "completed"  # All tasks completed


class ResourceType(Enum):
    """Types of resources that can be allocated."""

    COMPUTE = "compute"
    MEMORY = "memory"
    AGENTS = "agents"
    STORAGE = "storage"
    NETWORK = "network"
    TIME = "time"


class TaskProgressStatus(Enum):
    """Progress status for task execution."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ExecutionDomain:
    """A domain owned by a Duke for task execution.

    Per FR-GOV-11: Dukes own execution domains and allocate resources.
    Immutable to ensure domain integrity.
    """

    domain_id: str
    name: str
    description: str
    boundaries: tuple[str, ...]  # Scope constraints
    status: DomainStatus
    created_at: datetime
    assigned_tasks: tuple[UUID, ...] = ()
    owner_archon_id: str | None = None

    @classmethod
    def create(
        cls,
        domain_id: str,
        name: str,
        description: str,
        boundaries: list[str],
        timestamp: datetime,
    ) -> "ExecutionDomain":
        """Create a new execution domain.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            domain_id: Unique identifier for the domain
            name: Human-readable domain name
            description: Domain description
            boundaries: Scope constraints for the domain
            timestamp: Current time from TimeAuthorityProtocol

        Returns:
            New immutable ExecutionDomain with AVAILABLE status
        """
        return cls(
            domain_id=domain_id,
            name=name,
            description=description,
            boundaries=tuple(boundaries),
            status=DomainStatus.AVAILABLE,
            created_at=timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "domain_id": self.domain_id,
            "name": self.name,
            "description": self.description,
            "boundaries": list(self.boundaries),
            "status": self.status.value,
            "assigned_tasks": [str(t) for t in self.assigned_tasks],
            "owner_archon_id": self.owner_archon_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class ResourceAllocation:
    """Resource allocation within a Duke's domain.

    Immutable to ensure allocation integrity.
    """

    allocation_id: UUID
    task_id: UUID
    resource_type: ResourceType
    amount: int
    unit: str  # e.g., "cores", "GB", "agents"
    allocated_at: datetime
    constraints: tuple[str, ...] = ()
    allocated_by: str | None = None  # Duke Archon ID
    expires_at: datetime | None = None

    @classmethod
    def create(
        cls,
        task_id: UUID,
        resource_type: ResourceType,
        amount: int,
        unit: str,
        allocated_by: str,
        timestamp: datetime,
        constraints: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> "ResourceAllocation":
        """Create a new resource allocation.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            task_id: Task receiving the resources
            resource_type: Type of resource
            amount: Quantity of resource
            unit: Unit of measurement
            allocated_by: Duke Archon ID
            timestamp: Current time from TimeAuthorityProtocol
            constraints: Resource usage constraints
            expires_at: When allocation expires

        Returns:
            New immutable ResourceAllocation
        """
        return cls(
            allocation_id=uuid4(),
            task_id=task_id,
            resource_type=resource_type,
            amount=amount,
            unit=unit,
            allocated_at=timestamp,
            constraints=tuple(constraints or []),
            allocated_by=allocated_by,
            expires_at=expires_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "allocation_id": str(self.allocation_id),
            "task_id": str(self.task_id),
            "resource_type": self.resource_type.value,
            "amount": self.amount,
            "unit": self.unit,
            "constraints": list(self.constraints),
            "allocated_by": self.allocated_by,
            "allocated_at": self.allocated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass(frozen=True)
class ProgressReport:
    """Progress tracking data for task execution."""

    report_id: UUID
    task_id: UUID
    status: TaskProgressStatus
    percent_complete: float  # 0.0 to 100.0
    metrics: dict[str, float]  # Execution metrics
    reported_at: datetime
    blockers: tuple[str, ...] = ()
    reported_by: str | None = None  # Duke Archon ID

    @classmethod
    def create(
        cls,
        task_id: UUID,
        status: TaskProgressStatus,
        percent_complete: float,
        metrics: dict[str, float],
        reported_by: str,
        timestamp: datetime,
        blockers: list[str] | None = None,
    ) -> "ProgressReport":
        """Create a new progress report.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            task_id: Task being reported on
            status: Current progress status
            percent_complete: Completion percentage
            metrics: Execution metrics
            reported_by: Duke Archon ID
            timestamp: Current time from TimeAuthorityProtocol
            blockers: Any blocking issues

        Returns:
            New immutable ProgressReport
        """
        return cls(
            report_id=uuid4(),
            task_id=task_id,
            status=status,
            percent_complete=percent_complete,
            metrics=metrics,
            reported_at=timestamp,
            blockers=tuple(blockers or []),
            reported_by=reported_by,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "report_id": str(self.report_id),
            "task_id": str(self.task_id),
            "status": self.status.value,
            "percent_complete": self.percent_complete,
            "metrics": self.metrics,
            "blockers": list(self.blockers),
            "reported_by": self.reported_by,
            "reported_at": self.reported_at.isoformat(),
        }


@dataclass(frozen=True)
class StatusReport:
    """Execution status report with full details."""

    report_id: UUID
    task_id: UUID
    domain_id: str
    status: TaskProgressStatus
    summary: str
    details: dict[str, Any]
    reported_by: str  # Duke Archon ID
    reported_at: datetime
    motion_ref: UUID | None = None

    @classmethod
    def create(
        cls,
        task_id: UUID,
        domain_id: str,
        status: TaskProgressStatus,
        summary: str,
        details: dict[str, Any],
        reported_by: str,
        timestamp: datetime,
        motion_ref: UUID | None = None,
    ) -> "StatusReport":
        """Create a new status report.

        HARDENING-1: timestamp is required - use time_authority.now()

        Args:
            task_id: Task being reported on
            domain_id: Domain containing the task
            status: Current status
            summary: Brief status summary
            details: Full status details
            reported_by: Duke Archon ID
            timestamp: Current time from TimeAuthorityProtocol
            motion_ref: Related motion if any

        Returns:
            New immutable StatusReport
        """
        return cls(
            report_id=uuid4(),
            task_id=task_id,
            domain_id=domain_id,
            status=status,
            summary=summary,
            details=details,
            reported_by=reported_by,
            reported_at=timestamp,
            motion_ref=motion_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "report_id": str(self.report_id),
            "task_id": str(self.task_id),
            "domain_id": self.domain_id,
            "status": self.status.value,
            "summary": self.summary,
            "details": self.details,
            "reported_by": self.reported_by,
            "reported_at": self.reported_at.isoformat(),
            "motion_ref": str(self.motion_ref) if self.motion_ref else None,
        }


@dataclass
class DomainOwnershipRequest:
    """Request to take ownership of a domain."""

    duke_id: str  # Duke Archon ID
    domain_id: str


@dataclass
class DomainOwnershipResult:
    """Result of taking domain ownership."""

    success: bool
    domain: ExecutionDomain | None = None
    error: str | None = None


@dataclass
class ResourceAllocationRequest:
    """Request to allocate resources to a task."""

    duke_id: str  # Duke Archon ID
    task_id: UUID
    resource_type: ResourceType
    amount: int
    unit: str
    constraints: list[str] | None = None
    expires_at: datetime | None = None


@dataclass
class ResourceAllocationResult:
    """Result of resource allocation."""

    success: bool
    allocation: ResourceAllocation | None = None
    error: str | None = None


@dataclass
class ProgressTrackingResult:
    """Result of tracking progress."""

    success: bool
    report: ProgressReport | None = None
    error: str | None = None


@dataclass
class StatusReportResult:
    """Result of status reporting."""

    success: bool
    report: StatusReport | None = None
    error: str | None = None


class DukeServiceProtocol(ABC):
    """Abstract protocol for Duke-rank administrative functions.

    Per Government PRD:
    - FR-GOV-11: Own execution domains, allocate resources, track progress, report status
    - FR-GOV-13: No reinterpretation of intent, no suppression of failure signals

    This protocol explicitly EXCLUDES:
    - Motion introduction (King function)
    - Execution definition (President function) - Dukes execute, not define
    - Intent interpretation (Constitutional prohibition)
    - Compliance judgment (Prince function)
    - Witnessing (Knight function)
    """

    @abstractmethod
    async def own_domain(
        self,
        request: DomainOwnershipRequest,
    ) -> DomainOwnershipResult:
        """Take ownership of an execution domain.

        Per FR-GOV-11: Dukes own execution domains.

        Args:
            request: Domain ownership request

        Returns:
            DomainOwnershipResult with owned domain or error

        Raises:
            RankViolationError: If the Archon is not Duke-rank
        """
        ...

    @abstractmethod
    async def allocate_resources(
        self,
        request: ResourceAllocationRequest,
    ) -> ResourceAllocationResult:
        """Allocate resources to a task within the domain.

        Per FR-GOV-11: Dukes allocate resources.

        Args:
            request: Resource allocation request

        Returns:
            ResourceAllocationResult with allocation or error

        Note:
            Resources can only be allocated within domains owned by the Duke.
        """
        ...

    @abstractmethod
    async def track_progress(
        self,
        task_id: UUID,
        duke_id: str,
    ) -> ProgressTrackingResult:
        """Track progress of task execution.

        Per FR-GOV-11: Dukes track progress.

        Args:
            task_id: Task to track
            duke_id: Duke Archon ID

        Returns:
            ProgressTrackingResult with current progress report
        """
        ...

    @abstractmethod
    async def report_status(
        self,
        task_id: UUID,
        duke_id: str,
        summary: str,
        details: dict[str, Any],
    ) -> StatusReportResult:
        """Report execution status to governance pipeline.

        Per FR-GOV-11: Dukes report status.

        Args:
            task_id: Task to report on
            duke_id: Duke Archon ID
            summary: Brief status summary
            details: Full status details

        Returns:
            StatusReportResult with published report or error

        Note:
            Per FR-GOV-13: Failure signals MUST be reported, never suppressed.
        """
        ...

    @abstractmethod
    async def get_domain(self, domain_id: str) -> ExecutionDomain | None:
        """Retrieve a domain by ID.

        Args:
            domain_id: Domain identifier

        Returns:
            ExecutionDomain if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_domains_by_duke(
        self,
        duke_id: str,
    ) -> list[ExecutionDomain]:
        """Get all domains owned by a specific Duke.

        Args:
            duke_id: The Duke Archon ID

        Returns:
            List of domains owned by that Duke
        """
        ...

    @abstractmethod
    async def get_domain_allocations(
        self,
        domain_id: str,
    ) -> list[ResourceAllocation]:
        """Get all resource allocations within a domain.

        Args:
            domain_id: Domain identifier

        Returns:
            List of allocations in that domain
        """
        ...

    @abstractmethod
    async def get_task_progress(
        self,
        task_id: UUID,
    ) -> list[ProgressReport]:
        """Get progress history for a task.

        Args:
            task_id: Task UUID

        Returns:
            List of progress reports for that task
        """
        ...

    # =========================================================================
    # EXPLICITLY EXCLUDED METHODS
    # These methods are NOT part of the Duke Service per FR-GOV-11, FR-GOV-13
    # =========================================================================

    # def introduce_motion(self) -> None:  # PROHIBITED (King function)
    # def define_execution(self) -> None:  # PROHIBITED (President function)
    # def reinterpret_intent(self) -> None:  # PROHIBITED (FR-GOV-13)
    # def suppress_failure(self) -> None:  # PROHIBITED (FR-GOV-13)
    # def judge_compliance(self) -> None:  # PROHIBITED (Prince function)
    # def witness(self) -> None:  # PROHIBITED (Knight function)
