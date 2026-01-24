"""Unit tests for adoption ratio event payloads (Story 8.6, PREVENT-7).

Tests event payload creation, serialization, and signable content for witnessing.

Constitutional Constraints:
- PREVENT-7: Alert when adoption ratio exceeds 50%
- CT-12: All events must be witnessed
- D2: Use to_dict() not asdict(), include schema_version
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.adoption_ratio import (
    ADOPTION_RATIO_ALERT_SCHEMA_VERSION,
    ADOPTION_RATIO_EXCEEDED_EVENT_TYPE,
    ADOPTION_RATIO_NORMALIZED_EVENT_TYPE,
    AdoptionRatioExceededEventPayload,
    AdoptionRatioNormalizedEventPayload,
)


class TestAdoptionRatioExceededEventPayload:
    """Test AdoptionRatioExceededEventPayload (PREVENT-7, CT-12)."""

    def test_create_event_payload(self):
        """Create event payload with all fields."""
        # Given
        event_id = uuid4()
        alert_id = uuid4()
        king_id = uuid4()
        occurred_at = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)

        # When
        payload = AdoptionRatioExceededEventPayload(
            event_id=event_id,
            alert_id=alert_id,
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_ratio=0.65,
            threshold=0.50,
            severity="WARN",
            adopting_kings=(str(king_id),),
            adoption_count=65,
            escalation_count=100,
            trend_delta=0.05,
            occurred_at=occurred_at,
        )

        # Then
        assert payload.event_id == event_id
        assert payload.alert_id == alert_id
        assert payload.realm_id == "technology"
        assert payload.cycle_id == "2026-W04"
        assert payload.adoption_ratio == 0.65
        assert payload.threshold == 0.50
        assert payload.severity == "WARN"
        assert len(payload.adopting_kings) == 1
        assert payload.adoption_count == 65
        assert payload.escalation_count == 100
        assert payload.trend_delta == 0.05
        assert payload.occurred_at == occurred_at
        assert payload.schema_version == ADOPTION_RATIO_ALERT_SCHEMA_VERSION

    def test_to_dict_serialization(self):
        """to_dict() properly serializes all fields (D2 compliance)."""
        # Given
        event_id = uuid4()
        alert_id = uuid4()
        king_id = uuid4()
        occurred_at = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)

        payload = AdoptionRatioExceededEventPayload(
            event_id=event_id,
            alert_id=alert_id,
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_ratio=0.65,
            threshold=0.50,
            severity="WARN",
            adopting_kings=(str(king_id),),
            adoption_count=65,
            escalation_count=100,
            trend_delta=0.05,
            occurred_at=occurred_at,
        )

        # When
        result = payload.to_dict()

        # Then
        assert result["event_id"] == str(event_id)
        assert result["alert_id"] == str(alert_id)
        assert result["realm_id"] == "technology"
        assert result["cycle_id"] == "2026-W04"
        assert result["adoption_ratio"] == 0.65
        assert result["threshold"] == 0.50
        assert result["severity"] == "WARN"
        assert result["adopting_kings"] == [str(king_id)]
        assert result["adoption_count"] == 65
        assert result["escalation_count"] == 100
        assert result["trend_delta"] == 0.05
        assert result["occurred_at"] == "2026-01-20T10:00:00+00:00"
        assert result["schema_version"] == ADOPTION_RATIO_ALERT_SCHEMA_VERSION

    def test_to_dict_is_json_serializable(self):
        """to_dict() result can be JSON serialized."""
        # Given
        payload = AdoptionRatioExceededEventPayload(
            event_id=uuid4(),
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_ratio=0.65,
            threshold=0.50,
            severity="WARN",
            adopting_kings=(str(uuid4()),),
            adoption_count=65,
            escalation_count=100,
            trend_delta=None,
            occurred_at=datetime.now(timezone.utc),
        )

        # When
        result = json.dumps(payload.to_dict())

        # Then
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["realm_id"] == "technology"

    def test_signable_content_returns_bytes(self):
        """signable_content() returns canonical bytes for witnessing (CT-12)."""
        # Given
        payload = AdoptionRatioExceededEventPayload(
            event_id=uuid4(),
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_ratio=0.65,
            threshold=0.50,
            severity="WARN",
            adopting_kings=(str(uuid4()),),
            adoption_count=65,
            escalation_count=100,
            trend_delta=0.05,
            occurred_at=datetime.now(timezone.utc),
        )

        # When
        content = payload.signable_content()

        # Then
        assert isinstance(content, bytes)
        # Should be valid JSON
        parsed = json.loads(content.decode("utf-8"))
        assert parsed["realm_id"] == "technology"

    def test_signable_content_is_deterministic(self):
        """signable_content() produces same output for same input (CT-12)."""
        # Given
        event_id = uuid4()
        alert_id = uuid4()
        king_id = str(uuid4())
        occurred_at = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)

        payload1 = AdoptionRatioExceededEventPayload(
            event_id=event_id,
            alert_id=alert_id,
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_ratio=0.65,
            threshold=0.50,
            severity="WARN",
            adopting_kings=(king_id,),
            adoption_count=65,
            escalation_count=100,
            trend_delta=0.05,
            occurred_at=occurred_at,
        )

        payload2 = AdoptionRatioExceededEventPayload(
            event_id=event_id,
            alert_id=alert_id,
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_ratio=0.65,
            threshold=0.50,
            severity="WARN",
            adopting_kings=(king_id,),
            adoption_count=65,
            escalation_count=100,
            trend_delta=0.05,
            occurred_at=occurred_at,
        )

        # When/Then
        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_has_sorted_keys(self):
        """signable_content() JSON has sorted keys for determinism (CT-12)."""
        # Given
        payload = AdoptionRatioExceededEventPayload(
            event_id=uuid4(),
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_ratio=0.65,
            threshold=0.50,
            severity="WARN",
            adopting_kings=(str(uuid4()),),
            adoption_count=65,
            escalation_count=100,
            trend_delta=0.05,
            occurred_at=datetime.now(timezone.utc),
        )

        # When
        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())

        # Then
        assert keys == sorted(keys)

    def test_event_is_frozen(self):
        """Event payload is immutable (CT-12)."""
        # Given
        payload = AdoptionRatioExceededEventPayload(
            event_id=uuid4(),
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W04",
            adoption_ratio=0.65,
            threshold=0.50,
            severity="WARN",
            adopting_kings=(str(uuid4()),),
            adoption_count=65,
            escalation_count=100,
            trend_delta=0.05,
            occurred_at=datetime.now(timezone.utc),
        )

        # When/Then
        with pytest.raises(Exception):  # FrozenInstanceError
            payload.adoption_ratio = 0.99  # type: ignore


class TestAdoptionRatioNormalizedEventPayload:
    """Test AdoptionRatioNormalizedEventPayload (CT-12)."""

    def test_create_event_payload(self):
        """Create normalized event payload with all fields."""
        # Given
        event_id = uuid4()
        alert_id = uuid4()
        normalized_at = datetime(2026, 1, 27, 10, 0, 0, tzinfo=timezone.utc)

        # When
        payload = AdoptionRatioNormalizedEventPayload(
            event_id=event_id,
            alert_id=alert_id,
            realm_id="technology",
            cycle_id="2026-W05",
            new_adoption_ratio=0.35,
            previous_ratio=0.65,
            alert_duration_seconds=604800,  # 1 week
            normalized_at=normalized_at,
        )

        # Then
        assert payload.event_id == event_id
        assert payload.alert_id == alert_id
        assert payload.realm_id == "technology"
        assert payload.cycle_id == "2026-W05"
        assert payload.new_adoption_ratio == 0.35
        assert payload.previous_ratio == 0.65
        assert payload.alert_duration_seconds == 604800
        assert payload.normalized_at == normalized_at
        assert payload.schema_version == ADOPTION_RATIO_ALERT_SCHEMA_VERSION

    def test_to_dict_serialization(self):
        """to_dict() properly serializes all fields (D2 compliance)."""
        # Given
        event_id = uuid4()
        alert_id = uuid4()
        normalized_at = datetime(2026, 1, 27, 10, 0, 0, tzinfo=timezone.utc)

        payload = AdoptionRatioNormalizedEventPayload(
            event_id=event_id,
            alert_id=alert_id,
            realm_id="technology",
            cycle_id="2026-W05",
            new_adoption_ratio=0.35,
            previous_ratio=0.65,
            alert_duration_seconds=604800,
            normalized_at=normalized_at,
        )

        # When
        result = payload.to_dict()

        # Then
        assert result["event_id"] == str(event_id)
        assert result["alert_id"] == str(alert_id)
        assert result["realm_id"] == "technology"
        assert result["cycle_id"] == "2026-W05"
        assert result["new_adoption_ratio"] == 0.35
        assert result["previous_ratio"] == 0.65
        assert result["alert_duration_seconds"] == 604800
        assert result["normalized_at"] == "2026-01-27T10:00:00+00:00"
        assert result["schema_version"] == ADOPTION_RATIO_ALERT_SCHEMA_VERSION

    def test_to_dict_is_json_serializable(self):
        """to_dict() result can be JSON serialized."""
        # Given
        payload = AdoptionRatioNormalizedEventPayload(
            event_id=uuid4(),
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W05",
            new_adoption_ratio=0.35,
            previous_ratio=0.65,
            alert_duration_seconds=604800,
            normalized_at=datetime.now(timezone.utc),
        )

        # When
        result = json.dumps(payload.to_dict())

        # Then
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["realm_id"] == "technology"

    def test_signable_content_returns_bytes(self):
        """signable_content() returns canonical bytes for witnessing (CT-12)."""
        # Given
        payload = AdoptionRatioNormalizedEventPayload(
            event_id=uuid4(),
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W05",
            new_adoption_ratio=0.35,
            previous_ratio=0.65,
            alert_duration_seconds=604800,
            normalized_at=datetime.now(timezone.utc),
        )

        # When
        content = payload.signable_content()

        # Then
        assert isinstance(content, bytes)
        # Should be valid JSON
        parsed = json.loads(content.decode("utf-8"))
        assert parsed["realm_id"] == "technology"

    def test_signable_content_is_deterministic(self):
        """signable_content() produces same output for same input (CT-12)."""
        # Given
        event_id = uuid4()
        alert_id = uuid4()
        normalized_at = datetime(2026, 1, 27, 10, 0, 0, tzinfo=timezone.utc)

        payload1 = AdoptionRatioNormalizedEventPayload(
            event_id=event_id,
            alert_id=alert_id,
            realm_id="technology",
            cycle_id="2026-W05",
            new_adoption_ratio=0.35,
            previous_ratio=0.65,
            alert_duration_seconds=604800,
            normalized_at=normalized_at,
        )

        payload2 = AdoptionRatioNormalizedEventPayload(
            event_id=event_id,
            alert_id=alert_id,
            realm_id="technology",
            cycle_id="2026-W05",
            new_adoption_ratio=0.35,
            previous_ratio=0.65,
            alert_duration_seconds=604800,
            normalized_at=normalized_at,
        )

        # When/Then
        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_has_sorted_keys(self):
        """signable_content() JSON has sorted keys for determinism (CT-12)."""
        # Given
        payload = AdoptionRatioNormalizedEventPayload(
            event_id=uuid4(),
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W05",
            new_adoption_ratio=0.35,
            previous_ratio=0.65,
            alert_duration_seconds=604800,
            normalized_at=datetime.now(timezone.utc),
        )

        # When
        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())

        # Then
        assert keys == sorted(keys)

    def test_event_is_frozen(self):
        """Event payload is immutable (CT-12)."""
        # Given
        payload = AdoptionRatioNormalizedEventPayload(
            event_id=uuid4(),
            alert_id=uuid4(),
            realm_id="technology",
            cycle_id="2026-W05",
            new_adoption_ratio=0.35,
            previous_ratio=0.65,
            alert_duration_seconds=604800,
            normalized_at=datetime.now(timezone.utc),
        )

        # When/Then
        with pytest.raises(Exception):  # FrozenInstanceError
            payload.new_adoption_ratio = 0.99  # type: ignore


class TestEventTypeConstants:
    """Test event type constants."""

    def test_exceeded_event_type(self):
        """Exceeded event type constant is correct."""
        assert ADOPTION_RATIO_EXCEEDED_EVENT_TYPE == "adoption_ratio.alert.exceeded"

    def test_normalized_event_type(self):
        """Normalized event type constant is correct."""
        assert ADOPTION_RATIO_NORMALIZED_EVENT_TYPE == "adoption_ratio.alert.normalized"

    def test_schema_version(self):
        """Schema version constant is defined."""
        assert ADOPTION_RATIO_ALERT_SCHEMA_VERSION == 1
