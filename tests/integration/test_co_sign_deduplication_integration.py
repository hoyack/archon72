"""Integration tests for CoSign Deduplication (Story 5.7).

Tests the deduplication enforcement across the full co-sign flow:
- Sequential duplicate requests (second fails)
- Concurrent duplicate requests (race condition handling)
- Count accuracy after duplicate attempts
- HTTP 409 response format with existing signature details

Constitutional Constraints:
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- NFR-3.5: 0 duplicate signatures ever exist
- D7: RFC 7807 error responses with governance extensions
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.co_sign import AlreadySignedError
from src.domain.models.co_sign import CoSign
from src.infrastructure.stubs.co_sign_repository_stub import (
    CoSignRepositoryStub,
    StoredCoSign,
)


@pytest.fixture
def co_sign_repo() -> CoSignRepositoryStub:
    """Create fresh co-sign repository stub."""
    return CoSignRepositoryStub()


def _make_content_hash(petition_id, signer_id, signed_at) -> bytes:
    """Helper to create content hash for testing."""
    return CoSign.compute_content_hash(petition_id, signer_id, signed_at)


class TestSequentialDuplicateRequests:
    """Tests for sequential duplicate co-sign requests (AC1)."""

    @pytest.mark.asyncio
    async def test_first_co_sign_succeeds(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that first co-sign request succeeds."""
        petition_id = uuid4()
        signer_id = uuid4()
        cosign_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, signed_at)

        count = await co_sign_repo.create(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        assert count == 1
        assert await co_sign_repo.exists(petition_id, signer_id) is True

    @pytest.mark.asyncio
    async def test_second_co_sign_fails_with_409(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that second co-sign request fails with AlreadySignedError (AC1)."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, signed_at)

        # First request succeeds
        await co_sign_repo.create(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        # Second request fails
        with pytest.raises(AlreadySignedError) as exc_info:
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=datetime.now(timezone.utc),
                content_hash=_make_content_hash(
                    petition_id, signer_id, datetime.now(timezone.utc)
                ),
            )

        error = exc_info.value
        assert error.petition_id == petition_id
        assert error.signer_id == signer_id

    @pytest.mark.asyncio
    async def test_error_includes_existing_signature_details(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that error includes existing signature details (AC3, Story 5.7)."""
        petition_id = uuid4()
        signer_id = uuid4()
        first_cosign_id = uuid4()
        first_signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, first_signed_at)

        # First request
        await co_sign_repo.create(
            cosign_id=first_cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=first_signed_at,
            content_hash=content_hash,
        )

        # Second request - error should include existing signature details
        with pytest.raises(AlreadySignedError) as exc_info:
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=datetime.now(timezone.utc),
                content_hash=_make_content_hash(
                    petition_id, signer_id, datetime.now(timezone.utc)
                ),
            )

        error = exc_info.value
        assert error.existing_cosign_id == first_cosign_id
        assert error.signed_at == first_signed_at

    @pytest.mark.asyncio
    async def test_count_remains_one_after_duplicate_attempt(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that co-signer count remains 1 after duplicate attempt (AC1)."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, signed_at)

        # First request succeeds
        await co_sign_repo.create(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        # Attempt duplicate (should fail)
        try:
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=datetime.now(timezone.utc),
                content_hash=_make_content_hash(
                    petition_id, signer_id, datetime.now(timezone.utc)
                ),
            )
        except AlreadySignedError:
            pass

        # Count should still be 1 (NFR-3.5)
        count = await co_sign_repo.get_count(petition_id)
        assert count == 1


class TestConcurrentDuplicateRequests:
    """Tests for concurrent duplicate co-sign requests (AC2)."""

    @pytest.mark.asyncio
    async def test_concurrent_duplicates_exactly_one_succeeds(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that with concurrent duplicates, exactly one succeeds (AC2).

        Note: This is a logical test using the stub. The real database
        constraint handles actual concurrent race conditions.
        """
        petition_id = uuid4()
        signer_id = uuid4()
        co_sign_repo.add_valid_petition(petition_id)

        success_count = 0
        failure_count = 0

        async def attempt_co_sign(attempt_num: int) -> None:
            nonlocal success_count, failure_count
            try:
                signed_at = datetime.now(timezone.utc)
                await co_sign_repo.create(
                    cosign_id=uuid4(),
                    petition_id=petition_id,
                    signer_id=signer_id,
                    signed_at=signed_at,
                    content_hash=_make_content_hash(petition_id, signer_id, signed_at),
                )
                success_count += 1
            except AlreadySignedError:
                failure_count += 1

        # Run 5 concurrent attempts
        await asyncio.gather(*[attempt_co_sign(i) for i in range(5)])

        # Exactly one should succeed, others should fail
        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert failure_count == 4, f"Expected 4 failures, got {failure_count}"

    @pytest.mark.asyncio
    async def test_no_partial_state_after_concurrent_failure(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that no partial state exists after constraint violation (AC2)."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, signed_at)

        # First insert
        await co_sign_repo.create(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        # Failed duplicate attempts should not leave partial state
        for _ in range(3):
            try:
                await co_sign_repo.create(
                    cosign_id=uuid4(),
                    petition_id=petition_id,
                    signer_id=signer_id,
                    signed_at=datetime.now(timezone.utc),
                    content_hash=_make_content_hash(
                        petition_id, signer_id, datetime.now(timezone.utc)
                    ),
                )
            except AlreadySignedError:
                pass

        # Verify only 1 co-sign exists (no orphaned records)
        assert co_sign_repo.co_sign_count == 1
        assert await co_sign_repo.get_count(petition_id) == 1


class TestRFC7807ErrorFormat:
    """Tests for RFC 7807 error response format (AC3)."""

    @pytest.mark.asyncio
    async def test_error_has_required_rfc7807_fields(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that error response includes required RFC 7807 fields."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, signed_at)

        await co_sign_repo.create(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        with pytest.raises(AlreadySignedError) as exc_info:
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=datetime.now(timezone.utc),
                content_hash=_make_content_hash(
                    petition_id, signer_id, datetime.now(timezone.utc)
                ),
            )

        error = exc_info.value
        rfc7807 = error.to_rfc7807_dict()

        # Required RFC 7807 fields
        assert rfc7807["type"] == "https://archon72.ai/errors/co-sign/already-signed"
        assert rfc7807["title"] == "Already Signed"
        assert rfc7807["status"] == 409
        assert "detail" in rfc7807
        assert str(signer_id) in rfc7807["detail"]

        # Governance extensions
        assert rfc7807["petition_id"] == str(petition_id)
        assert rfc7807["signer_id"] == str(signer_id)

    @pytest.mark.asyncio
    async def test_error_includes_existing_signature_in_rfc7807(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that RFC 7807 includes existing signature details (Story 5.7)."""
        petition_id = uuid4()
        signer_id = uuid4()
        first_cosign_id = uuid4()
        first_signed_at = datetime(2026, 1, 20, 10, 30, 0, tzinfo=timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, first_signed_at)

        await co_sign_repo.create(
            cosign_id=first_cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=first_signed_at,
            content_hash=content_hash,
        )

        with pytest.raises(AlreadySignedError) as exc_info:
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=datetime.now(timezone.utc),
                content_hash=_make_content_hash(
                    petition_id, signer_id, datetime.now(timezone.utc)
                ),
            )

        error = exc_info.value
        rfc7807 = error.to_rfc7807_dict()

        assert rfc7807["existing_cosign_id"] == str(first_cosign_id)
        assert rfc7807["signed_at"] == "2026-01-20T10:30:00+00:00"


class TestPrePersistenceCheck:
    """Tests for pre-persistence check optimization (AC4)."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing_pair(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test exists() check before persistence."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, signed_at)

        # Initially doesn't exist
        assert await co_sign_repo.exists(petition_id, signer_id) is False

        # After creation, exists
        await co_sign_repo.create(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )
        assert await co_sign_repo.exists(petition_id, signer_id) is True

    @pytest.mark.asyncio
    async def test_get_existing_returns_signature_details(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test get_existing() returns signature details for service layer."""
        petition_id = uuid4()
        signer_id = uuid4()
        cosign_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, signed_at)

        # Initially None
        result = await co_sign_repo.get_existing(petition_id, signer_id)
        assert result is None

        # After creation, returns details
        await co_sign_repo.create(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        result = await co_sign_repo.get_existing(petition_id, signer_id)
        assert result is not None
        existing_id, existing_signed_at = result
        assert existing_id == cosign_id
        assert existing_signed_at == signed_at


class TestZeroDuplicatesInvariant:
    """Tests for NFR-3.5: 0 duplicate signatures ever exist."""

    @pytest.mark.asyncio
    async def test_rapid_duplicate_attempts_all_fail(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that rapid duplicate attempts all fail except first."""
        petition_id = uuid4()
        signer_id = uuid4()
        signed_at = datetime.now(timezone.utc)

        co_sign_repo.add_valid_petition(petition_id)
        content_hash = _make_content_hash(petition_id, signer_id, signed_at)

        # First succeeds
        await co_sign_repo.create(
            cosign_id=uuid4(),
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        # 100 rapid duplicate attempts all fail
        failures = 0
        for _ in range(100):
            try:
                await co_sign_repo.create(
                    cosign_id=uuid4(),
                    petition_id=petition_id,
                    signer_id=signer_id,
                    signed_at=datetime.now(timezone.utc),
                    content_hash=_make_content_hash(
                        petition_id, signer_id, datetime.now(timezone.utc)
                    ),
                )
            except AlreadySignedError:
                failures += 1

        assert failures == 100
        assert await co_sign_repo.get_count(petition_id) == 1

    @pytest.mark.asyncio
    async def test_different_signers_allowed(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that different signers can co-sign same petition."""
        petition_id = uuid4()
        co_sign_repo.add_valid_petition(petition_id)

        # 10 different signers
        for i in range(10):
            signer_id = uuid4()
            signed_at = datetime.now(timezone.utc)
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=signed_at,
                content_hash=_make_content_hash(petition_id, signer_id, signed_at),
            )

        assert await co_sign_repo.get_count(petition_id) == 10

    @pytest.mark.asyncio
    async def test_same_signer_different_petitions_allowed(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that same signer can co-sign different petitions."""
        signer_id = uuid4()

        # 10 different petitions
        for i in range(10):
            petition_id = uuid4()
            co_sign_repo.add_valid_petition(petition_id)
            signed_at = datetime.now(timezone.utc)
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=signed_at,
                content_hash=_make_content_hash(petition_id, signer_id, signed_at),
            )

        # All succeeded
        assert co_sign_repo.co_sign_count == 10
