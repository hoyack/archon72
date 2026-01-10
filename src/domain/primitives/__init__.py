"""Constitutional primitives for the Archon 72 domain layer.

This module provides foundational primitives that enforce constitutional
constraints at the domain level:

- DeletePreventionMixin: Prevents deletion of constitutional entities (FR80)
- AtomicOperationContext: Ensures atomic operations with rollback (FR81)

These primitives are used by Epic 1 (Event Store) and subsequent epics
to build constitutional features on a solid foundation.
"""

from src.domain.primitives.ensure_atomicity import AtomicOperationContext
from src.domain.primitives.prevent_delete import DeletePreventionMixin
from src.domain.primitives.constitutional_thresholds import (
    ATTESTATION_PERIOD_THRESHOLD,
    CESSATION_BREACH_THRESHOLD,
    CESSATION_WINDOW_DAYS_THRESHOLD,
    CONSTITUTIONAL_THRESHOLD_REGISTRY,
    ESCALATION_DAYS_THRESHOLD,
    FORK_SIGNAL_RATE_LIMIT_THRESHOLD,
    HALT_CONFIRMATION_SECONDS_THRESHOLD,
    MINIMUM_KEEPER_QUORUM_THRESHOLD,
    MISSED_ATTESTATIONS_THRESHOLD_DEF,
    OVERRIDE_GOVERNANCE_365_DAY_THRESHOLD,
    OVERRIDE_WARNING_30_DAY_THRESHOLD,
    RECOVERY_WAITING_HOURS_THRESHOLD,
    THRESHOLD_NAMES,
    TOPIC_DIVERSITY_THRESHOLD_DEF,
    WITNESS_POOL_MINIMUM_THRESHOLD,
    get_threshold,
    validate_all_thresholds,
)
from src.domain.primitives.integrity_guarantees import (
    ALL_GUARANTEES,
    GUARANTEE_IDS,
    INTEGRITY_GUARANTEE_REGISTRY,
    get_guarantee,
    validate_all_guarantees,
)

__all__: list[str] = [
    "DeletePreventionMixin",
    "AtomicOperationContext",
    "ATTESTATION_PERIOD_THRESHOLD",
    "CESSATION_BREACH_THRESHOLD",
    "CESSATION_WINDOW_DAYS_THRESHOLD",
    "CONSTITUTIONAL_THRESHOLD_REGISTRY",
    "ESCALATION_DAYS_THRESHOLD",
    "FORK_SIGNAL_RATE_LIMIT_THRESHOLD",
    "HALT_CONFIRMATION_SECONDS_THRESHOLD",
    "MINIMUM_KEEPER_QUORUM_THRESHOLD",
    "MISSED_ATTESTATIONS_THRESHOLD_DEF",
    "OVERRIDE_GOVERNANCE_365_DAY_THRESHOLD",
    "OVERRIDE_WARNING_30_DAY_THRESHOLD",
    "RECOVERY_WAITING_HOURS_THRESHOLD",
    "THRESHOLD_NAMES",
    "TOPIC_DIVERSITY_THRESHOLD_DEF",
    "WITNESS_POOL_MINIMUM_THRESHOLD",
    "get_threshold",
    "validate_all_thresholds",
    # Integrity Guarantee Registry (Story 7.10, FR144)
    "ALL_GUARANTEES",
    "GUARANTEE_IDS",
    "INTEGRITY_GUARANTEE_REGISTRY",
    "get_guarantee",
    "validate_all_guarantees",
]
