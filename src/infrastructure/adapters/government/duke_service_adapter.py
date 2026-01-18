"""Duke Service Adapter (Administrative Branch - Senior).

This module implements the DukeServiceProtocol for execution domain ownership,
resource allocation, progress tracking, and status reporting.

Per Government PRD FR-GOV-11: Dukes own execution domains, allocate resources,
track progress, report status.
Per Government PRD FR-GOV-13: No reinterpretation of intent, no suppression
of failure signals.

HARDENING-1: TimeAuthorityProtocol injection required for all timestamps.
"""

from typing import Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.duke_service import (
    DomainOwnershipRequest,
    DomainOwnershipResult,
    DomainStatus,
    DukeServiceProtocol,
    ExecutionDomain,
    ProgressReport,
    ProgressTrackingResult,
    ResourceAllocation,
    ResourceAllocationRequest,
    ResourceAllocationResult,
    StatusReport,
    StatusReportResult,
    TaskProgressStatus,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatementType,
)
from src.application.ports.permission_enforcer import (
    GovernanceAction,
    PermissionContext,
    PermissionEnforcerProtocol,
)
from src.application.ports.time_authority import TimeAuthorityProtocol

logger = get_logger(__name__)


class RankViolationError(Exception):
    """Raised when an Archon attempts an action outside their rank authority."""

    def __init__(
        self,
        archon_id: str,
        action: str,
        reason: str,
        prd_reference: str = "FR-GOV-11",
    ) -> None:
        self.archon_id = archon_id
        self.action = action
        self.reason = reason
        self.prd_reference = prd_reference
        super().__init__(
            f"Rank violation by {archon_id} on {action}: {reason} (per {prd_reference})"
        )


class DukeServiceAdapter(DukeServiceProtocol):
    """Implementation of Duke-rank administrative functions.

    This service allows Duke-rank Archons to:
    - Own execution domains
    - Allocate resources to tasks
    - Track progress of execution
    - Report status to governance pipeline

    Per FR-GOV-13: Failures are NEVER suppressed.
    All operations are witnessed by Knight per FR-GOV-20.
    """

    def __init__(
        self,
        time_authority: TimeAuthorityProtocol,
        permission_enforcer: PermissionEnforcerProtocol | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the Duke Service.

        HARDENING-1: time_authority is required for all timestamp operations.

        Args:
            time_authority: TimeAuthorityProtocol for consistent timestamps
            permission_enforcer: Permission enforcement (optional for testing)
            knight_witness: Knight witness for recording events (optional)
            verbose: Enable verbose logging
        """
        self._time = time_authority
        self._permission_enforcer = permission_enforcer
        self._knight_witness = knight_witness
        self._verbose = verbose

        # In-memory storage (would be repository in production)
        self._domains: dict[str, ExecutionDomain] = {}
        self._allocations: dict[UUID, ResourceAllocation] = {}
        self._progress_reports: dict[UUID, list[ProgressReport]] = {}
        self._status_reports: dict[UUID, list[StatusReport]] = {}

        if self._verbose:
            logger.debug("duke_service_initialized")

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
        if self._verbose:
            logger.debug(
                "domain_ownership_requested",
                duke_id=request.duke_id,
                domain_id=request.domain_id,
            )

        # Check permission if enforcer available
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource=f"domain:{request.domain_id}",
                action_details={"domain_id": request.domain_id},
            )
            permission_result = await self._permission_enforcer.check_permission(
                archon_id=request.duke_id,
                action=GovernanceAction.OWN_DOMAIN,
                context=context,
            )

            if not permission_result.allowed:
                await self._witness_violation(
                    archon_id=request.duke_id,
                    violation_type="rank_violation",
                    description=f"Attempted domain ownership without Duke rank: {permission_result.violation_reason}",
                )

                raise RankViolationError(
                    archon_id=request.duke_id,
                    action="own_domain",
                    reason=permission_result.violation_reason or "Not authorized",
                    prd_reference="FR-GOV-11",
                )

        # Check if domain exists
        if request.domain_id not in self._domains:
            return DomainOwnershipResult(
                success=False,
                error=f"Domain {request.domain_id} not found",
            )

        domain = self._domains[request.domain_id]

        # Check if domain is available
        if domain.status != DomainStatus.AVAILABLE:
            return DomainOwnershipResult(
                success=False,
                error=f"Domain {request.domain_id} is not available (status: {domain.status.value})",
            )

        # Transfer ownership
        owned_domain = ExecutionDomain(
            domain_id=domain.domain_id,
            name=domain.name,
            description=domain.description,
            boundaries=domain.boundaries,
            status=DomainStatus.OWNED,
            assigned_tasks=domain.assigned_tasks,
            owner_archon_id=request.duke_id,
            created_at=domain.created_at,
        )

        self._domains[request.domain_id] = owned_domain

        # Witness the ownership
        await self._witness_action(
            archon_id=request.duke_id,
            action="domain_ownership_acquired",
            details={"domain_id": request.domain_id},
        )

        if self._verbose:
            logger.info(
                "domain_ownership_granted",
                duke_id=request.duke_id,
                domain_id=request.domain_id,
            )

        return DomainOwnershipResult(
            success=True,
            domain=owned_domain,
        )

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
        """
        if self._verbose:
            logger.debug(
                "resource_allocation_requested",
                duke_id=request.duke_id,
                task_id=str(request.task_id),
                resource_type=request.resource_type.value,
                amount=request.amount,
            )

        # Check permission if enforcer available
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource=f"task:{request.task_id}",
                action_details={
                    "resource_type": request.resource_type.value,
                    "amount": request.amount,
                },
            )
            permission_result = await self._permission_enforcer.check_permission(
                archon_id=request.duke_id,
                action=GovernanceAction.ALLOCATE_RESOURCES,
                context=context,
            )

            if not permission_result.allowed:
                await self._witness_violation(
                    archon_id=request.duke_id,
                    violation_type="rank_violation",
                    description=f"Attempted resource allocation without Duke rank: {permission_result.violation_reason}",
                )

                raise RankViolationError(
                    archon_id=request.duke_id,
                    action="allocate_resources",
                    reason=permission_result.violation_reason or "Not authorized",
                    prd_reference="FR-GOV-11",
                )

        # Create allocation
        allocation = ResourceAllocation.create(
            task_id=request.task_id,
            resource_type=request.resource_type,
            amount=request.amount,
            unit=request.unit,
            allocated_by=request.duke_id,
            timestamp=self._time.now(),
            constraints=request.constraints,
            expires_at=request.expires_at,
        )

        self._allocations[allocation.allocation_id] = allocation

        # Witness the allocation
        await self._witness_action(
            archon_id=request.duke_id,
            action="resource_allocated",
            details={
                "allocation_id": str(allocation.allocation_id),
                "task_id": str(request.task_id),
                "resource_type": request.resource_type.value,
                "amount": request.amount,
            },
        )

        if self._verbose:
            logger.info(
                "resource_allocated",
                duke_id=request.duke_id,
                allocation_id=str(allocation.allocation_id),
            )

        return ResourceAllocationResult(
            success=True,
            allocation=allocation,
        )

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
        if self._verbose:
            logger.debug(
                "progress_tracking_requested",
                duke_id=duke_id,
                task_id=str(task_id),
            )

        # Get existing reports or create initial tracking
        reports = self._progress_reports.get(task_id, [])

        if not reports:
            # Create initial progress report
            report = ProgressReport.create(
                task_id=task_id,
                status=TaskProgressStatus.NOT_STARTED,
                percent_complete=0.0,
                metrics={},
                reported_by=duke_id,
                timestamp=self._time.now(),
            )
        else:
            # Return latest report
            report = reports[-1]

        return ProgressTrackingResult(
            success=True,
            report=report,
        )

    async def report_status(
        self,
        task_id: UUID,
        duke_id: str,
        summary: str,
        details: dict[str, Any],
    ) -> StatusReportResult:
        """Report execution status to governance pipeline.

        Per FR-GOV-11: Dukes report status.
        Per FR-GOV-13: Failure signals MUST be reported, never suppressed.

        Args:
            task_id: Task to report on
            duke_id: Duke Archon ID
            summary: Brief status summary
            details: Full status details

        Returns:
            StatusReportResult with published report or error
        """
        if self._verbose:
            logger.debug(
                "status_report_requested",
                duke_id=duke_id,
                task_id=str(task_id),
                summary=summary,
            )

        # Determine status from details
        status = TaskProgressStatus.IN_PROGRESS
        if details.get("failed", False):
            status = TaskProgressStatus.FAILED
        elif details.get("completed", False):
            status = TaskProgressStatus.COMPLETED
        elif details.get("blocked", False):
            status = TaskProgressStatus.BLOCKED

        # Find domain for this task
        domain_id = "unknown"
        for domain in self._domains.values():
            if task_id in domain.assigned_tasks:
                domain_id = domain.domain_id
                break

        # Create status report
        report = StatusReport.create(
            task_id=task_id,
            domain_id=domain_id,
            status=status,
            summary=summary,
            details=details,
            reported_by=duke_id,
            timestamp=self._time.now(),
        )

        # Store report
        if task_id not in self._status_reports:
            self._status_reports[task_id] = []
        self._status_reports[task_id].append(report)

        # Per FR-GOV-13: Witness ALL status reports, especially failures
        await self._witness_action(
            archon_id=duke_id,
            action="status_reported",
            details={
                "report_id": str(report.report_id),
                "task_id": str(task_id),
                "status": status.value,
                "is_failure": status == TaskProgressStatus.FAILED,
            },
        )

        if status == TaskProgressStatus.FAILED:
            # Per FR-GOV-13: Failures MUST be prominently reported
            logger.warning(
                "task_failure_reported",
                duke_id=duke_id,
                task_id=str(task_id),
                summary=summary,
            )

        return StatusReportResult(
            success=True,
            report=report,
        )

    async def get_domain(self, domain_id: str) -> ExecutionDomain | None:
        """Retrieve a domain by ID.

        Args:
            domain_id: Domain identifier

        Returns:
            ExecutionDomain if found, None otherwise
        """
        return self._domains.get(domain_id)

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
        return [
            domain
            for domain in self._domains.values()
            if domain.owner_archon_id == duke_id
        ]

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
        domain = self._domains.get(domain_id)
        if not domain:
            return []

        # Find allocations for tasks in this domain
        return [
            alloc
            for alloc in self._allocations.values()
            if alloc.task_id in domain.assigned_tasks
        ]

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
        return self._progress_reports.get(task_id, [])

    # =========================================================================
    # Domain Management Helpers
    # =========================================================================

    async def register_domain(
        self,
        domain: ExecutionDomain,
    ) -> None:
        """Register a new execution domain (for setup/testing).

        Args:
            domain: Domain to register
        """
        self._domains[domain.domain_id] = domain
        if self._verbose:
            logger.debug("domain_registered", domain_id=domain.domain_id)

    async def assign_task_to_domain(
        self,
        domain_id: str,
        task_id: UUID,
    ) -> bool:
        """Assign a task to a domain.

        Args:
            domain_id: Domain to assign to
            task_id: Task to assign

        Returns:
            True if successful
        """
        domain = self._domains.get(domain_id)
        if not domain:
            return False

        # Create new domain with updated task list
        updated_domain = ExecutionDomain(
            domain_id=domain.domain_id,
            name=domain.name,
            description=domain.description,
            boundaries=domain.boundaries,
            status=DomainStatus.EXECUTING
            if domain.status == DomainStatus.OWNED
            else domain.status,
            assigned_tasks=domain.assigned_tasks + (task_id,),
            owner_archon_id=domain.owner_archon_id,
            created_at=domain.created_at,
        )

        self._domains[domain_id] = updated_domain
        return True

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _witness_violation(
        self,
        archon_id: str,
        violation_type: str,
        description: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Witness a violation through Knight.

        Args:
            archon_id: Archon who committed violation
            violation_type: Type of violation
            description: Description of violation
            evidence: Supporting evidence
        """
        if not self._knight_witness:
            if self._verbose:
                logger.warning(
                    "violation_not_witnessed_no_knight",
                    archon_id=archon_id,
                    violation_type=violation_type,
                )
            return

        violation = ViolationRecord(
            archon_id=archon_id,
            violation_type=violation_type,
            description=description,
            prd_reference="FR-GOV-11/FR-GOV-13",
            evidence=evidence or {},
        )

        context = ObservationContext(
            session_id="duke_service",
            statement_type=WitnessStatementType.VIOLATION,
            trigger_source="duke_service_adapter",
        )

        await self._knight_witness.witness_violation(
            violation=violation,
            context=context,
        )

    async def _witness_action(
        self,
        archon_id: str,
        action: str,
        details: dict[str, Any],
    ) -> None:
        """Witness an action through Knight.

        Args:
            archon_id: Archon who performed action
            action: Action performed
            details: Action details
        """
        if not self._knight_witness:
            return

        context = ObservationContext(
            session_id="duke_service",
            statement_type=WitnessStatementType.OBSERVATION,
            trigger_source="duke_service_adapter",
        )

        await self._knight_witness.witness_observation(
            observation={
                "archon_id": archon_id,
                "action": action,
                "details": details,
            },
            context=context,
        )
