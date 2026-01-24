"""Status Token Service port (Story 7.1, FR-7.2).

Protocol defining the interface for status token operations for long-polling.

Constitutional Constraints:
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99
- CT-13: Read operations allowed during halt

Developer Golden Rules:
1. Protocol-based DI - all implementations through ports
2. Tokens are OPAQUE to clients
3. Version tracking enables change detection
"""

from abc import abstractmethod
from typing import Protocol
from uuid import UUID

from src.domain.models.status_token import StatusToken


class StatusTokenServiceProtocol(Protocol):
    """Protocol for status token service operations (FR-7.2).

    This service handles:
    - Token generation for petition status responses
    - Token validation for long-poll requests
    - Change detection based on state version

    Constitutional Constraints:
    - FR-7.2: System SHALL return status_token for efficient long-poll
    - NFR-1.2: Response latency < 100ms p99
    """

    @abstractmethod
    def generate_token(self, petition_id: UUID, state_version: int) -> StatusToken:
        """Generate a new status token for a petition.

        Args:
            petition_id: UUID of the petition.
            state_version: Current state version (for change detection).

        Returns:
            New StatusToken instance.
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def has_changed(self, token: StatusToken, current_version: int) -> bool:
        """Check if the state has changed since the token was issued.

        Args:
            token: The client's status token.
            current_version: Current state version from the database.

        Returns:
            True if state has changed (version differs), False otherwise.
        """
        ...

    @abstractmethod
    def compute_version(self, content_hash: bytes | None, state: str) -> int:
        """Compute a version number from content hash and state.

        This provides a deterministic version based on petition state.

        Args:
            content_hash: Blake3 hash of petition content (or None).
            state: Current petition state string.

        Returns:
            Integer version number.
        """
        ...
