"""Unit tests for WriterLockStub configurable modes (Stub Configurability).

Tests verify the enhanced WriterLockStub supports various failure scenarios
needed for comprehensive testing of writer lock handling.

Test Coverage:
- DEFAULT mode: All operations succeed
- ACQUIRE_FAILS mode: acquire() always returns False
- TTL_EXPIRES mode: Lock expires after N operations
- HEARTBEAT_FAILS mode: renew() fails after N calls
- CONTENTION mode: acquire() fails N times then succeeds
- Fencing token tracking
- Global lock simulation
"""

from __future__ import annotations

import pytest

from src.infrastructure.stubs.writer_lock_stub import (
    WriterLockConfig,
    WriterLockMode,
    WriterLockStub,
)


@pytest.fixture(autouse=True)
def reset_global_lock_state():
    """Reset global lock state before each test to ensure test isolation."""
    WriterLockStub.reset_global_state()
    yield
    WriterLockStub.reset_global_state()


class TestWriterLockStubDefaultMode:
    """Tests for DEFAULT mode (basic development scenario)."""

    @pytest.mark.asyncio
    async def test_acquire_succeeds(self) -> None:
        """DEFAULT: acquire() returns True."""
        stub = WriterLockStub()
        result = await stub.acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_release_succeeds(self) -> None:
        """DEFAULT: release() completes without error."""
        stub = WriterLockStub()
        await stub.acquire()
        await stub.release()  # Should not raise

    @pytest.mark.asyncio
    async def test_is_held_after_acquire(self) -> None:
        """DEFAULT: is_held() returns True after acquire."""
        stub = WriterLockStub()
        await stub.acquire()
        result = await stub.is_held()
        assert result is True

    @pytest.mark.asyncio
    async def test_is_held_after_release(self) -> None:
        """DEFAULT: is_held() returns False after release."""
        stub = WriterLockStub()
        await stub.acquire()
        await stub.release()
        result = await stub.is_held()
        assert result is False

    @pytest.mark.asyncio
    async def test_renew_succeeds_when_held(self) -> None:
        """DEFAULT: renew() returns True when lock is held."""
        stub = WriterLockStub()
        await stub.acquire()
        result = await stub.renew()
        assert result is True

    @pytest.mark.asyncio
    async def test_renew_fails_when_not_held(self) -> None:
        """DEFAULT: renew() returns False when lock not held."""
        stub = WriterLockStub()
        result = await stub.renew()
        assert result is False


class TestWriterLockStubAcquireFailsMode:
    """Tests for ACQUIRE_FAILS mode (another writer holds lock)."""

    @pytest.mark.asyncio
    async def test_acquire_always_fails(self) -> None:
        """ACQUIRE_FAILS: acquire() always returns False."""
        stub = WriterLockStub.with_acquire_failure()
        result = await stub.acquire()
        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_acquire_attempts_fail(self) -> None:
        """ACQUIRE_FAILS: Multiple acquire() attempts all fail."""
        stub = WriterLockStub.with_acquire_failure()
        for _ in range(5):
            result = await stub.acquire()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_held_returns_false(self) -> None:
        """ACQUIRE_FAILS: is_held() returns False (lock never acquired)."""
        stub = WriterLockStub.with_acquire_failure()
        await stub.acquire()  # Will fail
        result = await stub.is_held()
        assert result is False


class TestWriterLockStubTTLExpiresMode:
    """Tests for TTL_EXPIRES mode (simulating TTL expiration)."""

    @pytest.mark.asyncio
    async def test_lock_expires_after_n_operations(self) -> None:
        """TTL_EXPIRES: Lock expires after specified operations."""
        stub = WriterLockStub.with_ttl_expiration(operations_until_expire=3)
        await stub.acquire()

        # First 3 operations should succeed
        for i in range(3):
            result = await stub.is_held()
            assert result is True, f"Operation {i + 1} should succeed"

        # 4th operation should fail (expired)
        result = await stub.is_held()
        assert result is False

    @pytest.mark.asyncio
    async def test_operation_count_tracking(self) -> None:
        """TTL_EXPIRES: Operation count is tracked correctly."""
        stub = WriterLockStub.with_ttl_expiration(operations_until_expire=5)
        await stub.acquire()

        for _i in range(3):
            await stub.is_held()

        assert stub.get_operation_count() == 3

    @pytest.mark.asyncio
    async def test_single_operation_expiration(self) -> None:
        """TTL_EXPIRES: Lock can expire after just 1 operation."""
        stub = WriterLockStub.with_ttl_expiration(operations_until_expire=1)
        await stub.acquire()

        # First check succeeds
        result = await stub.is_held()
        assert result is True

        # Second check fails (expired)
        result = await stub.is_held()
        assert result is False


class TestWriterLockStubHeartbeatFailsMode:
    """Tests for HEARTBEAT_FAILS mode (simulating network issues)."""

    @pytest.mark.asyncio
    async def test_heartbeat_fails_after_n_renewals(self) -> None:
        """HEARTBEAT_FAILS: renew() fails after specified renewals."""
        stub = WriterLockStub.with_heartbeat_failure(renewals_until_fail=2)
        await stub.acquire()

        # First 2 renewals succeed
        for i in range(2):
            result = await stub.renew()
            assert result is True, f"Renewal {i + 1} should succeed"

        # 3rd renewal fails
        result = await stub.renew()
        assert result is False

    @pytest.mark.asyncio
    async def test_lock_lost_after_heartbeat_failure(self) -> None:
        """HEARTBEAT_FAILS: Lock is lost after heartbeat failure."""
        stub = WriterLockStub.with_heartbeat_failure(renewals_until_fail=1)
        await stub.acquire()

        # First renewal succeeds
        await stub.renew()

        # Second renewal fails and loses lock
        await stub.renew()

        # is_held should now return False
        result = await stub.is_held()
        assert result is False

    @pytest.mark.asyncio
    async def test_renewal_count_tracking(self) -> None:
        """HEARTBEAT_FAILS: Renewal count is tracked correctly."""
        stub = WriterLockStub.with_heartbeat_failure(renewals_until_fail=5)
        await stub.acquire()

        for _ in range(3):
            await stub.renew()

        assert stub.get_renewal_count() == 3


class TestWriterLockStubContentionMode:
    """Tests for CONTENTION mode (simulating temporary contention)."""

    @pytest.mark.asyncio
    async def test_acquire_fails_n_times_then_succeeds(self) -> None:
        """CONTENTION: acquire() fails N times then succeeds."""
        stub = WriterLockStub.with_contention(contention_count=3)

        # First 3 attempts fail
        for i in range(3):
            result = await stub.acquire()
            assert result is False, f"Attempt {i + 1} should fail"

        # 4th attempt succeeds
        result = await stub.acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_attempts_tracking(self) -> None:
        """CONTENTION: Acquire attempts are tracked correctly."""
        stub = WriterLockStub.with_contention(contention_count=2)

        await stub.acquire()  # Fail
        await stub.acquire()  # Fail

        assert stub.get_acquire_attempts() == 2

    @pytest.mark.asyncio
    async def test_zero_contention_succeeds_immediately(self) -> None:
        """CONTENTION: Zero contention count succeeds immediately."""
        stub = WriterLockStub.with_contention(contention_count=0)
        result = await stub.acquire()
        assert result is True


class TestWriterLockStubFencingToken:
    """Tests for fencing token functionality."""

    @pytest.mark.asyncio
    async def test_fencing_token_increments_on_acquire(self) -> None:
        """Fencing token increments each time lock is acquired."""
        stub = WriterLockStub()

        initial_token = stub.get_fencing_token()
        await stub.acquire()
        assert stub.get_fencing_token() == initial_token + 1

        await stub.release()
        await stub.acquire()
        assert stub.get_fencing_token() == initial_token + 2

    @pytest.mark.asyncio
    async def test_custom_fencing_token_start(self) -> None:
        """Fencing token can start at custom value."""
        config = WriterLockConfig(fencing_token_start=100)
        stub = WriterLockStub(config)

        assert stub.get_fencing_token() == 100

        await stub.acquire()
        assert stub.get_fencing_token() == 101

    @pytest.mark.asyncio
    async def test_fencing_token_not_incremented_on_failed_acquire(self) -> None:
        """Fencing token doesn't increment if acquire fails."""
        stub = WriterLockStub.with_acquire_failure()

        initial_token = stub.get_fencing_token()
        await stub.acquire()  # Fails

        assert stub.get_fencing_token() == initial_token


class TestWriterLockStubGlobalLockSimulation:
    """Tests for global lock holder simulation (distributed lock behavior)."""

    @pytest.mark.asyncio
    async def test_second_instance_cannot_acquire(self) -> None:
        """Second WriterLockStub instance cannot acquire when first holds lock."""
        stub1 = WriterLockStub()
        stub2 = WriterLockStub()

        await stub1.acquire()
        result = await stub2.acquire()

        assert result is False

    @pytest.mark.asyncio
    async def test_second_instance_can_acquire_after_release(self) -> None:
        """Second instance can acquire after first releases."""
        stub1 = WriterLockStub()
        stub2 = WriterLockStub()

        await stub1.acquire()
        await stub1.release()
        result = await stub2.acquire()

        assert result is True

    @pytest.mark.asyncio
    async def test_same_instance_can_reacquire(self) -> None:
        """Same instance can reacquire its own lock."""
        stub = WriterLockStub()

        await stub.acquire()
        result = await stub.acquire()  # Same instance reacquiring

        assert result is True


class TestWriterLockStubTestHelpers:
    """Tests for test helper methods."""

    @pytest.mark.asyncio
    async def test_set_lock_lost_simulates_sudden_loss(self) -> None:
        """set_lock_lost() simulates sudden lock loss."""
        stub = WriterLockStub()
        await stub.acquire()

        # Lock is held
        assert await stub.is_held() is True

        # Simulate sudden loss
        stub.set_lock_lost(True)

        # Lock appears lost
        assert await stub.is_held() is False
        assert await stub.renew() is False

    @pytest.mark.asyncio
    async def test_set_lock_lost_can_be_reversed(self) -> None:
        """set_lock_lost() can be reversed."""
        stub = WriterLockStub()
        await stub.acquire()

        stub.set_lock_lost(True)
        assert await stub.is_held() is False

        stub.set_lock_lost(False)
        assert await stub.is_held() is True

    @pytest.mark.asyncio
    async def test_reset_counters(self) -> None:
        """reset_counters() resets all tracking counters."""
        stub = WriterLockStub.with_ttl_expiration(operations_until_expire=10)
        await stub.acquire()

        # Accumulate some counts
        for _ in range(5):
            await stub.is_held()

        assert stub.get_operation_count() == 5

        # Reset
        stub.reset_counters()

        assert stub.get_operation_count() == 0
        assert stub.get_renewal_count() == 0
        assert stub.get_acquire_attempts() == 0


class TestWriterLockStubConfigDirect:
    """Tests for direct configuration usage."""

    @pytest.mark.asyncio
    async def test_config_with_multiple_settings(self) -> None:
        """Configuration can combine multiple settings."""
        config = WriterLockConfig(
            mode=WriterLockMode.TTL_EXPIRES,
            operations_until_expire=3,
            fencing_token_start=500,
        )
        stub = WriterLockStub(config)

        assert stub.get_fencing_token() == 500

        await stub.acquire()
        for _ in range(3):
            await stub.is_held()

        # Should expire on 4th
        assert await stub.is_held() is False

    @pytest.mark.asyncio
    async def test_default_config_values(self) -> None:
        """Default configuration uses sensible defaults."""
        config = WriterLockConfig()

        assert config.mode == WriterLockMode.DEFAULT
        assert config.operations_until_expire == 0
        assert config.renewals_until_fail == 0
        assert config.contention_count == 0
        assert config.fencing_token_start == 1
