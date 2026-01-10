"""Infrastructure initialization modules.

This package contains initialization logic for system setup,
including constitutional waiver documentation.

Available modules:
- ct15_waiver: CT-15 waiver initialization for MVP scope (Story 9.8, SC-4, SR-10)
"""

from src.infrastructure.initialization.ct15_waiver import (
    CT15_RATIONALE,
    CT15_STATEMENT,
    CT15_TARGET_PHASE,
    CT15_WAIVED_DESCRIPTION,
    CT15_WAIVER_ID,
    initialize_ct15_waiver,
)

__all__: list[str] = [
    "CT15_WAIVER_ID",
    "CT15_STATEMENT",
    "CT15_WAIVED_DESCRIPTION",
    "CT15_RATIONALE",
    "CT15_TARGET_PHASE",
    "initialize_ct15_waiver",
]
