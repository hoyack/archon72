"""Infrastructure adapters for Archon 72.

Adapters implement the ports defined in the application layer,
providing concrete implementations for external services.

Available adapters:
- CessationPetitionAdapter: Story 7.2 migration adapter (Story 0.3, FR-9.1)
- PostgresJobScheduler: Job queue for deadline monitoring (Story 0.4, AC4)
"""

from src.infrastructure.adapters.job_queue import PostgresJobScheduler
from src.infrastructure.adapters.petition_migration import (
    CESSATION_REALM,
    PETITION_DUAL_WRITE_ENABLED_DEFAULT,
    STATE_TO_STATUS_MAP,
    STATUS_TO_STATE_MAP,
    CessationPetitionAdapter,
    DualWritePetitionRepository,
    is_dual_write_enabled,
)

__all__: list[str] = [
    # Petition migration (Story 0.3, FR-9.1)
    "CessationPetitionAdapter",
    "CESSATION_REALM",
    "STATUS_TO_STATE_MAP",
    "STATE_TO_STATUS_MAP",
    # Dual-write repository (Story 0.3, AC2, FR-9.3)
    "DualWritePetitionRepository",
    "PETITION_DUAL_WRITE_ENABLED_DEFAULT",
    "is_dual_write_enabled",
    # Job Scheduler (Story 0.4, AC4, HP-1, HC-6)
    "PostgresJobScheduler",
]
