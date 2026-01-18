"""Emergence Violation Breach Service Stub (Story 9.6, FR109).

Test stub for EmergenceViolationBreachService that provides in-memory
breach storage and configurable halt state.

Constitutional Constraints:
- FR109: Emergence violations create constitutional breaches
- FR55: No emergence claims (the violated requirement)
- CT-11: HALT CHECK FIRST (simulated via set_halt_state)
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)


class EmergenceViolationBreachServiceStub:
    """Test stub for EmergenceViolationBreachService.

    Provides in-memory breach storage and configurable halt state
    for testing scenarios.

    Example:
        stub = EmergenceViolationBreachServiceStub()

        # Test normal operation
        breach = await stub.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="test-123",
            matched_terms=("emergence",),
            detection_method="keyword_scan",
        )
        assert len(stub.get_created_breaches()) == 1

        # Test halt state
        stub.set_halt_state(True)
        with pytest.raises(SystemHaltedError):
            await stub.create_breach_for_violation(...)
    """

    def __init__(self) -> None:
        """Initialize the stub with empty state."""
        self._breaches: list[BreachEventPayload] = []
        self._halt_state: bool = False
        self._halt_reason: str | None = None

    def set_halt_state(self, halted: bool, reason: str | None = None) -> None:
        """Set the simulated halt state for testing.

        Args:
            halted: Whether system should be considered halted.
            reason: Optional halt reason message.
        """
        self._halt_state = halted
        self._halt_reason = reason or "Test halt"

    def get_created_breaches(self) -> list[BreachEventPayload]:
        """Get all breaches created by this stub.

        Returns:
            List of created BreachEventPayload objects.
        """
        return list(self._breaches)

    def clear(self) -> None:
        """Clear all stored breaches and reset halt state.

        Use between tests for isolation.
        """
        self._breaches.clear()
        self._halt_state = False
        self._halt_reason = None

    async def create_breach_for_violation(
        self,
        violation_event_id: UUID,
        content_id: str,
        matched_terms: tuple[str, ...],
        detection_method: str,
    ) -> BreachEventPayload:
        """Create breach for emergence violation (FR109).

        This stub simulates the real service:
        - Checks halt state first (CT-11)
        - Creates a BreachEventPayload with type EMERGENCE_VIOLATION
        - Stores the breach in memory for test verification

        Args:
            violation_event_id: UUID of the blocked event.
            content_id: Identifier of the blocked content.
            matched_terms: Terms that triggered the violation.
            detection_method: How violation was detected.

        Returns:
            The created BreachEventPayload.

        Raises:
            SystemHaltedError: If halt state is set.
        """
        # HALT CHECK FIRST (CT-11)
        if self._halt_state:
            raise SystemHaltedError(f"CT-11: System is halted: {self._halt_reason}")

        # Create breach payload
        breach_id = uuid4()
        detection_timestamp = datetime.now(timezone.utc)

        details: dict[str, Any] = {
            "content_id": content_id,
            "matched_terms": list(matched_terms),
            "detection_method": detection_method,
            "violation_event_id": str(violation_event_id),
        }

        payload = BreachEventPayload(
            breach_id=breach_id,
            breach_type=BreachType.EMERGENCE_VIOLATION,
            violated_requirement="FR55",
            severity=BreachSeverity.HIGH,
            detection_timestamp=detection_timestamp,
            details=MappingProxyType(details),
            source_event_id=violation_event_id,
        )

        # Store for test verification
        self._breaches.append(payload)

        return payload
