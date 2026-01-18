"""Petition API routes (Story 7.2, FR39).

FastAPI router for external observer petition endpoints.

Constitutional Constraints:
- FR39: External observers can petition with 100+ co-signers
- FR44: Public read access without authentication
- AC1: Submit petition with Ed25519 signature
- AC2: Co-sign with duplicate rejection
- AC3: Threshold triggers agenda placement
- AC4: Ed25519 signature algorithm
- AC7: Halt rejects writes, allows reads
- AC8: Public petition listing
- CT-11: Silent failure destroys legitimacy - fail loud on errors
- CT-12: Witnessing creates accountability - all actions have attribution
- CT-13: Reads allowed during halt

Developer Golden Rules:
1. HALT CHECK FIRST - Service handles halt for writes
2. WITNESS EVERYTHING - Events written via EventWriterService
3. FAIL LOUD - Return meaningful error responses
4. READS DURING HALT - List/get endpoints work during halt
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.models.petition import (
    CoSignerResponse,
    CosignPetitionRequest,
    CosignPetitionResponse,
    ListPetitionsResponse,
    PetitionDetailResponse,
    PetitionErrorResponse,
    PetitionSummaryResponse,
    SubmitPetitionRequest,
    SubmitPetitionResponse,
)
from src.application.services.petition_service import PetitionService
from src.domain.errors import SystemHaltedError
from src.domain.errors.petition import (
    DuplicateCosignatureError,
    InvalidSignatureError,
    PetitionClosedError,
    PetitionNotFoundError,
)

router = APIRouter(prefix="/v1/petitions", tags=["petitions"])


# =============================================================================
# Dependency Injection Placeholder
# =============================================================================
# In production, this would be replaced with proper DI from the FastAPI app
# For now, we raise NotImplementedError as a placeholder


async def get_petition_service() -> PetitionService:
    """Get petition service instance.

    This is a placeholder dependency. In production, this would be
    configured via FastAPI dependency injection with proper service
    instantiation.

    Raises:
        NotImplementedError: Until proper DI is configured.
    """
    # TODO: Replace with actual service instantiation
    raise NotImplementedError(
        "PetitionService dependency not configured. "
        "Configure this in src/api/dependencies/petition.py"
    )


# =============================================================================
# Petition Endpoints
# =============================================================================


@router.post(
    "",
    response_model=SubmitPetitionResponse,
    status_code=201,
    responses={
        400: {"model": PetitionErrorResponse, "description": "Invalid signature"},
        503: {"model": PetitionErrorResponse, "description": "System halted"},
    },
    summary="Submit a new petition",
    description=(
        "Submit a new cessation petition with Ed25519 signature. "
        "Requires system to be operational (writes blocked during halt). "
        "FR39, AC1, AC4, AC7."
    ),
)
async def submit_petition(
    request_data: SubmitPetitionRequest,
    request: Request,
    petition_service: PetitionService = Depends(get_petition_service),
) -> SubmitPetitionResponse:
    """Submit a new petition (FR39, AC1).

    Constitutional Constraints:
    - AC1: Petition created with submitter's Ed25519 signature
    - AC4: Signature verification required
    - AC7: Rejected during halt (write operation)
    - CT-12: Event witnessed via EventWriterService
    """
    try:
        result = await petition_service.submit_petition(
            petition_content=request_data.petition_content,
            submitter_public_key=request_data.submitter_public_key,
            submitter_signature=request_data.submitter_signature,
        )
        return SubmitPetitionResponse(
            petition_id=result.petition_id,
            created_at=result.created_at,
            status="open",
        )

    except InvalidSignatureError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://archon72.io/errors/invalid-signature",
                "title": "Invalid Signature",
                "status": 400,
                "detail": str(e),
                "instance": str(request.url),
            },
        )

    except SystemHaltedError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": str(e),
                "instance": str(request.url),
            },
        )


@router.post(
    "/{petition_id}/cosign",
    response_model=CosignPetitionResponse,
    responses={
        400: {
            "model": PetitionErrorResponse,
            "description": "Invalid signature or duplicate",
        },
        404: {"model": PetitionErrorResponse, "description": "Petition not found"},
        409: {"model": PetitionErrorResponse, "description": "Petition closed"},
        503: {"model": PetitionErrorResponse, "description": "System halted"},
    },
    summary="Co-sign a petition",
    description=(
        "Add a co-signature to an existing petition. "
        "Duplicate signatures from same public key are rejected. "
        "At 100 co-signers, cessation is placed on agenda. "
        "FR39, AC2, AC3, AC4, AC5, AC7."
    ),
)
async def cosign_petition(
    petition_id: UUID,
    request_data: CosignPetitionRequest,
    request: Request,
    petition_service: PetitionService = Depends(get_petition_service),
) -> CosignPetitionResponse:
    """Co-sign a petition (FR39, AC2, AC3).

    Constitutional Constraints:
    - AC2: Duplicate co-signatures rejected
    - AC3: 100 co-signers triggers agenda placement
    - AC4: Signature verification required
    - AC5: Idempotent agenda placement
    - AC7: Rejected during halt (write operation)
    - CT-12: Event witnessed via EventWriterService
    """
    try:
        result = await petition_service.cosign_petition(
            petition_id=petition_id,
            cosigner_public_key=request_data.cosigner_public_key,
            cosigner_signature=request_data.cosigner_signature,
        )
        return CosignPetitionResponse(
            petition_id=result.petition_id,
            cosigner_sequence=result.cosigner_sequence,
            cosigner_count=result.cosigner_count,
            threshold_met=result.threshold_met,
            agenda_placement_id=result.agenda_placement_id,
        )

    except PetitionNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://archon72.io/errors/petition-not-found",
                "title": "Petition Not Found",
                "status": 404,
                "detail": str(e),
                "instance": str(request.url),
            },
        )

    except DuplicateCosignatureError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://archon72.io/errors/duplicate-cosignature",
                "title": "Duplicate Co-Signature",
                "status": 400,
                "detail": str(e),
                "instance": str(request.url),
            },
        )

    except PetitionClosedError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "type": "https://archon72.io/errors/petition-closed",
                "title": "Petition Closed",
                "status": 409,
                "detail": str(e),
                "instance": str(request.url),
            },
        )

    except InvalidSignatureError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://archon72.io/errors/invalid-signature",
                "title": "Invalid Signature",
                "status": 400,
                "detail": str(e),
                "instance": str(request.url),
            },
        )

    except SystemHaltedError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://archon72.io/errors/system-halted",
                "title": "System Halted",
                "status": 503,
                "detail": str(e),
                "instance": str(request.url),
            },
        )


@router.get(
    "/{petition_id}",
    response_model=PetitionDetailResponse,
    responses={
        404: {"model": PetitionErrorResponse, "description": "Petition not found"},
    },
    summary="Get petition details",
    description=(
        "Get detailed information about a specific petition. "
        "Public access - no authentication required. "
        "Works during halt (read operation). "
        "FR39, FR44, AC7, AC8."
    ),
)
async def get_petition(
    petition_id: UUID,
    request: Request,
    petition_service: PetitionService = Depends(get_petition_service),
) -> PetitionDetailResponse:
    """Get petition details (FR39, AC8).

    Constitutional Constraints:
    - FR44: Public access without authentication
    - AC7: Reads allowed during halt
    - AC8: Public petition access
    - CT-13: Read operations work during halt
    """
    petition = await petition_service.get_petition(petition_id)

    if petition is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://archon72.io/errors/petition-not-found",
                "title": "Petition Not Found",
                "status": 404,
                "detail": f"Petition {petition_id} not found",
                "instance": str(request.url),
            },
        )

    return PetitionDetailResponse(
        petition_id=petition.petition_id,
        submitter_public_key=petition.submitter_public_key,
        petition_content=petition.petition_content,
        created_at=petition.created_timestamp,
        status=petition.status.value,
        cosigner_count=petition.cosigner_count,
        threshold_met_at=petition.threshold_met_at,
        cosigners=[
            CoSignerResponse(
                public_key=c.public_key,
                signed_at=c.signed_at,
                sequence=c.sequence,
            )
            for c in petition.cosigners
        ],
    )


@router.get(
    "",
    response_model=ListPetitionsResponse,
    summary="List open petitions",
    description=(
        "List all open petitions with pagination. "
        "Public access - no authentication required. "
        "Works during halt (read operation). "
        "FR39, FR44, AC7, AC8."
    ),
)
async def list_petitions(
    request: Request,
    petition_service: PetitionService = Depends(get_petition_service),
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListPetitionsResponse:
    """List open petitions (FR39, AC8).

    Constitutional Constraints:
    - FR44: Public access without authentication
    - AC7: Reads allowed during halt
    - AC8: Public petition listing
    - CT-13: Read operations work during halt
    """
    petitions, total = await petition_service.list_open_petitions(
        limit=limit,
        offset=offset,
    )

    return ListPetitionsResponse(
        petitions=[
            PetitionSummaryResponse(
                petition_id=p.petition_id,
                submitter_public_key=p.submitter_public_key[:32] + "...",
                petition_content_preview=p.petition_content[:200]
                + ("..." if len(p.petition_content) > 200 else ""),
                created_at=p.created_timestamp,
                status=p.status.value,
                cosigner_count=p.cosigner_count,
            )
            for p in petitions
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
