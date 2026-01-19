"""Petition migration adapters (Story 0.3, FR-9.1, ADR-P7).

This module provides adapters for migrating Story 7.2 cessation petitions
to the new Story 0.2 petition submission schema.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → Migration must be auditable
- CT-12: Witnessing creates accountability → All changes logged
- FR-9.4: Petition ID preservation is MANDATORY

Available Adapters:
- CessationPetitionAdapter: Bidirectional conversion between Petition and PetitionSubmission
- DualWritePetitionRepository: Writes to both legacy and new schemas during migration

WARNING: These adapters are for migration use. Production code should use
the native repository implementations.
"""

from src.infrastructure.adapters.petition_migration.cessation_adapter import (
    CESSATION_REALM,
    STATE_TO_STATUS_MAP,
    STATUS_TO_STATE_MAP,
    CessationPetitionAdapter,
)
from src.infrastructure.adapters.petition_migration.dual_write_repository import (
    PETITION_DUAL_WRITE_ENABLED_DEFAULT,
    DualWritePetitionRepository,
    is_dual_write_enabled,
)

__all__: list[str] = [
    # Cessation adapter (Story 0.3, AC1)
    "CessationPetitionAdapter",
    "CESSATION_REALM",
    "STATUS_TO_STATE_MAP",
    "STATE_TO_STATUS_MAP",
    # Dual-write repository (Story 0.3, AC2)
    "DualWritePetitionRepository",
    "PETITION_DUAL_WRITE_ENABLED_DEFAULT",
    "is_dual_write_enabled",
]
