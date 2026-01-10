"""Unit tests for DeliberationOutputStub (Story 2.1, Task 6).

Tests:
- Store and retrieve outputs
- Hash verification
- Dev mode watermark

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- AC1: Immediate Output Commitment
- AC2: Hash Verification on View
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.events.deliberation_output import DeliberationOutputPayload


class TestDeliberationOutputStub:
    """Test DeliberationOutputStub implementation."""

    @pytest.mark.asyncio
    async def test_store_output_returns_stored_output(self) -> None:
        """store_output stores and returns StoredOutput."""
        from src.infrastructure.stubs.deliberation_output_stub import (
            DeliberationOutputStub,
        )

        stub = DeliberationOutputStub()

        output_id = uuid4()
        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="a" * 64,
            content_type="text/plain",
            raw_content="Test output",
        )

        result = await stub.store_output(payload, event_sequence=42)

        assert result.output_id == output_id
        assert result.content_hash == "a" * 64
        assert result.event_sequence == 42

    @pytest.mark.asyncio
    async def test_get_output_returns_stored_payload(self) -> None:
        """get_output returns previously stored payload."""
        from src.infrastructure.stubs.deliberation_output_stub import (
            DeliberationOutputStub,
        )

        stub = DeliberationOutputStub()

        output_id = uuid4()
        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="b" * 64,
            content_type="application/json",
            raw_content='{"key": "value"}',
        )

        await stub.store_output(payload, event_sequence=1)
        result = await stub.get_output(output_id)

        assert result is not None
        assert result.output_id == output_id
        assert result.agent_id == "archon-42"
        assert result.raw_content == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_get_output_returns_none_for_not_found(self) -> None:
        """get_output returns None for unknown output_id."""
        from src.infrastructure.stubs.deliberation_output_stub import (
            DeliberationOutputStub,
        )

        stub = DeliberationOutputStub()
        result = await stub.get_output(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_hash_returns_true_for_match(self) -> None:
        """verify_hash returns True when hash matches."""
        from src.infrastructure.stubs.deliberation_output_stub import (
            DeliberationOutputStub,
        )

        stub = DeliberationOutputStub()

        output_id = uuid4()
        content_hash = "c" * 64
        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash=content_hash,
            content_type="text/plain",
            raw_content="Test",
        )

        await stub.store_output(payload, event_sequence=1)
        result = await stub.verify_hash(output_id, content_hash)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_hash_returns_false_for_mismatch(self) -> None:
        """verify_hash returns False when hash doesn't match."""
        from src.infrastructure.stubs.deliberation_output_stub import (
            DeliberationOutputStub,
        )

        stub = DeliberationOutputStub()

        output_id = uuid4()
        payload = DeliberationOutputPayload(
            output_id=output_id,
            agent_id="archon-42",
            content_hash="d" * 64,
            content_type="text/plain",
            raw_content="Test",
        )

        await stub.store_output(payload, event_sequence=1)
        result = await stub.verify_hash(output_id, "e" * 64)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_hash_returns_false_for_not_found(self) -> None:
        """verify_hash returns False for unknown output_id."""
        from src.infrastructure.stubs.deliberation_output_stub import (
            DeliberationOutputStub,
        )

        stub = DeliberationOutputStub()
        result = await stub.verify_hash(uuid4(), "f" * 64)

        assert result is False


class TestDevModeWatermark:
    """Test dev mode watermark pattern."""

    def test_stub_has_dev_mode_watermark(self) -> None:
        """Stub has DEV_MODE_WATERMARK constant."""
        from src.infrastructure.stubs.deliberation_output_stub import (
            DeliberationOutputStub,
        )

        assert hasattr(DeliberationOutputStub, "DEV_MODE_WATERMARK")
        assert "DEV" in DeliberationOutputStub.DEV_MODE_WATERMARK


class TestDeliberationOutputPortCompliance:
    """Test stub implements DeliberationOutputPort."""

    def test_stub_implements_port(self) -> None:
        """Stub is instance of DeliberationOutputPort."""
        from src.application.ports.deliberation_output import DeliberationOutputPort
        from src.infrastructure.stubs.deliberation_output_stub import (
            DeliberationOutputStub,
        )

        stub = DeliberationOutputStub()
        assert isinstance(stub, DeliberationOutputPort)
