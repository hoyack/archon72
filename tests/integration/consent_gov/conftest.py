"""Fixtures for consent-gov isolation tests using Conclave artifacts.

This module provides pytest fixtures that load real Conclave session data
(checkpoints and transcripts) as test fixtures for validating consent-gov
infrastructure.

Fixture Sources:
- _bmad-output/conclave/checkpoint-*.json: Conclave session checkpoints
- _bmad-output/conclave/transcript-*.md: Session transcripts

Key Fixtures:
- conclave_checkpoint: Parsed checkpoint JSON with motions and participants
- debate_entries: List of debate entries from checkpoint
- speech_contents: List of speech content strings for coercion testing
- motion_data: Motion metadata for event emission tests
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest


# =============================================================================
# Path Constants
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONCLAVE_DIR = PROJECT_ROOT / "_bmad-output" / "conclave"

# Latest checkpoint file (most recent session)
CHECKPOINT_FILES = sorted(CONCLAVE_DIR.glob("checkpoint-*.json"))


# =============================================================================
# Domain Models for Parsed Checkpoint Data
# =============================================================================


@dataclass(frozen=True)
class DebateEntry:
    """A single debate entry from a Conclave session."""

    entry_id: str
    speaker_id: str
    speaker_name: str
    speaker_rank: str
    content: str
    round_number: int
    timestamp: datetime
    in_favor: bool


@dataclass(frozen=True)
class Motion:
    """A motion from a Conclave session."""

    motion_id: str
    motion_type: str
    title: str
    text: str
    proposer_id: str
    proposer_name: str
    seconder_id: str
    seconder_name: str
    status: str
    final_ayes: int
    final_nays: int
    final_abstentions: int
    debate_entries: tuple[DebateEntry, ...]


@dataclass(frozen=True)
class ConclaveCheckpoint:
    """Parsed Conclave session checkpoint."""

    session_id: str
    session_name: str
    started_at: datetime
    ended_at: datetime | None
    present_participants: tuple[str, ...]
    motions: tuple[Motion, ...]

    @property
    def participant_count(self) -> int:
        """Number of present participants."""
        return len(self.present_participants)

    @property
    def total_speeches(self) -> int:
        """Total number of debate entries across all motions."""
        return sum(len(m.debate_entries) for m in self.motions)


# =============================================================================
# Parser Functions
# =============================================================================


def _parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO datetime string to datetime object."""
    if not dt_str:
        return None
    # Handle various ISO formats
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        # Fallback for other formats
        return datetime.fromisoformat(dt_str)


def _parse_debate_entry(entry_data: dict[str, Any]) -> DebateEntry:
    """Parse a debate entry dict into DebateEntry dataclass."""
    return DebateEntry(
        entry_id=entry_data.get("entry_id", ""),
        speaker_id=entry_data.get("speaker_id", ""),
        speaker_name=entry_data.get("speaker_name", ""),
        speaker_rank=entry_data.get("speaker_rank", ""),
        content=entry_data.get("content", ""),
        round_number=entry_data.get("round_number", 0),
        timestamp=_parse_datetime(entry_data.get("timestamp")) or datetime.now(),
        in_favor=entry_data.get("in_favor", True),
    )


def _parse_motion(motion_data: dict[str, Any]) -> Motion:
    """Parse a motion dict into Motion dataclass."""
    debate_entries = tuple(
        _parse_debate_entry(e) for e in motion_data.get("debate_entries", [])
    )

    return Motion(
        motion_id=motion_data.get("motion_id", ""),
        motion_type=motion_data.get("motion_type", ""),
        title=motion_data.get("title", ""),
        text=motion_data.get("text", ""),
        proposer_id=motion_data.get("proposer_id", ""),
        proposer_name=motion_data.get("proposer_name", ""),
        seconder_id=motion_data.get("seconder_id", ""),
        seconder_name=motion_data.get("seconder_name", ""),
        status=motion_data.get("status", ""),
        final_ayes=motion_data.get("final_ayes", 0),
        final_nays=motion_data.get("final_nays", 0),
        final_abstentions=motion_data.get("final_abstentions", 0),
        debate_entries=debate_entries,
    )


def _parse_checkpoint(checkpoint_data: dict[str, Any]) -> ConclaveCheckpoint:
    """Parse checkpoint JSON into ConclaveCheckpoint dataclass."""
    motions = tuple(_parse_motion(m) for m in checkpoint_data.get("motions", []))

    return ConclaveCheckpoint(
        session_id=checkpoint_data.get("session_id", ""),
        session_name=checkpoint_data.get("session_name", ""),
        started_at=_parse_datetime(checkpoint_data.get("started_at"))
        or datetime.now(),
        ended_at=_parse_datetime(checkpoint_data.get("ended_at")),
        present_participants=tuple(checkpoint_data.get("present_participants", [])),
        motions=motions,
    )


# =============================================================================
# Pytest Fixtures - Raw Data
# =============================================================================


@pytest.fixture(scope="module")
def conclave_checkpoint_path() -> Path:
    """Get path to the latest Conclave checkpoint file.

    Returns:
        Path to the most recent checkpoint JSON file.

    Raises:
        FileNotFoundError: If no checkpoint files exist.
    """
    if not CHECKPOINT_FILES:
        pytest.skip(
            f"No Conclave checkpoint files found in {CONCLAVE_DIR}. "
            "Run a Conclave session first."
        )
    return CHECKPOINT_FILES[-1]  # Most recent


@pytest.fixture(scope="module")
def conclave_checkpoint_raw(conclave_checkpoint_path: Path) -> dict[str, Any]:
    """Load raw checkpoint JSON data.

    Returns:
        Parsed JSON dictionary from checkpoint file.
    """
    with open(conclave_checkpoint_path) as f:
        return json.load(f)


# =============================================================================
# Pytest Fixtures - Parsed Data
# =============================================================================


@pytest.fixture(scope="module")
def conclave_checkpoint(conclave_checkpoint_raw: dict[str, Any]) -> ConclaveCheckpoint:
    """Parse checkpoint into structured ConclaveCheckpoint.

    Returns:
        ConclaveCheckpoint with typed access to session data.
    """
    return _parse_checkpoint(conclave_checkpoint_raw)


@pytest.fixture(scope="module")
def motions(conclave_checkpoint: ConclaveCheckpoint) -> list[Motion]:
    """Get all motions from checkpoint.

    Returns:
        List of Motion objects.
    """
    return list(conclave_checkpoint.motions)


@pytest.fixture(scope="module")
def debate_entries(conclave_checkpoint: ConclaveCheckpoint) -> list[DebateEntry]:
    """Get all debate entries across all motions.

    Returns:
        Flattened list of all DebateEntry objects.
    """
    entries: list[DebateEntry] = []
    for motion in conclave_checkpoint.motions:
        entries.extend(motion.debate_entries)
    return entries


@pytest.fixture(scope="module")
def speech_contents(debate_entries: list[DebateEntry]) -> list[str]:
    """Get all speech content strings for coercion filter testing.

    Returns:
        List of speech content strings from debate entries.
    """
    return [e.content for e in debate_entries if e.content.strip()]


@pytest.fixture(scope="module")
def speaker_data(debate_entries: list[DebateEntry]) -> list[dict[str, Any]]:
    """Get speaker metadata for each debate entry.

    Returns:
        List of dicts with speaker_id, speaker_name, speaker_rank.
    """
    return [
        {
            "speaker_id": e.speaker_id,
            "speaker_name": e.speaker_name,
            "speaker_rank": e.speaker_rank,
            "round_number": e.round_number,
            "in_favor": e.in_favor,
        }
        for e in debate_entries
    ]


@pytest.fixture(scope="module")
def participant_ids(conclave_checkpoint: ConclaveCheckpoint) -> list[str]:
    """Get all participant UUIDs from the session.

    Returns:
        List of participant ID strings.
    """
    return list(conclave_checkpoint.present_participants)


# =============================================================================
# Pytest Fixtures - Event Creation Helpers
# =============================================================================


@pytest.fixture
def make_governance_event():
    """Factory fixture for creating GovernanceEvent from debate entry.

    Returns:
        Function that takes a DebateEntry and returns a GovernanceEvent.
    """
    from uuid import uuid4

    from src.domain.governance.events.event_envelope import GovernanceEvent

    def _make_event(
        entry: DebateEntry,
        event_type: str = "executive.speech.delivered",
    ) -> GovernanceEvent:
        """Create a GovernanceEvent from a DebateEntry."""
        return GovernanceEvent.create(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=entry.timestamp,
            actor_id=entry.speaker_id,
            trace_id=f"conclave-test-{entry.entry_id}",
            payload={
                "speaker_name": entry.speaker_name,
                "speaker_rank": entry.speaker_rank,
                "content": entry.content,
                "round_number": entry.round_number,
                "in_favor": entry.in_favor,
            },
        )

    return _make_event


@pytest.fixture
def make_motion_event():
    """Factory fixture for creating GovernanceEvent from motion.

    Returns:
        Function that takes a Motion and returns a GovernanceEvent.
    """
    from uuid import uuid4

    from src.domain.governance.events.event_envelope import GovernanceEvent

    def _make_event(
        motion: Motion,
        event_type: str = "executive.motion.passed",
    ) -> GovernanceEvent:
        """Create a GovernanceEvent from a Motion."""
        from datetime import timezone

        return GovernanceEvent.create(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_id=motion.proposer_id,
            trace_id=f"conclave-motion-{motion.motion_id}",
            payload={
                "motion_id": motion.motion_id,
                "motion_type": motion.motion_type,
                "title": motion.title,
                "text": motion.text,
                "proposer_name": motion.proposer_name,
                "seconder_name": motion.seconder_name,
                "final_ayes": motion.final_ayes,
                "final_nays": motion.final_nays,
                "final_abstentions": motion.final_abstentions,
            },
        )

    return _make_event


# =============================================================================
# Pytest Fixtures - Service Mocks
# =============================================================================


@pytest.fixture
def mock_pattern_library():
    """Mock pattern library for coercion filter tests.

    Returns:
        PatternLibraryPort mock with default patterns.
    """
    from unittest.mock import AsyncMock

    from src.domain.governance.filter import FilterVersion

    mock = AsyncMock()

    # Default version
    mock.get_current_version.return_value = FilterVersion(
        major=1, minor=0, patch=0, rules_hash="test-hash-123"
    )

    # No blocking patterns by default (clean speech)
    mock.get_blocking_patterns.return_value = []

    # No rejection patterns by default
    mock.get_rejection_patterns.return_value = []

    # No transformations by default
    mock.get_transformation_rules.return_value = []

    return mock


@pytest.fixture
def coercion_filter_service(mock_pattern_library, fake_time_authority):
    """Create CoercionFilterService with mock dependencies.

    Returns:
        Configured CoercionFilterService for testing.
    """
    from src.application.services.governance.coercion_filter_service import (
        CoercionFilterService,
    )

    return CoercionFilterService(
        pattern_library=mock_pattern_library,
        time_authority=fake_time_authority,
    )
