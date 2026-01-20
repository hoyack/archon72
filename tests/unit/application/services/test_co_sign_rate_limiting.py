"""Unit tests for rate limiting in CoSignSubmissionService (Story 5.4, FR-6.6, SYBIL-1).

Tests for the SYBIL-1 rate limiting integration in the co-sign submission service.

Constitutional Constraints Tested:
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer
- NFR-5.1: Rate limiting per identity: Configurable per type
- SYBIL-1: Identity verification + rate limiting per verified identity
- CT-11: Fail loud, not silent - return 429, never silently drop
- AC3: Rate limit checked AFTER identity verification
- AC4: Rate limit counter incremented AFTER successful persistence
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.co_sign_submission_service import CoSignSubmissionService
from src.domain.errors import CoSignRateLimitExceededError
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.infrastructure.stubs.co_sign_rate_limiter_stub import CoSignRateLimiterStub
from src.infrastructure.stubs.co_sign_repository_stub import CoSignRepositoryStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.identity_store_stub import IdentityStoreStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)


@pytest.fixture
def co_sign_repo() -> CoSignRepositoryStub:
    """Create fresh co-sign repository stub."""
    return CoSignRepositoryStub()


@pytest.fixture
def petition_repo() -> PetitionSubmissionRepositoryStub:
    """Create fresh petition repository stub."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create fresh halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def identity_store() -> IdentityStoreStub:
    """Create fresh identity store stub."""
    return IdentityStoreStub()


@pytest.fixture
def rate_limiter() -> CoSignRateLimiterStub:
    """Create fresh rate limiter stub."""
    return CoSignRateLimiterStub()


@pytest.fixture
def signer_id() -> uuid4:
    """Create a test signer UUID."""
    return uuid4()


@pytest.fixture
def petition_id(
    petition_repo: PetitionSubmissionRepositoryStub,
    co_sign_repo: CoSignRepositoryStub,
) -> uuid4:
    """Create a test petition and return its ID."""
    petition = PetitionSubmission(
        id=uuid4(),
        type=PetitionType.GENERAL,
        text="Test petition for rate limiting.",
        realm="test_realm",
        state=PetitionState.RECEIVED,
        content_hash=b"a" * 32,
        co_signer_count=0,
    )
    # Add to petition repository via internal dict (stub testing pattern)
    petition_repo._submissions[petition.id] = petition
    # Register as valid petition in co-sign repo (simulates FK constraint)
    co_sign_repo.add_valid_petition(petition.id)
    return petition.id


class TestRateLimitCheckOrder:
    """Tests for AC3: Rate limit checked AFTER identity verification."""

    async def test_rate_limit_checked_after_identity_verification(
        self,
        co_sign_repo: CoSignRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        rate_limiter: CoSignRateLimiterStub,
        petition_id: uuid4,
        signer_id: uuid4,
    ) -> None:
        """Rate limit check should happen after identity verification (AC3).

        If identity verification fails, rate limit should not be checked.
        """
        # Setup: Identity not found
        identity_store.remove_valid_identity(signer_id)

        # Setup: Rate limiter at limit (but should not be checked)
        rate_limiter.set_count(signer_id, 50)

        service = CoSignSubmissionService(
            co_sign_repo=co_sign_repo,
            petition_repo=petition_repo,
            halt_checker=halt_checker,
            identity_store=identity_store,
            rate_limiter=rate_limiter,
        )

        # Act & Assert: Should fail on identity, not rate limit
        with pytest.raises(Exception) as exc_info:
            await service.submit_co_sign(petition_id=petition_id, signer_id=signer_id)

        # Should be identity error, not rate limit error
        assert "IdentityNotFoundError" in str(type(exc_info.value).__name__)


class TestRateLimitExceeded:
    """Tests for rate limit exceeded behavior (AC1)."""

    async def test_rejects_when_at_limit(
        self,
        co_sign_repo: CoSignRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        rate_limiter: CoSignRateLimiterStub,
        petition_id: uuid4,
        signer_id: uuid4,
    ) -> None:
        """Should raise CoSignRateLimitExceededError when at limit (AC1)."""
        # Setup: Valid identity
        identity_store.add_valid_identity(signer_id)

        # Setup: Rate limiter at limit
        rate_limiter.set_count(signer_id, 50)

        service = CoSignSubmissionService(
            co_sign_repo=co_sign_repo,
            petition_repo=petition_repo,
            halt_checker=halt_checker,
            identity_store=identity_store,
            rate_limiter=rate_limiter,
        )

        # Act & Assert
        with pytest.raises(CoSignRateLimitExceededError) as exc_info:
            await service.submit_co_sign(petition_id=petition_id, signer_id=signer_id)

        error = exc_info.value
        assert error.signer_id == signer_id
        assert error.current_count == 50
        assert error.limit == 50
        assert error.retry_after_seconds > 0

    async def test_rejects_when_over_limit(
        self,
        co_sign_repo: CoSignRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        signer_id: uuid4,
        petition_id: uuid4,
    ) -> None:
        """Should raise CoSignRateLimitExceededError when over limit."""
        # Setup: Valid identity
        identity_store.add_valid_identity(signer_id)

        # Setup: Rate limiter over limit using factory
        rate_limiter = CoSignRateLimiterStub.over_limit(
            signer_id=signer_id,
            limit=50,
            current_count=55,
            reset_in_seconds=1800,
        )

        service = CoSignSubmissionService(
            co_sign_repo=co_sign_repo,
            petition_repo=petition_repo,
            halt_checker=halt_checker,
            identity_store=identity_store,
            rate_limiter=rate_limiter,
        )

        # Act & Assert
        with pytest.raises(CoSignRateLimitExceededError) as exc_info:
            await service.submit_co_sign(petition_id=petition_id, signer_id=signer_id)

        error = exc_info.value
        assert error.current_count == 55
        assert error.limit == 50


class TestRateLimitCounterIncrement:
    """Tests for AC4: Counter incremented AFTER successful persistence."""

    async def test_counter_incremented_after_success(
        self,
        co_sign_repo: CoSignRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        rate_limiter: CoSignRateLimiterStub,
        petition_id: uuid4,
        signer_id: uuid4,
    ) -> None:
        """Counter should be incremented after successful co-sign (AC4)."""
        # Setup: Valid identity
        identity_store.add_valid_identity(signer_id)

        # Setup: Under rate limit
        initial_count = rate_limiter.get_count(signer_id)
        assert initial_count == 0

        service = CoSignSubmissionService(
            co_sign_repo=co_sign_repo,
            petition_repo=petition_repo,
            halt_checker=halt_checker,
            identity_store=identity_store,
            rate_limiter=rate_limiter,
        )

        # Act
        await service.submit_co_sign(petition_id=petition_id, signer_id=signer_id)

        # Assert: Counter incremented
        new_count = rate_limiter.get_count(signer_id)
        assert new_count == 1

    async def test_counter_not_incremented_on_failure(
        self,
        co_sign_repo: CoSignRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        rate_limiter: CoSignRateLimiterStub,
        signer_id: uuid4,
    ) -> None:
        """Counter should NOT be incremented on failed co-sign (AC4)."""
        # Setup: Valid identity
        identity_store.add_valid_identity(signer_id)

        # Setup: Non-existent petition
        nonexistent_petition = uuid4()

        # Setup: Under rate limit
        initial_count = rate_limiter.get_count(signer_id)
        assert initial_count == 0

        service = CoSignSubmissionService(
            co_sign_repo=co_sign_repo,
            petition_repo=petition_repo,
            halt_checker=halt_checker,
            identity_store=identity_store,
            rate_limiter=rate_limiter,
        )

        # Act: Should fail (petition not found)
        with pytest.raises(Exception):
            await service.submit_co_sign(
                petition_id=nonexistent_petition, signer_id=signer_id
            )

        # Assert: Counter NOT incremented
        new_count = rate_limiter.get_count(signer_id)
        assert new_count == 0


class TestRateLimitInfoInResponse:
    """Tests for AC6: Rate limit info in success response."""

    async def test_rate_limit_info_in_success_response(
        self,
        co_sign_repo: CoSignRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        rate_limiter: CoSignRateLimiterStub,
        petition_id: uuid4,
        signer_id: uuid4,
    ) -> None:
        """Success response should include rate limit info (AC6)."""
        # Setup: Valid identity
        identity_store.add_valid_identity(signer_id)

        # Setup: Under rate limit with some usage
        rate_limiter.set_count(signer_id, 10)

        service = CoSignSubmissionService(
            co_sign_repo=co_sign_repo,
            petition_repo=petition_repo,
            halt_checker=halt_checker,
            identity_store=identity_store,
            rate_limiter=rate_limiter,
        )

        # Act
        result = await service.submit_co_sign(
            petition_id=petition_id, signer_id=signer_id
        )

        # Assert: Rate limit info in response
        # After increment: count is 11, so remaining is 50 - 11 = 39
        assert result.rate_limit_remaining == 39
        assert result.rate_limit_reset_at is not None
        assert result.rate_limit_reset_at > datetime.now(timezone.utc)


class TestBackwardsCompatibility:
    """Tests for backwards compatibility without rate limiter."""

    async def test_service_works_without_rate_limiter(
        self,
        co_sign_repo: CoSignRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
        identity_store: IdentityStoreStub,
        petition_id: uuid4,
        signer_id: uuid4,
    ) -> None:
        """Service should work without rate limiter for backwards compatibility."""
        # Setup: Valid identity
        identity_store.add_valid_identity(signer_id)

        # Create service WITHOUT rate limiter
        service = CoSignSubmissionService(
            co_sign_repo=co_sign_repo,
            petition_repo=petition_repo,
            halt_checker=halt_checker,
            identity_store=identity_store,
            rate_limiter=None,  # No rate limiter
        )

        # Act: Should succeed
        result = await service.submit_co_sign(
            petition_id=petition_id, signer_id=signer_id
        )

        # Assert: Success, but no rate limit info
        assert result.cosign_id is not None
        assert result.rate_limit_remaining is None
        assert result.rate_limit_reset_at is None

    async def test_service_works_without_identity_store_or_rate_limiter(
        self,
        co_sign_repo: CoSignRepositoryStub,
        petition_repo: PetitionSubmissionRepositoryStub,
        halt_checker: HaltCheckerStub,
        petition_id: uuid4,
        signer_id: uuid4,
    ) -> None:
        """Service should work without both identity store and rate limiter."""
        # Create service with minimal dependencies
        service = CoSignSubmissionService(
            co_sign_repo=co_sign_repo,
            petition_repo=petition_repo,
            halt_checker=halt_checker,
            identity_store=None,
            rate_limiter=None,
        )

        # Act: Should succeed
        result = await service.submit_co_sign(
            petition_id=petition_id, signer_id=signer_id
        )

        # Assert: Success
        assert result.cosign_id is not None
        assert result.identity_verified is False
        assert result.rate_limit_remaining is None
