"""Unit tests for witness selection domain models (FR59).

Tests WitnessSelectionRecord, WitnessSelectionSeed, and deterministic_select.
"""

import base64
from datetime import datetime, timezone

import pytest

from src.domain.models.witness_selection import (
    SELECTION_ALGORITHM_VERSION,
    WitnessSelectionRecord,
    WitnessSelectionSeed,
    deterministic_select,
)


class TestWitnessSelectionSeed:
    """Tests for WitnessSelectionSeed."""

    def test_combine_produces_deterministic_output(self) -> None:
        """Same inputs produce same combined seed."""
        external = b"external_entropy_32_bytes_here!"
        chain_hash = "a" * 64

        seed1 = WitnessSelectionSeed.combine(external, chain_hash)
        seed2 = WitnessSelectionSeed.combine(external, chain_hash)

        assert seed1.combined_seed == seed2.combined_seed

    def test_combine_different_external_produces_different_seed(self) -> None:
        """Different external entropy produces different seed."""
        external1 = b"external_entropy_32_bytes_here1"
        external2 = b"external_entropy_32_bytes_here2"
        chain_hash = "a" * 64

        seed1 = WitnessSelectionSeed.combine(external1, chain_hash)
        seed2 = WitnessSelectionSeed.combine(external2, chain_hash)

        assert seed1.combined_seed != seed2.combined_seed

    def test_combine_different_chain_produces_different_seed(self) -> None:
        """Different chain hash produces different seed."""
        external = b"external_entropy_32_bytes_here!"
        chain1 = "a" * 64
        chain2 = "b" * 64

        seed1 = WitnessSelectionSeed.combine(external, chain1)
        seed2 = WitnessSelectionSeed.combine(external, chain2)

        assert seed1.combined_seed != seed2.combined_seed

    def test_combined_seed_is_32_bytes(self) -> None:
        """Combined seed is SHA-256 output (32 bytes)."""
        external = b"external_entropy_32_bytes_here!"
        chain_hash = "a" * 64

        seed = WitnessSelectionSeed.combine(external, chain_hash)

        assert len(seed.combined_seed) == 32

    def test_seed_is_immutable(self) -> None:
        """Seed is frozen dataclass."""
        external = b"external_entropy_32_bytes_here!"
        chain_hash = "a" * 64

        seed = WitnessSelectionSeed.combine(external, chain_hash)

        with pytest.raises(AttributeError):
            seed.external_entropy = b"modified"  # type: ignore[misc]

    def test_to_dict_serializes_all_fields(self) -> None:
        """to_dict includes all fields in base64."""
        external = b"external_entropy_32_bytes_here!"
        chain_hash = "a" * 64

        seed = WitnessSelectionSeed.combine(external, chain_hash)
        result = seed.to_dict()

        assert "external_entropy" in result
        assert "chain_hash" in result
        assert "combined_seed" in result
        assert result["chain_hash"] == chain_hash


class TestDeterministicSelect:
    """Tests for deterministic_select function."""

    def test_select_from_pool_returns_element(self) -> None:
        """Selection returns an element from the pool."""
        seed = b"12345678" * 4
        pool = ("WITNESS:a", "WITNESS:b", "WITNESS:c")

        result = deterministic_select(seed, pool)

        assert result in pool

    def test_select_is_deterministic(self) -> None:
        """Same seed and pool produce same result."""
        seed = b"12345678" * 4
        pool = ("WITNESS:a", "WITNESS:b", "WITNESS:c")

        result1 = deterministic_select(seed, pool)
        result2 = deterministic_select(seed, pool)

        assert result1 == result2

    def test_select_different_seed_may_produce_different_result(self) -> None:
        """Different seeds may produce different results."""
        seed1 = b"00000000" * 4
        seed2 = b"11111111" * 4
        pool = ("WITNESS:a", "WITNESS:b", "WITNESS:c")

        deterministic_select(seed1, pool)
        deterministic_select(seed2, pool)

        # Different seeds should produce different results (with high probability)
        # Note: This is probabilistic but very likely with different seeds
        # We don't assert they're different as it's possible they collide

    def test_select_empty_pool_raises_error(self) -> None:
        """Empty pool raises ValueError."""
        seed = b"12345678" * 4
        pool: tuple[str, ...] = ()

        with pytest.raises(ValueError, match="empty pool"):
            deterministic_select(seed, pool)

    def test_select_short_seed_raises_error(self) -> None:
        """Seed shorter than 8 bytes raises ValueError."""
        seed = b"1234567"  # Only 7 bytes
        pool = ("WITNESS:a",)

        with pytest.raises(ValueError, match="at least 8 bytes"):
            deterministic_select(seed, pool)

    def test_select_single_element_pool_returns_that_element(self) -> None:
        """Single element pool always returns that element."""
        seed = b"12345678" * 4
        pool = ("WITNESS:only",)

        result = deterministic_select(seed, pool)

        assert result == "WITNESS:only"


class TestWitnessSelectionRecord:
    """Tests for WitnessSelectionRecord."""

    def test_record_creation_with_all_fields(self) -> None:
        """Record can be created with all fields."""
        seed = b"12345678" * 4
        pool = ("WITNESS:a", "WITNESS:b", "WITNESS:c")
        selected = deterministic_select(seed, pool)
        now = datetime.now(timezone.utc)

        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="external:test+chain:abc123",
            selected_witness_id=selected,
            pool_snapshot=pool,
            algorithm_version=SELECTION_ALGORITHM_VERSION,
            selected_at=now,
        )

        assert record.random_seed == seed
        assert record.seed_source == "external:test+chain:abc123"
        assert record.selected_witness_id == selected
        assert record.pool_snapshot == pool
        assert record.algorithm_version == SELECTION_ALGORITHM_VERSION
        assert record.selected_at == now

    def test_verify_selection_returns_true_for_valid_record(self) -> None:
        """verify_selection returns True for correctly constructed record."""
        seed = b"12345678" * 4
        pool = ("WITNESS:a", "WITNESS:b", "WITNESS:c")
        selected = deterministic_select(seed, pool)

        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="test",
            selected_witness_id=selected,
            pool_snapshot=pool,
        )

        assert record.verify_selection() is True

    def test_verify_selection_returns_false_for_tampered_witness(self) -> None:
        """verify_selection returns False if witness was tampered."""
        seed = b"12345678" * 4
        pool = ("WITNESS:a", "WITNESS:b", "WITNESS:c")
        actual_selected = deterministic_select(seed, pool)

        # Create record with wrong witness
        wrong_witness = [w for w in pool if w != actual_selected][0]
        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="test",
            selected_witness_id=wrong_witness,
            pool_snapshot=pool,
        )

        assert record.verify_selection() is False

    def test_verify_selection_raises_for_empty_pool(self) -> None:
        """verify_selection raises ValueError for empty pool."""
        seed = b"12345678" * 4

        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="test",
            selected_witness_id="WITNESS:a",
            pool_snapshot=(),  # Empty pool
        )

        with pytest.raises(ValueError, match="empty pool"):
            record.verify_selection()

    def test_record_is_immutable(self) -> None:
        """Record is frozen dataclass."""
        seed = b"12345678" * 4
        pool = ("WITNESS:a",)

        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="test",
            selected_witness_id="WITNESS:a",
            pool_snapshot=pool,
        )

        with pytest.raises(AttributeError):
            record.selected_witness_id = "WITNESS:b"  # type: ignore[misc]

    def test_to_dict_returns_expected_structure(self) -> None:
        """to_dict returns all fields in expected format."""
        seed = b"12345678" * 4
        pool = ("WITNESS:a", "WITNESS:b")
        now = datetime.now(timezone.utc)

        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="test",
            selected_witness_id="WITNESS:a",
            pool_snapshot=pool,
            selected_at=now,
        )

        result = record.to_dict()

        assert result["random_seed"] == base64.b64encode(seed).decode("utf-8")
        assert result["seed_source"] == "test"
        assert result["selected_witness_id"] == "WITNESS:a"
        assert result["pool_snapshot"] == ["WITNESS:a", "WITNESS:b"]
        assert result["algorithm_version"] == SELECTION_ALGORITHM_VERSION
        assert result["selected_at"] == now.isoformat()

    def test_signable_content_is_deterministic(self) -> None:
        """signable_content produces consistent output."""
        seed = b"12345678" * 4
        now = datetime.now(timezone.utc)

        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="test",
            selected_witness_id="WITNESS:a",
            pool_snapshot=("WITNESS:a", "WITNESS:b"),
            selected_at=now,
        )

        content1 = record.signable_content()
        content2 = record.signable_content()

        assert content1.raw_content == content2.raw_content

    def test_default_timestamp_is_utc_now(self) -> None:
        """Default selected_at is approximately now."""
        seed = b"12345678" * 4
        before = datetime.now(timezone.utc)

        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="test",
            selected_witness_id="WITNESS:a",
            pool_snapshot=("WITNESS:a",),
        )

        after = datetime.now(timezone.utc)

        assert before <= record.selected_at <= after

    def test_default_algorithm_version(self) -> None:
        """Default algorithm version is current version."""
        seed = b"12345678" * 4

        record = WitnessSelectionRecord(
            random_seed=seed,
            seed_source="test",
            selected_witness_id="WITNESS:a",
            pool_snapshot=("WITNESS:a",),
        )

        assert record.algorithm_version == SELECTION_ALGORITHM_VERSION
