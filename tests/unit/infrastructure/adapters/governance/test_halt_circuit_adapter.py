"""Unit tests for HaltCircuitAdapter (three-channel halt circuit).

Story: consent-gov-4.1 (Halt Circuit Port & Adapter)
Tests: Tasks 3-9 - Three-channel implementation and reliability

Acceptance Criteria Tested:
- AC1: In-memory channel (primary, fastest) checked before ANY I/O
- AC2: Redis channel (secondary) propagates halt to other instances
- AC3: Ledger channel (tertiary) records halt permanently
- AC4: Halt completes in ≤100ms (NFR-PERF-01)
- AC5: Primary halt works even if Redis/DB unavailable (NFR-REL-01)
- AC6: Halt flag checked before every I/O operation
- AC8: HaltCircuitAdapter implements three-channel design
- AC9: Unit tests for halt circuit reliability
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.application.ports.governance.halt_port import HaltChecker
from src.domain.governance.halt import HaltedException, HaltReason, HaltStatus
from src.infrastructure.adapters.governance.halt_circuit_adapter import (
    HaltCircuitAdapter,
)
from tests.helpers.fake_time_authority import FakeTimeAuthority


class FakeEventEmitter:
    """Fake event emitter for testing tertiary channel."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.emitted_events: list[dict[str, Any]] = []
        self.should_fail = should_fail

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
        trace_id: str | None = None,
    ) -> None:
        if self.should_fail:
            raise ConnectionError("Database unavailable")

        self.emitted_events.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
                "trace_id": trace_id,
            }
        )


class FakeRedis:
    """Fake Redis client for testing secondary channel."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.published_messages: list[tuple[str, str]] = []
        self.should_fail = should_fail
        self._pubsub = MagicMock()

    async def publish(self, channel: str, message: str) -> None:
        if self.should_fail:
            raise ConnectionError("Redis unavailable")

        self.published_messages.append((channel, message))

    def pubsub(self) -> MagicMock:
        return self._pubsub


@pytest.fixture
def fake_time() -> FakeTimeAuthority:
    """Provide fake time authority for deterministic tests."""
    return FakeTimeAuthority(
        frozen_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    )


@pytest.fixture
def fake_redis() -> FakeRedis:
    """Provide fake Redis client."""
    return FakeRedis()


@pytest.fixture
def fake_emitter() -> FakeEventEmitter:
    """Provide fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def halt_circuit(
    fake_time: FakeTimeAuthority,
    fake_redis: FakeRedis,
    fake_emitter: FakeEventEmitter,
) -> HaltCircuitAdapter:
    """Provide fully configured halt circuit adapter."""
    return HaltCircuitAdapter(
        time_authority=fake_time,
        redis_client=fake_redis,  # type: ignore
        event_emitter=fake_emitter,
    )


@pytest.fixture
def halt_circuit_minimal(fake_time: FakeTimeAuthority) -> HaltCircuitAdapter:
    """Provide halt circuit with no Redis/DB (minimal mode)."""
    return HaltCircuitAdapter(
        time_authority=fake_time,
        redis_client=None,
        event_emitter=None,
    )


class TestPrimaryChannel:
    """Tests for primary (in-memory) halt channel (AC1, AC5)."""

    @pytest.mark.asyncio
    async def test_initial_state_not_halted(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """Initial state is not halted."""
        assert halt_circuit.is_halted() is False

    @pytest.mark.asyncio
    async def test_trigger_halt_sets_flag(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """trigger_halt() sets the in-memory flag."""
        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Test halt",
        )

        assert halt_circuit.is_halted() is True

    @pytest.mark.asyncio
    async def test_is_halted_is_synchronous(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """is_halted() is synchronous (not async)."""
        # This test verifies that is_halted() can be called without await
        result = halt_circuit.is_halted()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_halt_status_includes_all_fields(
        self, halt_circuit: HaltCircuitAdapter, fake_time: FakeTimeAuthority
    ) -> None:
        """Halt status includes all provided fields."""
        operator_id = uuid4()
        trace_id = "test-trace-123"

        await halt_circuit.trigger_halt(
            reason=HaltReason.INTEGRITY_VIOLATION,
            message="Hash chain break detected",
            operator_id=operator_id,
            trace_id=trace_id,
        )

        status = halt_circuit.get_halt_status()
        assert status.is_halted is True
        assert status.reason == HaltReason.INTEGRITY_VIOLATION
        assert status.message == "Hash chain break detected"
        assert status.operator_id == operator_id
        assert status.trace_id == trace_id
        assert status.halted_at == fake_time.now()

    @pytest.mark.asyncio
    async def test_halt_is_idempotent(self, halt_circuit: HaltCircuitAdapter) -> None:
        """Triggering halt multiple times is idempotent."""
        first_status = await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="First halt",
        )

        second_status = await halt_circuit.trigger_halt(
            reason=HaltReason.SYSTEM_FAULT,
            message="Second halt attempt",
        )

        # Should return the first halt status
        assert first_status == second_status
        assert halt_circuit.get_halt_status().message == "First halt"


class TestPrimaryChannelReliability:
    """Tests for primary channel reliability (AC5: works without Redis/DB)."""

    @pytest.mark.asyncio
    async def test_halt_works_without_redis(
        self, halt_circuit_minimal: HaltCircuitAdapter
    ) -> None:
        """AC5: Primary halt works when Redis is unavailable."""
        await halt_circuit_minimal.trigger_halt(
            reason=HaltReason.SYSTEM_FAULT,
            message="Fault detected without Redis",
        )

        assert halt_circuit_minimal.is_halted() is True

    @pytest.mark.asyncio
    async def test_halt_works_without_db(
        self, fake_time: FakeTimeAuthority, fake_redis: FakeRedis
    ) -> None:
        """AC5: Primary halt works when DB is unavailable."""
        circuit = HaltCircuitAdapter(
            time_authority=fake_time,
            redis_client=fake_redis,  # type: ignore
            event_emitter=None,  # No DB
        )

        await circuit.trigger_halt(
            reason=HaltReason.INTEGRITY_VIOLATION,
            message="Hash chain break without DB",
        )

        assert circuit.is_halted() is True

    @pytest.mark.asyncio
    async def test_halt_works_without_both(
        self, halt_circuit_minimal: HaltCircuitAdapter
    ) -> None:
        """AC5: Primary halt works when both Redis and DB unavailable."""
        await halt_circuit_minimal.trigger_halt(
            reason=HaltReason.CONSTITUTIONAL_BREACH,
            message="Breach detected in degraded mode",
        )

        assert halt_circuit_minimal.is_halted() is True
        status = halt_circuit_minimal.get_halt_status()
        assert status.reason == HaltReason.CONSTITUTIONAL_BREACH

    @pytest.mark.asyncio
    async def test_halt_works_with_redis_failure(
        self, fake_time: FakeTimeAuthority, fake_emitter: FakeEventEmitter
    ) -> None:
        """Primary halt succeeds even when Redis publish fails."""
        failing_redis = FakeRedis(should_fail=True)
        circuit = HaltCircuitAdapter(
            time_authority=fake_time,
            redis_client=failing_redis,  # type: ignore
            event_emitter=fake_emitter,
        )

        # Should NOT raise, even though Redis fails
        await circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Halt despite Redis failure",
        )

        assert circuit.is_halted() is True

    @pytest.mark.asyncio
    async def test_halt_works_with_db_failure(
        self, fake_time: FakeTimeAuthority, fake_redis: FakeRedis
    ) -> None:
        """Primary halt succeeds even when DB write fails."""
        failing_emitter = FakeEventEmitter(should_fail=True)
        circuit = HaltCircuitAdapter(
            time_authority=fake_time,
            redis_client=fake_redis,  # type: ignore
            event_emitter=failing_emitter,
        )

        # Should NOT raise, even though DB fails
        await circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Halt despite DB failure",
        )

        assert circuit.is_halted() is True


class TestSecondaryChannel:
    """Tests for secondary (Redis) halt channel (AC2)."""

    @pytest.mark.asyncio
    async def test_halt_publishes_to_redis(
        self, halt_circuit: HaltCircuitAdapter, fake_redis: FakeRedis
    ) -> None:
        """AC2: Halt publishes to Redis channel."""
        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Test Redis propagation",
        )

        assert len(fake_redis.published_messages) == 1
        channel, message = fake_redis.published_messages[0]
        assert channel == "governance:halt"

        data = json.loads(message)
        assert data["is_halted"] is True
        assert data["reason"] == "operator"
        assert data["message"] == "Test Redis propagation"

    @pytest.mark.asyncio
    async def test_halt_includes_all_fields_in_redis(
        self,
        halt_circuit: HaltCircuitAdapter,
        fake_redis: FakeRedis,
        fake_time: FakeTimeAuthority,
    ) -> None:
        """Redis message includes all halt status fields."""
        operator_id = uuid4()

        await halt_circuit.trigger_halt(
            reason=HaltReason.INTEGRITY_VIOLATION,
            message="Hash break",
            operator_id=operator_id,
            trace_id="trace-abc",
        )

        _, message = fake_redis.published_messages[0]
        data = json.loads(message)

        assert data["operator_id"] == str(operator_id)
        assert data["trace_id"] == "trace-abc"
        assert data["halted_at"] == fake_time.now().isoformat()


class TestTertiaryChannel:
    """Tests for tertiary (ledger) halt channel (AC3)."""

    @pytest.mark.asyncio
    async def test_halt_records_to_ledger(
        self, halt_circuit: HaltCircuitAdapter, fake_emitter: FakeEventEmitter
    ) -> None:
        """AC3: Halt records event to ledger."""
        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Test ledger recording",
            trace_id="ledger-trace",
        )

        assert len(fake_emitter.emitted_events) == 1
        event = fake_emitter.emitted_events[0]

        assert event["event_type"] == "constitutional.halt.recorded"
        assert event["trace_id"] == "ledger-trace"
        assert event["payload"]["reason"] == "operator"
        assert event["payload"]["message"] == "Test ledger recording"

    @pytest.mark.asyncio
    async def test_system_halt_uses_system_actor(
        self, halt_circuit: HaltCircuitAdapter, fake_emitter: FakeEventEmitter
    ) -> None:
        """System-triggered halt uses 'system' actor."""
        await halt_circuit.trigger_halt(
            reason=HaltReason.SYSTEM_FAULT,
            message="Detected fault",
            operator_id=None,  # No operator
        )

        event = fake_emitter.emitted_events[0]
        assert event["actor"] == "system"

    @pytest.mark.asyncio
    async def test_operator_halt_uses_operator_actor(
        self, halt_circuit: HaltCircuitAdapter, fake_emitter: FakeEventEmitter
    ) -> None:
        """Operator-triggered halt uses operator_id as actor."""
        operator_id = uuid4()

        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Manual halt",
            operator_id=operator_id,
        )

        event = fake_emitter.emitted_events[0]
        assert event["actor"] == str(operator_id)


class TestPerformance:
    """Tests for performance constraints (AC4)."""

    @pytest.mark.asyncio
    async def test_is_halted_under_1ms(self, halt_circuit: HaltCircuitAdapter) -> None:
        """AC4: is_halted() completes in <1ms."""
        # Warm up
        for _ in range(100):
            halt_circuit.is_halted()

        # Measure
        iterations = 10000
        start = time.perf_counter()
        for _ in range(iterations):
            halt_circuit.is_halted()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1, f"is_halted() took {avg_ms:.4f}ms on average (limit: <1ms)"

    @pytest.mark.asyncio
    async def test_trigger_halt_under_100ms(
        self, halt_circuit_minimal: HaltCircuitAdapter
    ) -> None:
        """AC4: trigger_halt() completes in ≤100ms."""
        start = time.perf_counter()

        await halt_circuit_minimal.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Performance test",
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms <= 100, (
            f"trigger_halt() took {elapsed_ms:.2f}ms (limit: ≤100ms)"
        )


class TestRemoteHaltHandling:
    """Tests for handling halt signals from other instances."""

    def test_handle_remote_halt_sets_flag(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """Remote halt signal sets local halt flag."""
        message_data = json.dumps(
            {
                "is_halted": True,
                "halted_at": "2026-01-15T10:30:00+00:00",
                "reason": "operator",
                "operator_id": None,
                "message": "Remote halt",
                "trace_id": "remote-trace",
            }
        )

        halt_circuit.handle_remote_halt(message_data)

        assert halt_circuit.is_halted() is True
        status = halt_circuit.get_halt_status()
        assert status.message == "Remote halt"
        assert status.trace_id == "remote-trace"

    def test_remote_halt_ignored_if_already_halted(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """Remote halt is ignored if already halted locally."""
        # First halt locally
        halt_circuit._halted.set()
        halt_circuit._status = HaltStatus.halted(
            reason=HaltReason.OPERATOR,
            message="Local halt first",
            halted_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )

        # Then receive remote halt
        message_data = json.dumps(
            {
                "is_halted": True,
                "halted_at": "2026-01-15T10:30:00+00:00",
                "reason": "system_fault",
                "message": "Remote halt second",
                "operator_id": None,
                "trace_id": None,
            }
        )
        halt_circuit.handle_remote_halt(message_data)

        # Should keep local halt status
        status = halt_circuit.get_halt_status()
        assert status.message == "Local halt first"

    def test_handle_remote_halt_invalid_json(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """Invalid JSON in remote halt is handled gracefully."""
        # Should not raise
        halt_circuit.handle_remote_halt("invalid json {{{")

        # Should not be halted
        assert halt_circuit.is_halted() is False


class TestResetForTesting:
    """Tests for reset_for_testing() method."""

    @pytest.mark.asyncio
    async def test_reset_clears_halt(self, halt_circuit: HaltCircuitAdapter) -> None:
        """reset_for_testing() clears halt state."""
        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Will be reset",
        )
        assert halt_circuit.is_halted() is True

        halt_circuit.reset_for_testing()

        assert halt_circuit.is_halted() is False
        assert halt_circuit.get_halt_status() == HaltStatus.not_halted()


class TestHaltChecker:
    """Tests for HaltChecker utility (AC6)."""

    @pytest.mark.asyncio
    async def test_check_or_raise_when_not_halted(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """check_or_raise() does nothing when not halted."""
        checker = HaltChecker(halt_circuit)

        # Should not raise
        checker.check_or_raise()

    @pytest.mark.asyncio
    async def test_check_or_raise_when_halted(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """check_or_raise() raises HaltedException when halted."""
        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Halt for test",
        )

        checker = HaltChecker(halt_circuit)

        with pytest.raises(HaltedException) as exc_info:
            checker.check_or_raise()

        assert exc_info.value.status.is_halted is True
        assert exc_info.value.status.message == "Halt for test"

    @pytest.mark.asyncio
    async def test_is_halted_delegates_to_port(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """is_halted() delegates to halt port."""
        checker = HaltChecker(halt_circuit)

        assert checker.is_halted() is False

        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Test",
        )

        assert checker.is_halted() is True

    @pytest.mark.asyncio
    async def test_get_status_returns_full_status(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """get_status() returns full HaltStatus."""
        await halt_circuit.trigger_halt(
            reason=HaltReason.INTEGRITY_VIOLATION,
            message="Hash chain break",
            trace_id="status-test",
        )

        checker = HaltChecker(halt_circuit)
        status = checker.get_status()

        assert status.is_halted is True
        assert status.reason == HaltReason.INTEGRITY_VIOLATION
        assert status.trace_id == "status-test"

    @pytest.mark.asyncio
    async def test_wrap_sync_checks_before_operation(
        self, halt_circuit: HaltCircuitAdapter
    ) -> None:
        """wrap_sync() checks halt before executing operation."""
        checker = HaltChecker(halt_circuit)
        call_count = 0

        def my_operation() -> str:
            nonlocal call_count
            call_count += 1
            return "result"

        wrapped = checker.wrap_sync(my_operation)

        # Not halted - should work
        result = wrapped()
        assert result == "result"
        assert call_count == 1

        # Halt the system
        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            message="Test wrap",
        )

        # Should raise before calling operation
        with pytest.raises(HaltedException):
            wrapped()

        # Operation should not have been called again
        assert call_count == 1


class TestThreadSafety:
    """Tests for thread safety of halt circuit."""

    @pytest.mark.asyncio
    async def test_concurrent_halt_triggers(
        self, halt_circuit_minimal: HaltCircuitAdapter
    ) -> None:
        """Concurrent halt triggers don't cause race conditions."""
        results: list[HaltStatus] = []

        async def trigger_halt(n: int) -> None:
            status = await halt_circuit_minimal.trigger_halt(
                reason=HaltReason.OPERATOR,
                message=f"Concurrent halt {n}",
            )
            results.append(status)

        # Trigger 10 halts concurrently
        await asyncio.gather(*[trigger_halt(i) for i in range(10)])

        # All should return the same status (first one wins)
        assert all(r == results[0] for r in results)
        assert halt_circuit_minimal.is_halted() is True
