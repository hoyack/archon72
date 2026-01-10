"""Unit tests for publication domain models (Story 9.2, FR56).

Tests:
- Publication dataclass validation
- PublicationStatus transitions
- PublicationScanRequest validation
- PublicationScannedEventPayload creation and serialization
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.events.publication_scan import (
    PUBLICATION_BLOCKED_EVENT_TYPE,
    PUBLICATION_SCANNED_EVENT_TYPE,
    PublicationScannedEventPayload,
)
from src.domain.models.publication import (
    PUBLICATION_ID_PREFIX,
    Publication,
    PublicationScanRequest,
    PublicationStatus,
)


class TestPublicationStatus:
    """Tests for PublicationStatus enum (FR56)."""

    def test_status_values_exist(self) -> None:
        """Test all required status values exist."""
        assert PublicationStatus.DRAFT.value == "draft"
        assert PublicationStatus.PENDING_REVIEW.value == "pending_review"
        assert PublicationStatus.APPROVED.value == "approved"
        assert PublicationStatus.BLOCKED.value == "blocked"
        assert PublicationStatus.PUBLISHED.value == "published"

    def test_status_count(self) -> None:
        """Test expected number of statuses."""
        assert len(PublicationStatus) == 5

    def test_status_is_string_enum(self) -> None:
        """Test status values are strings."""
        for status in PublicationStatus:
            assert isinstance(status.value, str)

    def test_status_can_be_compared(self) -> None:
        """Test status values can be compared."""
        assert PublicationStatus.DRAFT != PublicationStatus.BLOCKED
        assert PublicationStatus.BLOCKED == PublicationStatus.BLOCKED


class TestPublication:
    """Tests for Publication dataclass (FR56)."""

    def test_create_valid_publication(self) -> None:
        """Test creating a valid publication."""
        now = datetime.now(timezone.utc)
        pub = Publication(
            id="pub-123",
            content="Test content",
            title="Test Title",
            author_agent_id="agent-456",
            status=PublicationStatus.DRAFT,
            created_at=now,
        )

        assert pub.id == "pub-123"
        assert pub.content == "Test content"
        assert pub.title == "Test Title"
        assert pub.author_agent_id == "agent-456"
        assert pub.status == PublicationStatus.DRAFT
        assert pub.created_at == now
        assert pub.scanned_at is None

    def test_publication_with_scan_timestamp(self) -> None:
        """Test publication with scan timestamp."""
        now = datetime.now(timezone.utc)
        pub = Publication(
            id="pub-123",
            content="Test content",
            title="Test Title",
            author_agent_id="agent-456",
            status=PublicationStatus.APPROVED,
            created_at=now,
            scanned_at=now,
        )

        assert pub.scanned_at == now

    def test_publication_is_frozen(self) -> None:
        """Test publication is immutable."""
        now = datetime.now(timezone.utc)
        pub = Publication(
            id="pub-123",
            content="Test content",
            title="Test Title",
            author_agent_id="agent-456",
            status=PublicationStatus.DRAFT,
            created_at=now,
        )

        with pytest.raises(AttributeError):
            pub.status = PublicationStatus.APPROVED  # type: ignore

    def test_publication_empty_id_raises(self) -> None:
        """Test empty ID raises ValueError with FR56 reference."""
        with pytest.raises(ValueError, match="FR56"):
            Publication(
                id="",
                content="Test content",
                title="Test Title",
                author_agent_id="agent-456",
                status=PublicationStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
            )

    def test_publication_empty_content_raises(self) -> None:
        """Test empty content raises ValueError with FR56 reference."""
        with pytest.raises(ValueError, match="FR56"):
            Publication(
                id="pub-123",
                content="",
                title="Test Title",
                author_agent_id="agent-456",
                status=PublicationStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
            )

    def test_publication_empty_title_raises(self) -> None:
        """Test empty title raises ValueError with FR56 reference."""
        with pytest.raises(ValueError, match="FR56"):
            Publication(
                id="pub-123",
                content="Test content",
                title="",
                author_agent_id="agent-456",
                status=PublicationStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
            )

    def test_publication_empty_agent_id_raises(self) -> None:
        """Test empty agent ID raises ValueError with FR56 reference."""
        with pytest.raises(ValueError, match="FR56"):
            Publication(
                id="pub-123",
                content="Test content",
                title="Test Title",
                author_agent_id="",
                status=PublicationStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
            )

    def test_with_status_returns_new_instance(self) -> None:
        """Test with_status creates new instance with updated status."""
        now = datetime.now(timezone.utc)
        pub = Publication(
            id="pub-123",
            content="Test content",
            title="Test Title",
            author_agent_id="agent-456",
            status=PublicationStatus.DRAFT,
            created_at=now,
        )

        updated = pub.with_status(PublicationStatus.APPROVED)

        assert updated.status == PublicationStatus.APPROVED
        assert pub.status == PublicationStatus.DRAFT  # Original unchanged
        assert updated.id == pub.id
        assert updated.content == pub.content

    def test_with_scan_timestamp_returns_new_instance(self) -> None:
        """Test with_scan_timestamp creates new instance."""
        now = datetime.now(timezone.utc)
        later = datetime.now(timezone.utc)
        pub = Publication(
            id="pub-123",
            content="Test content",
            title="Test Title",
            author_agent_id="agent-456",
            status=PublicationStatus.DRAFT,
            created_at=now,
        )

        updated = pub.with_scan_timestamp(later)

        assert updated.scanned_at == later
        assert pub.scanned_at is None  # Original unchanged


class TestPublicationScanRequest:
    """Tests for PublicationScanRequest dataclass (FR56)."""

    def test_create_valid_request(self) -> None:
        """Test creating a valid scan request."""
        request = PublicationScanRequest(
            publication_id="pub-123",
            content="Test content",
            title="Test Title",
        )

        assert request.publication_id == "pub-123"
        assert request.content == "Test content"
        assert request.title == "Test Title"

    def test_request_is_frozen(self) -> None:
        """Test request is immutable."""
        request = PublicationScanRequest(
            publication_id="pub-123",
            content="Test content",
            title="Test Title",
        )

        with pytest.raises(AttributeError):
            request.content = "Modified"  # type: ignore

    def test_request_empty_id_raises(self) -> None:
        """Test empty publication ID raises ValueError."""
        with pytest.raises(ValueError, match="FR56"):
            PublicationScanRequest(
                publication_id="",
                content="Test content",
                title="Test Title",
            )

    def test_request_empty_content_raises(self) -> None:
        """Test empty content raises ValueError."""
        with pytest.raises(ValueError, match="FR56"):
            PublicationScanRequest(
                publication_id="pub-123",
                content="",
                title="Test Title",
            )

    def test_request_empty_title_raises(self) -> None:
        """Test empty title raises ValueError."""
        with pytest.raises(ValueError, match="FR56"):
            PublicationScanRequest(
                publication_id="pub-123",
                content="Test content",
                title="",
            )

    def test_from_publication_factory(self) -> None:
        """Test from_publication factory method."""
        now = datetime.now(timezone.utc)
        pub = Publication(
            id="pub-123",
            content="Test content",
            title="Test Title",
            author_agent_id="agent-456",
            status=PublicationStatus.DRAFT,
            created_at=now,
        )

        request = PublicationScanRequest.from_publication(pub)

        assert request.publication_id == pub.id
        assert request.content == pub.content
        assert request.title == pub.title


class TestPublicationScannedEventPayload:
    """Tests for PublicationScannedEventPayload (FR56, AC5)."""

    def test_create_clean_scan_payload(self) -> None:
        """Test creating a clean scan event payload."""
        now = datetime.now(timezone.utc)
        payload = PublicationScannedEventPayload.clean_scan(
            publication_id="pub-123",
            title="Test Title",
            scanned_at=now,
        )

        assert payload.publication_id == "pub-123"
        assert payload.title == "Test Title"
        assert payload.scan_result == "clean"
        assert payload.matched_terms == ()
        assert payload.scanned_at == now
        assert payload.detection_method == "nfkc_scan"

    def test_create_blocked_scan_payload(self) -> None:
        """Test creating a blocked scan event payload."""
        now = datetime.now(timezone.utc)
        payload = PublicationScannedEventPayload.blocked_scan(
            publication_id="pub-123",
            title="Test Title",
            matched_terms=("emergence", "consciousness"),
            scanned_at=now,
        )

        assert payload.scan_result == "blocked"
        assert payload.matched_terms == ("emergence", "consciousness")
        assert payload.terms_count == 2

    def test_event_type_for_clean_scan(self) -> None:
        """Test event_type property for clean scan."""
        now = datetime.now(timezone.utc)
        payload = PublicationScannedEventPayload.clean_scan(
            publication_id="pub-123",
            title="Test Title",
            scanned_at=now,
        )

        assert payload.event_type == PUBLICATION_SCANNED_EVENT_TYPE

    def test_event_type_for_blocked_scan(self) -> None:
        """Test event_type property for blocked scan."""
        now = datetime.now(timezone.utc)
        payload = PublicationScannedEventPayload.blocked_scan(
            publication_id="pub-123",
            title="Test Title",
            matched_terms=("emergence",),
            scanned_at=now,
        )

        assert payload.event_type == PUBLICATION_BLOCKED_EVENT_TYPE

    def test_is_blocked_property(self) -> None:
        """Test is_blocked property."""
        now = datetime.now(timezone.utc)
        blocked = PublicationScannedEventPayload.blocked_scan(
            publication_id="pub-123",
            title="Test Title",
            matched_terms=("emergence",),
            scanned_at=now,
        )
        clean = PublicationScannedEventPayload.clean_scan(
            publication_id="pub-123",
            title="Test Title",
            scanned_at=now,
        )

        assert blocked.is_blocked is True
        assert blocked.is_clean is False
        assert clean.is_clean is True
        assert clean.is_blocked is False

    def test_to_dict_for_serialization(self) -> None:
        """Test to_dict returns serializable dictionary."""
        now = datetime.now(timezone.utc)
        payload = PublicationScannedEventPayload.blocked_scan(
            publication_id="pub-123",
            title="Test Title",
            matched_terms=("emergence",),
            scanned_at=now,
        )

        data = payload.to_dict()

        assert data["publication_id"] == "pub-123"
        assert data["title"] == "Test Title"
        assert data["scan_result"] == "blocked"
        assert data["matched_terms"] == ["emergence"]
        assert data["scanned_at"] == now.isoformat()
        assert data["detection_method"] == "nfkc_scan"
        assert data["terms_count"] == 1

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content returns deterministic bytes."""
        now = datetime.now(timezone.utc)
        payload = PublicationScannedEventPayload.blocked_scan(
            publication_id="pub-123",
            title="Test Title",
            matched_terms=("emergence", "consciousness"),
            scanned_at=now,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_content_hash_is_hex_string(self) -> None:
        """Test content_hash returns hex-encoded hash."""
        now = datetime.now(timezone.utc)
        payload = PublicationScannedEventPayload.clean_scan(
            publication_id="pub-123",
            title="Test Title",
            scanned_at=now,
        )

        hash_str = payload.content_hash()

        assert len(hash_str) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in hash_str)

    def test_validation_clean_scan_with_terms_raises(self) -> None:
        """Test clean scan with matched terms raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR56"):
            PublicationScannedEventPayload(
                publication_id="pub-123",
                title="Test Title",
                scan_result="clean",
                matched_terms=("emergence",),  # Should be empty for clean
                scanned_at=now,
                detection_method="nfkc_scan",
            )

    def test_validation_blocked_scan_without_terms_raises(self) -> None:
        """Test blocked scan without matched terms raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR56"):
            PublicationScannedEventPayload(
                publication_id="pub-123",
                title="Test Title",
                scan_result="blocked",
                matched_terms=(),  # Should have terms for blocked
                scanned_at=now,
                detection_method="nfkc_scan",
            )

    def test_validation_empty_publication_id_raises(self) -> None:
        """Test empty publication_id raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR56"):
            PublicationScannedEventPayload.clean_scan(
                publication_id="",
                title="Test Title",
                scanned_at=now,
            )

    def test_validation_empty_title_raises(self) -> None:
        """Test empty title raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR56"):
            PublicationScannedEventPayload.clean_scan(
                publication_id="pub-123",
                title="",
                scanned_at=now,
            )

    def test_validation_invalid_scan_result_raises(self) -> None:
        """Test invalid scan_result raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="FR56"):
            PublicationScannedEventPayload(
                publication_id="pub-123",
                title="Test Title",
                scan_result="invalid",  # type: ignore
                matched_terms=(),
                scanned_at=now,
                detection_method="nfkc_scan",
            )


class TestPublicationConstants:
    """Tests for publication module constants."""

    def test_publication_id_prefix(self) -> None:
        """Test PUBLICATION_ID_PREFIX constant."""
        assert PUBLICATION_ID_PREFIX == "pub-"
