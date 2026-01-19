"""Configuration module for Archon72.

This module provides centralized configuration for various system components.

Available Configurations:
- PetitionQueueConfig: Queue overflow protection (Story 1.3, FR-1.4)
"""

from src.config.petition_config import (
    DEFAULT_PETITION_QUEUE_CONFIG,
    HIGH_CAPACITY_PETITION_QUEUE_CONFIG,
    TEST_PETITION_QUEUE_CONFIG,
    PetitionQueueConfig,
)

__all__ = [
    "PetitionQueueConfig",
    "DEFAULT_PETITION_QUEUE_CONFIG",
    "TEST_PETITION_QUEUE_CONFIG",
    "HIGH_CAPACITY_PETITION_QUEUE_CONFIG",
]
