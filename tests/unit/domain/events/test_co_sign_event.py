"""Unit tests for co-sign domain events (Story 5.2).

Tests for:
- CoSignRecordedEvent (FR-6.1, FR-6.4, CT-12)
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events import (
    CO_SIGN_EVENT_SCHEMA_VERSION,
    CO_SIGN_RECORDED_EVENT_TYPE,
    CO_SIGN_SYSTEM_AGENT_ID,
    CoSignRecordedEvent,
)


class TestCoSignEventConstants:
    """Tests for co-sign event constants."""

    def test_co_sign_recorded_event_type(self) -> None:
        """Event type should follow naming convention."""
        assert CO_SIGN_RECORDED_EVENT_TYPE == "petition.co_sign.recorded"

    def test_co_sign_event_schema_version(self) -> None:
        """Schema version should be 1.0.0."""
        assert CO_SIGN_EVENT_SCHEMA_VERSION == "1.0.0"

    def test_co_sign_system_agent_id(self) -> None:
        """System agent ID should be set."""
        assert CO_SIGN_SYSTEM_AGENT_ID == "co-sign-system"


class TestCoSignRecordedEvent:
    """Tests for CoSignRecordedEvent (FR-6.1, FR-6.4, CT-12)."""

    @pytest.fixture
    def sample_event(self) -> CoSignRecordedEvent:
        """Create a sample event for testing."""
        return CoSignRecordedEvent(
            cosign_id=uuid4(),
            petition_id=uuid4(),
            signer_id=uuid4(),
            signed_at=datetime.now(timezone.utc),
            content_hash="a" * 64,  # 64 hex chars = 32 bytes
            co_signer_count=42,
        )

    def test_event_is_frozen(self, sample_event: CoSignRecordedEvent) -> None:
        """Event should be immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_event.co_signer_count = 100  # type: ignore

    def test_event_equality(self) -> None:
        """Two events with same values should be equal."""
        now = datetime.now(timezone.utc)
        cosign_id = uuid4()
        petition_id = uuid4()
        signer_id = uuid4()

        event1 = CoSignRecordedEvent(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=now,
            content_hash="abc123",
            co_signer_count=5,
        )
        event2 = CoSignRecordedEvent(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=now,
            content_hash="abc123",
            co_signer_count=5,
        )

        assert event1 == event2

    def test_signable_content_returns_bytes(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """signable_content should return bytes for witnessing (CT-12)."""
        content = sample_event.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_valid_json(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """signable_content should be valid JSON."""
        content = sample_event.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        assert isinstance(parsed, dict)

    def test_signable_content_has_sorted_keys(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """signable_content should have sorted keys for determinism."""
        content = sample_event.signable_content()
        parsed = json.loads(content.decode("utf-8"))
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_signable_content_includes_all_fields(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """signable_content should include all fields."""
        content = sample_event.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert "cosign_id" in parsed
        assert "petition_id" in parsed
        assert "signer_id" in parsed
        assert "signed_at" in parsed
        assert "content_hash" in parsed
        assert "co_signer_count" in parsed

    def test_signable_content_is_deterministic(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """signable_content should return same bytes for same event."""
        content1 = sample_event.signable_content()
        content2 = sample_event.signable_content()
        assert content1 == content2

    def test_to_dict_returns_dict(self, sample_event: CoSignRecordedEvent) -> None:
        """to_dict should return a dictionary."""
        result = sample_event.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_includes_schema_version(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """to_dict should include schema_version for D2 compliance."""
        result = sample_event.to_dict()
        assert "schema_version" in result
        assert result["schema_version"] == CO_SIGN_EVENT_SCHEMA_VERSION

    def test_to_dict_includes_all_fields(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """to_dict should include all fields."""
        result = sample_event.to_dict()

        assert "cosign_id" in result
        assert "petition_id" in result
        assert "signer_id" in result
        assert "signed_at" in result
        assert "content_hash" in result
        assert "co_signer_count" in result
        assert "schema_version" in result

    def test_to_dict_converts_uuids_to_strings(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """to_dict should convert UUIDs to strings."""
        result = sample_event.to_dict()

        assert isinstance(result["cosign_id"], str)
        assert isinstance(result["petition_id"], str)
        assert isinstance(result["signer_id"], str)

    def test_to_dict_converts_datetime_to_iso(
        self, sample_event: CoSignRecordedEvent
    ) -> None:
        """to_dict should convert datetime to ISO format."""
        result = sample_event.to_dict()
        assert isinstance(result["signed_at"], str)
        # Verify it's valid ISO format by parsing
        datetime.fromisoformat(result["signed_at"])

    def test_from_dict_round_trip(self, sample_event: CoSignRecordedEvent) -> None:
        """from_dict should reconstruct event from to_dict output."""
        data = sample_event.to_dict()
        reconstructed = CoSignRecordedEvent.from_dict(data)

        assert reconstructed.cosign_id == sample_event.cosign_id
        assert reconstructed.petition_id == sample_event.petition_id
        assert reconstructed.signer_id == sample_event.signer_id
        assert reconstructed.signed_at == sample_event.signed_at
        assert reconstructed.content_hash == sample_event.content_hash
        assert reconstructed.co_signer_count == sample_event.co_signer_count

    def test_from_dict_raises_on_missing_field(self) -> None:
        """from_dict should raise KeyError on missing required field."""
        incomplete_data = {
            "cosign_id": str(uuid4()),
            "petition_id": str(uuid4()),
            # Missing signer_id and other fields
        }

        with pytest.raises(KeyError):
            CoSignRecordedEvent.from_dict(incomplete_data)

    def test_from_dict_raises_on_invalid_uuid(self) -> None:
        """from_dict should raise ValueError on invalid UUID."""
        invalid_data = {
            "cosign_id": "not-a-uuid",
            "petition_id": str(uuid4()),
            "signer_id": str(uuid4()),
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": "abc123",
            "co_signer_count": 1,
        }

        with pytest.raises(ValueError):
            CoSignRecordedEvent.from_dict(invalid_data)

    def test_co_signer_count_can_be_any_positive_value(self) -> None:
        """co_signer_count should accept any positive integer."""
        event = CoSignRecordedEvent(
            cosign_id=uuid4(),
            petition_id=uuid4(),
            signer_id=uuid4(),
            signed_at=datetime.now(timezone.utc),
            content_hash="abc123",
            co_signer_count=999999,
        )
        assert event.co_signer_count == 999999

    def test_co_signer_count_can_be_one(self) -> None:
        """co_signer_count can be 1 (first co-signer)."""
        event = CoSignRecordedEvent(
            cosign_id=uuid4(),
            petition_id=uuid4(),
            signer_id=uuid4(),
            signed_at=datetime.now(timezone.utc),
            content_hash="abc123",
            co_signer_count=1,
        )
        assert event.co_signer_count == 1
