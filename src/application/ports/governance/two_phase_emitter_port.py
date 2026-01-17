"""TwoPhaseEventEmitterPort - Interface for two-phase event emission.

Story: consent-gov-1.6: Two-Phase Event Emission

This port defines the contract for emitting two-phase events that enable
Knight observability of all governance operations.

Two-Phase Emission Pattern:
1. emit_intent() - Published BEFORE operation begins
2. emit_commit() - Published on successful operation completion
3. emit_failure() - Published on operation failure

Constitutional Guarantees:
- Intent is ALWAYS emitted before operation begins
- Outcome (commit/failure) is ALWAYS emitted after operation
- No orphaned intents - auto-resolved after timeout

References:
- AD-3: Two-phase event emission
- NFR-CONST-07: Witness statements cannot be suppressed
- NFR-OBS-01: Events observable within ≤1 second
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class TwoPhaseEventEmitterPort(Protocol):
    """Port for two-phase event emission for Knight observability.

    This interface defines the contract for emitting governance events
    in two phases: intent and outcome (commit or failure).

    Constitutional Guarantee:
    - Intent is ALWAYS emitted before operation begins
    - Outcome (commit/failure) is ALWAYS emitted after operation
    - No orphaned intents - auto-resolved after timeout

    Usage Pattern:
        correlation_id = await emitter.emit_intent(...)
        try:
            result = await perform_operation()
            await emitter.emit_commit(correlation_id, result)
        except Exception as e:
            await emitter.emit_failure(correlation_id, str(e), {...})
            raise
    """

    async def emit_intent(
        self,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict[str, Any],
    ) -> UUID:
        """Emit intent event BEFORE operation begins.

        This method MUST be called before any governance operation starts.
        The returned correlation_id is used to link the intent to its
        outcome (commit or failure).

        Args:
            operation_type: Operation being attempted (e.g., "executive.task.accept").
            actor_id: ID of the archon or officer initiating the action.
            target_entity_id: ID of the entity being acted upon.
            intent_payload: Operation-specific intent data.

        Returns:
            UUID: The correlation_id linking this intent to its outcome.

        Note:
            The intent event is published to the ledger and Knight can
            observe it immediately (per NFR-OBS-01).
        """
        ...

    async def emit_commit(
        self,
        correlation_id: UUID,
        result_payload: dict[str, Any],
    ) -> None:
        """Emit commit event on successful operation completion.

        This method MUST be called after the governance operation
        completes successfully. It closes the two-phase cycle for
        the given correlation_id.

        Args:
            correlation_id: The correlation_id from emit_intent().
            result_payload: Operation-specific result data.

        Raises:
            TwoPhaseEmitError: If correlation_id doesn't match a pending intent.

        Note:
            After this call, the intent is no longer considered pending
            and will not be detected as an orphan.
        """
        ...

    async def emit_failure(
        self,
        correlation_id: UUID,
        failure_reason: str,
        failure_details: dict[str, Any],
    ) -> None:
        """Emit failure event when operation fails.

        This method MUST be called when the governance operation fails.
        It closes the two-phase cycle with a failure record.

        Args:
            correlation_id: The correlation_id from emit_intent().
            failure_reason: Short reason code (e.g., "VALIDATION_FAILED").
            failure_details: Detailed error information.

        Raises:
            TwoPhaseEmitError: If correlation_id doesn't match a pending intent.

        Note:
            After this call, the intent is no longer considered pending.
            For orphan auto-resolution, failure_reason should be "ORPHAN_TIMEOUT".
        """
        ...

    async def get_pending_intent(
        self,
        correlation_id: UUID,
    ) -> dict[str, Any] | None:
        """Get a pending intent by correlation_id.

        Used by the OrphanIntentDetector to retrieve intent details
        when auto-resolving orphaned intents.

        Args:
            correlation_id: The correlation_id to look up.

        Returns:
            Dict with intent details if pending, None if already resolved
            or not found.
        """
        ...


class TwoPhaseEmitError(Exception):
    """Raised when two-phase event emission fails.

    This error indicates that an emit operation could not complete,
    such as when trying to emit an outcome for a non-existent intent.
    """

    pass
