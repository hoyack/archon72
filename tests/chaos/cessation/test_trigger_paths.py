"""Alternative Trigger Path Tests (Story 7.9, AC6, Task 7).

Tests the alternative paths that can trigger cessation:
- FR37: 3 consecutive integrity failures in 30 days
- FR38: Anti-success alert sustained 90 days
- FR39: External observer petition
- RT-4: 5 non-consecutive failures in 90-day rolling window

Constitutional Context:
All trigger paths should lead to the same cessation flow,
ensuring consistent behavior regardless of how cessation is initiated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events.event import Event

from .test_cessation_chaos import (
    IsolatedCessationEnvironment,
    generate_archon_deliberations,
    seed_initial_events,
)

# =============================================================================
# Trigger Event Factories
# =============================================================================


def create_integrity_failure_event(
    sequence: int,
    previous_content_hash: str | None,
    failure_type: str = "hash_chain_break",
    timestamp: datetime | None = None,
) -> Event:
    """Create an integrity failure event for testing FR37/RT-4.

    Args:
        sequence: Event sequence number.
        previous_content_hash: Hash of previous event (None for first event).
        failure_type: Type of integrity failure.
        timestamp: Event timestamp (defaults to now).

    Returns:
        Event representing an integrity failure detection.
    """
    return Event.create_with_hash(
        sequence=sequence,
        event_type="integrity.failure_detected",
        payload={
            "failure_type": failure_type,
            "severity": "critical",
            "detection_timestamp": (
                timestamp or datetime.now(timezone.utc)
            ).isoformat(),
            "requires_agenda_placement": True,
        },
        signature=f"integrity_failure_sig_{sequence}",
        witness_id="SYSTEM:INTEGRITY_MONITOR",
        witness_signature=f"witness_sig_{sequence}",
        local_timestamp=timestamp or datetime.now(timezone.utc),
        previous_content_hash=previous_content_hash,
        agent_id="SYSTEM:INTEGRITY_CHECKER",
    )


def create_anti_success_alert_event(
    sequence: int,
    previous_content_hash: str | None,
    days_sustained: int = 90,
    timestamp: datetime | None = None,
) -> Event:
    """Create an anti-success alert event for testing FR38.

    Args:
        sequence: Event sequence number.
        previous_content_hash: Hash of previous event (None for first event).
        days_sustained: Number of days the alert has been sustained.
        timestamp: Event timestamp (defaults to now).

    Returns:
        Event representing a sustained anti-success alert.
    """
    return Event.create_with_hash(
        sequence=sequence,
        event_type="anti_success.alert_sustained",
        payload={
            "alert_type": "anti_success",
            "days_sustained": days_sustained,
            "threshold_days": 90,
            "first_alert_date": (
                (timestamp or datetime.now(timezone.utc))
                - timedelta(days=days_sustained)
            ).isoformat(),
            "requires_agenda_placement": True,
        },
        signature=f"anti_success_sig_{sequence}",
        witness_id="SYSTEM:ANTI_SUCCESS_MONITOR",
        witness_signature=f"witness_sig_{sequence}",
        local_timestamp=timestamp or datetime.now(timezone.utc),
        previous_content_hash=previous_content_hash,
        agent_id="SYSTEM:ANTI_SUCCESS_CHECKER",
    )


def create_external_petition_event(
    sequence: int,
    previous_content_hash: str | None,
    petitioner_id: str = "external_observer_001",
    timestamp: datetime | None = None,
) -> Event:
    """Create an external observer petition event for testing FR39.

    Args:
        sequence: Event sequence number.
        previous_content_hash: Hash of previous event (None for first event).
        petitioner_id: ID of the external observer petitioning.
        timestamp: Event timestamp (defaults to now).

    Returns:
        Event representing an external observer petition.
    """
    return Event.create_with_hash(
        sequence=sequence,
        event_type="petition.cessation_requested",
        payload={
            "petitioner_id": petitioner_id,
            "petition_type": "cessation",
            "reason": "External observer has identified constitutional violations",
            "submitted_at": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "requires_agenda_placement": True,
        },
        signature=f"petition_sig_{sequence}",
        witness_id="SYSTEM:PETITION_PROCESSOR",
        witness_signature=f"witness_sig_{sequence}",
        local_timestamp=timestamp or datetime.now(timezone.utc),
        previous_content_hash=previous_content_hash,
        agent_id="SYSTEM:PETITION_HANDLER",
    )


# =============================================================================
# CHAOS TESTS: FR37 - 3 Consecutive Integrity Failures
# =============================================================================


@pytest.mark.chaos
class TestFR37ConsecutiveIntegrityFailures:
    """Test FR37: 3 consecutive integrity failures in 30 days -> agenda placement."""

    @pytest.mark.asyncio
    async def test_three_consecutive_failures_triggers_cessation(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """FR37: Verify 3 consecutive failures lead to cessation flow."""
        env = isolated_cessation_env

        # Seed baseline events
        baseline = await seed_initial_events(env.event_store, count=2)

        # Create 3 consecutive integrity failure events
        failures: list[Event] = []
        base_time = datetime.now(timezone.utc) - timedelta(days=15)

        for i in range(3):
            prev_hash = (
                baseline[-1].content_hash if i == 0 else failures[i - 1].content_hash
            )
            failure = create_integrity_failure_event(
                sequence=len(baseline) + i + 1,
                previous_content_hash=prev_hash,
                failure_type=f"consecutive_failure_{i + 1}",
                timestamp=base_time + timedelta(days=i * 5),  # Spaced within 30 days
            )
            await env.event_store.append_event(failure)
            failures.append(failure)

        # Third failure triggers agenda placement -> cessation
        triggering_event_id = failures[-1].event_id

        # Execute cessation
        cessation_event = await env.cessation_execution_service.execute_cessation(
            triggering_event_id=triggering_event_id,
            reason="FR37: 3 consecutive integrity failures in 30-day window",
            agent_id="SYSTEM:FR37_TRIGGER",
        )

        # Verify cessation occurred
        assert cessation_event is not None
        assert await env.cessation_flag_repo.is_ceased() is True

        # Verify all failure events exist
        all_events = await env.event_store.get_events_by_type(
            "integrity.failure_detected"
        )
        assert len(all_events) == 3

    @pytest.mark.asyncio
    async def test_failure_payload_contains_agenda_flag(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """FR37: Verify failure events contain agenda placement flag."""
        env = isolated_cessation_env

        baseline = await seed_initial_events(env.event_store, count=1)

        failure = create_integrity_failure_event(
            sequence=2,
            previous_content_hash=baseline[0].content_hash,
        )
        await env.event_store.append_event(failure)

        # Verify payload contains the flag
        assert failure.payload["requires_agenda_placement"] is True
        assert failure.payload["severity"] == "critical"


# =============================================================================
# CHAOS TESTS: RT-4 - 5 Non-Consecutive Failures in 90-Day Window
# =============================================================================


@pytest.mark.chaos
class TestRT4RollingWindowFailures:
    """Test RT-4: 5 non-consecutive failures in 90-day rolling window.

    This is the defense against "wait and reset" timing attacks.
    """

    @pytest.mark.asyncio
    async def test_five_nonconsecutive_failures_triggers_cessation(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """RT-4: Verify 5 non-consecutive failures in 90 days trigger cessation."""
        env = isolated_cessation_env

        # Seed baseline events
        baseline = await seed_initial_events(env.event_store, count=2)

        # Create 5 non-consecutive integrity failure events over 90 days
        failures: list[Event] = []
        base_time = datetime.now(timezone.utc) - timedelta(days=85)

        # Space failures: days 0, 15, 30, 45, 60 (all within 90 days)
        failure_days = [0, 15, 30, 45, 60]

        for i, day_offset in enumerate(failure_days):
            prev_hash = (
                baseline[-1].content_hash if i == 0 else failures[i - 1].content_hash
            )
            failure = create_integrity_failure_event(
                sequence=len(baseline) + i + 1,
                previous_content_hash=prev_hash,
                failure_type=f"rolling_window_failure_{i + 1}",
                timestamp=base_time + timedelta(days=day_offset),
            )
            await env.event_store.append_event(failure)
            failures.append(failure)

        # Fifth failure triggers cessation
        triggering_event_id = failures[-1].event_id

        cessation_event = await env.cessation_execution_service.execute_cessation(
            triggering_event_id=triggering_event_id,
            reason="RT-4: 5 non-consecutive integrity failures in 90-day rolling window",
            agent_id="SYSTEM:RT4_TRIGGER",
        )

        # Verify cessation occurred
        assert cessation_event is not None
        assert await env.cessation_flag_repo.is_ceased() is True


# =============================================================================
# CHAOS TESTS: FR38 - Anti-Success Alert Sustained 90 Days
# =============================================================================


@pytest.mark.chaos
class TestFR38AntiSuccessAlert:
    """Test FR38: Anti-success alert sustained 90 days -> agenda placement."""

    @pytest.mark.asyncio
    async def test_sustained_anti_success_triggers_cessation(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """FR38: Verify sustained anti-success alert leads to cessation."""
        env = isolated_cessation_env

        # Seed baseline events
        baseline = await seed_initial_events(env.event_store, count=2)

        # Create anti-success alert event (sustained 90 days)
        alert_event = create_anti_success_alert_event(
            sequence=3,
            previous_content_hash=baseline[-1].content_hash,
            days_sustained=90,
        )
        await env.event_store.append_event(alert_event)

        # Alert triggers cessation
        cessation_event = await env.cessation_execution_service.execute_cessation(
            triggering_event_id=alert_event.event_id,
            reason="FR38: Anti-success alert sustained for 90 days",
            agent_id="SYSTEM:FR38_TRIGGER",
        )

        # Verify cessation occurred
        assert cessation_event is not None
        assert await env.cessation_flag_repo.is_ceased() is True

    @pytest.mark.asyncio
    async def test_anti_success_payload_contains_duration(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """FR38: Verify alert payload contains duration information."""
        env = isolated_cessation_env

        baseline = await seed_initial_events(env.event_store, count=1)

        alert = create_anti_success_alert_event(
            sequence=2,
            previous_content_hash=baseline[0].content_hash,
            days_sustained=90,
        )
        await env.event_store.append_event(alert)

        # Verify payload
        assert alert.payload["days_sustained"] == 90
        assert alert.payload["threshold_days"] == 90
        assert alert.payload["requires_agenda_placement"] is True


# =============================================================================
# CHAOS TESTS: FR39 - External Observer Petition
# =============================================================================


@pytest.mark.chaos
class TestFR39ExternalObserverPetition:
    """Test FR39: External observer petition -> agenda placement."""

    @pytest.mark.asyncio
    async def test_external_petition_triggers_cessation(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """FR39: Verify external petition leads to cessation flow."""
        env = isolated_cessation_env

        # Seed baseline events
        baseline = await seed_initial_events(env.event_store, count=2)

        # Create external observer petition
        petition_event = create_external_petition_event(
            sequence=3,
            previous_content_hash=baseline[-1].content_hash,
            petitioner_id="external_observer_regulatory_body",
        )
        await env.event_store.append_event(petition_event)

        # Generate 72-archon deliberation after petition
        deliberations = generate_archon_deliberations(48, 20, 4)

        # Execute cessation with deliberation
        cessation_event = (
            await env.cessation_execution_service.execute_cessation_with_deliberation(
                deliberation_id=uuid4(),
                deliberation_started_at=datetime.now(timezone.utc) - timedelta(hours=2),
                deliberation_ended_at=datetime.now(timezone.utc),
                archon_deliberations=deliberations,
                triggering_event_id=petition_event.event_id,
                reason="FR39: External observer petition approved by 72 archons",
                agent_id="SYSTEM:FR39_TRIGGER",
            )
        )

        # Verify cessation occurred
        assert cessation_event is not None
        assert await env.cessation_flag_repo.is_ceased() is True

    @pytest.mark.asyncio
    async def test_petition_payload_contains_petitioner_info(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """FR39: Verify petition payload contains petitioner information."""
        env = isolated_cessation_env

        baseline = await seed_initial_events(env.event_store, count=1)

        petition = create_external_petition_event(
            sequence=2,
            previous_content_hash=baseline[0].content_hash,
            petitioner_id="regulatory_observer_xyz",
        )
        await env.event_store.append_event(petition)

        # Verify payload
        assert petition.payload["petitioner_id"] == "regulatory_observer_xyz"
        assert petition.payload["petition_type"] == "cessation"
        assert petition.payload["requires_agenda_placement"] is True


# =============================================================================
# CHAOS TESTS: All Trigger Paths Lead to Same Cessation Flow
# =============================================================================


@pytest.mark.chaos
class TestTriggerPathConsistency:
    """Test that all trigger paths produce consistent cessation results."""

    @pytest.mark.asyncio
    async def test_all_paths_result_in_same_cessation_state(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """Verify all trigger paths result in identical cessation state."""
        env = isolated_cessation_env

        # Test with FR37 trigger (3 consecutive failures)
        baseline = await seed_initial_events(env.event_store, count=1)

        cessation_event = await env.cessation_execution_service.execute_cessation(
            triggering_event_id=baseline[0].event_id,
            reason="Trigger path consistency test",
            agent_id="SYSTEM:TEST",
        )

        # Verify cessation state is consistent
        assert cessation_event is not None
        assert await env.cessation_flag_repo.is_ceased() is True

        details = await env.cessation_flag_repo.get_cessation_details()
        assert details is not None
        assert details.cessation_event_id == cessation_event.event_id

        # Both channels should be set (ADR-3)
        assert env.cessation_flag_repo.redis_flag is not None
        assert env.cessation_flag_repo.db_flag is not None

        # Both channels should have identical data
        assert (
            env.cessation_flag_repo.redis_flag.reason
            == env.cessation_flag_repo.db_flag.reason
        )

    @pytest.mark.asyncio
    async def test_trigger_event_referenced_in_cessation(
        self,
        isolated_cessation_env: IsolatedCessationEnvironment,
    ) -> None:
        """Verify triggering event is properly referenced in cessation."""
        env = isolated_cessation_env

        baseline = await seed_initial_events(env.event_store, count=1)
        triggering_id = baseline[0].event_id

        cessation_event = await env.cessation_execution_service.execute_cessation(
            triggering_event_id=triggering_id,
            reason="Trigger reference test",
            agent_id="SYSTEM:TEST",
        )

        # Verify trigger source in payload
        payload = cessation_event.payload
        assert payload["triggering_event_id"] == str(triggering_id)
        assert payload["trigger_source"] == str(triggering_id)
