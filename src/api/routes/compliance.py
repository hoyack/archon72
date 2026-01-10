"""Compliance API routes (Story 9.9, NFR31-34).

FastAPI router for compliance documentation query endpoints.

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available
- FR44: Public read access without authentication
- CT-11: Silent failure destroys legitimacy - fail loud on errors
- CT-12: Witnessing creates accountability - all actions have attribution
- CT-13: Reads allowed during halt

Developer Golden Rules:
1. HALT CHECK FIRST - Service handles halt checking
2. WITNESS EVERYTHING - Compliance events written via EventWriterService
3. FAIL LOUD - Return meaningful error responses
4. READS DURING HALT - All endpoints are read-only, work during halt
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from src.api.models.compliance import (
    ComplianceAssessmentResponse,
    ComplianceErrorResponse,
    ComplianceFrameworksListResponse,
    ComplianceGapsResponse,
    CompliancePostureResponse,
    ComplianceRequirementResponse,
)
from src.application.services.compliance_documentation_service import (
    ComplianceDocumentationService,
)
from src.domain.errors import SystemHaltedError
from src.domain.models.compliance import ComplianceFramework, ComplianceStatus

router = APIRouter(prefix="/v1/compliance", tags=["compliance"])


# =============================================================================
# Dependency Injection Placeholder
# =============================================================================
# In production, this would be replaced with proper DI from the FastAPI app
# For now, we raise NotImplementedError as a placeholder


async def get_compliance_service() -> ComplianceDocumentationService:
    """Get compliance documentation service instance.

    This is a placeholder dependency. In production, this would be
    configured via FastAPI dependency injection with proper service
    instantiation.

    Raises:
        NotImplementedError: Until proper DI is configured.
    """
    # TODO: Replace with actual service instantiation
    raise NotImplementedError(
        "ComplianceDocumentationService dependency not configured. "
        "Configure this in src/api/dependencies/compliance.py"
    )


# =============================================================================
# Compliance Endpoints
# =============================================================================


@router.get(
    "",
    response_model=CompliancePostureResponse,
    responses={
        503: {"model": ComplianceErrorResponse, "description": "System halted"},
    },
    summary="Get compliance posture",
    description=(
        "Get overall compliance posture across all frameworks. "
        "Returns framework -> status mapping for quick overview. "
        "Public read access without authentication (FR44). "
        "NFR31-34, FR44, AC4."
    ),
)
async def get_compliance_posture(
    request: Request,
    compliance_service: ComplianceDocumentationService = Depends(get_compliance_service),
) -> CompliancePostureResponse:
    """Get compliance posture across all frameworks (NFR31-34, FR44, AC4).

    Returns framework to status mapping for quick compliance overview.
    Public read access without authentication.

    Returns:
        CompliancePostureResponse with framework -> status mapping.

    Raises:
        HTTPException 503: If system is halted (CT-11).
    """
    try:
        posture = await compliance_service.get_compliance_posture()
        posture_dict = {k.value: v.value for k, v in posture.items()}

        compliant_count = sum(
            1 for v in posture.values() if v == ComplianceStatus.COMPLIANT
        )
        gaps_count = sum(
            1 for v in posture.values() if v == ComplianceStatus.GAP_IDENTIFIED
        )

        return CompliancePostureResponse(
            posture=posture_dict,
            total_frameworks=len(posture),
            compliant_count=compliant_count,
            gaps_count=gaps_count,
        )
    except SystemHaltedError:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "System is halted - compliance queries unavailable",
                "instance": str(request.url),
            },
        )


@router.get(
    "/frameworks",
    response_model=ComplianceFrameworksListResponse,
    responses={
        503: {"model": ComplianceErrorResponse, "description": "System halted"},
    },
    summary="List all framework assessments",
    description=(
        "List the latest assessment for each compliance framework. "
        "Public read access without authentication (FR44). "
        "NFR31-34, FR44, AC4."
    ),
)
async def list_framework_assessments(
    request: Request,
    compliance_service: ComplianceDocumentationService = Depends(get_compliance_service),
) -> ComplianceFrameworksListResponse:
    """List all framework assessments (NFR31-34, FR44, AC4).

    Returns the latest assessment for each framework that has been assessed.
    Public read access without authentication.

    Returns:
        ComplianceFrameworksListResponse with all assessments.

    Raises:
        HTTPException 503: If system is halted (CT-11).
    """
    try:
        assessments = await compliance_service.get_all_assessments()
        return ComplianceFrameworksListResponse(
            assessments=[
                ComplianceAssessmentResponse(
                    assessment_id=a.assessment_id,
                    framework=a.framework.value,
                    assessment_date=a.assessment_date,
                    requirements=[
                        ComplianceRequirementResponse(
                            requirement_id=r.requirement_id,
                            framework=r.framework.value,
                            description=r.description,
                            status=r.status.value,
                            implementation_reference=r.implementation_reference,
                            evidence=list(r.evidence),
                        )
                        for r in a.requirements
                    ],
                    overall_status=a.overall_status.value,
                    gaps=list(a.gaps),
                    remediation_plan=a.remediation_plan,
                )
                for a in assessments
            ],
            total_count=len(assessments),
        )
    except SystemHaltedError:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "System is halted - compliance queries unavailable",
                "instance": str(request.url),
            },
        )


@router.get(
    "/frameworks/{framework}",
    response_model=ComplianceAssessmentResponse,
    responses={
        404: {"model": ComplianceErrorResponse, "description": "Framework not found"},
        503: {"model": ComplianceErrorResponse, "description": "System halted"},
    },
    summary="Get framework assessment",
    description=(
        "Get the latest assessment for a specific compliance framework. "
        "Public read access without authentication (FR44). "
        "NFR31-34, FR44, AC4."
    ),
)
async def get_framework_assessment(
    request: Request,
    framework: Annotated[
        str,
        Path(
            description="Compliance framework",
            examples=["EU_AI_ACT", "NIST_AI_RMF", "IEEE_7001", "GDPR", "MAESTRO"],
        ),
    ],
    compliance_service: ComplianceDocumentationService = Depends(get_compliance_service),
) -> ComplianceAssessmentResponse:
    """Get the latest assessment for a specific framework (NFR31-34, FR44, AC4).

    Returns the most recent assessment for the specified framework.
    Public read access without authentication.

    Args:
        framework: Compliance framework name (e.g., "EU_AI_ACT").

    Returns:
        ComplianceAssessmentResponse with assessment details.

    Raises:
        HTTPException 404: If framework not found or not assessed.
        HTTPException 503: If system is halted (CT-11).
    """
    try:
        # Validate framework name
        try:
            framework_enum = ComplianceFramework(framework)
        except ValueError:
            valid_frameworks = [f.value for f in ComplianceFramework]
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "https://archon72.io/errors/invalid-framework",
                    "title": "Invalid Framework",
                    "status": 404,
                    "detail": (
                        f"Framework '{framework}' is not valid. "
                        f"Valid frameworks: {valid_frameworks}"
                    ),
                    "instance": str(request.url),
                },
            )

        assessment = await compliance_service.get_framework_assessment(framework_enum)
        if assessment is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "https://archon72.io/errors/framework-not-assessed",
                    "title": "Framework Not Assessed",
                    "status": 404,
                    "detail": f"No assessment found for framework '{framework}'",
                    "instance": str(request.url),
                },
            )

        return ComplianceAssessmentResponse(
            assessment_id=assessment.assessment_id,
            framework=assessment.framework.value,
            assessment_date=assessment.assessment_date,
            requirements=[
                ComplianceRequirementResponse(
                    requirement_id=r.requirement_id,
                    framework=r.framework.value,
                    description=r.description,
                    status=r.status.value,
                    implementation_reference=r.implementation_reference,
                    evidence=list(r.evidence),
                )
                for r in assessment.requirements
            ],
            overall_status=assessment.overall_status.value,
            gaps=list(assessment.gaps),
            remediation_plan=assessment.remediation_plan,
        )
    except HTTPException:
        raise
    except SystemHaltedError:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "System is halted - compliance queries unavailable",
                "instance": str(request.url),
            },
        )


@router.get(
    "/gaps",
    response_model=ComplianceGapsResponse,
    responses={
        503: {"model": ComplianceErrorResponse, "description": "System halted"},
    },
    summary="List compliance gaps",
    description=(
        "List all requirements with GAP_IDENTIFIED status. "
        "Public read access without authentication (FR44). "
        "NFR31-34, FR44, AC4."
    ),
)
async def list_compliance_gaps(
    request: Request,
    compliance_service: ComplianceDocumentationService = Depends(get_compliance_service),
) -> ComplianceGapsResponse:
    """List all compliance gaps (NFR31-34, FR44, AC4).

    Returns all requirements with GAP_IDENTIFIED status across all frameworks.
    Public read access without authentication.

    Returns:
        ComplianceGapsResponse with all gap requirements.

    Raises:
        HTTPException 503: If system is halted (CT-11).
    """
    try:
        gaps = await compliance_service.get_gaps()
        return ComplianceGapsResponse(
            gaps=[
                ComplianceRequirementResponse(
                    requirement_id=r.requirement_id,
                    framework=r.framework.value,
                    description=r.description,
                    status=r.status.value,
                    implementation_reference=r.implementation_reference,
                    evidence=list(r.evidence),
                )
                for r in gaps
            ],
            total_count=len(gaps),
        )
    except SystemHaltedError:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": "System is halted - compliance queries unavailable",
                "instance": str(request.url),
            },
        )
