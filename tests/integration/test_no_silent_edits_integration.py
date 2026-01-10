"""Integration tests for No Silent Edits constraint (Story 2.5, FR13).

Tests the complete FR13 enforcement flow across domain, application,
and infrastructure layers.

Constitutional Constraints Verified:
- FR13: Published hash must equal canonical hash
- AC1: Hash equality on publish
- AC2: Silent edit detection and block
- AC3: Verification endpoint returns TRUE/FALSE with hash values
"""

import hashlib
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.content_verification import ContentVerificationResult
from src.application.services.publish_service import PublishService
from src.domain.errors.silent_edit import FR13ViolationError
from src.domain.errors.writer import SystemHaltedError
from src.domain.services.silent_edit_enforcer import SilentEditEnforcer
from src.infrastructure.stubs.content_verification_stub import ContentVerificationStub


class TestFR13PublishFlow:
    """Integration tests for FR13 publish flow (AC1, AC2)."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock HaltChecker (not halted)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def verification_stub(self) -> ContentVerificationStub:
        """Create ContentVerificationStub."""
        return ContentVerificationStub()

    @pytest.fixture
    def publish_service(
        self,
        mock_halt_checker: AsyncMock,
        verification_stub: ContentVerificationStub,
    ) -> PublishService:
        """Create PublishService with stub."""
        return PublishService(
            halt_checker=mock_halt_checker,
            verification_port=verification_stub,
        )

    @pytest.mark.asyncio
    async def test_publish_with_matching_hash_succeeds_ac1(
        self,
        publish_service: PublishService,
        verification_stub: ContentVerificationStub,
    ) -> None:
        """AC1: Publishing content with matching hash succeeds."""
        content_id = uuid4()
        content = b"original content for publishing"
        content_hash = hashlib.sha256(content).hexdigest()

        # Register original hash
        await verification_stub.register_content_hash(content_id, content_hash)

        # Publish should succeed
        result = await publish_service.publish_content(content_id, content)

        assert result is True

    @pytest.mark.asyncio
    async def test_publish_with_mismatched_hash_blocked_ac2(
        self,
        publish_service: PublishService,
        verification_stub: ContentVerificationStub,
    ) -> None:
        """AC2: Publishing content with mismatched hash is blocked."""
        content_id = uuid4()
        original_content = b"original content"
        modified_content = b"modified content - silent edit attempt"
        original_hash = hashlib.sha256(original_content).hexdigest()

        # Register original hash
        await verification_stub.register_content_hash(content_id, original_hash)

        # Try to publish modified content
        with pytest.raises(FR13ViolationError) as exc_info:
            await publish_service.publish_content(content_id, modified_content)

        assert "FR13" in str(exc_info.value)
        assert "Silent edit detected" in str(exc_info.value)
        assert "hash mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fr13_error_includes_correct_message_ac2(
        self,
        publish_service: PublishService,
        verification_stub: ContentVerificationStub,
    ) -> None:
        """AC2: Error includes 'FR13: Silent edit detected - hash mismatch'."""
        content_id = uuid4()
        original_hash = "a" * 64

        await verification_stub.register_content_hash(content_id, original_hash)

        with pytest.raises(FR13ViolationError) as exc_info:
            await publish_service.publish_content(content_id, b"different content")

        error_msg = str(exc_info.value)
        assert "FR13: Silent edit detected - hash mismatch" in error_msg


class TestFR13VerificationEndpoint:
    """Integration tests for FR13 verification endpoint (AC3)."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock HaltChecker (not halted)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def verification_stub(self) -> ContentVerificationStub:
        """Create ContentVerificationStub."""
        return ContentVerificationStub()

    @pytest.fixture
    def publish_service(
        self,
        mock_halt_checker: AsyncMock,
        verification_stub: ContentVerificationStub,
    ) -> PublishService:
        """Create PublishService with stub."""
        return PublishService(
            halt_checker=mock_halt_checker,
            verification_port=verification_stub,
        )

    @pytest.mark.asyncio
    async def test_verify_content_returns_true_for_match_ac3(
        self,
        publish_service: PublishService,
        verification_stub: ContentVerificationStub,
    ) -> None:
        """AC3: verify_content returns TRUE for matching hashes."""
        content_id = uuid4()
        content = b"content to verify"
        content_hash = hashlib.sha256(content).hexdigest()

        await verification_stub.register_content_hash(content_id, content_hash)

        result = await publish_service.verify_content(content_id, content)

        assert result.matches is True

    @pytest.mark.asyncio
    async def test_verify_content_returns_false_for_mismatch_ac3(
        self,
        publish_service: PublishService,
        verification_stub: ContentVerificationStub,
    ) -> None:
        """AC3: verify_content returns FALSE for mismatched hashes."""
        content_id = uuid4()
        original_hash = "b" * 64
        different_content = b"different content"

        await verification_stub.register_content_hash(content_id, original_hash)

        result = await publish_service.verify_content(content_id, different_content)

        assert result.matches is False

    @pytest.mark.asyncio
    async def test_verify_content_includes_hash_values_ac3(
        self,
        publish_service: PublishService,
        verification_stub: ContentVerificationStub,
    ) -> None:
        """AC3: Verification result includes both hash values."""
        content_id = uuid4()
        content = b"test content"
        stored_hash = hashlib.sha256(content).hexdigest()

        await verification_stub.register_content_hash(content_id, stored_hash)

        result = await publish_service.verify_content(content_id, content)

        assert isinstance(result, ContentVerificationResult)
        assert result.stored_hash == stored_hash
        assert result.computed_hash == stored_hash
        assert result.content_id == content_id


class TestFR13HaltBehavior:
    """Integration tests for FR13 with halt state."""

    @pytest.fixture
    def halted_checker(self) -> AsyncMock:
        """Create mock HaltChecker (halted)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=True)
        return checker

    @pytest.fixture
    def verification_stub(self) -> ContentVerificationStub:
        """Create ContentVerificationStub."""
        return ContentVerificationStub()

    @pytest.fixture
    def halted_service(
        self,
        halted_checker: AsyncMock,
        verification_stub: ContentVerificationStub,
    ) -> PublishService:
        """Create PublishService with halted state."""
        return PublishService(
            halt_checker=halted_checker,
            verification_port=verification_stub,
        )

    @pytest.mark.asyncio
    async def test_halt_blocks_publish_operations(
        self,
        halted_service: PublishService,
    ) -> None:
        """HALT state blocks publish operations."""
        with pytest.raises(SystemHaltedError):
            await halted_service.publish_content(uuid4(), b"content")


class TestFR13EndToEndFlow:
    """End-to-end integration tests for FR13."""

    @pytest.fixture
    def mock_halt_checker(self) -> AsyncMock:
        """Create mock HaltChecker (not halted)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def verification_stub(self) -> ContentVerificationStub:
        """Create ContentVerificationStub."""
        return ContentVerificationStub()

    @pytest.fixture
    def domain_enforcer(self) -> SilentEditEnforcer:
        """Create SilentEditEnforcer."""
        return SilentEditEnforcer()

    @pytest.mark.asyncio
    async def test_end_to_end_publish_flow_enforces_fr13(
        self,
        mock_halt_checker: AsyncMock,
        verification_stub: ContentVerificationStub,
        domain_enforcer: SilentEditEnforcer,
    ) -> None:
        """End-to-end: Complete publish flow enforces FR13."""
        content_id = uuid4()
        original_content = b"original constitutional content"
        original_hash = hashlib.sha256(original_content).hexdigest()

        # Step 1: Content is stored and hash is registered
        await verification_stub.register_content_hash(content_id, original_hash)
        domain_enforcer.register_hash(content_id, original_hash)

        # Step 2: Create publish service
        service = PublishService(
            halt_checker=mock_halt_checker,
            verification_port=verification_stub,
        )

        # Step 3: Legitimate publish succeeds
        result = await service.publish_content(content_id, original_content)
        assert result is True

        # Step 4: Silent edit is blocked
        modified_content = b"tampered content"
        with pytest.raises(FR13ViolationError):
            await service.publish_content(content_id, modified_content)

        # Step 5: Domain enforcer also catches the mismatch
        modified_hash = hashlib.sha256(modified_content).hexdigest()
        with pytest.raises(FR13ViolationError):
            domain_enforcer.verify_before_publish(content_id, modified_hash)

    @pytest.mark.asyncio
    async def test_domain_and_stub_hash_verification_consistent(
        self,
        verification_stub: ContentVerificationStub,
        domain_enforcer: SilentEditEnforcer,
    ) -> None:
        """Domain enforcer and stub produce consistent results."""
        content_id = uuid4()
        content = b"test content"
        content_hash = hashlib.sha256(content).hexdigest()

        # Register in both
        await verification_stub.register_content_hash(content_id, content_hash)
        domain_enforcer.register_hash(content_id, content_hash)

        # Both should pass for correct hash
        stub_result = await verification_stub.verify_content(content_id, content)
        domain_result = domain_enforcer.verify_hash(content_id, content_hash)

        assert stub_result.matches is True
        assert domain_result is True

        # Both should fail for wrong hash
        wrong_hash = "x" * 64
        wrong_content = b"wrong content"

        stub_result = await verification_stub.verify_content(content_id, wrong_content)
        assert stub_result.matches is False

        with pytest.raises(FR13ViolationError):
            domain_enforcer.verify_before_publish(content_id, wrong_hash)
