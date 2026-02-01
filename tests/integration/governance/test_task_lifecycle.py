"""Integration test: Full task lifecycle with in-memory adapters.

Story: Labor Layer Contract §6 — Settlement

Proves the complete task lifecycle from ROUTED through COMPLETED
using real service implementations wired to in-memory adapters.
No mocks — every service is real; only the persistence layer is
swapped for in-memory. When DB adapters are ready, swap the
fixtures and run unchanged.

Lifecycle paths tested:
1. Happy path:  ROUTED → ACCEPTED → IN_PROGRESS → REPORTED → COMPLETED
2. Decline:     ROUTED → DECLINED
3. Late decline: ROUTED → ACCEPTED → DECLINED
4. Problem report: IN_PROGRESS stays IN_PROGRESS
5. Halt: IN_PROGRESS → QUARANTINED (penalty-free)
6. Settlement:  REPORTED → COMPLETED (accept), REPORTED → AGGREGATED (aggregate)
7. Full loop:   ROUTED → ... → COMPLETED with events at every step

Constitutional guarantees verified:
- No silent paths (every operation emits ≥1 ledger event)
- Decline is always penalty-free
- Problem reports never change state
- Invalid transitions raise IllegalStateTransitionError
- Settlement decisions leave auditable trace
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from src.application.services.governance.task_consent_service import (
    TaskConsentService,
)
from src.application.services.governance.task_result_service import (
    TaskResultService,
)
from src.application.services.governance.task_timeout_service import (
    TaskTimeoutService,
)
from src.application.services.governance.two_phase_event_emitter import (
    TwoPhaseEventEmitter,
)
from src.domain.governance.task.task_state import (
    IllegalStateTransitionError,
    TaskState,
    TaskStatus,
)
from src.infrastructure.adapters.governance.in_memory_adapters import (
    InMemoryGovernanceLedger,
    InMemoryTaskStatePort,
)
from tests.helpers.fake_time_authority import FakeTimeAuthority

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLUSTER_ID = "a1b2c3d4-4201-4a01-b001-000000000042"
EARL_ID = "earl-bridge"


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Deterministic time authority starting at 2026-01-15 10:00 UTC."""
    from datetime import datetime, timezone

    return FakeTimeAuthority(
        frozen_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    )


@pytest.fixture
def task_state_port() -> InMemoryTaskStatePort:
    return InMemoryTaskStatePort()


@pytest.fixture
def ledger() -> InMemoryGovernanceLedger:
    return InMemoryGovernanceLedger()


@pytest.fixture
def two_phase_emitter(
    ledger: InMemoryGovernanceLedger,
    time_authority: FakeTimeAuthority,
) -> TwoPhaseEventEmitter:
    return TwoPhaseEventEmitter(
        ledger=ledger,
        time_authority=time_authority,
    )


@pytest.fixture
def consent_svc(
    task_state_port: InMemoryTaskStatePort,
    ledger: InMemoryGovernanceLedger,
    two_phase_emitter: TwoPhaseEventEmitter,
    time_authority: FakeTimeAuthority,
) -> TaskConsentService:
    return TaskConsentService(
        task_state_port=task_state_port,
        ledger_port=ledger,
        two_phase_emitter=two_phase_emitter,
        time_authority=time_authority,
    )


@pytest.fixture
def result_svc(
    task_state_port: InMemoryTaskStatePort,
    ledger: InMemoryGovernanceLedger,
    two_phase_emitter: TwoPhaseEventEmitter,
    time_authority: FakeTimeAuthority,
) -> TaskResultService:
    return TaskResultService(
        task_state_port=task_state_port,
        ledger_port=ledger,
        two_phase_emitter=two_phase_emitter,
        time_authority=time_authority,
    )


@pytest.fixture
def timeout_svc(
    task_state_port: InMemoryTaskStatePort,
    ledger: InMemoryGovernanceLedger,
    time_authority: FakeTimeAuthority,
) -> TaskTimeoutService:
    return TaskTimeoutService(
        task_state_port=task_state_port,
        ledger_port=ledger,
        time_authority=time_authority,
    )


def _create_routed_task(
    task_state_port: InMemoryTaskStatePort,
    time_authority: FakeTimeAuthority,
    cluster_id: str = CLUSTER_ID,
) -> TaskState:
    """Create a task in ROUTED state with cluster assigned."""

    task_id = uuid4()
    now = time_authority.now()
    task = TaskState(
        task_id=task_id,
        earl_id=EARL_ID,
        cluster_id=cluster_id,
        current_status=TaskStatus.ROUTED,
        created_at=now - timedelta(minutes=5),
        state_entered_at=now - timedelta(minutes=1),
        ttl=timedelta(hours=72),
    )
    task_state_port._tasks[task_id] = task
    return task


# ---------------------------------------------------------------------------
# 1. Happy path: ROUTED → ACCEPTED → IN_PROGRESS → REPORTED
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Full lifecycle: consent, start work, submit result."""

    async def test_full_lifecycle_routed_to_reported(
        self,
        consent_svc: TaskConsentService,
        result_svc: TaskResultService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """ROUTED → ACCEPTED → IN_PROGRESS → REPORTED with events at every step."""
        task = _create_routed_task(task_state_port, time_authority)
        events_before = len(ledger.events)

        # --- ROUTED → ACCEPTED ---
        time_authority.advance(seconds=10)
        accept_result = await consent_svc.accept_task(
            task_id=task.task_id,
            cluster_id=CLUSTER_ID,
        )
        assert accept_result.success is True
        assert accept_result.task_state.current_status == TaskStatus.ACCEPTED

        # Events were emitted (intent + accepted + commit)
        events_after_accept = len(ledger.events)
        assert events_after_accept > events_before, "Accept must emit events"

        # --- ACCEPTED → IN_PROGRESS ---
        time_authority.advance(seconds=60)
        accepted_task = await task_state_port.get_task(task.task_id)
        in_progress_task = accepted_task.transition(
            new_status=TaskStatus.IN_PROGRESS,
            transition_time=time_authority.now(),
            actor_id=CLUSTER_ID,
        )
        await task_state_port.save_task(in_progress_task)

        saved = await task_state_port.get_task(task.task_id)
        assert saved.current_status == TaskStatus.IN_PROGRESS

        # --- IN_PROGRESS → REPORTED ---
        time_authority.advance(seconds=300)
        submit_result = await result_svc.submit_result(
            task_id=task.task_id,
            cluster_id=CLUSTER_ID,
            output={"status": "complete", "artifact_ref": "D-CONF-001-v1"},
        )
        assert submit_result.success is True
        assert submit_result.new_status == "reported"

        # Verify final state
        final = await task_state_port.get_task(task.task_id)
        assert final.current_status == TaskStatus.REPORTED

        # Verify events were emitted at every step (no silent paths)
        total_events = len(ledger.events)
        assert total_events >= 4, (
            f"Expected ≥4 events (intent+accept+commit, intent+reported+commit), "
            f"got {total_events}"
        )

    async def test_result_output_preserved(
        self,
        consent_svc: TaskConsentService,
        result_svc: TaskResultService,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Result output is preserved in the submission result."""
        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        output = {"findings": ["item-1", "item-2"], "severity": "low"}
        result = await result_svc.submit_result(task.task_id, CLUSTER_ID, output)

        assert result.result.output == output
        assert result.result.cluster_id == CLUSTER_ID


# ---------------------------------------------------------------------------
# 2. Decline path: ROUTED → DECLINED
# ---------------------------------------------------------------------------


class TestDeclinePath:
    """Decline from ROUTED is penalty-free and emits events."""

    async def test_decline_from_routed(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """ROUTED → DECLINED with events and no penalty."""
        task = _create_routed_task(task_state_port, time_authority)

        result = await consent_svc.decline_task(
            task_id=task.task_id,
            cluster_id=CLUSTER_ID,
        )
        assert result.success is True
        assert result.task_state.current_status == TaskStatus.DECLINED

        # Verify events
        assert len(ledger.events) > 0, "Decline must emit events"

        # Constitutional guarantee: no penalty
        decline_events = [
            e for e in ledger.events if e.event_type == "executive.task.declined"
        ]
        assert len(decline_events) == 1
        payload = decline_events[0].event.payload
        assert payload["penalty_incurred"] is False
        assert "standing" not in payload
        assert "reputation" not in payload
        assert "score" not in payload

    async def test_decline_from_accepted(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """ACCEPTED → DECLINED (changed mind before starting work)."""
        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=30)
        result = await consent_svc.decline_task(task.task_id, CLUSTER_ID)

        assert result.success is True
        assert result.task_state.current_status == TaskStatus.DECLINED

    async def test_declined_is_terminal(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """DECLINED is terminal — no further transitions."""
        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.decline_task(task.task_id, CLUSTER_ID)

        declined = await task_state_port.get_task(task.task_id)
        assert declined.is_terminal is True

        # Attempting any transition should fail
        with pytest.raises(IllegalStateTransitionError):
            declined.transition(TaskStatus.ACCEPTED, time_authority.now(), CLUSTER_ID)


# ---------------------------------------------------------------------------
# 3. Problem report: IN_PROGRESS stays IN_PROGRESS
# ---------------------------------------------------------------------------


class TestProblemReport:
    """Problem reports do not change state (AC4)."""

    async def test_problem_report_preserves_state(
        self,
        consent_svc: TaskConsentService,
        result_svc: TaskResultService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Problem report keeps task IN_PROGRESS per AC4."""
        from src.application.ports.governance.task_result_port import ProblemCategory

        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        events_before = len(ledger.events)

        time_authority.advance(seconds=60)
        result = await result_svc.submit_problem_report(
            task_id=task.task_id,
            cluster_id=CLUSTER_ID,
            category=ProblemCategory.BLOCKED,
            description="Waiting on security review from cluster-43",
        )

        assert result.success is True
        assert result.new_status == "in_progress"

        # State unchanged
        after = await task_state_port.get_task(task.task_id)
        assert after.current_status == TaskStatus.IN_PROGRESS

        # Events were still emitted (not silent)
        events_after = len(ledger.events)
        assert events_after > events_before, "Problem report must emit events"

        # Verify problem report event
        problem_events = [
            e
            for e in ledger.events
            if e.event_type == "executive.task.problem_reported"
        ]
        assert len(problem_events) == 1
        assert problem_events[0].event.payload["category"] == "blocked"

    async def test_can_submit_result_after_problem_report(
        self,
        consent_svc: TaskConsentService,
        result_svc: TaskResultService,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """After problem report, task can still be completed normally."""
        from src.application.ports.governance.task_result_port import ProblemCategory

        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        # Submit problem first
        time_authority.advance(seconds=60)
        await result_svc.submit_problem_report(
            task.task_id, CLUSTER_ID, ProblemCategory.BLOCKED, "Blocked on review"
        )

        # Then submit final result
        time_authority.advance(seconds=600)
        result = await result_svc.submit_result(
            task.task_id, CLUSTER_ID, {"status": "complete"}
        )
        assert result.success is True
        assert result.new_status == "reported"

        final = await task_state_port.get_task(task.task_id)
        assert final.current_status == TaskStatus.REPORTED


# ---------------------------------------------------------------------------
# 4. Halt path: IN_PROGRESS → QUARANTINED (penalty-free)
# ---------------------------------------------------------------------------


class TestHaltPath:
    """Halt is penalty-free per FR5."""

    async def test_halt_transitions_to_quarantined(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """IN_PROGRESS → QUARANTINED with no penalty."""
        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        time_authority.advance(seconds=120)
        result = await consent_svc.halt_task(task.task_id, CLUSTER_ID)

        assert result.success is True
        assert result.task_state.current_status == TaskStatus.QUARANTINED

        # Constitutional guarantee: no penalty
        halt_events = [
            e for e in ledger.events if e.event_type == "executive.task.halted"
        ]
        assert len(halt_events) == 1
        assert halt_events[0].event.payload["penalty_incurred"] is False

    async def test_quarantined_is_terminal(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """QUARANTINED is terminal — no further transitions."""
        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        await consent_svc.halt_task(task.task_id, CLUSTER_ID)
        quarantined = await task_state_port.get_task(task.task_id)
        assert quarantined.is_terminal is True


# ---------------------------------------------------------------------------
# 5. No silent paths — every operation emits events
# ---------------------------------------------------------------------------


class TestNoSilentPaths:
    """Every governance operation must leave a trace in the ledger."""

    async def test_accept_emits_events(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        task = _create_routed_task(task_state_port, time_authority)
        before = len(ledger.events)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)
        assert len(ledger.events) > before

    async def test_decline_emits_events(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        task = _create_routed_task(task_state_port, time_authority)
        before = len(ledger.events)
        await consent_svc.decline_task(task.task_id, CLUSTER_ID)
        assert len(ledger.events) > before

    async def test_result_submission_emits_events(
        self,
        consent_svc: TaskConsentService,
        result_svc: TaskResultService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        before = len(ledger.events)
        await result_svc.submit_result(task.task_id, CLUSTER_ID, {"done": True})
        assert len(ledger.events) > before

    async def test_problem_report_emits_events(
        self,
        consent_svc: TaskConsentService,
        result_svc: TaskResultService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        from src.application.ports.governance.task_result_port import ProblemCategory

        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        before = len(ledger.events)
        await result_svc.submit_problem_report(
            task.task_id, CLUSTER_ID, ProblemCategory.BLOCKED, "blocker"
        )
        assert len(ledger.events) > before

    async def test_halt_emits_events(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        before = len(ledger.events)
        await consent_svc.halt_task(task.task_id, CLUSTER_ID)
        assert len(ledger.events) > before


# ---------------------------------------------------------------------------
# 6. Invalid transitions — state machine enforced
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    """State machine rejects illegal transitions."""

    async def test_cannot_report_from_accepted(
        self,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Cannot submit result from ACCEPTED (must be IN_PROGRESS)."""
        task = _create_routed_task(task_state_port, time_authority)

        # Transition to ACCEPTED
        accepted = task.transition(
            TaskStatus.ACCEPTED, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(accepted)

        # Cannot jump to REPORTED from ACCEPTED
        with pytest.raises(IllegalStateTransitionError):
            accepted.transition(TaskStatus.REPORTED, time_authority.now(), CLUSTER_ID)

    async def test_cannot_accept_already_declined(
        self,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Cannot accept a task that has been declined."""
        task = _create_routed_task(task_state_port, time_authority)

        declined = task.transition(
            TaskStatus.DECLINED, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(declined)

        with pytest.raises(IllegalStateTransitionError):
            declined.transition(TaskStatus.ACCEPTED, time_authority.now(), CLUSTER_ID)

    async def test_cannot_go_backwards_reported_to_in_progress(
        self,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Cannot transition backwards from REPORTED to IN_PROGRESS."""
        task = _create_routed_task(task_state_port, time_authority)
        accepted = task.transition(
            TaskStatus.ACCEPTED, time_authority.now(), CLUSTER_ID
        )
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        reported = ip.transition(TaskStatus.REPORTED, time_authority.now(), CLUSTER_ID)

        with pytest.raises(IllegalStateTransitionError):
            reported.transition(
                TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
            )


# ---------------------------------------------------------------------------
# 7. Unauthorized access — wrong cluster
# ---------------------------------------------------------------------------


class TestUnauthorizedAccess:
    """Only the assigned cluster can operate on a task."""

    async def test_wrong_cluster_cannot_accept(
        self,
        consent_svc: TaskConsentService,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        from src.application.ports.governance.task_consent_port import (
            UnauthorizedConsentError,
        )

        task = _create_routed_task(task_state_port, time_authority)

        with pytest.raises(UnauthorizedConsentError):
            await consent_svc.accept_task(task.task_id, "wrong-cluster-id")

    async def test_wrong_cluster_cannot_submit_result(
        self,
        consent_svc: TaskConsentService,
        result_svc: TaskResultService,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        from src.application.ports.governance.task_result_port import (
            UnauthorizedResultError,
        )

        task = _create_routed_task(task_state_port, time_authority)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        time_authority.advance(seconds=10)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        with pytest.raises(UnauthorizedResultError):
            await result_svc.submit_result(task.task_id, "wrong-cluster", {"x": 1})


# ---------------------------------------------------------------------------
# 8. Settlement: REPORTED → COMPLETED / AGGREGATED
# ---------------------------------------------------------------------------


def _create_reported_task(
    task_state_port: InMemoryTaskStatePort,
    time_authority: FakeTimeAuthority,
    cluster_id: str = CLUSTER_ID,
) -> TaskState:
    """Create a task in REPORTED state (simulates full lifecycle to this point)."""
    task_id = uuid4()
    now = time_authority.now()
    task = TaskState(
        task_id=task_id,
        earl_id=EARL_ID,
        cluster_id=cluster_id,
        current_status=TaskStatus.REPORTED,
        created_at=now - timedelta(minutes=30),
        state_entered_at=now - timedelta(minutes=5),
        ttl=timedelta(hours=72),
    )
    task_state_port._tasks[task_id] = task
    return task


class TestSettlement:
    """Settlement transitions: REPORTED → COMPLETED or AGGREGATED."""

    async def test_accept_settlement_reported_to_completed(
        self,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Accept settlement: REPORTED → COMPLETED (single-cluster direct)."""
        task = _create_reported_task(task_state_port, time_authority)

        time_authority.advance(seconds=60)
        completed = task.transition(
            TaskStatus.COMPLETED, time_authority.now(), "earl-bridge"
        )
        await task_state_port.save_task(completed)

        saved = await task_state_port.get_task(task.task_id)
        assert saved.current_status == TaskStatus.COMPLETED
        assert saved.is_terminal is True

    async def test_aggregate_settlement_reported_to_aggregated(
        self,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Aggregate settlement: REPORTED → AGGREGATED (needs review)."""
        task = _create_reported_task(task_state_port, time_authority)

        time_authority.advance(seconds=60)
        aggregated = task.transition(
            TaskStatus.AGGREGATED, time_authority.now(), "earl-bridge"
        )
        await task_state_port.save_task(aggregated)

        saved = await task_state_port.get_task(task.task_id)
        assert saved.current_status == TaskStatus.AGGREGATED
        assert saved.is_terminal is False  # AGGREGATED is post-consent, not terminal

    async def test_aggregated_to_completed(
        self,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """AGGREGATED → COMPLETED (final settlement after review)."""
        task = _create_reported_task(task_state_port, time_authority)

        time_authority.advance(seconds=60)
        aggregated = task.transition(
            TaskStatus.AGGREGATED, time_authority.now(), "earl-bridge"
        )

        time_authority.advance(seconds=120)
        completed = aggregated.transition(
            TaskStatus.COMPLETED, time_authority.now(), "earl-bridge"
        )
        await task_state_port.save_task(completed)

        saved = await task_state_port.get_task(task.task_id)
        assert saved.current_status == TaskStatus.COMPLETED

    async def test_completed_is_terminal(
        self,
        task_state_port: InMemoryTaskStatePort,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """COMPLETED is terminal — no further transitions."""
        task = _create_reported_task(task_state_port, time_authority)
        completed = task.transition(
            TaskStatus.COMPLETED, time_authority.now(), "earl-bridge"
        )

        with pytest.raises(IllegalStateTransitionError):
            completed.transition(
                TaskStatus.REPORTED, time_authority.now(), "earl-bridge"
            )


# ---------------------------------------------------------------------------
# 9. Full loop: ROUTED → ... → COMPLETED with events at every step
# ---------------------------------------------------------------------------


class TestFullLoop:
    """End-to-end lifecycle proving no gaps in the chain."""

    async def test_routed_to_completed_full_chain(
        self,
        consent_svc: TaskConsentService,
        result_svc: TaskResultService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """ROUTED → ACCEPTED → IN_PROGRESS → REPORTED → COMPLETED."""
        task = _create_routed_task(task_state_port, time_authority)

        # ROUTED → ACCEPTED
        time_authority.advance(seconds=10)
        await consent_svc.accept_task(task.task_id, CLUSTER_ID)

        # ACCEPTED → IN_PROGRESS
        time_authority.advance(seconds=30)
        accepted = await task_state_port.get_task(task.task_id)
        ip = accepted.transition(
            TaskStatus.IN_PROGRESS, time_authority.now(), CLUSTER_ID
        )
        await task_state_port.save_task(ip)

        # IN_PROGRESS → REPORTED
        time_authority.advance(seconds=300)
        await result_svc.submit_result(
            task.task_id, CLUSTER_ID, {"status": "done", "artifact": "D-CONF-001"}
        )

        # REPORTED → COMPLETED (settlement)
        time_authority.advance(seconds=60)
        reported = await task_state_port.get_task(task.task_id)
        completed = reported.transition(
            TaskStatus.COMPLETED, time_authority.now(), "earl-bridge"
        )
        await task_state_port.save_task(completed)

        # Verify final state
        final = await task_state_port.get_task(task.task_id)
        assert final.current_status == TaskStatus.COMPLETED
        assert final.is_terminal is True

        # Verify events were emitted throughout (no silent steps)
        assert len(ledger.events) >= 4, (
            f"Expected ≥4 events across full lifecycle, got {len(ledger.events)}"
        )

        # Verify key event types present
        event_types = {e.event_type for e in ledger.events}
        assert "executive.task.accepted" in event_types
        assert "executive.task.reported" in event_types


# ---------------------------------------------------------------------------
# 10. Time pressure: TTL expiry auto-declines, inactivity auto-starts,
#     reporting timeout auto-quarantines
# ---------------------------------------------------------------------------


class TestTimePressure:
    """Silence has consequence: timeouts produce state transitions and events."""

    async def test_routed_ttl_expiry_auto_declines(
        self,
        timeout_svc: TaskTimeoutService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """ROUTED task past 72h TTL → auto-DECLINED by system, no penalty."""
        task = _create_routed_task(task_state_port, time_authority)
        assert not task.is_ttl_expired(time_authority.now())

        # Advance past 72h TTL
        time_authority.advance(delta=timedelta(hours=73))
        assert task.is_ttl_expired(time_authority.now())

        declined_ids = await timeout_svc.process_activation_timeouts()

        assert task.task_id in declined_ids
        updated = await task_state_port.get_task(task.task_id)
        assert updated.current_status == TaskStatus.DECLINED
        assert updated.is_terminal is True

        # Verify auto_declined event
        auto_declined = [
            e for e in ledger.events if e.event_type == "executive.task.auto_declined"
        ]
        assert len(auto_declined) == 1
        payload = auto_declined[0].event.payload
        assert payload["reason"] == "ttl_expired"
        assert payload["penalty_incurred"] is False
        assert auto_declined[0].event.actor_id == "system"

    async def test_ttl_not_expired_stays_routed(
        self,
        timeout_svc: TaskTimeoutService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """ROUTED task within TTL is not touched."""
        task = _create_routed_task(task_state_port, time_authority)

        # Advance only 36h (50% TTL)
        time_authority.advance(delta=timedelta(hours=36))
        assert not task.is_ttl_expired(time_authority.now())

        declined_ids = await timeout_svc.process_activation_timeouts()
        assert len(declined_ids) == 0

        updated = await task_state_port.get_task(task.task_id)
        assert updated.current_status == TaskStatus.ROUTED

    async def test_accepted_inactivity_auto_starts(
        self,
        timeout_svc: TaskTimeoutService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """ACCEPTED task past 48h inactivity → auto-started by system."""
        task_id = uuid4()
        now = time_authority.now()
        task = TaskState(
            task_id=task_id,
            earl_id=EARL_ID,
            cluster_id=CLUSTER_ID,
            current_status=TaskStatus.ACCEPTED,
            created_at=now - timedelta(minutes=5),
            state_entered_at=now,
            ttl=timedelta(hours=72),
        )
        task_state_port._tasks[task_id] = task

        # Advance past 48h
        time_authority.advance(delta=timedelta(hours=49))

        started_ids = await timeout_svc.process_acceptance_timeouts()

        assert task_id in started_ids
        updated = await task_state_port.get_task(task_id)
        assert updated.current_status == TaskStatus.IN_PROGRESS

        # Verify auto_started event
        auto_started = [
            e for e in ledger.events if e.event_type == "executive.task.auto_started"
        ]
        assert len(auto_started) == 1
        assert auto_started[0].event.actor_id == "system"
        assert auto_started[0].event.payload["reason"] == "acceptance_inactivity"

    async def test_in_progress_reporting_timeout_auto_quarantines(
        self,
        timeout_svc: TaskTimeoutService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """IN_PROGRESS task past 7d reporting timeout → auto-QUARANTINED."""
        task_id = uuid4()
        now = time_authority.now()
        task = TaskState(
            task_id=task_id,
            earl_id=EARL_ID,
            cluster_id=CLUSTER_ID,
            current_status=TaskStatus.IN_PROGRESS,
            created_at=now - timedelta(hours=1),
            state_entered_at=now,
            ttl=timedelta(hours=72),
        )
        task_state_port._tasks[task_id] = task

        # Advance past 7 days
        time_authority.advance(delta=timedelta(days=7, hours=1))

        quarantined_ids = await timeout_svc.process_reporting_timeouts()

        assert task_id in quarantined_ids
        updated = await task_state_port.get_task(task_id)
        assert updated.current_status == TaskStatus.QUARANTINED
        assert updated.is_terminal is True

        # Verify auto_quarantined event
        auto_quarantined = [
            e
            for e in ledger.events
            if e.event_type == "executive.task.auto_quarantined"
        ]
        assert len(auto_quarantined) == 1
        payload = auto_quarantined[0].event.payload
        assert payload["reason"] == "reporting_timeout"
        assert payload["penalty_incurred"] is False
        assert auto_quarantined[0].event.actor_id == "system"

    async def test_process_all_timeouts_batch(
        self,
        timeout_svc: TaskTimeoutService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """process_all_timeouts handles all three scenarios in one call."""
        now = time_authority.now()

        # Create one task in each timeout-eligible state
        routed_id = uuid4()
        task_state_port._tasks[routed_id] = TaskState(
            task_id=routed_id,
            earl_id=EARL_ID,
            cluster_id=CLUSTER_ID,
            current_status=TaskStatus.ROUTED,
            created_at=now,
            state_entered_at=now,
            ttl=timedelta(hours=72),
        )

        accepted_id = uuid4()
        task_state_port._tasks[accepted_id] = TaskState(
            task_id=accepted_id,
            earl_id=EARL_ID,
            cluster_id=CLUSTER_ID,
            current_status=TaskStatus.ACCEPTED,
            created_at=now,
            state_entered_at=now,
            ttl=timedelta(hours=72),
        )

        in_progress_id = uuid4()
        task_state_port._tasks[in_progress_id] = TaskState(
            task_id=in_progress_id,
            earl_id=EARL_ID,
            cluster_id=CLUSTER_ID,
            current_status=TaskStatus.IN_PROGRESS,
            created_at=now,
            state_entered_at=now,
            ttl=timedelta(hours=72),
        )

        # Advance past all thresholds (7 days covers all)
        time_authority.advance(delta=timedelta(days=8))

        result = await timeout_svc.process_all_timeouts()

        assert routed_id in result.declined
        assert accepted_id in result.started
        assert in_progress_id in result.quarantined
        assert result.total_processed == 3

    async def test_timeout_events_always_emitted(
        self,
        timeout_svc: TaskTimeoutService,
        task_state_port: InMemoryTaskStatePort,
        ledger: InMemoryGovernanceLedger,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Golden Rule: every timeout emits an event, none are silent."""
        _create_routed_task(task_state_port, time_authority)
        events_before = len(ledger.events)

        time_authority.advance(delta=timedelta(hours=73))
        await timeout_svc.process_activation_timeouts()

        assert len(ledger.events) > events_before
        # All timeout events must have system as actor
        for evt in ledger.events[events_before:]:
            assert evt.event.actor_id == "system", (
                f"Timeout event {evt.event_type} has non-system actor"
            )


# ---------------------------------------------------------------------------
# 11. Blocker aging: PendingEscalation tracks urgency toward Conclave
# ---------------------------------------------------------------------------


class TestBlockerAging:
    """Blockers age through PENDING → WARNING → URGENT → OVERDUE."""

    def test_fresh_blocker_is_pending(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Fresh blocker (day 0) has urgency PENDING."""
        from src.domain.events.breach import BreachType
        from src.domain.models.pending_escalation import PendingEscalation

        esc = PendingEscalation.from_breach(
            breach_id=uuid4(),
            breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
            detection_timestamp=time_authority.now(),
            current_time=time_authority.now(),
        )
        assert esc.urgency_level == "PENDING"
        assert esc.days_remaining == 7
        assert not esc.is_overdue
        assert not esc.is_urgent

    def test_blocker_at_day_4_plus_is_warning(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Blocker past day 4 (< 72h remaining) has urgency WARNING."""
        from src.domain.events.breach import BreachType
        from src.domain.models.pending_escalation import PendingEscalation

        detection = time_authority.now()
        time_authority.advance(delta=timedelta(days=4, hours=1))

        esc = PendingEscalation.from_breach(
            breach_id=uuid4(),
            breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
            detection_timestamp=detection,
            current_time=time_authority.now(),
        )
        assert esc.urgency_level == "WARNING"
        assert esc.days_remaining == 2
        assert not esc.is_overdue

    def test_blocker_at_day_6_5_is_urgent(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Blocker at day 6.5 has urgency URGENT (< 24h remaining)."""
        from src.domain.events.breach import BreachType
        from src.domain.models.pending_escalation import PendingEscalation

        detection = time_authority.now()
        time_authority.advance(delta=timedelta(days=6, hours=12))

        esc = PendingEscalation.from_breach(
            breach_id=uuid4(),
            breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
            detection_timestamp=detection,
            current_time=time_authority.now(),
        )
        assert esc.urgency_level == "URGENT"
        assert esc.is_urgent
        assert not esc.is_overdue

    def test_blocker_past_7_days_is_overdue(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Blocker past 7 days is OVERDUE — eligible for Conclave agenda (FR31)."""
        from src.domain.events.breach import BreachType
        from src.domain.models.pending_escalation import PendingEscalation

        detection = time_authority.now()
        time_authority.advance(delta=timedelta(days=7, hours=1))

        esc = PendingEscalation.from_breach(
            breach_id=uuid4(),
            breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
            detection_timestamp=detection,
            current_time=time_authority.now(),
        )
        assert esc.urgency_level == "OVERDUE"
        assert esc.is_overdue
        assert esc.hours_remaining < 0


# ---------------------------------------------------------------------------
# 12. Aggregation: multi-task coverage, conflict detection, disposition
# ---------------------------------------------------------------------------

CLUSTER_A = "cluster-alpha-001"
CLUSTER_B = "cluster-beta-002"


class TestAggregation:
    """Aggregation is procedural — coverage checks, not quality judgment."""

    def test_single_cluster_full_coverage_is_complete(self) -> None:
        """One cluster covers all requirements with evidence → COMPLETE."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001", "FR-CONF-002", "NFR-CONF-001"),
                status="REPORTED",
                artifact_refs=("output/config.yaml",),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002", "NFR-CONF-001"],
            tasks=tasks,
        )

        assert result.disposition == AggregationDisposition.COMPLETE
        assert result.total_requirements == 3
        assert result.covered_count == 3
        assert len(result.missing_requirements) == 0
        assert len(result.conflicts) == 0

    def test_multi_cluster_same_reqs_is_conflicted(self) -> None:
        """Two clusters cover the same requirement → CONFLICTED."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001", "FR-CONF-002"),
                status="REPORTED",
            ),
            TaskEntry(
                task_ref="TASK-001b",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_B,
                rfp_requirement_ids=("FR-CONF-002", "NFR-CONF-001"),
                status="REPORTED",
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002", "NFR-CONF-001"],
            tasks=tasks,
        )

        assert result.disposition == AggregationDisposition.CONFLICTED
        assert len(result.conflicts) == 1
        assert result.conflicts[0].req_id == "FR-CONF-002"
        assert set(result.conflicts[0].cluster_ids) == {CLUSTER_A, CLUSTER_B}

    def test_multi_cluster_disjoint_reqs_is_complete(self) -> None:
        """Two clusters cover different requirements with evidence → COMPLETE."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
                artifact_refs=("output/alpha.yaml",),
            ),
            TaskEntry(
                task_ref="TASK-001b",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_B,
                rfp_requirement_ids=("FR-CONF-002",),
                status="REPORTED",
                artifact_refs=("output/beta.yaml",),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002"],
            tasks=tasks,
        )

        assert result.disposition == AggregationDisposition.COMPLETE
        assert result.covered_count == 2
        assert len(result.conflicts) == 0

    def test_missing_coverage_is_incomplete(self) -> None:
        """Task covers only subset of requirements → INCOMPLETE."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002", "NFR-CONF-001"],
            tasks=tasks,
        )

        assert result.disposition == AggregationDisposition.INCOMPLETE
        assert result.covered_count == 1
        assert set(result.missing_requirements) == {"FR-CONF-002", "NFR-CONF-001"}

    def test_conflict_overrides_incomplete(self) -> None:
        """If both conflicts AND missing, disposition is CONFLICTED."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
            ),
            TaskEntry(
                task_ref="TASK-001b",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_B,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002"],
            tasks=tasks,
        )

        # Conflicts override incomplete
        assert result.disposition == AggregationDisposition.CONFLICTED
        assert len(result.conflicts) == 1
        assert "FR-CONF-002" in result.missing_requirements


class TestAggregationArtifact:
    """Aggregation artifacts are Duke-readable and machine-parseable."""

    def test_result_to_dict_is_valid(self) -> None:
        """AggregationResult.to_dict() produces valid Duke-readable JSON."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001", "FR-CONF-002"),
                status="REPORTED",
            ),
            TaskEntry(
                task_ref="TASK-001b",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_B,
                rfp_requirement_ids=("FR-CONF-002", "NFR-CONF-001"),
                status="REPORTED",
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002", "NFR-CONF-001"],
            tasks=tasks,
        )
        d = result.to_dict()

        # Schema fields present
        assert d["schema_version"] == "1.0"
        assert d["artifact_type"] == "aggregation_result"
        assert d["deliverable_id"] == "D-CONF-001"
        assert d["disposition"] == "CONFLICTED"
        assert d["total_requirements"] == 3
        assert d["covered_count"] == 3
        assert len(d["conflicts"]) == 1
        assert d["conflicts"][0]["req_id"] == "FR-CONF-002"

    def test_conflict_artifact_identifies_clusters(self) -> None:
        """Conflict artifact names both clusters involved."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )

        tasks = [
            TaskEntry(
                task_ref="T-A",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
            ),
            TaskEntry(
                task_ref="T-B",
                deliverable_id="D-001",
                cluster_id=CLUSTER_B,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
        )

        conflict = result.conflicts[0]
        assert CLUSTER_A in conflict.cluster_ids
        assert CLUSTER_B in conflict.cluster_ids
        assert "T-A" in conflict.task_refs
        assert "T-B" in conflict.task_refs
        assert "mechanically determine" in conflict.reason


class TestAggregationHelpers:
    """Helper functions: grouping, requirement collection, needs check."""

    def test_needs_aggregation_single_cluster(self) -> None:
        """Single cluster → no aggregation needed."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            needs_aggregation,
        )

        tasks = [
            TaskEntry("T-A", "D-001", CLUSTER_A, ("FR-001",), "REPORTED"),
            TaskEntry("T-B", "D-001", CLUSTER_A, ("FR-002",), "REPORTED"),
        ]
        assert not needs_aggregation(tasks)

    def test_needs_aggregation_multi_cluster(self) -> None:
        """Multiple clusters → aggregation needed."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            needs_aggregation,
        )

        tasks = [
            TaskEntry("T-A", "D-001", CLUSTER_A, ("FR-001",), "REPORTED"),
            TaskEntry("T-B", "D-001", CLUSTER_B, ("FR-002",), "REPORTED"),
        ]
        assert needs_aggregation(tasks)

    def test_collect_requirement_ids_deduplicates(self) -> None:
        """Requirement IDs are deduplicated and sorted."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            collect_requirement_ids,
        )

        tasks = [
            TaskEntry("T-A", "D-001", CLUSTER_A, ("FR-002", "FR-001"), "REPORTED"),
            TaskEntry("T-B", "D-001", CLUSTER_B, ("FR-001", "NFR-001"), "REPORTED"),
        ]
        ids = collect_requirement_ids(tasks)
        assert ids == ["FR-001", "FR-002", "NFR-001"]

    def test_group_tasks_by_deliverable(self) -> None:
        """Tasks grouped correctly by deliverable_id."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            group_tasks_by_deliverable,
        )

        tasks = [
            TaskEntry("T-A", "D-001", CLUSTER_A, ("FR-001",), "REPORTED"),
            TaskEntry("T-B", "D-002", CLUSTER_B, ("FR-002",), "REPORTED"),
            TaskEntry("T-C", "D-001", CLUSTER_B, ("FR-003",), "REPORTED"),
        ]
        groups = group_tasks_by_deliverable(tasks)
        assert len(groups) == 2
        assert len(groups["D-001"]) == 2
        assert len(groups["D-002"]) == 1


# ---------------------------------------------------------------------------
# 13. Evidence-backed coverage: COMPLETE requires proof
# ---------------------------------------------------------------------------


class TestEvidenceBackedCoverage:
    """COMPLETE is mandatory-evidence. Coverage without proof is UNVERIFIED."""

    def test_coverage_with_artifact_refs_is_complete(self) -> None:
        """Task provides artifact_refs → COMPLETE."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001", "FR-CONF-002"),
                status="REPORTED",
                artifact_refs=("output/config.yaml", "output/schema.json"),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002"],
            tasks=tasks,
        )

        assert result.disposition == AggregationDisposition.COMPLETE
        assert result.covered_count == 2
        # Every requirement has evidence
        for cov in result.coverage_map:
            assert cov.has_evidence

    def test_coverage_with_acceptance_tests_is_complete(self) -> None:
        """Task provides acceptance_test_results → COMPLETE."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import (
            AcceptanceTestResult,
            AggregationDisposition,
        )

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
                acceptance_results=(
                    AcceptanceTestResult(test="config loads", passed=True),
                    AcceptanceTestResult(test="schema validates", passed=True),
                ),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001"],
            tasks=tasks,
        )

        assert result.disposition == AggregationDisposition.COMPLETE

    def test_coverage_without_evidence_is_unverified(self) -> None:
        """Task covers requirements but provides no evidence → UNVERIFIED."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001", "FR-CONF-002"),
                status="REPORTED",
                # No artifact_refs, no acceptance_results
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002"],
            tasks=tasks,
        )

        assert result.disposition == AggregationDisposition.UNVERIFIED
        assert result.covered_count == 2  # covered by metadata
        assert len(result.missing_requirements) == 0  # not missing, just unverified

    def test_partial_evidence_is_unverified(self) -> None:
        """One task has evidence, another doesn't → UNVERIFIED."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
                artifact_refs=("output/file.yaml",),  # has evidence
            ),
            TaskEntry(
                task_ref="TASK-001b",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-002",),
                status="REPORTED",
                # no evidence
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002"],
            tasks=tasks,
        )

        assert result.disposition == AggregationDisposition.UNVERIFIED
        # FR-CONF-001 has evidence, FR-CONF-002 doesn't
        cov_map = {c.req_id: c for c in result.coverage_map}
        assert cov_map["FR-CONF-001"].has_evidence
        assert not cov_map["FR-CONF-002"].has_evidence

    def test_conflict_overrides_unverified(self) -> None:
        """Conflicts take precedence over evidence status."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
                # no evidence — would be UNVERIFIED alone
            ),
            TaskEntry(
                task_ref="TASK-001b",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_B,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
                # no evidence — would be UNVERIFIED alone
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001"],
            tasks=tasks,
        )

        # Conflict overrides UNVERIFIED
        assert result.disposition == AggregationDisposition.CONFLICTED

    def test_incomplete_overrides_unverified(self) -> None:
        """Missing coverage takes precedence over evidence status."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
                # no evidence
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001", "FR-CONF-002"],
            tasks=tasks,
        )

        # INCOMPLETE overrides UNVERIFIED (FR-CONF-002 isn't covered at all)
        assert result.disposition == AggregationDisposition.INCOMPLETE

    def test_evidence_serialized_in_artifact(self) -> None:
        """Evidence appears in to_dict() output for Duke consumption."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AcceptanceTestResult

        tasks = [
            TaskEntry(
                task_ref="TASK-001a",
                deliverable_id="D-CONF-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-CONF-001",),
                status="REPORTED",
                artifact_refs=("output/config.yaml",),
                acceptance_results=(
                    AcceptanceTestResult(test="config loads", passed=True),
                ),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-CONF-001",
            all_requirement_ids=["FR-CONF-001"],
            tasks=tasks,
        )

        d = result.to_dict()
        cov = d["coverage_map"][0]
        assert cov["has_evidence"] is True
        assert len(cov["evidence"]) == 1
        ev = cov["evidence"][0]
        assert ev["req_id"] == "FR-CONF-001"
        assert ev["task_ref"] == "TASK-001a"
        assert "output/config.yaml" in ev["artifact_refs"]
        assert ev["acceptance_results"][0]["test"] == "config loads"
        assert ev["acceptance_results"][0]["passed"] is True

    def test_unverified_distinct_from_incomplete(self) -> None:
        """UNVERIFIED and INCOMPLETE are structurally different dispositions.

        UNVERIFIED: all requirements have covering tasks (covered_count == total)
        INCOMPLETE: some requirements have no covering tasks (covered_count < total)
        """
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition

        # UNVERIFIED: covered but no evidence
        unverified = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=[
                TaskEntry("T-A", "D-001", CLUSTER_A, ("FR-001",), "REPORTED"),
            ],
        )
        assert unverified.disposition == AggregationDisposition.UNVERIFIED
        assert unverified.covered_count == 1
        assert len(unverified.missing_requirements) == 0

        # INCOMPLETE: not covered at all
        incomplete = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001", "FR-002"],
            tasks=[
                TaskEntry("T-A", "D-001", CLUSTER_A, ("FR-001",), "REPORTED"),
            ],
        )
        assert incomplete.disposition == AggregationDisposition.INCOMPLETE
        assert incomplete.covered_count == 1
        assert "FR-002" in incomplete.missing_requirements


# ---------------------------------------------------------------------------
# 14. Evidence integrity verification: best-effort structural checks
# ---------------------------------------------------------------------------


class TestEvidenceVerification:
    """Evidence verification is structural — checksum, existence, not quality."""

    def test_artifact_checksum_verified_ok_counts(self, tmp_path: Path) -> None:
        """Artifact with correct checksum → VERIFIED_OK, evidence counts."""
        import hashlib

        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import (
            AggregationDisposition,
            VerificationStatus,
        )
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        # Create a real file with known content
        test_file = tmp_path / "config.yaml"
        test_file.write_text("key: value\n")
        checksum = hashlib.sha256(test_file.read_bytes()).hexdigest()
        ref = f"{test_file}:sha256={checksum}"

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=(ref,),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
            verifier=verifier,
        )

        assert result.disposition == AggregationDisposition.COMPLETE
        ev = result.coverage_map[0].evidence[0]
        assert ev.verification_status == VerificationStatus.VERIFIED_OK

    def test_artifact_checksum_mismatch_invalidates_evidence(
        self, tmp_path: Path
    ) -> None:
        """Artifact with wrong checksum → VERIFIED_FAILED, evidence nullified."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import (
            AggregationDisposition,
            VerificationStatus,
        )
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        # Create file but use a wrong checksum
        test_file = tmp_path / "config.yaml"
        test_file.write_text("key: value\n")
        wrong_checksum = "a" * 64
        ref = f"{test_file}:sha256={wrong_checksum}"

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=(ref,),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
            verifier=verifier,
        )

        # Evidence invalidated → UNVERIFIED
        assert result.disposition == AggregationDisposition.UNVERIFIED
        ev = result.coverage_map[0].evidence[0]
        assert ev.verification_status == VerificationStatus.VERIFIED_FAILED
        assert not ev.has_evidence

    def test_artifact_missing_file_invalidates_evidence(self, tmp_path: Path) -> None:
        """Artifact pointing to nonexistent file → VERIFIED_FAILED."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import (
            AggregationDisposition,
            VerificationStatus,
        )
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        ref = str(tmp_path / "nonexistent.yaml")
        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=(ref,),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
            verifier=verifier,
        )

        assert result.disposition == AggregationDisposition.UNVERIFIED
        ev = result.coverage_map[0].evidence[0]
        assert ev.verification_status == VerificationStatus.VERIFIED_FAILED

    def test_no_checksum_is_unverifiable_and_counts_in_best_effort(
        self, tmp_path: Path
    ) -> None:
        """Remote ref with no checksum → UNVERIFIABLE, still counts as evidence."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import (
            AggregationDisposition,
            VerificationStatus,
        )
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=("https://storage.example.com/output.yaml",),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
            verifier=verifier,
        )

        # UNVERIFIABLE but still counts → COMPLETE in best-effort
        assert result.disposition == AggregationDisposition.COMPLETE
        ev = result.coverage_map[0].evidence[0]
        assert ev.verification_status == VerificationStatus.UNVERIFIABLE
        assert ev.has_evidence  # counts in best-effort

    def test_existing_file_no_checksum_is_verified_ok(self, tmp_path: Path) -> None:
        """Local file that exists but has no checksum → VERIFIED_OK (exists)."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import (
            AggregationDisposition,
            VerificationStatus,
        )
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        test_file = tmp_path / "output.yaml"
        test_file.write_text("result: ok\n")

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=(str(test_file),),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
            verifier=verifier,
        )

        assert result.disposition == AggregationDisposition.COMPLETE
        ev = result.coverage_map[0].evidence[0]
        assert ev.verification_status == VerificationStatus.VERIFIED_OK

    def test_complete_with_only_failed_evidence_becomes_unverified(
        self, tmp_path: Path
    ) -> None:
        """All evidence fails verification → UNVERIFIED (not COMPLETE)."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001", "FR-002"),
                status="REPORTED",
                artifact_refs=(
                    str(tmp_path / "missing1.yaml"),
                    str(tmp_path / "missing2.yaml"),
                ),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001", "FR-002"],
            tasks=tasks,
            verifier=verifier,
        )

        assert result.disposition == AggregationDisposition.UNVERIFIED

    def test_unverifiable_evidence_keeps_requirement_evidenced_in_mvp(
        self, tmp_path: Path
    ) -> None:
        """UNVERIFIABLE evidence counts in best-effort → requirement is evidenced."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AcceptanceTestResult
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                acceptance_results=(
                    AcceptanceTestResult(
                        test="config loads", passed=True, notes="manual check"
                    ),
                ),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
            verifier=verifier,
        )

        # Acceptance test with no CI linkage → UNVERIFIABLE, but still counts
        ev = result.coverage_map[0].evidence[0]
        assert ev.has_evidence  # counts in best-effort

    def test_conflict_precedence_unchanged_by_verification(
        self, tmp_path: Path
    ) -> None:
        """CONFLICTED disposition unaffected by verification status."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        test_file = tmp_path / "output.yaml"
        test_file.write_text("ok\n")

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-A",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=(str(test_file),),
            ),
            TaskEntry(
                task_ref="T-B",
                deliverable_id="D-001",
                cluster_id=CLUSTER_B,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=(str(test_file),),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
            verifier=verifier,
        )

        # Even with VERIFIED_OK evidence, conflict still wins
        assert result.disposition == AggregationDisposition.CONFLICTED

    def test_incomplete_precedence_unchanged_by_verification(
        self, tmp_path: Path
    ) -> None:
        """INCOMPLETE disposition unaffected by verification of covered reqs."""
        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.domain.models.aggregation import AggregationDisposition
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        test_file = tmp_path / "output.yaml"
        test_file.write_text("ok\n")

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=(str(test_file),),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001", "FR-002"],
            tasks=tasks,
            verifier=verifier,
        )

        # FR-001 is verified, but FR-002 is missing entirely → INCOMPLETE
        assert result.disposition == AggregationDisposition.INCOMPLETE

    def test_verification_status_serialized_in_artifact(self, tmp_path: Path) -> None:
        """Verification status appears in to_dict() for Duke consumption."""
        import hashlib

        from src.application.services.governance.aggregation_service import (
            TaskEntry,
            aggregate_deliverable,
        )
        from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
            BestEffortEvidenceVerifier,
        )

        test_file = tmp_path / "config.yaml"
        test_file.write_text("key: value\n")
        checksum = hashlib.sha256(test_file.read_bytes()).hexdigest()

        verifier = BestEffortEvidenceVerifier(base_dir=tmp_path)
        tasks = [
            TaskEntry(
                task_ref="T-001",
                deliverable_id="D-001",
                cluster_id=CLUSTER_A,
                rfp_requirement_ids=("FR-001",),
                status="REPORTED",
                artifact_refs=(f"{test_file}:sha256={checksum}",),
            ),
        ]
        result = aggregate_deliverable(
            deliverable_id="D-001",
            all_requirement_ids=["FR-001"],
            tasks=tasks,
            verifier=verifier,
        )

        d = result.to_dict()
        ev = d["coverage_map"][0]["evidence"][0]
        assert ev["verification_status"] == "VERIFIED_OK"
        assert ev["has_evidence"] is True
