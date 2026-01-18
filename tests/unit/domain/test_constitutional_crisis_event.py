"""Unit tests for ConstitutionalCrisisPayload (Story 3.2, Task 1.6).

Tests the constitutional crisis event payload that records system
halt triggers. This event MUST be recorded BEFORE halt takes effect.

Constitutional Constraints:
- FR17: System SHALL halt immediately when crisis detected
- CT-11: Silent failure destroys legitimacy
- RT-2: Crisis event recorded BEFORE halt
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.constitutional_crisis import (
    CONSTITUTIONAL_CRISIS_EVENT_TYPE,
    ConstitutionalCrisisPayload,
    CrisisType,
)


class TestCrisisType:
    """Tests for CrisisType enum."""

    def test_fork_detected_value(self) -> None:
        """Test FORK_DETECTED has expected string value."""
        assert CrisisType.FORK_DETECTED.value == "fork_detected"

    def test_sequence_gap_detected_value(self) -> None:
        """Test SEQUENCE_GAP_DETECTED has expected string value (Story 3.7)."""
        assert CrisisType.SEQUENCE_GAP_DETECTED.value == "sequence_gap_detected"

    def test_crisis_type_is_string_enum(self) -> None:
        """Test CrisisType inherits from str for JSON serialization."""
        assert isinstance(CrisisType.FORK_DETECTED, str)
        assert isinstance(CrisisType.SEQUENCE_GAP_DETECTED, str)

    def test_crisis_type_can_be_used_as_string(self) -> None:
        """Test CrisisType can be used directly in string contexts."""
        crisis = CrisisType.FORK_DETECTED
        assert f"Crisis: {crisis}" == "Crisis: fork_detected"
        gap_crisis = CrisisType.SEQUENCE_GAP_DETECTED
        assert f"Crisis: {gap_crisis}" == "Crisis: sequence_gap_detected"


class TestConstitutionalCrisisEventType:
    """Tests for the event type constant."""

    def test_event_type_constant(self) -> None:
        """Test event type constant has expected value."""
        assert CONSTITUTIONAL_CRISIS_EVENT_TYPE == "constitutional.crisis"

    def test_event_type_is_string(self) -> None:
        """Test event type constant is a string."""
        assert isinstance(CONSTITUTIONAL_CRISIS_EVENT_TYPE, str)


class TestConstitutionalCrisisPayload:
    """Tests for ConstitutionalCrisisPayload dataclass."""

    @pytest.fixture
    def sample_triggering_ids(self) -> tuple[UUID, ...]:
        """Create sample triggering event IDs."""
        return (uuid4(), uuid4())

    @pytest.fixture
    def sample_payload(
        self, sample_triggering_ids: tuple[UUID, ...]
    ) -> ConstitutionalCrisisPayload:
        """Create a sample crisis payload."""
        return ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Fork: 2 conflicting events with same prev_hash",
            triggering_event_ids=sample_triggering_ids,
            detecting_service_id="fork-monitor-001",
        )

    def test_payload_creation(
        self, sample_payload: ConstitutionalCrisisPayload
    ) -> None:
        """Test payload can be created with all fields."""
        assert sample_payload.crisis_type == CrisisType.FORK_DETECTED
        assert isinstance(sample_payload.detection_timestamp, datetime)
        assert "Fork" in sample_payload.detection_details
        assert len(sample_payload.triggering_event_ids) == 2
        assert sample_payload.detecting_service_id == "fork-monitor-001"

    def test_payload_is_frozen(
        self, sample_payload: ConstitutionalCrisisPayload
    ) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_payload.crisis_type = CrisisType.FORK_DETECTED  # type: ignore

    def test_payload_equality(self, sample_triggering_ids: tuple[UUID, ...]) -> None:
        """Test two payloads with same values are equal."""
        timestamp = datetime.now(timezone.utc)
        payload1 = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=timestamp,
            detection_details="Test crisis",
            triggering_event_ids=sample_triggering_ids,
            detecting_service_id="test-service",
        )
        payload2 = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=timestamp,
            detection_details="Test crisis",
            triggering_event_ids=sample_triggering_ids,
            detecting_service_id="test-service",
        )
        assert payload1 == payload2

    def test_list_to_tuple_conversion(self) -> None:
        """Test lists are converted to tuples for immutability."""
        event_ids = [uuid4(), uuid4()]  # List, not tuple
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Test crisis",
            triggering_event_ids=event_ids,  # type: ignore
            detecting_service_id="test-service",
        )
        assert isinstance(payload.triggering_event_ids, tuple)

    def test_empty_triggering_event_ids(self) -> None:
        """Test payload can be created with empty triggering IDs."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Crisis with no specific trigger",
            triggering_event_ids=(),
            detecting_service_id="test-service",
        )
        assert len(payload.triggering_event_ids) == 0

    def test_single_triggering_event_id(self) -> None:
        """Test payload with single triggering event ID."""
        event_id = uuid4()
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Single event crisis",
            triggering_event_ids=(event_id,),
            detecting_service_id="test-service",
        )
        assert len(payload.triggering_event_ids) == 1
        assert payload.triggering_event_ids[0] == event_id

    def test_timestamp_is_preserved(self) -> None:
        """Test detection timestamp is preserved exactly."""
        # Use a specific timestamp with microseconds
        timestamp = datetime(2025, 12, 28, 10, 30, 45, 123456, tzinfo=timezone.utc)
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=timestamp,
            detection_details="Test crisis",
            triggering_event_ids=(),
            detecting_service_id="test-service",
        )
        assert payload.detection_timestamp == timestamp
        assert payload.detection_timestamp.tzinfo == timezone.utc

    def test_detection_details_can_be_long(self) -> None:
        """Test detection details can contain long descriptions."""
        long_details = "A" * 1000  # 1000 character description
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details=long_details,
            triggering_event_ids=(),
            detecting_service_id="test-service",
        )
        assert len(payload.detection_details) == 1000

    def test_payload_is_hashable(
        self, sample_payload: ConstitutionalCrisisPayload
    ) -> None:
        """Test frozen payload is hashable (can be used in sets)."""
        payload_set = {sample_payload}
        assert sample_payload in payload_set

    def test_many_triggering_event_ids(self) -> None:
        """Test payload with many triggering event IDs."""
        event_ids = tuple(uuid4() for _ in range(72))  # 72 archons worth
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details="Mass crisis",
            triggering_event_ids=event_ids,
            detecting_service_id="test-service",
        )
        assert len(payload.triggering_event_ids) == 72


class TestConstitutionalCrisisPayloadUsage:
    """Tests for real-world usage patterns."""

    def test_fork_detection_scenario(self) -> None:
        """Test creating crisis payload for fork detection (FR17)."""
        # Simulate fork detection - two events claiming same prev_hash
        conflicting_event_1 = uuid4()
        conflicting_event_2 = uuid4()

        crisis = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime.now(timezone.utc),
            detection_details=(
                f"FR17: Fork detected - 2 events claim same prev_hash. "
                f"Events: {conflicting_event_1}, {conflicting_event_2}"
            ),
            triggering_event_ids=(conflicting_event_1, conflicting_event_2),
            detecting_service_id="fork-monitor-main",
        )

        # Verify the crisis captures all necessary information
        assert crisis.crisis_type == CrisisType.FORK_DETECTED
        assert "FR17" in crisis.detection_details
        assert str(conflicting_event_1) in crisis.detection_details
        assert str(conflicting_event_2) in crisis.detection_details
        assert conflicting_event_1 in crisis.triggering_event_ids
        assert conflicting_event_2 in crisis.triggering_event_ids


class TestConstitutionalCrisisPayloadSignableContent:
    """Tests for signable_content() method (CT-12 witnessing support)."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes for signing."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            detection_details="Test crisis",
            triggering_event_ids=(),
            detecting_service_id="test-service",
        )
        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test same payload produces same signable content (critical for verification)."""
        event_id = UUID("12345678-1234-5678-1234-567812345678")
        timestamp = datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc)

        payload1 = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=timestamp,
            detection_details="Test crisis",
            triggering_event_ids=(event_id,),
            detecting_service_id="test-service",
        )
        payload2 = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=timestamp,
            detection_details="Test crisis",
            triggering_event_ids=(event_id,),
            detecting_service_id="test-service",
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_includes_crisis_type(self) -> None:
        """Test signable content includes crisis type value."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            detection_details="Test",
            triggering_event_ids=(),
            detecting_service_id="test",
        )
        content = payload.signable_content().decode("utf-8")
        assert "fork_detected" in content

    def test_signable_content_includes_timestamp(self) -> None:
        """Test signable content includes detection timestamp."""
        timestamp = datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc)
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=timestamp,
            detection_details="Test",
            triggering_event_ids=(),
            detecting_service_id="test",
        )
        content = payload.signable_content().decode("utf-8")
        assert timestamp.isoformat() in content

    def test_signable_content_includes_details(self) -> None:
        """Test signable content includes detection details."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            detection_details="Unique crisis details for test",
            triggering_event_ids=(),
            detecting_service_id="test",
        )
        content = payload.signable_content().decode("utf-8")
        assert "Unique crisis details for test" in content

    def test_signable_content_includes_service_id(self) -> None:
        """Test signable content includes detecting service ID."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            detection_details="Test",
            triggering_event_ids=(),
            detecting_service_id="fork-monitor-unique-123",
        )
        content = payload.signable_content().decode("utf-8")
        assert "fork-monitor-unique-123" in content

    def test_signable_content_includes_triggering_events(self) -> None:
        """Test signable content includes triggering event IDs."""
        event_id = UUID("12345678-1234-5678-1234-567812345678")
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            detection_details="Test",
            triggering_event_ids=(event_id,),
            detecting_service_id="test",
        )
        content = payload.signable_content().decode("utf-8")
        assert str(event_id) in content

    def test_signable_content_sorts_event_ids(self) -> None:
        """Test triggering event IDs are sorted for deterministic output."""
        # Create UUIDs that would sort differently if not explicitly sorted
        event_id_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        event_id_2 = UUID("11111111-1111-1111-1111-111111111111")

        # Create payloads with IDs in different orders
        payload1 = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            detection_details="Test",
            triggering_event_ids=(event_id_1, event_id_2),
            detecting_service_id="test",
        )
        payload2 = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            detection_details="Test",
            triggering_event_ids=(event_id_2, event_id_1),  # Reversed order
            detecting_service_id="test",
        )

        # Should produce same signable content due to sorting
        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_different_crisis_types(self) -> None:
        """Test different crisis types produce different signable content."""
        timestamp = datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc)

        fork_payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=timestamp,
            detection_details="Test",
            triggering_event_ids=(),
            detecting_service_id="test",
        )
        gap_payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.SEQUENCE_GAP_DETECTED,
            detection_timestamp=timestamp,
            detection_details="Test",
            triggering_event_ids=(),
            detecting_service_id="test",
        )

        assert fork_payload.signable_content() != gap_payload.signable_content()

    def test_signable_content_empty_triggering_events(self) -> None:
        """Test signable content handles empty triggering events."""
        payload = ConstitutionalCrisisPayload(
            crisis_type=CrisisType.FORK_DETECTED,
            detection_timestamp=datetime(2025, 12, 28, 10, 30, 0, tzinfo=timezone.utc),
            detection_details="Test",
            triggering_event_ids=(),
            detecting_service_id="test",
        )
        content = payload.signable_content()
        # Should not raise and should produce valid bytes
        assert isinstance(content, bytes)
        assert len(content) > 0
