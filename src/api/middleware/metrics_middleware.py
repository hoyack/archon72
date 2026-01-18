"""Metrics middleware for request instrumentation (Story 8.1, Task 2).

FastAPI middleware that records HTTP request metrics to Prometheus.

Constitutional Constraints:
- FR52: ONLY operational metrics (latency, error rates)
- NFR27: Latency percentiles (p50, p95, p99)
"""

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.monitoring.metrics import get_metrics_collector


def _classify_error_type(status_code: int) -> str:
    """Classify HTTP error status code into error type (AC4).

    Args:
        status_code: HTTP status code.

    Returns:
        Error type classification string.
    """
    if 400 <= status_code < 500:
        if status_code == 400:
            return "bad_request"
        elif status_code == 401:
            return "unauthorized"
        elif status_code == 403:
            return "forbidden"
        elif status_code == 404:
            return "not_found"
        elif status_code == 408:
            return "timeout"
        elif status_code == 429:
            return "rate_limited"
        else:
            return "client_error"
    elif status_code >= 500:
        if status_code == 500:
            return "internal_error"
        elif status_code == 502:
            return "bad_gateway"
        elif status_code == 503:
            return "service_unavailable"
        elif status_code == 504:
            return "gateway_timeout"
        else:
            return "server_error"
    return "unknown"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to record HTTP request metrics.

    Records:
    - Request duration (histogram)
    - Total requests (counter)
    - Failed requests (counter for 4xx/5xx)

    All metrics are labeled with (AC1, AC4):
    - service: Service name
    - environment: Deployment environment
    - method: HTTP method
    - endpoint: Request path
    - status: HTTP status code
    - error_type: Classification of error (for failed requests)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request and record metrics.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            HTTP response from the route handler.
        """
        start_time = time.perf_counter()

        # Process the request
        response = await call_next(request)

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Get labels
        method = request.method
        endpoint = request.url.path
        status = str(response.status_code)

        # Get metrics collector
        collector = get_metrics_collector()

        # Record request duration
        collector.observe_request_duration(
            method=method, endpoint=endpoint, duration=duration
        )

        # Increment total requests counter
        collector.increment_requests(method=method, endpoint=endpoint, status=status)

        # Increment failed requests counter for 4xx/5xx with error_type (AC4)
        if response.status_code >= 400:
            error_type = _classify_error_type(response.status_code)
            collector.increment_failed_requests(
                method=method, endpoint=endpoint, status=status, error_type=error_type
            )

        return response
