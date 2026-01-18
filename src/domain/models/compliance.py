"""Compliance domain models (Story 9.9, NFR31-34).

This module defines domain models for regulatory compliance documentation:
- ComplianceFramework: Regulatory frameworks (EU AI Act, NIST AI RMF, IEEE 7001, GDPR, MAESTRO)
- ComplianceStatus: Assessment status (COMPLIANT, PARTIAL, GAP_IDENTIFIED, NOT_APPLICABLE)
- ComplianceRequirement: Individual requirement with status and evidence
- ComplianceAssessment: Framework-level assessment aggregating requirements
- FrameworkMapping: Cross-framework alignment mapping

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before compliance operations
2. EVIDENCE REQUIRED - All requirements must have implementation references
3. FAIL LOUD - Never silently swallow compliance operations
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ComplianceFramework(Enum):
    """Regulatory compliance frameworks (NFR31-34).

    Each framework represents a regulatory or standards body
    whose requirements must be documented and tracked.
    """

    EU_AI_ACT = "EU_AI_ACT"
    """European Union AI Act (2024/1689)."""

    NIST_AI_RMF = "NIST_AI_RMF"
    """NIST AI Risk Management Framework."""

    IEEE_7001 = "IEEE_7001"
    """IEEE 7001 Transparency Standard."""

    GDPR = "GDPR"
    """General Data Protection Regulation."""

    MAESTRO = "MAESTRO"
    """CSA MAESTRO Framework for Agentic AI."""


class ComplianceStatus(Enum):
    """Status of compliance assessment (NFR31-34).

    Each status represents the compliance posture for a framework.
    """

    COMPLIANT = "COMPLIANT"
    """Full compliance with all requirements."""

    PARTIAL = "PARTIAL"
    """Partial compliance - some requirements met."""

    GAP_IDENTIFIED = "GAP_IDENTIFIED"
    """Gaps identified that require remediation."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    """Framework requirements do not apply."""


@dataclass(frozen=True, eq=True)
class ComplianceRequirement:
    """Individual compliance requirement (NFR31-34).

    Each requirement tracks a specific regulatory mandate with
    implementation status and evidence.

    Attributes:
        requirement_id: NFR ID (e.g., "NFR31").
        framework: Compliance framework this belongs to.
        description: Full description of the requirement.
        status: Current compliance status.
        implementation_reference: Where implemented in codebase (optional).
        evidence: List of evidence supporting compliance status.
    """

    requirement_id: str
    framework: ComplianceFramework
    description: str
    status: ComplianceStatus
    implementation_reference: str | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate requirement fields."""
        if not self.requirement_id:
            raise ValueError("requirement_id is required")
        if not self.description:
            raise ValueError("description is required")

    def to_dict(self) -> dict[str, Any]:
        """Convert requirement to dictionary for serialization.

        Returns:
            Dictionary representation of the requirement.
        """
        return {
            "requirement_id": self.requirement_id,
            "framework": self.framework.value,
            "description": self.description,
            "status": self.status.value,
            "implementation_reference": self.implementation_reference,
            "evidence": list(self.evidence),
        }


def _compute_overall_status(
    requirements: tuple[ComplianceRequirement, ...],
) -> ComplianceStatus:
    """Compute overall status from requirements.

    The overall status is computed as follows:
    - If all requirements are COMPLIANT or NOT_APPLICABLE -> COMPLIANT
    - If any requirement is GAP_IDENTIFIED -> GAP_IDENTIFIED
    - Otherwise -> PARTIAL

    Args:
        requirements: Tuple of compliance requirements.

    Returns:
        Computed overall compliance status.
    """
    if not requirements:
        return ComplianceStatus.NOT_APPLICABLE

    has_gaps = any(r.status == ComplianceStatus.GAP_IDENTIFIED for r in requirements)
    if has_gaps:
        return ComplianceStatus.GAP_IDENTIFIED

    all_compliant_or_na = all(
        r.status in (ComplianceStatus.COMPLIANT, ComplianceStatus.NOT_APPLICABLE)
        for r in requirements
    )
    if all_compliant_or_na:
        return ComplianceStatus.COMPLIANT

    return ComplianceStatus.PARTIAL


@dataclass(frozen=True, eq=True)
class ComplianceAssessment:
    """Framework-level compliance assessment (NFR31-34).

    An assessment aggregates all requirements for a specific
    framework and computes overall compliance status.

    Attributes:
        assessment_id: Unique assessment identifier.
        framework: Framework being assessed.
        assessment_date: When assessment was performed (UTC).
        requirements: Individual requirements with status.
        overall_status: Computed overall compliance status.
        gaps: List of identified gaps requiring remediation.
        remediation_plan: Plan for addressing gaps (optional).
    """

    assessment_id: str
    framework: ComplianceFramework
    assessment_date: datetime
    requirements: tuple[ComplianceRequirement, ...]
    gaps: tuple[str, ...] = field(default_factory=tuple)
    remediation_plan: str | None = None

    @property
    def overall_status(self) -> ComplianceStatus:
        """Compute overall status from requirements.

        Returns:
            Computed overall compliance status.
        """
        return _compute_overall_status(self.requirements)

    def __post_init__(self) -> None:
        """Validate assessment fields."""
        if not self.assessment_id:
            raise ValueError("assessment_id is required")

    def to_dict(self) -> dict[str, Any]:
        """Convert assessment to dictionary for serialization.

        Returns:
            Dictionary representation of the assessment.
        """
        return {
            "assessment_id": self.assessment_id,
            "framework": self.framework.value,
            "assessment_date": self.assessment_date.isoformat(),
            "requirements": [r.to_dict() for r in self.requirements],
            "overall_status": self.overall_status.value,
            "gaps": list(self.gaps),
            "remediation_plan": self.remediation_plan,
        }


@dataclass(frozen=True, eq=True)
class FrameworkMapping:
    """Cross-framework alignment mapping (NFR31-34).

    Maps implementation capabilities to multiple frameworks,
    showing how a single implementation satisfies requirements
    across different regulatory regimes.

    Attributes:
        mapping_id: Unique mapping identifier.
        capability: Implementation capability being mapped.
        framework_requirements: Dict of framework -> requirement IDs satisfied.
        implementation_reference: Where implemented in codebase.
    """

    mapping_id: str
    capability: str
    framework_requirements: dict[ComplianceFramework, tuple[str, ...]]
    implementation_reference: str

    def __post_init__(self) -> None:
        """Validate mapping fields."""
        if not self.mapping_id:
            raise ValueError("mapping_id is required")
        if not self.capability:
            raise ValueError("capability is required")
        if not self.implementation_reference:
            raise ValueError("implementation_reference is required")

    def to_dict(self) -> dict[str, Any]:
        """Convert mapping to dictionary for serialization.

        Returns:
            Dictionary representation of the mapping.
        """
        return {
            "mapping_id": self.mapping_id,
            "capability": self.capability,
            "framework_requirements": {
                k.value: list(v) for k, v in self.framework_requirements.items()
            },
            "implementation_reference": self.implementation_reference,
        }


def generate_assessment_id(framework: ComplianceFramework) -> str:
    """Generate a unique assessment ID.

    Args:
        framework: The compliance framework being assessed.

    Returns:
        Unique assessment ID with framework prefix.
    """
    short_uuid = str(uuid.uuid4())[:8]
    return f"{framework.value}-ASSESSMENT-{short_uuid}"
