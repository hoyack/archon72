"""Unit tests for witness pair domain models (FR60).

Tests WitnessPair and WitnessPairHistory.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.models.witness_pair import (
    ROTATION_WINDOW_HOURS,
    WitnessPair,
    WitnessPairHistory,
)


class TestWitnessPair:
    """Tests for WitnessPair."""

    def test_canonical_key_is_sorted(self) -> None:
        """Canonical key sorts witness IDs alphabetically."""
        pair = WitnessPair(
            witness_a_id="WITNESS:zzz",
            witness_b_id="WITNESS:aaa",
        )

        key = pair.canonical_key()

        # Should be sorted: aaa before zzz
        assert key == "WITNESS:aaa:WITNESS:zzz"

    def test_canonical_key_is_symmetric(self) -> None:
        """(A,B) has same canonical key as (B,A)."""
        pair1 = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )
        pair2 = WitnessPair(
            witness_a_id="WITNESS:b",
            witness_b_id="WITNESS:a",
        )

        assert pair1.canonical_key() == pair2.canonical_key()

    def test_same_witness_canonical_key(self) -> None:
        """Same witness in both positions has valid canonical key."""
        pair = WitnessPair(
            witness_a_id="WITNESS:same",
            witness_b_id="WITNESS:same",
        )

        key = pair.canonical_key()

        assert key == "WITNESS:same:WITNESS:same"

    def test_pair_is_immutable(self) -> None:
        """Pair is frozen dataclass."""
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )

        with pytest.raises(AttributeError):
            pair.witness_a_id = "WITNESS:c"  # type: ignore[misc]

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all fields and canonical key."""
        now = datetime.now(timezone.utc)
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
            paired_at=now,
        )

        result = pair.to_dict()

        assert result["witness_a_id"] == "WITNESS:a"
        assert result["witness_b_id"] == "WITNESS:b"
        assert result["paired_at"] == now.isoformat()
        assert result["canonical_key"] == pair.canonical_key()

    def test_default_timestamp_is_utc_now(self) -> None:
        """Default paired_at is approximately now."""
        before = datetime.now(timezone.utc)

        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )

        after = datetime.now(timezone.utc)

        assert before <= pair.paired_at <= after


class TestWitnessPairHistory:
    """Tests for WitnessPairHistory."""

    def test_has_appeared_in_24h_returns_false_for_new_pair(self) -> None:
        """New pair has not appeared."""
        history = WitnessPairHistory()
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )

        result = history.has_appeared_in_24h(pair)

        assert result is False

    def test_has_appeared_in_24h_returns_true_after_record(self) -> None:
        """Recorded pair has appeared."""
        history = WitnessPairHistory()
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )

        history.record_pair(pair)
        result = history.has_appeared_in_24h(pair)

        assert result is True

    def test_symmetric_pair_detection(self) -> None:
        """Recording (A,B) affects check for (B,A)."""
        history = WitnessPairHistory()
        pair1 = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )
        pair2 = WitnessPair(
            witness_a_id="WITNESS:b",
            witness_b_id="WITNESS:a",
        )

        history.record_pair(pair1)
        result = history.has_appeared_in_24h(pair2)

        assert result is True

    def test_has_appeared_returns_false_after_24h(self) -> None:
        """Pair is allowed after 24 hours."""
        history = WitnessPairHistory()

        # Record pair 25 hours ago
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
            paired_at=old_time,
        )
        history.record_pair(pair)

        # Check with new pair (same witnesses)
        new_pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )
        result = history.has_appeared_in_24h(new_pair)

        assert result is False

    def test_has_appeared_returns_true_at_24h_boundary(self) -> None:
        """Pair is blocked exactly at 24 hour boundary."""
        history = WitnessPairHistory()

        # Record pair exactly 23 hours 59 minutes ago
        almost_24h = datetime.now(timezone.utc) - timedelta(hours=23, minutes=59)
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
            paired_at=almost_24h,
        )
        history.record_pair(pair)

        # Should still be blocked (within window)
        new_pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
        )
        result = history.has_appeared_in_24h(new_pair)

        assert result is True

    def test_prune_old_pairs_removes_old_entries(self) -> None:
        """prune_old_pairs removes entries older than 24h."""
        history = WitnessPairHistory()

        # Add old pair (25 hours ago)
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        old_pair = WitnessPair(
            witness_a_id="WITNESS:old_a",
            witness_b_id="WITNESS:old_b",
            paired_at=old_time,
        )
        history.record_pair(old_pair)

        # Add recent pair
        recent_pair = WitnessPair(
            witness_a_id="WITNESS:new_a",
            witness_b_id="WITNESS:new_b",
        )
        history.record_pair(recent_pair)

        # Prune
        removed = history.prune_old_pairs()

        assert removed == 1
        assert history.pair_count == 1

    def test_clear_removes_all_pairs(self) -> None:
        """clear removes all pairs."""
        history = WitnessPairHistory()

        # Add some pairs
        for i in range(5):
            pair = WitnessPair(
                witness_a_id=f"WITNESS:a{i}",
                witness_b_id=f"WITNESS:b{i}",
            )
            history.record_pair(pair)

        assert history.pair_count == 5

        history.clear()

        assert history.pair_count == 0

    def test_get_last_appearance_returns_timestamp(self) -> None:
        """get_last_appearance returns recorded timestamp."""
        history = WitnessPairHistory()
        now = datetime.now(timezone.utc)
        pair = WitnessPair(
            witness_a_id="WITNESS:a",
            witness_b_id="WITNESS:b",
            paired_at=now,
        )

        history.record_pair(pair)
        result = history.get_last_appearance(pair.canonical_key())

        assert result == now

    def test_get_last_appearance_returns_none_for_unknown(self) -> None:
        """get_last_appearance returns None for unknown pair."""
        history = WitnessPairHistory()

        result = history.get_last_appearance("WITNESS:unknown:WITNESS:pair")

        assert result is None

    def test_rotation_window_hours_is_24(self) -> None:
        """ROTATION_WINDOW_HOURS constant is 24."""
        assert ROTATION_WINDOW_HOURS == 24
