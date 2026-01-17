"""Exit port interface for consent-based governance.

Story: consent-gov-7.1: Exit Request Processing

This module defines the ExitPort protocol for exit operations,
following hexagonal architecture principles.

Design Principles:
- Port defines interface, adapters implement
- No barrier methods (no confirm, approve, reject)
- Append-only semantics for exit records
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.governance.exit.exit_request import ExitRequest
from src.domain.governance.exit.exit_result import ExitResult


class ExitPort(Protocol):
    """Port interface for exit operations.

    Per FR42: Cluster can initiate exit request.
    Per FR43: System can process exit request.

    This port defines the interface for exit-related operations.
    Adapters implement this protocol for specific storage backends.

    INTENTIONALLY NOT DEFINED (NFR-EXIT-01):
    - confirm_exit(): Confirmation violates immediate exit
    - approve_exit(): Approval violates unconditional right
    - reject_exit(): Exit cannot be rejected
    - cancel_exit(): Exit cannot be cancelled once initiated
    - delay_exit(): Delay violates ≤2 round-trips
    """

    async def record_exit_request(
        self,
        request: ExitRequest,
    ) -> None:
        """Record an exit request.

        Stores the exit request for audit purposes.
        This is append-only - requests cannot be modified.

        Args:
            request: The exit request to record.
        """
        ...

    async def record_exit_result(
        self,
        result: ExitResult,
    ) -> None:
        """Record an exit result.

        Stores the exit result for audit purposes.
        This is append-only - results cannot be modified.

        Args:
            result: The exit result to record.
        """
        ...

    async def get_exit_request(
        self,
        request_id: UUID,
    ) -> ExitRequest | None:
        """Get an exit request by ID.

        Args:
            request_id: The unique identifier of the exit request.

        Returns:
            The exit request if found, None otherwise.
        """
        ...

    async def get_exit_result(
        self,
        request_id: UUID,
    ) -> ExitResult | None:
        """Get an exit result by request ID.

        Args:
            request_id: The unique identifier of the exit request.

        Returns:
            The exit result if found, None otherwise.
        """
        ...

    async def has_cluster_exited(
        self,
        cluster_id: UUID,
    ) -> bool:
        """Check if a Cluster has already exited.

        Args:
            cluster_id: The unique identifier of the Cluster.

        Returns:
            True if the Cluster has exited, False otherwise.
        """
        ...

    async def get_cluster_active_tasks(
        self,
        cluster_id: UUID,
    ) -> list[UUID]:
        """Get active task IDs for a Cluster.

        Returns tasks that are not in terminal states
        (completed, declined, quarantined, nullified).

        Args:
            cluster_id: The unique identifier of the Cluster.

        Returns:
            List of active task IDs.
        """
        ...

    async def get_exit_history(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[ExitResult]:
        """Get exit history for auditing.

        Args:
            since: Optional start date for filtering.
            until: Optional end date for filtering.

        Returns:
            List of exit results in the specified range.
        """
        ...

    # The following methods are INTENTIONALLY NOT DEFINED:
    #
    # async def confirm_exit(...): ...
    #   - Would add confirmation barrier (NFR-EXIT-01 violation)
    #
    # async def approve_exit(...): ...
    #   - Would require approval (Golden Rule violation)
    #
    # async def reject_exit(...): ...
    #   - Exit cannot be rejected (unconditional right)
    #
    # async def cancel_exit(...): ...
    #   - Exit cannot be cancelled once initiated
    #
    # async def delay_exit(...): ...
    #   - Would add waiting period (NFR-EXIT-01 violation)
    #
    # async def require_reason(...): ...
    #   - Would require justification (Golden Rule violation)
