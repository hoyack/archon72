"""Unit tests for CertifiedResultPayload domain event (Story 2.8, FR99-FR101).

Tests the certified result event payload for deliberation results.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.certified_result import (
    CERTIFIED_RESULT_EVENT_TYPE,
    CertifiedResultPayload,
)


class TestCertifiedResultEventType:
    """Tests for CERTIFIED_RESULT_EVENT_TYPE constant."""

    def test_event_type_follows_naming_convention(self) -> None:
        """Event type should follow lowercase.dot.notation convention."""
        assert CERTIFIED_RESULT_EVENT_TYPE == "deliberation.result.certified"

    def test_event_type_is_string(self) -> None:
        """Event type should be a string."""
        assert isinstance(CERTIFIED_RESULT_EVENT_TYPE, str)


class TestCertifiedResultPayload:
    """Tests for CertifiedResultPayload frozen dataclass."""

    def test_create_valid_payload(self) -> None:
        """Should create a valid CertifiedResultPayload with all fields."""
        result_id = uuid4()
        deliberation_id = uuid4()
        result_hash = "a" * 64
        participant_count = 72
        certification_timestamp = datetime.now(timezone.utc)
        certification_key_id = "CERT:key-001"
        result_type = "vote"

        payload = CertifiedResultPayload(
            result_id=result_id,
            deliberation_id=deliberation_id,
            result_hash=result_hash,
            participant_count=participant_count,
            certification_timestamp=certification_timestamp,
            certification_key_id=certification_key_id,
            result_type=result_type,
        )

        assert payload.result_id == result_id
        assert payload.deliberation_id == deliberation_id
        assert payload.result_hash == result_hash
        assert payload.participant_count == participant_count
        assert payload.certification_timestamp == certification_timestamp
        assert payload.certification_key_id == certification_key_id
        assert payload.result_type == result_type

    def test_payload_is_frozen(self) -> None:
        """Payload should be immutable (frozen dataclass)."""
        payload = CertifiedResultPayload(
            result_id=uuid4(),
            deliberation_id=uuid4(),
            result_hash="b" * 64,
            participant_count=50,
            certification_timestamp=datetime.now(timezone.utc),
            certification_key_id="CERT:key-002",
            result_type="resolution",
        )

        with pytest.raises(AttributeError):
            payload.participant_count = 100  # type: ignore[misc]

    def test_invalid_result_id_not_uuid(self) -> None:
        """Should raise TypeError if result_id is not a UUID."""
        with pytest.raises(TypeError, match="result_id must be UUID"):
            CertifiedResultPayload(
                result_id="not-a-uuid",  # type: ignore[arg-type]
                deliberation_id=uuid4(),
                result_hash="c" * 64,
                participant_count=30,
                certification_timestamp=datetime.now(timezone.utc),
                certification_key_id="CERT:key-003",
                result_type="decision",
            )

    def test_invalid_deliberation_id_not_uuid(self) -> None:
        """Should raise TypeError if deliberation_id is not a UUID."""
        with pytest.raises(TypeError, match="deliberation_id must be UUID"):
            CertifiedResultPayload(
                result_id=uuid4(),
                deliberation_id="not-a-uuid",  # type: ignore[arg-type]
                result_hash="d" * 64,
                participant_count=30,
                certification_timestamp=datetime.now(timezone.utc),
                certification_key_id="CERT:key-004",
                result_type="vote",
            )

    def test_invalid_result_hash_wrong_length(self) -> None:
        """Should raise ValueError if result_hash is not 64 characters."""
        with pytest.raises(
            ValueError, match="result_hash must be 64 character hex string"
        ):
            CertifiedResultPayload(
                result_id=uuid4(),
                deliberation_id=uuid4(),
                result_hash="short",
                participant_count=30,
                certification_timestamp=datetime.now(timezone.utc),
                certification_key_id="CERT:key-005",
                result_type="vote",
            )

    def test_invalid_participant_count_negative(self) -> None:
        """Should raise ValueError if participant_count is negative."""
        with pytest.raises(ValueError, match="participant_count must be >= 0"):
            CertifiedResultPayload(
                result_id=uuid4(),
                deliberation_id=uuid4(),
                result_hash="e" * 64,
                participant_count=-1,
                certification_timestamp=datetime.now(timezone.utc),
                certification_key_id="CERT:key-006",
                result_type="vote",
            )

    def test_zero_participant_count_allowed(self) -> None:
        """Should allow participant_count of 0 (edge case)."""
        payload = CertifiedResultPayload(
            result_id=uuid4(),
            deliberation_id=uuid4(),
            result_hash="f" * 64,
            participant_count=0,
            certification_timestamp=datetime.now(timezone.utc),
            certification_key_id="CERT:key-007",
            result_type="vote",
        )
        assert payload.participant_count == 0

    def test_invalid_certification_key_id_empty(self) -> None:
        """Should raise ValueError if certification_key_id is empty."""
        with pytest.raises(ValueError, match="certification_key_id must be non-empty"):
            CertifiedResultPayload(
                result_id=uuid4(),
                deliberation_id=uuid4(),
                result_hash="0" * 64,
                participant_count=30,
                certification_timestamp=datetime.now(timezone.utc),
                certification_key_id="",
                result_type="vote",
            )

    def test_invalid_result_type_empty(self) -> None:
        """Should raise ValueError if result_type is empty."""
        with pytest.raises(ValueError, match="result_type must be non-empty"):
            CertifiedResultPayload(
                result_id=uuid4(),
                deliberation_id=uuid4(),
                result_hash="0" * 64,
                participant_count=30,
                certification_timestamp=datetime.now(timezone.utc),
                certification_key_id="CERT:key-013",
                result_type="",
            )


class TestCertifiedResultPayloadToDict:
    """Tests for CertifiedResultPayload.to_dict() method."""

    def test_to_dict_returns_all_fields(self) -> None:
        """to_dict should return all fields as strings suitable for JSON."""
        result_id = uuid4()
        deliberation_id = uuid4()
        result_hash = "1" * 64
        participant_count = 72
        certification_timestamp = datetime(2025, 12, 28, 12, 0, 0, tzinfo=UTC)
        certification_key_id = "CERT:key-008"
        result_type = "vote"

        payload = CertifiedResultPayload(
            result_id=result_id,
            deliberation_id=deliberation_id,
            result_hash=result_hash,
            participant_count=participant_count,
            certification_timestamp=certification_timestamp,
            certification_key_id=certification_key_id,
            result_type=result_type,
        )

        result = payload.to_dict()

        assert result["result_id"] == str(result_id)
        assert result["deliberation_id"] == str(deliberation_id)
        assert result["result_hash"] == result_hash
        assert result["participant_count"] == participant_count
        assert result["certification_timestamp"] == certification_timestamp.isoformat()
        assert result["certification_key_id"] == certification_key_id
        assert result["result_type"] == result_type

    def test_to_dict_returns_json_serializable(self) -> None:
        """to_dict result should be JSON serializable."""
        import json

        payload = CertifiedResultPayload(
            result_id=uuid4(),
            deliberation_id=uuid4(),
            result_hash="2" * 64,
            participant_count=50,
            certification_timestamp=datetime.now(timezone.utc),
            certification_key_id="CERT:key-009",
            result_type="resolution",
        )

        result = payload.to_dict()
        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)


class TestCertifiedResultPayloadEquality:
    """Tests for CertifiedResultPayload equality and hashing."""

    def test_equal_payloads_are_equal(self) -> None:
        """Payloads with same values should be equal."""
        result_id = uuid4()
        deliberation_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        payload1 = CertifiedResultPayload(
            result_id=result_id,
            deliberation_id=deliberation_id,
            result_hash="3" * 64,
            participant_count=72,
            certification_timestamp=timestamp,
            certification_key_id="CERT:key-010",
            result_type="vote",
        )

        payload2 = CertifiedResultPayload(
            result_id=result_id,
            deliberation_id=deliberation_id,
            result_hash="3" * 64,
            participant_count=72,
            certification_timestamp=timestamp,
            certification_key_id="CERT:key-010",
            result_type="vote",
        )

        assert payload1 == payload2

    def test_different_payloads_are_not_equal(self) -> None:
        """Payloads with different values should not be equal."""
        timestamp = datetime.now(timezone.utc)

        payload1 = CertifiedResultPayload(
            result_id=uuid4(),
            deliberation_id=uuid4(),
            result_hash="4" * 64,
            participant_count=72,
            certification_timestamp=timestamp,
            certification_key_id="CERT:key-011",
            result_type="vote",
        )

        payload2 = CertifiedResultPayload(
            result_id=uuid4(),
            deliberation_id=uuid4(),
            result_hash="5" * 64,
            participant_count=50,
            certification_timestamp=timestamp,
            certification_key_id="CERT:key-012",
            result_type="resolution",
        )

        assert payload1 != payload2
