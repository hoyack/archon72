"""Unit tests for ObserverRateLimiter (Story 4.1, Task 2).

Tests for rate limiting middleware that applies identical limits
regardless of authentication status.

Constitutional Constraint:
- FR48: Rate limits identical for anonymous and authenticated users
- No preferential treatment for registered users
"""

from unittest.mock import MagicMock

import pytest


class TestObserverRateLimiter:
    """Tests for ObserverRateLimiter class."""

    def test_rate_limiter_class_exists(self) -> None:
        """Test that ObserverRateLimiter class exists."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()
        assert limiter is not None

    def test_rate_limiter_has_config_constants(self) -> None:
        """Test that rate limiter has required configuration constants."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        # Per FR48: These limits apply identically to ALL users
        assert hasattr(ObserverRateLimiter, "REQUESTS_PER_MINUTE")
        assert hasattr(ObserverRateLimiter, "BURST_LIMIT")
        assert ObserverRateLimiter.REQUESTS_PER_MINUTE > 0
        assert ObserverRateLimiter.BURST_LIMIT > 0

    @pytest.mark.asyncio
    async def test_rate_limiter_applies_to_anonymous(self) -> None:
        """Test rate limiter applies to anonymous requests."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()

        # Create mock request without auth header
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        # First request should succeed
        await limiter.check_rate_limit(request)

    @pytest.mark.asyncio
    async def test_rate_limiter_applies_to_authenticated(self) -> None:
        """Test rate limiter applies equally to authenticated requests."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()

        # Create mock request WITH auth header (authenticated user)
        request = MagicMock()
        request.headers = {"Authorization": "Bearer test-token"}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        # First request should succeed
        await limiter.check_rate_limit(request)

    @pytest.mark.asyncio
    async def test_rate_limits_identical_anonymous_authenticated(self) -> None:
        """Test that rate limits are identical for anonymous and authenticated.

        Per FR48: NO preferential treatment for registered users.
        Both get the same limits based on IP address, not auth status.
        """
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()

        # Anonymous request
        anon_request = MagicMock()
        anon_request.headers = {}
        anon_request.client = MagicMock()
        anon_request.client.host = "192.168.1.100"

        # Authenticated request from SAME IP
        auth_request = MagicMock()
        auth_request.headers = {"Authorization": "Bearer test-token"}
        auth_request.client = MagicMock()
        auth_request.client.host = "192.168.1.100"  # Same IP!

        # Both should use the same rate limit bucket (IP-based)
        # The auth header should NOT give preferential treatment
        client_key_anon = limiter._get_client_key(anon_request)
        client_key_auth = limiter._get_client_key(auth_request)

        # Keys should be identical since limits are IP-based, not auth-based
        assert client_key_anon == client_key_auth

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_429(self) -> None:
        """Test that exceeding rate limit raises HTTP 429."""
        from fastapi import HTTPException

        from src.api.middleware.rate_limiter import ObserverRateLimiter

        # Create limiter with very low limit for testing
        limiter = ObserverRateLimiter()
        # Override for testing
        original_limit = ObserverRateLimiter.REQUESTS_PER_MINUTE
        ObserverRateLimiter.REQUESTS_PER_MINUTE = 2

        try:
            request = MagicMock()
            request.headers = {}
            request.client = MagicMock()
            request.client.host = "192.168.1.200"

            # Make requests up to and over the limit
            await limiter.check_rate_limit(request)
            await limiter.check_rate_limit(request)

            # Third request should raise 429
            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit(request)

            assert exc_info.value.status_code == 429
            assert "rate limit" in exc_info.value.detail.lower()
        finally:
            # Restore original limit
            ObserverRateLimiter.REQUESTS_PER_MINUTE = original_limit

    def test_get_client_key_uses_ip(self) -> None:
        """Test that client key is based on IP address."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()

        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "10.0.0.50"

        key = limiter._get_client_key(request)
        assert "10.0.0.50" in key

    def test_get_client_key_uses_forwarded_header(self) -> None:
        """Test that X-Forwarded-For header is respected for proxied requests."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()

        request = MagicMock()
        request.headers = {"X-Forwarded-For": "203.0.113.50, 198.51.100.178"}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        key = limiter._get_client_key(request)
        # Should use first IP from X-Forwarded-For
        assert "203.0.113.50" in key

    def test_rate_limit_headers_format(self) -> None:
        """Test that rate limiter provides header info for responses."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()

        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        # Get rate limit info
        info = limiter.get_rate_limit_info(request)

        assert "limit" in info
        assert "remaining" in info
        assert "reset" in info
        assert info["limit"] == ObserverRateLimiter.REQUESTS_PER_MINUTE

    @pytest.mark.asyncio
    async def test_rate_limit_window_resets(self) -> None:
        """Test that rate limit window resets after time passes."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()

        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.150"

        # Make a request
        await limiter.check_rate_limit(request)

        # Simulate window reset by clearing internal state
        limiter.reset_for_client(request)

        # After reset, the counter should be back to 0
        info = limiter.get_rate_limit_info(request)
        assert info["remaining"] == ObserverRateLimiter.REQUESTS_PER_MINUTE

    def test_handles_missing_client(self) -> None:
        """Test graceful handling of missing client info."""
        from src.api.middleware.rate_limiter import ObserverRateLimiter

        limiter = ObserverRateLimiter()

        request = MagicMock()
        request.headers = {}
        request.client = None

        # Should not crash, use fallback
        key = limiter._get_client_key(request)
        assert key == "unknown"
