"""Hash chain tests using real Conclave debate speeches.

These tests validate that the hash chain infrastructure works correctly
with production-like speech content from actual Conclave sessions.

Tests:
- Creating events from debate entries
- Chaining events with hash computation
- Verifying individual event hashes
- Verifying chain links between events
- Detecting tampered events
- Full chain verification

Constitutional References:
- AD-6: BLAKE3/SHA-256 hash algorithms
- NFR-CONST-02: Event integrity verification
- NFR-AUDIT-06: Deterministic replay
- FR1: Events must be hash-chained
- FR2: Tampering detection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.hash_chain import (
    add_hash_to_event,
    chain_events,
    verify_chain_link,
    verify_event_full,
    verify_event_hash,
)

if TYPE_CHECKING:
    from .conftest import ConclaveCheckpoint, DebateEntry


class TestHashChainWithSpeeches:
    """Tests for hash chain using real Conclave speeches."""

    @pytest.mark.asyncio
    async def test_create_event_from_debate_entry(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Events can be created from real debate entries."""
        # Use first debate entry
        entry = debate_entries[0]

        event = make_governance_event(entry)

        assert event.event_type == "executive.speech.delivered"
        assert event.actor_id == entry.speaker_id
        assert event.payload["speaker_name"] == entry.speaker_name
        assert event.payload["content"] == entry.content
        assert event.payload["in_favor"] == entry.in_favor

    @pytest.mark.asyncio
    async def test_add_hash_to_speech_event(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Hash can be added to speech events (genesis case)."""
        entry = debate_entries[0]
        event = make_governance_event(entry)

        # Add hash as genesis event (using SHA-256 for test portability)
        hashed_event = add_hash_to_event(event, algorithm="sha256")

        assert hashed_event.has_hash()
        assert hashed_event.prev_hash.startswith("sha256:")
        assert hashed_event.hash.startswith("sha256:")

    @pytest.mark.asyncio
    async def test_chain_multiple_speeches(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Multiple speeches can be chained together."""
        # Use first 5 entries (or less if fewer available)
        entries_to_chain = debate_entries[: min(5, len(debate_entries))]
        events = [make_governance_event(e) for e in entries_to_chain]

        # Chain all events (using SHA-256 for test portability)
        chained = chain_events(events, algorithm="sha256")

        assert len(chained) == len(events)

        # All events should have hashes
        for event in chained:
            assert event.has_hash()

        # First event should have genesis prev_hash
        first = chained[0]
        assert first.prev_hash.startswith("sha256:")
        assert ":0000000000" in first.prev_hash  # Genesis hash pattern

        # Subsequent events should link to previous
        for i in range(1, len(chained)):
            current = chained[i]
            previous = chained[i - 1]
            assert current.prev_hash == previous.hash

    @pytest.mark.asyncio
    async def test_verify_speech_event_hash(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Speech event hash can be verified."""
        entry = debate_entries[0]
        event = make_governance_event(entry)
        hashed_event = add_hash_to_event(event, algorithm="sha256")

        result = verify_event_hash(hashed_event)

        assert result.is_valid
        assert result.event_hash_valid

    @pytest.mark.asyncio
    async def test_verify_chain_link_between_speeches(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Chain links between speeches verify correctly."""
        if len(debate_entries) < 2:
            pytest.skip("Need at least 2 debate entries for chain link test")

        entries = debate_entries[:2]
        events = [make_governance_event(e) for e in entries]
        chained = chain_events(events, algorithm="sha256")

        # Verify chain link
        result = verify_chain_link(chained[1], chained[0])

        assert result.is_valid
        assert result.chain_link_valid

    @pytest.mark.asyncio
    async def test_full_verification_of_speech_chain(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Full verification (hash + chain link) passes for valid chain."""
        entries = debate_entries[: min(3, len(debate_entries))]
        events = [make_governance_event(e) for e in entries]
        chained = chain_events(events, algorithm="sha256")

        # Verify each event
        for i, event in enumerate(chained):
            prev_event = chained[i - 1] if i > 0 else None
            result = verify_event_full(event, prev_event)
            assert result.is_valid, f"Event {i} failed verification: {result.error_message}"

    @pytest.mark.asyncio
    async def test_detect_tampered_speech_content(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Tampering with speech content is detected."""
        entry = debate_entries[0]
        event = make_governance_event(entry)
        hashed_event = add_hash_to_event(event, algorithm="sha256")

        # Create tampered event by modifying payload
        tampered_payload = dict(hashed_event.payload)
        tampered_payload["content"] = "TAMPERED SPEECH CONTENT"

        # Create new event with same metadata but tampered payload
        tampered_event = GovernanceEvent(
            metadata=hashed_event.metadata,
            payload=tampered_payload,
        )

        # Verification should fail
        result = verify_event_hash(tampered_event)

        assert not result.is_valid
        assert "mismatch" in result.error_message.lower() or "tamper" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_detect_broken_chain_link(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Broken chain links are detected."""
        if len(debate_entries) < 3:
            pytest.skip("Need at least 3 debate entries for broken chain test")

        entries = debate_entries[:3]
        events = [make_governance_event(e) for e in entries]
        chained = chain_events(events, algorithm="sha256")

        # Try to verify event[2] against event[0] (skipping event[1])
        result = verify_chain_link(chained[2], chained[0])

        assert not result.is_valid
        assert not result.chain_link_valid

    @pytest.mark.asyncio
    async def test_genesis_event_verification(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Genesis event (prev_event=None) verifies correctly."""
        entry = debate_entries[0]
        event = make_governance_event(entry)
        hashed_event = add_hash_to_event(event, algorithm="sha256")

        # Verify as genesis (no previous event)
        result = verify_chain_link(hashed_event, None)

        assert result.is_valid
        assert result.chain_link_valid


class TestHashChainWithRealSessionData:
    """Tests using complete session data from Conclave checkpoint."""

    @pytest.mark.asyncio
    async def test_chain_all_speeches_from_motion(
        self,
        conclave_checkpoint: ConclaveCheckpoint,
        make_governance_event,
    ) -> None:
        """All speeches from a motion can be chained."""
        if not conclave_checkpoint.motions:
            pytest.skip("No motions in checkpoint")

        motion = conclave_checkpoint.motions[0]
        entries = list(motion.debate_entries)

        if not entries:
            pytest.skip("No debate entries in first motion")

        events = [make_governance_event(e) for e in entries]
        chained = chain_events(events, algorithm="sha256")

        assert len(chained) == len(entries)

        # Verify entire chain
        for i, event in enumerate(chained):
            prev_event = chained[i - 1] if i > 0 else None
            result = verify_event_full(event, prev_event)
            assert result.is_valid, (
                f"Event {i} ({entries[i].speaker_name}) failed: {result.error_message}"
            )

    @pytest.mark.asyncio
    async def test_chain_with_mixed_positions(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Chain works with speeches both FOR and AGAINST."""
        # Find entries with different positions
        for_entries = [e for e in debate_entries if e.in_favor]
        against_entries = [e for e in debate_entries if not e.in_favor]

        if not for_entries or not against_entries:
            pytest.skip("Need speeches both FOR and AGAINST for this test")

        # Mix entries: FOR, AGAINST, FOR (if available)
        mixed_entries = [
            for_entries[0],
            against_entries[0],
        ]
        if len(for_entries) > 1:
            mixed_entries.append(for_entries[1])

        events = [make_governance_event(e) for e in mixed_entries]
        chained = chain_events(events, algorithm="sha256")

        # Verify chain integrity regardless of speech position
        for i, event in enumerate(chained):
            prev_event = chained[i - 1] if i > 0 else None
            result = verify_event_full(event, prev_event)
            assert result.is_valid

    @pytest.mark.asyncio
    async def test_payload_includes_full_speech_content(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Event payload includes the full speech content."""
        # Find a substantial speech
        substantial = next(
            (e for e in debate_entries if len(e.content) > 100),
            debate_entries[0] if debate_entries else None,
        )

        if not substantial:
            pytest.skip("No debate entries available")

        event = make_governance_event(substantial)

        assert event.payload["content"] == substantial.content
        assert len(event.payload["content"]) > 0


class TestHashAlgorithms:
    """Tests for hash algorithm support with real speech data."""

    @pytest.mark.asyncio
    async def test_sha256_is_portable_algorithm(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """SHA-256 is available and works consistently (per AD-6)."""
        entry = debate_entries[0]
        event = make_governance_event(entry)
        hashed_event = add_hash_to_event(event, algorithm="sha256")

        # Hash should use sha256 prefix
        assert hashed_event.hash.startswith("sha256:")
        assert hashed_event.prev_hash.startswith("sha256:")

    @pytest.mark.asyncio
    async def test_sha256_alternative_algorithm(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """SHA-256 can be used as alternative (per AD-6)."""
        entry = debate_entries[0]
        event = make_governance_event(entry)
        hashed_event = add_hash_to_event(event, algorithm="sha256")

        # Hash should use sha256 prefix
        assert hashed_event.hash.startswith("sha256:")
        assert hashed_event.prev_hash.startswith("sha256:")

        # Verification should still work
        result = verify_event_hash(hashed_event)
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_chain_with_sha256(
        self,
        debate_entries: list[DebateEntry],
        make_governance_event,
    ) -> None:
        """Complete chain can be built with SHA-256."""
        entries = debate_entries[: min(3, len(debate_entries))]
        events = [make_governance_event(e) for e in entries]
        chained = chain_events(events, algorithm="sha256")

        for event in chained:
            assert event.hash.startswith("sha256:")

        # Verify full chain
        for i, event in enumerate(chained):
            prev_event = chained[i - 1] if i > 0 else None
            result = verify_event_full(event, prev_event)
            assert result.is_valid
