"""Ceased Response Middleware (Story 7.5, Task 1).

This middleware injects CeasedStatusHeader into all responses when
the system has permanently ceased (FR42).

Constitutional Constraints:
- FR42: Read-only access indefinitely after cessation
- CT-11: Silent failure destroys legitimacy → Cessation status MUST be visible in ALL responses
- CT-13: Integrity outranks availability → Read access is GUARANTEED indefinitely

This middleware ONLY injects cessation information into responses.
It does NOT block any requests - that is handled by the require_not_ceased
dependency in Task 2.

Developer Golden Rules:
1. READS ALWAYS WORK - This middleware never blocks requests
2. STATUS IN EVERY RESPONSE - Every response includes cessation status when ceased
3. PRESERVE ORIGINAL DATA - Original response data is never lost
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from src.application.ports.freeze_checker import FreezeCheckerProtocol


class CeasedResponseMiddleware(BaseHTTPMiddleware):
    """Middleware that injects CeasedStatusHeader into all responses (FR42, AC5).

    When the system is in a ceased state, this middleware:
    1. Adds X-System-Status, X-Ceased-At, X-Final-Sequence headers to all responses
    2. For JSON responses, injects cessation_info into the response body

    This ensures external observers ALWAYS know when they are reading from
    a permanently ceased system (CT-11: Silent failure destroys legitimacy).

    Important: This middleware does NOT block any requests. Blocking writes
    is handled by the require_not_ceased dependency.

    Usage:
        app.add_middleware(CeasedResponseMiddleware, freeze_checker=freeze_checker)

    Attributes:
        _freeze_checker: Protocol for checking freeze state.
    """

    def __init__(
        self,
        app: Callable,
        freeze_checker: FreezeCheckerProtocol,
    ) -> None:
        """Initialize CeasedResponseMiddleware.

        Args:
            app: The ASGI app to wrap.
            freeze_checker: Protocol for checking if system is frozen.
        """
        super().__init__(app)
        self._freeze_checker = freeze_checker

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and inject cessation info if system is ceased.

        Per FR42: Read endpoints remain functional indefinitely.
        Per CT-11: Cessation status is visible in ALL responses.
        Per AC5: CeasedStatusHeader included in all read responses.

        Args:
            request: The incoming request.
            call_next: The next middleware/endpoint in the chain.

        Returns:
            Response with cessation headers/body when system is ceased.
        """
        # Call the actual endpoint first - reads are ALWAYS allowed
        response = await call_next(request)

        # Check if system is frozen AFTER getting response
        # This ensures we never block reads
        if not await self._freeze_checker.is_frozen():
            return response

        # System is ceased - get details for headers/body injection
        details = await self._freeze_checker.get_freeze_details()

        if details is None:
            # Frozen but no details - still add basic headers
            response.headers["X-System-Status"] = "CEASED"
            return response

        # Add cessation headers to ALL responses
        response.headers["X-System-Status"] = "CEASED"
        response.headers["X-Ceased-At"] = details.ceased_at.isoformat()
        response.headers["X-Final-Sequence"] = str(details.final_sequence_number)

        # For JSON responses, inject cessation_info into body
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            response = await self._inject_cessation_info_to_json(response, details)

        return response

    async def _inject_cessation_info_to_json(
        self,
        response: Response,
        details: CessationDetails,
    ) -> Response:
        """Inject cessation_info into JSON response body.

        Parses the response body, adds cessation_info, and returns
        a new response with the modified body.

        Per AC5: cessation_info contains: system_status, ceased_at,
        final_sequence_number, cessation_reason.

        Args:
            response: The original JSON response.
            details: Cessation details to inject.

        Returns:
            New response with cessation_info injected.
        """
        from starlette.responses import JSONResponse

        try:
            # Read the response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Parse as JSON
            data = json.loads(body)

            # Inject cessation_info
            data["cessation_info"] = {
                "system_status": "CEASED",
                "ceased_at": details.ceased_at.isoformat(),
                "final_sequence_number": details.final_sequence_number,
                "cessation_reason": details.reason,
            }

            # Create new response with modified body
            # Preserve original status code and headers
            new_response = JSONResponse(
                content=data,
                status_code=response.status_code,
            )

            # Copy headers from original response
            for key, value in response.headers.items():
                if key.lower() not in ("content-length", "content-type"):
                    new_response.headers[key] = value

            # Ensure cessation headers are present
            new_response.headers["X-System-Status"] = "CEASED"
            new_response.headers["X-Ceased-At"] = details.ceased_at.isoformat()
            new_response.headers["X-Final-Sequence"] = str(
                details.final_sequence_number
            )

            return new_response

        except (json.JSONDecodeError, Exception):
            # If we can't parse the JSON, just return original with headers
            return response
