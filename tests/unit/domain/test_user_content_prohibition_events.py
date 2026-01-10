"""Unit tests for user content prohibition events (Story 9.4, FR58).

Tests UserContentProhibitionEventPayload and UserContentClearedEventPayload
domain events for content prohibition workflow.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.events.user_content_prohibition import (
    USER_CONTENT_CLEARED_EVENT_TYPE,
    USER_CONTENT_PROHIBITED_EVENT_TYPE,
    USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
    UserContentClearedEventPayload,
    UserContentProhibitionEventPayload,
)


class TestUserContentProhibitionEventPayload:
    """Tests for UserContentProhibitionEventPayload dataclass."""

    def test_create_valid_prohibition_event(self) -> None:
        """Test creating a valid prohibition event."""
        now = datetime.now(timezone.utc)
        payload = UserContentProhibitionEventPayload(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence", "consciousness"),
            action_taken="flag_not_feature",
            flagged_at=now,
        )

        assert payload.content_id == "uc_123"
        assert payload.owner_id == "user_456"
        assert payload.title == "My Article"
        assert payload.matched_terms == ("emergence", "consciousness")
        assert payload.action_taken == "flag_not_feature"
        assert payload.flagged_at == now

    def test_create_via_factory_method(self) -> None:
        """Test creating via factory method sets action_taken automatically."""
        now = datetime.now(timezone.utc)
        payload = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )

        assert payload.action_taken == "flag_not_feature"
        assert payload.content_id == "uc_123"
        assert payload.matched_terms == ("emergence",)

    def test_content_id_required(self) -> None:
        """Test that content_id is required."""
        with pytest.raises(ValueError, match="FR58.*content_id"):
            UserContentProhibitionEventPayload(
                content_id="",
                owner_id="user_456",
                title="My Article",
                matched_terms=("emergence",),
                action_taken="flag_not_feature",
                flagged_at=datetime.now(timezone.utc),
            )

    def test_owner_id_required(self) -> None:
        """Test that owner_id is required."""
        with pytest.raises(ValueError, match="FR58.*owner_id"):
            UserContentProhibitionEventPayload(
                content_id="uc_123",
                owner_id="",
                title="My Article",
                matched_terms=("emergence",),
                action_taken="flag_not_feature",
                flagged_at=datetime.now(timezone.utc),
            )

    def test_title_required(self) -> None:
        """Test that title is required."""
        with pytest.raises(ValueError, match="FR58.*title"):
            UserContentProhibitionEventPayload(
                content_id="uc_123",
                owner_id="user_456",
                title="",
                matched_terms=("emergence",),
                action_taken="flag_not_feature",
                flagged_at=datetime.now(timezone.utc),
            )

    def test_matched_terms_required(self) -> None:
        """Test that matched_terms cannot be empty."""
        with pytest.raises(ValueError, match="FR58.*matched_terms"):
            UserContentProhibitionEventPayload(
                content_id="uc_123",
                owner_id="user_456",
                title="My Article",
                matched_terms=(),
                action_taken="flag_not_feature",
                flagged_at=datetime.now(timezone.utc),
            )

    def test_action_taken_must_be_flag_not_feature(self) -> None:
        """Test that action_taken must be 'flag_not_feature'."""
        with pytest.raises(ValueError, match="FR58.*flag_not_feature"):
            UserContentProhibitionEventPayload(
                content_id="uc_123",
                owner_id="user_456",
                title="My Article",
                matched_terms=("emergence",),
                action_taken="delete",
                flagged_at=datetime.now(timezone.utc),
            )

    def test_event_type_property(self) -> None:
        """Test event_type property returns correct type."""
        now = datetime.now(timezone.utc)
        payload = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )

        assert payload.event_type == USER_CONTENT_PROHIBITED_EVENT_TYPE
        assert payload.event_type == "user_content.prohibited"

    def test_terms_count_property(self) -> None:
        """Test terms_count property."""
        now = datetime.now(timezone.utc)
        payload = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence", "consciousness", "sentient"),
            flagged_at=now,
        )

        assert payload.terms_count == 3

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        payload = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence", "consciousness"),
            flagged_at=now,
        )

        data = payload.to_dict()
        assert data["content_id"] == "uc_123"
        assert data["owner_id"] == "user_456"
        assert data["title"] == "My Article"
        assert data["matched_terms"] == ["emergence", "consciousness"]
        assert data["action_taken"] == "flag_not_feature"
        assert data["flagged_at"] == now.isoformat()
        assert data["terms_count"] == 2


class TestUserContentProhibitionEventPayloadSignableContent:
    """Tests for signable content determinism (CT-12)."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes."""
        now = datetime.now(timezone.utc)
        payload = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)
        assert len(content) > 0

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content produces same result for same input."""
        now = datetime.now(timezone.utc)
        payload1 = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )
        payload2 = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_sorts_matched_terms(self) -> None:
        """Test signable_content produces same result regardless of term order."""
        now = datetime.now(timezone.utc)
        # Different order of matched_terms
        payload1 = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("consciousness", "emergence"),
            flagged_at=now,
        )
        payload2 = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence", "consciousness"),
            flagged_at=now,
        )

        # Should produce same signable content due to sorting
        assert payload1.signable_content() == payload2.signable_content()

    def test_content_hash_is_deterministic(self) -> None:
        """Test content_hash produces same result for same input."""
        now = datetime.now(timezone.utc)
        payload1 = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )
        payload2 = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )

        assert payload1.content_hash() == payload2.content_hash()
        assert len(payload1.content_hash()) == 64  # SHA-256 hex is 64 chars

    def test_different_inputs_produce_different_hashes(self) -> None:
        """Test different inputs produce different hashes."""
        now = datetime.now(timezone.utc)
        payload1 = UserContentProhibitionEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )
        payload2 = UserContentProhibitionEventPayload.create(
            content_id="uc_124",  # Different ID
            owner_id="user_456",
            title="My Article",
            matched_terms=("emergence",),
            flagged_at=now,
        )

        assert payload1.content_hash() != payload2.content_hash()


class TestUserContentClearedEventPayload:
    """Tests for UserContentClearedEventPayload dataclass."""

    def test_create_valid_cleared_event(self) -> None:
        """Test creating a valid cleared event."""
        now = datetime.now(timezone.utc)
        payload = UserContentClearedEventPayload(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
            detection_method="nfkc_scan",
        )

        assert payload.content_id == "uc_123"
        assert payload.owner_id == "user_456"
        assert payload.title == "My Article"
        assert payload.scanned_at == now
        assert payload.detection_method == "nfkc_scan"

    def test_create_via_factory_method(self) -> None:
        """Test creating via factory method with default detection_method."""
        now = datetime.now(timezone.utc)
        payload = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
        )

        assert payload.detection_method == "nfkc_scan"  # Default
        assert payload.content_id == "uc_123"

    def test_create_via_factory_method_custom_detection(self) -> None:
        """Test creating via factory method with custom detection_method."""
        now = datetime.now(timezone.utc)
        payload = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
            detection_method="manual_review: admin override",
        )

        assert payload.detection_method == "manual_review: admin override"

    def test_content_id_required(self) -> None:
        """Test that content_id is required."""
        with pytest.raises(ValueError, match="FR58.*content_id"):
            UserContentClearedEventPayload(
                content_id="",
                owner_id="user_456",
                title="My Article",
                scanned_at=datetime.now(timezone.utc),
                detection_method="nfkc_scan",
            )

    def test_owner_id_required(self) -> None:
        """Test that owner_id is required."""
        with pytest.raises(ValueError, match="FR58.*owner_id"):
            UserContentClearedEventPayload(
                content_id="uc_123",
                owner_id="",
                title="My Article",
                scanned_at=datetime.now(timezone.utc),
                detection_method="nfkc_scan",
            )

    def test_title_required(self) -> None:
        """Test that title is required."""
        with pytest.raises(ValueError, match="FR58.*title"):
            UserContentClearedEventPayload(
                content_id="uc_123",
                owner_id="user_456",
                title="",
                scanned_at=datetime.now(timezone.utc),
                detection_method="nfkc_scan",
            )

    def test_detection_method_required(self) -> None:
        """Test that detection_method is required."""
        with pytest.raises(ValueError, match="FR58.*detection_method"):
            UserContentClearedEventPayload(
                content_id="uc_123",
                owner_id="user_456",
                title="My Article",
                scanned_at=datetime.now(timezone.utc),
                detection_method="",
            )

    def test_event_type_property(self) -> None:
        """Test event_type property returns correct type."""
        now = datetime.now(timezone.utc)
        payload = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
        )

        assert payload.event_type == USER_CONTENT_CLEARED_EVENT_TYPE
        assert payload.event_type == "user_content.cleared"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        payload = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
            detection_method="nfkc_scan",
        )

        data = payload.to_dict()
        assert data["content_id"] == "uc_123"
        assert data["owner_id"] == "user_456"
        assert data["title"] == "My Article"
        assert data["scanned_at"] == now.isoformat()
        assert data["detection_method"] == "nfkc_scan"


class TestUserContentClearedEventPayloadSignableContent:
    """Tests for cleared event signable content determinism (CT-12)."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes."""
        now = datetime.now(timezone.utc)
        payload = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)
        assert len(content) > 0

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content produces same result for same input."""
        now = datetime.now(timezone.utc)
        payload1 = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
        )
        payload2 = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_content_hash_is_deterministic(self) -> None:
        """Test content_hash produces same result for same input."""
        now = datetime.now(timezone.utc)
        payload1 = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
        )
        payload2 = UserContentClearedEventPayload.create(
            content_id="uc_123",
            owner_id="user_456",
            title="My Article",
            scanned_at=now,
        )

        assert payload1.content_hash() == payload2.content_hash()
        assert len(payload1.content_hash()) == 64  # SHA-256 hex is 64 chars


class TestEventConstants:
    """Tests for module constants."""

    def test_prohibited_event_type_value(self) -> None:
        """Test USER_CONTENT_PROHIBITED_EVENT_TYPE value."""
        assert USER_CONTENT_PROHIBITED_EVENT_TYPE == "user_content.prohibited"

    def test_cleared_event_type_value(self) -> None:
        """Test USER_CONTENT_CLEARED_EVENT_TYPE value."""
        assert USER_CONTENT_CLEARED_EVENT_TYPE == "user_content.cleared"

    def test_system_agent_id_value(self) -> None:
        """Test USER_CONTENT_SCANNER_SYSTEM_AGENT_ID value."""
        assert USER_CONTENT_SCANNER_SYSTEM_AGENT_ID == "system:user_content_scanner"
