"""Audit repository port (Story 9.3, FR57).

Abstract interface for quarterly audit storage operations.
Tracks audit history, status, and results per FR57.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from typing import Protocol

from src.domain.models.material_audit import (
    AuditQuarter,
    MaterialAudit,
)


class AuditRepositoryProtocol(Protocol):
    """Repository protocol for quarterly audits (FR57).

    Provides storage and retrieval for quarterly audit records.
    Tracks audit history, current status, and determines when
    the next audit is due.

    Constitutional Constraints:
    - FR57: Audit history must be maintained
    - CT-11: Operations should respect halt state
    """

    async def save_audit(self, audit: MaterialAudit) -> None:
        """Save or update an audit record.

        Args:
            audit: The audit record to save.

        Note:
            If an audit with the same audit_id exists, it will
            be updated. This allows tracking status transitions.
        """
        ...

    async def get_audit(self, audit_id: str) -> MaterialAudit | None:
        """Get a specific audit by ID.

        Args:
            audit_id: The ID of the audit to retrieve.

        Returns:
            The audit if found, None otherwise.
        """
        ...

    async def get_latest_audit(self) -> MaterialAudit | None:
        """Get the most recent completed audit.

        Returns:
            The most recently completed audit, or None if no
            audits have been completed.
        """
        ...

    async def get_audit_by_quarter(
        self, quarter: AuditQuarter
    ) -> MaterialAudit | None:
        """Get the audit for a specific quarter.

        Args:
            quarter: The quarter to look up.

        Returns:
            The audit for that quarter if exists, None otherwise.
        """
        ...

    async def get_audit_history(
        self, limit: int = 10
    ) -> list[MaterialAudit]:
        """Get recent audit history.

        Args:
            limit: Maximum number of audits to return.

        Returns:
            List of audits ordered by most recent first.
        """
        ...

    async def is_audit_due(self) -> bool:
        """Check if a quarterly audit is due.

        Returns True if:
        - No audit has ever been completed
        - The current quarter has no completed audit

        Returns:
            True if an audit should be run, False otherwise.
        """
        ...

    async def get_in_progress_audit(self) -> MaterialAudit | None:
        """Get any currently running audit.

        Returns:
            The in-progress audit if one exists, None otherwise.
        """
        ...
