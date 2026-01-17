"""Halt API routes (Story consent-gov-4.2).

FastAPI router for halt trigger endpoint.
Authentication required for halt operations.

Constitutional Constraints:
- FR22: Human Operator can trigger system halt
- FR23: System can execute halt operation
- AC6: Operator must be authenticated and authorized
- NFR-PERF-01: Halt completes in ≤100ms
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status

from src.api.models.halt import (
    HaltErrorResponse,
    HaltRequest,
    HaltResponse,
    HaltStatusResponse,
)
from src.application.ports.governance.halt_port import HaltPort
from src.application.ports.governance.halt_trigger_port import (
    HaltMessageRequiredError,
    UnauthorizedHaltError,
)
from src.application.services.governance.halt_service import HaltService
from src.domain.governance.halt import HaltReason


router = APIRouter(prefix="/v1/governance/halt", tags=["governance", "halt"])


# Dependency injection placeholders
# In production, these would be provided by the DI container
_halt_service: HaltService | None = None
_halt_port: HaltPort | None = None


def set_halt_service(service: HaltService) -> None:
    """Set the halt service for dependency injection."""
    global _halt_service
    _halt_service = service


def set_halt_port(port: HaltPort) -> None:
    """Set the halt port for dependency injection."""
    global _halt_port
    _halt_port = port


def get_halt_service() -> HaltService:
    """Get the halt service.

    Raises:
        RuntimeError: If halt service not configured.
    """
    if _halt_service is None:
        raise RuntimeError("Halt service not configured")
    return _halt_service


def get_halt_port() -> HaltPort:
    """Get the halt port.

    Raises:
        RuntimeError: If halt port not configured.
    """
    if _halt_port is None:
        raise RuntimeError("Halt port not configured")
    return _halt_port


def get_operator_id(
    x_operator_id: Annotated[
        str | None,
        Header(
            description="Operator ID for authentication. Required for halt operations."
        ),
    ] = None,
) -> UUID:
    """Extract and validate operator ID from header.

    Per AC6: Operator must be authenticated.

    Args:
        x_operator_id: Operator ID from X-Operator-Id header.

    Returns:
        Validated operator UUID.

    Raises:
        HTTPException: If operator ID is missing or invalid.
    """
    if not x_operator_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Operator-Id header is required",
        )

    try:
        return UUID(x_operator_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid operator ID format (must be UUID)",
        )


@router.post(
    "",
    response_model=HaltResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": HaltErrorResponse, "description": "Unauthorized"},
        403: {"model": HaltErrorResponse, "description": "Forbidden"},
        422: {"model": HaltErrorResponse, "description": "Validation Error"},
    },
    summary="Trigger system halt",
    description="""
Trigger a system halt. This is an emergency operation that stops all
governance operations immediately.

**Requires authentication via X-Operator-Id header.**

Per FR22: Human Operator can trigger system halt.
Per AC6: Operator must be authenticated and authorized.
Per NFR-PERF-01: Halt completes in ≤100ms.
""",
)
async def trigger_halt(
    request: HaltRequest,
    operator_id: Annotated[UUID, Depends(get_operator_id)],
    halt_service: Annotated[HaltService, Depends(get_halt_service)],
) -> HaltResponse:
    """Trigger system halt.

    Per FR22: Human Operator can trigger system halt.
    Per AC6: Operator must be authenticated and authorized.

    Args:
        request: Halt request with reason and message.
        operator_id: Authenticated operator ID from header.
        halt_service: Injected halt service.

    Returns:
        HaltResponse with execution details.

    Raises:
        HTTPException: If unauthorized or invalid request.
    """
    try:
        reason = HaltReason(request.reason)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid halt reason: {request.reason}",
        )

    try:
        result = await halt_service.trigger_halt(
            operator_id=operator_id,
            reason=reason,
            message=request.message,
        )

        return HaltResponse(
            success=result.success,
            halted_at=result.executed_at,
            execution_ms=result.execution_ms,
            channels_reached=result.channels_reached,
            reason=request.reason,
            message=request.message,
        )

    except UnauthorizedHaltError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    except HaltMessageRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.get(
    "/status",
    response_model=HaltStatusResponse,
    summary="Get halt status",
    description="""
Get the current halt status of the system.

This endpoint does NOT require authentication as halt status
is public information for transparency.
""",
)
async def get_halt_status(
    halt_port: Annotated[HaltPort, Depends(get_halt_port)],
) -> HaltStatusResponse:
    """Get current halt status.

    Public endpoint - no authentication required.

    Args:
        halt_port: Injected halt port.

    Returns:
        HaltStatusResponse with current status.
    """
    status = halt_port.get_halt_status()

    return HaltStatusResponse(
        is_halted=status.is_halted,
        halted_at=status.halted_at,
        reason=status.reason.value if status.reason else None,
        message=status.message,
        operator_id=str(status.operator_id) if status.operator_id else None,
    )
