"""Governance adapters for consent-based governance system.

This package contains adapters for the consent-based governance system
as specified in governance-architecture.md (Phase 3 Government PRD).

Available adapters:
- PostgresGovernanceLedgerAdapter: Append-only ledger (Story 1-2)
- ValidatedGovernanceLedgerAdapter: Ledger with write-time validation (Story 1-4)
- PostgresProjectionAdapter: Derived state projections (Story 1-5)

Constitutional Constraints:
- NFR-CONST-01: Append-only enforcement - NO delete methods on ledger
- AD-1: Event sourcing as canonical model
- AD-8: Same DB, schema isolation (ledger.*, projections.*)
- AD-9: CQRS-Lite query pattern
- AD-12: Write-time prevention
"""

from src.infrastructure.adapters.governance.postgres_ledger_adapter import (
    PostgresGovernanceLedgerAdapter,
)
from src.infrastructure.adapters.governance.postgres_projection_adapter import (
    KNOWN_PROJECTIONS,
    PostgresProjectionAdapter,
)
from src.infrastructure.adapters.governance.validated_ledger_adapter import (
    ValidatedGovernanceLedgerAdapter,
)

__all__ = [
    "PostgresGovernanceLedgerAdapter",
    "ValidatedGovernanceLedgerAdapter",
    "PostgresProjectionAdapter",
    "KNOWN_PROJECTIONS",
]
