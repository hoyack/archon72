"""External health check response models (Story 8.3, FR54).

Models for the external health check endpoint (/health/external).

This endpoint is designed for third-party monitoring services:
- No authentication required
- Minimal response for fast parsing
- Status values intentionally simple
"""

from datetime import datetime

from pydantic import BaseModel, Field

from src.application.ports.external_health import ExternalHealthStatus


class ExternalHealthResponse(BaseModel):
    """External health check response model (FR54).

    This response is designed to be:
    1. Minimal - fast to generate and parse
    2. Machine-readable - simple status enum
    3. Secure - no internal state exposed

    Attributes:
        status: Current system status (up, halted, frozen).
        timestamp: Server timestamp (UTC) for freshness verification.
    """

    status: ExternalHealthStatus = Field(
        description="System status: up (operational), halted (constitutional halt), frozen (ceased)"
    )
    timestamp: datetime = Field(
        description="Server timestamp (UTC) for freshness verification"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "up",
                    "timestamp": "2026-01-08T12:00:00.000000Z",
                },
                {
                    "status": "halted",
                    "timestamp": "2026-01-08T12:00:00.000000Z",
                },
                {
                    "status": "frozen",
                    "timestamp": "2026-01-08T12:00:00.000000Z",
                },
            ]
        }
    }
