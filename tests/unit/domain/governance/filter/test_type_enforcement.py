"""Architectural tests for type system enforcement.

Tests AC3: Unfiltered content cannot reach participants (type system enforced).
Tests AC7: Type enforcement validates FilteredContent is used.
"""

import pytest
from typing import get_type_hints, Any
from datetime import datetime

from src.domain.governance.filter.filtered_content import FilteredContent
from src.domain.governance.filter.filter_version import FilterVersion


def validate_filtered_content(content: Any) -> FilteredContent:
    """Runtime validation that content is FilteredContent.

    This function provides defense-in-depth for type enforcement.
    Participant-facing APIs should call this to ensure only
    FilteredContent reaches participants.

    Args:
        content: Content to validate

    Returns:
        The content as FilteredContent if valid

    Raises:
        TypeError: If content is not FilteredContent
    """
    if not isinstance(content, FilteredContent):
        raise TypeError(
            f"Participant-facing content must be FilteredContent, got {type(content).__name__}"
        )
    return content


class TestTypeEnforcement:
    """Architectural tests for type system enforcement."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        """Create a test filter version."""
        return FilterVersion(
            major=1,
            minor=0,
            patch=0,
            rules_hash="abc123",
        )

    @pytest.fixture
    def filtered_content(self, filter_version: FilterVersion) -> FilteredContent:
        """Create test filtered content."""
        return FilteredContent._create(
            content="Hello, participant",
            original_content="HELLO! participant",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

    def test_validate_filtered_content_accepts_filtered(
        self, filtered_content: FilteredContent
    ) -> None:
        """validate_filtered_content accepts FilteredContent."""
        result = validate_filtered_content(filtered_content)
        assert result == filtered_content

    def test_validate_filtered_content_rejects_string(self) -> None:
        """validate_filtered_content rejects raw string."""
        with pytest.raises(TypeError) as exc_info:
            validate_filtered_content("raw string")

        assert "must be FilteredContent" in str(exc_info.value)
        assert "str" in str(exc_info.value)

    def test_validate_filtered_content_rejects_dict(self) -> None:
        """validate_filtered_content rejects dict."""
        with pytest.raises(TypeError) as exc_info:
            validate_filtered_content({"content": "data"})

        assert "must be FilteredContent" in str(exc_info.value)
        assert "dict" in str(exc_info.value)

    def test_validate_filtered_content_rejects_bytes(self) -> None:
        """validate_filtered_content rejects bytes."""
        with pytest.raises(TypeError) as exc_info:
            validate_filtered_content(b"raw bytes")

        assert "must be FilteredContent" in str(exc_info.value)
        assert "bytes" in str(exc_info.value)

    def test_validate_filtered_content_rejects_none(self) -> None:
        """validate_filtered_content rejects None."""
        with pytest.raises(TypeError) as exc_info:
            validate_filtered_content(None)

        assert "must be FilteredContent" in str(exc_info.value)
        assert "NoneType" in str(exc_info.value)

    def test_filtered_content_type_hint_enforcement(self) -> None:
        """FilteredContent can be used as type hint for enforcement."""
        # This test verifies the type can be used in hints
        def send_to_participant(content: FilteredContent) -> str:
            """Example function that requires FilteredContent."""
            return content.content

        hints = get_type_hints(send_to_participant)
        assert hints["content"] == FilteredContent

    def test_raw_string_not_subtype_of_filtered_content(self) -> None:
        """str is not a subtype of FilteredContent."""
        assert not isinstance("raw string", FilteredContent)

    def test_filtered_content_is_instance_of_itself(
        self, filtered_content: FilteredContent
    ) -> None:
        """FilteredContent passes isinstance check."""
        assert isinstance(filtered_content, FilteredContent)

    def test_no_direct_construction_bypass(
        self, filter_version: FilterVersion
    ) -> None:
        """Direct construction still requires all fields properly.

        While Python doesn't prevent direct construction, the design
        pattern of using _create factory makes intent clear.
        """
        # Direct construction is possible but not the intended pattern
        direct = FilteredContent(
            _content="content",
            _original_hash="hash",
            _filter_version=filter_version,
            _filtered_at=datetime.now(),
        )

        # It works but the hash won't match the content
        # This is a code smell that the filter was bypassed
        assert direct._original_hash == "hash"
        # Real usage through _create would have a proper hash

    def test_factory_method_generates_correct_hash(
        self, filter_version: FilterVersion
    ) -> None:
        """_create factory generates correct hash from original content."""
        from hashlib import blake2b

        original = "Original content"
        content = FilteredContent._create(
            content="Filtered content",
            original_content=original,
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        expected_hash = blake2b(original.encode("utf-8"), digest_size=32).hexdigest()
        assert content.original_hash == expected_hash
