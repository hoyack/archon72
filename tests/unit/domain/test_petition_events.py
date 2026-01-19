"""Unit tests for petition event payloads (Story 7.2 FR39, Story 1.2 FR-1.7).

Tests cover:
- PetitionReceivedEventPayload creation and serialization (Story 1.2)
- PetitionCreatedEventPayload creation and serialization (Story 7.2)
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
    PETITION_RECEIVED_EVENT_TYPE,
    PETITION_SYSTEM_AGENT_ID,
    PETITION_THRESHOLD_COSIGNERS,
    PETITION_THRESHOLD_MET_EVENT_TYPE,
    PetitionCoSignedEventPayload,
    PetitionCreatedEventPayload,
    PetitionReceivedEventPayload,
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

    def test_petition_received_event_type(self) -> None:
        """Test petition received event type constant (FR-1.7)."""
        assert PETITION_RECEIVED_EVENT_TYPE == "petition.received"

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


class TestPetitionReceivedEventPayload:
    """Tests for PetitionReceivedEventPayload (Story 1.2, FR-1.7)."""

    @pytest.fixture
    def sample_payload(self) -> PetitionReceivedEventPayload:
        """Create a sample payload for testing."""
        return PetitionReceivedEventPayload(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="dGVzdGhhc2g=",  # base64 encoded
            submitter_id=uuid4(),
            received_timestamp=datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_creation(self, sample_payload: PetitionReceivedEventPayload) -> None:
        """Test payload creation with all fields."""
        assert sample_payload.petition_type == "GENERAL"
        assert sample_payload.realm == "default"
        assert sample_payload.content_hash == "dGVzdGhhc2g="
        assert sample_payload.received_timestamp.year == 2026

    def test_creation_without_submitter(self) -> None:
        """Test payload creation without submitter_id (anonymous submission)."""
        payload = PetitionReceivedEventPayload(
            petition_id=uuid4(),
            petition_type="CESSATION",
            realm="governance",
            content_hash="aGFzaA==",
            submitter_id=None,
            received_timestamp=datetime.now(timezone.utc),
        )
        assert payload.submitter_id is None

    def test_is_frozen(self, sample_payload: PetitionReceivedEventPayload) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_payload.petition_type = "MODIFIED"  # type: ignore[misc]

    def test_signable_content_determinism(self) -> None:
        """Test signable_content() produces identical bytes for identical payloads."""
        petition_id = uuid4()
        submitter_id = uuid4()
        timestamp = datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = PetitionReceivedEventPayload(
            petition_id=petition_id,
            petition_type="GENERAL",
            realm="default",
            content_hash="hash123",
            submitter_id=submitter_id,
            received_timestamp=timestamp,
        )
        payload2 = PetitionReceivedEventPayload(
            petition_id=petition_id,
            petition_type="GENERAL",
            realm="default",
            content_hash="hash123",
            submitter_id=submitter_id,
            received_timestamp=timestamp,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_is_bytes(
        self, sample_payload: PetitionReceivedEventPayload
    ) -> None:
        """Test signable_content() returns bytes."""
        content = sample_payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_includes_all_fields(
        self, sample_payload: PetitionReceivedEventPayload
    ) -> None:
        """Test signable_content() includes all required fields."""
        content = sample_payload.signable_content().decode("utf-8")
        assert "petition_id" in content
        assert "petition_type" in content
        assert "realm" in content
        assert "content_hash" in content
        assert "submitter_id" in content
        assert "received_timestamp" in content

    def test_signable_content_null_submitter(self) -> None:
        """Test signable_content() handles null submitter_id correctly."""
        payload = PetitionReceivedEventPayload(
            petition_id=uuid4(),
            petition_type="GENERAL",
            realm="default",
            content_hash="hash",
            submitter_id=None,
            received_timestamp=datetime.now(timezone.utc),
        )
        content = payload.signable_content().decode("utf-8")
        # Should contain "submitter_id": null in JSON
        assert '"submitter_id": null' in content

    def test_to_dict(self, sample_payload: PetitionReceivedEventPayload) -> None:
        """Test to_dict() serialization."""
        result = sample_payload.to_dict()
        assert result["petition_id"] == str(sample_payload.petition_id)
        assert result["petition_type"] == "GENERAL"
        assert result["realm"] == "default"
        assert result["content_hash"] == "dGVzdGhhc2g="
        assert result["submitter_id"] == str(sample_payload.submitter_id)
        assert "2026-01-19" in result["received_timestamp"]

    def test_to_dict_null_submitter(self) -> None:
        """Test to_dict() serialization with null submitter_id."""
        payload = PetitionReceivedEventPayload(
            petition_id=uuid4(),
            petition_type="GRIEVANCE",
            realm="default",
            content_hash="hash",
            submitter_id=None,
            received_timestamp=datetime.now(timezone.utc),
        )
        result = payload.to_dict()
        assert result["submitter_id"] is None

    def test_all_petition_types(self) -> None:
        """Test payload accepts all valid petition types (FR-10.1)."""
        for petition_type in ["GENERAL", "CESSATION", "GRIEVANCE", "COLLABORATION"]:
            payload = PetitionReceivedEventPayload(
                petition_id=uuid4(),
                petition_type=petition_type,
                realm="default",
                content_hash="hash",
                submitter_id=None,
                received_timestamp=datetime.now(timezone.utc),
            )
            assert payload.petition_type == petition_type


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


class TestFateEventTypeConstants:
    """Tests for fate event type constants (Story 1.7, FR-2.5)."""

    def test_petition_acknowledged_event_type(self) -> None:
        """Test petition acknowledged event type constant (FR-2.5)."""
        from src.domain.events.petition import PETITION_ACKNOWLEDGED_EVENT_TYPE

        assert PETITION_ACKNOWLEDGED_EVENT_TYPE == "petition.acknowledged"

    def test_petition_referred_event_type(self) -> None:
        """Test petition referred event type constant (FR-2.5)."""
        from src.domain.events.petition import PETITION_REFERRED_EVENT_TYPE

        assert PETITION_REFERRED_EVENT_TYPE == "petition.referred"

    def test_petition_escalated_event_type(self) -> None:
        """Test petition escalated event type constant (FR-2.5)."""
        from src.domain.events.petition import PETITION_ESCALATED_EVENT_TYPE

        assert PETITION_ESCALATED_EVENT_TYPE == "petition.escalated"


class TestPetitionFateEventPayload:
    """Tests for PetitionFateEventPayload (Story 1.7, FR-2.5).

    Constitutional Constraints:
    - FR-2.5: Emit fate event in same transaction as state update
    - NFR-3.3: 100% fate events persisted
    - HC-1: Fate transition requires witness event
    - CT-12: Witnessing creates accountability
    """

    @pytest.fixture
    def sample_acknowledged_payload(self) -> "PetitionFateEventPayload":
        """Create a sample ACKNOWLEDGED fate payload."""
        from src.domain.events.petition import PetitionFateEventPayload

        return PetitionFateEventPayload(
            petition_id=uuid4(),
            previous_state="DELIBERATING",
            new_state="ACKNOWLEDGED",
            actor_id="fate-archon-1",
            timestamp=datetime(2026, 1, 19, 14, 0, 0, tzinfo=timezone.utc),
            reason="Petition addressed through existing mechanisms",
        )

    @pytest.fixture
    def sample_referred_payload(self) -> "PetitionFateEventPayload":
        """Create a sample REFERRED fate payload."""
        from src.domain.events.petition import PetitionFateEventPayload

        return PetitionFateEventPayload(
            petition_id=uuid4(),
            previous_state="DELIBERATING",
            new_state="REFERRED",
            actor_id="fate-archon-2",
            timestamp=datetime(2026, 1, 19, 14, 30, 0, tzinfo=timezone.utc),
            reason="Referred to Knight for realm-specific review",
        )

    @pytest.fixture
    def sample_escalated_payload(self) -> "PetitionFateEventPayload":
        """Create a sample ESCALATED fate payload."""
        from src.domain.events.petition import PetitionFateEventPayload

        return PetitionFateEventPayload(
            petition_id=uuid4(),
            previous_state="DELIBERATING",
            new_state="ESCALATED",
            actor_id="fate-archon-3",
            timestamp=datetime(2026, 1, 19, 15, 0, 0, tzinfo=timezone.utc),
            reason="Constitutional concern requires King review",
        )

    def test_creation_acknowledged(
        self, sample_acknowledged_payload: "PetitionFateEventPayload"
    ) -> None:
        """Test ACKNOWLEDGED fate payload creation."""
        assert sample_acknowledged_payload.previous_state == "DELIBERATING"
        assert sample_acknowledged_payload.new_state == "ACKNOWLEDGED"
        assert sample_acknowledged_payload.actor_id == "fate-archon-1"
        assert sample_acknowledged_payload.reason is not None

    def test_creation_referred(
        self, sample_referred_payload: "PetitionFateEventPayload"
    ) -> None:
        """Test REFERRED fate payload creation."""
        assert sample_referred_payload.previous_state == "DELIBERATING"
        assert sample_referred_payload.new_state == "REFERRED"
        assert sample_referred_payload.actor_id == "fate-archon-2"

    def test_creation_escalated(
        self, sample_escalated_payload: "PetitionFateEventPayload"
    ) -> None:
        """Test ESCALATED fate payload creation."""
        assert sample_escalated_payload.previous_state == "DELIBERATING"
        assert sample_escalated_payload.new_state == "ESCALATED"
        assert sample_escalated_payload.actor_id == "fate-archon-3"

    def test_creation_with_null_reason(self) -> None:
        """Test fate payload creation with no reason (optional field)."""
        from src.domain.events.petition import PetitionFateEventPayload

        payload = PetitionFateEventPayload(
            petition_id=uuid4(),
            previous_state="RECEIVED",
            new_state="ACKNOWLEDGED",
            actor_id="system",
            timestamp=datetime.now(timezone.utc),
            reason=None,
        )
        assert payload.reason is None

    def test_is_frozen(
        self, sample_acknowledged_payload: "PetitionFateEventPayload"
    ) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_acknowledged_payload.new_state = "MODIFIED"  # type: ignore[misc]

    def test_signable_content_determinism(self) -> None:
        """Test signable_content() produces identical bytes for identical payloads."""
        from src.domain.events.petition import PetitionFateEventPayload

        petition_id = uuid4()
        timestamp = datetime(2026, 1, 19, 14, 0, 0, tzinfo=timezone.utc)

        payload1 = PetitionFateEventPayload(
            petition_id=petition_id,
            previous_state="DELIBERATING",
            new_state="ACKNOWLEDGED",
            actor_id="test-actor",
            timestamp=timestamp,
            reason="Test reason",
        )
        payload2 = PetitionFateEventPayload(
            petition_id=petition_id,
            previous_state="DELIBERATING",
            new_state="ACKNOWLEDGED",
            actor_id="test-actor",
            timestamp=timestamp,
            reason="Test reason",
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_is_bytes(
        self, sample_acknowledged_payload: "PetitionFateEventPayload"
    ) -> None:
        """Test signable_content() returns bytes."""
        content = sample_acknowledged_payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_includes_all_fields(
        self, sample_acknowledged_payload: "PetitionFateEventPayload"
    ) -> None:
        """Test signable_content() includes all required fields (CT-12)."""
        content = sample_acknowledged_payload.signable_content().decode("utf-8")
        assert "petition_id" in content
        assert "previous_state" in content
        assert "new_state" in content
        assert "actor_id" in content
        assert "timestamp" in content
        assert "reason" in content

    def test_signable_content_null_reason(self) -> None:
        """Test signable_content() handles null reason correctly."""
        from src.domain.events.petition import PetitionFateEventPayload

        payload = PetitionFateEventPayload(
            petition_id=uuid4(),
            previous_state="RECEIVED",
            new_state="ACKNOWLEDGED",
            actor_id="system",
            timestamp=datetime.now(timezone.utc),
            reason=None,
        )
        content = payload.signable_content().decode("utf-8")
        # Should contain "reason": null in JSON
        assert '"reason": null' in content

    def test_to_dict(
        self, sample_acknowledged_payload: "PetitionFateEventPayload"
    ) -> None:
        """Test to_dict() serialization."""
        result = sample_acknowledged_payload.to_dict()
        assert result["petition_id"] == str(sample_acknowledged_payload.petition_id)
        assert result["previous_state"] == "DELIBERATING"
        assert result["new_state"] == "ACKNOWLEDGED"
        assert result["actor_id"] == "fate-archon-1"
        assert result["reason"] == "Petition addressed through existing mechanisms"
        assert "2026-01-19" in result["timestamp"]

    def test_to_dict_includes_schema_version(
        self, sample_acknowledged_payload: "PetitionFateEventPayload"
    ) -> None:
        """Test to_dict() includes schema_version (D2 - CRITICAL)."""
        result = sample_acknowledged_payload.to_dict()
        assert "schema_version" in result
        assert result["schema_version"] == "1.0.0"

    def test_to_dict_null_reason(self) -> None:
        """Test to_dict() serialization with null reason."""
        from src.domain.events.petition import PetitionFateEventPayload

        payload = PetitionFateEventPayload(
            petition_id=uuid4(),
            previous_state="DELIBERATING",
            new_state="REFERRED",
            actor_id="system",
            timestamp=datetime.now(timezone.utc),
            reason=None,
        )
        result = payload.to_dict()
        assert result["reason"] is None

    def test_all_fate_states_supported(self) -> None:
        """Test payload accepts all three terminal fate states (FR-2.6)."""
        from src.domain.events.petition import PetitionFateEventPayload

        for fate_state in ["ACKNOWLEDGED", "REFERRED", "ESCALATED"]:
            payload = PetitionFateEventPayload(
                petition_id=uuid4(),
                previous_state="DELIBERATING",
                new_state=fate_state,
                actor_id="test-actor",
                timestamp=datetime.now(timezone.utc),
                reason=None,
            )
            assert payload.new_state == fate_state

    def test_previous_state_received_allowed(self) -> None:
        """Test previous_state can be RECEIVED (for withdrawal before deliberation)."""
        from src.domain.events.petition import PetitionFateEventPayload

        payload = PetitionFateEventPayload(
            petition_id=uuid4(),
            previous_state="RECEIVED",
            new_state="ACKNOWLEDGED",
            actor_id="submitter-withdrawal",
            timestamp=datetime.now(timezone.utc),
            reason="Withdrawal by submitter",
        )
        assert payload.previous_state == "RECEIVED"

    def test_equality(self) -> None:
        """Test payload equality based on all fields."""
        from src.domain.events.petition import PetitionFateEventPayload

        petition_id = uuid4()
        timestamp = datetime(2026, 1, 19, 14, 0, 0, tzinfo=timezone.utc)

        payload1 = PetitionFateEventPayload(
            petition_id=petition_id,
            previous_state="DELIBERATING",
            new_state="ACKNOWLEDGED",
            actor_id="test",
            timestamp=timestamp,
            reason="reason",
        )
        payload2 = PetitionFateEventPayload(
            petition_id=petition_id,
            previous_state="DELIBERATING",
            new_state="ACKNOWLEDGED",
            actor_id="test",
            timestamp=timestamp,
            reason="reason",
        )

        assert payload1 == payload2
