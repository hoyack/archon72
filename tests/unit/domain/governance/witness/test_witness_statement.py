"""Unit tests for witness statement domain model.

Story: consent-gov-6-1: Knight Witness Domain Model

Tests the Knight witness capability per:
- FR33: Knight can observe all branch actions
- FR34: Witness statements are observation only, no judgment
- NFR-CONST-07: Statements cannot be suppressed by any role

The Knight is analogous to a court reporter:
- Records everything accurately
- Does not interrupt proceedings
- Does not offer opinions
- Provides transcript for others to judge
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.witness.observation_content import ObservationContent
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement


class TestObservationType:
    """Unit tests for observation type enum."""

    def test_branch_action_type_exists(self) -> None:
        """BRANCH_ACTION type exists for normal operations."""
        assert ObservationType.BRANCH_ACTION.value == "branch_action"

    def test_potential_violation_type_exists(self) -> None:
        """POTENTIAL_VIOLATION type exists for pattern matches."""
        assert ObservationType.POTENTIAL_VIOLATION.value == "potential_violation"

    def test_timing_anomaly_type_exists(self) -> None:
        """TIMING_ANOMALY type exists for unexpected timing."""
        assert ObservationType.TIMING_ANOMALY.value == "timing_anomaly"

    def test_hash_chain_gap_type_exists(self) -> None:
        """HASH_CHAIN_GAP type exists for missing events."""
        assert ObservationType.HASH_CHAIN_GAP.value == "hash_chain_gap"

    def test_all_types_are_observations(self) -> None:
        """All observation types are neutral observations (AC3)."""
        # None of these should imply judgment
        neutral_types = [
            ObservationType.BRANCH_ACTION,
            ObservationType.POTENTIAL_VIOLATION,  # "potential" = observation
            ObservationType.TIMING_ANOMALY,
            ObservationType.HASH_CHAIN_GAP,
        ]

        for obs_type in ObservationType:
            assert obs_type in neutral_types
            # Type names don't include judgment words
            assert "guilty" not in obs_type.value
            assert "innocent" not in obs_type.value
            assert "fault" not in obs_type.value


class TestObservationContent:
    """Unit tests for observation content structure."""

    def test_observation_content_is_frozen(self) -> None:
        """Observation content is immutable (AC: immutability)."""
        content = ObservationContent(
            what="Task state changed from AUTHORIZED to ACTIVATED",
            when=datetime.now(timezone.utc),
            who=("actor-uuid-1",),
            where="executive.task_coordination",
            event_type="executive.task.activated",
            event_id=uuid4(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            content.what = "modified"  # type: ignore[misc]

    def test_observation_content_has_factual_fields_only(self) -> None:
        """Observation content structure is factual only (AC7, AC8)."""
        content = ObservationContent(
            what="Task activated without explicit consent",
            when=datetime.now(timezone.utc),
            who=("actor-uuid-1",),
            where="executive.task_coordination",
            event_type="task.activated",
            event_id=uuid4(),
        )

        # Factual fields present
        assert content.what
        assert content.when
        assert content.who
        assert content.where
        assert content.event_type
        assert content.event_id

        # No judgment fields (they don't exist in the class)
        assert not hasattr(content, "why")
        assert not hasattr(content, "should")
        assert not hasattr(content, "severity")
        assert not hasattr(content, "recommendation")
        assert not hasattr(content, "remedy")

    def test_observation_content_summary_is_factual(self) -> None:
        """Summary property provides factual description."""
        when = datetime(2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc)
        content = ObservationContent(
            what="Task state changed",
            when=when,
            who=("actor-uuid-1",),
            where="executive.task_coordination",
            event_type="executive.task.activated",
            event_id=uuid4(),
        )

        summary = content.summary
        assert "2026-01-17" in summary
        assert "executive.task.activated" in summary
        assert "executive.task_coordination" in summary


class TestWitnessStatement:
    """Unit tests for witness statement domain model."""

    def test_statement_is_immutable(self) -> None:
        """Statements cannot be modified after creation (AC4)."""
        statement = WitnessStatement(
            statement_id=uuid4(),
            observation_type=ObservationType.BRANCH_ACTION,
            content=ObservationContent(
                what="Task state changed",
                when=datetime.now(timezone.utc),
                who=("actor-uuid-1",),
                where="executive",
                event_type="executive.task.activated",
                event_id=uuid4(),
            ),
            observed_at=datetime.now(timezone.utc),
            hash_chain_position=1,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            statement.hash_chain_position = 999  # type: ignore[misc]

    def test_statement_has_no_judgment_fields(self) -> None:
        """Statement structure excludes judgment fields (AC3, AC8)."""
        statement = WitnessStatement(
            statement_id=uuid4(),
            observation_type=ObservationType.BRANCH_ACTION,
            content=ObservationContent(
                what="Task state changed",
                when=datetime.now(timezone.utc),
                who=("actor-uuid-1",),
                where="executive",
                event_type="executive.task.activated",
                event_id=uuid4(),
            ),
            observed_at=datetime.now(timezone.utc),
            hash_chain_position=1,
        )

        # These should not exist - Knight does not judge
        assert not hasattr(statement, "severity")
        assert not hasattr(statement, "recommendation")
        assert not hasattr(statement, "violation")
        assert not hasattr(statement, "remedy")
        assert not hasattr(statement, "finding")
        assert not hasattr(statement, "verdict")

    def test_statement_references_observed_event(self) -> None:
        """Statement includes observed event reference (AC5)."""
        event_id = uuid4()
        statement = WitnessStatement(
            statement_id=uuid4(),
            observation_type=ObservationType.BRANCH_ACTION,
            content=ObservationContent(
                what="Task state changed",
                when=datetime.now(timezone.utc),
                who=("actor-uuid-1",),
                where="executive",
                event_type="executive.task.activated",
                event_id=event_id,
            ),
            observed_at=datetime.now(timezone.utc),
            hash_chain_position=1,
        )

        assert statement.content.event_id == event_id

    def test_statement_includes_observation_timestamp(self) -> None:
        """Statement includes observation timestamp (AC6)."""
        observed_at = datetime(2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc)
        statement = WitnessStatement(
            statement_id=uuid4(),
            observation_type=ObservationType.BRANCH_ACTION,
            content=ObservationContent(
                what="Task state changed",
                when=datetime.now(timezone.utc),
                who=("actor-uuid-1",),
                where="executive",
                event_type="executive.task.activated",
                event_id=uuid4(),
            ),
            observed_at=observed_at,
            hash_chain_position=1,
        )

        assert statement.observed_at == observed_at

    def test_statement_has_hash_chain_position(self) -> None:
        """Statement has hash chain position for gap detection."""
        statement = WitnessStatement(
            statement_id=uuid4(),
            observation_type=ObservationType.BRANCH_ACTION,
            content=ObservationContent(
                what="Task state changed",
                when=datetime.now(timezone.utc),
                who=("actor-uuid-1",),
                where="executive",
                event_type="executive.task.activated",
                event_id=uuid4(),
            ),
            observed_at=datetime.now(timezone.utc),
            hash_chain_position=42,
        )

        assert statement.hash_chain_position == 42

    def test_statement_equality_by_id(self) -> None:
        """Statements are equal if they have the same statement_id."""
        statement_id = uuid4()
        event_id = uuid4()
        observed_at = datetime(2026, 1, 17, 10, 30, 0, tzinfo=timezone.utc)
        event_when = datetime(2026, 1, 17, 10, 29, 0, tzinfo=timezone.utc)
        content = ObservationContent(
            what="Task state changed",
            when=event_when,
            who=("actor-uuid-1",),
            where="executive",
            event_type="executive.task.activated",
            event_id=event_id,
        )

        statement1 = WitnessStatement(
            statement_id=statement_id,
            observation_type=ObservationType.BRANCH_ACTION,
            content=content,
            observed_at=observed_at,
            hash_chain_position=1,
        )

        statement2 = WitnessStatement(
            statement_id=statement_id,
            observation_type=ObservationType.BRANCH_ACTION,
            content=content,
            observed_at=observed_at,
            hash_chain_position=1,
        )

        assert statement1 == statement2

    def test_statement_hashable(self) -> None:
        """Statements can be used in sets and as dict keys."""
        statement = WitnessStatement(
            statement_id=uuid4(),
            observation_type=ObservationType.BRANCH_ACTION,
            content=ObservationContent(
                what="Task state changed",
                when=datetime.now(timezone.utc),
                who=("actor-uuid-1",),
                where="executive",
                event_type="executive.task.activated",
                event_id=uuid4(),
            ),
            observed_at=datetime.now(timezone.utc),
            hash_chain_position=1,
        )

        # Should be hashable
        statement_set = {statement}
        assert statement in statement_set
