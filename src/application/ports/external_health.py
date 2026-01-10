"""External health check port (Story 8.3, FR53/FR54).

This module defines the protocol for external health checking that allows
third-party monitoring services to independently detect system unavailability.

Constitutional Constraints:
- FR53: Operational metrics SHALL NOT assess constitutional integrity
- FR54: System unavailability SHALL be independently detectable
- CT-11: Silent failure destroys legitimacy -> External detection critical

Key Design Principles:
1. NO DATABASE QUERIES - Must be fast (<50ms target)
2. In-memory halt/freeze state only
3. No authentication required for basic availability
4. Status values intentionally vague (security)

Status Precedence Rules:
1. HALTED (highest) - Constitutional halt in effect
2. FROZEN - System ceased/frozen (read-only available)
3. UP - System operational
4. DOWN is inferred by external monitors via timeout (never returned)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Protocol


class ExternalHealthStatus(str, Enum):
    """External health status values (FR54).

    These values are intentionally minimal to:
    1. Avoid exposing internal state details (security)
    2. Enable fast checks with no complex logic
    3. Be parseable by external monitoring services

    DOWN is not a status we return - external monitors infer
    DOWN when they receive no response (timeout).
    """

    UP = "up"  # System operational, accepting requests
    HALTED = "halted"  # Constitutional halt in effect (Story 3.2-3.4)
    FROZEN = "frozen"  # System ceased/frozen, read-only (Story 7.4)


class ExternalHealthPort(Protocol):
    """Protocol for external health checking (FR54).

    This protocol defines the interface for checking system availability
    from an external observer's perspective. The implementation must be
    extremely fast (no DB queries) to serve as a reliable canary.

    Constitutional Constraint (FR54):
    System unavailability SHALL be independently detectable by external parties.
    This means external monitors can ping this interface and determine if the
    system is responsive without relying on self-reporting.

    Implementers MUST:
    1. Return status in <50ms (no database queries)
    2. Use cached halt/freeze state only
    3. Never expose sensitive internal state details
    4. Apply precedence: HALTED > FROZEN > UP

    Usage:
        status = await external_health.get_status()
        timestamp = await external_health.get_timestamp()

        # External monitors will:
        # - See "up" for healthy system
        # - See "halted" for constitutional halt
        # - See "frozen" for ceased system
        # - Infer "down" from timeout (no response)
    """

    async def get_status(self) -> ExternalHealthStatus:
        """Get the current external health status.

        Checks system state and returns the appropriate status:
        1. If halted -> HALTED (highest precedence)
        2. If frozen -> FROZEN
        3. Otherwise -> UP

        This method MUST be fast (<50ms) as it serves as the canary
        endpoint for external monitoring services.

        Returns:
            ExternalHealthStatus indicating current availability.
        """
        ...

    async def get_timestamp(self) -> datetime:
        """Get the current timestamp for the health check.

        Returns the server's current UTC timestamp, useful for:
        - Response freshness verification
        - Clock drift detection by monitors
        - Audit trail of health checks

        Returns:
            Current UTC datetime.
        """
        ...
