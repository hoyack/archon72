"""Unit tests for FilteredContent value object.

Tests AC2: FilteredContent type required for all participant-facing output.
Tests AC3: Unfiltered content cannot reach participants.
Tests AC4: Filter version tracked for auditability.
Tests AC8: Immutable value objects for filter decisions.
"""

import pytest
from datetime import datetime
from dataclasses import FrozenInstanceError
from hashlib import blake2b

from src.domain.governance.filter.filtered_content import FilteredContent
from src.domain.governance.filter.filter_version import FilterVersion


class TestFilteredContent:
    """Unit tests for FilteredContent value object."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        """Create a test filter version."""
        return FilterVersion(
            major=1,
            minor=0,
            patch=0,
            rules_hash="abc123def456",
        )

    def test_create_filtered_content(self, filter_version: FilterVersion) -> None:
        """FilteredContent can be created via _create factory."""
        content = FilteredContent._create(
            content="Hello, participant",
            original_content="HELLO! URGENT! participant",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        assert content.content == "Hello, participant"
        assert content.filter_version == filter_version

    def test_filtered_content_immutable(self, filter_version: FilterVersion) -> None:
        """FilteredContent is immutable (frozen dataclass)."""
        content = FilteredContent._create(
            content="Hello",
            original_content="HELLO!",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        with pytest.raises(FrozenInstanceError):
            content._content = "Modified"  # type: ignore

    def test_filtered_content_tracks_original_hash(
        self, filter_version: FilterVersion
    ) -> None:
        """Original content hash preserved for audit trail."""
        original = "Original content with URGENCY!"
        content = FilteredContent._create(
            content="Original content with emphasis",
            original_content=original,
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        expected_hash = blake2b(original.encode("utf-8"), digest_size=32).hexdigest()
        assert content.original_hash == expected_hash

    def test_filtered_content_tracks_version(
        self, filter_version: FilterVersion
    ) -> None:
        """Filter version is tracked for auditability (AC4)."""
        content = FilteredContent._create(
            content="Hello",
            original_content="Hello",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        assert content.filter_version.major == 1
        assert content.filter_version.minor == 0
        assert content.filter_version.patch == 0

    def test_filtered_content_tracks_timestamp(
        self, filter_version: FilterVersion
    ) -> None:
        """Filtering timestamp is tracked."""
        now = datetime.now()
        content = FilteredContent._create(
            content="Hello",
            original_content="Hello",
            filter_version=filter_version,
            filtered_at=now,
        )

        assert content.filtered_at == now

    def test_filtered_content_len(self, filter_version: FilterVersion) -> None:
        """FilteredContent supports len()."""
        content = FilteredContent._create(
            content="Hello",
            original_content="Hello",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        assert len(content) == 5

    def test_filtered_content_bool_non_empty(
        self, filter_version: FilterVersion
    ) -> None:
        """Non-empty FilteredContent is truthy."""
        content = FilteredContent._create(
            content="Hello",
            original_content="Hello",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        assert bool(content) is True

    def test_filtered_content_bool_empty(
        self, filter_version: FilterVersion
    ) -> None:
        """Empty FilteredContent is falsy."""
        content = FilteredContent._create(
            content="",
            original_content="Removed content",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        assert bool(content) is False

    def test_different_original_content_different_hash(
        self, filter_version: FilterVersion
    ) -> None:
        """Different original content produces different hashes."""
        content1 = FilteredContent._create(
            content="Result",
            original_content="Original A",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )
        content2 = FilteredContent._create(
            content="Result",
            original_content="Original B",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        assert content1.original_hash != content2.original_hash

    def test_same_original_content_same_hash(
        self, filter_version: FilterVersion
    ) -> None:
        """Same original content produces same hash."""
        original = "Same original content"
        content1 = FilteredContent._create(
            content="Result 1",
            original_content=original,
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )
        content2 = FilteredContent._create(
            content="Result 2",
            original_content=original,
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

        assert content1.original_hash == content2.original_hash
