"""Observer API adapter (Story 4.1, Task 4; Story 4.2, Task 2).

Adapter to transform domain Event to API response.

Constitutional Constraints:
- FR44: ALL event data must be exposed to observers
- FR45: Raw events with hashes for verification
- No fields hidden or transformed
"""

from types import MappingProxyType
from typing import Any

from src.api.models.observer import ObserverEventResponse
from src.domain.events import Event


def _format_sig_alg_version(version: int) -> str:
    """Convert numeric sig_alg_version to human-readable string name.

    Version mapping (per architecture.md):
    - 1: Ed25519

    Args:
        version: Numeric signature algorithm version from domain Event.

    Returns:
        Human-readable algorithm name string.
    """
    if version == 1:
        return "Ed25519"
    return f"Unknown({version})"


class EventToObserverAdapter:
    """Adapts domain Event to observer API response.

    Per FR44: ALL event data is exposed to observers.
    No fields are hidden or transformed.

    This adapter converts the immutable domain Event entity
    to a Pydantic response model suitable for API serialization.
    """

    @staticmethod
    def to_response(event: Event) -> ObserverEventResponse:
        """Convert domain event to API response.

        Args:
            event: The domain Event entity.

        Returns:
            ObserverEventResponse suitable for API serialization.

        Note:
            The MappingProxyType payload is converted to a regular dict
            for JSON serialization.
        """
        # Convert MappingProxyType to dict if needed
        payload: dict[str, Any]
        if isinstance(event.payload, MappingProxyType):
            payload = dict(event.payload)
        else:
            payload = event.payload

        return ObserverEventResponse(
            event_id=event.event_id,
            sequence=event.sequence,
            event_type=event.event_type,
            payload=payload,
            content_hash=event.content_hash,
            prev_hash=event.prev_hash,
            signature=event.signature,
            agent_id=event.agent_id or "",
            witness_id=event.witness_id,
            witness_signature=event.witness_signature,
            local_timestamp=event.local_timestamp,
            authority_timestamp=event.authority_timestamp,
            hash_algorithm_version="SHA256",
            sig_alg_version=_format_sig_alg_version(event.sig_alg_version),
        )

    @staticmethod
    def to_response_list(events: list[Event]) -> list[ObserverEventResponse]:
        """Convert list of domain events to API responses.

        Args:
            events: List of domain Event entities.

        Returns:
            List of ObserverEventResponse objects.
        """
        return [EventToObserverAdapter.to_response(e) for e in events]
