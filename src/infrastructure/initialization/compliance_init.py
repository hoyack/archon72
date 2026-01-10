"""Compliance documentation initialization for NFR31-34 (Story 9.9).

This module provides constants and initialization logic for documenting
regulatory compliance across EU AI Act, NIST AI RMF, IEEE 7001, GDPR,
and MAESTRO frameworks.

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available
- CT-12: Witnessing creates accountability -> Compliance events witnessed

References:
- _bmad-output/planning-artifacts/epics.md#Story-9.9
- _bmad-output/planning-artifacts/research-integration-addendum.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
)

if TYPE_CHECKING:
    from src.application.services.compliance_documentation_service import (
        ComplianceDocumentationService,
    )


# ==============================================================================
# NFR31-34 Requirements
# ==============================================================================

NFR31_REQUIREMENT = ComplianceRequirement(
    requirement_id="NFR31",
    framework=ComplianceFramework.GDPR,
    description="Personal data SHALL be stored separately from constitutional events",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/infrastructure/adapters/persistence/ - patronage_private schema isolation",
    evidence=(
        "patronage_private schema isolation",
        "No PII in events table",
        "Separate database connection for private data",
    ),
)

NFR32_REQUIREMENT = ComplianceRequirement(
    requirement_id="NFR32",
    framework=ComplianceFramework.GDPR,
    description="Retention policy SHALL be published and immutable",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="CT-13: Integrity outranks availability - append-only event store",
    evidence=(
        "Append-only event store (CT-13)",
        "Retention policy in docs/operations/retention-policy.md",
        "Immutable hash chain prevents deletion",
    ),
)

NFR33_REQUIREMENT = ComplianceRequirement(
    requirement_id="NFR33",
    framework=ComplianceFramework.GDPR,
    description="System SHALL provide structured audit export in standard format",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/application/services/export_service.py (Story 4-7)",
    evidence=(
        "Regulatory reporting export endpoint",
        "JSON-LD structured format",
        "CSV export for auditors",
    ),
)

NFR34_REQUIREMENT = ComplianceRequirement(
    requirement_id="NFR34",
    framework=ComplianceFramework.GDPR,
    description="Third-party attestation interface SHALL be available",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/api/routes/observer.py (Epic 4)",
    evidence=(
        "Observer API public read access",
        "Raw events with hashes",
        "Verification toolkit",
    ),
)

# ==============================================================================
# EU AI Act Requirements
# ==============================================================================

EU_AI_ACT_HUMAN_OVERSIGHT = ComplianceRequirement(
    requirement_id="EU-AI-ACT-01",
    framework=ComplianceFramework.EU_AI_ACT,
    description="Human oversight for high-risk AI systems (Article 14)",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/application/services/override_service.py (Epic 5)",
    evidence=(
        "Human Override Protocol (Human-in-Command model)",
        "Keeper attribution with scope and duration",
        "Public override visibility",
    ),
)

EU_AI_ACT_TRANSPARENCY = ComplianceRequirement(
    requirement_id="EU-AI-ACT-02",
    framework=ComplianceFramework.EU_AI_ACT,
    description="Transparency obligations for AI systems (Article 52)",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/api/routes/observer.py (Epic 4)",
    evidence=(
        "Observer API provides public read access",
        "Raw events with cryptographic verification",
        "Full audit trail accessible to regulators",
    ),
)

EU_AI_ACT_AUDIT_TRAIL = ComplianceRequirement(
    requirement_id="EU-AI-ACT-03",
    framework=ComplianceFramework.EU_AI_ACT,
    description="Audit trail for AI decision-making (Article 12)",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/application/services/event_writer_service.py (Epic 1)",
    evidence=(
        "Hash-chained event store",
        "Witnessed events with attribution",
        "Sequence numbers prevent gaps",
    ),
)

# ==============================================================================
# NIST AI RMF Requirements
# ==============================================================================

NIST_AI_RMF_GOVERN = ComplianceRequirement(
    requirement_id="NIST-GOVERN",
    framework=ComplianceFramework.NIST_AI_RMF,
    description="GOVERN function - Establish AI governance structure",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/application/services/keeper_*.py (Epic 5)",
    evidence=(
        "Keeper governance structure",
        "Override accountability",
        "Independence attestation",
    ),
)

NIST_AI_RMF_MAP = ComplianceRequirement(
    requirement_id="NIST-MAP",
    framework=ComplianceFramework.NIST_AI_RMF,
    description="MAP function - Identify and assess AI risks",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="_bmad-output/planning-artifacts/architecture.md",
    evidence=(
        "Constitutional Truths identify risks",
        "ADRs document risk decisions",
        "Risk thresholds in domain models",
    ),
)

NIST_AI_RMF_MEASURE = ComplianceRequirement(
    requirement_id="NIST-MEASURE",
    framework=ComplianceFramework.NIST_AI_RMF,
    description="MEASURE function - Monitor AI system performance",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/application/services/*_service.py (Epic 8)",
    evidence=(
        "Operational metrics collection",
        "Constitutional health metrics",
        "Complexity budget tracking",
    ),
)

NIST_AI_RMF_MANAGE = ComplianceRequirement(
    requirement_id="NIST-MANAGE",
    framework=ComplianceFramework.NIST_AI_RMF,
    description="MANAGE function - Implement AI risk management",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/application/services/halt_*.py (Epic 3)",
    evidence=(
        "Override mechanisms",
        "Halt protocols",
        "Fork detection",
    ),
)

# ==============================================================================
# IEEE 7001 Requirements
# ==============================================================================

IEEE_7001_TRACEABILITY = ComplianceRequirement(
    requirement_id="IEEE-7001-01",
    framework=ComplianceFramework.IEEE_7001,
    description="Decision traceability",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/domain/events/*.py (Epic 1)",
    evidence=(
        "Every decision logged with attribution",
        "Agent attribution on all events",
        "Witness attestation for accountability",
    ),
)

IEEE_7001_VERSIONING = ComplianceRequirement(
    requirement_id="IEEE-7001-02",
    framework=ComplianceFramework.IEEE_7001,
    description="Algorithm versioning",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/domain/events/hash_utils.py",
    evidence=(
        "hash_alg_version in events",
        "sig_alg_version in events",
        "Schema versioning for upgrades",
    ),
)

IEEE_7001_PUBLIC_VERIFICATION = ComplianceRequirement(
    requirement_id="IEEE-7001-03",
    framework=ComplianceFramework.IEEE_7001,
    description="Public verification interface",
    status=ComplianceStatus.COMPLIANT,
    implementation_reference="src/api/routes/observer.py (Epic 4, Story 4-4)",
    evidence=(
        "Observer API",
        "Open-source verification toolkit",
        "Merkle paths for light verification",
    ),
)

# ==============================================================================
# Framework Versions
# ==============================================================================

GDPR_VERSION = "2016/679"
EU_AI_ACT_VERSION = "2024/1689"
NIST_AI_RMF_VERSION = "1.0"
IEEE_7001_VERSION = "2021"


# ==============================================================================
# Initialization Functions
# ==============================================================================


async def initialize_gdpr_compliance(
    service: ComplianceDocumentationService,
) -> ComplianceAssessment:
    """Initialize GDPR (NFR31-34) compliance documentation.

    This function is idempotent - if the assessment already exists,
    it creates a new version with updated assessment date.

    Args:
        service: ComplianceDocumentationService for documenting compliance.

    Returns:
        ComplianceAssessment for GDPR compliance.

    Raises:
        SystemHaltedError: If system is halted (CT-11).
    """
    requirements = [
        NFR31_REQUIREMENT,
        NFR32_REQUIREMENT,
        NFR33_REQUIREMENT,
        NFR34_REQUIREMENT,
    ]

    return await service.document_assessment(
        framework=ComplianceFramework.GDPR,
        requirements=requirements,
        gaps=[],
        remediation_plan=None,
        framework_version=GDPR_VERSION,
    )


async def initialize_eu_ai_act_compliance(
    service: ComplianceDocumentationService,
) -> ComplianceAssessment:
    """Initialize EU AI Act compliance documentation.

    Args:
        service: ComplianceDocumentationService for documenting compliance.

    Returns:
        ComplianceAssessment for EU AI Act compliance.

    Raises:
        SystemHaltedError: If system is halted (CT-11).
    """
    requirements = [
        EU_AI_ACT_HUMAN_OVERSIGHT,
        EU_AI_ACT_TRANSPARENCY,
        EU_AI_ACT_AUDIT_TRAIL,
    ]

    return await service.document_assessment(
        framework=ComplianceFramework.EU_AI_ACT,
        requirements=requirements,
        gaps=[],
        remediation_plan=None,
        framework_version=EU_AI_ACT_VERSION,
    )


async def initialize_nist_ai_rmf_compliance(
    service: ComplianceDocumentationService,
) -> ComplianceAssessment:
    """Initialize NIST AI RMF compliance documentation.

    Args:
        service: ComplianceDocumentationService for documenting compliance.

    Returns:
        ComplianceAssessment for NIST AI RMF compliance.

    Raises:
        SystemHaltedError: If system is halted (CT-11).
    """
    requirements = [
        NIST_AI_RMF_GOVERN,
        NIST_AI_RMF_MAP,
        NIST_AI_RMF_MEASURE,
        NIST_AI_RMF_MANAGE,
    ]

    return await service.document_assessment(
        framework=ComplianceFramework.NIST_AI_RMF,
        requirements=requirements,
        gaps=[],
        remediation_plan=None,
        framework_version=NIST_AI_RMF_VERSION,
    )


async def initialize_ieee_7001_compliance(
    service: ComplianceDocumentationService,
) -> ComplianceAssessment:
    """Initialize IEEE 7001 compliance documentation.

    Args:
        service: ComplianceDocumentationService for documenting compliance.

    Returns:
        ComplianceAssessment for IEEE 7001 compliance.

    Raises:
        SystemHaltedError: If system is halted (CT-11).
    """
    requirements = [
        IEEE_7001_TRACEABILITY,
        IEEE_7001_VERSIONING,
        IEEE_7001_PUBLIC_VERIFICATION,
    ]

    return await service.document_assessment(
        framework=ComplianceFramework.IEEE_7001,
        requirements=requirements,
        gaps=[],
        remediation_plan=None,
        framework_version=IEEE_7001_VERSION,
    )


async def initialize_all_compliance_documentation(
    service: ComplianceDocumentationService,
) -> tuple[ComplianceAssessment, ...]:
    """Initialize all compliance documentation for NFR31-34.

    Initializes documentation for:
    - GDPR (NFR31-34)
    - EU AI Act
    - NIST AI RMF
    - IEEE 7001

    This function can be called during application startup to ensure
    all compliance documentation is properly recorded.

    Args:
        service: ComplianceDocumentationService for documenting compliance.

    Returns:
        Tuple of all ComplianceAssessments created.

    Raises:
        SystemHaltedError: If system is halted (CT-11).

    Example:
        # During application startup
        assessments = await initialize_all_compliance_documentation(service)
        for a in assessments:
            logger.info("Compliance documented", framework=a.framework.value)
    """
    gdpr = await initialize_gdpr_compliance(service)
    eu_ai_act = await initialize_eu_ai_act_compliance(service)
    nist = await initialize_nist_ai_rmf_compliance(service)
    ieee = await initialize_ieee_7001_compliance(service)

    return (gdpr, eu_ai_act, nist, ieee)
