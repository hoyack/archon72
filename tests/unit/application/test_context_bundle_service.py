"""Unit tests for ContextBundleService (Story 2.9, ADR-2).

Tests cover:
- Service initialization
- Bundle creation with HALT FIRST
- Bundle validation with HALT FIRST
- Head sequence retrieval
- MA-3 temporal determinism pattern

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

from src.application.ports.context_bundle_creator import (
    BundleCreationResult,
)
from src.application.ports.context_bundle_validator import (
    BundleValidationResult,
)
from src.application.services.context_bundle_service import (
    ContextBundleService,
    CreateBundleInput,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.context_bundle import (
    CONTENT_REF_PREFIX,
    CONTEXT_BUNDLE_SCHEMA_VERSION,
    ContextBundlePayload,
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
def mock_halt_checker() -> HaltCheckerStub:
    """Return a non-halted HaltCheckerStub."""
    return HaltCheckerStub(force_halted=False)


@pytest.fixture
def halted_halt_checker() -> HaltCheckerStub:
    """Return a halted HaltCheckerStub."""
    return HaltCheckerStub(force_halted=True)


@pytest.fixture
def mock_creator() -> AsyncMock:
    """Return a mock ContextBundleCreatorPort."""
    creator = AsyncMock()
    return creator


@pytest.fixture
def mock_validator() -> AsyncMock:
    """Return a mock ContextBundleValidatorPort."""
    validator = AsyncMock()
    return validator


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Return a mock EventStorePort."""
    event_store = AsyncMock()
    event_store.get_max_sequence = AsyncMock(return_value=42)
    return event_store


@pytest.fixture
def context_bundle_service(
    mock_halt_checker: HaltCheckerStub,
    mock_creator: AsyncMock,
    mock_validator: AsyncMock,
    mock_event_store: AsyncMock,
) -> ContextBundleService:
    """Return a ContextBundleService with mock dependencies."""
    return ContextBundleService(
        halt_checker=mock_halt_checker,
        creator=mock_creator,
        validator=mock_validator,
        event_store=mock_event_store,
    )


@pytest.fixture
def valid_bundle(
    valid_content_ref: str,
    valid_meeting_state_ref: str,
) -> ContextBundlePayload:
    """Return a valid ContextBundlePayload."""
    meeting_id = uuid4()
    return ContextBundlePayload(
        schema_version=CONTEXT_BUNDLE_SCHEMA_VERSION,
        meeting_id=meeting_id,
        as_of_event_seq=42,
        identity_prompt_ref=valid_content_ref,
        meeting_state_ref=valid_meeting_state_ref,
        precedent_refs=tuple(),
        created_at=datetime.now(timezone.utc),
        bundle_hash="a" * 64,
        signature="b" * 64,
        signing_key_id="TEST_KEY",
    )


# ============================================================================
# Initialization Tests
# ============================================================================


class TestContextBundleServiceInit:
    """Tests for service initialization."""

    def test_service_initializes_with_dependencies(
        self,
        mock_halt_checker: HaltCheckerStub,
        mock_creator: AsyncMock,
        mock_validator: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Service should initialize with required dependencies."""
        service = ContextBundleService(
            halt_checker=mock_halt_checker,
            creator=mock_creator,
            validator=mock_validator,
            event_store=mock_event_store,
        )
        assert service._halt_checker is mock_halt_checker
        assert service._creator is mock_creator
        assert service._validator is mock_validator
        assert service._event_store is mock_event_store

    def test_service_requires_halt_checker(
        self,
        mock_creator: AsyncMock,
        mock_validator: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Service should require halt_checker."""
        with pytest.raises(TypeError, match="halt_checker is required"):
            ContextBundleService(
                halt_checker=None,
                creator=mock_creator,
                validator=mock_validator,
                event_store=mock_event_store,
            )

    def test_service_requires_creator(
        self,
        mock_halt_checker: HaltCheckerStub,
        mock_validator: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Service should require creator."""
        with pytest.raises(TypeError, match="creator is required"):
            ContextBundleService(
                halt_checker=mock_halt_checker,
                creator=None,
                validator=mock_validator,
                event_store=mock_event_store,
            )

    def test_service_requires_validator(
        self,
        mock_halt_checker: HaltCheckerStub,
        mock_creator: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Service should require validator."""
        with pytest.raises(TypeError, match="validator is required"):
            ContextBundleService(
                halt_checker=mock_halt_checker,
                creator=mock_creator,
                validator=None,
                event_store=mock_event_store,
            )

    def test_service_requires_event_store(
        self,
        mock_halt_checker: HaltCheckerStub,
        mock_creator: AsyncMock,
        mock_validator: AsyncMock,
    ) -> None:
        """Service should require event_store."""
        with pytest.raises(TypeError, match="event_store is required"):
            ContextBundleService(
                halt_checker=mock_halt_checker,
                creator=mock_creator,
                validator=mock_validator,
                event_store=None,
            )


# ============================================================================
# Bundle Creation Tests
# ============================================================================


class TestBundleCreation:
    """Tests for bundle creation."""

    @pytest.mark.asyncio
    async def test_create_bundle_success(
        self,
        context_bundle_service: ContextBundleService,
        mock_creator: AsyncMock,
        valid_bundle: ContextBundlePayload,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """create_bundle_for_meeting should succeed with valid input."""
        # Setup
        mock_creator.create_bundle.return_value = BundleCreationResult(
            success=True,
            bundle=valid_bundle,
            bundle_hash="a" * 64,
        )

        # Execute
        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=valid_bundle.meeting_id,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        # Assert
        assert result.success is True
        assert result.bundle == valid_bundle
        assert result.bundle_hash == "a" * 64

    @pytest.mark.asyncio
    async def test_create_bundle_uses_current_head_seq(
        self,
        context_bundle_service: ContextBundleService,
        mock_creator: AsyncMock,
        mock_event_store: AsyncMock,
        valid_bundle: ContextBundlePayload,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """create_bundle_for_meeting should use current head sequence (MA-3)."""
        # Setup
        mock_event_store.get_max_sequence.return_value = 100
        mock_creator.create_bundle.return_value = BundleCreationResult(
            success=True,
            bundle=valid_bundle,
            bundle_hash="a" * 64,
        )

        # Execute
        await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=valid_bundle.meeting_id,
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        # Assert - verify as_of_event_seq was passed correctly
        mock_creator.create_bundle.assert_called_once()
        call_kwargs = mock_creator.create_bundle.call_args.kwargs
        assert call_kwargs["as_of_event_seq"] == 100

    @pytest.mark.asyncio
    async def test_create_bundle_returns_error_on_failure(
        self,
        context_bundle_service: ContextBundleService,
        mock_creator: AsyncMock,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """create_bundle_for_meeting should return error on failure."""
        # Setup
        mock_creator.create_bundle.return_value = BundleCreationResult(
            success=False,
            bundle=None,
            bundle_hash=None,
            error_message="Creation failed",
        )

        # Execute
        result = await context_bundle_service.create_bundle_for_meeting(
            CreateBundleInput(
                meeting_id=uuid4(),
                identity_prompt_ref=valid_content_ref,
                meeting_state_ref=valid_meeting_state_ref,
            )
        )

        # Assert
        assert result.success is False
        assert result.error_message == "Creation failed"


# ============================================================================
# HALT FIRST Tests
# ============================================================================


class TestHaltFirst:
    """Tests for HALT FIRST pattern."""

    @pytest.mark.asyncio
    async def test_create_bundle_halts_when_system_halted(
        self,
        halted_halt_checker: HaltCheckerStub,
        mock_creator: AsyncMock,
        mock_validator: AsyncMock,
        mock_event_store: AsyncMock,
        valid_content_ref: str,
        valid_meeting_state_ref: str,
    ) -> None:
        """create_bundle_for_meeting should halt when system is halted."""
        service = ContextBundleService(
            halt_checker=halted_halt_checker,
            creator=mock_creator,
            validator=mock_validator,
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

        # Creator should not be called
        mock_creator.create_bundle.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_bundle_halts_when_system_halted(
        self,
        halted_halt_checker: HaltCheckerStub,
        mock_creator: AsyncMock,
        mock_validator: AsyncMock,
        mock_event_store: AsyncMock,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_bundle should halt when system is halted."""
        service = ContextBundleService(
            halt_checker=halted_halt_checker,
            creator=mock_creator,
            validator=mock_validator,
            event_store=mock_event_store,
        )

        with pytest.raises(SystemHaltedError, match="halted"):
            await service.validate_bundle(valid_bundle)

        # Validator should not be called
        mock_validator.validate_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_current_head_seq_halts_when_system_halted(
        self,
        halted_halt_checker: HaltCheckerStub,
        mock_creator: AsyncMock,
        mock_validator: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """get_current_head_seq should halt when system is halted."""
        service = ContextBundleService(
            halt_checker=halted_halt_checker,
            creator=mock_creator,
            validator=mock_validator,
            event_store=mock_event_store,
        )

        with pytest.raises(SystemHaltedError, match="halted"):
            await service.get_current_head_seq()

    @pytest.mark.asyncio
    async def test_verify_bundle_signature_halts_when_system_halted(
        self,
        halted_halt_checker: HaltCheckerStub,
        mock_creator: AsyncMock,
        mock_validator: AsyncMock,
        mock_event_store: AsyncMock,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """verify_bundle_signature should halt when system is halted."""
        service = ContextBundleService(
            halt_checker=halted_halt_checker,
            creator=mock_creator,
            validator=mock_validator,
            event_store=mock_event_store,
        )

        with pytest.raises(SystemHaltedError, match="halted"):
            await service.verify_bundle_signature(valid_bundle)


# ============================================================================
# Bundle Validation Tests
# ============================================================================


class TestBundleValidation:
    """Tests for bundle validation."""

    @pytest.mark.asyncio
    async def test_validate_bundle_success(
        self,
        context_bundle_service: ContextBundleService,
        mock_validator: AsyncMock,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_bundle should succeed with valid bundle."""
        # Setup
        mock_validator.validate_all.return_value = BundleValidationResult(
            valid=True,
            bundle_id=valid_bundle.bundle_id,
        )

        # Execute
        result = await context_bundle_service.validate_bundle(valid_bundle)

        # Assert
        assert result.valid is True
        assert result.bundle_id == valid_bundle.bundle_id

    @pytest.mark.asyncio
    async def test_validate_bundle_returns_error(
        self,
        context_bundle_service: ContextBundleService,
        mock_validator: AsyncMock,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_bundle should return error details on failure."""
        # Setup
        mock_validator.validate_all.return_value = BundleValidationResult(
            valid=False,
            bundle_id=valid_bundle.bundle_id,
            error_code="INVALID_SIGNATURE",
            error_message="ADR-2: Invalid context bundle signature",
        )

        # Execute
        result = await context_bundle_service.validate_bundle(valid_bundle)

        # Assert
        assert result.valid is False
        assert result.error_code == "INVALID_SIGNATURE"
        assert "ADR-2" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_bundle_passes_current_head_seq(
        self,
        context_bundle_service: ContextBundleService,
        mock_validator: AsyncMock,
        mock_event_store: AsyncMock,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """validate_bundle should pass current head sequence for freshness check."""
        # Setup
        mock_event_store.get_max_sequence.return_value = 100
        mock_validator.validate_all.return_value = BundleValidationResult(
            valid=True,
            bundle_id=valid_bundle.bundle_id,
        )

        # Execute
        await context_bundle_service.validate_bundle(valid_bundle)

        # Assert - verify current_head_seq was passed
        mock_validator.validate_all.assert_called_once()
        call_kwargs = mock_validator.validate_all.call_args.kwargs
        assert call_kwargs["current_head_seq"] == 100


# ============================================================================
# Head Sequence Tests
# ============================================================================


class TestHeadSequence:
    """Tests for head sequence retrieval."""

    @pytest.mark.asyncio
    async def test_get_current_head_seq(
        self,
        context_bundle_service: ContextBundleService,
        mock_event_store: AsyncMock,
    ) -> None:
        """get_current_head_seq should return current max sequence."""
        mock_event_store.get_max_sequence.return_value = 42

        result = await context_bundle_service.get_current_head_seq()

        assert result == 42

    @pytest.mark.asyncio
    async def test_get_current_head_seq_returns_1_for_empty_store(
        self,
        context_bundle_service: ContextBundleService,
        mock_event_store: AsyncMock,
    ) -> None:
        """get_current_head_seq should return 1 for empty store."""
        mock_event_store.get_max_sequence.return_value = 0

        result = await context_bundle_service.get_current_head_seq()

        assert result == 1


# ============================================================================
# Bundle Retrieval Tests
# ============================================================================


class TestBundleRetrieval:
    """Tests for bundle retrieval."""

    @pytest.mark.asyncio
    async def test_get_bundle_returns_stored_bundle(
        self,
        context_bundle_service: ContextBundleService,
        mock_creator: AsyncMock,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """get_bundle should return stored bundle."""
        mock_creator.get_bundle.return_value = valid_bundle

        result = await context_bundle_service.get_bundle(valid_bundle.bundle_id)

        assert result == valid_bundle

    @pytest.mark.asyncio
    async def test_get_bundle_returns_none_for_missing(
        self,
        context_bundle_service: ContextBundleService,
        mock_creator: AsyncMock,
    ) -> None:
        """get_bundle should return None for missing bundle."""
        mock_creator.get_bundle.return_value = None

        result = await context_bundle_service.get_bundle("ctx_nonexistent_1")

        assert result is None


# ============================================================================
# Signature Verification Tests
# ============================================================================


class TestSignatureVerification:
    """Tests for signature verification."""

    @pytest.mark.asyncio
    async def test_verify_bundle_signature_returns_true_for_valid(
        self,
        context_bundle_service: ContextBundleService,
        mock_validator: AsyncMock,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """verify_bundle_signature should return True for valid signature."""
        mock_validator.validate_signature.return_value = BundleValidationResult(
            valid=True,
            bundle_id=valid_bundle.bundle_id,
        )

        result = await context_bundle_service.verify_bundle_signature(valid_bundle)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_bundle_signature_returns_false_for_invalid(
        self,
        context_bundle_service: ContextBundleService,
        mock_validator: AsyncMock,
        valid_bundle: ContextBundlePayload,
    ) -> None:
        """verify_bundle_signature should return False for invalid signature."""
        mock_validator.validate_signature.return_value = BundleValidationResult(
            valid=False,
            bundle_id=valid_bundle.bundle_id,
            error_code="INVALID_SIGNATURE",
            error_message="ADR-2: Invalid context bundle signature",
        )

        result = await context_bundle_service.verify_bundle_signature(valid_bundle)

        assert result is False
