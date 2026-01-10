"""Override Registry port interface (Story 5.2, AC2).

This port defines the interface for tracking active overrides and detecting
when they expire. The registry is used by the expiration service to
automatically revert expired overrides.

Constitutional Constraints:
- FR24: Override duration must be bounded -> Registry enables expiration
- CT-11: Silent failure destroys legitimacy -> Expirations must be logged
- CT-12: Witnessing creates accountability -> All state changes witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ExpiredOverrideInfo:
    """Information about an expired override for event creation.

    This dataclass provides all the data needed to create an
    OverrideExpiredEvent when an override's duration elapses.

    Attributes:
        override_id: The original override event ID.
        keeper_id: The Keeper who initiated the override.
        scope: What was overridden.
        expires_at: When the override was supposed to expire.
    """

    override_id: UUID
    keeper_id: str
    scope: str
    expires_at: datetime


class OverrideRegistryPort(Protocol):
    """Port for tracking active overrides and detecting expirations (AC2).

    This port enables the Override Expiration Service to:
    1. Register new overrides when they are initiated
    2. Check for overrides that have exceeded their duration
    3. Mark overrides as reverted after expiration events are written

    Constitutional Constraints:
    - FR24: Duration bounded -> Registry tracks expiration times
    - CT-11: No silent failures -> All expirations must be detected and logged

    Implementations:
    - OverrideRegistryStub: In-memory implementation for testing/dev
    - Future: Database-backed implementation for production
    """

    async def register_active_override(
        self,
        override_id: UUID,
        keeper_id: str,
        scope: str,
        expires_at: datetime,
    ) -> None:
        """Register an active override for expiration tracking.

        Called when an override is successfully initiated. The registry
        stores the override information to enable automatic expiration.

        Args:
            override_id: The override event ID.
            keeper_id: The Keeper who initiated the override.
            scope: What is being overridden.
            expires_at: When the override should expire (UTC).
        """
        ...

    async def get_expired_overrides(self) -> list[ExpiredOverrideInfo]:
        """Get all overrides that have exceeded their duration.

        Returns overrides where current_time >= expires_at and the
        override has not yet been reverted.

        Returns:
            List of expired override information for event creation.
            Empty list if no overrides have expired.
        """
        ...

    async def mark_override_reverted(self, override_id: UUID) -> None:
        """Mark an override as reverted after expiration event is written.

        Called after the OverrideExpiredEvent is successfully written
        to the event store. This prevents duplicate expiration events.

        Args:
            override_id: The override event ID that was reverted.
        """
        ...

    async def is_override_active(self, override_id: UUID) -> bool:
        """Check if an override is currently active.

        An override is active if it has been registered and has not
        been reverted (either by expiration or manual revocation).

        Args:
            override_id: The override event ID to check.

        Returns:
            True if the override is active, False otherwise.
        """
        ...
