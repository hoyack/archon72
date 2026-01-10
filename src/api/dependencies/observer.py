"""Observer API dependencies (Story 4.1, Task 7; Story 4.6 - FR136 fix; Story 4.7 - FR139, FR140; Story 4.8 - SR-9; Story 7.8 - FR135 AC7; Story 7.10 - FR144).

Dependency injection setup for observer components.
These provide stub implementations for testing and development.

Constitutional Constraint:
- FR44: No authentication dependencies on observer routes
- FR135: Final deliberation SHALL be recorded and immutable (Story 7.8 AC7)
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Observers SHALL be able to verify event inclusion without downloading full chain
- FR139: Export SHALL support structured audit format (JSON Lines, CSV)
- FR140: Third-party attestation interface with attestation metadata
- FR144: System SHALL maintain published Integrity Case Artifact (Story 7.10)
- SR-9: Observer push notifications - webhook/SSE for breach events
- RT-5: Breach events pushed to multiple channels
"""

from collections.abc import AsyncIterator
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING

from src.api.middleware.rate_limiter import ObserverRateLimiter
from src.application.ports.checkpoint_repository import CheckpointRepository
from src.application.ports.event_store import EventStorePort
from src.application.ports.final_deliberation_recorder import FinalDeliberationRecorder
from src.application.ports.halt_checker import HaltChecker
from src.application.services.export_service import ExportService
from src.application.services.merkle_tree_service import MerkleTreeService
from src.application.services.notification_service import NotificationService
from src.application.services.observer_service import ObserverService
from src.infrastructure.stubs.checkpoint_repository_stub import CheckpointRepositoryStub
from src.infrastructure.stubs.final_deliberation_recorder_stub import (
    FinalDeliberationRecorderStub,
)
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.integrity_case_repository_stub import (
    IntegrityCaseRepositoryStub,
)
from src.application.services.integrity_case_service import IntegrityCaseService

if TYPE_CHECKING:
    from src.domain.events import Event


# Stub event store for development/testing
# In production, this would be replaced with a real implementation
class EventStoreStub(EventStorePort):
    """Stub event store for development and testing."""

    async def append_event(self, event):
        raise NotImplementedError("Stub does not support writes")

    async def get_latest_event(self):
        return None

    async def get_event_by_sequence(self, sequence: int):
        return None

    async def get_event_by_id(self, event_id):
        return None

    async def get_events_by_type(self, event_type: str, limit: int = 100, offset: int = 0):
        return []

    async def count_events(self) -> int:
        return 0

    async def get_max_sequence(self) -> int:
        return 0

    async def get_events_by_sequence_range(self, start: int, end: int):
        return []

    async def verify_sequence_continuity(self, start: int, end: int):
        return True, []

    async def mark_events_orphaned(self, start_sequence: int, end_sequence: int) -> int:
        return 0

    async def get_head_sequence(self) -> int:
        return 0

    async def set_head_sequence(self, sequence: int) -> None:
        pass

    async def get_events_by_sequence_range_with_orphaned(
        self, start: int, end: int, include_orphaned: bool = False
    ):
        return []

    async def get_events_filtered(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date=None,
        end_date=None,
        event_types=None,
    ):
        return []

    async def count_events_filtered(
        self,
        start_date=None,
        end_date=None,
        event_types=None,
    ) -> int:
        return 0

    # Historical query methods (Story 4.5 - FR88, FR89)
    async def get_events_up_to_sequence(
        self,
        max_sequence: int,
        limit: int = 100,
        offset: int = 0,
    ):
        return []

    async def count_events_up_to_sequence(self, max_sequence: int) -> int:
        return 0

    async def find_sequence_for_timestamp(self, timestamp) -> int | None:
        return None

    # Export methods (Story 4.7 - FR139)
    async def stream_events(
        self,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_types: list[str] | None = None,
        batch_size: int = 100,
    ) -> AsyncIterator["Event"]:
        # Stub yields nothing
        return
        yield  # type: ignore[misc]  # Required for async generator

    async def count_events_in_range(
        self,
        start_sequence: int,
        end_sequence: int,
    ) -> int:
        return 0


@lru_cache(maxsize=1)
def get_rate_limiter() -> ObserverRateLimiter:
    """Get singleton rate limiter.

    Returns:
        ObserverRateLimiter instance (cached).
    """
    return ObserverRateLimiter()


def get_event_store() -> EventStorePort:
    """Get event store instance.

    Note: In production, this would return a real implementation.
    For now, returns a stub for development/testing.

    Returns:
        EventStorePort implementation.
    """
    return EventStoreStub()


def get_halt_checker() -> HaltChecker:
    """Get halt checker instance.

    Note: In production, this would return a real implementation.
    For now, returns a stub that reports not halted.

    Returns:
        HaltChecker implementation.
    """
    return HaltCheckerStub()


@lru_cache(maxsize=1)
def get_checkpoint_repo() -> CheckpointRepository:
    """Get checkpoint repository instance.

    Note: In production, this would return a real implementation.
    For now, returns a stub for development/testing.

    Returns:
        CheckpointRepository implementation.
    """
    return CheckpointRepositoryStub()


@lru_cache(maxsize=1)
def get_merkle_service() -> MerkleTreeService:
    """Get Merkle tree service instance.

    Returns singleton MerkleTreeService for Merkle proof generation.

    Returns:
        MerkleTreeService instance.
    """
    return MerkleTreeService()


def get_freeze_checker_for_observer() -> FreezeCheckerStub:
    """Get freeze checker instance for observer service.

    Returns the freeze checker used for cessation status (Story 7.5).
    Note: In production, this would return a real implementation.

    Returns:
        FreezeCheckerStub implementation.
    """
    return FreezeCheckerStub()


def get_observer_service() -> ObserverService:
    """Get observer service instance.

    Creates the service with proper dependencies including
    checkpoint_repo, merkle_service for FR136 Merkle proofs,
    and freeze_checker for cessation status (Story 7.5).

    No parameters to avoid FastAPI dependency injection issues.

    Returns:
        ObserverService instance.
    """
    return ObserverService(
        event_store=get_event_store(),
        halt_checker=get_halt_checker(),
        checkpoint_repo=get_checkpoint_repo(),
        merkle_service=get_merkle_service(),
        freeze_checker=get_freeze_checker_for_observer(),
    )


def get_export_service() -> ExportService:
    """Get export service instance.

    Creates the export service for regulatory export functionality.
    Per FR139: Export SHALL support structured audit format.
    Per FR140: Third-party attestation interface.

    No parameters to avoid FastAPI dependency injection issues.

    Returns:
        ExportService instance.
    """
    return ExportService(
        event_store=get_event_store(),
        # HSM is optional - not provided for stub, will not sign attestations
    )


# Singleton notification service for SSE connections to persist across requests
_notification_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """Get notification service instance (singleton).

    Creates the notification service for push notification functionality.
    Per SR-9: Observer push notifications - webhook/SSE for breach events.
    Per RT-5: Breach events pushed to multiple channels.

    Uses singleton pattern because SSE connections must persist
    across multiple requests.

    Returns:
        NotificationService instance.
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService(
            base_url="http://localhost:8000",
        )
    return _notification_service


# Singleton deliberation recorder for Observer API queries (Story 7.8, AC7)
_deliberation_recorder: FinalDeliberationRecorder | None = None


def get_deliberation_recorder() -> FinalDeliberationRecorder:
    """Get deliberation recorder instance (singleton).

    Creates the deliberation recorder for Observer API access to final
    deliberation records.
    Per FR135: Final deliberation SHALL be recorded and immutable.
    Per AC7: Observer query access - vote counts, dissent, and reasoning available.

    Uses singleton pattern to share state across requests.

    Returns:
        FinalDeliberationRecorder instance.
    """
    global _deliberation_recorder
    if _deliberation_recorder is None:
        _deliberation_recorder = FinalDeliberationRecorderStub()
    return _deliberation_recorder


# Singleton integrity case service for Observer API queries (Story 7.10, FR144)
_integrity_case_service: IntegrityCaseService | None = None


def get_integrity_case_service() -> IntegrityCaseService:
    """Get integrity case service instance (singleton).

    Creates the integrity case service for Observer API access to the
    Integrity Case Artifact.
    Per FR144: System SHALL maintain published Integrity Case Artifact.
    Per CT-13: MUST remain available after cessation (read-only).

    Uses singleton pattern to share state across requests.

    Returns:
        IntegrityCaseService instance.
    """
    global _integrity_case_service
    if _integrity_case_service is None:
        repository = IntegrityCaseRepositoryStub()
        _integrity_case_service = IntegrityCaseService(repository=repository)
    return _integrity_case_service
