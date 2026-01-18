"""Integration tests for Context Bundle (Story 2.9, ADR-2).

Tests cover ADR-2 compliance:
- Context bundle includes all required fields
- Bundle hash computed over canonical JSON
- Bundle signed with creator's key
- Signature verified before parsing content
- Invalid signature rejected with ADR-2 message
- Stale as_of_event_seq rejected
- HALT state blocks operations
- End-to-end bundle creation and validation flow

Constitutional Constraints:
- CT-1: LLMs are stateless -> Context bundles provide deterministic state
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Bundle hash creates audit trail
- CT-13: Integrity outranks availability -> Signature verification mandatory
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.context_bundle_service import (
    ContextBundleService,
    CreateBundleInput,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.context_bundle import (
    BUNDLE_ID_PREFIX,
    CONTENT_REF_LENGTH,
    CONTENT_REF_PREFIX,
    CONTEXT_BUNDLE_SCHEMA_VERSION,
    MAX_PRECEDENT_REFS,
    ContextBundlePayload,
)
from src.infrastructure.stubs.context_bundle_creator_stub import (
    ContextBundleCreatorStub,
)
from src.infrastructure.stubs.context_bundle_validator_stub import (
    ContextBundleValidatorStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub

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
def valid_precedent_refs() -> tuple[str, ...]:
    """Return valid precedent ContentRefs."""
    return (
        f"{CONTENT_REF_PREFIX}{'c' * 64}",
        f"{CONTENT_REF_PREFIX}{'d' * 64}",
    )


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Return a non-halted HaltCheckerStub."""
    return HaltCheckerStub(force_halted=False)


@pytest.fixture
def creator_stub() -> ContextBundleCreatorStub:
    """Return a fresh ContextBundleCreatorStub."""
    return ContextBundleCreatorStub()


@pytest.fixture
def validator_stub() -> ContextBundleValidatorStub:
    """Return a fresh ContextBundleValidatorStub."""
    return ContextBundleValidatorStub()


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Return a mock EventStorePort with sequence 100."""
    event_store = AsyncMock()
    event_store.get_max_sequence = AsyncMock(return_value=100)
    return event_store


@pytest.fixture
def context_bundle_service(
    halt_checker: HaltCheckerStub,
    creator_stub: ContextBundleCreatorStub,
    validator_stub: ContextBundleValidatorStub,
    mock_event_store: AsyncMock,
) -> ContextBundleService:
    """Return a ContextBundleService with stub implementations."""
    return ContextBundleService(
        halt_checker=halt_checker,
        creator=creator_stub,
        validator=validator_stub,
        event_store=mock_event_store,
    )


# ============================================================================
# AC1: Context Bundle Required Fields Tests
# ============================================================================


class TestContextBundleRequiredFields:
    """Tests for AC1: Context bundle includes all required fields."""

    @pytest.mark.asyncio
    async def test_bundle_includes_schema_version(
        self,
        context_bundle_service: ContextBundleService,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should include schema_version."""
        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        assert result.success is True
        assert result.bundle.schema_version == CONTEXT_BUNDLE_SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_bundle_includes_bundle_id(
        self,
        context_bundle_service: ContextBundleService,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should include bundle_id starting with ctx_."""
        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        assert result.success is True
        assert result.bundle.bundle_id.startswith(BUNDLE_ID_PREFIX)

    @pytest.mark.asyncio
    async def test_bundle_includes_meeting_id(
        self,
        context_bundle_service: ContextBundleService,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should include meeting_id."""
        meeting_id = uuid4()
        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=meeting_id,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        assert result.success is True
        assert result.bundle.meeting_id == meeting_id

    @pytest.mark.asyncio
    async def test_bundle_includes_as_of_event_seq(
        self,
        context_bundle_service: ContextBundleService,
        mock_event_store: AsyncMock,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should include as_of_event_seq anchored to specific event."""
        mock_event_store.get_max_sequence.return_value = 42

        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        assert result.success is True
        assert result.bundle.as_of_event_seq == 42

    @pytest.mark.asyncio
    async def test_bundle_includes_identity_prompt_ref(
        self,
        context_bundle_service: ContextBundleService,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should include identity_prompt_ref."""
        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        assert result.success is True
        assert result.bundle.identity_prompt_ref == valid_content_ref

    @pytest.mark.asyncio
    async def test_bundle_includes_meeting_state_ref(
        self,
        context_bundle_service: ContextBundleService,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should include meeting_state_ref."""
        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        assert result.success is True
        assert result.bundle.meeting_state_ref == valid_meeting_state_ref

    @pytest.mark.asyncio
    async def test_bundle_includes_precedent_refs(
        self,
        context_bundle_service: ContextBundleService,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
        valid_precedent_refs: tuple[str, ...],
    ) -> None:
        """Bundle should include precedent_refs[]."""
        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
                precedent_refs=valid_precedent_refs,
            )
        )

        assert result.success is True
        assert result.bundle.precedent_refs == valid_precedent_refs


# ============================================================================
# AC2: Context Bundle Signing and Hash Tests
# ============================================================================


class TestContextBundleSigningAndHash:
    """Tests for AC2: Bundle signing and hash computation."""

    @pytest.mark.asyncio
    async def test_bundle_hash_computed_over_canonical_json(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle hash should be computed over canonical JSON."""
        meeting_id = uuid4()
        result = await creator_stub.create_bundle(
            meeting_id=meeting_id,
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert result.success is True
        assert len(result.bundle_hash) == 64
        assert result.bundle.bundle_hash == result.bundle_hash

    @pytest.mark.asyncio
    async def test_bundle_signed_with_creator_key(
        self,
        creator_stub: ContextBundleCreatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should be signed with creator's key."""
        result = await creator_stub.create_bundle(
            meeting_id=uuid4(),
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        assert result.success is True
        assert len(result.bundle.signature) == 64
        assert result.bundle.signing_key_id is not None

    @pytest.mark.asyncio
    async def test_bundle_can_be_verified_after_creation(
        self,
        creator_stub: ContextBundleCreatorStub,
        validator_stub: ContextBundleValidatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Created bundle should pass signature verification."""
        create_result = await creator_stub.create_bundle(
            meeting_id=uuid4(),
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        validation_result = await validator_stub.validate_signature(
            create_result.bundle
        )

        assert validation_result.valid is True


# ============================================================================
# AC3: Context Bundle Validation Tests
# ============================================================================


class TestContextBundleValidation:
    """Tests for AC3: Bundle validation requirements."""

    @pytest.mark.asyncio
    async def test_signature_verified_before_parsing(
        self,
        validator_stub: ContextBundleValidatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Signature should be verified before parsing content (ADR-2)."""
        # Create a bundle with invalid signature
        meeting_id = uuid4()
        bundle = ContextBundlePayload(
            schema_version=CONTEXT_BUNDLE_SCHEMA_VERSION,
            meeting_id=meeting_id,
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
            created_at=datetime.now(timezone.utc),
            bundle_hash="a" * 64,  # Valid format but won't match
            signature="b" * 64,  # Invalid signature
            signing_key_id="TEST_KEY",
        )

        # validate_all runs signature first
        result = await validator_stub.validate_all(bundle, current_head_seq=100)

        assert result.valid is False
        # First error should be signature-related
        assert (
            "HASH_MISMATCH" in result.error_code
            or "INVALID_SIGNATURE" in result.error_code
        )

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected_with_adr2_message(
        self,
        creator_stub: ContextBundleCreatorStub,
        validator_stub: ContextBundleValidatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Invalid signature should be rejected with ADR-2 error message."""
        # Create valid bundle, then tamper with signature
        create_result = await creator_stub.create_bundle(
            meeting_id=uuid4(),
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        # Create tampered bundle
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
        assert "ADR-2" in result.error_message
        assert "Invalid context bundle signature" in result.error_message

    @pytest.mark.asyncio
    async def test_stale_as_of_event_seq_rejected(
        self,
        creator_stub: ContextBundleCreatorStub,
        validator_stub: ContextBundleValidatorStub,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle with stale/future as_of_event_seq should be rejected."""
        # Create bundle at sequence 200
        create_result = await creator_stub.create_bundle(
            meeting_id=uuid4(),
            as_of_event_seq=200,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        # Validate against current head of 100 (200 is future)
        result = await validator_stub.validate_freshness(
            create_result.bundle,
            current_head_seq=100,
        )

        assert result.fresh is False
        assert "future sequence" in result.error_message.lower()


# ============================================================================
# HALT State Tests
# ============================================================================


class TestHaltStateBlocking:
    """Tests for HALT state blocking operations."""

    @pytest.mark.asyncio
    async def test_halt_state_blocks_bundle_creation(
        self,
        creator_stub: ContextBundleCreatorStub,
        validator_stub: ContextBundleValidatorStub,
        mock_event_store: AsyncMock,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """HALT state should block bundle creation."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = ContextBundleService(
            halt_checker=halt_checker,
            creator=creator_stub,
            validator=validator_stub,
            event_store=mock_event_store,
        )

        with pytest.raises(SystemHaltedError, match="halted"):
            await service.create_bundle_for_meeting(
                CreateBundleInput(
                    meeting_id=uuid4(),
                    identity_prompt_ref=valid_content_ref,
                    meeting_state_ref=valid_meeting_state_ref,
                )
            )

    @pytest.mark.asyncio
    async def test_halt_state_blocks_bundle_validation(
        self,
        creator_stub: ContextBundleCreatorStub,
        validator_stub: ContextBundleValidatorStub,
        mock_event_store: AsyncMock,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """HALT state should block bundle validation."""
        # Create bundle first (before halt)
        create_result = await creator_stub.create_bundle(
            meeting_id=uuid4(),
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=tuple(),
        )

        # Now halt the system
        halt_checker = HaltCheckerStub(force_halted=True)
        service = ContextBundleService(
            halt_checker=halt_checker,
            creator=creator_stub,
            validator=validator_stub,
            event_store=mock_event_store,
        )

        with pytest.raises(SystemHaltedError, match="halted"):
            await service.validate_bundle(create_result.bundle)


# ============================================================================
# End-to-End Tests
# ============================================================================


class TestEndToEndBundleFlow:
    """Tests for end-to-end bundle creation and validation."""

    @pytest.mark.asyncio
    async def test_create_and_validate_bundle(
        self,
        context_bundle_service: ContextBundleService,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """End-to-end: Create bundle and validate it."""
        # Create bundle
        create_result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        assert create_result.success is True

        # Validate bundle
        validate_result = await context_bundle_service.validate_bundle(
            create_result.bundle
        )

        assert validate_result.valid is True

    @pytest.mark.asyncio
    async def test_create_bundle_with_precedents_and_validate(
        self,
        context_bundle_service: ContextBundleService,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
        valid_precedent_refs: tuple[str, ...],
    ) -> None:
        """End-to-end: Create bundle with precedents and validate."""
        # Create bundle with precedents
        create_result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
                precedent_refs=valid_precedent_refs,
            )
        )

        assert create_result.success is True
        assert len(create_result.bundle.precedent_refs) == 2

        # Validate bundle
        validate_result = await context_bundle_service.validate_bundle(
            create_result.bundle
        )

        assert validate_result.valid is True


# ============================================================================
# ContentRef Format Validation Tests
# ============================================================================


class TestContentRefFormat:
    """Tests for ContentRef format validation (ref:{sha256_hex})."""

    def test_content_ref_format_constants(self) -> None:
        """ContentRef format constants should be correct."""
        assert CONTENT_REF_PREFIX == "ref:"
        assert CONTENT_REF_LENGTH == 68  # 4 (prefix) + 64 (hex)

    def test_valid_content_ref_format(
        self,
        valid_content_ref: str,
    ) -> None:
        """Valid ContentRef should match format."""
        assert valid_content_ref.startswith(CONTENT_REF_PREFIX)
        assert len(valid_content_ref) == CONTENT_REF_LENGTH


# ============================================================================
# Precedent Refs Maximum Tests
# ============================================================================


class TestPrecedentRefsMaximum:
    """Tests for precedent_refs maximum of 10."""

    def test_max_precedent_refs_constant(self) -> None:
        """MAX_PRECEDENT_REFS should be 10."""
        assert MAX_PRECEDENT_REFS == 10

    def test_bundle_rejects_too_many_precedent_refs(
        self,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should reject more than 10 precedent refs."""
        # Create 11 precedent refs
        precedent_refs = tuple(
            f"{CONTENT_REF_PREFIX}{hex(i)[2:].zfill(64)}" for i in range(11)
        )

        with pytest.raises(ValueError, match="Maximum 10 precedent references allowed"):
            ContextBundlePayload(
                schema_version=CONTEXT_BUNDLE_SCHEMA_VERSION,
                meeting_id=uuid4(),
                as_of_event_seq=42,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
                precedent_refs=precedent_refs,
                created_at=datetime.now(timezone.utc),
                bundle_hash="a" * 64,
                signature="b" * 64,
                signing_key_id="TEST_KEY",
            )

    def test_bundle_accepts_max_precedent_refs(
        self,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """Bundle should accept exactly 10 precedent refs."""
        # Create exactly 10 precedent refs
        precedent_refs = tuple(
            f"{CONTENT_REF_PREFIX}{hex(i)[2:].zfill(64)}" for i in range(10)
        )

        bundle = ContextBundlePayload(
            schema_version=CONTEXT_BUNDLE_SCHEMA_VERSION,
            meeting_id=uuid4(),
            as_of_event_seq=42,
            identity_prompt_ref=valid_content_ref,
            meeting_state_ref=valid_meeting_state_ref,
            precedent_refs=precedent_refs,
            created_at=datetime.now(timezone.utc),
            bundle_hash="a" * 64,
            signature="b" * 64,
            signing_key_id="TEST_KEY",
        )

        assert len(bundle.precedent_refs) == MAX_PRECEDENT_REFS
