"""Override executor stub for development and testing (Story 5.1, FR23).

This stub implements OverrideExecutorPort for testing the override
flow without actual override execution.

WARNING: This stub is NOT for production use.
Production implementation would connect to actual override mechanisms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from src.application.ports.override_executor import OverrideExecutorPort, OverrideResult
from src.domain.events.override_event import OverrideEventPayload

if TYPE_CHECKING:
    pass


@dataclass
class ExecutedOverride:
    """Record of an executed override for testing verification."""

    payload: OverrideEventPayload
    event_id: UUID


class OverrideExecutorStub(OverrideExecutorPort):
    """Stub implementation of OverrideExecutorPort for testing.

    This stub tracks all executed overrides in memory and can be
    configured to simulate success or failure.

    Attributes:
        executed_overrides: List of all successfully executed overrides.
        should_fail: If True, execute_override returns failure.
        failure_message: Message to return when should_fail is True.
    """

    def __init__(
        self,
        should_fail: bool = False,
        failure_message: str = "Stub configured to fail",
    ) -> None:
        """Initialize the stub.

        Args:
            should_fail: If True, all executions fail.
            failure_message: Error message when failing.
        """
        self._executed_overrides: list[ExecutedOverride] = []
        self._should_fail = should_fail
        self._failure_message = failure_message

    @property
    def executed_overrides(self) -> list[ExecutedOverride]:
        """Get list of executed overrides."""
        return self._executed_overrides.copy()

    def set_should_fail(
        self, should_fail: bool, message: str = "Stub configured to fail"
    ) -> None:
        """Configure whether executions should fail.

        Args:
            should_fail: If True, all executions fail.
            message: Error message when failing.
        """
        self._should_fail = should_fail
        self._failure_message = message

    def clear_executed(self) -> None:
        """Clear the list of executed overrides."""
        self._executed_overrides.clear()

    async def execute_override(
        self,
        override_payload: OverrideEventPayload,
        event_id: UUID,
    ) -> OverrideResult:
        """Execute an override action (stub implementation).

        Args:
            override_payload: The validated override payload.
            event_id: UUID of the logged override event.

        Returns:
            OverrideResult indicating success or failure based on configuration.
        """
        if self._should_fail:
            return OverrideResult(
                success=False,
                event_id=event_id,
                error_message=self._failure_message,
            )

        # Track the executed override
        self._executed_overrides.append(
            ExecutedOverride(
                payload=override_payload,
                event_id=event_id,
            )
        )

        return OverrideResult(
            success=True,
            event_id=event_id,
            error_message=None,
        )
