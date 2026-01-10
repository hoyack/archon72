"""Unit tests for ContextBundleValidatorStub (Story 2.9, ADR-2).

Tests cover:
- Signature validation (ADR-2: MUST be first)
- Schema validation
- Freshness validation
- Combined validate_all flow
- DEV_MODE_WATERMARK pattern

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Clear validation errors
- CT-13: Integrity outranks availability -> Validation before use
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern verification
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.context_bundle_validator import (
    ContextBundleValidatorPort,
)
from src.domain.models.context_bundle import (
    CONTENT_REF_PREFIX,
    CONTEXT_BUNDLE_SCHEMA_VERSION,
    ContextBundlePayload,
)
from src.infrastructure.stubs.context_bundle_creator_stub import (
    ContextBundleCreatorStub,
)
from src.infrastructure.stubs.context_bundle_validator_stub import (
    DEV_MODE_WATERMARK,
    ContextBundleValidatorStub,
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
def creator_stub() -> ContextBundleCreatorStub:
    """Return a fresh ContextBundleCreatorStub."""
    return ContextBundleCreatorStub()


@pytest.fixture
def validator_stub() -> ContextBundleValidatorStub:
    """Return a fresh ContextBundleValidatorStub."""
    return ContextBundleValidatorStub()


@pytest.fixture
async def valid_bundle(
    creator_stub: ContextBundleCreatorStub,
    valid_content_ref: str,
    valid_meeting_state_ref: str,
) -> ContextBundlePayload:
    """Create and return a valid bundle."""
    result = await creator_stub.create_bundle(
        meeting_id=uuid4(),
        as_of_event_seq=42,
        identity_prompt_ref=valid_content_ref,
        meeting_state_ref=valid_meeting_state_ref,
        precedent_refs=tuple(),
    )
    return result.bundle


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
        assert "ContextBundleValidatorStub" in DEV_MODE_WATERMARK
        assert "DEV_STUB" in DEV_MODE_WATERMARK


# ============================================================================
# Initialization Tests
# ============================================================================


class TestContextBundleValidatorStubInit:
    """Tests for stub initialization."""

    def test_stub_implements_port(self) -> None:
        """Stub should implement ContextBundleValidatorPort."""
        stub = ContextBundleValidatorStub()
        assert isinstance(stub, ContextBundleValidatorPort)

    def test_stub_with_default_key(
        self,
        validator_stub: ContextBundleValidatorStub,
    ) -> None:
        """Stub should have default expected signing key."""
        assert validator_stub._signing_key_id is not None

    def test_stub_with_custom_key(self) -> None:
        """Stub should use custom expected key when provided."""
        stub = ContextBundleValidatorStub(signing_key_id="CUSTOM_KEY:test:v1")
        assert stub._signing_key_id == "CUSTOM_KEY:test:v1"


# ============================================================================
# Signature Validation Tests (ADR-2: MUST be first)
# ============================================================================


class TestSignatureValidation:
    """Tests for signature validation (ADR-2 requirement)."""

    @pytest.mark.asyncio
    async def test_validate_signature_valid_bundle(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_signature should return valid for correctly signed bundle."""
        result = await validator_stub.validate_signature(valid_bundle)

        assert result.valid is True
        assert result.bundle_id == valid_bundle.bundle_id
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_validate_signature_returns_bundle_id(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_signature should return bundle_id."""
        result = await validator_stub.validate_signature(valid_bundle)

        assert result.bundle_id == valid_bundle.bundle_id

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_adr2_message(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Invalid signature should return ADR-2 error message."""
        # Create a bundle with tampered signature
        meeting_id = uuid4()
        bundle = ContextBundlePayload(
            schema_version=CONTEXT_BUNDLE_SCHEMA_VERSION,
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
            created_at=datetime.now(timezone.utc),
            bundle_hash="a" * 64,
            signature="tampered_signature_" + "x" * 45,  # Wrong signature
            signing_key_id="BUNDLE:DEV_STUB:ContextBundleCreatorStub:v1",
        )

        result = await validator_stub.validate_signature(bundle)

        assert result.valid is False
        assert "ADR-2" in result.error_message
        assert "Invalid context bundle signature" in result.error_message


# ============================================================================
# Schema Validation Tests
# ============================================================================


class TestSchemaValidation:
    """Tests for schema validation."""

    @pytest.mark.asyncio
    async def test_validate_schema_valid_bundle(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_schema should return valid for correct schema."""
        result = await validator_stub.validate_schema(valid_bundle)

        assert result.valid is True
        assert result.bundle_id == valid_bundle.bundle_id

    @pytest.mark.asyncio
    async def test_validate_schema_checks_version(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_schema should verify schema_version is 1.0."""
        # The valid_bundle fixture already has correct version
        result = await validator_stub.validate_schema(valid_bundle)

        assert result.valid is True
        assert valid_bundle.schema_version == "1.0"

    @pytest.mark.asyncio
    async def test_validate_schema_checks_content_refs(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_schema should verify ContentRef format."""
        result = await validator_stub.validate_schema(valid_bundle)

        assert result.valid is True
        # Verify refs have correct format
        assert valid_bundle.identity_prompt_ref.startswith(CONTENT_REF_PREFIX)
        assert valid_bundle.meeting_state_ref.startswith(CONTENT_REF_PREFIX)


# ============================================================================
# Freshness Validation Tests
# ============================================================================


class TestFreshnessValidation:
    """Tests for freshness validation (ADR-2 requirement)."""

    @pytest.mark.asyncio
    async def test_validate_freshness_valid_sequence(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_freshness should return fresh for valid sequence."""
        current_head_seq = 100  # Bundle is at seq 42

        result = await validator_stub.validate_freshness(valid_bundle, current_head_seq)

        assert result.fresh is True
        assert result.as_of_event_seq == valid_bundle.as_of_event_seq
        assert result.current_head_seq == current_head_seq

    @pytest.mark.asyncio
    async def test_validate_freshness_future_sequence_is_stale(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_freshness should reject future sequences."""
        current_head_seq = 10  # Bundle is at seq 42, which is future

        result = await validator_stub.validate_freshness(valid_bundle, current_head_seq)

        assert result.fresh is False
        assert "future sequence" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_freshness_at_head_is_valid(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_freshness should accept sequence at head."""
        current_head_seq = valid_bundle.as_of_event_seq  # Exactly at head

        result = await validator_stub.validate_freshness(valid_bundle, current_head_seq)

        assert result.fresh is True


# ============================================================================
# Combined Validation Tests
# ============================================================================


class TestValidateAll:
    """Tests for validate_all (combined validation)."""

    @pytest.mark.asyncio
    async def test_validate_all_valid_bundle(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_all should pass for valid bundle."""
        current_head_seq = 100

        result = await validator_stub.validate_all(valid_bundle, current_head_seq)

        assert result.valid is True
        assert result.bundle_id == valid_bundle.bundle_id

    @pytest.mark.asyncio
    async def test_validate_all_fails_on_invalid_signature(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """validate_all should fail fast on invalid signature (ADR-2)."""
        meeting_id = uuid4()
        bundle = ContextBundlePayload(
            schema_version=CONTEXT_BUNDLE_SCHEMA_VERSION,
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
            created_at=datetime.now(timezone.utc),
            bundle_hash="a" * 64,
            signature="tampered_" + "x" * 55,
            signing_key_id="BUNDLE:DEV_STUB:ContextBundleCreatorStub:v1",
        )

        result = await validator_stub.validate_all(bundle, current_head_seq=100)

        assert result.valid is False
        assert "ADR-2" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_all_fails_on_stale_bundle(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_all should fail for stale bundles."""
        current_head_seq = 10  # Bundle at 42 is future/invalid

        result = await validator_stub.validate_all(valid_bundle, current_head_seq)

        assert result.valid is False
        assert result.error_code == "STALE_BUNDLE"


# ============================================================================
# ContentRef Validation Tests
# ============================================================================


class TestContentRefValidation:
    """Tests for ContentRef format validation."""

    def test_valid_content_ref_accepted(
        self,
        validator_stub: ContextBundleValidatorStub,
    ) -> None:
        """Valid ContentRef should be accepted."""
        ref = f"{CONTENT_REF_PREFIX}{'a' * 64}"
        assert validator_stub._is_valid_content_ref(ref) is True

    def test_invalid_prefix_rejected(
        self,
        validator_stub: ContextBundleValidatorStub,
    ) -> None:
        """ContentRef without 'ref:' prefix should be rejected."""
        ref = "xxx:" + "a" * 64
        assert validator_stub._is_valid_content_ref(ref) is False

    def test_wrong_length_rejected(
        self,
        validator_stub: ContextBundleValidatorStub,
    ) -> None:
        """ContentRef with wrong length should be rejected."""
        ref = f"{CONTENT_REF_PREFIX}{'a' * 32}"  # Too short
        assert validator_stub._is_valid_content_ref(ref) is False

    def test_uppercase_hex_rejected(
        self,
        validator_stub: ContextBundleValidatorStub,
    ) -> None:
        """ContentRef with uppercase hex should be rejected."""
        ref = f"{CONTENT_REF_PREFIX}{'A' * 64}"  # Uppercase
        assert validator_stub._is_valid_content_ref(ref) is False

    def test_non_hex_rejected(
        self,
        validator_stub: ContextBundleValidatorStub,
    ) -> None:
        """ContentRef with non-hex characters should be rejected."""
        ref = f"{CONTENT_REF_PREFIX}{'g' * 64}"  # g is not hex
        assert validator_stub._is_valid_content_ref(ref) is False


# ============================================================================
# Error Result Tests (CT-11: Clear validation errors)
# ============================================================================


class TestErrorResults:
    """Tests for clear error results (CT-11)."""

    @pytest.mark.asyncio
    async def test_hash_mismatch_error_code(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Hash mismatch should return HASH_MISMATCH error code."""
        meeting_id = uuid4()
        # Use valid hex hash that doesn't match computed hash
        bundle = ContextBundlePayload(
            schema_version=CONTEXT_BUNDLE_SCHEMA_VERSION,
            meeting_id=meeting_id,
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
            created_at=datetime.now(timezone.utc),
            bundle_hash="f" * 64,  # Valid hex but won't match computed hash
            signature="a" * 64,
            signing_key_id="BUNDLE:DEV_STUB:ContextBundleCreatorStub:v1",
        )

        result = await validator_stub.validate_signature(bundle)

        assert result.valid is False
        assert result.error_code == "HASH_MISMATCH"

    @pytest.mark.asyncio
    async def test_invalid_signature_error_code(
        self,
        validator_stub: ContextBundleValidatorStub,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Invalid signature should return INVALID_SIGNATURE error code."""
        # Create valid bundle, then tamper with signature
        create_result = await creator_stub.create_bundle(
            meeting_id=uuid4(),
            as_of_event_seq=1,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        # Create tampered bundle with same hash but different signature
        tampered = ContextBundlePayload(
            schema_version=create_result.bundle.schema_version,
            meeting_id=create_result.bundle.meeting_id,
            as_of_event_seq=create_result.bundle.as_of_event_seq,
            identity_prompt_ref=create_result.bundle.identity_prompt_ref,
            meeting_state_ref=create_result.bundle.meeting_state_ref,
            precedent_refs=create_result.bundle.precedent_refs,
            created_at=create_result.bundle.created_at,
            bundle_hash=create_result.bundle.bundle_hash,
            signature="tampered_" + "x" * 55,  # Tampered signature
            signing_key_id=create_result.bundle.signing_key_id,
        )

        result = await validator_stub.validate_signature(tampered)

        assert result.valid is False
        assert result.error_code == "INVALID_SIGNATURE"
