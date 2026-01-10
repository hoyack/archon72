"""Unit tests for SemanticViolationSuspectedEventPayload (Story 9.7, FR110).

Tests creation, serialization, and validation of semantic violation events.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.events.semantic_violation import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    MAX_CONTENT_PREVIEW_LENGTH,
    SEMANTIC_SCANNER_SYSTEM_AGENT_ID,
    SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE,
    SemanticViolationSuspectedEventPayload,
)


class TestSemanticViolationSuspectedEventPayload:
    """Tests for SemanticViolationSuspectedEventPayload."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid event payload."""
        detected_at = datetime.now(timezone.utc)
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=(r"\bwe\s+feel\b", r"\bwe\s+think\b"),
            confidence_score=0.85,
            analysis_method="pattern_analysis",
            content_preview="We feel strongly about this decision.",
            detected_at=detected_at,
        )

        assert payload.content_id == "content-123"
        assert payload.suspected_patterns == (r"\bwe\s+feel\b", r"\bwe\s+think\b")
        assert payload.confidence_score == 0.85
        assert payload.analysis_method == "pattern_analysis"
        assert payload.content_preview == "We feel strongly about this decision."
        assert payload.detected_at == detected_at

    def test_create_with_minimum_fields(self) -> None:
        """Test creating payload with minimum required fields."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-456",
            suspected_patterns=("pattern",),
            confidence_score=0.5,
            analysis_method="test",
            content_preview="",
            detected_at=datetime.now(timezone.utc),
        )

        assert payload.content_id == "content-456"
        assert len(payload.suspected_patterns) == 1

    def test_event_type_property(self) -> None:
        """Test event_type property returns correct constant."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview="Test content",
            detected_at=datetime.now(timezone.utc),
        )

        assert payload.event_type == SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE
        assert payload.event_type == "semantic.violation.suspected"


class TestPayloadValidation:
    """Tests for payload validation."""

    def test_empty_content_id_raises(self) -> None:
        """Test that empty content_id raises ValueError."""
        with pytest.raises(ValueError, match="FR110: content_id is required"):
            SemanticViolationSuspectedEventPayload(
                content_id="",  # Empty
                suspected_patterns=("pattern",),
                confidence_score=0.7,
                analysis_method="test",
                content_preview="Test",
                detected_at=datetime.now(timezone.utc),
            )

    def test_empty_patterns_raises(self) -> None:
        """Test that empty suspected_patterns raises ValueError."""
        with pytest.raises(ValueError, match="FR110: At least one suspected pattern"):
            SemanticViolationSuspectedEventPayload(
                content_id="content-123",
                suspected_patterns=(),  # Empty
                confidence_score=0.7,
                analysis_method="test",
                content_preview="Test",
                detected_at=datetime.now(timezone.utc),
            )

    def test_empty_analysis_method_raises(self) -> None:
        """Test that empty analysis_method raises ValueError."""
        with pytest.raises(ValueError, match="FR110: analysis_method is required"):
            SemanticViolationSuspectedEventPayload(
                content_id="content-123",
                suspected_patterns=("pattern",),
                confidence_score=0.7,
                analysis_method="",  # Empty
                content_preview="Test",
                detected_at=datetime.now(timezone.utc),
            )

    def test_confidence_below_zero_raises(self) -> None:
        """Test that confidence_score < 0 raises ValueError."""
        with pytest.raises(ValueError, match="FR110: confidence_score must be between"):
            SemanticViolationSuspectedEventPayload(
                content_id="content-123",
                suspected_patterns=("pattern",),
                confidence_score=-0.1,  # Invalid
                analysis_method="test",
                content_preview="Test",
                detected_at=datetime.now(timezone.utc),
            )

    def test_confidence_above_one_raises(self) -> None:
        """Test that confidence_score > 1 raises ValueError."""
        with pytest.raises(ValueError, match="FR110: confidence_score must be between"):
            SemanticViolationSuspectedEventPayload(
                content_id="content-123",
                suspected_patterns=("pattern",),
                confidence_score=1.1,  # Invalid
                analysis_method="test",
                content_preview="Test",
                detected_at=datetime.now(timezone.utc),
            )


class TestContentPreviewTruncation:
    """Tests for content preview truncation."""

    def test_long_content_preview_truncated(self) -> None:
        """Test that long content preview is truncated."""
        long_content = "x" * 500  # 500 chars, exceeds limit
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview=long_content,
            detected_at=datetime.now(timezone.utc),
        )

        assert len(payload.content_preview) == MAX_CONTENT_PREVIEW_LENGTH
        assert len(payload.content_preview) == 200

    def test_short_content_preview_not_truncated(self) -> None:
        """Test that short content preview is not truncated."""
        short_content = "Short content"
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview=short_content,
            detected_at=datetime.now(timezone.utc),
        )

        assert payload.content_preview == short_content


class TestPayloadProperties:
    """Tests for payload computed properties."""

    def test_pattern_count_single(self) -> None:
        """Test pattern_count with single pattern."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview="Test",
            detected_at=datetime.now(timezone.utc),
        )

        assert payload.pattern_count == 1

    def test_pattern_count_multiple(self) -> None:
        """Test pattern_count with multiple patterns."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("p1", "p2", "p3"),
            confidence_score=0.7,
            analysis_method="test",
            content_preview="Test",
            detected_at=datetime.now(timezone.utc),
        )

        assert payload.pattern_count == 3

    def test_is_high_confidence_true(self) -> None:
        """Test is_high_confidence returns True when >= 0.7."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,  # Exactly at threshold
            analysis_method="test",
            content_preview="Test",
            detected_at=datetime.now(timezone.utc),
        )

        assert payload.is_high_confidence is True

    def test_is_high_confidence_false(self) -> None:
        """Test is_high_confidence returns False when < 0.7."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.69,  # Just below threshold
            analysis_method="test",
            content_preview="Test",
            detected_at=datetime.now(timezone.utc),
        )

        assert payload.is_high_confidence is False


class TestToDict:
    """Tests for to_dict serialization."""

    def test_to_dict_contains_all_fields(self) -> None:
        """Test that to_dict includes all expected fields."""
        detected_at = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("p1", "p2"),
            confidence_score=0.85,
            analysis_method="pattern_analysis",
            content_preview="Test content",
            detected_at=detected_at,
        )

        result = payload.to_dict()

        assert result["content_id"] == "content-123"
        assert result["suspected_patterns"] == ["p1", "p2"]  # Converted to list
        assert result["confidence_score"] == 0.85
        assert result["analysis_method"] == "pattern_analysis"
        assert result["content_preview"] == "Test content"
        assert result["detected_at"] == "2025-01-15T12:30:00+00:00"
        assert result["pattern_count"] == 2
        assert result["is_high_confidence"] is True

    def test_to_dict_patterns_as_list(self) -> None:
        """Test that patterns are converted to list for JSON serialization."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview="Test",
            detected_at=datetime.now(timezone.utc),
        )

        result = payload.to_dict()

        assert isinstance(result["suspected_patterns"], list)


class TestSignableContent:
    """Tests for signable_content and content_hash methods."""

    def test_signable_content_deterministic(self) -> None:
        """Test that signable_content produces deterministic bytes."""
        detected_at = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("p2", "p1"),  # Unordered
            confidence_score=0.85,
            analysis_method="test",
            content_preview="Test",
            detected_at=detected_at,
        )

        # Call twice
        bytes1 = payload.signable_content()
        bytes2 = payload.signable_content()

        assert bytes1 == bytes2

    def test_signable_content_sorts_patterns(self) -> None:
        """Test that patterns are sorted for determinism."""
        detected_at = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)

        # Create with different pattern order
        payload1 = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("p2", "p1"),
            confidence_score=0.85,
            analysis_method="test",
            content_preview="Test",
            detected_at=detected_at,
        )

        payload2 = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("p1", "p2"),
            confidence_score=0.85,
            analysis_method="test",
            content_preview="Test",
            detected_at=detected_at,
        )

        # Both should produce same signable content due to sorting
        assert payload1.signable_content() == payload2.signable_content()

    def test_content_hash_returns_hex_string(self) -> None:
        """Test that content_hash returns a hex string."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview="Test",
            detected_at=datetime.now(timezone.utc),
        )

        hash_value = payload.content_hash()

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 hex is 64 chars
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestConstants:
    """Tests for module constants."""

    def test_event_type_constant(self) -> None:
        """Test event type constant value."""
        assert SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE == "semantic.violation.suspected"

    def test_system_agent_id_constant(self) -> None:
        """Test system agent ID constant value."""
        assert SEMANTIC_SCANNER_SYSTEM_AGENT_ID == "system:semantic_scanner"

    def test_max_content_preview_length(self) -> None:
        """Test max content preview length constant."""
        assert MAX_CONTENT_PREVIEW_LENGTH == 200

    def test_default_confidence_threshold(self) -> None:
        """Test default confidence threshold constant."""
        assert DEFAULT_CONFIDENCE_THRESHOLD == 0.7


class TestFrozenDataclass:
    """Tests for frozen dataclass behavior."""

    def test_payload_is_immutable(self) -> None:
        """Test that payload cannot be modified after creation."""
        payload = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview="Test",
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.content_id = "modified"  # type: ignore

    def test_payload_equality(self) -> None:
        """Test that payloads with same values are equal."""
        detected_at = datetime(2025, 1, 15, 12, 30, 0, tzinfo=timezone.utc)

        payload1 = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview="Test",
            detected_at=detected_at,
        )

        payload2 = SemanticViolationSuspectedEventPayload(
            content_id="content-123",
            suspected_patterns=("pattern",),
            confidence_score=0.7,
            analysis_method="test",
            content_preview="Test",
            detected_at=detected_at,
        )

        assert payload1 == payload2
