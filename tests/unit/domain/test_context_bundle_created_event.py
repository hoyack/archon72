"""Unit tests for ContextBundleCreatedPayload domain event (Story 2.9, ADR-2).

Tests cover:
- Payload creation and validation
- Field validation (bundle_id, meeting_id, as_of_event_seq, etc.)
- Serialization (to_dict)
- Edge cases
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.events.context_bundle_created import (
    CONTEXT_BUNDLE_CREATED_EVENT_TYPE,
    ContextBundleCreatedPayload,
)
from src.domain.models.context_bundle import CONTENT_REF_PREFIX

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def valid_content_ref() -> str:
    """Return a valid ContentRef."""
    return f"{CONTENT_REF_PREFIX}{'a' * 64}"


@pytest.fixture
def valid_bundle_hash() -> str:
    """Return a valid bundle hash."""
    return "b" * 64


@pytest.fixture
def valid_meeting_id() -> UUID:
    """Return a valid meeting UUID."""
    return uuid4()


@pytest.fixture
def valid_created_at() -> datetime:
    """Return a valid UTC datetime."""
    return datetime.now(timezone.utc)


@pytest.fixture
def valid_bundle_created_payload(
    valid_meeting_id: UUID,
    valid_content_ref: str,
    valid_bundle_hash: str,
    valid_created_at: datetime,
) -> ContextBundleCreatedPayload:
    """Return a valid ContextBundleCreatedPayload."""
    return ContextBundleCreatedPayload(
        bundle_id=f"ctx_{valid_meeting_id}_42",
        meeting_id=valid_meeting_id,
        as_of_event_seq=42,
        identity_prompt_ref=valid_content_ref,
        meeting_state_ref=f"{CONTENT_REF_PREFIX}{'c' * 64}",
        precedent_count=3,
        bundle_hash=valid_bundle_hash,
        signing_key_id="key-001",
        created_at=valid_created_at,
    )


# ============================================================================
# Event Type Constant Tests
# ============================================================================


class TestEventTypeConstant:
    """Tests for event type constant."""

    def test_event_type_constant_value(self) -> None:
        """Event type should match expected value."""
        assert CONTEXT_BUNDLE_CREATED_EVENT_TYPE == "context.bundle.created"


# ============================================================================
# Payload Creation Tests
# ============================================================================


class TestContextBundleCreatedPayloadCreation:
    """Tests for payload creation."""

    def test_valid_payload_creates_successfully(
        self,
        valid_bundle_created_payload: ContextBundleCreatedPayload,
    ) -> None:
        """Valid payload should create successfully."""
        assert valid_bundle_created_payload.as_of_event_seq == 42
        assert valid_bundle_created_payload.precedent_count == 3

    def test_payload_is_frozen(
        self,
        valid_bundle_created_payload: ContextBundleCreatedPayload,
    ) -> None:
        """Payload should be frozen (immutable)."""
        with pytest.raises(AttributeError):
            valid_bundle_created_payload.precedent_count = 5  # type: ignore[misc]


# ============================================================================
# Field Validation Tests
# ============================================================================


class TestContextBundleCreatedPayloadValidation:
    """Tests for payload field validation."""

    def test_empty_bundle_id_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Empty bundle_id should raise ValueError."""
        with pytest.raises(ValueError, match="bundle_id must be non-empty"):
            ContextBundleCreatedPayload(
                bundle_id="",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_count=0,
                bundle_hash=valid_bundle_hash,
                signing_key_id="key",
                created_at=valid_created_at,
            )

    def test_invalid_bundle_id_prefix_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """bundle_id without 'ctx_' prefix should raise ValueError."""
        with pytest.raises(ValueError, match="bundle_id must start with"):
            ContextBundleCreatedPayload(
                bundle_id="wrong_prefix_123",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_count=0,
                bundle_hash=valid_bundle_hash,
                signing_key_id="key",
                created_at=valid_created_at,
            )

    def test_non_uuid_meeting_id_raises_type_error(
        self,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Non-UUID meeting_id should raise TypeError."""
        with pytest.raises(TypeError, match="meeting_id must be UUID"):
            ContextBundleCreatedPayload(
                bundle_id="ctx_test_1",
                meeting_id="not-a-uuid",  # type: ignore[arg-type]
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_count=0,
                bundle_hash=valid_bundle_hash,
                signing_key_id="key",
                created_at=valid_created_at,
            )

    def test_zero_sequence_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """as_of_event_seq = 0 should raise ValueError."""
        with pytest.raises(ValueError, match="as_of_event_seq must be >= 1"):
            ContextBundleCreatedPayload(
                bundle_id="ctx_test_0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=0,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_count=0,
                bundle_hash=valid_bundle_hash,
                signing_key_id="key",
                created_at=valid_created_at,
            )

    def test_invalid_identity_prompt_ref_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Invalid identity_prompt_ref should raise ValueError."""
        with pytest.raises(ValueError, match="identity_prompt_ref"):
            ContextBundleCreatedPayload(
                bundle_id="ctx_test_1",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref="invalid",
                meeting_state_ref=valid_content_ref,
                precedent_count=0,
                bundle_hash=valid_bundle_hash,
                signing_key_id="key",
                created_at=valid_created_at,
            )

    def test_invalid_meeting_state_ref_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Invalid meeting_state_ref should raise ValueError."""
        with pytest.raises(ValueError, match="meeting_state_ref"):
            ContextBundleCreatedPayload(
                bundle_id="ctx_test_1",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref="invalid",
                precedent_count=0,
                bundle_hash=valid_bundle_hash,
                signing_key_id="key",
                created_at=valid_created_at,
            )

    def test_negative_precedent_count_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Negative precedent_count should raise ValueError."""
        with pytest.raises(ValueError, match="precedent_count must be >= 0"):
            ContextBundleCreatedPayload(
                bundle_id="ctx_test_1",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_count=-1,
                bundle_hash=valid_bundle_hash,
                signing_key_id="key",
                created_at=valid_created_at,
            )

    def test_invalid_bundle_hash_length_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_created_at: datetime,
    ) -> None:
        """Invalid bundle_hash length should raise ValueError."""
        with pytest.raises(ValueError, match="bundle_hash must be 64"):
            ContextBundleCreatedPayload(
                bundle_id="ctx_test_1",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_count=0,
                bundle_hash="short",
                signing_key_id="key",
                created_at=valid_created_at,
            )

    def test_empty_signing_key_id_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Empty signing_key_id should raise ValueError."""
        with pytest.raises(ValueError, match="signing_key_id must be non-empty"):
            ContextBundleCreatedPayload(
                bundle_id="ctx_test_1",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_count=0,
                bundle_hash=valid_bundle_hash,
                signing_key_id="",
                created_at=valid_created_at,
            )

    def test_invalid_created_at_type_raises_type_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
    ) -> None:
        """Non-datetime created_at should raise TypeError."""
        with pytest.raises(TypeError, match="created_at must be datetime"):
            ContextBundleCreatedPayload(
                bundle_id="ctx_test_1",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_count=0,
                bundle_hash=valid_bundle_hash,
                signing_key_id="key",
                created_at="2025-01-01T00:00:00Z",  # type: ignore[arg-type]
            )


# ============================================================================
# Serialization Tests
# ============================================================================


class TestContextBundleCreatedPayloadSerialization:
    """Tests for payload serialization."""

    def test_to_dict_contains_all_fields(
        self,
        valid_bundle_created_payload: ContextBundleCreatedPayload,
    ) -> None:
        """to_dict should contain all fields."""
        d = valid_bundle_created_payload.to_dict()
        assert "bundle_id" in d
        assert "meeting_id" in d
        assert "as_of_event_seq" in d
        assert "identity_prompt_ref" in d
        assert "meeting_state_ref" in d
        assert "precedent_count" in d
        assert "bundle_hash" in d
        assert "signing_key_id" in d
        assert "created_at" in d

    def test_to_dict_meeting_id_is_string(
        self,
        valid_bundle_created_payload: ContextBundleCreatedPayload,
    ) -> None:
        """meeting_id in to_dict should be string."""
        d = valid_bundle_created_payload.to_dict()
        assert isinstance(d["meeting_id"], str)

    def test_to_dict_created_at_is_iso_format(
        self,
        valid_bundle_created_payload: ContextBundleCreatedPayload,
    ) -> None:
        """created_at in to_dict should be ISO format string."""
        d = valid_bundle_created_payload.to_dict()
        assert isinstance(d["created_at"], str)
        # Should be parseable as datetime
        datetime.fromisoformat(d["created_at"])


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestContextBundleCreatedPayloadEdgeCases:
    """Tests for edge cases."""

    def test_zero_precedent_count_valid(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """precedent_count = 0 should be valid."""
        payload = ContextBundleCreatedPayload(
            bundle_id="ctx_test_1",
            meeting_id=valid_meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_content_ref,
            precedent_count=0,
            bundle_hash=valid_bundle_hash,
            signing_key_id="key",
            created_at=valid_created_at,
        )
        assert payload.precedent_count == 0

    def test_sequence_1_valid(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: str,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """as_of_event_seq = 1 should be valid."""
        payload = ContextBundleCreatedPayload(
            bundle_id="ctx_test_1",
            meeting_id=valid_meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_content_ref,
            precedent_count=0,
            bundle_hash=valid_bundle_hash,
            signing_key_id="key",
            created_at=valid_created_at,
        )
        assert payload.as_of_event_seq == 1
