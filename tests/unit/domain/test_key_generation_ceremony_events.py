"""Unit tests for KeyGenerationCeremony event payloads (FR69).

Tests event payload creation, serialization, and signable content.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.key_generation_ceremony import (
    KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE,
    KeyGenerationCeremonyCompletedPayload,
    KeyGenerationCeremonyFailedPayload,
    KeyGenerationCeremonyStartedPayload,
    KeyGenerationCeremonyWitnessedPayload,
)


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_started_event_type(self) -> None:
        """Started event type is correct."""
        assert KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE == "ceremony.key_generation.started"

    def test_witnessed_event_type(self) -> None:
        """Witnessed event type is correct."""
        assert KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE == "ceremony.key_generation.witnessed"

    def test_completed_event_type(self) -> None:
        """Completed event type is correct."""
        assert KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE == "ceremony.key_generation.completed"

    def test_failed_event_type(self) -> None:
        """Failed event type is correct."""
        assert KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE == "ceremony.key_generation.failed"


class TestStartedPayload:
    """Tests for KeyGenerationCeremonyStartedPayload."""

    def test_create_new_key_started_payload(self) -> None:
        """Create started payload for new key ceremony."""
        ceremony_id = uuid4()
        payload = KeyGenerationCeremonyStartedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            initiator_id="KEEPER:admin",
            old_key_id=None,
        )

        assert payload.ceremony_id == ceremony_id
        assert payload.keeper_id == "KEEPER:alice"
        assert payload.ceremony_type == "new_keeper_key"
        assert payload.initiator_id == "KEEPER:admin"
        assert payload.old_key_id is None

    def test_create_rotation_started_payload(self) -> None:
        """Create started payload for key rotation ceremony."""
        ceremony_id = uuid4()
        payload = KeyGenerationCeremonyStartedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:bob",
            ceremony_type="key_rotation",
            initiator_id="KEEPER:admin",
            old_key_id="old-key-123",
        )

        assert payload.ceremony_type == "key_rotation"
        assert payload.old_key_id == "old-key-123"

    def test_started_payload_signable_content(self) -> None:
        """Signable content is deterministic JSON."""
        ceremony_id = uuid4()
        started_at = datetime.now(timezone.utc)
        payload = KeyGenerationCeremonyStartedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            initiator_id="KEEPER:admin",
            old_key_id=None,
            started_at=started_at,
        )

        content = payload.signable_content()

        # Verify it's valid JSON
        parsed = json.loads(content)
        assert parsed["event_type"] == KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE
        assert parsed["ceremony_id"] == str(ceremony_id)
        assert parsed["keeper_id"] == "KEEPER:alice"
        assert parsed["ceremony_type"] == "new_keeper_key"
        assert parsed["initiator_id"] == "KEEPER:admin"
        assert parsed["old_key_id"] is None
        assert parsed["started_at"] == started_at.isoformat()

    def test_started_payload_is_frozen(self) -> None:
        """Started payload is immutable."""
        payload = KeyGenerationCeremonyStartedPayload(
            ceremony_id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            initiator_id="KEEPER:admin",
            old_key_id=None,
        )

        with pytest.raises(AttributeError):
            payload.keeper_id = "changed"  # type: ignore


class TestWitnessedPayload:
    """Tests for KeyGenerationCeremonyWitnessedPayload."""

    def test_create_witnessed_payload(self) -> None:
        """Create witnessed payload."""
        ceremony_id = uuid4()
        payload = KeyGenerationCeremonyWitnessedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            witness_id="KEEPER:witness1",
            witness_type="keeper",
            witness_count=1,
        )

        assert payload.ceremony_id == ceremony_id
        assert payload.keeper_id == "KEEPER:alice"
        assert payload.witness_id == "KEEPER:witness1"
        assert payload.witness_type == "keeper"
        assert payload.witness_count == 1

    def test_witnessed_payload_signable_content(self) -> None:
        """Signable content is deterministic JSON."""
        ceremony_id = uuid4()
        witnessed_at = datetime.now(timezone.utc)
        payload = KeyGenerationCeremonyWitnessedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            witness_id="KEEPER:witness1",
            witness_type="keeper",
            witness_count=2,
            witnessed_at=witnessed_at,
        )

        content = payload.signable_content()

        parsed = json.loads(content)
        assert parsed["event_type"] == KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE
        assert parsed["ceremony_id"] == str(ceremony_id)
        assert parsed["witness_id"] == "KEEPER:witness1"
        assert parsed["witness_type"] == "keeper"
        assert parsed["witness_count"] == 2

    def test_witnessed_payload_is_frozen(self) -> None:
        """Witnessed payload is immutable."""
        payload = KeyGenerationCeremonyWitnessedPayload(
            ceremony_id=uuid4(),
            keeper_id="KEEPER:alice",
            witness_id="KEEPER:witness1",
            witness_type="keeper",
            witness_count=1,
        )

        with pytest.raises(AttributeError):
            payload.witness_count = 99  # type: ignore


class TestCompletedPayload:
    """Tests for KeyGenerationCeremonyCompletedPayload."""

    def test_create_completed_payload_new_key(self) -> None:
        """Create completed payload for new key."""
        ceremony_id = uuid4()
        payload = KeyGenerationCeremonyCompletedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            new_key_id="new-key-456",
            old_key_id=None,
            transition_end_at=None,
            witness_ids=["KEEPER:w1", "KEEPER:w2", "KEEPER:w3"],
        )

        assert payload.new_key_id == "new-key-456"
        assert payload.old_key_id is None
        assert payload.transition_end_at is None
        assert payload.witness_ids == ("KEEPER:w1", "KEEPER:w2", "KEEPER:w3")

    def test_create_completed_payload_rotation(self) -> None:
        """Create completed payload for key rotation with transition."""
        ceremony_id = uuid4()
        transition_end = datetime.now(timezone.utc)
        payload = KeyGenerationCeremonyCompletedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:bob",
            ceremony_type="key_rotation",
            new_key_id="new-key-789",
            old_key_id="old-key-123",
            transition_end_at=transition_end,
            witness_ids=("KEEPER:w1", "KEEPER:w2", "KEEPER:w3"),
        )

        assert payload.old_key_id == "old-key-123"
        assert payload.transition_end_at == transition_end

    def test_completed_payload_converts_list_to_tuple(self) -> None:
        """Witness IDs list is converted to tuple."""
        payload = KeyGenerationCeremonyCompletedPayload(
            ceremony_id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            new_key_id="key-1",
            old_key_id=None,
            transition_end_at=None,
            witness_ids=["w1", "w2"],  # List input
        )

        assert isinstance(payload.witness_ids, tuple)

    def test_completed_payload_signable_content(self) -> None:
        """Signable content is deterministic JSON."""
        ceremony_id = uuid4()
        completed_at = datetime.now(timezone.utc)
        transition_end = datetime.now(timezone.utc)

        payload = KeyGenerationCeremonyCompletedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            ceremony_type="key_rotation",
            new_key_id="new-key",
            old_key_id="old-key",
            transition_end_at=transition_end,
            witness_ids=("w1", "w2", "w3"),
            completed_at=completed_at,
        )

        content = payload.signable_content()

        parsed = json.loads(content)
        assert parsed["event_type"] == KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE
        assert parsed["new_key_id"] == "new-key"
        assert parsed["old_key_id"] == "old-key"
        assert parsed["transition_end_at"] == transition_end.isoformat()
        assert parsed["witness_ids"] == ["w1", "w2", "w3"]

    def test_completed_payload_is_frozen(self) -> None:
        """Completed payload is immutable."""
        payload = KeyGenerationCeremonyCompletedPayload(
            ceremony_id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            new_key_id="key-1",
            old_key_id=None,
            transition_end_at=None,
            witness_ids=("w1",),
        )

        with pytest.raises(AttributeError):
            payload.new_key_id = "changed"  # type: ignore


class TestFailedPayload:
    """Tests for KeyGenerationCeremonyFailedPayload."""

    def test_create_failed_payload(self) -> None:
        """Create failed payload."""
        ceremony_id = uuid4()
        payload = KeyGenerationCeremonyFailedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            failure_reason="VAL-2: Ceremony timeout after 3600s",
            witness_count=1,
        )

        assert payload.ceremony_id == ceremony_id
        assert payload.failure_reason == "VAL-2: Ceremony timeout after 3600s"
        assert payload.witness_count == 1

    def test_failed_payload_signable_content(self) -> None:
        """Signable content is deterministic JSON."""
        ceremony_id = uuid4()
        failed_at = datetime.now(timezone.utc)
        payload = KeyGenerationCeremonyFailedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            failure_reason="Test failure",
            witness_count=2,
            failed_at=failed_at,
        )

        content = payload.signable_content()

        parsed = json.loads(content)
        assert parsed["event_type"] == KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE
        assert parsed["failure_reason"] == "Test failure"
        assert parsed["witness_count"] == 2

    def test_failed_payload_is_frozen(self) -> None:
        """Failed payload is immutable."""
        payload = KeyGenerationCeremonyFailedPayload(
            ceremony_id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            failure_reason="Error",
            witness_count=0,
        )

        with pytest.raises(AttributeError):
            payload.failure_reason = "changed"  # type: ignore


class TestSignableContentDeterminism:
    """Tests to ensure signable content is deterministic."""

    def test_started_payload_same_inputs_same_output(self) -> None:
        """Same inputs produce same signable content."""
        ceremony_id = uuid4()
        started_at = datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = KeyGenerationCeremonyStartedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            initiator_id="KEEPER:admin",
            old_key_id=None,
            started_at=started_at,
        )

        payload2 = KeyGenerationCeremonyStartedPayload(
            ceremony_id=ceremony_id,
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            initiator_id="KEEPER:admin",
            old_key_id=None,
            started_at=started_at,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_completed_payload_sorted_keys(self) -> None:
        """Completed payload uses sorted keys for determinism."""
        payload = KeyGenerationCeremonyCompletedPayload(
            ceremony_id=uuid4(),
            keeper_id="KEEPER:alice",
            ceremony_type="new_keeper_key",
            new_key_id="key-1",
            old_key_id=None,
            transition_end_at=None,
            witness_ids=("w1", "w2"),
        )

        content = payload.signable_content().decode("utf-8")

        # Keys should be sorted alphabetically
        # ceremony_id < ceremony_type < completed_at < ...
        assert content.index("ceremony_id") < content.index("ceremony_type")
        assert content.index("ceremony_type") < content.index("completed_at")
