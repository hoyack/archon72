"""Compliance repository port for regulatory compliance persistence (Story 9.9, NFR31-34).

This module defines the interface for storing and retrieving compliance assessments.
Assessments document regulatory framework compliance status and gaps.

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available
- CT-12: Witnessing creates accountability -> Compliance changes witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before repository operations
2. WITNESS EVERYTHING - Compliance changes create witnessed events
3. FAIL LOUD - Never silently swallow repository errors
"""

from __future__ import annotations

from typing import Optional, Protocol

from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
)


class ComplianceRepositoryProtocol(Protocol):
    """Repository protocol for compliance assessments (NFR31-34).

    This protocol defines operations for persisting and retrieving compliance
    assessments. Implementations should ensure transactional integrity and
    thread safety.

    Constitutional Constraints:
    - NFR31-34: Regulatory compliance documentation requirements
    - CT-12: Witnessing creates accountability
    """

    async def get_assessment(
        self, assessment_id: str
    ) -> Optional[ComplianceAssessment]:
        """Retrieve an assessment by its ID.

        Args:
            assessment_id: Unique assessment identifier.

        Returns:
            ComplianceAssessment if found, None otherwise.
        """
        ...

    async def get_assessments_by_framework(
        self, framework: ComplianceFramework
    ) -> tuple[ComplianceAssessment, ...]:
        """Retrieve all assessments for a specific framework.

        Args:
            framework: The compliance framework to filter by.

        Returns:
            Tuple of ComplianceAssessments for the framework (empty if none).
        """
        ...

    async def get_latest_assessment(
        self, framework: ComplianceFramework
    ) -> Optional[ComplianceAssessment]:
        """Retrieve the most recent assessment for a framework.

        Args:
            framework: The compliance framework.

        Returns:
            Most recent ComplianceAssessment if exists, None otherwise.
        """
        ...

    async def get_all_latest_assessments(self) -> tuple[ComplianceAssessment, ...]:
        """Retrieve the latest assessment for each framework.

        Returns:
            Tuple of the most recent ComplianceAssessment for each framework
            that has been assessed (empty if no assessments exist).
        """
        ...

    async def get_requirements_by_status(
        self, status: ComplianceStatus
    ) -> tuple[ComplianceRequirement, ...]:
        """Retrieve all requirements with a specific status.

        This is useful for finding all GAP_IDENTIFIED requirements
        across all frameworks.

        Args:
            status: The compliance status to filter by.

        Returns:
            Tuple of ComplianceRequirements with the specified status.
        """
        ...

    async def save_assessment(self, assessment: ComplianceAssessment) -> None:
        """Save a compliance assessment.

        If an assessment with the same ID exists, it will be updated.
        Otherwise, a new assessment will be created.

        Args:
            assessment: The assessment to save.

        Raises:
            RepositoryError: If the save operation fails.
        """
        ...

    async def exists(self, assessment_id: str) -> bool:
        """Check if an assessment exists.

        Args:
            assessment_id: Unique assessment identifier.

        Returns:
            True if the assessment exists, False otherwise.
        """
        ...
