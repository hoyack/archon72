"""High Archon authorization helper (Story 8.4, FR-8.4).

This module provides authentication and authorization for High Archon operations,
including access to the legitimacy dashboard.

Constitutional Constraints:
- FR-8.4: Dashboard accessible to High Archon only
- NFR-5.6: Authorization check completes quickly (<50ms)
- CT-12: Witnessing creates accountability -> Log all auth attempts
"""

from typing import Annotated
from uuid import UUID

from fastapi import Header, HTTPException, status

import structlog

logger = structlog.get_logger(__name__)


def get_high_archon_id(
    x_archon_id: Annotated[
        str | None,
        Header(
            description="Archon ID for authentication. Required for High Archon operations."
        ),
    ] = None,
    x_archon_role: Annotated[
        str | None,
        Header(
            description="Archon role for authorization. Must be 'HIGH_ARCHON' for dashboard access."
        ),
    ] = None,
) -> UUID:
    """Extract and validate High Archon ID from headers (FR-8.4).

    Validates that:
    1. X-Archon-Id header is present and valid UUID
    2. X-Archon-Role header is present and equals "HIGH_ARCHON"

    Args:
        x_archon_id: Archon ID from X-Archon-Id header.
        x_archon_role: Archon role from X-Archon-Role header.

    Returns:
        Validated High Archon UUID.

    Raises:
        HTTPException 401: If authentication headers are missing or invalid.
        HTTPException 403: If role is not HIGH_ARCHON.
    """
    log = logger.bind(component="high_archon_auth")

    # Check authentication (X-Archon-Id header)
    if not x_archon_id:
        log.warning("auth_failed", reason="missing_archon_id")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Archon-Id header is required for High Archon operations",
        )

    # Validate UUID format
    try:
        archon_uuid = UUID(x_archon_id)
    except ValueError:
        log.warning("auth_failed", reason="invalid_archon_id", archon_id=x_archon_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Archon ID format (must be UUID)",
        )

    # Check authorization (X-Archon-Role header)
    if not x_archon_role:
        log.warning("auth_failed", reason="missing_role", archon_id=str(archon_uuid))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Archon-Role header is required for High Archon operations",
        )

    if x_archon_role != "HIGH_ARCHON":
        log.warning(
            "authz_failed",
            reason="insufficient_role",
            archon_id=str(archon_uuid),
            provided_role=x_archon_role,
            required_role="HIGH_ARCHON",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"High Archon role required. Provided role: {x_archon_role}",
        )

    # Success - log for audit trail (CT-12)
    log.info(
        "high_archon_authenticated",
        archon_id=str(archon_uuid),
        role=x_archon_role,
    )

    return archon_uuid
