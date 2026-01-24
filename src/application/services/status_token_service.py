"""Status Token Service implementation (Story 7.1, FR-7.2).

Service for generating, validating, and managing status tokens for long-polling.

Constitutional Constraints:
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99
- CT-13: Read operations allowed during halt

Developer Golden Rules:
1. Tokens are OPAQUE to clients
2. Version tracking enables change detection
3. Keep operations fast for p99 latency requirement
"""

from uuid import UUID

from src.application.ports.status_token_service import StatusTokenServiceProtocol
from src.domain.models.status_token import StatusToken


class StatusTokenService(StatusTokenServiceProtocol):
    """Implementation of status token service for long-polling (FR-7.2).

    This service handles:
    - Token generation for petition status responses
    - Token validation for long-poll requests
    - Change detection based on state version

    Constitutional Constraints:
    - FR-7.2: System SHALL return status_token for efficient long-poll
    - NFR-1.2: Response latency < 100ms p99
    """

    def __init__(
        self,
        default_max_age_seconds: int = StatusToken.DEFAULT_MAX_AGE_SECONDS,
    ) -> None:
        """Initialize the status token service.

        Args:
            default_max_age_seconds: Default maximum token age for validation.
        """
        self._default_max_age_seconds = default_max_age_seconds

    def generate_token(self, petition_id: UUID, state_version: int) -> StatusToken:
        """Generate a new status token for a petition.

        Args:
            petition_id: UUID of the petition.
            state_version: Current state version (for change detection).

        Returns:
            New StatusToken instance.
        """
        return StatusToken.create(petition_id=petition_id, version=state_version)

    def validate_token(
        self,
        token_string: str,
        expected_petition_id: UUID,
        max_age_seconds: int | None = None,
    ) -> StatusToken:
        """Validate a status token string and return the parsed token.

        Args:
            token_string: Base64url encoded token from client.
            expected_petition_id: The petition ID from the request path.
            max_age_seconds: Maximum token age in seconds (optional).

        Returns:
            Validated and parsed StatusToken.

        Raises:
            InvalidStatusTokenError: If token is malformed or petition ID mismatch.
            ExpiredStatusTokenError: If token has exceeded max age.
        """
        # Decode the token (raises InvalidStatusTokenError if malformed)
        token = StatusToken.decode(token_string)

        # Validate petition ID matches (raises InvalidStatusTokenError on mismatch)
        token.validate_petition_id(expected_petition_id)

        # Validate not expired (raises ExpiredStatusTokenError if expired)
        effective_max_age = (
            max_age_seconds
            if max_age_seconds is not None
            else self._default_max_age_seconds
        )
        token.validate_not_expired(max_age_seconds=effective_max_age)

        return token

    def has_changed(self, token: StatusToken, current_version: int) -> bool:
        """Check if the state has changed since the token was issued.

        Args:
            token: The client's status token.
            current_version: Current state version from the database.

        Returns:
            True if state has changed (version differs), False otherwise.
        """
        return token.has_changed(current_version)

    def compute_version(self, content_hash: bytes | None, state: str) -> int:
        """Compute a version number from content hash and state.

        This provides a deterministic version based on petition state.

        Args:
            content_hash: Blake3 hash of petition content (or None).
            state: Current petition state string.

        Returns:
            Integer version number.
        """
        return StatusToken.compute_version_from_hash(content_hash, state)
