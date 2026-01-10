"""Configuration health response models (Story 6.10, NFR39, AC6).

Pydantic models for configuration health endpoint responses.

Constitutional Constraints:
- NFR39: No configuration SHALL allow thresholds below constitutional floors
"""

from pydantic import BaseModel


class ThresholdStatusResponse(BaseModel):
    """Status of a single constitutional threshold.

    Attributes:
        threshold_name: Name of the threshold.
        floor_value: Constitutional floor (minimum value).
        current_value: Currently configured value.
        is_valid: True if current_value >= floor_value.
    """

    threshold_name: str
    floor_value: float | int
    current_value: float | int
    is_valid: bool


class ConfigurationHealthResponse(BaseModel):
    """Health status of all configuration floors.

    Attributes:
        is_healthy: True if all thresholds are valid.
        threshold_statuses: Status of each threshold.
        checked_at: ISO timestamp of health check.
    """

    is_healthy: bool
    threshold_statuses: list[ThresholdStatusResponse]
    checked_at: str
