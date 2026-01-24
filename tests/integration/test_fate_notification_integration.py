"""Integration tests for fate notification flow (Story 7.2, FR-7.3).

Tests:
- End-to-end notification flow on fate assignment
- Notification preference storage on submission
- Webhook delivery integration
- Long-poll waiter notification
"""

from datetime import datetime, timezone

import pytest

from src.application.services.fate_notification_service import FateNotificationService
from src.application.services.petition_submission_service import (
    PetitionSubmissionService,
)
from src.domain.models.notification_preference import NotificationChannel
from src.domain.models.petition_submission import PetitionState, PetitionType
from src.infrastructure.stubs.notification_preference_repository_stub import (
    NotificationPreferenceRepositoryStub,
)
from src.infrastructure.stubs.status_token_registry_stub import (
    StatusTokenRegistryStub,
)
from src.infrastructure.stubs.webhook_delivery_adapter_stub import (
    WebhookDeliveryAdapterStub,
)


class MockContentHashService:
    """Mock content hash service."""

    def hash_text(self, text: str) -> bytes:
        # Return 32 bytes for Blake3 hash validation
        import hashlib

        return hashlib.sha256(text.encode()).digest()


class MockRealmRegistry:
    """Mock realm registry."""

    def get_default_realm(self):
        from dataclasses import dataclass

        @dataclass
        class Realm:
            name: str

        return Realm(name="default")

    def get_realm_by_name(self, name: str):
        from dataclasses import dataclass

        @dataclass
        class Realm:
            name: str

        return Realm(name=name) if name == "default" else None


class MockHaltChecker:
    """Mock halt checker."""

    async def is_halted(self) -> bool:
        return False

    async def get_halt_reason(self) -> str | None:
        return None


class MockPetitionRepository:
    """Mock petition submission repository."""

    def __init__(self):
        self._petitions = {}

    async def save(self, petition):
        self._petitions[petition.id] = petition

    async def get(self, petition_id):
        return self._petitions.get(petition_id)

    async def assign_fate_cas(
        self,
        petition_id,
        expected_state,
        new_state,
        fate_reason=None,
        escalation_source=None,
        escalated_to_realm=None,
    ):
        petition = self._petitions.get(petition_id)
        if petition is None:
            raise ValueError(f"Petition not found: {petition_id}")
        if petition.state != expected_state:
            raise ValueError(f"State mismatch: {petition.state} != {expected_state}")
        # Create updated petition
        from src.domain.models.petition_submission import PetitionSubmission

        updated = PetitionSubmission(
            id=petition.id,
            type=petition.type,
            text=petition.text,
            state=new_state,
            submitter_id=petition.submitter_id,
            content_hash=petition.content_hash,
            realm=petition.realm,
            created_at=petition.created_at,
            updated_at=datetime.now(timezone.utc),
            fate_reason=fate_reason,
            escalation_source=escalation_source,
            escalated_to_realm=escalated_to_realm,
        )
        self._petitions[petition_id] = updated
        return updated

    async def update_state(self, petition_id, state):
        petition = self._petitions.get(petition_id)
        if petition:
            from src.domain.models.petition_submission import PetitionSubmission

            updated = PetitionSubmission(
                id=petition.id,
                type=petition.type,
                text=petition.text,
                state=state,
                submitter_id=petition.submitter_id,
                content_hash=petition.content_hash,
                realm=petition.realm,
                created_at=petition.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._petitions[petition_id] = updated


class MockEventEmitter:
    """Mock event emitter."""

    def __init__(self):
        self.events = []

    async def emit_petition_received(self, **kwargs):
        self.events.append(("petition.received", kwargs))
        return True

    async def emit_fate_event(self, **kwargs):
        self.events.append(("petition.fated", kwargs))


class TestFateNotificationIntegration:
    """Integration tests for fate notification flow."""

    @pytest.mark.asyncio
    async def test_full_flow_webhook_notification(self) -> None:
        """Test full flow: submission with preferences, fate assignment, webhook notification."""
        # Setup
        notification_pref_repo = NotificationPreferenceRepositoryStub()
        registry = StatusTokenRegistryStub()
        webhook_adapter = WebhookDeliveryAdapterStub()

        fate_notification_service = FateNotificationService(
            notification_preference_repo=notification_pref_repo,
            status_token_registry=registry,
            webhook_adapter=webhook_adapter,
        )

        petition_repo = MockPetitionRepository()
        event_emitter = MockEventEmitter()

        submission_service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            event_emitter=event_emitter,
            notification_pref_repo=notification_pref_repo,
            fate_notification_service=fate_notification_service,
        )

        # Step 1: Submit petition with webhook preferences
        result = await submission_service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition for notification",
            notification_channel="WEBHOOK",
            notification_webhook_url="https://example.com/webhook",
            notification_enabled=True,
        )

        petition_id = result.petition_id

        # Verify preference was stored
        preference = await notification_pref_repo.get_by_petition_id(petition_id)
        assert preference is not None
        assert preference.channel == NotificationChannel.WEBHOOK
        assert preference.webhook_url == "https://example.com/webhook"

        # Step 2: Assign fate to petition
        updated_petition = await submission_service.assign_fate_transactional(
            petition_id=petition_id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ACKNOWLEDGED,
            actor_id="test-agent",
            reason="Test acknowledgment",
        )

        assert updated_petition.state == PetitionState.ACKNOWLEDGED

        # Step 3: Verify webhook was called
        assert webhook_adapter.get_delivery_count() == 1
        attempts = webhook_adapter.get_attempts()
        assert attempts[0].url == "https://example.com/webhook"
        assert attempts[0].petition_id == petition_id
        assert attempts[0].fate == "ACKNOWLEDGED"
        assert attempts[0].success is True

    @pytest.mark.asyncio
    async def test_fate_assignment_notifies_longpoll_waiters(self) -> None:
        """Test that fate assignment notifies long-poll waiters via registry."""
        # Setup
        notification_pref_repo = NotificationPreferenceRepositoryStub()
        registry = StatusTokenRegistryStub()

        fate_notification_service = FateNotificationService(
            notification_preference_repo=notification_pref_repo,
            status_token_registry=registry,
        )

        petition_repo = MockPetitionRepository()
        event_emitter = MockEventEmitter()

        submission_service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            event_emitter=event_emitter,
            fate_notification_service=fate_notification_service,
        )

        # Submit petition (no notification preferences)
        result = await submission_service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition",
        )

        petition_id = result.petition_id

        # Register initial version in registry
        initial_version = 1
        await registry.register_petition(petition_id, initial_version)

        # Assign fate
        await submission_service.assign_fate_transactional(
            petition_id=petition_id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ESCALATED,
            actor_id="test-agent",
        )

        # Verify registry was updated (new version set)
        current_version = await registry.get_current_version(petition_id)
        # Version changed (computed from new state hash)
        assert current_version is not None
        assert current_version != initial_version

    @pytest.mark.asyncio
    async def test_webhook_failure_schedules_retry(self) -> None:
        """Test that webhook delivery failure schedules a retry."""
        # Setup
        notification_pref_repo = NotificationPreferenceRepositoryStub()
        registry = StatusTokenRegistryStub()
        webhook_adapter = WebhookDeliveryAdapterStub(default_success=False)

        fate_notification_service = FateNotificationService(
            notification_preference_repo=notification_pref_repo,
            status_token_registry=registry,
            webhook_adapter=webhook_adapter,
        )

        petition_repo = MockPetitionRepository()
        event_emitter = MockEventEmitter()

        submission_service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            event_emitter=event_emitter,
            notification_pref_repo=notification_pref_repo,
            fate_notification_service=fate_notification_service,
        )

        # Submit with webhook preference
        result = await submission_service.submit_petition(
            petition_type=PetitionType.GRIEVANCE,
            text="Test grievance petition",
            notification_channel="WEBHOOK",
            notification_webhook_url="https://example.com/failing-webhook",
            notification_enabled=True,
        )

        # Assign fate
        await submission_service.assign_fate_transactional(
            petition_id=result.petition_id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.REFERRED,
            actor_id="test-agent",
        )

        # Webhook was called but failed
        assert webhook_adapter.get_delivery_count() == 1
        failed = webhook_adapter.get_failed_attempts()
        assert len(failed) == 1

        # Retry was scheduled
        assert fate_notification_service.get_pending_retry_count() == 1

    @pytest.mark.asyncio
    async def test_notification_without_preferences(self) -> None:
        """Test fate assignment without notification preferences still updates registry."""
        # Setup
        notification_pref_repo = NotificationPreferenceRepositoryStub()
        registry = StatusTokenRegistryStub()

        fate_notification_service = FateNotificationService(
            notification_preference_repo=notification_pref_repo,
            status_token_registry=registry,
        )

        petition_repo = MockPetitionRepository()
        event_emitter = MockEventEmitter()

        submission_service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            event_emitter=event_emitter,
            fate_notification_service=fate_notification_service,
        )

        # Submit without notification preferences
        result = await submission_service.submit_petition(
            petition_type=PetitionType.CESSATION,
            text="Test cessation petition",
        )

        # Assign fate
        await submission_service.assign_fate_transactional(
            petition_id=result.petition_id,
            expected_state=PetitionState.RECEIVED,
            new_state=PetitionState.ESCALATED,
            actor_id="test-agent",
        )

        # Registry should have been updated
        current_version = await registry.get_current_version(result.petition_id)
        assert current_version is not None


class TestNotificationPreferenceStorage:
    """Tests for notification preference storage on submission."""

    @pytest.mark.asyncio
    async def test_webhook_preference_stored(self) -> None:
        """Test webhook preference is stored on submission."""
        notification_pref_repo = NotificationPreferenceRepositoryStub()
        petition_repo = MockPetitionRepository()

        service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            notification_pref_repo=notification_pref_repo,
        )

        result = await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition",
            notification_channel="WEBHOOK",
            notification_webhook_url="https://example.com/hook",
        )

        preference = await notification_pref_repo.get_by_petition_id(result.petition_id)
        assert preference is not None
        assert preference.channel == NotificationChannel.WEBHOOK
        assert preference.webhook_url == "https://example.com/hook"
        assert preference.enabled is True

    @pytest.mark.asyncio
    async def test_in_app_preference_stored(self) -> None:
        """Test in-app preference is stored on submission."""
        notification_pref_repo = NotificationPreferenceRepositoryStub()
        petition_repo = MockPetitionRepository()

        service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            notification_pref_repo=notification_pref_repo,
        )

        result = await service.submit_petition(
            petition_type=PetitionType.COLLABORATION,
            text="Test collaboration petition",
            notification_channel="IN_APP",
        )

        preference = await notification_pref_repo.get_by_petition_id(result.petition_id)
        assert preference is not None
        assert preference.channel == NotificationChannel.IN_APP
        assert preference.webhook_url is None

    @pytest.mark.asyncio
    async def test_disabled_preference_stored(self) -> None:
        """Test disabled preference is stored on submission."""
        notification_pref_repo = NotificationPreferenceRepositoryStub()
        petition_repo = MockPetitionRepository()

        service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            notification_pref_repo=notification_pref_repo,
        )

        result = await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition",
            notification_channel="WEBHOOK",
            notification_webhook_url="https://example.com/hook",
            notification_enabled=False,
        )

        preference = await notification_pref_repo.get_by_petition_id(result.petition_id)
        assert preference is not None
        assert preference.enabled is False

    @pytest.mark.asyncio
    async def test_no_preference_when_channel_not_specified(self) -> None:
        """Test no preference stored when channel not specified."""
        notification_pref_repo = NotificationPreferenceRepositoryStub()
        petition_repo = MockPetitionRepository()

        service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            notification_pref_repo=notification_pref_repo,
        )

        result = await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition without notification",
        )

        preference = await notification_pref_repo.get_by_petition_id(result.petition_id)
        assert preference is None

    @pytest.mark.asyncio
    async def test_preference_storage_failure_does_not_fail_submission(self) -> None:
        """Test that preference storage failure doesn't fail petition submission."""

        class FailingNotificationPrefRepo:
            """Repository that always fails."""

            async def save(self, preference):
                raise Exception("Storage failure")

            async def get_by_petition_id(self, petition_id):
                return None

        petition_repo = MockPetitionRepository()

        service = PetitionSubmissionService(
            repository=petition_repo,
            hash_service=MockContentHashService(),
            realm_registry=MockRealmRegistry(),
            halt_checker=MockHaltChecker(),
            notification_pref_repo=FailingNotificationPrefRepo(),
        )

        # Should not raise
        result = await service.submit_petition(
            petition_type=PetitionType.GENERAL,
            text="Test petition",
            notification_channel="WEBHOOK",
            notification_webhook_url="https://example.com/hook",
        )

        # Petition should still be created
        assert result.petition_id is not None
        petition = await petition_repo.get(result.petition_id)
        assert petition is not None
