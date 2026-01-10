"""Unit tests for petition event payloads (Story 7.2, FR39).

Tests cover:
- PetitionCreatedEventPayload creation and serialization
- PetitionCoSignedEventPayload creation and serialization
- PetitionThresholdMetEventPayload creation and serialization
- signable_content() determinism for all payloads
- PetitionStatus enum values
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.events.petition import (
    PETITION_COSIGNED_EVENT_TYPE,
    PETITION_CREATED_EVENT_TYPE,
    PETITION_SYSTEM_AGENT_ID,
    PETITION_THRESHOLD_COSIGNERS,
    PETITION_THRESHOLD_MET_EVENT_TYPE,
    PetitionCoSignedEventPayload,
    PetitionCreatedEventPayload,
    PetitionStatus,
    PetitionThresholdMetEventPayload,
)


class TestPetitionStatus:
    """Tests for PetitionStatus enum."""

    def test_status_values(self) -> None:
        """Test all petition status values exist."""
        assert PetitionStatus.OPEN.value == "open"
        assert PetitionStatus.THRESHOLD_MET.value == "threshold_met"
        assert PetitionStatus.CLOSED.value == "closed"

    def test_status_is_string_enum(self) -> None:
        """Test PetitionStatus is a string enum."""
        assert isinstance(PetitionStatus.OPEN, str)
        assert PetitionStatus.OPEN == "open"


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_petition_created_event_type(self) -> None:
        """Test petition created event type constant."""
        assert PETITION_CREATED_EVENT_TYPE == "petition.created"

    def test_petition_cosigned_event_type(self) -> None:
        """Test petition co-signed event type constant."""
        assert PETITION_COSIGNED_EVENT_TYPE == "petition.cosigned"

    def test_petition_threshold_met_event_type(self) -> None:
        """Test petition threshold met event type constant."""
        assert PETITION_THRESHOLD_MET_EVENT_TYPE == "petition.threshold_met"

    def test_petition_system_agent_id(self) -> None:
        """Test petition system agent ID constant."""
        assert PETITION_SYSTEM_AGENT_ID == "petition-system"

    def test_petition_threshold_cosigners(self) -> None:
        """Test petition threshold cosigners constant (FR39: 100)."""
        assert PETITION_THRESHOLD_COSIGNERS == 100


class TestPetitionCreatedEventPayload:
    """Tests for PetitionCreatedEventPayload."""

    @pytest.fixture
    def sample_payload(self) -> PetitionCreatedEventPayload:
        """Create a sample payload for testing."""
        return PetitionCreatedEventPayload(
            petition_id=uuid4(),
            submitter_public_key="abc123def456",
            submitter_signature="sig789",
            petition_content="Concern about integrity failures",
            created_timestamp=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_creation(self, sample_payload: PetitionCreatedEventPayload) -> None:
        """Test payload creation with all fields."""
        assert sample_payload.submitter_public_key == "abc123def456"
        assert sample_payload.submitter_signature == "sig789"
        assert sample_payload.petition_content == "Concern about integrity failures"
        assert sample_payload.created_timestamp.year == 2026

    def test_is_frozen(self, sample_payload: PetitionCreatedEventPayload) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_payload.petition_content = "modified"  # type: ignore[misc]

    def test_signable_content_determinism(self) -> None:
        """Test signable_content() produces identical bytes for identical payloads."""
        petition_id = uuid4()
        timestamp = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = PetitionCreatedEventPayload(
            petition_id=petition_id,
            submitter_public_key="abc123",
            submitter_signature="sig123",
            petition_content="Content",
            created_timestamp=timestamp,
        )
        payload2 = PetitionCreatedEventPayload(
            petition_id=petition_id,
            submitter_public_key="abc123",
            submitter_signature="sig123",
            petition_content="Content",
            created_timestamp=timestamp,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_is_bytes(
        self, sample_payload: PetitionCreatedEventPayload
    ) -> None:
        """Test signable_content() returns bytes."""
        content = sample_payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_includes_all_fields(
        self, sample_payload: PetitionCreatedEventPayload
    ) -> None:
        """Test signable_content() includes all required fields."""
        content = sample_payload.signable_content().decode("utf-8")
        assert "petition_id" in content
        assert "submitter_public_key" in content
        assert "submitter_signature" in content
        assert "petition_content" in content
        assert "created_timestamp" in content

    def test_to_dict(self, sample_payload: PetitionCreatedEventPayload) -> None:
        """Test to_dict() serialization."""
        result = sample_payload.to_dict()
        assert result["petition_id"] == str(sample_payload.petition_id)
        assert result["submitter_public_key"] == "abc123def456"
        assert result["submitter_signature"] == "sig789"
        assert result["petition_content"] == "Concern about integrity failures"
        assert "2026-01-08" in result["created_timestamp"]


class TestPetitionCoSignedEventPayload:
    """Tests for PetitionCoSignedEventPayload."""

    @pytest.fixture
    def sample_payload(self) -> PetitionCoSignedEventPayload:
        """Create a sample payload for testing."""
        return PetitionCoSignedEventPayload(
            petition_id=uuid4(),
            cosigner_public_key="cosigner_key_123",
            cosigner_signature="cosigner_sig_456",
            cosigned_timestamp=datetime(2026, 1, 8, 13, 0, 0, tzinfo=timezone.utc),
            cosigner_sequence=42,
        )

    def test_creation(self, sample_payload: PetitionCoSignedEventPayload) -> None:
        """Test payload creation with all fields."""
        assert sample_payload.cosigner_public_key == "cosigner_key_123"
        assert sample_payload.cosigner_signature == "cosigner_sig_456"
        assert sample_payload.cosigner_sequence == 42

    def test_is_frozen(self, sample_payload: PetitionCoSignedEventPayload) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_payload.cosigner_sequence = 99  # type: ignore[misc]

    def test_signable_content_determinism(self) -> None:
        """Test signable_content() produces identical bytes for identical payloads."""
        petition_id = uuid4()
        timestamp = datetime(2026, 1, 8, 13, 0, 0, tzinfo=timezone.utc)

        payload1 = PetitionCoSignedEventPayload(
            petition_id=petition_id,
            cosigner_public_key="key123",
            cosigner_signature="sig123",
            cosigned_timestamp=timestamp,
            cosigner_sequence=1,
        )
        payload2 = PetitionCoSignedEventPayload(
            petition_id=petition_id,
            cosigner_public_key="key123",
            cosigner_signature="sig123",
            cosigned_timestamp=timestamp,
            cosigner_sequence=1,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_includes_all_fields(
        self, sample_payload: PetitionCoSignedEventPayload
    ) -> None:
        """Test signable_content() includes all required fields."""
        content = sample_payload.signable_content().decode("utf-8")
        assert "petition_id" in content
        assert "cosigner_public_key" in content
        assert "cosigner_signature" in content
        assert "cosigned_timestamp" in content
        assert "cosigner_sequence" in content

    def test_to_dict(self, sample_payload: PetitionCoSignedEventPayload) -> None:
        """Test to_dict() serialization."""
        result = sample_payload.to_dict()
        assert result["petition_id"] == str(sample_payload.petition_id)
        assert result["cosigner_public_key"] == "cosigner_key_123"
        assert result["cosigner_signature"] == "cosigner_sig_456"
        assert result["cosigner_sequence"] == 42
        assert "2026-01-08" in result["cosigned_timestamp"]


class TestPetitionThresholdMetEventPayload:
    """Tests for PetitionThresholdMetEventPayload."""

    @pytest.fixture
    def sample_payload(self) -> PetitionThresholdMetEventPayload:
        """Create a sample payload for testing."""
        return PetitionThresholdMetEventPayload(
            petition_id=uuid4(),
            threshold=100,
            final_cosigner_count=102,
            trigger_timestamp=datetime(2026, 1, 8, 14, 0, 0, tzinfo=timezone.utc),
            cosigner_public_keys=("key1", "key2", "key3"),
            agenda_placement_reason="FR39: External observer petition reached 100 co-signers",
        )

    def test_creation(self, sample_payload: PetitionThresholdMetEventPayload) -> None:
        """Test payload creation with all fields."""
        assert sample_payload.threshold == 100
        assert sample_payload.final_cosigner_count == 102
        assert len(sample_payload.cosigner_public_keys) == 3
        assert "FR39" in sample_payload.agenda_placement_reason

    def test_is_frozen(self, sample_payload: PetitionThresholdMetEventPayload) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_payload.threshold = 50  # type: ignore[misc]

    def test_cosigner_keys_is_tuple(
        self, sample_payload: PetitionThresholdMetEventPayload
    ) -> None:
        """Test cosigner_public_keys is an immutable tuple."""
        assert isinstance(sample_payload.cosigner_public_keys, tuple)

    def test_signable_content_determinism(self) -> None:
        """Test signable_content() produces identical bytes for identical payloads."""
        petition_id = uuid4()
        timestamp = datetime(2026, 1, 8, 14, 0, 0, tzinfo=timezone.utc)
        keys = ("k1", "k2", "k3")

        payload1 = PetitionThresholdMetEventPayload(
            petition_id=petition_id,
            threshold=100,
            final_cosigner_count=100,
            trigger_timestamp=timestamp,
            cosigner_public_keys=keys,
            agenda_placement_reason="Test reason",
        )
        payload2 = PetitionThresholdMetEventPayload(
            petition_id=petition_id,
            threshold=100,
            final_cosigner_count=100,
            trigger_timestamp=timestamp,
            cosigner_public_keys=keys,
            agenda_placement_reason="Test reason",
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_includes_all_fields(
        self, sample_payload: PetitionThresholdMetEventPayload
    ) -> None:
        """Test signable_content() includes all required fields."""
        content = sample_payload.signable_content().decode("utf-8")
        assert "petition_id" in content
        assert "threshold" in content
        assert "final_cosigner_count" in content
        assert "trigger_timestamp" in content
        assert "cosigner_public_keys" in content
        assert "agenda_placement_reason" in content

    def test_to_dict(self, sample_payload: PetitionThresholdMetEventPayload) -> None:
        """Test to_dict() serialization."""
        result = sample_payload.to_dict()
        assert result["petition_id"] == str(sample_payload.petition_id)
        assert result["threshold"] == 100
        assert result["final_cosigner_count"] == 102
        assert result["cosigner_public_keys"] == ["key1", "key2", "key3"]
        assert "FR39" in result["agenda_placement_reason"]
        assert "2026-01-08" in result["trigger_timestamp"]

    def test_threshold_boundary_at_100(self) -> None:
        """Test threshold is exactly 100 per FR39."""
        payload = PetitionThresholdMetEventPayload(
            petition_id=uuid4(),
            threshold=100,
            final_cosigner_count=100,
            trigger_timestamp=datetime.now(timezone.utc),
            cosigner_public_keys=tuple(f"key{i}" for i in range(100)),
            agenda_placement_reason="FR39: External observer petition reached 100 co-signers",
        )
        assert payload.threshold == 100
        assert payload.final_cosigner_count == 100
        assert len(payload.cosigner_public_keys) == 100
