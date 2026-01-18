"""Override event adapter (Story 5.3, FR25).

Adapter for converting domain events to API response models.
CRITICAL: Keeper identity is NOT anonymized per FR25.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: No authentication required
- CT-12: Witnessing creates accountability
"""

from datetime import timedelta
from typing import TYPE_CHECKING

from src.api.models.override import OverrideEventResponse

if TYPE_CHECKING:
    from src.domain.events import Event


class EventToOverrideAdapter:
    """Converts domain events to Override API response models.

    CRITICAL: This adapter does NOT anonymize Keeper identity.
    Per FR25, all override data must be publicly visible.
    """

    @staticmethod
    def to_response(event: "Event") -> OverrideEventResponse:
        """Convert Event to OverrideEventResponse.

        CRITICAL: Keeper ID is NOT anonymized per FR25.

        Args:
            event: Domain event with override payload.

        Returns:
            OverrideEventResponse with full public visibility.
        """
        payload = event.payload

        # Extract fields from payload (MappingProxyType)
        keeper_id = str(payload.get("keeper_id", ""))
        scope = str(payload.get("scope", ""))
        duration = int(payload.get("duration", 0))
        reason = str(payload.get("reason", ""))
        action_type = str(payload.get("action_type", ""))
        initiated_at = payload.get("initiated_at")

        # Parse initiated_at if it's a string (ISO format)
        if isinstance(initiated_at, str):
            from datetime import datetime

            initiated_at = datetime.fromisoformat(initiated_at.replace("Z", "+00:00"))

        # Calculate expires_at from initiated_at + duration
        expires_at = (
            initiated_at + timedelta(seconds=duration) if initiated_at else None
        )

        return OverrideEventResponse(
            override_id=event.event_id,
            keeper_id=keeper_id,  # VISIBLE - FR25 (NOT anonymized)
            scope=scope,
            duration=duration,
            reason=reason,
            action_type=action_type,
            initiated_at=initiated_at,
            expires_at=expires_at,
            event_hash=event.content_hash,
            sequence=event.sequence,
            witness_id=event.witness_id if event.witness_id else None,
        )

    @staticmethod
    def to_response_list(events: list["Event"]) -> list[OverrideEventResponse]:
        """Convert list of Events to list of OverrideEventResponses.

        Args:
            events: List of domain events.

        Returns:
            List of OverrideEventResponse models.
        """
        return [EventToOverrideAdapter.to_response(event) for event in events]
