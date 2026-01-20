"""Auto-Escalation Executor Stub for testing (Story 5.6, FR-5.1, FR-5.3).

This module provides a configurable stub implementation of AutoEscalationExecutorProtocol
for use in unit and integration tests.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count [P0]
- CT-12: All outputs through witnessing pipeline
- CT-14: Silence must be expensive - auto-escalation ensures collective
         petitions get King attention without deliberation delay
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.application.ports.auto_escalation_executor import AutoEscalationResult


@dataclass
class EscalationHistoryEntry:
    """Record of an escalation execution attempt (for test assertions).

    Attributes:
        petition_id: The petition that was escalated.
        trigger_type: The type of trigger (e.g., "CO_SIGNER_THRESHOLD").
        co_signer_count: The co-signer count at time of trigger.
        threshold: The threshold that was reached.
        triggered_by: UUID of the signer who triggered threshold.
        timestamp: When the escalation was executed.
        result: The result of the escalation attempt.
    """

    petition_id: UUID
    trigger_type: str
    co_signer_count: int
    threshold: int
    triggered_by: UUID | None
    timestamp: datetime
    result: AutoEscalationResult


class AutoEscalationExecutorStub:
    """Stub implementation of AutoEscalationExecutorProtocol for testing (Story 5.6).

    Provides full control over escalation behavior for testing
    different scenarios including:
    - Successful escalation
    - Already escalated (idempotent)
    - Petition not in valid state
    - Failure simulation

    Attributes:
        _escalated_petitions: Set of petition IDs that have been escalated.
        _history: List of all escalation attempts for assertions.
        _fail_next: Whether to simulate failure on next execution.
        _invalid_state_petitions: Petitions to treat as invalid state.
    """

    def __init__(self) -> None:
        """Initialize auto-escalation executor stub."""
        self._escalated_petitions: set[UUID] = set()
        self._history: list[EscalationHistoryEntry] = []
        self._fail_next: bool = False
        self._fail_exception: Exception | None = None
        self._invalid_state_petitions: set[UUID] = set()

    async def execute(
        self,
        petition_id: UUID,
        trigger_type: str,
        co_signer_count: int,
        threshold: int,
        triggered_by: UUID | None = None,
    ) -> AutoEscalationResult:
        """Execute auto-escalation for a petition.

        Args:
            petition_id: The petition to escalate.
            trigger_type: The type of trigger (e.g., "CO_SIGNER_THRESHOLD").
            co_signer_count: The co-signer count at time of trigger.
            threshold: The threshold that was reached.
            triggered_by: UUID of the signer who triggered threshold.

        Returns:
            AutoEscalationResult with escalation details.

        Raises:
            Exception: If fail_next is set with an exception.
        """
        timestamp = datetime.now(timezone.utc)

        # Check for configured failure
        if self._fail_next:
            self._fail_next = False
            if self._fail_exception is not None:
                exc = self._fail_exception
                self._fail_exception = None
                raise exc
            raise RuntimeError("Simulated escalation failure")

        # Check for already escalated (idempotent)
        if petition_id in self._escalated_petitions:
            result = AutoEscalationResult(
                escalation_id=None,
                petition_id=petition_id,
                triggered=False,
                event_id=None,
                timestamp=timestamp,
                already_escalated=True,
                trigger_type=trigger_type,
                co_signer_count=co_signer_count,
                threshold=threshold,
            )
            self._history.append(
                EscalationHistoryEntry(
                    petition_id=petition_id,
                    trigger_type=trigger_type,
                    co_signer_count=co_signer_count,
                    threshold=threshold,
                    triggered_by=triggered_by,
                    timestamp=timestamp,
                    result=result,
                )
            )
            return result

        # Check for invalid state
        if petition_id in self._invalid_state_petitions:
            result = AutoEscalationResult(
                escalation_id=None,
                petition_id=petition_id,
                triggered=False,
                event_id=None,
                timestamp=timestamp,
                already_escalated=False,
                trigger_type=trigger_type,
                co_signer_count=co_signer_count,
                threshold=threshold,
            )
            self._history.append(
                EscalationHistoryEntry(
                    petition_id=petition_id,
                    trigger_type=trigger_type,
                    co_signer_count=co_signer_count,
                    threshold=threshold,
                    triggered_by=triggered_by,
                    timestamp=timestamp,
                    result=result,
                )
            )
            return result

        # Successful escalation
        escalation_id = uuid4()
        event_id = uuid4()

        # Mark petition as escalated
        self._escalated_petitions.add(petition_id)

        result = AutoEscalationResult(
            escalation_id=escalation_id,
            petition_id=petition_id,
            triggered=True,
            event_id=event_id,
            timestamp=timestamp,
            already_escalated=False,
            trigger_type=trigger_type,
            co_signer_count=co_signer_count,
            threshold=threshold,
        )

        self._history.append(
            EscalationHistoryEntry(
                petition_id=petition_id,
                trigger_type=trigger_type,
                co_signer_count=co_signer_count,
                threshold=threshold,
                triggered_by=triggered_by,
                timestamp=timestamp,
                result=result,
            )
        )

        return result

    async def check_already_escalated(
        self,
        petition_id: UUID,
    ) -> bool:
        """Check if a petition has already been escalated.

        Args:
            petition_id: The petition to check.

        Returns:
            True if petition is already in ESCALATED state, False otherwise.
        """
        return petition_id in self._escalated_petitions

    # Test helper methods

    def set_already_escalated(self, petition_id: UUID) -> None:
        """Mark a petition as already escalated (test helper).

        Args:
            petition_id: UUID of the petition to mark as escalated.
        """
        self._escalated_petitions.add(petition_id)

    def set_invalid_state(self, petition_id: UUID) -> None:
        """Mark a petition as having invalid state for escalation (test helper).

        Args:
            petition_id: UUID of the petition with invalid state.
        """
        self._invalid_state_petitions.add(petition_id)

    def clear_invalid_state(self, petition_id: UUID) -> None:
        """Clear invalid state flag for a petition (test helper).

        Args:
            petition_id: UUID of the petition.
        """
        self._invalid_state_petitions.discard(petition_id)

    def fail_next(self, exception: Exception | None = None) -> None:
        """Configure next execution to fail (test helper).

        Args:
            exception: Optional exception to raise. Defaults to RuntimeError.
        """
        self._fail_next = True
        self._fail_exception = exception

    def get_history(self) -> list[EscalationHistoryEntry]:
        """Get all escalation attempts (test helper).

        Returns:
            List of all escalation history entries.
        """
        return list(self._history)

    def get_history_for_petition(
        self,
        petition_id: UUID,
    ) -> list[EscalationHistoryEntry]:
        """Get escalation attempts for a specific petition (test helper).

        Args:
            petition_id: UUID of the petition.

        Returns:
            List of escalation history entries for the petition.
        """
        return [h for h in self._history if h.petition_id == petition_id]

    def get_escalated_petitions(self) -> set[UUID]:
        """Get set of all escalated petition IDs (test helper).

        Returns:
            Set of escalated petition UUIDs.
        """
        return set(self._escalated_petitions)

    def get_escalation_count(self) -> int:
        """Get total number of successful escalations (test helper).

        Returns:
            Number of successful escalations.
        """
        return len(self._escalated_petitions)

    def reset(self) -> None:
        """Reset all state (test helper)."""
        self._escalated_petitions.clear()
        self._history.clear()
        self._fail_next = False
        self._fail_exception = None
        self._invalid_state_petitions.clear()

    @classmethod
    def allowing(cls) -> AutoEscalationExecutorStub:
        """Factory for stub that allows escalations.

        Returns:
            AutoEscalationExecutorStub configured to allow escalations.
        """
        return cls()

    @classmethod
    def with_escalated(cls, *petition_ids: UUID) -> AutoEscalationExecutorStub:
        """Factory for stub with petitions already escalated.

        Args:
            petition_ids: UUIDs of petitions to mark as escalated.

        Returns:
            AutoEscalationExecutorStub with specified petitions escalated.
        """
        stub = cls()
        for pid in petition_ids:
            stub._escalated_petitions.add(pid)
        return stub

    @classmethod
    def failing(cls, exception: Exception | None = None) -> AutoEscalationExecutorStub:
        """Factory for stub that will fail on next execution.

        Args:
            exception: Optional exception to raise.

        Returns:
            AutoEscalationExecutorStub configured to fail.
        """
        stub = cls()
        stub.fail_next(exception)
        return stub
