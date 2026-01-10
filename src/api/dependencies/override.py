"""Override API dependencies (Story 5.3, FR25).

Dependency injection setup for override visibility components.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: No authentication dependencies on override routes
- FR48: Rate limits identical for anonymous and authenticated users
"""

from src.api.dependencies.observer import get_event_store
from src.application.services.public_override_service import PublicOverrideService


def get_public_override_service() -> PublicOverrideService:
    """Get public override service instance.

    Creates the service with event store dependency for reading
    override events.

    Per FR25: All overrides are publicly visible.
    Per FR44: No authentication required.

    Returns:
        PublicOverrideService instance.
    """
    return PublicOverrideService(
        event_store=get_event_store(),
    )
