"""Logging middleware for correlation ID propagation (Story 8.7, AC2).

This middleware handles correlation ID management for HTTP requests:
- Extracts correlation ID from incoming X-Correlation-ID header
- Generates new correlation ID if not present
- Sets correlation ID in context for downstream use
- Includes correlation ID in response headers
- Logs request start/end with timing

Constitutional Constraints:
- NFR27: Operational monitoring with distributed tracing
- AC2: Correlation ID consistency across all services

Usage:
    from fastapi import FastAPI
    from src.api.middleware.logging_middleware import LoggingMiddleware

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
"""

import time
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.observability.correlation import (
    generate_correlation_id,
    set_correlation_id,
)

# Header name for correlation ID
CORRELATION_HEADER = "X-Correlation-ID"


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for correlation ID propagation and request logging.

    This middleware:
    1. Extracts or generates correlation ID from X-Correlation-ID header
    2. Sets correlation ID in context for the request scope
    3. Logs request start with method, path, correlation_id
    4. Logs request completion with status code and duration
    5. Adds correlation ID to response headers

    All downstream services and loggers can access the correlation ID
    via get_correlation_id() from the observability module.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request with correlation ID and logging.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            HTTP response with correlation ID header added.
        """
        # Extract or generate correlation ID
        correlation_id = request.headers.get(CORRELATION_HEADER) or generate_correlation_id()

        # Set in context for downstream use
        set_correlation_id(correlation_id)

        # Create bound logger with request context
        log = structlog.get_logger().bind(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )

        # Log request start
        log.info("request_started")

        # Time the request
        start_time = time.perf_counter()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log request completion
            log.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add correlation ID to response headers
            response.headers[CORRELATION_HEADER] = correlation_id

            return response

        except Exception as exc:
            # Calculate duration even on error
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log request failure
            log.exception(
                "request_failed",
                duration_ms=round(duration_ms, 2),
                error_type=type(exc).__name__,
            )

            # Re-raise to let error handlers deal with it
            raise
