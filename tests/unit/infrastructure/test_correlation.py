"""Unit tests for correlation ID management (Story 8.7, AC2).

Tests the correlation ID context management and structlog processor.
"""

import asyncio
import re

import pytest

from src.infrastructure.observability.correlation import (
    correlation_id_processor,
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
)


class TestGenerateCorrelationId:
    """Tests for generate_correlation_id function."""

    @pytest.mark.asyncio
    async def test_generate_returns_uuid_format(self) -> None:
        """Test that generated ID matches UUID4 format (AC2)."""
        correlation_id = generate_correlation_id()

        # UUID4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        assert uuid_pattern.match(correlation_id) is not None

    @pytest.mark.asyncio
    async def test_generate_returns_unique_ids(self) -> None:
        """Test that each call returns a unique ID (AC2)."""
        ids = [generate_correlation_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestCorrelationIdContext:
    """Tests for correlation ID context management."""

    @pytest.mark.asyncio
    async def test_get_returns_empty_string_when_not_set(self) -> None:
        """Test that get returns empty string when no ID is set."""
        # Context should be clean at test start
        # Note: We need to clear context for isolated tests
        set_correlation_id("")
        result = get_correlation_id()
        assert result == ""

    @pytest.mark.asyncio
    async def test_set_and_get_correlation_id(self) -> None:
        """Test that set followed by get returns the same ID (AC2)."""
        test_id = "test-correlation-id-123"
        set_correlation_id(test_id)

        result = get_correlation_id()
        assert result == test_id

        # Clean up
        set_correlation_id("")

    @pytest.mark.asyncio
    async def test_context_isolation_between_tasks(self) -> None:
        """Test that correlation IDs are isolated between async tasks (AC2)."""
        results: dict[str, str] = {}

        async def task_with_id(task_name: str, correlation_id: str) -> None:
            set_correlation_id(correlation_id)
            await asyncio.sleep(0.01)  # Allow context switch
            results[task_name] = get_correlation_id()

        # Run concurrent tasks with different correlation IDs
        await asyncio.gather(
            task_with_id("task1", "id-for-task-1"),
            task_with_id("task2", "id-for-task-2"),
            task_with_id("task3", "id-for-task-3"),
        )

        # Each task should have its own correlation ID preserved
        assert results["task1"] == "id-for-task-1"
        assert results["task2"] == "id-for-task-2"
        assert results["task3"] == "id-for-task-3"

    @pytest.mark.asyncio
    async def test_context_preserved_across_await(self) -> None:
        """Test that correlation ID is preserved across await points (AC2)."""
        test_id = "preserved-across-await"
        set_correlation_id(test_id)

        # Multiple await points
        await asyncio.sleep(0.01)
        first_check = get_correlation_id()
        await asyncio.sleep(0.01)
        second_check = get_correlation_id()
        await asyncio.sleep(0.01)
        third_check = get_correlation_id()

        assert first_check == test_id
        assert second_check == test_id
        assert third_check == test_id

        # Clean up
        set_correlation_id("")


class TestCorrelationIdProcessor:
    """Tests for the structlog correlation ID processor."""

    @pytest.mark.asyncio
    async def test_processor_adds_correlation_id_when_set(self) -> None:
        """Test that processor adds correlation_id to event dict (AC2)."""
        test_id = "processor-test-id"
        set_correlation_id(test_id)

        event_dict: dict[str, object] = {"event": "test_event", "key": "value"}
        result = correlation_id_processor(None, "info", event_dict)

        assert result["correlation_id"] == test_id
        assert result["event"] == "test_event"
        assert result["key"] == "value"

        # Clean up
        set_correlation_id("")

    @pytest.mark.asyncio
    async def test_processor_preserves_existing_fields(self) -> None:
        """Test that processor preserves all existing event dict fields."""
        set_correlation_id("preserve-test")

        event_dict: dict[str, object] = {
            "event": "test_event",
            "timestamp": "2024-01-01",
            "level": "info",
            "service": "test_service",
            "custom_field": 42,
        }
        result = correlation_id_processor(None, "info", event_dict)

        assert result["event"] == "test_event"
        assert result["timestamp"] == "2024-01-01"
        assert result["level"] == "info"
        assert result["service"] == "test_service"
        assert result["custom_field"] == 42
        assert result["correlation_id"] == "preserve-test"

        # Clean up
        set_correlation_id("")

    @pytest.mark.asyncio
    async def test_processor_skips_when_no_correlation_id(self) -> None:
        """Test that processor does not add empty correlation_id."""
        set_correlation_id("")  # Clear any existing

        event_dict: dict[str, object] = {"event": "test_event"}
        result = correlation_id_processor(None, "info", event_dict)

        # correlation_id should not be added when empty
        assert "correlation_id" not in result
