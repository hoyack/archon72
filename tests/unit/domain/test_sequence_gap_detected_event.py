"""Unit tests for SequenceGapDetectedPayload (FR18-FR19, Story 3.7).

Tests the sequence gap detected event payload that records gap detection.
This event is witnessed and triggers investigation.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
- CT-3: Sequence is authoritative ordering
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone

import pytest

from src.domain.events.sequence_gap_detected import (
    SEQUENCE_GAP_DETECTED_EVENT_TYPE,
    SequenceGapDetectedPayload,
)


class TestSequenceGapDetectedEventType:
    """Tests for the event type constant."""

    def test_event_type_constant(self) -> None:
        """Test event type constant has expected value."""
        assert SEQUENCE_GAP_DETECTED_EVENT_TYPE == "sequence.gap_detected"

    def test_event_type_is_string(self) -> None:
        """Test event type constant is a string."""
        assert isinstance(SEQUENCE_GAP_DETECTED_EVENT_TYPE, str)

    def test_event_type_uses_dot_notation(self) -> None:
        """Test event type follows project naming convention (dot notation)."""
        assert "." in SEQUENCE_GAP_DETECTED_EVENT_TYPE


class TestSequenceGapDetectedPayload:
    """Tests for SequenceGapDetectedPayload dataclass."""

    @pytest.fixture
    def sample_payload(self) -> SequenceGapDetectedPayload:
        """Create a sample gap detection payload."""
        return SequenceGapDetectedPayload(
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            expected_sequence=5,
            actual_sequence=10,
            gap_size=5,
            missing_sequences=(5, 6, 7, 8, 9),
            detection_service_id="sequence_gap_detector",
            previous_check_timestamp=datetime(
                2025, 12, 28, 10, 29, 30, tzinfo=timezone.utc
            ),
        )

    def test_payload_creation(self, sample_payload: SequenceGapDetectedPayload) -> None:
        """Test payload can be created with all fields."""
        assert sample_payload.expected_sequence == 5
        assert sample_payload.actual_sequence == 10
        assert sample_payload.gap_size == 5
        assert sample_payload.missing_sequences == (5, 6, 7, 8, 9)
        assert sample_payload.detection_service_id == "sequence_gap_detector"

    def test_payload_is_frozen(
        self, sample_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_payload.expected_sequence = 10  # type: ignore

    def test_detection_timestamp_preserved(
        self, sample_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test detection timestamp is preserved exactly."""
        expected = datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc)
        assert sample_payload.detection_timestamp == expected
        assert sample_payload.detection_timestamp.tzinfo == timezone.utc

    def test_previous_check_timestamp_preserved(
        self, sample_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test previous check timestamp is preserved."""
        expected = datetime(2025, 12, 28, 10, 29, 30, tzinfo=timezone.utc)
        assert sample_payload.previous_check_timestamp == expected

    def test_single_missing_sequence(self) -> None:
        """Test payload with single missing sequence."""
        payload = SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=5,
            actual_sequence=6,
            gap_size=1,
            missing_sequences=(5,),
            detection_service_id="test",
            previous_check_timestamp=datetime.now(timezone.utc),
        )
        assert payload.gap_size == 1
        assert payload.missing_sequences == (5,)

    def test_large_gap(self) -> None:
        """Test payload with large gap (many missing sequences)."""
        missing = tuple(range(100, 200))  # 100 missing sequences
        payload = SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=100,
            actual_sequence=200,
            gap_size=100,
            missing_sequences=missing,
            detection_service_id="test",
            previous_check_timestamp=datetime.now(timezone.utc),
        )
        assert payload.gap_size == 100
        assert len(payload.missing_sequences) == 100


class TestSequenceGapDetectedPayloadSignableContent:
    """Tests for signable_content() method - witnessing support."""

    @pytest.fixture
    def fixed_payload(self) -> SequenceGapDetectedPayload:
        """Create a payload with fixed timestamps for deterministic testing."""
        return SequenceGapDetectedPayload(
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            expected_sequence=5,
            actual_sequence=10,
            gap_size=5,
            missing_sequences=(5, 6, 7, 8, 9),
            detection_service_id="test_detector",
            previous_check_timestamp=datetime(
                2025, 12, 28, 10, 29, 30, tzinfo=timezone.utc
            ),
        )

    def test_signable_content_returns_bytes(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content returns bytes."""
        content = fixed_payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content returns same bytes for same input."""
        content1 = fixed_payload.signable_content()
        content2 = fixed_payload.signable_content()
        assert content1 == content2

    def test_signable_content_includes_expected_sequence(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content includes expected sequence."""
        content = fixed_payload.signable_content()
        assert b"expected:5" in content

    def test_signable_content_includes_actual_sequence(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content includes actual sequence."""
        content = fixed_payload.signable_content()
        assert b"actual:10" in content

    def test_signable_content_includes_gap_size(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content includes gap size."""
        content = fixed_payload.signable_content()
        assert b"gap_size:5" in content

    def test_signable_content_includes_missing_sequences(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content includes missing sequences."""
        content = fixed_payload.signable_content()
        assert b"missing:5,6,7,8,9" in content

    def test_signable_content_includes_service_id(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content includes detection service ID."""
        content = fixed_payload.signable_content()
        assert b"service:test_detector" in content

    def test_signable_content_includes_timestamp(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content includes detection timestamp."""
        content = fixed_payload.signable_content()
        # ISO format timestamp should be present
        assert b"2025-12-28" in content

    def test_signable_content_includes_previous_check_timestamp(
        self, fixed_payload: SequenceGapDetectedPayload
    ) -> None:
        """Test signable_content includes previous check timestamp (M1 fix)."""
        content = fixed_payload.signable_content()
        # Previous check timestamp should be in the signable content
        assert b"previous_check:" in content
        # The actual timestamp value
        assert b"2025-12-28T10:29:30" in content

    def test_different_payloads_have_different_content(self) -> None:
        """Test different payloads produce different signable content."""
        now = datetime.now(timezone.utc)
        payload1 = SequenceGapDetectedPayload(
            detection_timestamp=now,
            expected_sequence=5,
            actual_sequence=10,
            gap_size=5,
            missing_sequences=(5, 6, 7, 8, 9),
            detection_service_id="detector1",
            previous_check_timestamp=now,
        )
        payload2 = SequenceGapDetectedPayload(
            detection_timestamp=now,
            expected_sequence=10,
            actual_sequence=15,
            gap_size=5,
            missing_sequences=(10, 11, 12, 13, 14),
            detection_service_id="detector1",
            previous_check_timestamp=now,
        )
        assert payload1.signable_content() != payload2.signable_content()


class TestSequenceGapDetectedPayloadUsage:
    """Tests for real-world usage patterns."""

    def test_gap_detection_scenario(self) -> None:
        """Test creating payload for gap detection (FR18-FR19)."""
        now = datetime.now(timezone.utc)
        previous = datetime(2025, 12, 28, 10, 29, 30, tzinfo=timezone.utc)

        payload = SequenceGapDetectedPayload(
            detection_timestamp=now,
            expected_sequence=100,
            actual_sequence=105,
            gap_size=5,
            missing_sequences=(100, 101, 102, 103, 104),
            detection_service_id="sequence_gap_monitor",
            previous_check_timestamp=previous,
        )

        # Verify payload captures all necessary information
        assert payload.expected_sequence == 100
        assert payload.actual_sequence == 105
        assert payload.gap_size == 5
        assert 100 in payload.missing_sequences
        assert 104 in payload.missing_sequences

        # Verify signable content for witnessing
        content = payload.signable_content()
        assert isinstance(content, bytes)
        assert len(content) > 0
