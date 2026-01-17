"""Audit domain errors.

Story: consent-gov-9.1: Ledger Export

Error types for audit operations that indicate constitutional
constraint violations.
"""

from __future__ import annotations


class PartialExportError(ValueError):
    """Raised when partial export is detected or attempted.

    Per NFR-CONST-03: Partial export is impossible.
    This error indicates a sequence gap or incomplete export.

    This should never happen in normal operation - partial export
    methods do not exist. This error catches internal corruption
    or validation failures.
    """

    pass


class PIIDetectedError(ValueError):
    """Raised when PII is detected in export.

    Per NFR-INT-02: Ledger contains no PII.

    This indicates a bug - PII should never be stored in the ledger
    in the first place. Finding it during export is a serious issue.
    """

    pass


class ExportValidationError(ValueError):
    """Raised when export validation fails.

    Generic error for export-related validation failures that
    don't fit other categories.
    """

    pass
