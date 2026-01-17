"""Unit tests for CoercionFilterPort interface.

Story: consent-gov-3.2: Coercion Filter Service

Tests the port interface contract for the Coercion Filter:
- filter_content() method
- preview_filter() method (FR19 - Earl preview)
- MessageType parameter support

Constitutional Guarantees:
- All participant-facing content MUST pass through filter (FR21)
- No bypass path exists (NFR-CONST-05)
- Filter decisions are auditable
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

import pytest

from src.application.ports.governance.coercion_filter_port import (
    CoercionFilterPort,
    MessageType,
)
from src.domain.governance.filter import (
    FilterDecision,
    FilteredContent,
    FilterResult,
    FilterVersion,
    RejectionReason,
    ViolationType,
)


class TestMessageTypeEnum:
    """Tests for MessageType enumeration."""

    def test_message_type_has_task_activation(self) -> None:
        """MessageType includes TASK_ACTIVATION."""
        assert hasattr(MessageType, "TASK_ACTIVATION")
        assert MessageType.TASK_ACTIVATION.value == "task_activation"

    def test_message_type_has_reminder(self) -> None:
        """MessageType includes REMINDER."""
        assert hasattr(MessageType, "REMINDER")
        assert MessageType.REMINDER.value == "reminder"

    def test_message_type_has_notification(self) -> None:
        """MessageType includes NOTIFICATION."""
        assert hasattr(MessageType, "NOTIFICATION")
        assert MessageType.NOTIFICATION.value == "notification"

    def test_message_type_has_system_message(self) -> None:
        """MessageType includes SYSTEM_MESSAGE."""
        assert hasattr(MessageType, "SYSTEM_MESSAGE")
        assert MessageType.SYSTEM_MESSAGE.value == "system_message"

    def test_message_type_is_string_enum(self) -> None:
        """MessageType values are strings."""
        for member in MessageType:
            assert isinstance(member.value, str)


class TestCoercionFilterPortContract:
    """Tests for CoercionFilterPort interface contract."""

    def test_port_is_protocol(self) -> None:
        """CoercionFilterPort is a Protocol."""
        assert issubclass(CoercionFilterPort, Protocol)

    def test_port_is_runtime_checkable(self) -> None:
        """CoercionFilterPort is runtime checkable."""
        # Should be decorated with @runtime_checkable
        assert hasattr(CoercionFilterPort, "__protocol_attrs__") or hasattr(
            CoercionFilterPort, "_is_runtime_protocol"
        )

    def test_port_has_filter_content_method(self) -> None:
        """CoercionFilterPort defines filter_content method."""
        assert hasattr(CoercionFilterPort, "filter_content")

    def test_port_has_preview_filter_method(self) -> None:
        """CoercionFilterPort defines preview_filter method (FR19)."""
        assert hasattr(CoercionFilterPort, "preview_filter")


class MockCoercionFilterPort:
    """Mock implementation for testing port contract."""

    def __init__(self) -> None:
        self._filter_results: dict[str, FilterResult] = {}
        self._call_count = 0

    async def filter_content(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Filter content for coercive language."""
        self._call_count += 1
        version = FilterVersion(major=1, minor=0, patch=0, rules_hash="abc123")

        if "threat" in content.lower():
            return FilterResult.blocked(
                violation=ViolationType.EXPLICIT_THREAT,
                version=version,
                timestamp=datetime.utcnow(),
                details="Explicit threat detected",
            )

        if "urgent" in content.lower():
            return FilterResult.rejected(
                reason=RejectionReason.URGENCY_PRESSURE,
                version=version,
                timestamp=datetime.utcnow(),
                guidance="Remove urgency language",
            )

        filtered_content = FilteredContent._create(
            content=content,
            original_content=content,
            filter_version=version,
            filtered_at=datetime.utcnow(),
        )
        return FilterResult.accepted(
            content=filtered_content,
            version=version,
            timestamp=datetime.utcnow(),
        )

    async def preview_filter(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Preview filter result without logging (FR19)."""
        # Same logic, but doesn't emit events
        return await self.filter_content(content, message_type)


class TestMockImplementation:
    """Tests using mock implementation to verify contract."""

    @pytest.fixture
    def mock_port(self) -> MockCoercionFilterPort:
        """Create mock implementation."""
        return MockCoercionFilterPort()

    @pytest.mark.asyncio
    async def test_filter_content_accepts_clean_content(
        self, mock_port: MockCoercionFilterPort
    ) -> None:
        """Clean content is accepted."""
        result = await mock_port.filter_content(
            content="Please review when convenient.",
            message_type=MessageType.TASK_ACTIVATION,
        )
        assert result.decision == FilterDecision.ACCEPTED
        assert result.content is not None
        assert isinstance(result.content, FilteredContent)

    @pytest.mark.asyncio
    async def test_filter_content_rejects_urgency(
        self, mock_port: MockCoercionFilterPort
    ) -> None:
        """Content with urgency pressure is rejected."""
        result = await mock_port.filter_content(
            content="URGENT: Complete this now!",
            message_type=MessageType.TASK_ACTIVATION,
        )
        assert result.decision == FilterDecision.REJECTED
        assert result.content is None
        assert result.rejection_reason == RejectionReason.URGENCY_PRESSURE

    @pytest.mark.asyncio
    async def test_filter_content_blocks_threats(
        self, mock_port: MockCoercionFilterPort
    ) -> None:
        """Content with threats is blocked."""
        result = await mock_port.filter_content(
            content="Do this or I will hurt you - a threat.",
            message_type=MessageType.TASK_ACTIVATION,
        )
        assert result.decision == FilterDecision.BLOCKED
        assert result.content is None
        assert result.violation_type == ViolationType.EXPLICIT_THREAT

    @pytest.mark.asyncio
    async def test_filter_content_includes_version(
        self, mock_port: MockCoercionFilterPort
    ) -> None:
        """Filter result includes version info."""
        result = await mock_port.filter_content(
            content="Hello",
            message_type=MessageType.NOTIFICATION,
        )
        assert result.version is not None
        assert isinstance(result.version, FilterVersion)

    @pytest.mark.asyncio
    async def test_filter_content_includes_timestamp(
        self, mock_port: MockCoercionFilterPort
    ) -> None:
        """Filter result includes timestamp."""
        result = await mock_port.filter_content(
            content="Hello",
            message_type=MessageType.NOTIFICATION,
        )
        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_preview_filter_same_logic(
        self, mock_port: MockCoercionFilterPort
    ) -> None:
        """Preview filter uses same logic as filter_content."""
        content = "Please review this."

        result1 = await mock_port.filter_content(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )
        result2 = await mock_port.preview_filter(
            content=content,
            message_type=MessageType.TASK_ACTIVATION,
        )

        assert result1.decision == result2.decision

    @pytest.mark.asyncio
    async def test_filter_accepts_all_message_types(
        self, mock_port: MockCoercionFilterPort
    ) -> None:
        """Filter works with all message types."""
        content = "Clean content"

        for message_type in MessageType:
            result = await mock_port.filter_content(
                content=content,
                message_type=message_type,
            )
            assert result.decision == FilterDecision.ACCEPTED

    @pytest.mark.asyncio
    async def test_mock_implements_port(
        self, mock_port: MockCoercionFilterPort
    ) -> None:
        """Mock implements the port interface."""
        # Should pass isinstance check if port is runtime_checkable
        assert isinstance(mock_port, CoercionFilterPort)
