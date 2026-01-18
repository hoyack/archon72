"""Stub WriterLock for development/testing (Story 1.6, Task 4.4).

Production uses Redis distributed lock with fencing token per ADR-1.
This stub provides configurable behavior for local development and testing.

WARNING: This stub is for development/testing only.
Production must use the real Redis-based lock implementation.

Production Requirements (for future implementation):
- Redis SETNX with TTL for distributed lock
- Fencing token to prevent zombie writes
- Heartbeat renewal at TTL/3 intervals
- Lock TTL of 30 seconds (configurable)
- If heartbeat fails, Writer must halt immediately

Configurable Test Modes:
- DEFAULT: Always succeeds (basic development)
- ACQUIRE_FAILS: acquire() always returns False
- TTL_EXPIRES: Lock expires after N operations (simulates TTL expiration)
- HEARTBEAT_FAILS: renew() fails after N calls (simulates network issues)
- CONTENTION: Multiple acquire() calls simulate lock contention

Usage Examples:
    # Basic usage (always succeeds)
    stub = WriterLockStub()

    # Simulate acquire failure (another writer holds lock)
    stub = WriterLockStub.with_acquire_failure()

    # Simulate TTL expiration after 5 operations
    stub = WriterLockStub.with_ttl_expiration(operations_until_expire=5)

    # Simulate heartbeat failure after 3 renewals
    stub = WriterLockStub.with_heartbeat_failure(renewals_until_fail=3)

    # Simulate lock contention
    stub = WriterLockStub.with_contention(contention_count=2)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from src.application.ports.writer_lock import WriterLockProtocol


class WriterLockMode(Enum):
    """Configurable modes for WriterLockStub behavior."""

    DEFAULT = "default"  # Always succeeds
    ACQUIRE_FAILS = "acquire_fails"  # acquire() returns False
    TTL_EXPIRES = "ttl_expires"  # Lock expires after N operations
    HEARTBEAT_FAILS = "heartbeat_fails"  # renew() fails after N calls
    CONTENTION = "contention"  # Simulate lock contention


@dataclass
class WriterLockConfig:
    """Configuration for WriterLockStub behavior.

    Attributes:
        mode: The operating mode for the stub.
        operations_until_expire: For TTL_EXPIRES mode, operations until lock expires.
        renewals_until_fail: For HEARTBEAT_FAILS mode, renewals until failure.
        contention_count: For CONTENTION mode, acquire() attempts before success.
        fencing_token_start: Starting value for fencing tokens.
    """

    mode: WriterLockMode = WriterLockMode.DEFAULT
    operations_until_expire: int = 0
    renewals_until_fail: int = 0
    contention_count: int = 0
    fencing_token_start: int = 1


class WriterLockStub(WriterLockProtocol):
    """Configurable stub implementation for testing writer lock scenarios.

    For development/testing only. Production uses Redis distributed lock.

    This stub maintains internal state to allow testing of lock
    acquisition, release, verification flows, and various failure scenarios.

    Modes:
        DEFAULT: All operations succeed (basic development).
        ACQUIRE_FAILS: acquire() always returns False (test writer rejection).
        TTL_EXPIRES: Lock expires after N operations (test TTL handling).
        HEARTBEAT_FAILS: renew() fails after N calls (test heartbeat failure).
        CONTENTION: acquire() fails N times then succeeds (test retry logic).

    Attributes:
        _held: Whether this instance holds the lock.
        _force_not_held: If True, is_held() returns False (for testing lock loss).
        _config: Configuration controlling stub behavior.
        _operation_count: Count of operations for TTL tracking.
        _renewal_count: Count of renewals for heartbeat tracking.
        _acquire_attempts: Count of acquire attempts for contention tracking.
        _fencing_token: Current fencing token value.
    """

    # Class-level shared state for simulating distributed lock
    _global_lock_holder: ClassVar[WriterLockStub | None] = None

    def __init__(self, config: WriterLockConfig | None = None) -> None:
        """Initialize the stub with optional configuration.

        Args:
            config: Optional configuration for stub behavior. Defaults to DEFAULT mode.
        """
        self._held = False
        self._force_not_held = False
        self._config = config or WriterLockConfig()
        self._operation_count = 0
        self._renewal_count = 0
        self._acquire_attempts = 0
        self._fencing_token = self._config.fencing_token_start

    # --- Factory methods for common test scenarios ---

    @classmethod
    def with_acquire_failure(cls) -> WriterLockStub:
        """Create stub that always fails to acquire lock.

        Use this to test scenarios where another writer holds the lock.

        Returns:
            WriterLockStub configured to fail all acquire() calls.
        """
        return cls(WriterLockConfig(mode=WriterLockMode.ACQUIRE_FAILS))

    @classmethod
    def with_ttl_expiration(cls, operations_until_expire: int = 5) -> WriterLockStub:
        """Create stub that expires lock after N operations.

        Use this to test TTL expiration handling. Lock will be lost
        after the specified number of is_held() checks.

        Args:
            operations_until_expire: Number of is_held() calls before expiration.

        Returns:
            WriterLockStub configured to expire after N operations.
        """
        return cls(
            WriterLockConfig(
                mode=WriterLockMode.TTL_EXPIRES,
                operations_until_expire=operations_until_expire,
            )
        )

    @classmethod
    def with_heartbeat_failure(cls, renewals_until_fail: int = 3) -> WriterLockStub:
        """Create stub that fails heartbeat after N renewals.

        Use this to test heartbeat failure handling. Lock renewal
        will fail after the specified number of renew() calls.

        Args:
            renewals_until_fail: Number of renew() calls before failure.

        Returns:
            WriterLockStub configured to fail heartbeat after N renewals.
        """
        return cls(
            WriterLockConfig(
                mode=WriterLockMode.HEARTBEAT_FAILS,
                renewals_until_fail=renewals_until_fail,
            )
        )

    @classmethod
    def with_contention(cls, contention_count: int = 2) -> WriterLockStub:
        """Create stub that simulates lock contention.

        Use this to test retry logic. acquire() will fail N times
        before succeeding, simulating temporary lock contention.

        Args:
            contention_count: Number of acquire() failures before success.

        Returns:
            WriterLockStub configured to simulate contention.
        """
        return cls(
            WriterLockConfig(
                mode=WriterLockMode.CONTENTION,
                contention_count=contention_count,
            )
        )

    @classmethod
    def reset_global_state(cls) -> None:
        """Reset class-level shared state.

        Call this between tests when using shared lock simulation.
        """
        cls._global_lock_holder = None

    # --- Protocol implementation ---

    async def acquire(self) -> bool:
        """Acquire the writer lock based on configured mode.

        Returns:
            True if lock acquired successfully, False otherwise.
        """
        self._acquire_attempts += 1

        if self._config.mode == WriterLockMode.ACQUIRE_FAILS:
            return False

        if self._config.mode == WriterLockMode.CONTENTION:
            if self._acquire_attempts <= self._config.contention_count:
                return False

        # Check global lock holder for distributed simulation
        if WriterLockStub._global_lock_holder is not None:
            if WriterLockStub._global_lock_holder is not self:
                return False

        self._held = True
        self._fencing_token += 1
        WriterLockStub._global_lock_holder = self
        return True

    async def release(self) -> None:
        """Release the writer lock."""
        self._held = False
        if WriterLockStub._global_lock_holder is self:
            WriterLockStub._global_lock_holder = None

    async def is_held(self) -> bool:
        """Check if this instance holds the lock.

        Returns:
            True if lock is held and not expired/lost, False otherwise.
        """
        if self._force_not_held:
            return False

        if self._config.mode == WriterLockMode.TTL_EXPIRES:
            self._operation_count += 1
            if self._operation_count > self._config.operations_until_expire:
                self._held = False
                return False

        return self._held

    async def renew(self) -> bool:
        """Renew the lock TTL (heartbeat).

        Returns:
            True if renewal succeeded, False if failed.
        """
        if self._force_not_held:
            return False

        if not self._held:
            return False

        if self._config.mode == WriterLockMode.HEARTBEAT_FAILS:
            self._renewal_count += 1
            if self._renewal_count > self._config.renewals_until_fail:
                self._held = False
                return False

        return True

    # --- Test helpers ---

    def set_lock_lost(self, lost: bool = True) -> None:
        """Test helper: Simulate sudden lock loss.

        Use this to test immediate lock loss scenarios (e.g., network partition).

        Args:
            lost: If True, is_held() and renew() will return False.
        """
        self._force_not_held = lost

    def get_fencing_token(self) -> int:
        """Test helper: Get current fencing token.

        Fencing tokens prevent zombie writes by ensuring writes
        are rejected if they carry a stale token.

        Returns:
            Current fencing token value.
        """
        return self._fencing_token

    def get_operation_count(self) -> int:
        """Test helper: Get operation count for TTL tracking.

        Returns:
            Number of is_held() calls made.
        """
        return self._operation_count

    def get_renewal_count(self) -> int:
        """Test helper: Get renewal count for heartbeat tracking.

        Returns:
            Number of renew() calls made.
        """
        return self._renewal_count

    def get_acquire_attempts(self) -> int:
        """Test helper: Get acquire attempt count.

        Returns:
            Number of acquire() calls made.
        """
        return self._acquire_attempts

    def reset_counters(self) -> None:
        """Test helper: Reset all counters without changing mode.

        Useful for testing multi-phase scenarios.
        """
        self._operation_count = 0
        self._renewal_count = 0
        self._acquire_attempts = 0
