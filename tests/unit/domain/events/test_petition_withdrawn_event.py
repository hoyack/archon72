"""Unit tests for PetitionWithdrawnEventPayload (Story 7.3, FR-7.5).

Tests verify:
- Frozen dataclass immutability
- signable_content() canonical JSON serialization
- to_dict() with schema_version (D2 compliance)
- Event type constant

Constitutional Constraints:
- CT-12: Witnessing creates accountability -> signable_content() must be deterministic
- D2: Schema versioning -> to_dict() must include schema_version
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.petition import (
    PETITION_WITHDRAWN_EVENT_TYPE,
    WITHDRAWAL_EVENT_SCHEMA_VERSION,
    PetitionWithdrawnEventPayload,
)


class TestPetitionWithdrawnEventPayload:
    """Tests for PetitionWithdrawnEventPayload dataclass."""

    def test_event_type_constant(self) -> None:
        """PETITION_WITHDRAWN_EVENT_TYPE has correct value."""
        assert PETITION_WITHDRAWN_EVENT_TYPE == "petition.submission.withdrawn"

    def test_schema_version_constant(self) -> None:
        """WITHDRAWAL_EVENT_SCHEMA_VERSION has correct value (D2 compliance)."""
        assert WITHDRAWAL_EVENT_SCHEMA_VERSION == "1.0.0"

    def test_create_payload_with_reason(self) -> None:
        """Payload can be created with all fields including reason."""
        petition_id = uuid4()
        withdrawn_by = uuid4()
        reason = "Changed my mind about this petition"
        withdrawn_at = datetime.now(timezone.utc)

        payload = PetitionWithdrawnEventPayload(
            petition_id=petition_id,
            withdrawn_by=withdrawn_by,
            reason=reason,
            withdrawn_at=withdrawn_at,
        )

        assert payload.petition_id == petition_id
        assert payload.withdrawn_by == withdrawn_by
        assert payload.reason == reason
        assert payload.withdrawn_at == withdrawn_at

    def test_create_payload_without_reason(self) -> None:
        """Payload can be created with None reason."""
        petition_id = uuid4()
        withdrawn_by = uuid4()
        withdrawn_at = datetime.now(timezone.utc)

        payload = PetitionWithdrawnEventPayload(
            petition_id=petition_id,
            withdrawn_by=withdrawn_by,
            reason=None,
            withdrawn_at=withdrawn_at,
        )

        assert payload.petition_id == petition_id
        assert payload.reason is None

    def test_payload_is_frozen(self) -> None:
        """Payload is immutable (frozen dataclass)."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test",
            withdrawn_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.reason = "modified"  # type: ignore[misc]

    def test_payload_equality(self) -> None:
        """Payloads with same values are equal."""
        petition_id = uuid4()
        withdrawn_by = uuid4()
        reason = "Same reason"
        withdrawn_at = datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = PetitionWithdrawnEventPayload(
            petition_id=petition_id,
            withdrawn_by=withdrawn_by,
            reason=reason,
            withdrawn_at=withdrawn_at,
        )
        payload2 = PetitionWithdrawnEventPayload(
            petition_id=petition_id,
            withdrawn_by=withdrawn_by,
            reason=reason,
            withdrawn_at=withdrawn_at,
        )

        assert payload1 == payload2

    def test_signable_content_returns_bytes(self) -> None:
        """signable_content() returns UTF-8 encoded bytes (CT-12)."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test reason",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = payload.signable_content()

        assert isinstance(result, bytes)

    def test_signable_content_is_valid_json(self) -> None:
        """signable_content() returns valid JSON."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test reason",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = payload.signable_content()
        parsed = json.loads(result.decode("utf-8"))

        assert isinstance(parsed, dict)
        assert "petition_id" in parsed
        assert "withdrawn_by" in parsed
        assert "reason" in parsed
        assert "withdrawn_at" in parsed

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content() returns identical bytes for same payload (CT-12)."""
        petition_id = uuid4()
        withdrawn_by = uuid4()
        reason = "deterministic test"
        withdrawn_at = datetime(2026, 1, 22, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = PetitionWithdrawnEventPayload(
            petition_id=petition_id,
            withdrawn_by=withdrawn_by,
            reason=reason,
            withdrawn_at=withdrawn_at,
        )
        payload2 = PetitionWithdrawnEventPayload(
            petition_id=petition_id,
            withdrawn_by=withdrawn_by,
            reason=reason,
            withdrawn_at=withdrawn_at,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_has_sorted_keys(self) -> None:
        """signable_content() uses sorted keys for canonical JSON."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = json.loads(payload.signable_content().decode("utf-8"))
        keys = list(result.keys())

        assert keys == sorted(keys)

    def test_signable_content_handles_none_reason(self) -> None:
        """signable_content() correctly serializes None reason."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason=None,
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = json.loads(payload.signable_content().decode("utf-8"))

        assert result["reason"] is None

    def test_to_dict_returns_dict(self) -> None:
        """to_dict() returns a dictionary."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = payload.to_dict()

        assert isinstance(result, dict)

    def test_to_dict_includes_schema_version(self) -> None:
        """to_dict() includes schema_version (D2 compliance - CRITICAL)."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = payload.to_dict()

        assert "schema_version" in result
        assert result["schema_version"] == WITHDRAWAL_EVENT_SCHEMA_VERSION

    def test_to_dict_converts_uuids_to_strings(self) -> None:
        """to_dict() converts UUIDs to strings for JSON serialization."""
        petition_id = uuid4()
        withdrawn_by = uuid4()

        payload = PetitionWithdrawnEventPayload(
            petition_id=petition_id,
            withdrawn_by=withdrawn_by,
            reason="test",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = payload.to_dict()

        assert result["petition_id"] == str(petition_id)
        assert result["withdrawn_by"] == str(withdrawn_by)

    def test_to_dict_converts_datetime_to_iso(self) -> None:
        """to_dict() converts datetime to ISO 8601 string."""
        withdrawn_at = datetime(2026, 1, 22, 12, 30, 45, tzinfo=timezone.utc)

        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test",
            withdrawn_at=withdrawn_at,
        )

        result = payload.to_dict()

        assert result["withdrawn_at"] == "2026-01-22T12:30:45+00:00"

    def test_to_dict_has_all_required_fields(self) -> None:
        """to_dict() includes all required fields."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test reason",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = payload.to_dict()

        required_fields = {
            "petition_id",
            "withdrawn_by",
            "reason",
            "withdrawn_at",
            "schema_version",
        }
        assert set(result.keys()) == required_fields

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict() output can be JSON serialized."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = payload.to_dict()
        json_str = json.dumps(result)

        assert isinstance(json_str, str)

    def test_signable_content_excludes_schema_version(self) -> None:
        """signable_content() does NOT include schema_version (signing should be stable)."""
        payload = PetitionWithdrawnEventPayload(
            petition_id=uuid4(),
            withdrawn_by=uuid4(),
            reason="test",
            withdrawn_at=datetime.now(timezone.utc),
        )

        result = json.loads(payload.signable_content().decode("utf-8"))

        assert "schema_version" not in result
