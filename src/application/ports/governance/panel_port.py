"""Panel port interface for Prince Panel operations.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the port interface for panel persistence and operations.
This port defines the contract for adapters to implement.

Port Design Principles:
-----------------------
1. Define contract, not implementation
2. Allow multiple adapter implementations
3. Support testability via mock adapters
4. Keep interface minimal and focused

References:
    - AC2: Human Operator convenes panel
    - AC4: Panel can issue formal finding with remedy
    - FR36: Human Operator can convene panel (≥3 members)
    - FR38: Prince Panel can issue formal finding with remedy
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol
from uuid import UUID

from src.domain.governance.panel import (
    PanelFinding,
    PrincePanel,
    RecusalRequest,
    ReviewSession,
)


class PanelPort(Protocol):
    """Port interface for Prince Panel operations.

    This protocol defines the contract for panel persistence and
    operations. Adapters implement this interface to provide concrete
    storage (e.g., database, in-memory).

    Methods are organized by operation type:
    - Panel lifecycle: convene, get, list, update
    - Finding operations: record, get
    - Recusal operations: record
    - Review operations: record, get

    Example adapter implementation:
        class PostgresPanelAdapter:
            def __init__(self, connection_pool: AsyncConnectionPool):
                self._pool = connection_pool

            async def save_panel(self, panel: PrincePanel) -> None:
                async with self._pool.connection() as conn:
                    await conn.execute(...)

    Example usage with dependency injection:
        class PanelService:
            def __init__(self, panel_port: PanelPort):
                self._panels = panel_port

            async def convene_panel(self, ...) -> PrincePanel:
                panel = PrincePanel(...)
                await self._panels.save_panel(panel)
                return panel
    """

    # =========================================================================
    # Panel Lifecycle Operations
    # =========================================================================

    @abstractmethod
    async def save_panel(self, panel: PrincePanel) -> None:
        """Save or update a panel.

        Used for both creating new panels and updating existing ones
        (e.g., status changes, adding finding).

        Args:
            panel: The panel to save

        Raises:
            PanelStorageError: If save operation fails
        """
        ...

    @abstractmethod
    async def get_panel(self, panel_id: UUID) -> PrincePanel | None:
        """Get a panel by ID.

        Args:
            panel_id: UUID of the panel

        Returns:
            The panel if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_panel_by_statement(self, statement_id: UUID) -> PrincePanel | None:
        """Get the panel reviewing a specific statement.

        Args:
            statement_id: UUID of the witness statement

        Returns:
            The panel reviewing this statement, None if not found
        """
        ...

    @abstractmethod
    async def list_panels_by_status(
        self, status: str, limit: int = 100
    ) -> list[PrincePanel]:
        """List panels by status.

        Args:
            status: Panel status to filter by (e.g., "convened", "reviewing")
            limit: Maximum number of panels to return

        Returns:
            List of panels with the given status
        """
        ...

    # =========================================================================
    # Finding Operations
    # =========================================================================

    @abstractmethod
    async def save_finding(self, finding: PanelFinding) -> None:
        """Save a panel finding.

        Findings are immutable once issued. This saves the finding
        to the audit trail.

        Args:
            finding: The finding to save

        Raises:
            FindingStorageError: If save operation fails
        """
        ...

    @abstractmethod
    async def get_finding(self, finding_id: UUID) -> PanelFinding | None:
        """Get a finding by ID.

        Args:
            finding_id: UUID of the finding

        Returns:
            The finding if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_finding_by_panel(self, panel_id: UUID) -> PanelFinding | None:
        """Get the finding issued by a specific panel.

        Args:
            panel_id: UUID of the panel

        Returns:
            The finding issued by this panel, None if not yet issued
        """
        ...

    # =========================================================================
    # Recusal Operations
    # =========================================================================

    @abstractmethod
    async def save_recusal(self, recusal: RecusalRequest) -> None:
        """Save a recusal request.

        Recusals are recorded for audit purposes.

        Args:
            recusal: The recusal request to save

        Raises:
            RecusalStorageError: If save operation fails
        """
        ...

    @abstractmethod
    async def list_recusals_by_panel(self, panel_id: UUID) -> list[RecusalRequest]:
        """List all recusals for a panel.

        Args:
            panel_id: UUID of the panel

        Returns:
            List of recusal requests for this panel
        """
        ...

    # =========================================================================
    # Review Session Operations
    # =========================================================================

    @abstractmethod
    async def save_review_session(self, session: ReviewSession) -> None:
        """Save a review session.

        Review sessions track panel review of artifacts.

        Args:
            session: The review session to save

        Raises:
            SessionStorageError: If save operation fails
        """
        ...

    @abstractmethod
    async def get_review_session(self, session_id: UUID) -> ReviewSession | None:
        """Get a review session by ID.

        Args:
            session_id: UUID of the session

        Returns:
            The session if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_active_session_for_panel(
        self, panel_id: UUID
    ) -> ReviewSession | None:
        """Get the active review session for a panel.

        Args:
            panel_id: UUID of the panel

        Returns:
            The active session if one exists, None otherwise
        """
        ...
