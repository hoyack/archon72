"""Validated Governance Ledger Adapter.

Story: consent-gov-1.4: Write-Time Validation

This adapter wraps the PostgresGovernanceLedgerAdapter to add write-time
validation before events are appended to the ledger.

Design Decision:
    Validation happens BEFORE append, not inside the transaction.
    This allows:
    - Validation failures to not start a transaction
    - Validation to be cached/optimized separately
    - Clear separation of concerns

Constitutional Constraint:
    Failed validation leaves the ledger unchanged (AC8).
    The ledger is sacred - only valid events may be appended.

References:
    - AD-12: Write-time prevention
    - NFR-ATOMIC-01: Atomic operations
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.application.ports.governance.ledger_port import (
    GovernanceLedgerPort,
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.domain.governance.events.event_envelope import GovernanceEvent

if TYPE_CHECKING:
    from src.application.services.governance.ledger_validation_service import (
        LedgerValidationService,
    )


class ValidatedGovernanceLedgerAdapter(GovernanceLedgerPort):
    """Governance ledger adapter with write-time validation.

    This adapter composes a base ledger adapter with a validation service.
    It validates events BEFORE delegating to the base adapter's append.

    Pattern:
        ```python
        validated_adapter = ValidatedGovernanceLedgerAdapter(
            base_adapter=PostgresGovernanceLedgerAdapter(session_factory),
            validation_service=LedgerValidationService(...),
        )

        # This will validate first, then append if valid
        await validated_adapter.append_event(event)
        ```

    Constitutional Constraint:
        Failed validation raises WriteTimeValidationError and leaves
        the ledger completely unchanged. No partial writes occur.

    AC8 Enforcement:
        If validation fails, the base adapter's append_event is NEVER called.
        The ledger remains in its previous state.
    """

    def __init__(
        self,
        base_adapter: GovernanceLedgerPort,
        validation_service: LedgerValidationService,
    ) -> None:
        """Initialize the validated adapter.

        Args:
            base_adapter: The underlying ledger adapter for actual persistence.
            validation_service: The validation service to use for write-time checks.
        """
        self._base = base_adapter
        self._validation = validation_service

    async def append_event(
        self,
        event: GovernanceEvent,
    ) -> PersistedGovernanceEvent:
        """Validate and append a governance event to the ledger.

        Validation is performed FIRST. Only if all validations pass
        is the event appended to the ledger.

        Args:
            event: The GovernanceEvent to validate and persist.

        Returns:
            PersistedGovernanceEvent with ledger-assigned sequence.

        Raises:
            WriteTimeValidationError: If any validation fails.
                Subclasses indicate the specific failure:
                - UnknownEventTypeError
                - UnknownActorError
                - IllegalStateTransitionError
                - HashChainBreakError
            TypeError: If event is not a GovernanceEvent instance.
            ConstitutionalViolationError: If persistence fails.
        """
        # Validation first - fails fast without touching the ledger
        await self._validation.validate(event)

        # Only append if validation passed
        return await self._base.append_event(event)

    async def get_latest_event(self) -> PersistedGovernanceEvent | None:
        """Get the most recent event from the ledger.

        Delegates to base adapter.
        """
        return await self._base.get_latest_event()

    async def get_max_sequence(self) -> int:
        """Get the highest sequence number in the ledger.

        Delegates to base adapter.
        """
        return await self._base.get_max_sequence()

    async def read_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> list[PersistedGovernanceEvent]:
        """Read events from the ledger with optional filters.

        Delegates to base adapter.
        """
        return await self._base.read_events(options)

    async def get_event_by_sequence(
        self,
        sequence: int,
    ) -> PersistedGovernanceEvent | None:
        """Get a single event by its sequence number.

        Delegates to base adapter.
        """
        return await self._base.get_event_by_sequence(sequence)

    async def get_event_by_id(
        self,
        event_id: UUID,
    ) -> PersistedGovernanceEvent | None:
        """Get a single event by its event ID.

        Delegates to base adapter.
        """
        return await self._base.get_event_by_id(event_id)

    async def count_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> int:
        """Count events matching the given criteria.

        Delegates to base adapter.
        """
        return await self._base.count_events(options)
