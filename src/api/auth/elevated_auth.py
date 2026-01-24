"""Elevated authorization helper (Story 7.6, FR-7.4, Ruling-2).

This module provides authentication and authorization for elevated operations
that require HIGH_ARCHON or AUDITOR role. This is the elevated tier of
Ruling-2 - full transcript access for governance actors.

Constitutional Constraints:
- Ruling-2: Elevated tier access for HIGH_ARCHON and AUDITOR only
- FR-7.4: System SHALL provide full transcript to governance actors
- CT-12: Witnessing creates accountability - Log all auth attempts
- AC-1: HIGH_ARCHON role gets full access
- AC-2: AUDITOR role gets full access
- AC-3: OBSERVER role denied with redirect hint
- AC-4: SEEKER role denied with redirect hint
"""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Header, HTTPException, Request, status

logger = structlog.get_logger(__name__)

# Roles that are allowed elevated access
ELEVATED_ROLES = {"HIGH_ARCHON", "AUDITOR"}

# Roles that should be redirected to mediated access
MEDIATED_ROLES = {"OBSERVER", "SEEKER"}


@dataclass(frozen=True)
class ElevatedActor:
    """Authenticated elevated actor with role (Story 7.6).

    Represents a governance actor with elevated transcript access.

    Attributes:
        archon_id: UUID of the authenticated archon.
        role: Role of the archon (HIGH_ARCHON or AUDITOR).
    """

    archon_id: UUID
    role: str


def get_elevated_actor(
    request: Request,
    x_archon_id: Annotated[
        str | None,
        Header(
            description="Archon ID for authentication. Required for elevated operations."
        ),
    ] = None,
    x_archon_role: Annotated[
        str | None,
        Header(
            description="Archon role for authorization. Must be 'HIGH_ARCHON' or 'AUDITOR'."
        ),
    ] = None,
) -> ElevatedActor:
    """Extract and validate elevated actor from headers (Story 7.6, AC-1, AC-2, AC-3, AC-4).

    Validates that:
    1. X-Archon-Id header is present and valid UUID
    2. X-Archon-Role header is present
    3. Role is HIGH_ARCHON or AUDITOR (elevated tier)

    Returns 403 Forbidden with redirect hint for OBSERVER/SEEKER roles.

    Args:
        request: FastAPI request object for IP logging.
        x_archon_id: Archon ID from X-Archon-Id header.
        x_archon_role: Archon role from X-Archon-Role header.

    Returns:
        ElevatedActor with validated archon_id and role.

    Raises:
        HTTPException 401: If authentication headers are missing or invalid.
        HTTPException 403: If role is not elevated (includes redirect hint).
    """
    log = logger.bind(component="elevated_auth")

    # Get request IP for audit logging
    request_ip = request.client.host if request.client else "unknown"

    # Check authentication (X-Archon-Id header)
    if not x_archon_id:
        log.warning("auth_failed", reason="missing_archon_id", request_ip=request_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Archon-Id header is required for elevated operations",
        )

    # Validate UUID format
    try:
        archon_uuid = UUID(x_archon_id)
    except ValueError:
        log.warning(
            "auth_failed",
            reason="invalid_archon_id",
            archon_id=x_archon_id,
            request_ip=request_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Archon ID format (must be UUID)",
        )

    # Check authorization (X-Archon-Role header)
    if not x_archon_role:
        log.warning(
            "auth_failed",
            reason="missing_role",
            archon_id=str(archon_uuid),
            request_ip=request_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Archon-Role header is required for elevated operations",
        )

    # Check if role is elevated (HIGH_ARCHON or AUDITOR)
    if x_archon_role in ELEVATED_ROLES:
        # Success - log for audit trail (CT-12, AC-7)
        log.info(
            "elevated_actor_authenticated",
            archon_id=str(archon_uuid),
            role=x_archon_role,
            request_ip=request_ip,
        )
        return ElevatedActor(archon_id=archon_uuid, role=x_archon_role)

    # Role is not elevated - check if it's a mediated role
    if x_archon_role in MEDIATED_ROLES:
        # Log failed access attempt (CT-12)
        log.warning(
            "authz_failed",
            reason="insufficient_role_mediated",
            archon_id=str(archon_uuid),
            provided_role=x_archon_role,
            required_roles=list(ELEVATED_ROLES),
            request_ip=request_ip,
        )

        # Return 403 with redirect hint (AC-3, AC-4)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "urn:archon72:transcript:insufficient-role",
                "title": "Elevated role required for full transcript access",
                "status": 403,
                "detail": f"Role '{x_archon_role}' does not have elevated transcript access. "
                "Use the mediated summary endpoint instead.",
                "redirect_hint": "/api/v1/petitions/{petition_id}/deliberation-summary",
                "actor": str(archon_uuid),
            },
        )

    # Unknown role - generic 403
    log.warning(
        "authz_failed",
        reason="unknown_role",
        archon_id=str(archon_uuid),
        provided_role=x_archon_role,
        required_roles=list(ELEVATED_ROLES),
        request_ip=request_ip,
    )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Elevated role required. Provided role: {x_archon_role}. "
        f"Allowed roles: {', '.join(ELEVATED_ROLES)}",
    )
