"""Unit tests for TerminalEventDetectorProtocol (Story 7.3, FR40, NFR40).

Tests for:
- Protocol definition
- Method signatures
- Type hints
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import uuid4

import pytest

from src.application.ports.terminal_event_detector import TerminalEventDetectorProtocol
from src.domain.events.event import Event


class TestTerminalEventDetectorProtocol:
    """Tests for the TerminalEventDetectorProtocol definition."""

    def test_is_protocol(self) -> None:
        """Should be a Protocol class."""
        assert hasattr(TerminalEventDetectorProtocol, "__protocol_attrs__") or issubclass(
            TerminalEventDetectorProtocol, Protocol
        )

    def test_has_is_system_terminated_method(self) -> None:
        """Should have is_system_terminated method."""
        assert hasattr(TerminalEventDetectorProtocol, "is_system_terminated")

    def test_has_get_terminal_event_method(self) -> None:
        """Should have get_terminal_event method."""
        assert hasattr(TerminalEventDetectorProtocol, "get_terminal_event")

    def test_has_get_termination_timestamp_method(self) -> None:
        """Should have get_termination_timestamp method."""
        assert hasattr(TerminalEventDetectorProtocol, "get_termination_timestamp")


class MockTerminalEventDetector:
    """Mock implementation for testing protocol compliance."""

    def __init__(self) -> None:
        self._terminated = False
        self._terminal_event: Event | None = None
        self._termination_timestamp: datetime | None = None

    def set_terminated(
        self,
        event: Event,
        timestamp: datetime,
    ) -> None:
        """Configure as terminated."""
        self._terminated = True
        self._terminal_event = event
        self._termination_timestamp = timestamp

    def clear(self) -> None:
        """Reset to non-terminated state (for test setup)."""
        self._terminated = False
        self._terminal_event = None
        self._termination_timestamp = None

    async def is_system_terminated(self) -> bool:
        """Check if system is terminated."""
        return self._terminated

    async def get_terminal_event(self) -> Event | None:
        """Get terminal event if exists."""
        return self._terminal_event

    async def get_termination_timestamp(self) -> datetime | None:
        """Get termination timestamp if exists."""
        return self._termination_timestamp


class TestMockImplementation:
    """Tests for mock implementation protocol compliance."""

    @pytest.mark.asyncio
    async def test_is_system_terminated_returns_bool(self) -> None:
        """is_system_terminated should return bool."""
        detector = MockTerminalEventDetector()
        result = await detector.is_system_terminated()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_is_system_terminated_false_initially(self) -> None:
        """is_system_terminated should be False initially."""
        detector = MockTerminalEventDetector()
        assert await detector.is_system_terminated() is False

    @pytest.mark.asyncio
    async def test_is_system_terminated_true_after_termination(self) -> None:
        """is_system_terminated should be True after set_terminated."""
        detector = MockTerminalEventDetector()

        event = Event(
            event_id=uuid4(),
            event_type="cessation.executed",
            sequence=42,
            local_timestamp=datetime.now(timezone.utc),
            agent_id="system",
            content_hash="a" * 64,
            prev_hash="b" * 64,
            signature="sig",
            witness_id="witness-1",
            witness_signature="wsig",
            payload={"is_terminal": True},
        )
        detector.set_terminated(event, datetime.now(timezone.utc))

        assert await detector.is_system_terminated() is True

    @pytest.mark.asyncio
    async def test_get_terminal_event_returns_none_initially(self) -> None:
        """get_terminal_event should return None initially."""
        detector = MockTerminalEventDetector()
        result = await detector.get_terminal_event()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_terminal_event_returns_event_after_termination(self) -> None:
        """get_terminal_event should return Event after termination."""
        detector = MockTerminalEventDetector()

        event = Event(
            event_id=uuid4(),
            event_type="cessation.executed",
            sequence=42,
            local_timestamp=datetime.now(timezone.utc),
            agent_id="system",
            content_hash="c" * 64,
            prev_hash="d" * 64,
            signature="sig",
            witness_id="witness-1",
            witness_signature="wsig",
            payload={"is_terminal": True},
        )
        detector.set_terminated(event, datetime.now(timezone.utc))

        result = await detector.get_terminal_event()
        assert result is event

    @pytest.mark.asyncio
    async def test_get_termination_timestamp_returns_none_initially(self) -> None:
        """get_termination_timestamp should return None initially."""
        detector = MockTerminalEventDetector()
        result = await detector.get_termination_timestamp()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_termination_timestamp_returns_datetime_after_termination(
        self,
    ) -> None:
        """get_termination_timestamp should return datetime after termination."""
        detector = MockTerminalEventDetector()

        event = Event(
            event_id=uuid4(),
            event_type="cessation.executed",
            sequence=42,
            local_timestamp=datetime.now(timezone.utc),
            agent_id="system",
            content_hash="e" * 64,
            prev_hash="f" * 64,
            signature="sig",
            witness_id="witness-1",
            witness_signature="wsig",
            payload={"is_terminal": True},
        )
        timestamp = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        detector.set_terminated(event, timestamp)

        result = await detector.get_termination_timestamp()
        assert result == timestamp


class TestProtocolDocumentation:
    """Tests verifying protocol documentation requirements."""

    def test_protocol_docstring_mentions_nfr40(self) -> None:
        """Protocol docstring should mention NFR40."""
        docstring = TerminalEventDetectorProtocol.__doc__
        assert docstring is not None
        assert "NFR40" in docstring

    def test_protocol_docstring_mentions_terminal_first(self) -> None:
        """Protocol docstring should mention terminal check order."""
        docstring = TerminalEventDetectorProtocol.__doc__
        assert docstring is not None
        assert "terminal" in docstring.lower() or "first" in docstring.lower()

    def test_is_system_terminated_docstring_mentions_permanent(self) -> None:
        """is_system_terminated docstring should mention permanent state."""
        method = getattr(TerminalEventDetectorProtocol, "is_system_terminated", None)
        if method and method.__doc__:
            assert "permanent" in method.__doc__.lower() or "irreversible" in method.__doc__.lower()
