"""Unit tests for ContactPreventionService.

Story: consent-gov-7.4: Follow-Up Contact Prevention

Tests:
- Block on exit functionality
- Violation detection and recording
- Event emission
- Structural prohibition (no win-back methods)
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.application.services.governance.contact_prevention_service import (
    ContactPreventionService,
)
from src.domain.governance.exit.contact_block import ContactBlock
from src.domain.governance.exit.contact_block_status import ContactBlockStatus
from src.domain.governance.exit.contact_violation import ContactViolation


class FakeContactBlockPort:
    """Fake contact block port for testing."""

    def __init__(self) -> None:
        self._blocks: dict[UUID, ContactBlock] = {}

    async def add_block(self, block: ContactBlock) -> None:
        """Add a contact block."""
        if block.cluster_id in self._blocks:
            raise ValueError(f"Block already exists for cluster: {block.cluster_id}")
        self._blocks[block.cluster_id] = block

    async def is_blocked(self, cluster_id: UUID) -> bool:
        """Check if cluster is blocked."""
        return cluster_id in self._blocks

    async def get_block(self, cluster_id: UUID) -> ContactBlock | None:
        """Get block for cluster."""
        return self._blocks.get(cluster_id)

    async def get_all_blocked(self) -> list[UUID]:
        """Get all blocked cluster IDs."""
        return list(self._blocks.keys())


class FakeEventEmitter:
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        """Record emitted event."""
        self.events.append({
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
        })

    def get_events(self, event_type: str | None = None) -> list[dict]:
        """Get recorded events, optionally filtered by type."""
        if event_type is None:
            return self.events
        return [e for e in self.events if e["event_type"] == event_type]

    def get_last(self, event_type: str) -> dict | None:
        """Get most recent event of given type."""
        events = self.get_events(event_type)
        return events[-1] if events else None


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        """Return fixed time."""
        return self._time

    def set_time(self, time: datetime) -> None:
        """Set the fixed time."""
        self._time = time


@pytest.fixture
def contact_block_port() -> FakeContactBlockPort:
    """Create fake contact block port."""
    return FakeContactBlockPort()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Create fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Create fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def prevention_service(
    contact_block_port: FakeContactBlockPort,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> ContactPreventionService:
    """Create contact prevention service with fakes."""
    return ContactPreventionService(
        contact_block_port=contact_block_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


class TestBlockOnExit:
    """Tests for block_on_exit functionality."""

    @pytest.mark.asyncio
    async def test_block_on_exit_creates_block(
        self,
        prevention_service: ContactPreventionService,
        contact_block_port: FakeContactBlockPort,
    ):
        """block_on_exit creates a permanent block."""
        cluster_id = uuid4()

        block = await prevention_service.block_on_exit(cluster_id)

        assert block.cluster_id == cluster_id
        assert block.status == ContactBlockStatus.PERMANENTLY_BLOCKED
        assert block.reason == "exit"

    @pytest.mark.asyncio
    async def test_block_on_exit_persists_block(
        self,
        prevention_service: ContactPreventionService,
        contact_block_port: FakeContactBlockPort,
    ):
        """block_on_exit persists the block to port."""
        cluster_id = uuid4()

        await prevention_service.block_on_exit(cluster_id)

        assert await contact_block_port.is_blocked(cluster_id)

    @pytest.mark.asyncio
    async def test_block_on_exit_emits_event(
        self,
        prevention_service: ContactPreventionService,
        event_emitter: FakeEventEmitter,
    ):
        """block_on_exit emits custodial.contact.blocked event."""
        cluster_id = uuid4()

        await prevention_service.block_on_exit(cluster_id)

        event = event_emitter.get_last("custodial.contact.blocked")
        assert event is not None
        assert event["actor"] == "system"
        assert event["payload"]["cluster_id"] == str(cluster_id)
        assert event["payload"]["reason"] == "exit"
        assert event["payload"]["permanent"] is True

    @pytest.mark.asyncio
    async def test_block_on_exit_uses_time_authority(
        self,
        prevention_service: ContactPreventionService,
        time_authority: FakeTimeAuthority,
    ):
        """block_on_exit uses time authority for timestamp."""
        fixed_time = datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
        time_authority.set_time(fixed_time)

        cluster_id = uuid4()
        block = await prevention_service.block_on_exit(cluster_id)

        assert block.blocked_at == fixed_time


class TestIsBlocked:
    """Tests for is_blocked functionality."""

    @pytest.mark.asyncio
    async def test_is_blocked_returns_false_for_unblocked(
        self,
        prevention_service: ContactPreventionService,
    ):
        """is_blocked returns False for non-blocked cluster."""
        assert not await prevention_service.is_blocked(uuid4())

    @pytest.mark.asyncio
    async def test_is_blocked_returns_true_after_exit(
        self,
        prevention_service: ContactPreventionService,
    ):
        """is_blocked returns True after block_on_exit."""
        cluster_id = uuid4()

        await prevention_service.block_on_exit(cluster_id)

        assert await prevention_service.is_blocked(cluster_id)


class TestGetBlock:
    """Tests for get_block functionality."""

    @pytest.mark.asyncio
    async def test_get_block_returns_none_for_unblocked(
        self,
        prevention_service: ContactPreventionService,
    ):
        """get_block returns None for non-blocked cluster."""
        assert await prevention_service.get_block(uuid4()) is None

    @pytest.mark.asyncio
    async def test_get_block_returns_block_after_exit(
        self,
        prevention_service: ContactPreventionService,
    ):
        """get_block returns block after block_on_exit."""
        cluster_id = uuid4()

        original = await prevention_service.block_on_exit(cluster_id)
        retrieved = await prevention_service.get_block(cluster_id)

        assert retrieved == original


class TestRecordContactAttempt:
    """Tests for record_contact_attempt functionality."""

    @pytest.mark.asyncio
    async def test_record_contact_attempt_returns_violation(
        self,
        prevention_service: ContactPreventionService,
    ):
        """record_contact_attempt returns a ContactViolation."""
        cluster_id = uuid4()
        await prevention_service.block_on_exit(cluster_id)

        violation = await prevention_service.record_contact_attempt(
            cluster_id=cluster_id,
            attempted_by="MessageRouter",
        )

        assert isinstance(violation, ContactViolation)
        assert violation.cluster_id == cluster_id
        assert violation.attempted_by == "MessageRouter"
        assert violation.blocked is True

    @pytest.mark.asyncio
    async def test_record_contact_attempt_emits_violation_event(
        self,
        prevention_service: ContactPreventionService,
        event_emitter: FakeEventEmitter,
    ):
        """record_contact_attempt emits violation event."""
        cluster_id = uuid4()
        await prevention_service.block_on_exit(cluster_id)

        await prevention_service.record_contact_attempt(
            cluster_id=cluster_id,
            attempted_by="NotificationService",
        )

        event = event_emitter.get_last("constitutional.violation.contact_attempt")
        assert event is not None
        assert event["actor"] == "NotificationService"
        assert event["payload"]["cluster_id"] == str(cluster_id)
        assert event["payload"]["blocked"] is True
        assert event["payload"]["violation_type"] == "nfr_exit_02_contact_after_exit"

    @pytest.mark.asyncio
    async def test_record_contact_attempt_uses_time_authority(
        self,
        prevention_service: ContactPreventionService,
        time_authority: FakeTimeAuthority,
    ):
        """record_contact_attempt uses time authority."""
        fixed_time = datetime(2026, 1, 17, 14, 30, 0, tzinfo=timezone.utc)
        time_authority.set_time(fixed_time)

        cluster_id = uuid4()

        violation = await prevention_service.record_contact_attempt(
            cluster_id=cluster_id,
            attempted_by="API",
        )

        assert violation.attempted_at == fixed_time

    @pytest.mark.asyncio
    async def test_record_contact_attempt_various_components(
        self,
        prevention_service: ContactPreventionService,
        event_emitter: FakeEventEmitter,
    ):
        """record_contact_attempt records different component names."""
        cluster_id = uuid4()
        components = [
            "MessageRouter",
            "NotificationService",
            "API:/cluster/{id}/message",
            "EmailService",
            "TaskReminderService",
        ]

        for component in components:
            violation = await prevention_service.record_contact_attempt(
                cluster_id=cluster_id,
                attempted_by=component,
            )
            assert violation.attempted_by == component


class TestGetAllBlockedClusters:
    """Tests for get_all_blocked_clusters functionality."""

    @pytest.mark.asyncio
    async def test_get_all_blocked_clusters_empty_initially(
        self,
        prevention_service: ContactPreventionService,
    ):
        """get_all_blocked_clusters returns empty list initially."""
        blocked = await prevention_service.get_all_blocked_clusters()
        assert blocked == []

    @pytest.mark.asyncio
    async def test_get_all_blocked_clusters_returns_all(
        self,
        prevention_service: ContactPreventionService,
    ):
        """get_all_blocked_clusters returns all blocked IDs."""
        cluster_ids = [uuid4() for _ in range(5)]

        for cluster_id in cluster_ids:
            await prevention_service.block_on_exit(cluster_id)

        blocked = await prevention_service.get_all_blocked_clusters()

        assert len(blocked) == 5
        assert set(blocked) == set(cluster_ids)


class TestStructuralProhibition:
    """Tests verifying structural prohibition - no win-back methods.

    NFR-EXIT-02: No follow-up contact mechanism may exist.
    """

    def test_no_unblock_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service has no unblock method."""
        assert not hasattr(prevention_service, "unblock")

    def test_no_remove_block_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service has no remove_block method."""
        assert not hasattr(prevention_service, "remove_block")

    def test_no_send_to_exited_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service has no send_to_exited method."""
        assert not hasattr(prevention_service, "send_to_exited")

    def test_no_winback_message_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service has no winback_message method."""
        assert not hasattr(prevention_service, "winback_message")

    def test_no_reengagement_campaign_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service has no reengagement_campaign method."""
        assert not hasattr(prevention_service, "reengagement_campaign")

    def test_no_come_back_notification_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service has no come_back_notification method."""
        assert not hasattr(prevention_service, "come_back_notification")

    def test_no_we_miss_you_email_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service has no we_miss_you_email method."""
        assert not hasattr(prevention_service, "we_miss_you_email")

    def test_no_tasks_waiting_reminder_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service has no tasks_waiting_reminder method."""
        assert not hasattr(prevention_service, "tasks_waiting_reminder")


class TestNoWinBackCapability:
    """Additional tests ensuring no capability for win-back patterns."""

    def test_service_has_only_allowed_public_methods(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Service only has approved public methods.

        Allowed methods:
        - block_on_exit
        - is_blocked
        - get_block
        - record_contact_attempt
        - get_all_blocked_clusters

        No other methods should exist that could be used for contact.
        """
        allowed_methods = {
            "block_on_exit",
            "is_blocked",
            "get_block",
            "record_contact_attempt",
            "get_all_blocked_clusters",
        }

        # Get all public methods (not starting with _)
        public_methods = {
            name for name in dir(prevention_service)
            if not name.startswith("_") and callable(getattr(prevention_service, name))
        }

        # The public methods should be exactly the allowed set
        assert public_methods == allowed_methods, (
            f"Unexpected methods found: {public_methods - allowed_methods}"
        )

    @pytest.mark.asyncio
    async def test_block_is_permanent(
        self,
        prevention_service: ContactPreventionService,
    ):
        """Once blocked, cluster stays blocked forever.

        There is no way to unblock because:
        1. No unblock method exists
        2. Blocks cannot be removed from storage
        3. Block status is PERMANENTLY_BLOCKED only
        """
        cluster_id = uuid4()

        # Block the cluster
        await prevention_service.block_on_exit(cluster_id)

        # Verify blocked
        assert await prevention_service.is_blocked(cluster_id)

        # There is literally no code path to unblock
        # because no unblock method exists
        # This test documents that permanence is structural


class TestReEngagementPath:
    """Tests documenting the one-way re-engagement path.

    Re-engagement requires new initiation from Cluster.
    System cannot initiate contact with exited Cluster.
    """

    @pytest.mark.asyncio
    async def test_system_cannot_reach_exited_cluster(
        self,
        prevention_service: ContactPreventionService,
    ):
        """System has no method to contact exited cluster."""
        cluster_id = uuid4()
        await prevention_service.block_on_exit(cluster_id)

        # There is no method like:
        # await prevention_service.send_message(cluster_id, "come back!")
        # await prevention_service.notify(cluster_id, "we miss you")
        #
        # These methods don't exist - structural prohibition

        # The only interaction possible is checking blocked status
        # and recording violations when contact is attempted
        assert await prevention_service.is_blocked(cluster_id)

    @pytest.mark.asyncio
    async def test_violation_recorded_not_delivered(
        self,
        prevention_service: ContactPreventionService,
        event_emitter: FakeEventEmitter,
    ):
        """Contact attempts record violations, not deliveries.

        When contact is attempted to an exited cluster:
        - Contact is BLOCKED (always)
        - Violation is RECORDED (for Knight observation)
        - Message is NOT DELIVERED (structural)
        """
        cluster_id = uuid4()
        await prevention_service.block_on_exit(cluster_id)

        # Simulate a contact attempt being blocked by infrastructure
        violation = await prevention_service.record_contact_attempt(
            cluster_id=cluster_id,
            attempted_by="MessageRouter",
        )

        # Contact was blocked
        assert violation.blocked is True

        # Violation was recorded for observability
        event = event_emitter.get_last("constitutional.violation.contact_attempt")
        assert event is not None

        # No "message delivered" event exists - by design
        delivered_events = event_emitter.get_events("message.delivered")
        assert len(delivered_events) == 0
