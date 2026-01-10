"""Cessation flag repository stub for testing (Story 7.4, FR41, ADR-3).

This module provides a stub implementation of CessationFlagRepositoryProtocol
for unit and integration testing.

The stub simulates dual-channel storage (Redis + DB) with:
1. In-memory storage for both channels
2. Configurable failure modes
3. Atomic semantics simulation
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.ceased_status_header import CessationDetails


@dataclass
class FailureMode:
    """Configuration for simulating channel failures."""

    redis_fails: bool = False
    db_fails: bool = False
    redis_read_fails: bool = False
    db_read_fails: bool = False


class CessationFlagRepositoryStub:
    """Stub implementation of CessationFlagRepositoryProtocol for testing.

    Simulates dual-channel storage (Redis + DB) for cessation flag.

    Usage:
        stub = CessationFlagRepositoryStub()

        # Set cessation
        from src.domain.models.ceased_status_header import CessationDetails
        details = CessationDetails(...)
        await stub.set_ceased(details)

        # Check cessation
        assert await stub.is_ceased() is True

        # Test failure modes
        stub.set_failure_mode(FailureMode(redis_fails=True))
        # Redis write will fail, but operation should still fail
        # (atomic semantics)

        # Reset for next test
        stub.clear()
    """

    def __init__(self) -> None:
        """Initialize stub with empty channels."""
        self._redis_flag: CessationDetails | None = None
        self._db_flag: CessationDetails | None = None
        self._failure_mode: FailureMode = FailureMode()
        self._set_count: int = 0
        self._check_count: int = 0

    def set_failure_mode(self, mode: FailureMode) -> None:
        """Configure failure simulation for testing.

        Args:
            mode: FailureMode configuration.
        """
        self._failure_mode = mode

    def clear_failure_mode(self) -> None:
        """Clear failure mode (all channels work normally)."""
        self._failure_mode = FailureMode()

    def clear(self) -> None:
        """Clear all state for test isolation.

        Call this in test teardown to ensure clean state.
        """
        self._redis_flag = None
        self._db_flag = None
        self._failure_mode = FailureMode()
        self._set_count = 0
        self._check_count = 0

    @property
    def set_count(self) -> int:
        """Get the number of times set_ceased() was called."""
        return self._set_count

    @property
    def check_count(self) -> int:
        """Get the number of times is_ceased() was called."""
        return self._check_count

    @property
    def redis_flag(self) -> CessationDetails | None:
        """Get the current Redis channel value (for test assertions)."""
        return self._redis_flag

    @property
    def db_flag(self) -> CessationDetails | None:
        """Get the current DB channel value (for test assertions)."""
        return self._db_flag

    async def set_ceased(self, details: CessationDetails) -> None:
        """Set cessation flag in both channels (simulated).

        Implements atomic semantics: if either channel fails,
        the operation fails entirely (no partial writes).

        Args:
            details: CessationDetails to store.

        Raises:
            RuntimeError: If channel write fails (simulated).
        """
        self._set_count += 1

        # Check for failures first (atomic - fail before any write)
        if self._failure_mode.redis_fails:
            raise RuntimeError("Simulated Redis write failure")
        if self._failure_mode.db_fails:
            raise RuntimeError("Simulated DB write failure")

        # Atomic write to both channels
        self._redis_flag = deepcopy(details)
        self._db_flag = deepcopy(details)

    async def is_ceased(self) -> bool:
        """Check if cessation flag is set in either channel.

        Tries Redis first (fast path), then DB.
        Returns True if EITHER has the flag (resilience).

        Returns:
            True if cessation flag is set in either channel.

        Raises:
            RuntimeError: If both channels fail to read.
        """
        self._check_count += 1

        redis_available = not self._failure_mode.redis_read_fails
        db_available = not self._failure_mode.db_read_fails

        if not redis_available and not db_available:
            raise RuntimeError("Both channels unavailable")

        # Try Redis first (fast path)
        if redis_available and self._redis_flag is not None:
            return True

        # Fall back to DB
        if db_available and self._db_flag is not None:
            return True

        return False

    async def get_cessation_details(self) -> CessationDetails | None:
        """Get cessation details from either channel.

        Tries Redis first (fast path), then DB.

        Returns:
            CessationDetails if cessation occurred, None otherwise.
        """
        redis_available = not self._failure_mode.redis_read_fails
        db_available = not self._failure_mode.db_read_fails

        # Try Redis first
        if redis_available and self._redis_flag is not None:
            return deepcopy(self._redis_flag)

        # Fall back to DB
        if db_available and self._db_flag is not None:
            return deepcopy(self._db_flag)

        return None
