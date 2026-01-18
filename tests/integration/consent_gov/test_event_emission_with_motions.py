"""Event emission tests using real Conclave motion data.

These tests validate that governance events can be created and emitted
from real Conclave session motions, including debate entries and votes.

Tests:
- Creating motion events
- Creating debate entry events
- Event type validation
- Branch derivation from event types
- Payload structure validation

Constitutional References:
- AD-4: Event envelope structure
- AD-15: Branch derived at write-time
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from src.domain.governance.events.event_envelope import (
    EventMetadata,
    GovernanceEvent,
)

if TYPE_CHECKING:
    from .conftest import ConclaveCheckpoint, DebateEntry, Motion


class TestMotionEventCreation:
    """Tests for creating events from Conclave motions."""

    @pytest.mark.asyncio
    async def test_create_motion_passed_event(
        self,
        motions: list,
        make_motion_event,
    ) -> None:
        """Motion passed event can be created."""
        if not motions:
            pytest.skip("No motions in checkpoint")

        motion = motions[0]
        event = make_motion_event(motion)

        assert event.event_type == "executive.motion.passed"
        assert event.actor_id == motion.proposer_id
        assert event.payload["motion_id"] == motion.motion_id
        assert event.payload["title"] == motion.title

    @pytest.mark.asyncio
    async def test_motion_event_includes_vote_tallies(
        self,
        motions: list,
        make_motion_event,
    ) -> None:
        """Motion event includes vote counts."""
        if not motions:
            pytest.skip("No motions in checkpoint")

        motion = motions[0]
        event = make_motion_event(motion)

        assert event.payload["final_ayes"] == motion.final_ayes
        assert event.payload["final_nays"] == motion.final_nays
        assert event.payload["final_abstentions"] == motion.final_abstentions

    @pytest.mark.asyncio
    async def test_motion_event_includes_proposer_seconder(
        self,
        motions: list,
        make_motion_event,
    ) -> None:
        """Motion event includes proposer and seconder info."""
        if not motions:
            pytest.skip("No motions in checkpoint")

        motion = motions[0]
        event = make_motion_event(motion)

        assert event.payload["proposer_name"] == motion.proposer_name
        assert event.payload["seconder_name"] == motion.seconder_name

    @pytest.mark.asyncio
    async def test_motion_event_branch_derived(
        self,
        motions: list,
        make_motion_event,
    ) -> None:
        """Branch is correctly derived from motion event type."""
        if not motions:
            pytest.skip("No motions in checkpoint")

        motion = motions[0]
        event = make_motion_event(motion)

        # Branch should be derived from event_type (first segment)
        assert event.branch == "executive"


class TestDebateEntryEventCreation:
    """Tests for creating events from debate entries."""

    @pytest.mark.asyncio
    async def test_create_speech_event(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Speech event can be created from debate entry."""
        if not debate_entries:
            pytest.skip("No debate entries in checkpoint")

        entry = debate_entries[0]
        event = make_governance_event(entry)

        assert event.event_type == "executive.speech.delivered"
        assert event.actor_id == entry.speaker_id

    @pytest.mark.asyncio
    async def test_speech_event_includes_speaker_details(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Speech event includes speaker metadata."""
        if not debate_entries:
            pytest.skip("No debate entries in checkpoint")

        entry = debate_entries[0]
        event = make_governance_event(entry)

        assert event.payload["speaker_name"] == entry.speaker_name
        assert event.payload["speaker_rank"] == entry.speaker_rank

    @pytest.mark.asyncio
    async def test_speech_event_includes_position(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Speech event includes position (in_favor)."""
        if not debate_entries:
            pytest.skip("No debate entries in checkpoint")

        entry = debate_entries[0]
        event = make_governance_event(entry)

        assert event.payload["in_favor"] == entry.in_favor
        assert event.payload["round_number"] == entry.round_number

    @pytest.mark.asyncio
    async def test_speech_event_includes_content(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Speech event includes full speech content."""
        if not debate_entries:
            pytest.skip("No debate entries in checkpoint")

        # Find a substantial speech
        substantial = next(
            (e for e in debate_entries if len(e.content) > 50),
            debate_entries[0],
        )
        event = make_governance_event(substantial)

        assert event.payload["content"] == substantial.content
        assert len(event.payload["content"]) > 0


class TestEventTypeValidation:
    """Tests for event type validation rules."""

    @pytest.mark.asyncio
    async def test_valid_executive_event_type(
        self,
        fake_time_authority,
    ) -> None:
        """Valid executive branch event type passes validation."""
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.motion.passed",
            timestamp=fake_time_authority.now(),
            actor_id="test-archon-id",
            trace_id="test-trace",
            payload={"motion_id": "test-motion"},
        )

        assert event.event_type == "executive.motion.passed"
        assert event.branch == "executive"

    @pytest.mark.asyncio
    async def test_valid_judicial_event_type(
        self,
        fake_time_authority,
    ) -> None:
        """Valid judicial branch event type passes validation."""
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="judicial.panel.convened",
            timestamp=fake_time_authority.now(),
            actor_id="test-prince-id",
            trace_id="test-trace",
            payload={"panel_id": "test-panel"},
        )

        assert event.branch == "judicial"

    @pytest.mark.asyncio
    async def test_valid_witness_event_type(
        self,
        fake_time_authority,
    ) -> None:
        """Valid witness branch event type passes validation."""
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="witness.observation.recorded",
            timestamp=fake_time_authority.now(),
            actor_id="test-knight-id",
            trace_id="test-trace",
            payload={"observation_id": "test-obs"},
        )

        assert event.branch == "witness"


class TestEventMetadataValidation:
    """Tests for event metadata validation."""

    @pytest.mark.asyncio
    async def test_event_requires_actor_id(
        self,
        debate_entries: list,
        fake_time_authority,
    ) -> None:
        """Event creation requires non-empty actor_id."""
        from src.domain.errors.constitutional import ConstitutionalViolationError

        with pytest.raises(ConstitutionalViolationError):
            GovernanceEvent.create(
                event_id=uuid4(),
                event_type="executive.speech.delivered",
                timestamp=fake_time_authority.now(),
                actor_id="",  # Empty actor_id
                trace_id="test-trace",
                payload={"content": "test"},
            )

    @pytest.mark.asyncio
    async def test_event_requires_trace_id(
        self,
        fake_time_authority,
    ) -> None:
        """Event creation requires non-empty trace_id."""
        from src.domain.errors.constitutional import ConstitutionalViolationError

        with pytest.raises(ConstitutionalViolationError):
            GovernanceEvent.create(
                event_id=uuid4(),
                event_type="executive.speech.delivered",
                timestamp=fake_time_authority.now(),
                actor_id="test-actor",
                trace_id="",  # Empty trace_id
                payload={"content": "test"},
            )

    @pytest.mark.asyncio
    async def test_event_timestamp_from_debate_entry(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Event preserves timestamp from debate entry."""
        if not debate_entries:
            pytest.skip("No debate entries")

        entry = debate_entries[0]
        event = make_governance_event(entry)

        assert event.timestamp == entry.timestamp


class TestEventPayloadImmutability:
    """Tests for event payload immutability."""

    @pytest.mark.asyncio
    async def test_payload_is_frozen(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Event payload is immutable (MappingProxyType)."""
        from types import MappingProxyType

        if not debate_entries:
            pytest.skip("No debate entries")

        entry = debate_entries[0]
        event = make_governance_event(entry)

        # Payload should be MappingProxyType (immutable)
        assert isinstance(event.payload, MappingProxyType)

    @pytest.mark.asyncio
    async def test_payload_modification_raises(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Attempting to modify payload raises TypeError."""
        if not debate_entries:
            pytest.skip("No debate entries")

        entry = debate_entries[0]
        event = make_governance_event(entry)

        with pytest.raises(TypeError):
            event.payload["new_key"] = "new_value"  # type: ignore


class TestBulkEventCreation:
    """Tests for creating multiple events from session data."""

    @pytest.mark.asyncio
    async def test_create_events_for_all_entries(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Events can be created for all debate entries."""
        events = [make_governance_event(e) for e in debate_entries]

        assert len(events) == len(debate_entries)
        for event in events:
            assert event.event_type == "executive.speech.delivered"
            assert event.payload.get("content")

    @pytest.mark.asyncio
    async def test_events_have_unique_ids(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Each created event has unique event_id."""
        events = [make_governance_event(e) for e in debate_entries]

        event_ids = [e.event_id for e in events]
        assert len(event_ids) == len(set(event_ids))  # All unique

    @pytest.mark.asyncio
    async def test_events_preserve_debate_order(
        self,
        debate_entries: list,
        make_governance_event,
    ) -> None:
        """Events preserve order of debate entries."""
        events = [make_governance_event(e) for e in debate_entries]

        for i, (event, entry) in enumerate(zip(events, debate_entries)):
            assert event.actor_id == entry.speaker_id
            assert event.payload["speaker_name"] == entry.speaker_name
