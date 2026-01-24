"""Shared fixtures for cessation chaos tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from src.application.services.cessation_execution_service import (
    CessationExecutionService,
)
from src.application.services.event_writer_service import EventWriterService
from src.application.services.final_deliberation_service import (
    FinalDeliberationService,
)
from src.domain.events.event import Event
from src.infrastructure.stubs.cessation_flag_repository_stub import (
    CessationFlagRepositoryStub,
)
from src.infrastructure.stubs.event_store_stub import EventStoreStub
from src.infrastructure.stubs.final_deliberation_recorder_stub import (
    FinalDeliberationRecorderStub,
)


@dataclass
class ChaosTestArtifact:
    """Artifact documenting chaos test execution (AC4)."""

    test_name: str
    execution_timestamp: datetime
    events_created: list[str] = field(default_factory=list)
    final_sequence: int | None = None
    read_only_verified: bool = False
    issues: list[str] = field(default_factory=list)
    success: bool = False


@dataclass
class IsolatedCessationEnvironment:
    """Completely isolated environment for cessation chaos testing (AC5)."""

    event_store: EventStoreStub
    cessation_flag_repo: CessationFlagRepositoryStub
    deliberation_recorder: FinalDeliberationRecorderStub
    event_writer: EventWriterService
    final_deliberation_service: FinalDeliberationService
    cessation_execution_service: CessationExecutionService
    artifact: ChaosTestArtifact

    def clear(self) -> None:
        """Clear all state for test isolation."""
        self.event_store.clear()
        self.cessation_flag_repo.clear()
        self.deliberation_recorder.recorded_deliberations.clear()
        self.deliberation_recorder.recorded_failures.clear()


def _create_mock_event_writer(event_store: EventStoreStub) -> EventWriterService:
    """Create a minimal EventWriterService mock for chaos testing."""
    from unittest.mock import AsyncMock, MagicMock

    mock_writer = MagicMock(spec=EventWriterService)

    async def mock_write_event(
        event_type: str,
        payload: dict[str, object],
        agent_id: str,
        local_timestamp: datetime | None = None,
    ) -> Event:
        current_head = await event_store.get_latest_event()
        next_sequence = (current_head.sequence + 1) if current_head else 1
        prev_hash = current_head.content_hash if current_head else None

        event = Event.create_with_hash(
            sequence=next_sequence,
            event_type=event_type,
            payload=payload,
            signature=f"chaos_test_signature_{next_sequence}",
            witness_id="SYSTEM:CHAOS_TEST_WITNESS",
            witness_signature=f"chaos_witness_sig_{next_sequence}",
            local_timestamp=local_timestamp or datetime.now(timezone.utc),
            previous_content_hash=prev_hash,
            agent_id=agent_id,
        )

        await event_store.append_event(event)
        return event

    mock_writer.write_event = AsyncMock(side_effect=mock_write_event)

    return mock_writer


@pytest.fixture
def isolated_cessation_env() -> IsolatedCessationEnvironment:
    """Create completely isolated environment for cessation chaos test."""
    event_store = EventStoreStub()
    cessation_flag_repo = CessationFlagRepositoryStub()
    deliberation_recorder = FinalDeliberationRecorderStub()

    event_writer = _create_mock_event_writer(event_store)

    final_deliberation_service = FinalDeliberationService(
        recorder=deliberation_recorder,
        max_retries=3,
    )

    cessation_execution_service = CessationExecutionService(
        event_writer=event_writer,
        event_store=event_store,
        cessation_flag_repo=cessation_flag_repo,
        final_deliberation_service=final_deliberation_service,
    )

    artifact = ChaosTestArtifact(
        test_name="cessation_chaos_test",
        execution_timestamp=datetime.now(timezone.utc),
    )

    return IsolatedCessationEnvironment(
        event_store=event_store,
        cessation_flag_repo=cessation_flag_repo,
        deliberation_recorder=deliberation_recorder,
        event_writer=event_writer,
        final_deliberation_service=final_deliberation_service,
        cessation_execution_service=cessation_execution_service,
        artifact=artifact,
    )


__all__ = [
    "ChaosTestArtifact",
    "IsolatedCessationEnvironment",
    "isolated_cessation_env",
]
