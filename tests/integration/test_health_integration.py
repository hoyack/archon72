"""Integration tests for health endpoint.

These tests verify the health endpoint functionality using ASGI transport
(no container dependencies required).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_health_endpoint_returns_200() -> None:
    """Test health endpoint returns 200 OK."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/health")
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
async def test_health_endpoint_returns_healthy_status() -> None:
    """Test health endpoint returns healthy status in body."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/health")
        data = response.json()
        assert data == {"status": "healthy"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_health_endpoint_content_type() -> None:
    """Test health endpoint returns JSON content type."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/health")
        assert response.headers["content-type"] == "application/json"
