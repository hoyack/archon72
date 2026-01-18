"""WitnessedHaltWriter port (Story 3.9, Task 4).

Port interface for writing witnessed halt events to the event store.
This is a specialized writer that can write halt events even when
the system is about to halt.

Constitutional Constraints:
- RT-2: Halt event must be written BEFORE halt takes effect
- CT-12: Witnessing creates accountability - events must be witnessed
- CT-11: Silent failure destroys legitimacy - failures must be handled
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.domain.events.constitutional_crisis import ConstitutionalCrisisPayload
    from src.domain.events.event import Event


@runtime_checkable
class WitnessedHaltWriter(Protocol):
    """Port for writing witnessed halt events.

    This is a specialized writer that writes ConstitutionalCrisisEvents
    to the event store with proper witnessing. It's designed for the
    critical halt path where we need to record the halt BEFORE it
    takes effect (RT-2).

    Constitutional Constraints:
    - RT-2: Halt event MUST be written BEFORE halt takes effect
    - CT-12: Witnessing creates accountability - all halts witnessed
    - CT-13: If write fails, halt proceeds anyway (integrity over availability)

    Design Notes:
    - This port never raises exceptions - returns None on failure
    - Callers handle failure by creating UnwitnessedHaltRecord
    - The separation from EventWriterService allows halt-specific handling

    Example:
        >>> result = await writer.write_halt_event(crisis_payload)
        >>> if result is None:
        ...     # Write failed - create unwitnessed halt record
        ...     await repo.save(UnwitnessedHaltRecord(...))
        >>> # Proceed with halt either way (CT-13)
        >>> await halt_transport.write_halt(...)
    """

    async def write_halt_event(
        self,
        crisis_payload: ConstitutionalCrisisPayload,
    ) -> Event | None:
        """Write a witnessed halt event.

        Attempts to write a ConstitutionalCrisisEvent to the event store
        with proper witnessing. This is the last event before halt.

        Args:
            crisis_payload: The crisis details to record.

        Returns:
            Event if successful (with witness_id, witness_signature).
            None if write failed for any reason.

        Note:
            This method NEVER raises exceptions. All errors are caught
            and None is returned. This design ensures the halt path
            is not blocked by exceptions. Callers must check return
            value and handle failure appropriately.
        """
        ...
