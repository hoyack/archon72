"""Persistence adapters for infrastructure layer.

This module contains adapters for database and storage operations.

Available adapters:
- InMemoryKeyRegistry: In-memory key registry for testing
- InMemoryWitnessPool: In-memory witness pool for testing
- InMemoryHaltFlagRepository: In-memory halt flag storage for testing
- HaltFlagRepository: Abstract halt flag repository interface
- TerminalEventDetector: PostgreSQL terminal event detection (Story 7.6)
- InMemoryTerminalEventDetector: In-memory terminal detection for testing
"""

from src.infrastructure.adapters.persistence.halt_flag_repository import (
    HaltFlagRepository,
    InMemoryHaltFlagRepository,
)
from src.infrastructure.adapters.persistence.key_registry import InMemoryKeyRegistry
from src.infrastructure.adapters.persistence.terminal_event_detector import (
    InMemoryTerminalEventDetector,
    TerminalEventDetector,
)
from src.infrastructure.adapters.persistence.witness_pool import InMemoryWitnessPool

__all__: list[str] = [
    "InMemoryKeyRegistry",
    "InMemoryWitnessPool",
    "HaltFlagRepository",
    "InMemoryHaltFlagRepository",
    "TerminalEventDetector",
    "InMemoryTerminalEventDetector",
]
