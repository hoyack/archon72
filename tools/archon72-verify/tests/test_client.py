"""Tests for HTTP client (Task 2).

Tests for ObserverClient that fetches events from Observer API.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from archon72_verify.client import ObserverClient


class TestObserverClientInit:
    """Tests for client initialization."""

    def test_default_base_url(self):
        """Verify default base URL is production."""
        client = ObserverClient()
        assert client.base_url == "https://api.archon72.io"

    def test_custom_base_url(self):
        """Verify custom base URL is used."""
        client = ObserverClient(base_url="http://localhost:8000")
        assert client.base_url == "http://localhost:8000"

    def test_custom_timeout(self):
        """Verify custom timeout is set."""
        client = ObserverClient(timeout=60.0)
        assert client._client.timeout.read == 60.0


class TestObserverClientGetEvents:
    """Tests for get_events method."""

    @pytest.mark.asyncio
    async def test_client_fetches_events(self):
        """Verify client fetches events from API."""
        client = ObserverClient(base_url="http://test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"sequence": 1, "event_type": "test"},
                {"sequence": 2, "event_type": "test"},
            ],
            "pagination": {"has_more": False},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            events = await client.get_events(1, 2)

        assert len(events) == 2
        assert events[0]["sequence"] == 1
        assert events[1]["sequence"] == 2

    @pytest.mark.asyncio
    async def test_client_handles_pagination(self):
        """Verify client handles paginated responses."""
        client = ObserverClient(base_url="http://test")

        # First page
        response1 = MagicMock()
        response1.json.return_value = {
            "events": [{"sequence": 1}, {"sequence": 2}],
            "pagination": {"has_more": True},
        }
        response1.raise_for_status = MagicMock()

        # Second page
        response2 = MagicMock()
        response2.json.return_value = {
            "events": [{"sequence": 3}],
            "pagination": {"has_more": False},
        }
        response2.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [response1, response2]
            events = await client.get_events(1, 3, page_size=2)

        assert len(events) == 3
        assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_client_filters_by_sequence_range(self):
        """Verify client filters events by sequence range."""
        client = ObserverClient(base_url="http://test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"sequence": 1},
                {"sequence": 2},
                {"sequence": 3},
                {"sequence": 4},
            ],
            "pagination": {"has_more": False},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            events = await client.get_events(2, 3)

        # Should only include sequences 2 and 3
        assert len(events) == 2
        sequences = [e["sequence"] for e in events]
        assert sequences == [2, 3]


class TestObserverClientGetEventById:
    """Tests for get_event_by_id method."""

    @pytest.mark.asyncio
    async def test_client_fetches_event_by_id(self):
        """Verify client fetches single event by ID."""
        client = ObserverClient(base_url="http://test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "sequence": 1,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            event = await client.get_event_by_id("550e8400-e29b-41d4-a716-446655440000")

        assert event["event_id"] == "550e8400-e29b-41d4-a716-446655440000"
        mock_get.assert_called_once_with(
            "/v1/observer/events/550e8400-e29b-41d4-a716-446655440000"
        )


class TestObserverClientGetVerificationSpec:
    """Tests for get_verification_spec method."""

    @pytest.mark.asyncio
    async def test_client_fetches_verification_spec(self):
        """Verify client fetches verification spec."""
        client = ObserverClient(base_url="http://test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hash_algorithm": "SHA-256",
            "genesis_hash": "0" * 64,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            spec = await client.get_verification_spec()

        assert spec["hash_algorithm"] == "SHA-256"
        mock_get.assert_called_once_with("/v1/observer/verification-spec")


class TestObserverClientContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self):
        """Verify context manager closes client on exit."""
        async with ObserverClient(base_url="http://test") as client:
            assert client is not None
            # Client should be open
            assert not client._client.is_closed

        # After context, client should be closed
        assert client._client.is_closed

    @pytest.mark.asyncio
    async def test_manual_close(self):
        """Verify manual close works."""
        client = ObserverClient(base_url="http://test")
        assert not client._client.is_closed

        await client.close()
        assert client._client.is_closed
