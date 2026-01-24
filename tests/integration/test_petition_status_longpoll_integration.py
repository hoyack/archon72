"""Integration tests for petition status long-poll endpoint (Story 7.1).

Tests cover full request-response cycle through the API:
- Long-poll with valid token
- Immediate return on state change
- Timeout with HTTP 304
- Concurrent long-poll connections
- Cancellation handling
- State change notification across waiters

Constitutional Constraints:
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99 on state change
- CT-13: Reads allowed during halt
- AC2: 30-second timeout with HTTP 304
- AC3: Efficient connection management (no busy-wait)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.dependencies.petition_submission import (
    reset_petition_submission_dependencies,
    set_halt_checker,
    set_petition_submission_repository,
    set_realm_registry,
)
from src.api.routes.petition_submission import router
from src.domain.models.petition_submission import PetitionState
from src.domain.models.status_token import StatusToken
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.realm_registry_stub import RealmRegistryStub
from src.infrastructure.stubs.status_token_registry_stub import (
    get_status_token_registry,
    reset_status_token_registry,
)


@pytest.fixture(autouse=True)
def reset_dependencies():
    """Reset all DI singletons before each test."""
    reset_petition_submission_dependencies()
    reset_status_token_registry()
    yield
    reset_petition_submission_dependencies()
    reset_status_token_registry()


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_repository() -> PetitionSubmissionRepositoryStub:
    """Create mock petition submission repository."""
    return PetitionSubmissionRepositoryStub()


@pytest.fixture
def mock_halt_checker() -> HaltCheckerStub:
    """Create mock halt checker (not halted)."""
    return HaltCheckerStub()


@pytest.fixture
def mock_realm_registry() -> RealmRegistryStub:
    """Create mock realm registry with canonical realms."""
    return RealmRegistryStub(populate_canonical=True)


@pytest.fixture
def configured_app(
    app: FastAPI,
    mock_repository: PetitionSubmissionRepositoryStub,
    mock_halt_checker: HaltCheckerStub,
    mock_realm_registry: RealmRegistryStub,
) -> FastAPI:
    """Configure app with mock services."""
    set_petition_submission_repository(mock_repository)
    set_halt_checker(mock_halt_checker)
    set_realm_registry(mock_realm_registry)
    return app


class TestLongPollIntegration:
    """Integration tests for long-poll full request-response cycle."""

    @pytest.mark.asyncio
    async def test_longpoll_returns_immediately_on_state_change(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Long-poll returns immediately if state changed (AC2, NFR-1.2)."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create a petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            assert submit_response.status_code == 201
            petition_id = UUID(submit_response.json()["petition_id"])

            # Get initial token
            get_response = await client.get(f"/v1/petition-submissions/{petition_id}")
            assert get_response.status_code == 200
            initial_token = get_response.json()["status_token"]

            # Change state
            await mock_repository.update_state(petition_id, PetitionState.DELIBERATING)

            # Long-poll should return immediately with new status
            longpoll_response = await client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": initial_token},
            )

            assert longpoll_response.status_code == 200
            data = longpoll_response.json()
            assert data["state"] == "DELIBERATING"
            assert data["status_token"] != initial_token  # New token

    @pytest.mark.asyncio
    async def test_longpoll_timeout_returns_304(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Long-poll returns HTTP 304 on timeout (AC2)."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create a petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            assert submit_response.status_code == 201
            petition_id = submit_response.json()["petition_id"]

            # Get token
            get_response = await client.get(f"/v1/petition-submissions/{petition_id}")
            token = get_response.json()["status_token"]

            # Patch timeout to be very short for testing
            with patch(
                "src.api.routes.petition_submission.LONGPOLL_TIMEOUT_SECONDS", 0.1
            ):
                longpoll_response = await client.get(
                    f"/v1/petition-submissions/{petition_id}/status",
                    params={"token": token},
                )

            assert longpoll_response.status_code == 304
            assert longpoll_response.headers.get("X-Status-Token") == token


class TestLongPollConcurrentConnections:
    """Integration tests for concurrent long-poll connections (AC3)."""

    @pytest.mark.asyncio
    async def test_multiple_waiters_notified_on_state_change(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Multiple concurrent long-poll connections all receive notification (AC3)."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create a petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            assert submit_response.status_code == 201
            petition_id = UUID(submit_response.json()["petition_id"])

            # Get initial token
            get_response = await client.get(f"/v1/petition-submissions/{petition_id}")
            initial_token = get_response.json()["status_token"]

            # Start multiple concurrent long-poll requests
            num_waiters = 3

            async def longpoll_request():
                return await client.get(
                    f"/v1/petition-submissions/{petition_id}/status",
                    params={"token": initial_token},
                    timeout=5.0,
                )

            # Start long-poll tasks
            tasks = [asyncio.create_task(longpoll_request()) for _ in range(num_waiters)]

            # Give them time to start waiting
            await asyncio.sleep(0.1)

            # Get registry and trigger state change
            registry = await get_status_token_registry()
            # Verify waiters are registered
            assert registry.get_active_waiter_count() >= 1

            # Change state to wake up all waiters
            await mock_repository.update_state(petition_id, PetitionState.DELIBERATING)
            new_version = StatusToken.compute_version_from_hash(None, "DELIBERATING")
            await registry.update_version(petition_id, new_version)

            # All tasks should complete with 200
            responses = await asyncio.gather(*tasks)
            for response in responses:
                assert response.status_code == 200
                assert response.json()["state"] == "DELIBERATING"

    @pytest.mark.asyncio
    async def test_waiter_count_metric_tracks_connections(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Waiter count metric accurately tracks active connections."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create a petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            petition_id = UUID(submit_response.json()["petition_id"])

            # Get token
            get_response = await client.get(f"/v1/petition-submissions/{petition_id}")
            token = get_response.json()["status_token"]

            registry = await get_status_token_registry()
            initial_count = registry.get_active_waiter_count()

            # Start a long-poll that will timeout
            async def longpoll_with_timeout():
                with patch(
                    "src.api.routes.petition_submission.LONGPOLL_TIMEOUT_SECONDS", 0.5
                ):
                    return await client.get(
                        f"/v1/petition-submissions/{petition_id}/status",
                        params={"token": token},
                    )

            task = asyncio.create_task(longpoll_with_timeout())
            await asyncio.sleep(0.1)  # Let it start waiting

            # Count should have increased
            during_count = registry.get_active_waiter_count()
            assert during_count >= initial_count

            # Wait for timeout
            response = await task
            assert response.status_code == 304

            # Count should return to initial
            await asyncio.sleep(0.1)  # Let cleanup happen
            final_count = registry.get_active_waiter_count()
            assert final_count == initial_count


class TestLongPollCancellation:
    """Integration tests for long-poll cancellation handling."""

    @pytest.mark.asyncio
    async def test_cancelled_request_cleans_up_waiter(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Cancelled long-poll request properly cleans up waiter count."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create a petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            petition_id = UUID(submit_response.json()["petition_id"])

            # Get token
            get_response = await client.get(f"/v1/petition-submissions/{petition_id}")
            token = get_response.json()["status_token"]

            registry = await get_status_token_registry()
            initial_count = registry.get_active_waiter_count()

            # Start a long-poll that we'll cancel
            async def longpoll_long_wait():
                with patch(
                    "src.api.routes.petition_submission.LONGPOLL_TIMEOUT_SECONDS", 60.0
                ):
                    return await client.get(
                        f"/v1/petition-submissions/{petition_id}/status",
                        params={"token": token},
                    )

            task = asyncio.create_task(longpoll_long_wait())
            await asyncio.sleep(0.1)  # Let it start waiting

            # Cancel the task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Wait for cleanup
            await asyncio.sleep(0.1)

            # Waiter count should return to initial
            final_count = registry.get_active_waiter_count()
            assert final_count == initial_count


class TestLongPollHaltIntegration:
    """Integration tests for long-poll during halt (CT-13)."""

    @pytest.mark.asyncio
    async def test_longpoll_works_during_halt(
        self,
        app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
        mock_realm_registry: RealmRegistryStub,
    ) -> None:
        """Long-poll works during system halt - reads allowed (CT-13)."""
        # Create petition while not halted
        not_halted = HaltCheckerStub()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(not_halted)
        set_realm_registry(mock_realm_registry)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            petition_id = UUID(submit_response.json()["petition_id"])

            # Get token
            get_response = await client.get(f"/v1/petition-submissions/{petition_id}")
            token = get_response.json()["status_token"]

            # Change state before halt
            await mock_repository.update_state(petition_id, PetitionState.DELIBERATING)

        # Now halt system
        halted_checker = HaltCheckerStub()
        halted_checker.set_halted(True, "Test halt")
        reset_petition_submission_dependencies()
        set_petition_submission_repository(mock_repository)
        set_halt_checker(halted_checker)
        set_realm_registry(mock_realm_registry)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Long-poll should still work (CT-13: reads allowed)
            longpoll_response = await client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": token},
            )

            assert longpoll_response.status_code == 200
            assert longpoll_response.json()["state"] == "DELIBERATING"


class TestLongPollTokenValidation:
    """Integration tests for token validation in long-poll endpoint."""

    @pytest.mark.asyncio
    async def test_invalid_token_returns_400(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Long-poll with invalid token returns 400 (D7)."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create a petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            petition_id = submit_response.json()["petition_id"]

            response = await client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": "invalid_base64_token!!!"},
            )
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert detail["type"] == "https://archon72.io/errors/invalid-status-token"
            assert detail["status"] == 400

    @pytest.mark.asyncio
    async def test_expired_token_returns_400(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Long-poll with expired token returns 400."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create a petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            petition_id = UUID(submit_response.json()["petition_id"])

            # Create an old token manually
            old_time = datetime.now(timezone.utc) - timedelta(seconds=600)
            old_token = StatusToken(
                petition_id=petition_id, version=1, created_at=old_time
            )
            token_str = old_token.encode()

            response = await client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": token_str},
            )
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert detail["type"] == "https://archon72.io/errors/expired-status-token"
            assert "max_age_seconds" in detail

    @pytest.mark.asyncio
    async def test_wrong_petition_id_returns_400(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Long-poll with token for different petition returns 400."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create first petition
            submit1 = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition 1"},
            )
            petition_id_1 = UUID(submit1.json()["petition_id"])

            # Create second petition
            submit2 = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition 2"},
            )
            petition_id_2 = submit2.json()["petition_id"]

            # Get token for petition 1
            get_response = await client.get(f"/v1/petition-submissions/{petition_id_1}")
            token_for_1 = get_response.json()["status_token"]

            # Try to use token for petition 2
            response = await client.get(
                f"/v1/petition-submissions/{petition_id_2}/status",
                params={"token": token_for_1},
            )
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert "mismatch" in detail["detail"].lower()

    @pytest.mark.asyncio
    async def test_petition_not_found_returns_404(
        self,
        configured_app: FastAPI,
    ) -> None:
        """Long-poll for nonexistent petition returns 404."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            fake_id = uuid4()
            # Create a valid token for the fake ID
            token = StatusToken.create(petition_id=fake_id, version=1)
            token_str = token.encode()

            response = await client.get(
                f"/v1/petition-submissions/{fake_id}/status",
                params={"token": token_str},
            )
            assert response.status_code == 404
            detail = response.json()["detail"]
            assert detail["type"] == "https://archon72.io/errors/petition-not-found"


class TestLongPollResponseContent:
    """Integration tests for response content completeness."""

    @pytest.mark.asyncio
    async def test_immediate_return_includes_all_fields(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """Immediate return includes all status response fields."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create a petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            petition_id = UUID(submit_response.json()["petition_id"])

            # Get initial token
            get_response = await client.get(f"/v1/petition-submissions/{petition_id}")
            initial_token = get_response.json()["status_token"]

            # Change state
            await mock_repository.update_state(petition_id, PetitionState.DELIBERATING)

            # Long-poll
            longpoll_response = await client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": initial_token},
            )

            assert longpoll_response.status_code == 200
            data = longpoll_response.json()
            # Verify all required fields
            assert "petition_id" in data
            assert "state" in data
            assert "type" in data
            assert "realm" in data
            assert "co_signer_count" in data
            assert "created_at" in data
            assert "updated_at" in data
            assert "status_token" in data

    @pytest.mark.asyncio
    async def test_new_token_generated_on_state_change(
        self,
        configured_app: FastAPI,
        mock_repository: PetitionSubmissionRepositoryStub,
    ) -> None:
        """New token is generated when state changes (FR-7.2)."""
        async with AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        ) as client:
            # Create petition
            submit_response = await client.post(
                "/v1/petition-submissions",
                json={"type": "GENERAL", "text": "Test petition"},
            )
            petition_id = UUID(submit_response.json()["petition_id"])

            # Get initial token
            get_response = await client.get(f"/v1/petition-submissions/{petition_id}")
            initial_token = get_response.json()["status_token"]

            # Change state
            await mock_repository.update_state(petition_id, PetitionState.DELIBERATING)

            # Long-poll
            longpoll_response = await client.get(
                f"/v1/petition-submissions/{petition_id}/status",
                params={"token": initial_token},
            )

            new_token = longpoll_response.json()["status_token"]
            assert new_token != initial_token

            # Decode and verify new token has new version
            decoded_initial = StatusToken.decode(initial_token)
            decoded_new = StatusToken.decode(new_token)
            assert decoded_new.version != decoded_initial.version
