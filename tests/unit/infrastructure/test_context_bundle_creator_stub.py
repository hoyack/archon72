"""Unit tests for ContextBundleCreatorStub (Story 2.9, ADR-2).

Tests cover:
- Bundle creation with DEV_MODE_WATERMARK
- Signature verification
- Hash computation
- Bundle storage and retrieval
- Error handling

Constitutional Constraints:
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern verification
- CT-12: Witnessing through hash verification
"""

from uuid import uuid4

import pytest

from src.application.ports.context_bundle_creator import (
    ContextBundleCreatorPort,
)
from src.domain.models.context_bundle import (
    CONTENT_REF_PREFIX,
    CONTEXT_BUNDLE_SCHEMA_VERSION,
)
from src.infrastructure.stubs.context_bundle_creator_stub import (
    DEV_MODE_WATERMARK,
    ContextBundleCreatorStub,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def valid_content_ref() -> str:
    """Return a valid ContentRef."""
    return f"{CONTENT_REF_PREFIX}{'a' * 64}"


@pytest.fixture
def valid_meeting_state_ref() -> str:
    """Return a valid meeting state ContentRef."""
    return f"{CONTENT_REF_PREFIX}{'b' * 64}"


@pytest.fixture
def valid_precedent_ref() -> str:
    """Return a valid precedent ContentRef."""
    return f"{CONTENT_REF_PREFIX}{'c' * 64}"


@pytest.fixture
def creator_stub() -> ContextBundleCreatorStub:
    """Return a fresh ContextBundleCreatorStub."""
    return ContextBundleCreatorStub()


@pytest.fixture
def creator_stub_with_custom_key() -> ContextBundleCreatorStub:
    """Return a stub with custom signing key."""
    return ContextBundleCreatorStub(signing_key_id="CUSTOM_KEY:test:v1")


# ============================================================================
# DEV_MODE_WATERMARK Tests
# ============================================================================


class TestDevModeWatermark:
    """Tests for DEV_MODE_WATERMARK pattern (RT-1/ADR-4)."""

    def test_watermark_constant_exists(self) -> None:
        """DEV_MODE_WATERMARK constant should exist."""
        assert DEV_MODE_WATERMARK is not None
        assert isinstance(DEV_MODE_WATERMARK, str)

    def test_watermark_contains_stub_identifier(self) -> None:
        """Watermark should identify the stub."""
        assert "ContextBundleCreatorStub" in DEV_MODE_WATERMARK
        assert "DEV_STUB" in DEV_MODE_WATERMARK

    def test_default_signing_key_contains_watermark(
        self,
        creator_stub: ContextBundleCreatorStub,
    ) -> None:
        """Default signing key should contain watermark."""
        assert DEV_MODE_WATERMARK in creator_stub._signing_key_id


# ============================================================================
# Initialization Tests
# ============================================================================


class TestContextBundleCreatorStubInit:
    """Tests for stub initialization."""

    def test_stub_implements_port(self) -> None:
        """Stub should implement ContextBundleCreatorPort."""
        stub = ContextBundleCreatorStub()
        assert isinstance(stub, ContextBundleCreatorPort)

    def test_stub_initializes_empty_bundles(
        self,
        creator_stub: ContextBundleCreatorStub,
    ) -> None:
        """Stub should start with empty bundle storage."""
        assert len(creator_stub._bundles) == 0

    def test_stub_with_default_key(
        self,
        creator_stub: ContextBundleCreatorStub,
    ) -> None:
        """Stub should have default signing key."""
        assert creator_stub._signing_key_id is not None
        assert "BUNDLE:" in creator_stub._signing_key_id

    def test_stub_with_custom_key(
        self,
        creator_stub_with_custom_key: ContextBundleCreatorStub,
    ) -> None:
        """Stub should use custom signing key when provided."""
        assert creator_stub_with_custom_key._signing_key_id == "CUSTOM_KEY:test:v1"


# ============================================================================
# Bundle Creation Tests
# ============================================================================


class TestBundleCreation:
    """Tests for bundle creation."""

    @pytest.mark.asyncio
    async def test_create_bundle_success(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """create_bundle should succeed with valid inputs."""
        meeting_id = uuid4()
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert result.success is True
        assert result.bundle is not None
        assert result.bundle_hash is not None
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_create_bundle_sets_schema_version(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Created bundle should have correct schema version."""
        meeting_id = uuid4()
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert result.bundle.schema_version == CONTEXT_BUNDLE_SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_create_bundle_sets_meeting_id(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Created bundle should have correct meeting_id."""
        meeting_id = uuid4()
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert result.bundle.meeting_id == meeting_id

    @pytest.mark.asyncio
    async def test_create_bundle_sets_sequence(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Created bundle should have correct as_of_event_seq."""
        meeting_id = uuid4()
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=999,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert result.bundle.as_of_event_seq == 999

    @pytest.mark.asyncio
    async def test_create_bundle_with_precedents(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
        valid_precedent_ref: str,
    ) -> None:
        """Created bundle should include precedent refs."""
        meeting_id = uuid4()
        precedents = (valid_precedent_ref, f"{CONTENT_REF_PREFIX}{'d' * 64}")
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=precedents,
        )

        assert result.bundle.precedent_refs == precedents
        assert len(result.bundle.precedent_refs) == 2

    @pytest.mark.asyncio
    async def test_create_bundle_stores_bundle(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Created bundle should be stored in internal dict."""
        meeting_id = uuid4()
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert result.bundle.bundle_id in creator_stub._bundles
        assert creator_stub._bundles[result.bundle.bundle_id] == result.bundle

    @pytest.mark.asyncio
    async def test_create_bundle_generates_hash(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Created bundle should have valid hash."""
        meeting_id = uuid4()
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert len(result.bundle_hash) == 64
        assert result.bundle.bundle_hash == result.bundle_hash

    @pytest.mark.asyncio
    async def test_create_bundle_generates_signature(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Created bundle should have valid signature."""
        meeting_id = uuid4()
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert len(result.bundle.signature) == 64


# ============================================================================
# Bundle Verification Tests
# ============================================================================


class TestBundleVerification:
    """Tests for bundle verification."""

    @pytest.mark.asyncio
    async def test_verify_valid_bundle(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """verify_bundle should return valid for correctly signed bundle."""
        meeting_id = uuid4()
        create_result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        verify_result = await creator_stub.verify_bundle(create_result.bundle)

        assert verify_result.valid is True
        assert verify_result.error_message is None

    @pytest.mark.asyncio
    async def test_verify_bundle_returns_bundle_id(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """verify_bundle should return bundle_id."""
        meeting_id = uuid4()
        create_result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        verify_result = await creator_stub.verify_bundle(create_result.bundle)

        assert verify_result.bundle_id == create_result.bundle.bundle_id

    @pytest.mark.asyncio
    async def test_verify_bundle_returns_signing_key(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """verify_bundle should return signing_key_id."""
        meeting_id = uuid4()
        create_result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        verify_result = await creator_stub.verify_bundle(create_result.bundle)

        assert verify_result.signing_key_id == creator_stub._signing_key_id


# ============================================================================
# Bundle Retrieval Tests
# ============================================================================


class TestBundleRetrieval:
    """Tests for bundle retrieval."""

    @pytest.mark.asyncio
    async def test_get_bundle_returns_stored_bundle(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """get_bundle should return stored bundle."""
        meeting_id = uuid4()
        create_result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        retrieved = await creator_stub.get_bundle(create_result.bundle.bundle_id)

        assert retrieved == create_result.bundle

    @pytest.mark.asyncio
    async def test_get_bundle_returns_none_for_missing(
        self,
        creator_stub: ContextBundleCreatorStub,
    ) -> None:
        """get_bundle should return None for non-existent bundle."""
        retrieved = await creator_stub.get_bundle("ctx_nonexistent_1")

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_signing_key_id(
        self,
        creator_stub: ContextBundleCreatorStub,
    ) -> None:
        """get_signing_key_id should return current key."""
        key_id = await creator_stub.get_signing_key_id()

        assert key_id == creator_stub._signing_key_id
        assert DEV_MODE_WATERMARK in key_id


# ============================================================================
# Hash Determinism Tests
# ============================================================================


class TestHashDeterminism:
    """Tests for hash computation determinism."""

    @pytest.mark.asyncio
    async def test_same_inputs_produce_same_hash(
        self,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Same inputs should produce same hash."""
        stub1 = ContextBundleCreatorStub()
        stub2 = ContextBundleCreatorStub()

        data = {"key": "value", "num": 42}

        hash1 = await stub1._compute_hash(data)
        hash2 = await stub2._compute_hash(data)

        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_different_inputs_produce_different_hash(
        self,
        creator_stub: ContextBundleCreatorStub,
    ) -> None:
        """Different inputs should produce different hashes."""
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}

        hash1 = await creator_stub._compute_hash(data1)
        hash2 = await creator_stub._compute_hash(data2)

        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_hash_is_64_hex_characters(
        self,
        creator_stub: ContextBundleCreatorStub,
    ) -> None:
        """Hash should be 64 lowercase hex characters."""
        data = {"test": "data"}
        hash_value = await creator_stub._compute_hash(data)

        assert len(hash_value) == 64
        assert hash_value == hash_value.lower()
        int(hash_value, 16)  # Should not raise
