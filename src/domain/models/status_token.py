"""Status Token domain model for long-poll efficiency (Story 7.1, FR-7.2).

Value object representing an opaque status token that encodes the current
state version for efficient long-polling of petition status changes.

Constitutional Constraints:
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99
- CT-13: Read operations allowed during halt
- D7: RFC 7807 error responses

Developer Golden Rules:
1. Token is OPAQUE to clients - only server can parse
2. Use base64url encoding for URL safety (RFC 4648 Section 5)
3. Include version to detect state changes
4. Tokens are SHORT-LIVED - encode timestamp for expiry validation
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID


class InvalidStatusTokenError(ValueError):
    """Raised when a status token is invalid or cannot be parsed."""

    def __init__(self, message: str = "Invalid status token") -> None:
        super().__init__(message)
        self.message = message


class ExpiredStatusTokenError(ValueError):
    """Raised when a status token has expired."""

    def __init__(
        self, message: str = "Status token has expired", max_age_seconds: int = 0
    ) -> None:
        super().__init__(message)
        self.message = message
        self.max_age_seconds = max_age_seconds


@dataclass(frozen=True)
class StatusToken:
    """Value object representing a status token for long-polling (FR-7.2).

    The token encodes:
    - petition_id: UUID of the petition
    - version: State version (update counter or hash)
    - created_at: Timestamp for expiry validation

    Token Format (internal):
        base64url(petition_id:version:timestamp)

    Example:
        "YWJjZDEyMzQ..." (base64url encoded, opaque to client)

    Attributes:
        petition_id: UUID of the petition this token is for.
        version: State version counter (increments on state change).
        created_at: When the token was created (UTC).
    """

    petition_id: UUID
    version: int
    created_at: datetime

    # Default token max age: 5 minutes (300 seconds)
    # Tokens older than this are considered expired for security
    DEFAULT_MAX_AGE_SECONDS = 300

    @classmethod
    def create(cls, petition_id: UUID, version: int) -> StatusToken:
        """Create a new status token for a petition.

        Args:
            petition_id: UUID of the petition.
            version: Current state version (update counter).

        Returns:
            New StatusToken instance with current timestamp.
        """
        return cls(
            petition_id=petition_id,
            version=version,
            created_at=datetime.now(timezone.utc),
        )

    def encode(self) -> str:
        """Encode the token as a base64url string.

        Returns:
            Base64url encoded token string (URL-safe).
        """
        # Format: petition_id:version:timestamp_unix
        timestamp_unix = int(self.created_at.timestamp())
        token_data = f"{self.petition_id}:{self.version}:{timestamp_unix}"
        # Use base64url encoding (RFC 4648 Section 5) - URL safe
        return base64.urlsafe_b64encode(token_data.encode("utf-8")).decode("ascii")

    @classmethod
    def decode(cls, token_string: str) -> StatusToken:
        """Decode a base64url token string back to a StatusToken.

        Args:
            token_string: Base64url encoded token string.

        Returns:
            StatusToken instance parsed from the string.

        Raises:
            InvalidStatusTokenError: If token cannot be decoded or parsed.
        """
        try:
            # Decode base64url
            token_bytes = base64.urlsafe_b64decode(token_string.encode("ascii"))
            token_data = token_bytes.decode("utf-8")

            # Parse: petition_id:version:timestamp
            parts = token_data.split(":")
            if len(parts) != 3:
                raise InvalidStatusTokenError(
                    f"Invalid token format: expected 3 parts, got {len(parts)}"
                )

            petition_id = UUID(parts[0])
            version = int(parts[1])
            timestamp_unix = int(parts[2])
            created_at = datetime.fromtimestamp(timestamp_unix, tz=timezone.utc)

            return cls(
                petition_id=petition_id,
                version=version,
                created_at=created_at,
            )

        except (ValueError, UnicodeDecodeError, base64.binascii.Error) as e:
            raise InvalidStatusTokenError(f"Failed to decode token: {e}") from e

    def validate_not_expired(
        self, max_age_seconds: int | None = None
    ) -> None:
        """Validate that the token has not expired.

        Args:
            max_age_seconds: Maximum age in seconds. Defaults to DEFAULT_MAX_AGE_SECONDS.

        Raises:
            ExpiredStatusTokenError: If token has exceeded max age.
        """
        if max_age_seconds is None:
            max_age_seconds = self.DEFAULT_MAX_AGE_SECONDS

        age_seconds = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        if age_seconds > max_age_seconds:
            raise ExpiredStatusTokenError(
                f"Token expired: age {age_seconds:.0f}s exceeds max {max_age_seconds}s",
                max_age_seconds=max_age_seconds,
            )

    def validate_petition_id(self, expected_petition_id: UUID) -> None:
        """Validate that the token's petition_id matches the expected value.

        Args:
            expected_petition_id: The petition ID from the request path.

        Raises:
            InvalidStatusTokenError: If petition IDs don't match.
        """
        if self.petition_id != expected_petition_id:
            raise InvalidStatusTokenError(
                f"Token petition_id mismatch: token={self.petition_id}, "
                f"expected={expected_petition_id}"
            )

    def has_changed(self, current_version: int) -> bool:
        """Check if the state has changed since this token was issued.

        Args:
            current_version: Current state version from the database.

        Returns:
            True if state has changed (version differs), False otherwise.
        """
        return self.version != current_version

    @staticmethod
    def compute_version_from_hash(content_hash: bytes | None, state: str) -> int:
        """Compute a version number from content hash and state.

        This provides a deterministic version based on petition state,
        useful when no explicit version counter is maintained.

        Args:
            content_hash: Blake3 hash of petition content (or None).
            state: Current petition state string.

        Returns:
            Integer version number derived from hash.
        """
        # Combine content hash (if present) with state to create version
        hash_input = state.encode("utf-8")
        if content_hash:
            hash_input = content_hash + hash_input

        # Use first 8 bytes of SHA256 as version (deterministic)
        full_hash = hashlib.sha256(hash_input).digest()
        # Convert first 8 bytes to int (big-endian)
        return int.from_bytes(full_hash[:8], byteorder="big")
