"""Observer API rate limiter (Story 4.1, Task 2).

Rate limiting middleware that applies identical limits regardless
of authentication status.

Constitutional Constraint:
- FR48: Rate limits MUST be identical for anonymous and authenticated users
- No preferential treatment for registered users
- Equal access is a transparency guarantee
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request


class ObserverRateLimiter:
    """Rate limiter for observer API.

    Per FR48: Rate limits MUST be identical for anonymous
    and authenticated users. No preferential treatment.

    This limiter uses IP-based identification, NOT auth status.
    An authenticated user from IP X gets the same limits as
    an anonymous user from IP X.

    Constitutional Constraint:
    - Equal access is a transparency guarantee
    - Different limits would create gatekeeping
    """

    # Same limits for ALL users - constitutional requirement (FR48)
    REQUESTS_PER_MINUTE: int = 60
    BURST_LIMIT: int = 100
    WINDOW_SECONDS: int = 60

    def __init__(self) -> None:
        """Initialize rate limiter with in-memory storage.

        Note: In production, this should use Redis for distributed rate limiting.
        This implementation is suitable for single-instance deployments and testing.
        """
        # Maps client_key -> list of request timestamps
        self._request_timestamps: dict[str, list[datetime]] = {}

    def _get_client_key(self, request: Request) -> str:
        """Get client identifier - IP-based, not auth-based.

        Per FR48: We identify by IP, not by auth status.
        This ensures anonymous and authenticated get same treatment.

        Args:
            request: The FastAPI request object.

        Returns:
            Client identifier string based on IP address.
        """
        # Check X-Forwarded-For header for proxied requests
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Use first IP in the chain (original client)
            return forwarded.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client and request.client.host:
            return request.client.host

        return "unknown"

    def _cleanup_old_requests(self, client_key: str, now: datetime) -> None:
        """Remove request timestamps outside the current window.

        Args:
            client_key: The client identifier.
            now: Current timestamp.
        """
        if client_key not in self._request_timestamps:
            return

        window_start = now - timedelta(seconds=self.WINDOW_SECONDS)
        self._request_timestamps[client_key] = [
            ts
            for ts in self._request_timestamps[client_key]
            if ts > window_start
        ]

    async def check_rate_limit(self, request: Request) -> None:
        """Check and enforce rate limit.

        Per FR48: This check is IDENTICAL for all users regardless
        of authentication status.

        Args:
            request: The FastAPI request object.

        Raises:
            HTTPException: 429 if rate limit exceeded.
        """
        client_key = self._get_client_key(request)
        now = datetime.now(timezone.utc)

        # Clean up old requests
        self._cleanup_old_requests(client_key, now)

        # Initialize if needed
        if client_key not in self._request_timestamps:
            self._request_timestamps[client_key] = []

        # Check if rate limit exceeded
        request_count = len(self._request_timestamps[client_key])
        if request_count >= self.REQUESTS_PER_MINUTE:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before making more requests.",
                headers={
                    "Retry-After": str(self.WINDOW_SECONDS),
                    "X-RateLimit-Limit": str(self.REQUESTS_PER_MINUTE),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Record this request
        self._request_timestamps[client_key].append(now)

    def get_rate_limit_info(self, request: Request) -> dict[str, Any]:
        """Get current rate limit info for a client.

        Useful for adding rate limit headers to responses.

        Args:
            request: The FastAPI request object.

        Returns:
            Dict with limit, remaining, and reset info.
        """
        client_key = self._get_client_key(request)
        now = datetime.now(timezone.utc)

        # Clean up old requests
        self._cleanup_old_requests(client_key, now)

        # Get current count
        request_count = len(self._request_timestamps.get(client_key, []))
        remaining = max(0, self.REQUESTS_PER_MINUTE - request_count)

        # Calculate reset time
        window_start = now - timedelta(seconds=self.WINDOW_SECONDS)
        if client_key in self._request_timestamps and self._request_timestamps[client_key]:
            oldest_in_window = min(self._request_timestamps[client_key])
            reset_at = oldest_in_window + timedelta(seconds=self.WINDOW_SECONDS)
        else:
            reset_at = now + timedelta(seconds=self.WINDOW_SECONDS)

        return {
            "limit": self.REQUESTS_PER_MINUTE,
            "remaining": remaining,
            "reset": reset_at.isoformat(),
        }

    def reset_for_client(self, request: Request) -> None:
        """Reset rate limit for a specific client.

        Used primarily for testing.

        Args:
            request: The FastAPI request object.
        """
        client_key = self._get_client_key(request)
        if client_key in self._request_timestamps:
            self._request_timestamps[client_key] = []
