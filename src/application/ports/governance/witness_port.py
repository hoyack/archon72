"""Witness port interface for Knight witness operations.

Story: consent-gov-6-1: Knight Witness Domain Model

This module defines the port interface for witness statement operations.
The interface is intentionally designed to PREVENT suppression:
- No delete_statement() method exists
- No modify_statement() method exists
- Only append-only record_statement() is available

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All statements attributable
- NFR-CONST-07: Statements cannot be suppressed by any role

Suppression Prevention by Design:
---------------------------------
This port interface is the CONTRACT between the application layer and
any adapter implementation. By NOT defining delete or modify methods,
we ensure that NO adapter can implement suppression capabilities.

This is a "pit of success" design - the right behavior is the only
behavior possible.

References:
    - FR33: Knight can observe all branch actions
    - FR34: Witness statements are observation only, no judgment
    - NFR-CONST-07: Witness statements cannot be suppressed by any role
    - AC4: Statements cannot be suppressed by any role
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement


@runtime_checkable
class WitnessPort(Protocol):
    """Port for witness statement operations.

    This interface defines the contract for witness statement persistence.
    It is intentionally designed to PREVENT suppression.

    Available operations (read + append):
        - record_statement: Append a new statement (write-once)
        - get_statements_for_event: Retrieve statements by event ID
        - get_statements_by_type: Retrieve statements by observation type
        - get_statement_chain: Retrieve statements by chain position

    Intentionally NOT defined (suppression prevention):
        - delete_statement: Suppression not allowed (NFR-CONST-07)
        - modify_statement: Immutability enforced
        - update_statement: Immutability enforced
        - remove_statement: Suppression not allowed

    Any adapter implementing this port MUST NOT add these methods.
    The port interface is the enforcement mechanism.

    Example:
        >>> class PostgresWitnessAdapter:
        ...     async def record_statement(self, statement: WitnessStatement) -> None:
        ...         # Insert into append-only table
        ...         await self._db.execute(
        ...             "INSERT INTO witness_statements (...) VALUES (...)"
        ...         )
        ...
        ...     # Note: NO delete_statement method - not in the interface
    """

    async def record_statement(
        self,
        statement: WitnessStatement,
    ) -> None:
        """Record witness statement to append-only ledger.

        Once recorded, statement cannot be deleted or modified.
        This is the ONLY write operation available.

        Args:
            statement: The witness statement to record.

        Raises:
            Any persistence-related exceptions from the adapter.
        """
        ...

    async def get_statements_for_event(
        self,
        event_id: UUID,
    ) -> list[WitnessStatement]:
        """Get all witness statements for an event.

        Args:
            event_id: The ID of the event to get statements for.

        Returns:
            List of witness statements for this event.
        """
        ...

    async def get_statements_by_type(
        self,
        observation_type: ObservationType,
        since: datetime | None = None,
    ) -> list[WitnessStatement]:
        """Get statements by observation type.

        Args:
            observation_type: The type of observation to filter by.
            since: Optional timestamp to filter statements after.

        Returns:
            List of witness statements matching the criteria.
        """
        ...

    async def get_statement_chain(
        self,
        start_position: int,
        end_position: int,
    ) -> list[WitnessStatement]:
        """Get statements by chain position for gap detection.

        Used by Knight to detect missing statements in the chain.
        If statements 41 and 43 exist but 42 is missing, this
        allows detection of the gap.

        Args:
            start_position: Start of the position range (inclusive).
            end_position: End of the position range (inclusive).

        Returns:
            List of witness statements in the position range.
            Gaps in the sequence indicate potential suppression.
        """
        ...

    # =========================================================================
    # Explicitly NOT defined - these methods DO NOT EXIST:
    # =========================================================================
    #
    # - delete_statement(statement_id: UUID) -> None
    #   Suppression not allowed (NFR-CONST-07)
    #
    # - modify_statement(statement_id: UUID, ...) -> WitnessStatement
    #   Immutability enforced
    #
    # - update_statement(statement_id: UUID, ...) -> WitnessStatement
    #   Immutability enforced
    #
    # - remove_statement(statement_id: UUID) -> None
    #   Suppression not allowed
    #
    # Any adapter that adds these methods is VIOLATING the contract.
    # =========================================================================
