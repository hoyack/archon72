"""Audit errors (Story 9.3, FR57).

Error types for quarterly material audit operations.
All errors reference FR57 for traceability.

Constitutional Constraints:
- FR57: Quarterly audits of all public materials
- CT-11: HALT CHECK FIRST on all operations
- CT-12: All audit events must be witnessed
"""

from __future__ import annotations

from src.domain.errors.constitutional import ConstitutionalViolationError


class AuditError(ConstitutionalViolationError):
    """Base error for quarterly audit operations (FR57).

    All audit-related errors inherit from this class to provide
    consistent categorization and FR57 reference.
    """

    pass


class AuditNotDueError(AuditError):
    """Raised when audit is requested but not yet due (FR57).

    Quarterly audits have a schedule. This error is raised when
    an audit is requested before the current quarter's audit is due.

    Attributes:
        last_audit_quarter: The most recent completed audit quarter.
        current_quarter: The current quarter.
    """

    def __init__(
        self,
        last_audit_quarter: str | None = None,
        current_quarter: str | None = None,
    ) -> None:
        """Initialize AuditNotDueError.

        Args:
            last_audit_quarter: The quarter of the last completed audit.
            current_quarter: The current quarter.
        """
        self.last_audit_quarter = last_audit_quarter
        self.current_quarter = current_quarter

        if last_audit_quarter and current_quarter:
            message = (
                f"FR57: Audit not due. Last audit: {last_audit_quarter}, "
                f"current quarter: {current_quarter}"
            )
        elif last_audit_quarter:
            message = f"FR57: Audit not due. Last audit was {last_audit_quarter}"
        else:
            message = "FR57: Audit not due"

        super().__init__(message)


class AuditInProgressError(AuditError):
    """Raised when audit already running (FR57).

    Only one audit can run at a time. This error is raised when
    a new audit is requested while one is already in progress.

    Attributes:
        audit_id: The ID of the audit already in progress.
    """

    def __init__(self, audit_id: str) -> None:
        """Initialize AuditInProgressError.

        Args:
            audit_id: The ID of the audit already in progress.
        """
        self.audit_id = audit_id
        super().__init__(f"FR57: Audit already in progress: {audit_id}")


class MaterialViolationError(AuditError):
    """Raised when violations found during audit (FR57, AC3).

    This error indicates that prohibited content was found in
    one or more materials during the quarterly audit. Per AC3,
    this starts the clock for Conclave response.

    Attributes:
        audit_id: The ID of the audit that found violations.
        violations_count: Number of violations detected.
        violation_ids: IDs of materials with violations.
    """

    def __init__(
        self,
        audit_id: str,
        violations_count: int,
        violation_ids: tuple[str, ...] | None = None,
    ) -> None:
        """Initialize MaterialViolationError.

        Args:
            audit_id: The ID of the audit.
            violations_count: Number of violations found.
            violation_ids: Optional tuple of material IDs with violations.
        """
        self.audit_id = audit_id
        self.violations_count = violations_count
        self.violation_ids = violation_ids or ()

        message = f"FR57: Quarterly audit {audit_id} found {violations_count} violations"
        if violation_ids:
            material_list = ", ".join(violation_ids[:5])
            if len(violation_ids) > 5:
                material_list += f" and {len(violation_ids) - 5} more"
            message += f" in materials: {material_list}"

        super().__init__(message)


class AuditNotFoundError(AuditError):
    """Raised when requested audit does not exist (FR57).

    Attributes:
        audit_id: The ID of the audit that was not found.
    """

    def __init__(self, audit_id: str) -> None:
        """Initialize AuditNotFoundError.

        Args:
            audit_id: The ID of the audit that was not found.
        """
        self.audit_id = audit_id
        super().__init__(f"FR57: Audit not found: {audit_id}")


class AuditFailedError(AuditError):
    """Raised when audit fails to complete (FR57).

    This error indicates that the audit could not complete due
    to an unexpected error during processing.

    Attributes:
        audit_id: The ID of the failed audit.
        reason: Reason for the failure.
    """

    def __init__(self, audit_id: str, reason: str) -> None:
        """Initialize AuditFailedError.

        Args:
            audit_id: The ID of the failed audit.
            reason: Description of why the audit failed.
        """
        self.audit_id = audit_id
        self.reason = reason
        super().__init__(f"FR57: Audit {audit_id} failed: {reason}")
