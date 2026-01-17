"""Ledger Export Port - Interface for complete ledger export.

Story: consent-gov-9.1: Ledger Export

This port defines the interface for exporting the complete governance
ledger. The interface is deliberately minimal and does NOT include
any partial export methods.

Constitutional Constraints:
- FR56: Any participant can export complete ledger
- NFR-CONST-03: Partial export is impossible
- NFR-AUDIT-05: Export format is machine-readable (JSON) and human-auditable
- NFR-INT-02: Ledger contains no PII; publicly readable by design

┌────────────────────────────────────────────────────────────────────┐
│                    CONSTITUTIONAL CONSTRAINTS                       │
│                                                                      │
│  ⚠️  NO partial export methods - export is ALWAYS complete          │
│  ⚠️  NO date range filters - all events from genesis                │
│  ⚠️  NO pagination - complete export only                           │
│  ⚠️  NO event type filters - all events included                    │
│                                                                      │
│  This interface deliberately omits filtering methods.               │
│  The absence is INTENTIONAL per NFR-CONST-03.                       │
│                                                                      │
│  Ref: NFR-CONST-03, FR56, governance-architecture.md               │
└────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.governance.audit.ledger_export import LedgerExport


@runtime_checkable
class LedgerExportPort(Protocol):
    """Port for complete ledger export operations.

    This port provides ONLY complete export functionality.
    There are no methods for partial, filtered, or paginated export.

    The export is ALWAYS:
    - Complete from genesis (event #1) to latest
    - Includes ALL events without exception
    - Preserves hash chain for verification
    - Contains no PII (UUIDs only)

    ┌────────────────────────────────────────────────────────────────┐
    │  Intentionally NOT defined (NFR-CONST-03):                     │
    │  - export_range() - no date ranges                             │
    │  - export_filtered() - no type filters                         │
    │  - export_partial() - no partial exports                       │
    │  - export_paginated() - no pagination                          │
    └────────────────────────────────────────────────────────────────┘
    """

    async def export_complete(
        self,
        requester_id: UUID,
    ) -> "LedgerExport":
        """Export the complete ledger.

        This method ALWAYS exports ALL events from genesis to latest.
        There are no parameters to limit or filter the export.

        Args:
            requester_id: UUID of the participant requesting the export.
                         Used for audit logging only.

        Returns:
            LedgerExport containing ALL events from genesis to latest.

        Raises:
            PartialExportError: If export validation fails (sequence gap detected).
            PIIDetectedError: If PII is detected in any event (bug indicator).

        Constitutional Reference:
            - FR56: Any participant can export complete ledger
            - NFR-CONST-03: Partial export is impossible
        """
        ...

    async def stream_export(
        self,
        requester_id: UUID,
        batch_size: int = 1000,
    ) -> AsyncIterator["LedgerExport"]:
        """Stream the complete ledger in batches for large exports.

        This method exports ALL events from genesis to latest,
        yielding batches for memory efficiency with large ledgers.
        Each batch is part of the complete export - NOT a partial export.

        IMPORTANT: The final yielded batch contains the complete export.
        Intermediate batches are progress indicators. Callers MUST
        consume all batches and use only the final one.

        Args:
            requester_id: UUID of the participant requesting the export.
            batch_size: Number of events per progress update.

        Yields:
            LedgerExport batches, with the final one being complete.

        Raises:
            PartialExportError: If export validation fails.
            PIIDetectedError: If PII is detected in any event.

        Note:
            This is NOT a paginated API. All events are included.
            Batches are for progress/memory management only.
        """
        ...

    async def export_to_json(
        self,
        requester_id: UUID,
        pretty_print: bool = True,
    ) -> str:
        """Export the complete ledger as a JSON string.

        Convenience method that exports and serializes to JSON in one call.

        Args:
            requester_id: UUID of the participant requesting the export.
            pretty_print: If True, format with indentation for readability.

        Returns:
            JSON string containing the complete ledger export.

        Raises:
            PartialExportError: If export validation fails.
            PIIDetectedError: If PII is detected in any event.

        Constitutional Reference:
            - NFR-AUDIT-05: Export format is machine-readable (JSON) and human-auditable
        """
        ...

    # Intentionally NOT defined (NFR-CONST-03):
    #
    # async def export_range(
    #     self,
    #     start: datetime,
    #     end: datetime,
    # ) -> LedgerExport:
    #     """NOT IMPLEMENTED - Partial export is impossible."""
    #     ...
    #
    # async def export_filtered(
    #     self,
    #     event_types: list[str],
    # ) -> LedgerExport:
    #     """NOT IMPLEMENTED - Partial export is impossible."""
    #     ...
    #
    # async def export_partial(
    #     self,
    #     start_sequence: int,
    #     end_sequence: int,
    # ) -> LedgerExport:
    #     """NOT IMPLEMENTED - Partial export is impossible."""
    #     ...


@runtime_checkable
class PIICheckerPort(Protocol):
    """Port for checking content for PII.

    Used by the export service to verify that no PII exists
    in the ledger before export.
    """

    def contains_pii(self, content: str) -> bool:
        """Check if content contains personally identifiable information.

        Args:
            content: String content to check.

        Returns:
            True if PII is detected, False otherwise.
        """
        ...

    def contains_email(self, content: str) -> bool:
        """Check if content contains email addresses.

        Args:
            content: String content to check.

        Returns:
            True if email address is detected, False otherwise.
        """
        ...

    def contains_name_pattern(self, content: str) -> bool:
        """Check if content contains name-like patterns.

        This is a heuristic check for strings that look like
        personal names (capitalized word patterns that aren't
        known technical terms).

        Args:
            content: String content to check.

        Returns:
            True if name pattern is detected, False otherwise.
        """
        ...

    def is_valid_uuid_only(self, value: str) -> bool:
        """Check if a value is a valid UUID string.

        Used to verify that attribution fields use UUIDs
        rather than personal identifiers.

        Args:
            value: String to check.

        Returns:
            True if value is a valid UUID, False otherwise.
        """
        ...
