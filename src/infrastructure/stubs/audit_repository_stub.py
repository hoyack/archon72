"""Audit repository stub (Story 9.3, FR57).

In-memory stub implementation of AuditRepositoryProtocol for testing.
Provides configurable behavior for unit and integration tests.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.ports.audit_repository import AuditRepositoryProtocol
from src.domain.models.material_audit import (
    AuditQuarter,
    AuditStatus,
    MaterialAudit,
)


class AuditRepositoryStub(AuditRepositoryProtocol):
    """Stub implementation of AuditRepositoryProtocol.

    Provides in-memory storage for audits with configurable
    behavior for testing scenarios.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._audits: dict[str, MaterialAudit] = {}
        self._audit_due_override: bool | None = None

    def clear(self) -> None:
        """Clear all stored data."""
        self._audits.clear()
        self._audit_due_override = None

    def set_audit_due(self, is_due: bool) -> None:
        """Override the audit due check result.

        Args:
            is_due: Whether to report audit as due.
        """
        self._audit_due_override = is_due

    def add_audit(self, audit: MaterialAudit) -> None:
        """Add an audit directly to storage for testing.

        Args:
            audit: The audit to add.
        """
        self._audits[audit.audit_id] = audit

    async def save_audit(self, audit: MaterialAudit) -> None:
        """Save or update an audit record.

        Args:
            audit: The audit record to save.
        """
        self._audits[audit.audit_id] = audit

    async def get_audit(self, audit_id: str) -> MaterialAudit | None:
        """Get a specific audit by ID.

        Args:
            audit_id: The ID of the audit to retrieve.

        Returns:
            The audit if found, None otherwise.
        """
        return self._audits.get(audit_id)

    async def get_latest_audit(self) -> MaterialAudit | None:
        """Get the most recent completed audit.

        Returns:
            The most recently completed audit, or None if no
            audits have been completed.
        """
        completed_audits = [
            a for a in self._audits.values()
            if a.status == AuditStatus.COMPLETED
        ]
        if not completed_audits:
            return None

        # Sort by completed_at descending
        completed_audits.sort(
            key=lambda a: a.completed_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return completed_audits[0]

    async def get_audit_by_quarter(
        self, quarter: AuditQuarter
    ) -> MaterialAudit | None:
        """Get the audit for a specific quarter.

        Args:
            quarter: The quarter to look up.

        Returns:
            The audit for that quarter if exists, None otherwise.
        """
        for audit in self._audits.values():
            if audit.quarter == quarter:
                return audit
        return None

    async def get_audit_history(
        self, limit: int = 10
    ) -> list[MaterialAudit]:
        """Get recent audit history.

        Args:
            limit: Maximum number of audits to return.

        Returns:
            List of audits ordered by most recent first.
        """
        completed_audits = [
            a for a in self._audits.values()
            if a.status == AuditStatus.COMPLETED
        ]
        # Sort by completed_at descending
        completed_audits.sort(
            key=lambda a: a.completed_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return completed_audits[:limit]

    async def is_audit_due(self) -> bool:
        """Check if a quarterly audit is due.

        Returns True if:
        - Override is set to True
        - No audit has ever been completed
        - The current quarter has no completed audit

        Returns:
            True if an audit should be run, False otherwise.
        """
        # Check for override
        if self._audit_due_override is not None:
            return self._audit_due_override

        # Default logic: check if current quarter has completed audit
        current_quarter = AuditQuarter.from_datetime(datetime.now(timezone.utc))
        quarter_audit = await self.get_audit_by_quarter(current_quarter)

        if quarter_audit is None:
            return True  # No audit for current quarter

        # Audit exists, check if completed
        return quarter_audit.status != AuditStatus.COMPLETED

    async def get_in_progress_audit(self) -> MaterialAudit | None:
        """Get any currently running audit.

        Returns:
            The in-progress audit if one exists, None otherwise.
        """
        for audit in self._audits.values():
            if audit.status == AuditStatus.IN_PROGRESS:
                return audit
        return None


class ConfigurableAuditRepositoryStub(AuditRepositoryStub):
    """Extended stub with additional configuration options.

    Provides more fine-grained control for testing edge cases.
    """

    def __init__(self) -> None:
        """Initialize the configurable stub."""
        super().__init__()
        self._save_should_fail = False
        self._save_failure_message = "Simulated save failure"

    def configure_save_failure(
        self,
        should_fail: bool,
        message: str = "Simulated save failure",
    ) -> None:
        """Configure whether saves should fail.

        Args:
            should_fail: Whether to raise error on save.
            message: Error message to use.
        """
        self._save_should_fail = should_fail
        self._save_failure_message = message

    async def save_audit(self, audit: MaterialAudit) -> None:
        """Save or update an audit record.

        Args:
            audit: The audit record to save.

        Raises:
            RuntimeError: If configured to fail.
        """
        if self._save_should_fail:
            raise RuntimeError(self._save_failure_message)
        await super().save_audit(audit)
