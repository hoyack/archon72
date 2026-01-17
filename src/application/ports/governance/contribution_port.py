"""Contribution port protocol for consent-based governance.

Story: consent-gov-7.3: Contribution Preservation

Defines the ContributionPort protocol for contribution operations.
This port intentionally has NO delete methods to enforce ledger immutability.

Constitutional Truths Honored:
- FR45: Contribution history preserved on exit
- NFR-INT-02: Public data only, no PII
- Ledger immutability: No deletion or modification

Key Design Principles:
1. NO delete methods (immutability)
2. NO scrub methods (immutability)
3. NO modify methods (immutability)
4. Mark-only preservation (flag set, no data change)
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.governance.exit.contribution_record import ContributionRecord


class ContributionPort(Protocol):
    """Port for contribution operations.

    Per FR45: Contribution history preserved on exit.
    Per AC7: No scrubbing of historical events.

    STRUCTURAL ABSENCE (immutability enforcement):
        The following methods DO NOT EXIST and CANNOT be added:
        - delete_contribution()
        - remove_contribution()
        - scrub_contribution()
        - modify_contribution()

        These methods are intentionally absent. Adding them would
        violate ledger immutability principles.

    Operations provided:
    - get_for_cluster: Get all contributions for a Cluster
    - get_preserved: Get preserved contributions (for historical query)
    - mark_preserved: Mark contribution as preserved (flag only)
    - record: Record a new contribution
    """

    # ========================================================================
    # STRUCTURAL ABSENCE - The following methods DO NOT EXIST
    # ========================================================================
    #
    # These methods are INTENTIONALLY absent (immutability enforcement):
    #
    # async def delete_contribution(self, record_id: UUID) -> None:
    #     '''Would delete contribution - NO DELETION ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def remove_contribution(self, record_id: UUID) -> None:
    #     '''Would remove contribution - NO REMOVAL ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def scrub_contribution(self, record_id: UUID) -> None:
    #     '''Would scrub contribution - NO SCRUBBING ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # async def modify_contribution(self, ...) -> None:
    #     '''Would modify contribution - NO MODIFICATION ALLOWED'''
    #     # NO IMPLEMENTATION - METHOD DOES NOT EXIST
    #
    # If these methods are ever added, Knight should observe and record
    # as a CONSTITUTIONAL VIOLATION.
    # ========================================================================

    async def get_for_cluster(
        self,
        cluster_id: UUID,
    ) -> list[ContributionRecord]:
        """Get all contributions for a Cluster.

        Per FR45: Contribution history preserved on exit.
        Per AC6: Historical queries show preserved contributions.

        This returns ALL contributions regardless of preservation state.
        Works the same before and after exit.

        Args:
            cluster_id: ID of the Cluster whose contributions to retrieve.

        Returns:
            List of ContributionRecord objects for the Cluster.
        """
        ...

    async def get_preserved(
        self,
        cluster_id: UUID,
    ) -> list[ContributionRecord]:
        """Get preserved contributions for a Cluster.

        Per AC6: Historical queries show preserved contributions.
        Per AC7: No scrubbing of historical events.

        This returns only contributions that have been preserved
        (i.e., preserved_at is not None). Used for historical queries.

        Args:
            cluster_id: ID of the Cluster whose preserved contributions to retrieve.

        Returns:
            List of ContributionRecord objects with preserved_at set.
        """
        ...

    async def mark_preserved(
        self,
        record_id: UUID,
        preserved_at: datetime,
    ) -> None:
        """Mark contribution as preserved.

        Per FR45: Contribution history preserved on exit.
        Per AC2: History remains in ledger (immutable).

        This sets the preserved_at timestamp on a contribution record.
        It does NOT delete or modify the contribution data.

        Flag-only operation:
        - Sets preserved_at timestamp
        - Does NOT delete contribution
        - Does NOT modify contribution content
        - Does NOT remove from query results

        Args:
            record_id: ID of the contribution record to mark.
            preserved_at: Timestamp when preservation occurred.
        """
        ...

    async def record(
        self,
        contribution: ContributionRecord,
    ) -> None:
        """Record a new contribution.

        Per FR45: Contribution history preserved on exit.

        Adds a new contribution record to the system.
        Contributions are immutable once recorded.

        Args:
            contribution: ContributionRecord to record.
        """
        ...

    async def get_by_id(
        self,
        record_id: UUID,
    ) -> ContributionRecord | None:
        """Get a contribution by its record ID.

        Args:
            record_id: ID of the contribution record.

        Returns:
            ContributionRecord if found, None otherwise.
        """
        ...

    async def count_for_cluster(
        self,
        cluster_id: UUID,
    ) -> int:
        """Count contributions for a Cluster.

        Args:
            cluster_id: ID of the Cluster.

        Returns:
            Count of contributions for the Cluster.
        """
        ...
