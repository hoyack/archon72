"""Unit tests for NotificationPreferenceRepositoryStub (Story 7.2).

Tests:
- Save and retrieve preferences
- Duplicate prevention
- Update enabled flag
- Delete preferences
- Batch retrieval
- Singleton pattern
"""

from uuid import uuid4

import pytest

from src.application.ports.notification_preference_repository import (
    NotificationPreferenceAlreadyExistsError,
    NotificationPreferenceNotFoundError,
)
from src.domain.models.notification_preference import (
    NotificationPreference,
)
from src.infrastructure.stubs.notification_preference_repository_stub import (
    NotificationPreferenceRepositoryStub,
    get_notification_preference_repository,
    reset_notification_preference_repository,
)


@pytest.fixture
def repository() -> NotificationPreferenceRepositoryStub:
    """Create a fresh repository instance for each test."""
    return NotificationPreferenceRepositoryStub()


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset the singleton before each test."""
    reset_notification_preference_repository()


class TestNotificationPreferenceRepositorySave:
    """Tests for save operation."""

    @pytest.mark.asyncio
    async def test_save_webhook_preference_success(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Save webhook preference succeeds."""
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com/hook",
        )

        await repository.save(pref)

        assert repository.count() == 1

    @pytest.mark.asyncio
    async def test_save_in_app_preference_success(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Save in-app preference succeeds."""
        pref = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=uuid4(),
        )

        await repository.save(pref)

        assert repository.count() == 1

    @pytest.mark.asyncio
    async def test_save_duplicate_raises_error(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Save duplicate preference for same petition raises error."""
        petition_id = uuid4()
        pref1 = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook1",
        )
        pref2 = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook2",
        )

        await repository.save(pref1)

        with pytest.raises(NotificationPreferenceAlreadyExistsError) as exc_info:
            await repository.save(pref2)

        assert exc_info.value.petition_id == petition_id


class TestNotificationPreferenceRepositoryGet:
    """Tests for get_by_petition_id operation."""

    @pytest.mark.asyncio
    async def test_get_existing_preference(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Get existing preference returns it."""
        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
        )
        await repository.save(pref)

        result = await repository.get_by_petition_id(petition_id)

        assert result is not None
        assert result.petition_id == petition_id
        assert result.webhook_url == "https://example.com/hook"

    @pytest.mark.asyncio
    async def test_get_nonexistent_preference_returns_none(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Get nonexistent preference returns None."""
        result = await repository.get_by_petition_id(uuid4())

        assert result is None


class TestNotificationPreferenceRepositoryListByPetitionIds:
    """Tests for list_by_petition_ids operation."""

    @pytest.mark.asyncio
    async def test_list_multiple_preferences(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """List multiple preferences returns matching ones."""
        petition_id_1 = uuid4()
        petition_id_2 = uuid4()
        petition_id_3 = uuid4()

        pref1 = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id_1,
            webhook_url="https://example.com/hook1",
        )
        pref2 = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=petition_id_2,
        )

        await repository.save(pref1)
        await repository.save(pref2)

        result = await repository.list_by_petition_ids(
            [petition_id_1, petition_id_2, petition_id_3]
        )

        assert len(result) == 2
        assert petition_id_1 in result
        assert petition_id_2 in result
        assert petition_id_3 not in result

    @pytest.mark.asyncio
    async def test_list_empty_when_none_exist(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """List returns empty dict when no preferences exist."""
        result = await repository.list_by_petition_ids([uuid4(), uuid4()])

        assert result == {}


class TestNotificationPreferenceRepositoryDelete:
    """Tests for delete operation."""

    @pytest.mark.asyncio
    async def test_delete_existing_preference(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Delete existing preference returns True."""
        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
        )
        await repository.save(pref)

        result = await repository.delete(petition_id)

        assert result is True
        assert repository.count() == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_preference_returns_false(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Delete nonexistent preference returns False."""
        result = await repository.delete(uuid4())

        assert result is False


class TestNotificationPreferenceRepositoryUpdateEnabled:
    """Tests for update_enabled operation."""

    @pytest.mark.asyncio
    async def test_update_enabled_to_false(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Update enabled to False succeeds."""
        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
            enabled=True,
        )
        await repository.save(pref)

        await repository.update_enabled(petition_id, enabled=False)

        result = await repository.get_by_petition_id(petition_id)
        assert result is not None
        assert result.enabled is False

    @pytest.mark.asyncio
    async def test_update_enabled_to_true(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Update enabled to True succeeds."""
        petition_id = uuid4()
        pref = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=petition_id,
            webhook_url="https://example.com/hook",
            enabled=False,
        )
        await repository.save(pref)

        await repository.update_enabled(petition_id, enabled=True)

        result = await repository.get_by_petition_id(petition_id)
        assert result is not None
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_update_enabled_nonexistent_raises_error(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Update enabled for nonexistent preference raises error."""
        petition_id = uuid4()

        with pytest.raises(NotificationPreferenceNotFoundError) as exc_info:
            await repository.update_enabled(petition_id, enabled=False)

        assert exc_info.value.petition_id == petition_id


class TestNotificationPreferenceRepositoryClear:
    """Tests for clear operation."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_preferences(
        self, repository: NotificationPreferenceRepositoryStub
    ) -> None:
        """Clear removes all stored preferences."""
        pref1 = NotificationPreference.create_webhook(
            preference_id=uuid4(),
            petition_id=uuid4(),
            webhook_url="https://example.com/hook1",
        )
        pref2 = NotificationPreference.create_in_app(
            preference_id=uuid4(),
            petition_id=uuid4(),
        )
        await repository.save(pref1)
        await repository.save(pref2)

        assert repository.count() == 2

        await repository.clear()

        assert repository.count() == 0


class TestNotificationPreferenceRepositorySingleton:
    """Tests for singleton pattern."""

    @pytest.mark.asyncio
    async def test_get_singleton_returns_same_instance(self) -> None:
        """get_notification_preference_repository returns singleton."""
        repo1 = await get_notification_preference_repository()
        repo2 = await get_notification_preference_repository()

        assert repo1 is repo2

    @pytest.mark.asyncio
    async def test_reset_creates_new_instance(self) -> None:
        """reset_notification_preference_repository creates new instance."""
        repo1 = await get_notification_preference_repository()
        reset_notification_preference_repository()
        repo2 = await get_notification_preference_repository()

        assert repo1 is not repo2
