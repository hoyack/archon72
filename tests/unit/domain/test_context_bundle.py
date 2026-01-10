"""Unit tests for ContextBundlePayload domain model (Story 2.9, ADR-2).

Tests cover:
- ContentRef validation and creation
- ContextBundlePayload field validation
- Bundle ID computation
- Serialization (to_dict, to_signable_dict)
- Edge cases (empty precedent_refs, max precedent_refs)

Constitutional Constraints:
- CT-1: LLMs are stateless -> Context bundles provide deterministic state
- CT-13: Integrity outranks availability -> Strict validation
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.models.context_bundle import (
    BUNDLE_ID_PREFIX,
    CONTENT_REF_LENGTH,
    CONTENT_REF_PREFIX,
    MAX_PRECEDENT_REFS,
    ContentRef,
    ContextBundlePayload,
    UnsignedContextBundle,
    create_content_ref,
    validate_content_ref,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def valid_content_ref() -> ContentRef:
    """Return a valid ContentRef."""
    return f"{CONTENT_REF_PREFIX}{'a' * 64}"


@pytest.fixture
def valid_bundle_hash() -> str:
    """Return a valid bundle hash (64 hex chars)."""
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
def valid_context_bundle_payload(
    valid_meeting_id: UUID,
    valid_content_ref: ContentRef,
    valid_bundle_hash: str,
    valid_created_at: datetime,
) -> ContextBundlePayload:
    """Return a valid ContextBundlePayload."""
    return ContextBundlePayload(
        schema_version="1.0",
        meeting_id=valid_meeting_id,
        as_of_event_seq=42,
        identity_prompt_ref=valid_content_ref,
        meeting_state_ref=f"{CONTENT_REF_PREFIX}{'c' * 64}",
        precedent_refs=tuple(),
        created_at=valid_created_at,
        bundle_hash=valid_bundle_hash,
        signature="test_signature_123",
        signing_key_id="key-001",
    )


# ============================================================================
# ContentRef Validation Tests
# ============================================================================


class TestValidateContentRef:
    """Tests for validate_content_ref function."""

    def test_valid_content_ref_passes(self, valid_content_ref: ContentRef) -> None:
        """Valid ContentRef should pass validation."""
        # Should not raise
        validate_content_ref(valid_content_ref, "test_field")

    def test_missing_prefix_raises_value_error(self) -> None:
        """ContentRef without 'ref:' prefix should raise ValueError."""
        invalid_ref = "a" * 64  # Missing prefix
        with pytest.raises(ValueError, match="must be ContentRef format"):
            validate_content_ref(invalid_ref, "test_field")

    def test_wrong_prefix_raises_value_error(self) -> None:
        """ContentRef with wrong prefix should raise ValueError."""
        invalid_ref = f"wrong:{'a' * 64}"
        with pytest.raises(ValueError, match="must be ContentRef format"):
            validate_content_ref(invalid_ref, "test_field")

    def test_short_hash_raises_value_error(self) -> None:
        """ContentRef with short hash should raise ValueError."""
        invalid_ref = f"{CONTENT_REF_PREFIX}{'a' * 63}"  # 63 chars, not 64
        with pytest.raises(ValueError, match=f"must be {CONTENT_REF_LENGTH} chars"):
            validate_content_ref(invalid_ref, "test_field")

    def test_long_hash_raises_value_error(self) -> None:
        """ContentRef with long hash should raise ValueError."""
        invalid_ref = f"{CONTENT_REF_PREFIX}{'a' * 65}"  # 65 chars, not 64
        with pytest.raises(ValueError, match=f"must be {CONTENT_REF_LENGTH} chars"):
            validate_content_ref(invalid_ref, "test_field")

    def test_uppercase_hash_raises_value_error(self) -> None:
        """ContentRef with uppercase hex should raise ValueError."""
        invalid_ref = f"{CONTENT_REF_PREFIX}{'A' * 64}"  # Uppercase
        with pytest.raises(ValueError, match="must match pattern"):
            validate_content_ref(invalid_ref, "test_field")

    def test_non_hex_chars_raises_value_error(self) -> None:
        """ContentRef with non-hex characters should raise ValueError."""
        invalid_ref = f"{CONTENT_REF_PREFIX}{'g' * 64}"  # 'g' is not hex
        with pytest.raises(ValueError, match="must match pattern"):
            validate_content_ref(invalid_ref, "test_field")

    def test_field_name_in_error_message(self) -> None:
        """Field name should appear in error message."""
        invalid_ref = "invalid"
        with pytest.raises(ValueError, match="my_custom_field"):
            validate_content_ref(invalid_ref, "my_custom_field")


class TestCreateContentRef:
    """Tests for create_content_ref function."""

    def test_creates_valid_ref_from_hash(self) -> None:
        """Should create valid ContentRef from SHA-256 hash."""
        sha256_hash = "a" * 64
        ref = create_content_ref(sha256_hash)
        assert ref == f"{CONTENT_REF_PREFIX}{sha256_hash}"

    def test_short_hash_raises_value_error(self) -> None:
        """Short hash should raise ValueError."""
        with pytest.raises(ValueError, match="must be 64 chars"):
            create_content_ref("a" * 63)

    def test_long_hash_raises_value_error(self) -> None:
        """Long hash should raise ValueError."""
        with pytest.raises(ValueError, match="must be 64 chars"):
            create_content_ref("a" * 65)

    def test_uppercase_hash_raises_value_error(self) -> None:
        """Uppercase hex should raise ValueError."""
        with pytest.raises(ValueError, match="must be lowercase hex"):
            create_content_ref("A" * 64)

    def test_non_hex_chars_raises_value_error(self) -> None:
        """Non-hex characters should raise ValueError."""
        with pytest.raises(ValueError, match="must be lowercase hex"):
            create_content_ref("z" * 64)


# ============================================================================
# ContextBundlePayload Validation Tests
# ============================================================================


class TestContextBundlePayloadValidation:
    """Tests for ContextBundlePayload field validation."""

    def test_valid_payload_creates_successfully(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """Valid payload should create successfully."""
        assert valid_context_bundle_payload.schema_version == "1.0"
        assert valid_context_bundle_payload.as_of_event_seq == 42

    def test_invalid_schema_version_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Invalid schema_version should raise ValueError."""
        with pytest.raises(ValueError, match="schema_version must be"):
            ContextBundlePayload(
                schema_version="2.0",  # type: ignore[arg-type]
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="key",
            )

    def test_non_uuid_meeting_id_raises_type_error(
        self,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Non-UUID meeting_id should raise TypeError."""
        with pytest.raises(TypeError, match="meeting_id must be UUID"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id="not-a-uuid",  # type: ignore[arg-type]
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="key",
            )

    def test_zero_sequence_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """as_of_event_seq = 0 should raise ValueError."""
        with pytest.raises(ValueError, match="as_of_event_seq must be >= 1"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=0,  # Invalid
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="key",
            )

    def test_negative_sequence_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Negative as_of_event_seq should raise ValueError."""
        with pytest.raises(ValueError, match="as_of_event_seq must be >= 1"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=-5,  # Invalid
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="key",
            )

    def test_invalid_identity_prompt_ref_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Invalid identity_prompt_ref should raise ValueError."""
        with pytest.raises(ValueError, match="identity_prompt_ref"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref="invalid",  # Invalid
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="key",
            )

    def test_invalid_meeting_state_ref_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Invalid meeting_state_ref should raise ValueError."""
        with pytest.raises(ValueError, match="meeting_state_ref"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref="invalid",  # Invalid
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="key",
            )

    def test_too_many_precedent_refs_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """More than MAX_PRECEDENT_REFS should raise ValueError."""
        too_many_refs = tuple(
            f"{CONTENT_REF_PREFIX}{str(i).zfill(64)[-64:]}"
            for i in range(MAX_PRECEDENT_REFS + 1)
        )
        # Fix the refs to be valid hex
        too_many_refs = tuple(
            f"{CONTENT_REF_PREFIX}{'0' * (64 - len(str(i)))}{str(i)[-64:]}"[:68]
            for i in range(MAX_PRECEDENT_REFS + 1)
        )
        # Actually make them valid
        too_many_refs = tuple(
            f"{CONTENT_REF_PREFIX}{'a' * 64}" for _ in range(MAX_PRECEDENT_REFS + 1)
        )

        with pytest.raises(ValueError, match=f"Maximum {MAX_PRECEDENT_REFS}"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=too_many_refs,
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="key",
            )

    def test_invalid_precedent_ref_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Invalid precedent_ref in array should raise ValueError."""
        with pytest.raises(ValueError, match="precedent_refs"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=(valid_content_ref, "invalid"),  # One invalid
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="key",
            )

    def test_invalid_bundle_hash_length_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_created_at: datetime,
    ) -> None:
        """Invalid bundle_hash length should raise ValueError."""
        with pytest.raises(ValueError, match="bundle_hash must be 64"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash="short",  # Invalid
                signature="sig",
                signing_key_id="key",
            )

    def test_invalid_bundle_hash_format_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_created_at: datetime,
    ) -> None:
        """Invalid bundle_hash format should raise ValueError."""
        with pytest.raises(ValueError, match="bundle_hash must be lowercase hex"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash="G" * 64,  # Invalid (non-hex)
                signature="sig",
                signing_key_id="key",
            )

    def test_empty_signature_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Empty signature should raise ValueError."""
        with pytest.raises(ValueError, match="signature must be non-empty"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="",  # Invalid
                signing_key_id="key",
            )

    def test_empty_signing_key_id_raises_value_error(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Empty signing_key_id should raise ValueError."""
        with pytest.raises(ValueError, match="signing_key_id must be non-empty"):
            ContextBundlePayload(
                schema_version="1.0",
                meeting_id=valid_meeting_id,
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
                bundle_hash=valid_bundle_hash,
                signature="sig",
                signing_key_id="",  # Invalid
            )


# ============================================================================
# Bundle ID and Properties Tests
# ============================================================================


class TestContextBundlePayloadProperties:
    """Tests for ContextBundlePayload properties."""

    def test_bundle_id_computed_correctly(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """bundle_id should be computed from meeting_id and as_of_event_seq."""
        expected_id = (
            f"{BUNDLE_ID_PREFIX}"
            f"{valid_context_bundle_payload.meeting_id}_"
            f"{valid_context_bundle_payload.as_of_event_seq}"
        )
        assert valid_context_bundle_payload.bundle_id == expected_id

    def test_bundle_id_starts_with_prefix(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """bundle_id should start with BUNDLE_ID_PREFIX."""
        assert valid_context_bundle_payload.bundle_id.startswith(BUNDLE_ID_PREFIX)

    def test_bundle_is_frozen(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """ContextBundlePayload should be frozen (immutable)."""
        with pytest.raises(AttributeError):
            valid_context_bundle_payload.as_of_event_seq = 100  # type: ignore[misc]


# ============================================================================
# Serialization Tests
# ============================================================================


class TestContextBundlePayloadSerialization:
    """Tests for ContextBundlePayload serialization methods."""

    def test_to_dict_contains_all_fields(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """to_dict should contain all fields."""
        d = valid_context_bundle_payload.to_dict()
        assert "schema_version" in d
        assert "bundle_id" in d
        assert "meeting_id" in d
        assert "as_of_event_seq" in d
        assert "identity_prompt_ref" in d
        assert "meeting_state_ref" in d
        assert "precedent_refs" in d
        assert "created_at" in d
        assert "bundle_hash" in d
        assert "signature" in d
        assert "signing_key_id" in d

    def test_to_dict_meeting_id_is_string(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """meeting_id in to_dict should be string."""
        d = valid_context_bundle_payload.to_dict()
        assert isinstance(d["meeting_id"], str)

    def test_to_dict_created_at_is_iso_format(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """created_at in to_dict should be ISO format string."""
        d = valid_context_bundle_payload.to_dict()
        assert isinstance(d["created_at"], str)
        # Should be parseable as datetime
        datetime.fromisoformat(d["created_at"])

    def test_to_dict_precedent_refs_is_list(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """precedent_refs in to_dict should be list (not tuple)."""
        d = valid_context_bundle_payload.to_dict()
        assert isinstance(d["precedent_refs"], list)

    def test_to_signable_dict_excludes_signature_fields(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """to_signable_dict should NOT contain signature or bundle_hash."""
        d = valid_context_bundle_payload.to_signable_dict()
        assert "signature" not in d
        assert "bundle_hash" not in d
        assert "signing_key_id" not in d
        assert "bundle_id" not in d

    def test_to_signable_dict_contains_core_fields(
        self,
        valid_context_bundle_payload: ContextBundlePayload,
    ) -> None:
        """to_signable_dict should contain core fields for hashing."""
        d = valid_context_bundle_payload.to_signable_dict()
        assert "schema_version" in d
        assert "meeting_id" in d
        assert "as_of_event_seq" in d
        assert "identity_prompt_ref" in d
        assert "meeting_state_ref" in d
        assert "precedent_refs" in d
        assert "created_at" in d

    def test_canonical_json_is_deterministic(self) -> None:
        """canonical_json should produce deterministic output."""
        data = {"z": 1, "a": 2, "m": 3}
        json1 = ContextBundlePayload.canonical_json(data)
        json2 = ContextBundlePayload.canonical_json(data)
        assert json1 == json2
        # Keys should be sorted
        assert json1 == '{"a":2,"m":3,"z":1}'

    def test_canonical_json_no_whitespace(self) -> None:
        """canonical_json should have no whitespace."""
        data = {"key": "value", "nested": {"a": 1}}
        json_str = ContextBundlePayload.canonical_json(data)
        assert " " not in json_str
        assert "\n" not in json_str


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestContextBundlePayloadEdgeCases:
    """Tests for edge cases."""

    def test_empty_precedent_refs_valid(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Empty precedent_refs tuple should be valid."""
        payload = ContextBundlePayload(
            schema_version="1.0",
            meeting_id=valid_meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_content_ref,
            precedent_refs=tuple(),  # Empty
            created_at=valid_created_at,
            bundle_hash=valid_bundle_hash,
            signature="sig",
            signing_key_id="key",
        )
        assert len(payload.precedent_refs) == 0

    def test_max_precedent_refs_valid(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """Exactly MAX_PRECEDENT_REFS should be valid."""
        max_refs = tuple(
            f"{CONTENT_REF_PREFIX}{'a' * 64}" for _ in range(MAX_PRECEDENT_REFS)
        )
        payload = ContextBundlePayload(
            schema_version="1.0",
            meeting_id=valid_meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_content_ref,
            precedent_refs=max_refs,
            created_at=valid_created_at,
            bundle_hash=valid_bundle_hash,
            signature="sig",
            signing_key_id="key",
        )
        assert len(payload.precedent_refs) == MAX_PRECEDENT_REFS

    def test_sequence_1_valid(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_bundle_hash: str,
        valid_created_at: datetime,
    ) -> None:
        """as_of_event_seq = 1 (minimum) should be valid."""
        payload = ContextBundlePayload(
            schema_version="1.0",
            meeting_id=valid_meeting_id,
            as_of_event_seq=1,  # Minimum valid
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_content_ref,
            precedent_refs=tuple(),
            created_at=valid_created_at,
            bundle_hash=valid_bundle_hash,
            signature="sig",
            signing_key_id="key",
        )
        assert payload.as_of_event_seq == 1


# ============================================================================
# UnsignedContextBundle Tests
# ============================================================================


class TestUnsignedContextBundle:
    """Tests for UnsignedContextBundle intermediate state."""

    def test_valid_unsigned_bundle_creates_successfully(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_created_at: datetime,
    ) -> None:
        """Valid unsigned bundle should create successfully."""
        bundle = UnsignedContextBundle(
            schema_version="1.0",
            meeting_id=valid_meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_content_ref,
            precedent_refs=tuple(),
            created_at=valid_created_at,
        )
        assert bundle.schema_version == "1.0"

    def test_to_signable_dict_returns_correct_fields(
        self,
        valid_meeting_id: UUID,
        valid_content_ref: ContentRef,
        valid_created_at: datetime,
    ) -> None:
        """to_signable_dict should return signable fields."""
        bundle = UnsignedContextBundle(
            schema_version="1.0",
            meeting_id=valid_meeting_id,
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_content_ref,
            precedent_refs=tuple(),
            created_at=valid_created_at,
        )
        d = bundle.to_signable_dict()
        assert d["schema_version"] == "1.0"
        assert d["as_of_event_seq"] == 42

    def test_invalid_unsigned_bundle_raises_error(
        self,
        valid_content_ref: ContentRef,
        valid_created_at: datetime,
    ) -> None:
        """Invalid unsigned bundle should raise error."""
        with pytest.raises(TypeError, match="meeting_id must be UUID"):
            UnsignedContextBundle(
                schema_version="1.0",
                meeting_id="not-uuid",  # type: ignore[arg-type]
                as_of_event_seq=1,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_content_ref,
                precedent_refs=tuple(),
                created_at=valid_created_at,
            )
