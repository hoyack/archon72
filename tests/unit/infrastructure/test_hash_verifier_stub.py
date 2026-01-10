"""Unit tests for HashVerifierStub (Story 6.8, FR125).

Tests the in-memory stub implementation of HashVerifierProtocol.
"""

from __future__ import annotations

import pytest

from src.domain.events.hash_verification import HashVerificationResult
from src.infrastructure.stubs.hash_verifier_stub import HashVerifierStub


@pytest.fixture
def stub() -> HashVerifierStub:
    """Create a fresh stub for each test."""
    return HashVerifierStub()


class TestAddEvent:
    """Tests for add_event method."""

    def test_adds_event(self, stub: HashVerifierStub) -> None:
        """Test that events can be added."""
        stub.add_event(
            event_id="event-1",
            sequence_num=0,
            content_hash="hash_a",
            prev_hash="genesis",
        )

        # Event should be retrievable by verifying
        # (indirect test since we don't expose _events)
        assert stub._events["event-1"].event_id == "event-1"


class TestVerifyEventHash:
    """Tests for verify_event_hash method."""

    @pytest.mark.asyncio
    async def test_passes_valid_hash(self, stub: HashVerifierStub) -> None:
        """Test that valid hash passes verification."""
        stub.add_event(
            event_id="event-1",
            sequence_num=0,
            content_hash="hash_a",
            prev_hash="genesis",
        )

        result = await stub.verify_event_hash("event-1")
        assert result == HashVerificationResult.PASSED

    @pytest.mark.asyncio
    async def test_fails_with_override(self, stub: HashVerifierStub) -> None:
        """Test that verification fails when expected hash is set."""
        stub.add_event(
            event_id="event-1",
            sequence_num=0,
            content_hash="actual_hash",
            prev_hash="genesis",
        )
        stub.set_expected_hash("event-1", "expected_hash")

        result = await stub.verify_event_hash("event-1")
        assert result == HashVerificationResult.FAILED
        assert stub.halt_triggered

    @pytest.mark.asyncio
    async def test_raises_for_unknown_event(self, stub: HashVerifierStub) -> None:
        """Test that verification raises for unknown event."""
        from src.domain.errors.event_store import EventNotFoundError

        with pytest.raises(EventNotFoundError):
            await stub.verify_event_hash("non-existent")


class TestRunFullScan:
    """Tests for run_full_scan method."""

    @pytest.mark.asyncio
    async def test_passes_empty_store(self, stub: HashVerifierStub) -> None:
        """Test that empty store passes scan."""
        result = await stub.run_full_scan()
        assert result.passed
        assert result.events_scanned == 0

    @pytest.mark.asyncio
    async def test_passes_valid_chain(self, stub: HashVerifierStub) -> None:
        """Test that valid chain passes scan."""
        stub.add_event("event-1", 0, "hash_a", "genesis")
        stub.add_event("event-2", 1, "hash_b", "hash_a")
        stub.add_event("event-3", 2, "hash_c", "hash_b")

        result = await stub.run_full_scan()
        assert result.passed
        assert result.events_scanned == 3

    @pytest.mark.asyncio
    async def test_fails_hash_mismatch(self, stub: HashVerifierStub) -> None:
        """Test that hash mismatch fails scan."""
        stub.add_event("event-1", 0, "hash_a", "genesis")
        stub.add_event("event-2", 1, "hash_b", "hash_a")
        stub.set_expected_hash("event-2", "wrong_hash")

        result = await stub.run_full_scan()
        assert not result.passed
        assert result.failed_event_id == "event-2"
        assert stub.halt_triggered

    @pytest.mark.asyncio
    async def test_fails_broken_chain(self, stub: HashVerifierStub) -> None:
        """Test that broken chain fails scan."""
        stub.add_event("event-1", 0, "hash_a", "genesis")
        stub.add_event("event-2", 1, "hash_b", "wrong_prev")  # Chain broken

        result = await stub.run_full_scan()
        assert not result.passed
        assert result.failed_event_id == "event-2"
        assert stub.halt_triggered

    @pytest.mark.asyncio
    async def test_respects_max_events(self, stub: HashVerifierStub) -> None:
        """Test that max_events limits scan."""
        for i in range(10):
            prev = "genesis" if i == 0 else f"hash_{i-1}"
            stub.add_event(f"event-{i}", i, f"hash_{i}", prev)

        result = await stub.run_full_scan(max_events=5)
        assert result.passed
        assert result.events_scanned == 5


class TestGetLastScanStatus:
    """Tests for get_last_scan_status method."""

    @pytest.mark.asyncio
    async def test_returns_status(self, stub: HashVerifierStub) -> None:
        """Test that status is returned."""
        stub.add_event("event-1", 0, "hash_a", "genesis")
        await stub.run_full_scan()

        status = await stub.get_last_scan_status()
        assert status.last_scan_id is not None
        assert status.last_scan_passed is True
        assert status.events_verified_total == 1
        assert status.is_healthy

    @pytest.mark.asyncio
    async def test_initial_status(self, stub: HashVerifierStub) -> None:
        """Test initial status before any scans."""
        status = await stub.get_last_scan_status()
        assert status.last_scan_id is None
        assert status.last_scan_passed is None
        assert status.is_healthy  # No scans yet is okay


class TestScheduleContinuousVerification:
    """Tests for schedule_continuous_verification method."""

    @pytest.mark.asyncio
    async def test_sets_interval(self, stub: HashVerifierStub) -> None:
        """Test that interval can be set."""
        await stub.schedule_continuous_verification(1800)
        interval = await stub.get_verification_interval()
        assert interval == 1800

    @pytest.mark.asyncio
    async def test_rejects_invalid_interval(self, stub: HashVerifierStub) -> None:
        """Test that invalid interval is rejected."""
        with pytest.raises(ValueError):
            await stub.schedule_continuous_verification(0)

        with pytest.raises(ValueError):
            await stub.schedule_continuous_verification(-100)


class TestVerifyHashChainLink:
    """Tests for verify_hash_chain_link method."""

    @pytest.mark.asyncio
    async def test_passes_valid_link(self, stub: HashVerifierStub) -> None:
        """Test that valid chain link passes."""
        stub.add_event("event-1", 0, "hash_a", "genesis")
        stub.add_event("event-2", 1, "hash_b", "hash_a")

        result = await stub.verify_hash_chain_link(1)
        assert result == HashVerificationResult.PASSED

    @pytest.mark.asyncio
    async def test_passes_sequence_zero(self, stub: HashVerifierStub) -> None:
        """Test that sequence 0 always passes (no previous event)."""
        result = await stub.verify_hash_chain_link(0)
        assert result == HashVerificationResult.PASSED

    @pytest.mark.asyncio
    async def test_fails_broken_link(self, stub: HashVerifierStub) -> None:
        """Test that broken chain link fails."""
        stub.add_event("event-1", 0, "hash_a", "genesis")
        stub.add_event("event-2", 1, "hash_b", "wrong_prev")

        result = await stub.verify_hash_chain_link(1)
        assert result == HashVerificationResult.FAILED
        assert stub.halt_triggered


class TestClear:
    """Tests for clear method."""

    @pytest.mark.asyncio
    async def test_clears_all_data(self, stub: HashVerifierStub) -> None:
        """Test that clear removes all data."""
        stub.add_event("event-1", 0, "hash_a", "genesis")
        await stub.run_full_scan()

        stub.clear()

        assert stub._events == {}
        assert stub._last_scan_id is None
        assert stub._halt_triggered is False
