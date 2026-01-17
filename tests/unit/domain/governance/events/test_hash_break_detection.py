"""Unit tests for hash_break_detection module.

Story: consent-gov-1.3: Hash Chain Implementation

Tests hash break detection per AC8.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.events.event_envelope import (
    EventMetadata,
    GovernanceEvent,
)
from src.domain.governance.events.hash_algorithms import GENESIS_PREV_HASH
from src.domain.governance.events.hash_break_detection import (
    HASH_BREAK_EVENT_TYPE,
    HashBreakDetectionResult,
    HashBreakDetector,
    HashBreakInfo,
    HashBreakType,
)
from src.domain.governance.events.hash_chain import add_hash_to_event


def make_test_event(
    event_type: str = "executive.task.accepted",
    payload: dict | None = None,
    prev_hash: str = "",
    hash_: str = "",
) -> GovernanceEvent:
    """Create a test GovernanceEvent."""
    metadata = EventMetadata(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        actor_id="test-actor",
        schema_version="1.0.0",
        trace_id=str(uuid4()),
        prev_hash=prev_hash,
        hash=hash_,
    )
    return GovernanceEvent(
        metadata=metadata,
        payload=payload or {"key": "value"},
    )


class TestHashBreakType:
    """Tests for HashBreakType enum."""

    def test_hash_mismatch_type(self) -> None:
        """HASH_MISMATCH type exists."""
        assert HashBreakType.HASH_MISMATCH.value == "hash_mismatch"

    def test_chain_break_type(self) -> None:
        """CHAIN_BREAK type exists."""
        assert HashBreakType.CHAIN_BREAK.value == "chain_break"

    def test_sequence_gap_type(self) -> None:
        """SEQUENCE_GAP type exists."""
        assert HashBreakType.SEQUENCE_GAP.value == "sequence_gap"


class TestHashBreakInfo:
    """Tests for HashBreakInfo dataclass."""

    def test_hash_break_info_is_frozen(self) -> None:
        """HashBreakInfo is immutable."""
        info = HashBreakInfo(
            break_type=HashBreakType.HASH_MISMATCH,
            sequence=42,
            event_id=uuid4(),
            expected_hash="blake3:aaa...",
            actual_hash="blake3:bbb...",
            detected_at=datetime.now(timezone.utc),
            detector_id="test-detector",
        )
        with pytest.raises(Exception):
            info.sequence = 100  # type: ignore

    def test_hash_break_info_with_details(self) -> None:
        """HashBreakInfo can include additional details."""
        info = HashBreakInfo(
            break_type=HashBreakType.CHAIN_BREAK,
            sequence=10,
            event_id=uuid4(),
            expected_hash="expected",
            actual_hash="actual",
            detected_at=datetime.now(timezone.utc),
            detector_id="detector",
            details="Chain link broken between events 9 and 10",
        )
        assert "Chain link" in info.details


class TestHashBreakDetector:
    """Tests for HashBreakDetector class (AC8)."""

    def test_detector_has_id(self) -> None:
        """Detector stores its identifier."""
        detector = HashBreakDetector("ledger-service")
        assert detector.detector_id == "ledger-service"

    def test_check_valid_genesis_event(self) -> None:
        """Valid genesis event passes check."""
        detector = HashBreakDetector("test")
        unhashed_event = make_test_event()
        hashed_event = add_hash_to_event(unhashed_event, None, "blake3")

        result = detector.check_event(
            hashed_event,
            None,
            datetime.now(timezone.utc),
        )

        assert result.has_break is False
        assert result.events_verified == 1

    def test_check_valid_chained_event(self) -> None:
        """Valid chained event passes check."""
        detector = HashBreakDetector("test")

        event1 = add_hash_to_event(make_test_event(), None, "blake3")
        event2 = add_hash_to_event(
            make_test_event(payload={"seq": 2}),
            event1.hash,
            "blake3",
        )

        result = detector.check_event(
            event2,
            event1,
            datetime.now(timezone.utc),
        )

        assert result.has_break is False
        assert result.events_verified == 1

    def test_detect_hash_mismatch(self) -> None:
        """Detects when event hash doesn't match content."""
        detector = HashBreakDetector("test")
        now = datetime.now(timezone.utc)

        # Create event with wrong hash
        event = make_test_event(
            prev_hash=GENESIS_PREV_HASH,
            hash_=f"blake3:{'x' * 64}",  # Wrong hash
        )

        result = detector.check_event(event, None, now)

        assert result.has_break is True
        assert result.break_info is not None
        assert result.break_info.break_type == HashBreakType.HASH_MISMATCH
        assert result.break_info.detector_id == "test"

    def test_detect_chain_break(self) -> None:
        """Detects when prev_hash doesn't match previous event."""
        detector = HashBreakDetector("test")
        now = datetime.now(timezone.utc)

        # Create valid first event
        event1 = add_hash_to_event(make_test_event(), None, "blake3")

        # Create second event with valid hash but wrong prev_hash
        event2_unhashed = make_test_event(payload={"seq": 2})
        # Manually create event2 with correct hash of its content
        # but wrong prev_hash
        from src.domain.governance.events.hash_chain import compute_event_hash_with_prev

        wrong_prev_hash = f"blake3:{'a' * 64}"
        correct_hash = compute_event_hash_with_prev(
            event2_unhashed, wrong_prev_hash, "blake3"
        )

        event2 = GovernanceEvent(
            metadata=EventMetadata(
                event_id=event2_unhashed.event_id,
                event_type=event2_unhashed.event_type,
                timestamp=event2_unhashed.timestamp,
                actor_id=event2_unhashed.actor_id,
                schema_version=event2_unhashed.schema_version,
                trace_id=event2_unhashed.trace_id,
                prev_hash=wrong_prev_hash,
                hash=correct_hash,
            ),
            payload=dict(event2_unhashed.payload),
        )

        result = detector.check_event(event2, event1, now)

        assert result.has_break is True
        assert result.break_info is not None
        assert result.break_info.break_type == HashBreakType.CHAIN_BREAK

    def test_check_sequence_all_valid(self) -> None:
        """check_sequence returns success for valid chain."""
        detector = HashBreakDetector("test")
        now = datetime.now(timezone.utc)

        # Create chain of 3 events
        events = []
        prev_hash = None
        for i in range(3):
            event = add_hash_to_event(
                make_test_event(payload={"seq": i}),
                prev_hash,
                "blake3",
            )
            events.append(event)
            prev_hash = event.hash

        result = detector.check_sequence(events, now)

        assert result.has_break is False
        assert result.events_verified == 3

    def test_check_sequence_finds_break(self) -> None:
        """check_sequence detects break in chain."""
        detector = HashBreakDetector("test")
        now = datetime.now(timezone.utc)

        # Create valid first event
        event1 = add_hash_to_event(make_test_event(), None, "blake3")

        # Create invalid second event (wrong hash)
        event2 = make_test_event(
            prev_hash=event1.hash,
            hash_=f"blake3:{'z' * 64}",
        )

        result = detector.check_sequence([event1, event2], now)

        assert result.has_break is True
        assert result.events_verified == 1  # Stopped at first break

    def test_check_empty_sequence(self) -> None:
        """check_sequence handles empty list."""
        detector = HashBreakDetector("test")
        result = detector.check_sequence([], datetime.now(timezone.utc))

        assert result.has_break is False
        assert result.events_verified == 0


class TestHashBreakEventPayload:
    """Tests for hash break event payload creation."""

    def test_create_break_event_payload(self) -> None:
        """Creates payload for ledger.integrity.hash_break_detected event."""
        detector = HashBreakDetector("ledger-service")
        now = datetime.now(timezone.utc)

        # Create event with wrong hash to trigger break
        event = make_test_event(
            prev_hash=GENESIS_PREV_HASH,
            hash_=f"blake3:{'x' * 64}",
        )

        result = detector.check_event(event, None, now)

        assert result.has_break is True

        payload = detector.create_break_event_payload(result)

        assert payload["break_type"] == "hash_mismatch"
        assert "affected_event_id" in payload
        assert payload["detector_id"] == "ledger-service"

    def test_create_break_event_payload_raises_for_no_break(self) -> None:
        """create_break_event_payload raises for result with no break."""
        detector = HashBreakDetector("test")

        result = HashBreakDetectionResult(has_break=False, events_verified=1)

        with pytest.raises(ValueError, match="no break"):
            detector.create_break_event_payload(result)


class TestHashBreakEventType:
    """Tests for hash break event type constant."""

    def test_event_type_is_ledger_integrity(self) -> None:
        """HASH_BREAK_EVENT_TYPE is the expected value."""
        assert HASH_BREAK_EVENT_TYPE == "ledger.integrity.hash_break_detected"

    def test_event_type_follows_convention(self) -> None:
        """Event type follows branch.noun.verb convention."""
        parts = HASH_BREAK_EVENT_TYPE.split(".")
        assert len(parts) == 3
        assert parts[0] == "ledger"
        assert parts[1] == "integrity"


class TestHashBreakDetectionResult:
    """Tests for HashBreakDetectionResult dataclass."""

    def test_result_is_frozen(self) -> None:
        """HashBreakDetectionResult is immutable."""
        result = HashBreakDetectionResult(has_break=False, events_verified=5)
        with pytest.raises(Exception):
            result.has_break = True  # type: ignore

    def test_result_with_break_info(self) -> None:
        """Result can include break info."""
        info = HashBreakInfo(
            break_type=HashBreakType.HASH_MISMATCH,
            sequence=1,
            event_id=uuid4(),
            expected_hash="a",
            actual_hash="b",
            detected_at=datetime.now(timezone.utc),
            detector_id="test",
        )
        result = HashBreakDetectionResult(
            has_break=True,
            break_info=info,
            events_verified=1,
        )
        assert result.break_info is not None
        assert result.break_info.break_type == HashBreakType.HASH_MISMATCH
