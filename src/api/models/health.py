"""Health check response models."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model.

    Attributes:
        status: Health status string (e.g., "healthy").
    """

    status: str
