"""Unit tests for WaiverDocumentedEvent domain event (Story 9.8, SC-4, SR-10).

Tests for the WaiverDocumentedEventPayload and WaiverStatus models.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- CT-12: Witnessing creates accountability -> Event must be signable
"""

import json
from datetime import datetime, timezone

import pytest

from src.domain.events.waiver import (
    WAIVER_DOCUMENTED_EVENT_TYPE,
    WAIVER_SYSTEM_AGENT_ID,
    WaiverDocumentedEventPayload,
    WaiverStatus,
)


class TestWaiverStatus:
    """Tests for WaiverStatus enum."""

    def test_active_status_value(self) -> None:
        """Test ACTIVE status has correct value."""
        assert WaiverStatus.ACTIVE.value == "ACTIVE"

    def test_implemented_status_value(self) -> None:
        """Test IMPLEMENTED status has correct value."""
        assert WaiverStatus.IMPLEMENTED.value == "IMPLEMENTED"

    def test_cancelled_status_value(self) -> None:
        """Test CANCELLED status has correct value."""
        assert WaiverStatus.CANCELLED.value == "CANCELLED"


class TestWaiverDocumentedEventPayload:
    """Tests for WaiverDocumentedEventPayload dataclass."""

    @pytest.fixture
    def valid_payload(self) -> WaiverDocumentedEventPayload:
        """Create a valid payload for testing."""
        return WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Legitimacy requires consent",
            what_is_waived="Full consent mechanism implementation",
            rationale="MVP focuses on constitutional infrastructure",
            target_phase="Phase 2 - Seeker Journey",
            status=WaiverStatus.ACTIVE,
            documented_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            documented_by=WAIVER_SYSTEM_AGENT_ID,
        )

    def test_payload_creation_success(self, valid_payload: WaiverDocumentedEventPayload) -> None:
        """Test successful payload creation with all fields."""
        assert valid_payload.waiver_id == "CT-15-MVP-WAIVER"
        assert valid_payload.constitutional_truth_id == "CT-15"
        assert valid_payload.constitutional_truth_statement == "Legitimacy requires consent"
        assert valid_payload.what_is_waived == "Full consent mechanism implementation"
        assert valid_payload.rationale == "MVP focuses on constitutional infrastructure"
        assert valid_payload.target_phase == "Phase 2 - Seeker Journey"
        assert valid_payload.status == WaiverStatus.ACTIVE
        assert valid_payload.documented_by == WAIVER_SYSTEM_AGENT_ID

    def test_payload_is_immutable(self, valid_payload: WaiverDocumentedEventPayload) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            valid_payload.waiver_id = "different-id"  # type: ignore

    def test_payload_equality(self) -> None:
        """Test two payloads with same values are equal."""
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        payload1 = WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Legitimacy requires consent",
            what_is_waived="Consent implementation",
            rationale="MVP scope",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=timestamp,
            documented_by="system:test",
        )
        payload2 = WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Legitimacy requires consent",
            what_is_waived="Consent implementation",
            rationale="MVP scope",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=timestamp,
            documented_by="system:test",
        )
        assert payload1 == payload2

    def test_payload_validation_empty_waiver_id(self) -> None:
        """Test validation fails for empty waiver_id."""
        with pytest.raises(ValueError, match="waiver_id is required"):
            WaiverDocumentedEventPayload(
                waiver_id="",
                constitutional_truth_id="CT-15",
                constitutional_truth_statement="Test",
                what_is_waived="Test",
                rationale="Test",
                target_phase="Phase 2",
                status=WaiverStatus.ACTIVE,
                documented_at=datetime.now(timezone.utc),
                documented_by="system:test",
            )

    def test_payload_validation_empty_ct_id(self) -> None:
        """Test validation fails for empty constitutional_truth_id."""
        with pytest.raises(ValueError, match="constitutional_truth_id is required"):
            WaiverDocumentedEventPayload(
                waiver_id="TEST-WAIVER",
                constitutional_truth_id="",
                constitutional_truth_statement="Test",
                what_is_waived="Test",
                rationale="Test",
                target_phase="Phase 2",
                status=WaiverStatus.ACTIVE,
                documented_at=datetime.now(timezone.utc),
                documented_by="system:test",
            )

    def test_payload_validation_empty_rationale(self) -> None:
        """Test validation fails for empty rationale."""
        with pytest.raises(ValueError, match="rationale is required"):
            WaiverDocumentedEventPayload(
                waiver_id="TEST-WAIVER",
                constitutional_truth_id="CT-15",
                constitutional_truth_statement="Test",
                what_is_waived="Test",
                rationale="",
                target_phase="Phase 2",
                status=WaiverStatus.ACTIVE,
                documented_at=datetime.now(timezone.utc),
                documented_by="system:test",
            )


class TestWaiverDocumentedEventPayloadToDict:
    """Tests for WaiverDocumentedEventPayload.to_dict() method."""

    def test_to_dict_contains_all_fields(self) -> None:
        """Test to_dict includes all required fields."""
        payload = WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Legitimacy requires consent",
            what_is_waived="Consent implementation",
            rationale="MVP scope",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            documented_by="system:test",
        )
        result = payload.to_dict()

        assert result["waiver_id"] == "CT-15-MVP-WAIVER"
        assert result["constitutional_truth_id"] == "CT-15"
        assert result["constitutional_truth_statement"] == "Legitimacy requires consent"
        assert result["what_is_waived"] == "Consent implementation"
        assert result["rationale"] == "MVP scope"
        assert result["target_phase"] == "Phase 2"
        assert result["status"] == "ACTIVE"
        assert result["documented_at"] == "2025-01-01T00:00:00+00:00"
        assert result["documented_by"] == "system:test"

    def test_to_dict_is_json_serializable(self) -> None:
        """Test to_dict output can be serialized to JSON."""
        payload = WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
            status=WaiverStatus.IMPLEMENTED,
            documented_at=datetime(2025, 6, 15, 12, 30, 0, tzinfo=timezone.utc),
            documented_by="system:test",
        )
        result = payload.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert json_str is not None
        assert len(json_str) > 0


class TestWaiverDocumentedEventPayloadSignableContent:
    """Tests for WaiverDocumentedEventPayload.signable_content() method (CT-12)."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes."""
        payload = WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            documented_by="system:test",
        )
        result = payload.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content produces same output for same input."""
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        payload1 = WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=timestamp,
            documented_by="system:test",
        )
        payload2 = WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=timestamp,
            documented_by="system:test",
        )
        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_differs_for_different_payloads(self) -> None:
        """Test signable_content differs when payload differs."""
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        payload1 = WaiverDocumentedEventPayload(
            waiver_id="CT-15-MVP-WAIVER",
            constitutional_truth_id="CT-15",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=timestamp,
            documented_by="system:test",
        )
        payload2 = WaiverDocumentedEventPayload(
            waiver_id="CT-16-MVP-WAIVER",  # Different ID
            constitutional_truth_id="CT-16",
            constitutional_truth_statement="Test",
            what_is_waived="Test",
            rationale="Test",
            target_phase="Phase 2",
            status=WaiverStatus.ACTIVE,
            documented_at=timestamp,
            documented_by="system:test",
        )
        assert payload1.signable_content() != payload2.signable_content()


class TestWaiverEventTypeConstants:
    """Tests for event type constants."""

    def test_event_type_constant_value(self) -> None:
        """Test event type constant has expected value."""
        assert WAIVER_DOCUMENTED_EVENT_TYPE == "waiver.documented"

    def test_system_agent_id_constant_value(self) -> None:
        """Test system agent ID constant has expected value."""
        assert WAIVER_SYSTEM_AGENT_ID == "system:waiver-documentation"
