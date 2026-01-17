"""Governance ports - Abstract interfaces for consent-based governance system.

This module defines the contracts for the consent-based governance system
as specified in governance-architecture.md (Phase 3 Government PRD).

Available ports:
- GovernanceLedgerPort: Append-only ledger for governance events (Story 1-2)
- ProjectionPort: Derived state projections from ledger (Story 1-5)

Constitutional Constraints:
- NFR-CONST-01: Append-only enforcement - NO delete methods on ledger
- AD-1: Event sourcing as canonical model
- AD-8: Same DB, schema isolation (ledger.*, projections.*)
- AD-9: CQRS-Lite query pattern
- AD-11: Global monotonic sequence
"""

from src.application.ports.governance.ledger_port import (
    GovernanceLedgerPort,
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.application.ports.governance.projection_port import (
    ActorRegistryProjectionPort,
    LegitimacyStateProjectionPort,
    ProjectionApplyRecord,
    ProjectionCheckpoint,
    ProjectionPort,
    TaskStateProjectionPort,
)

__all__ = [
    # Ledger ports (Story 1-2)
    "GovernanceLedgerPort",
    "LedgerReadOptions",
    "PersistedGovernanceEvent",
    # Projection ports (Story 1-5)
    "ProjectionPort",
    "ProjectionCheckpoint",
    "ProjectionApplyRecord",
    "TaskStateProjectionPort",
    "LegitimacyStateProjectionPort",
    "ActorRegistryProjectionPort",
]
