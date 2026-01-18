"""Compliance repository stub for testing (Story 9.9, NFR31-34).

This module provides an in-memory stub implementation of ComplianceRepositoryProtocol
for unit and integration testing.

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available
"""

from __future__ import annotations

from src.application.ports.compliance_repository import ComplianceRepositoryProtocol
from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
)


class ComplianceRepositoryStub(ComplianceRepositoryProtocol):
    """In-memory stub for ComplianceRepositoryProtocol (Story 9.9, NFR31-34).

    This stub provides an in-memory implementation for testing.
    It supports all standard repository operations and test isolation via clear().

    Example:
        stub = ComplianceRepositoryStub()
        await stub.save_assessment(assessment)
        retrieved = await stub.get_assessment(assessment.assessment_id)
        stub.clear()  # Reset for next test
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._assessments: dict[str, ComplianceAssessment] = {}

    async def get_assessment(self, assessment_id: str) -> ComplianceAssessment | None:
        """Retrieve an assessment by its ID.

        Args:
            assessment_id: Unique assessment identifier.

        Returns:
            ComplianceAssessment if found, None otherwise.
        """
        return self._assessments.get(assessment_id)

    async def get_assessments_by_framework(
        self, framework: ComplianceFramework
    ) -> tuple[ComplianceAssessment, ...]:
        """Retrieve all assessments for a specific framework.

        Args:
            framework: The compliance framework to filter by.

        Returns:
            Tuple of ComplianceAssessments for the framework (empty if none).
        """
        return tuple(
            assessment
            for assessment in self._assessments.values()
            if assessment.framework == framework
        )

    async def get_latest_assessment(
        self, framework: ComplianceFramework
    ) -> ComplianceAssessment | None:
        """Retrieve the most recent assessment for a framework.

        Args:
            framework: The compliance framework.

        Returns:
            Most recent ComplianceAssessment if exists, None otherwise.
        """
        assessments = [
            a for a in self._assessments.values() if a.framework == framework
        ]
        if not assessments:
            return None
        return max(assessments, key=lambda a: a.assessment_date)

    async def get_all_latest_assessments(self) -> tuple[ComplianceAssessment, ...]:
        """Retrieve the latest assessment for each framework.

        Returns:
            Tuple of the most recent ComplianceAssessment for each framework
            that has been assessed (empty if no assessments exist).
        """
        latest: dict[ComplianceFramework, ComplianceAssessment] = {}
        for assessment in self._assessments.values():
            if (
                assessment.framework not in latest
                or assessment.assessment_date
                > latest[assessment.framework].assessment_date
            ):
                latest[assessment.framework] = assessment
        return tuple(latest.values())

    async def get_requirements_by_status(
        self, status: ComplianceStatus
    ) -> tuple[ComplianceRequirement, ...]:
        """Retrieve all requirements with a specific status.

        Args:
            status: The compliance status to filter by.

        Returns:
            Tuple of ComplianceRequirements with the specified status.
        """
        result: list[ComplianceRequirement] = []
        for assessment in self._assessments.values():
            for requirement in assessment.requirements:
                if requirement.status == status:
                    result.append(requirement)
        return tuple(result)

    async def save_assessment(self, assessment: ComplianceAssessment) -> None:
        """Save a compliance assessment.

        If an assessment with the same ID exists, it will be updated.
        Otherwise, a new assessment will be created.

        Args:
            assessment: The assessment to save.
        """
        self._assessments[assessment.assessment_id] = assessment

    async def exists(self, assessment_id: str) -> bool:
        """Check if an assessment exists.

        Args:
            assessment_id: Unique assessment identifier.

        Returns:
            True if the assessment exists, False otherwise.
        """
        return assessment_id in self._assessments

    def clear(self) -> None:
        """Clear all assessments for test isolation."""
        self._assessments.clear()

    def get_assessment_count(self) -> int:
        """Get the number of stored assessments (for testing).

        Returns:
            Number of assessments currently stored.
        """
        return len(self._assessments)
