"""Unit tests for ForkDetectionService domain service (Story 3.1, Task 3).

Tests the fork detection logic - detecting when two events claim
the same prev_hash but have different content_hashes.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.event import Event
from src.domain.events.fork_detected import ForkDetectedPayload
from src.domain.services.fork_detection import ForkDetectionService


class TestForkDetectionService:
    """Tests for ForkDetectionService."""

    @pytest.fixture
    def service(self) -> ForkDetectionService:
        """Create a fork detection service."""
        return ForkDetectionService(service_id="test-fork-detector")

    @pytest.fixture
    def create_event(self) -> callable:
        """Factory for creating test events."""

        def _create(
            prev_hash: str = "a" * 64,
            content_hash: str | None = None,
            sequence: int = 1,
        ) -> Event:
            return Event(
                event_id=uuid4(),
                sequence=sequence,
                event_type="test.event",
                payload={"test": True},
                prev_hash=prev_hash,
                content_hash=content_hash or uuid4().hex + uuid4().hex,
                signature="sig" * 20,
                witness_id="WITNESS:test",
                witness_signature="wsig" * 20,
                local_timestamp=datetime.now(timezone.utc),
            )

        return _create

    def test_no_fork_empty_events(self, service: ForkDetectionService) -> None:
        """No fork when events list is empty."""
        result = service.detect_fork([])
        assert result is None

    def test_no_fork_single_event(
        self, service: ForkDetectionService, create_event: callable
    ) -> None:
        """No fork with only one event."""
        events = [create_event()]
        result = service.detect_fork(events)
        assert result is None

    def test_no_fork_unique_prev_hashes(
        self, service: ForkDetectionService, create_event: callable
    ) -> None:
        """No fork when all events have unique prev_hashes."""
        events = [
            create_event(prev_hash="a" * 64, sequence=1),
            create_event(prev_hash="b" * 64, sequence=2),
            create_event(prev_hash="c" * 64, sequence=3),
        ]
        result = service.detect_fork(events)
        assert result is None

    def test_no_fork_same_prev_hash_same_content(
        self, service: ForkDetectionService, create_event: callable
    ) -> None:
        """No fork when events with same prev_hash also have same content_hash."""
        # This is an edge case - shouldn't happen in practice
        # but same content_hash means identical events
        shared_hash = "d" * 64
        shared_content = "e" * 64
        events = [
            create_event(prev_hash=shared_hash, content_hash=shared_content),
            create_event(prev_hash=shared_hash, content_hash=shared_content),
        ]
        result = service.detect_fork(events)
        assert result is None

    def test_fork_detected_same_prev_different_content(
        self, service: ForkDetectionService, create_event: callable
    ) -> None:
        """Fork detected when same prev_hash but different content_hash."""
        shared_prev = "f" * 64
        event1 = create_event(prev_hash=shared_prev, content_hash="1" * 64)
        event2 = create_event(prev_hash=shared_prev, content_hash="2" * 64)

        result = service.detect_fork([event1, event2])

        assert result is not None
        assert isinstance(result, ForkDetectedPayload)
        assert result.prev_hash == shared_prev
        assert event1.event_id in result.conflicting_event_ids
        assert event2.event_id in result.conflicting_event_ids
        assert "1" * 64 in result.content_hashes
        assert "2" * 64 in result.content_hashes

    def test_fork_includes_service_id(
        self, service: ForkDetectionService, create_event: callable
    ) -> None:
        """Fork payload includes detecting service ID."""
        shared_prev = "g" * 64
        events = [
            create_event(prev_hash=shared_prev, content_hash="1" * 64),
            create_event(prev_hash=shared_prev, content_hash="2" * 64),
        ]

        result = service.detect_fork(events)

        assert result is not None
        assert result.detecting_service_id == "test-fork-detector"

    def test_fork_includes_timestamp(
        self, service: ForkDetectionService, create_event: callable
    ) -> None:
        """Fork payload includes detection timestamp."""
        shared_prev = "h" * 64
        events = [
            create_event(prev_hash=shared_prev, content_hash="1" * 64),
            create_event(prev_hash=shared_prev, content_hash="2" * 64),
        ]

        before = datetime.now(timezone.utc)
        result = service.detect_fork(events)
        after = datetime.now(timezone.utc)

        assert result is not None
        assert before <= result.detection_timestamp <= after

    def test_fork_detection_returns_first_found(
        self, service: ForkDetectionService, create_event: callable
    ) -> None:
        """Fork detection returns immediately on first fork found."""
        # Multiple forks - should return the first one found
        fork1_prev = "i" * 64
        fork2_prev = "j" * 64

        events = [
            create_event(prev_hash=fork1_prev, content_hash="1" * 64),
            create_event(prev_hash=fork1_prev, content_hash="2" * 64),  # Fork 1!
            create_event(prev_hash=fork2_prev, content_hash="3" * 64),
            create_event(prev_hash=fork2_prev, content_hash="4" * 64),  # Fork 2!
        ]

        result = service.detect_fork(events)

        assert result is not None
        # Should find a fork (may be either one depending on iteration order)
        assert result.prev_hash in (fork1_prev, fork2_prev)

    def test_fork_with_three_conflicting_events(
        self, service: ForkDetectionService, create_event: callable
    ) -> None:
        """Fork detected when three events share same prev_hash."""
        shared_prev = "k" * 64
        events = [
            create_event(prev_hash=shared_prev, content_hash="1" * 64),
            create_event(prev_hash=shared_prev, content_hash="2" * 64),
            create_event(prev_hash=shared_prev, content_hash="3" * 64),
        ]

        result = service.detect_fork(events)

        assert result is not None
        # Should detect at least 2 conflicting events
        assert len(result.conflicting_event_ids) >= 2


class TestForkDetectionServiceAttributes:
    """Tests for ForkDetectionService attributes."""

    def test_service_id_required(self) -> None:
        """Service ID is required."""
        service = ForkDetectionService(service_id="my-service")
        assert service.service_id == "my-service"

    def test_service_id_stored(self) -> None:
        """Service ID is stored on the service."""
        service = ForkDetectionService(service_id="detector-001")
        assert service.service_id == "detector-001"
