"""Panel Finding Port - Append-only interface for finding preservation.

Story: consent-gov-6-5: Panel Finding Preservation

This port defines the interface for preserving panel findings in an
append-only ledger. The port enforces immutability by design - there
are NO update or delete methods.

Constitutional Constraints (NFR-CONST-06, FR40):
- Record is the ONLY write operation
- NO update methods - findings are immutable once recorded
- NO delete methods - findings are permanent
- The absence of mutation methods is INTENTIONAL, not an oversight

Why Immutable Findings?
----------------------
Judicial outcomes must be permanent because:
  - Accountability requires permanence
  - Historical record must be complete
  - Appeal requires original finding
  - Trust requires no revisions

If findings could be changed:
  - Panel could "clean up" unpopular decisions
  - Accountability could be erased
  - Historical analysis impossible
  - Trust in process destroyed

References:
    - FR40: System can record all panel findings in append-only ledger
    - NFR-CONST-06: Panel findings cannot be deleted or modified
    - FR39: Prince Panel can record dissent in finding
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.panel.panel_finding import PanelFinding
from src.domain.governance.panel.determination import Determination
from src.domain.governance.panel.finding_record import FindingRecord


@runtime_checkable
class PanelFindingPort(Protocol):
    """Append-only port for panel finding preservation.

    This protocol defines the contract for preserving panel findings
    in a permanent, append-only store. Findings cannot be modified
    or deleted after recording (NFR-CONST-06).

    ┌────────────────────────────────────────────────────────────────────┐
    │                    CONSTITUTIONAL CONSTRAINTS                       │
    │                                                                      │
    │  ⚠️  NO update methods - findings are immutable once recorded       │
    │  ⚠️  NO delete methods - findings are permanent and auditable       │
    │  ⚠️  Record is the ONLY write operation allowed                     │
    │                                                                      │
    │  This interface deliberately omits mutation methods.                 │
    │  The absence is INTENTIONAL, not an oversight.                      │
    │                                                                      │
    │  Ref: NFR-CONST-06, FR40, governance-architecture.md               │
    └────────────────────────────────────────────────────────────────────┘

    Implementation Notes:
    - Adapters must use append-only storage patterns
    - Dissent is stored as part of the finding, not separately
    - Voting record is preserved with the finding
    - All operations are async for I/O efficiency

    Intentionally NOT defined (NFR-CONST-06):
    - delete_finding()
    - modify_finding()
    - update_finding()
    - remove_finding()
    """

    # =========================================================================
    # Record Operation (ONLY write method)
    # =========================================================================

    async def record_finding(
        self,
        finding: PanelFinding,
    ) -> FindingRecord:
        """Record a finding to the append-only ledger.

        This is the ONLY write operation. Findings cannot be updated
        or deleted after being recorded (NFR-CONST-06).

        The ledger assigns:
        - A ledger position for ordering
        - An integrity hash for verification
        - A recorded_at timestamp

        Dissent, if present, is recorded as part of the finding
        and cannot be suppressed (FR39).

        Args:
            finding: The PanelFinding to preserve. Must include all
                     data: determination, remedy, dissent, voting record.

        Returns:
            FindingRecord with ledger metadata.

        Raises:
            FindingStorageError: If the record operation fails.

        Constitutional Reference:
            - NFR-CONST-06: Append-only enforcement
            - FR40: Record findings in append-only ledger
            - FR39: Preserve dissent with finding
        """
        ...

    # =========================================================================
    # Query by ID
    # =========================================================================

    async def get_finding(
        self,
        finding_id: UUID,
    ) -> Optional[FindingRecord]:
        """Get a finding by its finding ID.

        Args:
            finding_id: UUID of the finding to retrieve.

        Returns:
            The FindingRecord if found, None otherwise.
        """
        ...

    async def get_finding_by_record_id(
        self,
        record_id: UUID,
    ) -> Optional[FindingRecord]:
        """Get a finding by its record ID.

        Args:
            record_id: UUID of the record to retrieve.

        Returns:
            The FindingRecord if found, None otherwise.
        """
        ...

    # =========================================================================
    # Query by Statement (AC6: Statement Linkage)
    # =========================================================================

    async def get_findings_for_statement(
        self,
        statement_id: UUID,
    ) -> List[FindingRecord]:
        """Get all findings for a witness statement.

        Provides bi-directional query from statement to findings.
        Statement linkage is immutable once recorded.

        Args:
            statement_id: UUID of the witness statement.

        Returns:
            List of findings for this statement, ordered by ledger position.
        """
        ...

    # =========================================================================
    # Query by Panel
    # =========================================================================

    async def get_findings_by_panel(
        self,
        panel_id: UUID,
    ) -> List[FindingRecord]:
        """Get all findings from a specific panel.

        Args:
            panel_id: UUID of the panel.

        Returns:
            List of findings from this panel, ordered by ledger position.
        """
        ...

    # =========================================================================
    # Query by Determination (AC7: Historical Query)
    # =========================================================================

    async def get_findings_by_determination(
        self,
        determination: Determination,
        since: Optional[datetime] = None,
    ) -> List[FindingRecord]:
        """Get findings by determination type.

        Supports historical analysis of panel decisions.

        Args:
            determination: The determination type to filter by.
            since: Optional start date for the query.

        Returns:
            List of findings with this determination, ordered by issue date.
        """
        ...

    # =========================================================================
    # Query by Date Range (AC7: Historical Query)
    # =========================================================================

    async def get_findings_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> List[FindingRecord]:
        """Get findings recorded within a date range.

        Supports historical queries for audit and analysis.

        Args:
            start: Start of the date range (inclusive).
            end: End of the date range (inclusive).

        Returns:
            List of findings in this range, ordered by recorded_at.
        """
        ...

    # =========================================================================
    # Query by Ledger Position
    # =========================================================================

    async def get_finding_by_position(
        self,
        position: int,
    ) -> Optional[FindingRecord]:
        """Get a finding by its ledger position.

        Args:
            position: The ledger position to query.

        Returns:
            The FindingRecord at this position, None if not found.
        """
        ...

    async def get_latest_finding(self) -> Optional[FindingRecord]:
        """Get the most recently recorded finding.

        Returns:
            The finding with the highest ledger position, None if empty.
        """
        ...

    async def count_findings(
        self,
        determination: Optional[Determination] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Count findings matching criteria.

        Args:
            determination: Optional filter by determination type.
            since: Optional filter by recorded date.

        Returns:
            Count of matching findings.
        """
        ...

    # Intentionally NOT defined (NFR-CONST-06):
    # async def delete_finding(self, finding_id: UUID) -> None: ...
    # async def modify_finding(self, finding_id: UUID, ...) -> None: ...
    # async def update_finding(self, finding_id: UUID, ...) -> None: ...
    # async def remove_finding(self, finding_id: UUID) -> None: ...
