"""Cessation dependencies for API endpoints (Story 7.5, Task 2).

This module provides dependencies for handling cessation state in API endpoints.

Constitutional Constraints:
- FR42: Read-only access indefinitely after cessation
- AC2: Write endpoints return 503 with Retry-After: never
- CT-11: Silent failure destroys legitimacy -> Clear error messages
- CT-13: Integrity outranks availability -> Reads always succeed

Developer Golden Rules:
1. READS NEVER BLOCKED - Only write endpoints use require_not_ceased
2. PERMANENT REJECTION - 503 with Retry-After: never signals no recovery
3. CLEAR ERRORS - Include reason, ceased_at, final_sequence in response
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

if TYPE_CHECKING:
    from src.application.ports.freeze_checker import FreezeCheckerProtocol


# Global singleton for freeze checker (replaced in production)
_freeze_checker: FreezeCheckerProtocol | None = None


def get_freeze_checker() -> FreezeCheckerProtocol:
    """Get the freeze checker instance.

    This is a factory function that can be overridden in tests.
    In production, this would return a real implementation.

    Returns:
        FreezeCheckerProtocol implementation.
    """
    global _freeze_checker
    if _freeze_checker is None:
        _freeze_checker = FreezeCheckerStub()
    return _freeze_checker


def set_freeze_checker(checker: FreezeCheckerProtocol) -> None:
    """Set the freeze checker instance (for production use).

    Args:
        checker: FreezeCheckerProtocol implementation.
    """
    global _freeze_checker
    _freeze_checker = checker


async def require_not_ceased(
    freeze_checker: FreezeCheckerProtocol = Depends(get_freeze_checker),
) -> None:
    """Dependency that blocks requests when system is ceased (AC2).

    Use this as a dependency on write endpoints to prevent modifications
    after system cessation.

    Per FR42: After cessation, only read access is allowed.
    Per AC2: Write endpoints return 503 with Retry-After: never.
    Per CT-11: Error includes cessation reason for transparency.

    Usage:
        @app.post("/events", dependencies=[Depends(require_not_ceased)])
        async def create_event():
            # This endpoint will return 503 if system is ceased
            ...

    Raises:
        HTTPException: 503 Service Unavailable if system is ceased.
    """
    if not await freeze_checker.is_frozen():
        # System is operational - allow request to proceed
        return

    # System is ceased - get details for error response
    details = await freeze_checker.get_freeze_details()

    # Build error response with full cessation context
    error_detail = {
        "error": "system_ceased",
        "message": "The Archon72 system has permanently ceased operations. "
        "Only read access is available indefinitely.",
        "system_status": "CEASED",
    }

    if details:
        error_detail["ceased_at"] = details.ceased_at.isoformat()
        error_detail["final_sequence_number"] = details.final_sequence_number
        error_detail["cessation_reason"] = details.reason

    # Build headers for the 503 response
    headers = {
        "Retry-After": "never",  # Signals permanent unavailability
        "X-System-Status": "CEASED",
    }

    if details:
        headers["X-Ceased-At"] = details.ceased_at.isoformat()
        headers["X-Final-Sequence"] = str(details.final_sequence_number)

    raise HTTPException(
        status_code=503,
        detail=error_detail,
        headers=headers,
    )


class CeasedWriteResponse(JSONResponse):
    """Custom JSON response for ceased write attempts (AC2).

    This response class is used when a write is attempted on a ceased system.
    It includes all required headers and a descriptive body.

    Not typically used directly - prefer the require_not_ceased dependency.
    But useful for manual response creation in special cases.

    Attributes:
        Inherits all from JSONResponse.

    Usage:
        if await freeze_checker.is_frozen():
            details = await freeze_checker.get_freeze_details()
            return CeasedWriteResponse.from_cessation_details(details)
    """

    @classmethod
    def from_cessation_details(
        cls,
        details: CessationDetails | None = None,
    ) -> CeasedWriteResponse:
        """Create response from cessation details.

        Args:
            details: Optional cessation details for full context.

        Returns:
            CeasedWriteResponse with 503 status and headers.
        """
        content = {
            "error": "system_ceased",
            "message": "The Archon72 system has permanently ceased operations. "
            "Only read access is available indefinitely.",
            "system_status": "CEASED",
        }

        headers = {
            "Retry-After": "never",
            "X-System-Status": "CEASED",
        }

        if details:
            content["ceased_at"] = details.ceased_at.isoformat()
            content["final_sequence_number"] = details.final_sequence_number
            content["cessation_reason"] = details.reason
            headers["X-Ceased-At"] = details.ceased_at.isoformat()
            headers["X-Final-Sequence"] = str(details.final_sequence_number)

        return cls(
            content=content,
            status_code=503,
            headers=headers,
        )


# Type hint for external use
if TYPE_CHECKING:
    from src.domain.models.ceased_status_header import CessationDetails
