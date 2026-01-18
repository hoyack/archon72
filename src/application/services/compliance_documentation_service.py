"""Compliance documentation service for regulatory compliance (Story 9.9, NFR31-34).

This service coordinates compliance documentation, persistence, and event creation.
All compliance operations create witnessed constitutional events.

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All compliance events witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Compliance documentation creates witnessed events
3. FAIL LOUD - Never silently swallow compliance errors
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.ports.compliance_repository import ComplianceRepositoryProtocol
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors import SystemHaltedError
from src.domain.events.compliance import (
    COMPLIANCE_DOCUMENTED_EVENT_TYPE,
    COMPLIANCE_SYSTEM_AGENT_ID,
    ComplianceDocumentedEventPayload,
)
from src.domain.events.compliance import (
    ComplianceFramework as EventComplianceFramework,
)
from src.domain.events.compliance import (
    ComplianceStatus as EventComplianceStatus,
)
from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
    generate_assessment_id,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService


# System agent ID for compliance documentation service
COMPLIANCE_DOCUMENTATION_SYSTEM_AGENT_ID: str = COMPLIANCE_SYSTEM_AGENT_ID


class ComplianceDocumentationService:
    """Service for documenting regulatory compliance (Story 9.9, NFR31-34).

    This service provides operations for creating, retrieving, and managing
    compliance assessments. All operations are witnessed via the EventWriterService.

    Constitutional Constraints:
    - NFR31-34: Regulatory compliance documentation requirements
    - CT-11: HALT CHECK FIRST on every operation
    - CT-12: All compliance events must be witnessed

    Example:
        service = ComplianceDocumentationService(
            compliance_repository=repo,
            event_writer=writer,
            halt_checker=halt_checker,
        )

        assessment = await service.document_assessment(
            framework=ComplianceFramework.EU_AI_ACT,
            requirements=[req1, req2],
            gaps=["Some gap identified"],
            remediation_plan="Address in Phase 2",
        )
    """

    def __init__(
        self,
        compliance_repository: ComplianceRepositoryProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the compliance documentation service.

        Args:
            compliance_repository: Repository for compliance persistence.
            event_writer: Service for creating witnessed events.
            halt_checker: Interface for checking halt state.
        """
        self._repository = compliance_repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def document_assessment(
        self,
        framework: ComplianceFramework,
        requirements: list[ComplianceRequirement],
        gaps: list[str],
        remediation_plan: str | None = None,
        framework_version: str = "1.0",
        documented_by: str = COMPLIANCE_DOCUMENTATION_SYSTEM_AGENT_ID,
    ) -> ComplianceAssessment:
        """Document a compliance assessment (NFR31-34).

        Creates a new assessment record and writes a witnessed event.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST
        - CT-12: Compliance documentation creates witnessed event

        Args:
            framework: Compliance framework being assessed.
            requirements: List of individual requirements with status.
            gaps: List of identified gaps.
            remediation_plan: Plan for addressing gaps (optional).
            framework_version: Version of the framework standard.
            documented_by: Agent/system documenting the compliance.

        Returns:
            ComplianceAssessment for the documented assessment.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot document compliance")

        # Create assessment
        assessment_date = datetime.now(timezone.utc)
        assessment_id = generate_assessment_id(framework)
        assessment = ComplianceAssessment(
            assessment_id=assessment_id,
            framework=framework,
            assessment_date=assessment_date,
            requirements=tuple(requirements),
            gaps=tuple(gaps),
            remediation_plan=remediation_plan,
        )

        # Save to repository
        await self._repository.save_assessment(assessment)

        # Map model enums to event enums
        event_framework = EventComplianceFramework(framework.value)
        event_status = EventComplianceStatus(assessment.overall_status.value)

        # Create witnessed event (CT-12)
        event_payload = ComplianceDocumentedEventPayload(
            compliance_id=assessment_id,
            framework=event_framework,
            framework_version=framework_version,
            assessment_date=assessment_date,
            status=event_status,
            findings=tuple(
                f"{r.requirement_id}: {r.status.value}" for r in requirements
            ),
            remediation_plan=remediation_plan,
            next_review_date=None,
            documented_by=documented_by,
        )

        await self._event_writer.write_event(
            event_type=COMPLIANCE_DOCUMENTED_EVENT_TYPE,
            payload=event_payload.to_dict(),
            agent_id=documented_by,
        )

        return assessment

    async def get_compliance_posture(
        self,
    ) -> dict[ComplianceFramework, ComplianceStatus]:
        """Get current compliance posture across all frameworks.

        Returns the latest status for each framework that has been assessed.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Returns:
            Dict mapping framework to its latest compliance status.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot get compliance posture")

        assessments = await self._repository.get_all_latest_assessments()
        return {a.framework: a.overall_status for a in assessments}

    async def get_gaps(self) -> tuple[ComplianceRequirement, ...]:
        """Get all requirements with GAP_IDENTIFIED status.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Returns:
            Tuple of requirements with gaps identified.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot get compliance gaps")

        return await self._repository.get_requirements_by_status(
            ComplianceStatus.GAP_IDENTIFIED
        )

    async def get_framework_assessment(
        self, framework: ComplianceFramework
    ) -> ComplianceAssessment | None:
        """Get the latest assessment for a specific framework.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Args:
            framework: The compliance framework.

        Returns:
            Latest ComplianceAssessment for the framework, or None if none exist.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot get framework assessment")

        return await self._repository.get_latest_assessment(framework)

    async def get_all_assessments(self) -> tuple[ComplianceAssessment, ...]:
        """Get the latest assessment for all frameworks.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Returns:
            Tuple of latest ComplianceAssessments for each framework.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot get all assessments")

        return await self._repository.get_all_latest_assessments()

    async def assessment_exists(self, assessment_id: str) -> bool:
        """Check if an assessment exists.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Args:
            assessment_id: Unique assessment identifier.

        Returns:
            True if the assessment exists, False otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot check assessment existence")

        return await self._repository.exists(assessment_id)
