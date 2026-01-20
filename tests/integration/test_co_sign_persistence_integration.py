"""Integration tests for CoSign persistence (Story 5.1).

Tests the database-level constraints and persistence behavior:
- FR-6.2: Unique constraint on (petition_id, signer_id)
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-6.4: Full signer list queryable
- CT-12: Content hash integrity

These tests use in-memory stubs to verify the logical behavior
that would be enforced by the database schema.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.co_sign import CoSign


class CoSignRepositoryStub:
    """In-memory CoSign repository stub for testing.

    Implements the logical behavior of the co_signs table including
    the unique constraint on (petition_id, signer_id).
    """

    def __init__(self) -> None:
        self._co_signs: dict[str, CoSign] = {}  # keyed by cosign_id
        self._unique_pairs: set[tuple[str, str]] = set()  # (petition_id, signer_id)

    async def save(self, co_sign: CoSign) -> None:
        """Save a co-sign, enforcing unique constraint.

        Args:
            co_sign: The co-sign to save.

        Raises:
            IntegrityError: If (petition_id, signer_id) already exists (FR-6.2).
        """
        pair = (str(co_sign.petition_id), str(co_sign.signer_id))
        if pair in self._unique_pairs:
            raise IntegrityError(
                f"Duplicate key violation: (petition_id={co_sign.petition_id}, "
                f"signer_id={co_sign.signer_id}) already exists"
            )

        self._unique_pairs.add(pair)
        self._co_signs[str(co_sign.cosign_id)] = co_sign

    async def get_by_id(self, cosign_id: str) -> CoSign | None:
        """Get co-sign by ID."""
        return self._co_signs.get(cosign_id)

    async def get_by_petition_id(self, petition_id: str) -> list[CoSign]:
        """Get all co-signs for a petition (NFR-6.4)."""
        return [
            cs
            for cs in self._co_signs.values()
            if str(cs.petition_id) == petition_id
        ]

    async def count_by_petition_id(self, petition_id: str) -> int:
        """Count co-signs for a petition (FR-6.4, FR-6.5)."""
        return len(await self.get_by_petition_id(petition_id))

    async def get_by_signer_id(self, signer_id: str) -> list[CoSign]:
        """Get all co-signs by a signer (for SYBIL-1 rate limiting)."""
        return [
            cs
            for cs in self._co_signs.values()
            if str(cs.signer_id) == signer_id
        ]

    async def count_by_signer_since(
        self, signer_id: str, since: datetime
    ) -> int:
        """Count co-signs by signer since a timestamp (FR-6.6 rate limiting)."""
        return len(
            [
                cs
                for cs in self._co_signs.values()
                if str(cs.signer_id) == signer_id and cs.signed_at >= since
            ]
        )

    async def exists(self, petition_id: str, signer_id: str) -> bool:
        """Check if a co-sign exists for this pair."""
        return (petition_id, signer_id) in self._unique_pairs

    def clear(self) -> None:
        """Clear all co-signs."""
        self._co_signs.clear()
        self._unique_pairs.clear()


class IntegrityError(Exception):
    """Database integrity constraint violation."""

    pass


@pytest.fixture
def co_sign_repo() -> CoSignRepositoryStub:
    """Create fresh co-sign repository stub."""
    return CoSignRepositoryStub()


def _make_co_sign(
    petition_id: str | None = None,
    signer_id: str | None = None,
    cosign_id: str | None = None,
) -> CoSign:
    """Helper to create a valid CoSign for testing."""
    if petition_id is None:
        petition_id = str(uuid4())
    if signer_id is None:
        signer_id = str(uuid4())
    if cosign_id is None:
        cosign_id = str(uuid4())

    from uuid import UUID

    petition_uuid = UUID(petition_id)
    signer_uuid = UUID(signer_id)
    cosign_uuid = UUID(cosign_id)
    signed_at = datetime.now(timezone.utc)
    content_hash = CoSign.compute_content_hash(petition_uuid, signer_uuid, signed_at)

    return CoSign(
        cosign_id=cosign_uuid,
        petition_id=petition_uuid,
        signer_id=signer_uuid,
        signed_at=signed_at,
        content_hash=content_hash,
    )


class TestCoSignUniqueConstraint:
    """Tests for unique constraint on (petition_id, signer_id) - FR-6.2, NFR-3.5."""

    @pytest.mark.asyncio
    async def test_insert_valid_co_sign_succeeds(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that inserting a valid co-sign succeeds."""
        co_sign = _make_co_sign()

        await co_sign_repo.save(co_sign)

        retrieved = await co_sign_repo.get_by_id(str(co_sign.cosign_id))
        assert retrieved is not None
        assert retrieved.cosign_id == co_sign.cosign_id

    @pytest.mark.asyncio
    async def test_duplicate_petition_signer_raises_integrity_error(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that duplicate (petition_id, signer_id) raises IntegrityError (FR-6.2)."""
        petition_id = str(uuid4())
        signer_id = str(uuid4())

        # First co-sign succeeds
        co_sign_1 = _make_co_sign(petition_id=petition_id, signer_id=signer_id)
        await co_sign_repo.save(co_sign_1)

        # Second co-sign with same petition_id and signer_id fails
        co_sign_2 = _make_co_sign(petition_id=petition_id, signer_id=signer_id)

        with pytest.raises(IntegrityError, match="Duplicate key violation"):
            await co_sign_repo.save(co_sign_2)

    @pytest.mark.asyncio
    async def test_same_signer_different_petitions_allowed(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that a signer can co-sign multiple different petitions."""
        signer_id = str(uuid4())

        # Co-sign petition 1
        co_sign_1 = _make_co_sign(signer_id=signer_id)
        await co_sign_repo.save(co_sign_1)

        # Co-sign petition 2 (different petition)
        co_sign_2 = _make_co_sign(signer_id=signer_id)
        await co_sign_repo.save(co_sign_2)

        # Both should exist
        signer_co_signs = await co_sign_repo.get_by_signer_id(signer_id)
        assert len(signer_co_signs) == 2

    @pytest.mark.asyncio
    async def test_same_petition_different_signers_allowed(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that multiple signers can co-sign the same petition."""
        petition_id = str(uuid4())

        # Signer 1 co-signs
        co_sign_1 = _make_co_sign(petition_id=petition_id)
        await co_sign_repo.save(co_sign_1)

        # Signer 2 co-signs (different signer)
        co_sign_2 = _make_co_sign(petition_id=petition_id)
        await co_sign_repo.save(co_sign_2)

        # Both should exist
        petition_co_signs = await co_sign_repo.get_by_petition_id(petition_id)
        assert len(petition_co_signs) == 2

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing_pair(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test exists() returns True for existing (petition_id, signer_id)."""
        petition_id = str(uuid4())
        signer_id = str(uuid4())

        co_sign = _make_co_sign(petition_id=petition_id, signer_id=signer_id)
        await co_sign_repo.save(co_sign)

        assert await co_sign_repo.exists(petition_id, signer_id) is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_non_existing_pair(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test exists() returns False for non-existing pair."""
        petition_id = str(uuid4())
        signer_id = str(uuid4())

        assert await co_sign_repo.exists(petition_id, signer_id) is False


class TestCoSignQueryOperations:
    """Tests for query operations - NFR-6.4 (full signer list queryable)."""

    @pytest.mark.asyncio
    async def test_count_by_petition_id_with_no_co_signs(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test counting co-signs for a petition with no co-signs."""
        petition_id = str(uuid4())
        count = await co_sign_repo.count_by_petition_id(petition_id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_by_petition_id_with_multiple_co_signs(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test counting co-signs for a petition with multiple co-signs."""
        petition_id = str(uuid4())

        # Add 5 co-signs
        for _ in range(5):
            co_sign = _make_co_sign(petition_id=petition_id)
            await co_sign_repo.save(co_sign)

        count = await co_sign_repo.count_by_petition_id(petition_id)
        assert count == 5

    @pytest.mark.asyncio
    async def test_get_by_petition_id_returns_all_co_signs(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test getting all co-signs for a petition (NFR-6.4)."""
        petition_id = str(uuid4())
        expected_ids = set()

        # Add 3 co-signs
        for _ in range(3):
            co_sign = _make_co_sign(petition_id=petition_id)
            await co_sign_repo.save(co_sign)
            expected_ids.add(str(co_sign.cosign_id))

        co_signs = await co_sign_repo.get_by_petition_id(petition_id)
        actual_ids = {str(cs.cosign_id) for cs in co_signs}

        assert actual_ids == expected_ids

    @pytest.mark.asyncio
    async def test_get_by_signer_id_returns_all_co_signs(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test getting all co-signs by a signer."""
        signer_id = str(uuid4())
        expected_ids = set()

        # Add 4 co-signs by the same signer
        for _ in range(4):
            co_sign = _make_co_sign(signer_id=signer_id)
            await co_sign_repo.save(co_sign)
            expected_ids.add(str(co_sign.cosign_id))

        co_signs = await co_sign_repo.get_by_signer_id(signer_id)
        actual_ids = {str(cs.cosign_id) for cs in co_signs}

        assert actual_ids == expected_ids


class TestCoSignRateLimiting:
    """Tests for rate limiting queries (FR-6.6 SYBIL-1)."""

    @pytest.mark.asyncio
    async def test_count_by_signer_since_filters_by_time(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test counting co-signs by signer since a timestamp."""
        from datetime import timedelta

        signer_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Create a co-sign with timestamp in the past
        from uuid import UUID

        signer_uuid = UUID(signer_id)
        petition_uuid_1 = uuid4()
        old_time = now - timedelta(hours=2)
        content_hash_1 = CoSign.compute_content_hash(
            petition_uuid_1, signer_uuid, old_time
        )
        old_co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_uuid_1,
            signer_id=signer_uuid,
            signed_at=old_time,
            content_hash=content_hash_1,
        )
        await co_sign_repo.save(old_co_sign)

        # Create a co-sign with timestamp now
        petition_uuid_2 = uuid4()
        content_hash_2 = CoSign.compute_content_hash(petition_uuid_2, signer_uuid, now)
        new_co_sign = CoSign(
            cosign_id=uuid4(),
            petition_id=petition_uuid_2,
            signer_id=signer_uuid,
            signed_at=now,
            content_hash=content_hash_2,
        )
        await co_sign_repo.save(new_co_sign)

        # Count since 1 hour ago - should only get the new one
        since = now - timedelta(hours=1)
        count = await co_sign_repo.count_by_signer_since(signer_id, since)
        assert count == 1

        # Count since 3 hours ago - should get both
        since_longer = now - timedelta(hours=3)
        count_longer = await co_sign_repo.count_by_signer_since(signer_id, since_longer)
        assert count_longer == 2


class TestCoSignContentHashIntegrity:
    """Tests for content hash integrity (CT-12)."""

    @pytest.mark.asyncio
    async def test_saved_co_sign_has_valid_hash(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that saved co-sign maintains hash integrity."""
        co_sign = _make_co_sign()
        await co_sign_repo.save(co_sign)

        retrieved = await co_sign_repo.get_by_id(str(co_sign.cosign_id))
        assert retrieved is not None
        assert retrieved.verify_content_hash() is True

    @pytest.mark.asyncio
    async def test_all_co_signs_for_petition_have_valid_hashes(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that all co-signs for a petition have valid hashes (CT-12)."""
        petition_id = str(uuid4())

        # Add 5 co-signs
        for _ in range(5):
            co_sign = _make_co_sign(petition_id=petition_id)
            await co_sign_repo.save(co_sign)

        co_signs = await co_sign_repo.get_by_petition_id(petition_id)

        for cs in co_signs:
            assert cs.verify_content_hash() is True, f"Hash invalid for {cs.cosign_id}"


class TestCoSignVolumeOperations:
    """Tests for high-volume operations (scalability)."""

    @pytest.mark.asyncio
    async def test_count_query_with_1000_co_signers(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test count query with 1000 co-signers (scalability test)."""
        import time

        petition_id = str(uuid4())

        # Add 1000 co-signs
        for _ in range(1000):
            co_sign = _make_co_sign(petition_id=petition_id)
            await co_sign_repo.save(co_sign)

        # Time the count query
        start = time.perf_counter()
        count = await co_sign_repo.count_by_petition_id(petition_id)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert count == 1000
        # In-memory should be fast; real DB would use index
        # Just verify it completes in reasonable time
        assert elapsed_ms < 1000, f"Count query took {elapsed_ms}ms, expected < 1000ms"

    @pytest.mark.asyncio
    async def test_no_duplicates_with_rapid_insertions(
        self, co_sign_repo: CoSignRepositoryStub
    ) -> None:
        """Test that unique constraint prevents duplicates under rapid insertion."""
        petition_id = str(uuid4())
        signer_id = str(uuid4())

        # First insert succeeds
        co_sign_1 = _make_co_sign(petition_id=petition_id, signer_id=signer_id)
        await co_sign_repo.save(co_sign_1)

        # Rapid duplicate attempts all fail
        duplicate_count = 0
        for _ in range(10):
            try:
                co_sign_dup = _make_co_sign(petition_id=petition_id, signer_id=signer_id)
                await co_sign_repo.save(co_sign_dup)
            except IntegrityError:
                duplicate_count += 1

        # All 10 should have been rejected
        assert duplicate_count == 10

        # Only 1 co-sign should exist (NFR-3.5: 0 duplicates)
        count = await co_sign_repo.count_by_petition_id(petition_id)
        assert count == 1
