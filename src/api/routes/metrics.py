"""Metrics endpoint for Prometheus scraping (Story 8.1, Task 3).

Exposes operational metrics in Prometheus exposition format.

Constitutional Constraints:
- FR52: ONLY operational metrics (uptime, latency, errors)
- NO constitutional metrics exposed here
"""

from fastapi import APIRouter, Response

from src.bootstrap.metrics import get_metrics_exporter

router = APIRouter(prefix="/v1", tags=["metrics"])


@router.get(
    "/metrics",
    summary="Prometheus metrics endpoint",
    description="Returns operational metrics in Prometheus exposition format for scraping.",
    response_class=Response,
    responses={
        200: {
            "description": "Metrics in Prometheus format",
            "content": {"text/plain": {}},
        }
    },
)
async def get_metrics() -> Response:
    """Get operational metrics in Prometheus format.

    Returns:
        Response with metrics in Prometheus exposition format.

    Note:
        Per FR52, this endpoint exposes ONLY operational metrics:
        - uptime_seconds
        - service_starts_total
        - http_request_duration_seconds
        - http_requests_total
        - http_requests_failed_total

        Constitutional metrics (breach_count, halt_state, etc.)
        are NOT exposed here and belong to Story 8.10.
    """
    exporter = get_metrics_exporter()
    metrics_output = exporter.generate_metrics()
    return Response(
        content=metrics_output,
        media_type=exporter.content_type,
    )
