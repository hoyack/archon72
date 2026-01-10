"""Unit tests for InMemoryWitnessPairHistory stub.

Tests the stub implementation of WitnessPairHistoryProtocol.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.models.witness_pair import WitnessPair
from src.infrastructure.stubs.witness_pair_history_stub import InMemoryWitnessPairHistory


class TestInMemoryWitnessPairHistory:
    """Tests for InMemoryWitnessPairHistory."""

    @pytest.mark.asyncio
    async def test_has_appeared_in_24h_false_for_new_pair(self) -> None:
        """New pair has not appeared."""
        history = InMemoryWitnessPairHistory()
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )

        result = await history.has_appeared_in_24h(pair)

        assert result is False

    @pytest.mark.asyncio
    async def test_has_appeared_in_24h_true_after_record(self) -> None:
        """Recorded pair has appeared."""
        history = InMemoryWitnessPairHistory()
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )

        await history.record_pair(pair)
        result = await history.has_appeared_in_24h(pair)

        assert result is True

    @pytest.mark.asyncio
    async def test_record_pair_updates_timestamp(self) -> None:
        """Recording pair updates the timestamp."""
        history = InMemoryWitnessPairHistory()
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )

        await history.record_pair(pair)
        first_appearance = await history.get_pair_last_appearance(pair.canonical_key())

        # Record again with new timestamp
        new_pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )
        await history.record_pair(new_pair)
        second_appearance = await history.get_pair_last_appearance(pair.canonical_key())

        assert second_appearance >= first_appearance

    @pytest.mark.asyncio
    async def test_get_pair_last_appearance_returns_timestamp(self) -> None:
        """get_pair_last_appearance returns recorded timestamp."""
        history = InMemoryWitnessPairHistory()
        now = datetime.now(timezone.utc)
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
            paired_at=now,
        )

        await history.record_pair(pair)
        result = await history.get_pair_last_appearance(pair.canonical_key())

        assert result == now

    @pytest.mark.asyncio
    async def test_get_pair_last_appearance_returns_none_for_unknown(self) -> None:
        """get_pair_last_appearance returns None for unknown pair."""
        history = InMemoryWitnessPairHistory()

        result = await history.get_pair_last_appearance("UNKNOWN:KEY")

        assert result is None

    @pytest.mark.asyncio
    async def test_prune_old_pairs_removes_old_entries(self) -> None:
        """prune_old_pairs removes entries older than 24h."""
        history = InMemoryWitnessPairHistory()

        # Add old pair (25 hours ago)
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        old_pair = WitnessPair(
            witness_a_id="WITNESS:old_a",
            witness_b_id="WITNESS:old_b",
            paired_at=old_time,
        )
        await history.record_pair(old_pair)

        # Add recent pair
        recent_pair = WitnessPair(
            witness_a_id="WITNESS:new_a",
            witness_b_id="WITNESS:new_b",
        )
        await history.record_pair(recent_pair)

        # Prune
        removed = await history.prune_old_pairs()

        assert removed == 1
        assert await history.count_tracked_pairs() == 1

    @pytest.mark.asyncio
    async def test_count_tracked_pairs(self) -> None:
        """count_tracked_pairs returns correct count."""
        history = InMemoryWitnessPairHistory()

        for i in range(5):
            pair = WitnessPair(
                witness_a_id=f"WITNESS:a{i}",
                witness_b_id=f"WITNESS:b{i}",
            )
            await history.record_pair(pair)

        count = await history.count_tracked_pairs()

        assert count == 5

    def test_clear_removes_all_pairs(self) -> None:
        """clear removes all pairs."""
        history = InMemoryWitnessPairHistory()

        # Add some pairs synchronously via inject
        history.inject_pair("WITNESS:a:WITNESS:b", datetime.now(timezone.utc))
        history.inject_pair("WITNESS:c:WITNESS:d", datetime.now(timezone.utc))

        assert history.pair_count == 2

        history.clear()

        assert history.pair_count == 0

    def test_inject_pair_for_testing(self) -> None:
        """inject_pair allows test setup."""
        history = InMemoryWitnessPairHistory()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        history.inject_pair("WITNESS:test:WITNESS:pair", timestamp)

        pairs = history.get_all_pairs()
        assert "WITNESS:test:WITNESS:pair" in pairs
        assert pairs["WITNESS:test:WITNESS:pair"] == timestamp

    def test_get_all_pairs_returns_copy(self) -> None:
        """get_all_pairs returns a copy of internal dict."""
        history = InMemoryWitnessPairHistory()
        history.inject_pair("key", datetime.now(timezone.utc))

        pairs = history.get_all_pairs()
        pairs["modified"] = datetime.now(timezone.utc)

        assert "modified" not in history.get_all_pairs()

    def test_pair_count_property(self) -> None:
        """pair_count property returns current count."""
        history = InMemoryWitnessPairHistory()

        assert history.pair_count == 0

        history.inject_pair("key1", datetime.now(timezone.utc))
        assert history.pair_count == 1

        history.inject_pair("key2", datetime.now(timezone.utc))
        assert history.pair_count == 2
