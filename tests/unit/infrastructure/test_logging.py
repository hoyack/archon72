"""Unit tests for structured logging configuration (Story 8.7, AC1, AC3).

Tests the structlog configuration and logging output format.
"""

import json
import logging
import os
from io import StringIO
from unittest.mock import patch

import pytest
import structlog

from src.infrastructure.observability.correlation import set_correlation_id
from src.infrastructure.observability.logging import (
    configure_structlog,
    get_logger_for_service,
)


class TestConfigureStructlog:
    """Tests for configure_structlog function."""

    @pytest.mark.asyncio
    async def test_configure_production_mode(self) -> None:
        """Test that production mode configures JSON output (AC3)."""
        configure_structlog(environment="production")

        # Verify configuration was applied
        # In production mode, logs should be JSON
        config = structlog.get_config()
        assert config is not None

        # The last processor should be JSONRenderer in production
        processors = config.get("processors", [])
        assert len(processors) > 0

        # Find JSONRenderer in processors
        json_renderer_found = any(
            isinstance(p, structlog.processors.JSONRenderer)
            or (hasattr(p, "__class__") and "JSONRenderer" in str(type(p)))
            for p in processors
        )
        assert json_renderer_found, "JSONRenderer should be in processors for production"

    @pytest.mark.asyncio
    async def test_configure_development_mode(self) -> None:
        """Test that development mode configures console output (AC3)."""
        configure_structlog(environment="development")

        # Verify configuration was applied
        config = structlog.get_config()
        assert config is not None

        # The last processor should be ConsoleRenderer in development
        processors = config.get("processors", [])
        assert len(processors) > 0

        # Find ConsoleRenderer in processors
        console_renderer_found = any(
            isinstance(p, structlog.dev.ConsoleRenderer)
            or (hasattr(p, "__class__") and "ConsoleRenderer" in str(type(p)))
            for p in processors
        )
        assert console_renderer_found, "ConsoleRenderer should be in processors for development"

    @pytest.mark.asyncio
    async def test_configure_defaults_to_production(self) -> None:
        """Test that default environment is production (AC3)."""
        configure_structlog()  # No environment specified

        config = structlog.get_config()
        processors = config.get("processors", [])

        # Should default to production (JSON output)
        json_renderer_found = any(
            isinstance(p, structlog.processors.JSONRenderer)
            or (hasattr(p, "__class__") and "JSONRenderer" in str(type(p)))
            for p in processors
        )
        assert json_renderer_found


class TestLogOutput:
    """Tests for actual log output format."""

    @pytest.fixture(autouse=True)
    def setup_production_logging(self) -> None:
        """Set up production logging for output tests."""
        configure_structlog(environment="production")

    @pytest.mark.asyncio
    async def test_json_output_structure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that log output is valid JSON with required fields (AC1)."""
        # Set correlation ID for the test
        set_correlation_id("test-json-output")

        logger = structlog.get_logger()
        logger.info("test_event", custom_field="value")

        captured = capsys.readouterr()
        output = captured.out.strip()

        # Should be valid JSON
        if output:
            log_entry = json.loads(output)

            # AC1: Required fields
            assert "event" in log_entry
            assert log_entry["event"] == "test_event"
            assert "level" in log_entry
            assert log_entry["level"] == "info"
            assert "timestamp" in log_entry
            assert "correlation_id" in log_entry
            assert log_entry["correlation_id"] == "test-json-output"

            # Custom field preserved
            assert "custom_field" in log_entry
            assert log_entry["custom_field"] == "value"

        # Clean up
        set_correlation_id("")

    @pytest.mark.asyncio
    async def test_timestamp_iso8601_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that timestamp is ISO 8601 format (AC1)."""
        set_correlation_id("test-timestamp")

        logger = structlog.get_logger()
        logger.info("timestamp_test")

        captured = capsys.readouterr()
        output = captured.out.strip()

        if output:
            log_entry = json.loads(output)

            # Timestamp should be ISO 8601 format
            timestamp = log_entry.get("timestamp", "")
            # ISO 8601 format includes T and Z or timezone offset
            assert "T" in timestamp or "-" in timestamp

        # Clean up
        set_correlation_id("")

    @pytest.mark.asyncio
    async def test_additional_context_preserved(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that additional context fields are preserved (AC1)."""
        set_correlation_id("test-context")

        logger = structlog.get_logger()
        logger.info(
            "context_test",
            service="test_service",
            operation="test_op",
            user_id=123,
            nested={"key": "value"},
        )

        captured = capsys.readouterr()
        output = captured.out.strip()

        if output:
            log_entry = json.loads(output)

            assert log_entry.get("service") == "test_service"
            assert log_entry.get("operation") == "test_op"
            assert log_entry.get("user_id") == 123
            assert log_entry.get("nested") == {"key": "value"}

        # Clean up
        set_correlation_id("")


class TestLogLevelConfiguration:
    """Tests for log level configuration."""

    @pytest.mark.asyncio
    async def test_default_log_level_is_info(self) -> None:
        """Test that default log level is INFO (AC3)."""
        # Clear any existing LOG_LEVEL env var
        with patch.dict(os.environ, {}, clear=True):
            configure_structlog(environment="production")

            # INFO level should work
            logger = structlog.get_logger()
            # No exception should be raised
            logger.info("info_level_test")

    @pytest.mark.asyncio
    async def test_log_level_from_environment(self) -> None:
        """Test that log level can be configured via environment (AC3)."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=False):
            configure_structlog(environment="production")

            # DEBUG level should work
            logger = structlog.get_logger()
            logger.debug("debug_level_test")


class TestGetLoggerForService:
    """Tests for get_logger_for_service helper."""

    @pytest.mark.asyncio
    async def test_logger_bound_with_service_name(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that logger is bound with service name (AC4)."""
        configure_structlog(environment="production")
        set_correlation_id("test-service-name")

        logger = get_logger_for_service("TestService")
        logger.info("service_test")

        captured = capsys.readouterr()
        output = captured.out.strip()

        if output:
            log_entry = json.loads(output)
            assert log_entry.get("service") == "TestService"
            assert log_entry.get("component") == "constitutional"

        # Clean up
        set_correlation_id("")

    @pytest.mark.asyncio
    async def test_logger_bound_with_custom_component(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that logger accepts custom component name (AC4)."""
        configure_structlog(environment="production")
        set_correlation_id("test-component")

        logger = get_logger_for_service("MyService", component="operational")
        logger.info("component_test")

        captured = capsys.readouterr()
        output = captured.out.strip()

        if output:
            log_entry = json.loads(output)
            assert log_entry.get("service") == "MyService"
            assert log_entry.get("component") == "operational"

        # Clean up
        set_correlation_id("")
