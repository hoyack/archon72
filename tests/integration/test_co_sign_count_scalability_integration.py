"""Integration tests for co-sign counter scalability (Story 5.8).

Tests the counter column pattern for O(1) read performance at scale:
- AC2: Co-sign insertion increments counter atomically
- AC3: Counter column on petition_submissions table
- AC5: Counter equals actual count after N insertions

Uses the infrastructure stubs to validate counter semantics.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from blake3 import blake3

from src.domain.errors.co_sign import AlreadySignedError
from src.infrastructure.stubs.co_sign_repository_stub import CoSignRepositoryStub


@pytest.fixture
def co_sign_repo() -> CoSignRepositoryStub:
    """Create fresh CoSign repository stub."""
    return CoSignRepositoryStub()


class TestCounterIncrementSemantics:
    """Tests for atomic counter increment (AC2, FR-6.4)."""

    @pytest.mark.asyncio
    async def test_counter_increments_on_each_co_sign(
        self,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Test that co_signer_count increments by 1 on each co-sign.

        AC2: co_signer_count is atomically incremented.
        """
        petition_id = uuid4()
        co_sign_repo.add_valid_petition(petition_id)

        # Insert 10 co-signers and verify count at each step
        for i in range(10):
            signer_id = uuid4()
            cosign_id = uuid4()
            content_hash = blake3(f"content-{i}".encode()).digest()
            signed_at = datetime.now(tz=timezone.utc)

            new_count = await co_sign_repo.create(
                cosign_id=cosign_id,
                petition_id=petition_id,
                signer_id=signer_id,
                signed_at=signed_at,
                content_hash=content_hash,
            )

            assert new_count == i + 1, f"Expected {i + 1}, got {new_count}"

    @pytest.mark.asyncio
    async def test_counter_not_affected_by_duplicate_attempts(
        self,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Test that duplicate attempts don't increment counter.

        AC2: Counter only increments on successful co-sign.
        """
        petition_id = uuid4()
        co_sign_repo.add_valid_petition(petition_id)

        signer_id = uuid4()
        cosign_id = uuid4()
        content_hash = blake3(b"content").digest()
        signed_at = datetime.now(tz=timezone.utc)

        # First co-sign succeeds
        await co_sign_repo.create(
            cosign_id=cosign_id,
            petition_id=petition_id,
            signer_id=signer_id,
            signed_at=signed_at,
            content_hash=content_hash,
        )

        # Duplicate attempts should raise error, not increment counter
        for _ in range(5):
            with pytest.raises(AlreadySignedError):
                await co_sign_repo.create(
                    cosign_id=uuid4(),
                    petition_id=petition_id,
                    signer_id=signer_id,  # Same signer
                    signed_at=datetime.now(tz=timezone.utc),
                    content_hash=content_hash,
                )

        # Count should still be 1
        count = await co_sign_repo.get_count(petition_id)
        assert count == 1

    @pytest.mark.asyncio
    async def test_counter_returns_new_value_after_increment(
        self,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Test that create() returns the new counter value.

        AC2: RETURNING clause returns updated count.
        """
        petition_id = uuid4()
        co_sign_repo.add_valid_petition(petition_id)

        content_hash = blake3(b"test").digest()
        signed_at = datetime.now(tz=timezone.utc)

        # Insert and verify returned values
        for expected in [1, 2, 3, 4, 5]:
            result = await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=uuid4(),
                signed_at=signed_at,
                content_hash=content_hash,
            )
            assert result == expected


class TestCounterEqualsActualCount:
    """Tests for counter consistency (AC5)."""

    @pytest.mark.asyncio
    async def test_counter_equals_actual_count_after_insertions(
        self,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Test that counter value equals the actual co-sign count.

        AC5: Counter value equals SELECT COUNT(*) FROM co_signs.
        """
        petition_id = uuid4()
        co_sign_repo.add_valid_petition(petition_id)

        # Insert 100 co-signers
        for i in range(100):
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=uuid4(),
                signed_at=datetime.now(tz=timezone.utc),
                content_hash=blake3(f"content-{i}".encode()).digest(),
            )

        # Counter from get_count
        counter_value = await co_sign_repo.get_count(petition_id)

        # Actual count (stub stores all co-signs)
        actual_count = co_sign_repo.co_sign_count

        assert counter_value == 100
        assert counter_value == actual_count

    @pytest.mark.asyncio
    async def test_counter_zero_for_new_petition(
        self,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Test that new petition has counter value of 0.

        AC3: Counter is INTEGER NOT NULL DEFAULT 0.
        """
        petition_id = uuid4()
        co_sign_repo.add_valid_petition(petition_id)

        count = await co_sign_repo.get_count(petition_id)
        assert count == 0


class TestCounterPerformance:
    """Tests for counter performance characteristics."""

    @pytest.mark.asyncio
    async def test_get_count_is_constant_time(
        self,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Test that get_count() is O(1) regardless of co-signer count.

        AC1: Count query uses optimized path (not COUNT(*) scan).

        The stub simulates this with dict lookup.
        """
        import time

        petition_id = uuid4()
        co_sign_repo.add_valid_petition(petition_id)

        # Insert many co-signers
        for i in range(1000):
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_id,
                signer_id=uuid4(),
                signed_at=datetime.now(tz=timezone.utc),
                content_hash=blake3(f"content-{i}".encode()).digest(),
            )

        # Measure get_count latency
        times = []
        for _ in range(100):
            start = time.perf_counter()
            await co_sign_repo.get_count(petition_id)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time_ms = (sum(times) / len(times)) * 1000

        # Stub should be sub-millisecond (O(1) dict lookup)
        assert avg_time_ms < 1.0, f"Avg get_count time {avg_time_ms}ms > 1ms"


class TestMultiplePetitionsCounters:
    """Tests for multiple petitions with independent counters."""

    @pytest.mark.asyncio
    async def test_counters_are_independent_per_petition(
        self,
        co_sign_repo: CoSignRepositoryStub,
    ) -> None:
        """Test that each petition has its own independent counter."""
        petition_1 = uuid4()
        petition_2 = uuid4()
        petition_3 = uuid4()

        co_sign_repo.add_valid_petition(petition_1)
        co_sign_repo.add_valid_petition(petition_2)
        co_sign_repo.add_valid_petition(petition_3)

        content_hash = blake3(b"test").digest()
        signed_at = datetime.now(tz=timezone.utc)

        # Add different amounts to each petition
        for _ in range(5):
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_1,
                signer_id=uuid4(),
                signed_at=signed_at,
                content_hash=content_hash,
            )

        for _ in range(10):
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_2,
                signer_id=uuid4(),
                signed_at=signed_at,
                content_hash=content_hash,
            )

        for _ in range(3):
            await co_sign_repo.create(
                cosign_id=uuid4(),
                petition_id=petition_3,
                signer_id=uuid4(),
                signed_at=signed_at,
                content_hash=content_hash,
            )

        # Verify independent counts
        assert await co_sign_repo.get_count(petition_1) == 5
        assert await co_sign_repo.get_count(petition_2) == 10
        assert await co_sign_repo.get_count(petition_3) == 3
