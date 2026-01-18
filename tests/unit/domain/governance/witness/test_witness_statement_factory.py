"""Unit tests for witness statement factory.

Story: consent-gov-6-1: Knight Witness Domain Model

Tests the WitnessStatementFactory which creates valid witness statements
and enforces observation-only content (no judgment language).

References:
    - FR34: Witness statements are observation only, no judgment
    - AC3: Witness statements are observation only, no judgment
    - AC7: Statement includes factual observation content
    - AC8: No interpretation or recommendation in statement
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.witness.errors import JudgmentLanguageError
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement_factory import (
    WitnessStatementFactory,
)


class FakeTimeAuthority:
    """Fake time authority for testing.

    Implements TimeAuthorityProtocol interface for testing.
    """

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._fixed_time = fixed_time or datetime(
            2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc
        )

    def now(self) -> datetime:
        """Return current time (fixed for testing)."""
        return self._fixed_time

    def utcnow(self) -> datetime:
        """Return current UTC time (fixed for testing)."""
        return self._fixed_time

    def monotonic(self) -> float:
        """Return monotonic clock value (fixed for testing)."""
        return 0.0


class FakeEvent:
    """Fake event for testing factory."""

    def __init__(
        self,
        event_id: str | None = None,
        event_type: str = "executive.task.activated",
        timestamp: datetime | None = None,
        actor: str = "actor-uuid-1",
    ) -> None:
        self.event_id = uuid4() if event_id is None else event_id
        self.event_type = event_type
        self.timestamp = timestamp or datetime(
            2026, 1, 17, 10, 29, 0, tzinfo=timezone.utc
        )
        self.actor = actor


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def factory(time_authority: FakeTimeAuthority) -> WitnessStatementFactory:
    """Create factory with fake time authority."""
    return WitnessStatementFactory(time_authority=time_authority)


@pytest.fixture
def observed_event() -> FakeEvent:
    """Create fake observed event."""
    return FakeEvent()


class TestWitnessStatementFactory:
    """Unit tests for statement factory."""

    def test_factory_creates_valid_statement(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory creates valid observation statement (AC7)."""
        statement = factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=observed_event,
            what="Task state changed from AUTHORIZED to ACTIVATED",
            where="executive.task_coordination",
        )

        assert statement.observation_type == ObservationType.BRANCH_ACTION
        assert statement.content.event_id == observed_event.event_id
        assert (
            statement.content.what == "Task state changed from AUTHORIZED to ACTIVATED"
        )
        assert statement.content.where == "executive.task_coordination"

    def test_factory_sets_observation_timestamp(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory sets observed_at from time authority."""
        statement = factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=observed_event,
            what="Task state changed",
            where="executive",
        )

        # observed_at should be from time authority (2026-01-17 10:30)
        assert statement.observed_at == datetime(
            2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc
        )

    def test_factory_increments_hash_chain_position(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory increments hash chain position for gap detection."""
        statement1 = factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=observed_event,
            what="First observation",
            where="executive",
        )

        statement2 = factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=FakeEvent(),
            what="Second observation",
            where="executive",
        )

        assert statement2.hash_chain_position == statement1.hash_chain_position + 1

    def test_factory_rejects_should_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'should' judgment language (AC8)."""
        with pytest.raises(JudgmentLanguageError) as exc_info:
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="This should not have happened",
                where="executive",
            )

        assert "should" in str(exc_info.value)
        assert "observation-only" in str(exc_info.value)

    def test_factory_rejects_must_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'must' judgment language (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Actor must follow the protocol",
                where="executive",
            )

    def test_factory_rejects_recommend_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'recommend' judgment language (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Recommend immediate halt",
                where="executive",
            )

    def test_factory_rejects_suggests_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'suggests' judgment language (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Evidence suggests malicious intent",
                where="executive",
            )

    def test_factory_rejects_violated_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'violated' determination language (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Actor violated consent protocol",
                where="executive",
            )

    def test_factory_rejects_guilty_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'guilty' judgment language (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Actor is guilty of misconduct",
                where="executive",
            )

    def test_factory_rejects_severe_severity_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'severe' severity descriptor (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Severe violation of consent protocol",
                where="executive",
            )

    def test_factory_rejects_critical_severity_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'critical' severity descriptor (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Critical security breach detected",
                where="executive",
            )

    def test_factory_rejects_minor_severity_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'minor' severity descriptor (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Minor protocol deviation observed",
                where="executive",
            )

    def test_factory_rejects_remedy_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'remedy' prescription language (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Remedy required for protocol violation",
                where="executive",
            )

    def test_factory_rejects_punishment_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects 'punishment' prescription language (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Punishment warranted for this action",
                where="executive",
            )

    def test_factory_accepts_neutral_observation(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory accepts neutral factual observation (AC7)."""
        # All of these should be accepted - they're factual
        factual_observations = [
            "Task activated without explicit consent recorded in ledger",
            "Timing deviation of 500ms observed between request and response",
            "Hash chain gap detected between positions 42 and 44",
            "Branch action executed by actor-uuid-1 at 10:30:00 UTC",
            "State transition from AUTHORIZED to ACTIVATED completed",
        ]

        for observation in factual_observations:
            statement = factory.create_statement(
                observation_type=ObservationType.BRANCH_ACTION,
                observed_event=FakeEvent(),
                what=observation,
                where="executive",
            )
            assert statement.content.what == observation

    def test_factory_case_insensitive_judgment_detection(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory detects judgment language regardless of case (AC8)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="This SHOULD NOT have happened",
                where="executive",
            )

    def test_factory_generates_unique_statement_ids(
        self,
        factory: WitnessStatementFactory,
    ) -> None:
        """Factory generates unique statement IDs."""
        statement1 = factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=FakeEvent(),
            what="First observation",
            where="executive",
        )

        statement2 = factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=FakeEvent(),
            what="Second observation",
            where="executive",
        )

        assert statement1.statement_id != statement2.statement_id

    def test_factory_extracts_actor_from_event(
        self,
        factory: WitnessStatementFactory,
    ) -> None:
        """Factory extracts actor from observed event."""
        event = FakeEvent(actor="archon-42")
        statement = factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=event,
            what="Task state changed",
            where="executive",
        )

        assert "archon-42" in statement.content.who

    def test_factory_rejects_empty_what(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects empty what field (AC7: factual content required)."""
        with pytest.raises(ValueError) as exc_info:
            factory.create_statement(
                observation_type=ObservationType.BRANCH_ACTION,
                observed_event=observed_event,
                what="",
                where="executive",
            )

        assert "cannot be empty" in str(exc_info.value)

    def test_factory_rejects_whitespace_only_what(
        self,
        factory: WitnessStatementFactory,
        observed_event: FakeEvent,
    ) -> None:
        """Factory rejects whitespace-only what field (AC7)."""
        with pytest.raises(ValueError) as exc_info:
            factory.create_statement(
                observation_type=ObservationType.BRANCH_ACTION,
                observed_event=observed_event,
                what="   ",
                where="executive",
            )

        assert "cannot be empty" in str(exc_info.value)

    def test_factory_is_thread_safe(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Factory position counter is thread-safe."""
        import concurrent.futures

        factory = WitnessStatementFactory(time_authority=time_authority)
        positions: list[int] = []

        def create_and_record() -> int:
            statement = factory.create_statement(
                observation_type=ObservationType.BRANCH_ACTION,
                observed_event=FakeEvent(),
                what="Concurrent observation",
                where="executive",
            )
            return statement.hash_chain_position

        # Create statements concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_and_record) for _ in range(100)]
            positions = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All positions should be unique (no duplicates from race conditions)
        assert len(positions) == len(set(positions)), (
            "Duplicate positions detected - race condition!"
        )
        # Positions should be 1-100
        assert set(positions) == set(range(1, 101))
