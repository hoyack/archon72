"""Hash chain validator for governance events.

Story: consent-gov-1.4: Write-Time Validation

Validates that new events correctly link to the existing hash chain.
Hash chain breaks are rejected before being appended to the ledger.

Performance Target: ≤50ms (hash computation)

References:
    - AD-6: Hash chain implementation
    - NFR-CONST-02: Event integrity verification
"""

from __future__ import annotations

from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.domain.governance.errors.validation_errors import HashChainBreakError
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.hash_algorithms import (
    GENESIS_PREV_HASH,
    is_genesis_hash,
)
from src.domain.governance.events.hash_chain import verify_event_hash


class HashChainValidator:
    """Validates hash chain integrity for governance events.

    Ensures that:
    1. The event's prev_hash matches the latest event's hash
    2. The event's hash correctly computed from its content
    3. Genesis events use the well-known genesis hash

    Constitutional Constraint:
        Hash chain breaks are EXISTENTIAL threats to ledger integrity.
        Any break results in immediate rejection.

    Performance:
        - Latest event lookup: ~5ms (indexed query)
        - Hash verification: ~30ms (BLAKE3 or SHA-256)
        - Total: ≤50ms

    Attributes:
        skip_validation: If True, skip hash validation (admin replay only).
    """

    def __init__(
        self,
        ledger_port: GovernanceLedgerPort,
        *,
        skip_validation: bool = False,
    ) -> None:
        """Initialize the hash chain validator.

        Args:
            ledger_port: Port for accessing the ledger.
            skip_validation: If True, skip validation (admin replay only).
        """
        self._ledger = ledger_port
        self._skip_validation = skip_validation

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate that the event correctly links to the hash chain.

        Validates:
        1. Event has hash fields (prev_hash and hash)
        2. Event's prev_hash matches latest event's hash (or genesis)
        3. Event's hash correctly computed from content

        Args:
            event: The GovernanceEvent to validate.

        Raises:
            HashChainBreakError: If hash chain validation fails.
        """
        if self._skip_validation:
            return

        # Check that event has hash fields
        if not event.has_hash():
            raise HashChainBreakError(
                event_id=event.event_id,
                expected_prev_hash="(event should have hash computed)",
                actual_prev_hash="(no hash fields present)",
                latest_sequence=0,
            )

        # Get the latest event from ledger
        latest_persisted = await self._ledger.get_latest_event()

        # Determine expected prev_hash
        if latest_persisted is None:
            # This is the genesis event - prev_hash should be genesis hash
            expected_prev_hash = None  # Will check for genesis hash format
            latest_sequence = 0
        else:
            expected_prev_hash = latest_persisted.event.hash
            latest_sequence = latest_persisted.sequence

        # Validate prev_hash links correctly
        await self._validate_prev_hash(
            event=event,
            expected_prev_hash=expected_prev_hash,
            latest_sequence=latest_sequence,
        )

        # Validate event's own hash is correct
        await self._validate_event_hash(event, latest_sequence)

    async def _validate_prev_hash(
        self,
        event: GovernanceEvent,
        expected_prev_hash: str | None,
        latest_sequence: int,
    ) -> None:
        """Validate that prev_hash correctly links to previous event.

        Args:
            event: The event to validate.
            expected_prev_hash: Expected prev_hash (None for genesis).
            latest_sequence: Sequence of latest event for error context.

        Raises:
            HashChainBreakError: If prev_hash doesn't match.
        """
        actual_prev_hash = event.prev_hash

        if expected_prev_hash is None:
            # Genesis case - prev_hash should be genesis hash
            if not is_genesis_hash(actual_prev_hash):
                raise HashChainBreakError(
                    event_id=event.event_id,
                    expected_prev_hash=GENESIS_PREV_HASH,
                    actual_prev_hash=actual_prev_hash,
                    latest_sequence=latest_sequence,
                )
        else:
            # Non-genesis case - prev_hash should match latest event's hash
            if actual_prev_hash != expected_prev_hash:
                raise HashChainBreakError(
                    event_id=event.event_id,
                    expected_prev_hash=expected_prev_hash,
                    actual_prev_hash=actual_prev_hash,
                    latest_sequence=latest_sequence,
                )

    async def _validate_event_hash(
        self,
        event: GovernanceEvent,
        latest_sequence: int,
    ) -> None:
        """Validate that event's hash is correctly computed from content.

        Args:
            event: The event to validate.
            latest_sequence: Sequence of latest event for error context.

        Raises:
            HashChainBreakError: If hash doesn't match content.
        """
        result = verify_event_hash(event)

        if not result.is_valid:
            raise HashChainBreakError(
                event_id=event.event_id,
                expected_prev_hash=result.expected_hash or "(hash verification failed)",
                actual_prev_hash=result.actual_hash or "(computed hash differs)",
                latest_sequence=latest_sequence,
            )

    async def is_valid_chain_link(
        self,
        event: GovernanceEvent,
    ) -> bool:
        """Check if an event correctly links to the chain without raising.

        Args:
            event: The event to check.

        Returns:
            True if the event correctly links to the chain, False otherwise.
        """
        try:
            await self.validate(event)
            return True
        except HashChainBreakError:
            return False
