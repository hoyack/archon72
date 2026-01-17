"""Unit tests for exit port interface.

Story: consent-gov-7.1: Exit Request Processing

Tests for:
- ExitPort protocol definition
- No barrier methods exist
- Interface completeness
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.application.ports.governance.exit_port import ExitPort
from src.domain.governance.exit.exit_request import ExitRequest
from src.domain.governance.exit.exit_result import ExitResult
from src.domain.governance.exit.exit_status import ExitStatus


# =============================================================================
# Protocol Interface Tests
# =============================================================================


class TestExitPortInterface:
    """Tests for ExitPort protocol interface."""

    def test_record_exit_request_method_exists(self):
        """ExitPort has record_exit_request method."""
        assert hasattr(ExitPort, "record_exit_request")

    def test_record_exit_result_method_exists(self):
        """ExitPort has record_exit_result method."""
        assert hasattr(ExitPort, "record_exit_result")

    def test_get_exit_request_method_exists(self):
        """ExitPort has get_exit_request method."""
        assert hasattr(ExitPort, "get_exit_request")

    def test_get_exit_result_method_exists(self):
        """ExitPort has get_exit_result method."""
        assert hasattr(ExitPort, "get_exit_result")

    def test_has_cluster_exited_method_exists(self):
        """ExitPort has has_cluster_exited method."""
        assert hasattr(ExitPort, "has_cluster_exited")

    def test_get_cluster_active_tasks_method_exists(self):
        """ExitPort has get_cluster_active_tasks method."""
        assert hasattr(ExitPort, "get_cluster_active_tasks")

    def test_get_exit_history_method_exists(self):
        """ExitPort has get_exit_history method."""
        assert hasattr(ExitPort, "get_exit_history")


# =============================================================================
# No Barrier Methods Tests (NFR-EXIT-01)
# =============================================================================


class TestNoBarrierMethods:
    """Tests ensuring no barrier methods exist on ExitPort.

    Per NFR-EXIT-01: Exit completes in ≤2 message round-trips.
    No barrier methods should exist on the port interface.
    """

    def test_no_confirm_exit_method(self):
        """ExitPort has no confirm_exit method."""
        assert not hasattr(ExitPort, "confirm_exit")

    def test_no_approve_exit_method(self):
        """ExitPort has no approve_exit method."""
        assert not hasattr(ExitPort, "approve_exit")

    def test_no_reject_exit_method(self):
        """ExitPort has no reject_exit method."""
        assert not hasattr(ExitPort, "reject_exit")

    def test_no_cancel_exit_method(self):
        """ExitPort has no cancel_exit method."""
        assert not hasattr(ExitPort, "cancel_exit")

    def test_no_delay_exit_method(self):
        """ExitPort has no delay_exit method."""
        assert not hasattr(ExitPort, "delay_exit")

    def test_no_require_reason_method(self):
        """ExitPort has no require_reason method."""
        assert not hasattr(ExitPort, "require_reason")

    def test_no_wait_for_exit_method(self):
        """ExitPort has no wait_for_exit method."""
        assert not hasattr(ExitPort, "wait_for_exit")

    def test_no_set_waiting_period_method(self):
        """ExitPort has no set_waiting_period method."""
        assert not hasattr(ExitPort, "set_waiting_period")


# =============================================================================
# Fake Implementation for Testing
# =============================================================================


class FakeExitPort:
    """Fake implementation of ExitPort for testing."""

    def __init__(self):
        self._requests: dict[UUID, ExitRequest] = {}
        self._results: dict[UUID, ExitResult] = {}
        self._exited_clusters: set[UUID] = set()
        self._active_tasks: dict[UUID, list[UUID]] = {}

    async def record_exit_request(self, request: ExitRequest) -> None:
        """Record exit request."""
        self._requests[request.request_id] = request

    async def record_exit_result(self, result: ExitResult) -> None:
        """Record exit result."""
        self._results[result.request_id] = result
        if result.status == ExitStatus.COMPLETED:
            self._exited_clusters.add(result.cluster_id)

    async def get_exit_request(self, request_id: UUID) -> ExitRequest | None:
        """Get exit request by ID."""
        return self._requests.get(request_id)

    async def get_exit_result(self, request_id: UUID) -> ExitResult | None:
        """Get exit result by request ID."""
        return self._results.get(request_id)

    async def has_cluster_exited(self, cluster_id: UUID) -> bool:
        """Check if cluster has exited."""
        return cluster_id in self._exited_clusters

    async def get_cluster_active_tasks(self, cluster_id: UUID) -> list[UUID]:
        """Get active tasks for cluster."""
        return self._active_tasks.get(cluster_id, [])

    async def get_exit_history(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[ExitResult]:
        """Get exit history."""
        results = list(self._results.values())
        if since:
            results = [r for r in results if r.initiated_at >= since]
        if until:
            results = [r for r in results if r.initiated_at <= until]
        return results

    # Helper methods for test setup
    def set_active_tasks(self, cluster_id: UUID, task_ids: list[UUID]) -> None:
        """Set active tasks for a cluster (test helper)."""
        self._active_tasks[cluster_id] = task_ids

    def mark_as_exited(self, cluster_id: UUID) -> None:
        """Mark a cluster as exited (test helper)."""
        self._exited_clusters.add(cluster_id)


# =============================================================================
# Fake Implementation Tests
# =============================================================================


@pytest.fixture
def fake_exit_port() -> FakeExitPort:
    """Create a fake exit port."""
    return FakeExitPort()


@pytest.fixture
def now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class TestFakeExitPort:
    """Tests for FakeExitPort implementation."""

    @pytest.mark.asyncio
    async def test_record_and_get_exit_request(self, fake_exit_port, now):
        """Can record and retrieve exit request."""
        request = ExitRequest(
            request_id=uuid4(),
            cluster_id=uuid4(),
            requested_at=now,
            tasks_at_request=(uuid4(),),
        )

        await fake_exit_port.record_exit_request(request)
        retrieved = await fake_exit_port.get_exit_request(request.request_id)

        assert retrieved == request

    @pytest.mark.asyncio
    async def test_record_and_get_exit_result(self, fake_exit_port, now):
        """Can record and retrieve exit result."""
        result = ExitResult(
            request_id=uuid4(),
            cluster_id=uuid4(),
            status=ExitStatus.COMPLETED,
            initiated_at=now,
            completed_at=now,
            tasks_affected=1,
            obligations_released=1,
            round_trips=2,
        )

        await fake_exit_port.record_exit_result(result)
        retrieved = await fake_exit_port.get_exit_result(result.request_id)

        assert retrieved == result

    @pytest.mark.asyncio
    async def test_has_cluster_exited_false_initially(self, fake_exit_port):
        """has_cluster_exited returns False initially."""
        cluster_id = uuid4()
        assert await fake_exit_port.has_cluster_exited(cluster_id) is False

    @pytest.mark.asyncio
    async def test_has_cluster_exited_true_after_completed_result(self, fake_exit_port, now):
        """has_cluster_exited returns True after completed exit."""
        cluster_id = uuid4()
        result = ExitResult(
            request_id=uuid4(),
            cluster_id=cluster_id,
            status=ExitStatus.COMPLETED,
            initiated_at=now,
            completed_at=now,
            tasks_affected=0,
            obligations_released=0,
            round_trips=2,
        )

        await fake_exit_port.record_exit_result(result)

        assert await fake_exit_port.has_cluster_exited(cluster_id) is True

    @pytest.mark.asyncio
    async def test_get_cluster_active_tasks_empty_default(self, fake_exit_port):
        """get_cluster_active_tasks returns empty list by default."""
        cluster_id = uuid4()
        tasks = await fake_exit_port.get_cluster_active_tasks(cluster_id)
        assert tasks == []

    @pytest.mark.asyncio
    async def test_get_cluster_active_tasks_with_data(self, fake_exit_port):
        """get_cluster_active_tasks returns set tasks."""
        cluster_id = uuid4()
        task_ids = [uuid4(), uuid4()]
        fake_exit_port.set_active_tasks(cluster_id, task_ids)

        tasks = await fake_exit_port.get_cluster_active_tasks(cluster_id)
        assert tasks == task_ids

    @pytest.mark.asyncio
    async def test_get_exit_history_empty(self, fake_exit_port):
        """get_exit_history returns empty list when no exits."""
        history = await fake_exit_port.get_exit_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_get_exit_history_with_data(self, fake_exit_port, now):
        """get_exit_history returns recorded results."""
        result1 = ExitResult(
            request_id=uuid4(),
            cluster_id=uuid4(),
            status=ExitStatus.COMPLETED,
            initiated_at=now,
            completed_at=now,
            tasks_affected=1,
            obligations_released=1,
            round_trips=2,
        )
        result2 = ExitResult(
            request_id=uuid4(),
            cluster_id=uuid4(),
            status=ExitStatus.COMPLETED,
            initiated_at=now,
            completed_at=now,
            tasks_affected=2,
            obligations_released=2,
            round_trips=2,
        )

        await fake_exit_port.record_exit_result(result1)
        await fake_exit_port.record_exit_result(result2)

        history = await fake_exit_port.get_exit_history()
        assert len(history) == 2
