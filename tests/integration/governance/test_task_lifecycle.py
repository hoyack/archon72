"""Integration test: Full task lifecycle with in-memory adapters.

Story: Labor Layer Contract §6 — Settlement

Proves the complete task lifecycle from ROUTED through REPORTED
using real service implementations wired to in-memory adapters.
No mocks — every service is real; only the persistence layer is
swapped for in-memory. When DB adapters are ready, swap the
fixtures and run unchanged.

Lifecycle paths tested:
1. Happy path:  ROUTED → ACCEPTED → IN_PROGRESS → REPORTED
2. Decline:     ROUTED → DECLINED
3. Late decline: ROUTED → ACCEPTED → DECLINED
4. Problem report: IN_PROGRESS stays IN_PROGRESS
5. Halt: IN_PROGRESS → QUARANTINED (penalty-free)

Constitutional guarantees verified:
- No silent paths (every operation emits ≥1 ledger event)
- Decline is always penalty-free
- Problem reports never change state
- Invalid transitions raise IllegalStateTransitionError
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from src.application.services.governance.task_consent_service import (
    TaskConsentService,
)
from src.application.services.governance.task_result_service import (
    TaskResultService,
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
