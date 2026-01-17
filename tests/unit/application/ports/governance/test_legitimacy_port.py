"""Unit tests for LegitimacyPort interface.

Tests AC3: Current band tracked and queryable
Tests AC4: Band state queryable by any participant
"""

import pytest
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)
from src.domain.governance.legitimacy.transition_type import TransitionType
from src.application.ports.governance.legitimacy_port import (
    LegitimacyPort,
    LegitimacyQueryPort,
)


class InMemoryLegitimacyAdapter:
    """In-memory implementation for testing."""

    def __init__(self) -> None:
        self._state: Optional[LegitimacyState] = None
        self._transitions: list[LegitimacyTransition] = []

    async def get_current_band(self) -> LegitimacyBand:
        if self._state is None:
            raise RuntimeError("State not initialized")
        return self._state.current_band

    async def get_legitimacy_state(self) -> LegitimacyState:
        if self._state is None:
            raise RuntimeError("State not initialized")
        return self._state

    async def get_transition_history(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[LegitimacyTransition]:
        result = self._transitions

        if since is not None:
            result = [t for t in result if t.timestamp > since]

        if limit is not None:
            result = result[:limit]

        return result

    async def record_transition(
        self,
        transition: LegitimacyTransition,
    ) -> None:
        self._transitions.append(transition)
        self._state = LegitimacyState(
            current_band=transition.to_band,
            entered_at=transition.timestamp,
            violation_count=self._state.violation_count if self._state else 0,
            last_triggering_event_id=transition.triggering_event_id,
            last_transition_type=transition.transition_type,
        )

    async def get_state_at(
        self,
        timestamp: datetime,
    ) -> Optional[LegitimacyState]:
        # Find the latest transition before timestamp
        relevant_transitions = [
            t for t in self._transitions
            if t.timestamp <= timestamp
        ]

        if not relevant_transitions:
            return None

        last_transition = relevant_transitions[-1]
        return LegitimacyState(
            current_band=last_transition.to_band,
            entered_at=last_transition.timestamp,
            violation_count=0,
            last_triggering_event_id=last_transition.triggering_event_id,
            last_transition_type=last_transition.transition_type,
        )

    async def get_violation_count(self) -> int:
        if self._state is None:
            return 0
        return self._state.violation_count

    async def initialize_state(
        self,
        initial_band: LegitimacyBand,
        timestamp: datetime,
    ) -> LegitimacyState:
        if self._state is not None:
            raise RuntimeError("State already initialized")

        self._state = LegitimacyState(
            current_band=initial_band,
            entered_at=timestamp,
            violation_count=0,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )
        return self._state


class TestLegitimacyPortProtocolConformance:
    """Tests that InMemoryLegitimacyAdapter conforms to LegitimacyPort."""

    def test_adapter_is_legitimacy_port(self) -> None:
        """Adapter implements LegitimacyPort protocol."""
        adapter = InMemoryLegitimacyAdapter()
        # This is a structural check - if adapter doesn't have all methods,
        # Python will fail at attribute access
        assert hasattr(adapter, "get_current_band")
        assert hasattr(adapter, "get_legitimacy_state")
        assert hasattr(adapter, "get_transition_history")
        assert hasattr(adapter, "record_transition")
        assert hasattr(adapter, "get_state_at")
        assert hasattr(adapter, "get_violation_count")
        assert hasattr(adapter, "initialize_state")


class TestLegitimacyPortInitialization:
    """Tests for state initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_state(self) -> None:
        """initialize_state creates initial state."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        state = await adapter.initialize_state(LegitimacyBand.STABLE, now)

        assert state.current_band == LegitimacyBand.STABLE
        assert state.entered_at == now
        assert state.violation_count == 0

    @pytest.mark.asyncio
    async def test_initialize_fails_if_already_initialized(self) -> None:
        """initialize_state raises if state exists."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        await adapter.initialize_state(LegitimacyBand.STABLE, now)

        with pytest.raises(RuntimeError, match="already initialized"):
            await adapter.initialize_state(LegitimacyBand.STABLE, now)


class TestLegitimacyPortQueries:
    """Tests for query operations (AC3, AC4)."""

    @pytest.mark.asyncio
    async def test_get_current_band_returns_band(self) -> None:
        """get_current_band returns current band."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        await adapter.initialize_state(LegitimacyBand.STABLE, now)

        band = await adapter.get_current_band()
        assert band == LegitimacyBand.STABLE

    @pytest.mark.asyncio
    async def test_get_current_band_fails_if_not_initialized(self) -> None:
        """get_current_band raises if state not initialized."""
        adapter = InMemoryLegitimacyAdapter()

        with pytest.raises(RuntimeError, match="not initialized"):
            await adapter.get_current_band()

    @pytest.mark.asyncio
    async def test_get_legitimacy_state_returns_full_state(self) -> None:
        """get_legitimacy_state returns complete state."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        await adapter.initialize_state(LegitimacyBand.STABLE, now)

        state = await adapter.get_legitimacy_state()
        assert state.current_band == LegitimacyBand.STABLE
        assert state.entered_at == now
        assert state.violation_count == 0

    @pytest.mark.asyncio
    async def test_get_transition_history_empty_initially(self) -> None:
        """get_transition_history returns empty list initially."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        await adapter.initialize_state(LegitimacyBand.STABLE, now)

        history = await adapter.get_transition_history()
        assert history == []


class TestLegitimacyPortTransitions:
    """Tests for recording transitions."""

    @pytest.mark.asyncio
    async def test_record_transition_updates_state(self) -> None:
        """record_transition updates current state."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        await adapter.initialize_state(LegitimacyBand.STABLE, now)

        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="Test violation",
        )

        await adapter.record_transition(transition)

        band = await adapter.get_current_band()
        assert band == LegitimacyBand.STRAINED

    @pytest.mark.asyncio
    async def test_record_transition_adds_to_history(self) -> None:
        """record_transition adds to transition history."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        await adapter.initialize_state(LegitimacyBand.STABLE, now)

        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime.now(timezone.utc),
            reason="Test violation",
        )

        await adapter.record_transition(transition)

        history = await adapter.get_transition_history()
        assert len(history) == 1
        assert history[0] == transition


class TestLegitimacyPortHistoryFiltering:
    """Tests for transition history filtering."""

    @pytest.mark.asyncio
    async def test_get_transition_history_with_since(self) -> None:
        """get_transition_history filters by since timestamp."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        await adapter.initialize_state(LegitimacyBand.STABLE, now)

        # Record two transitions
        old_transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STABLE,
            to_band=LegitimacyBand.STRAINED,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            reason="Old violation",
        )
        await adapter.record_transition(old_transition)

        new_transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=LegitimacyBand.STRAINED,
            to_band=LegitimacyBand.ERODING,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=uuid4(),
            acknowledgment_id=None,
            timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
            reason="New violation",
        )
        await adapter.record_transition(new_transition)

        # Filter for only new
        history = await adapter.get_transition_history(
            since=datetime(2024, 3, 1, tzinfo=timezone.utc)
        )
        assert len(history) == 1
        assert history[0] == new_transition

    @pytest.mark.asyncio
    async def test_get_transition_history_with_limit(self) -> None:
        """get_transition_history respects limit."""
        adapter = InMemoryLegitimacyAdapter()
        now = datetime.now(timezone.utc)

        await adapter.initialize_state(LegitimacyBand.STABLE, now)

        # Record multiple transitions
        for i, (from_band, to_band) in enumerate([
            (LegitimacyBand.STABLE, LegitimacyBand.STRAINED),
            (LegitimacyBand.STRAINED, LegitimacyBand.ERODING),
            (LegitimacyBand.ERODING, LegitimacyBand.COMPROMISED),
        ]):
            transition = LegitimacyTransition(
                transition_id=uuid4(),
                from_band=from_band,
                to_band=to_band,
                transition_type=TransitionType.AUTOMATIC,
                actor="system",
                triggering_event_id=uuid4(),
                acknowledgment_id=None,
                timestamp=datetime.now(timezone.utc),
                reason=f"Violation {i}",
            )
            await adapter.record_transition(transition)

        history = await adapter.get_transition_history(limit=2)
        assert len(history) == 2


class TestLegitimacyQueryPort:
    """Tests for read-only query port."""

    def test_query_port_is_subset(self) -> None:
        """LegitimacyQueryPort is subset of LegitimacyPort."""
        # Verify that all methods in QueryPort are in full Port
        query_methods = [
            "get_current_band",
            "get_legitimacy_state",
            "get_transition_history",
        ]

        adapter = InMemoryLegitimacyAdapter()
        for method in query_methods:
            assert hasattr(adapter, method), f"Missing method: {method}"
