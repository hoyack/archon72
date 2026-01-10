"""Freeze checker stub for testing (Story 7.4, FR41).

This module provides a stub implementation of FreezeCheckerProtocol
for unit and integration testing.

The stub allows tests to:
1. Configure frozen state
2. Clear frozen state for test isolation
3. Verify freeze check calls
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from src.domain.models.ceased_status_header import CessationDetails


class FreezeCheckerStub:
    """Stub implementation of FreezeCheckerProtocol for testing.

    Provides configurable freeze state for testing freeze mechanics.

    Usage:
        stub = FreezeCheckerStub()

        # Test frozen state
        stub.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=12345,
            reason="Test cessation",
        )
        assert await stub.is_frozen() is True

        # Reset for next test
        stub.clear_frozen()
        assert await stub.is_frozen() is False
    """

    def __init__(self) -> None:
        """Initialize stub with not-frozen state."""
        self._frozen: bool = False
        self._details: CessationDetails | None = None
        self._check_count: int = 0

    def set_frozen(
        self,
        *,
        ceased_at: datetime,
        final_sequence: int,
        reason: str,
        cessation_event_id: str | None = None,
    ) -> None:
        """Configure frozen state for testing.

        Args:
            ceased_at: When cessation occurred.
            final_sequence: Final sequence number.
            reason: Reason for cessation.
            cessation_event_id: Optional event ID (generated if not provided).
        """
        from src.domain.models.ceased_status_header import CessationDetails

        self._frozen = True
        self._details = CessationDetails(
            ceased_at=ceased_at,
            final_sequence_number=final_sequence,
            reason=reason,
            cessation_event_id=uuid4() if cessation_event_id is None else uuid4(),
        )

    def set_frozen_simple(self) -> None:
        """Set frozen state with default values for simple tests.

        Creates a frozen state with current time and reasonable defaults.
        """
        self.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=1000,
            reason="Test cessation",
        )

    def clear_frozen(self) -> None:
        """Clear frozen state for test isolation.

        Call this in test teardown to ensure clean state.
        """
        self._frozen = False
        self._details = None
        self._check_count = 0

    @property
    def check_count(self) -> int:
        """Get the number of times is_frozen() was called.

        Useful for verifying freeze checks are being performed.
        """
        return self._check_count

    async def is_frozen(self) -> bool:
        """Check if stub is in frozen state.

        Returns:
            True if set_frozen() was called, False otherwise.
        """
        self._check_count += 1
        return self._frozen

    async def get_freeze_details(self) -> CessationDetails | None:
        """Get configured cessation details.

        Returns:
            CessationDetails if frozen, None otherwise.
        """
        return self._details

    async def get_ceased_at(self) -> datetime | None:
        """Get the configured ceased_at timestamp.

        Returns:
            datetime if frozen, None otherwise.
        """
        if self._details is None:
            return None
        return self._details.ceased_at

    async def get_final_sequence(self) -> int | None:
        """Get the configured final sequence number.

        Returns:
            int if frozen, None otherwise.
        """
        if self._details is None:
            return None
        return self._details.final_sequence_number
