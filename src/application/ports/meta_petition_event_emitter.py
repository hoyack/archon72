"""META petition event emitter port (Story 8.5, CT-12).

This module defines the protocol for META petition event emission,
enabling witnessing of META petition lifecycle events.

Constitutional Constraints:
- CT-12: Witnessing creates accountability -> Events witnessed via emitter
- CT-11: Silent failure destroys legitimacy -> All emissions logged
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.domain.events.meta_petition import (
        MetaPetitionReceivedEventPayload,
        MetaPetitionResolvedEventPayload,
    )


class MetaPetitionEventEmitterProtocol(Protocol):
    """Protocol for META petition event emission (CT-12).

    Implementations emit events for witnessing. Events are used for:
    1. Audit trail of META petition handling
    2. Prometheus metrics collection
    3. Structured logging

    Methods:
        emit_meta_petition_received: Emit when META petition is routed
        emit_meta_petition_resolved: Emit when High Archon resolves
    """

    async def emit_meta_petition_received(
        self,
        event: MetaPetitionReceivedEventPayload,
    ) -> None:
        """Emit MetaPetitionReceived event.

        Called when a META petition is routed to High Archon queue.

        Args:
            event: The event payload to emit.
        """
        ...

    async def emit_meta_petition_resolved(
        self,
        event: MetaPetitionResolvedEventPayload,
    ) -> None:
        """Emit MetaPetitionResolved event.

        Called when High Archon resolves a META petition.

        Args:
            event: The event payload to emit.
        """
        ...
