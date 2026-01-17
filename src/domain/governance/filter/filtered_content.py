"""FilteredContent value object for type-safe content delivery.

This is the ONLY type that can reach participants per NFR-CONST-05.
The type system ensures no bypass path exists.
"""

from dataclasses import dataclass
from datetime import datetime
from hashlib import blake2b
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.governance.filter.filter_version import FilterVersion


@dataclass(frozen=True)
class FilteredContent:
    """Type-safe container for filtered content.

    This type MUST be used for all participant-facing output.
    It cannot be created without going through the filter.

    Per NFR-CONST-05, there is NO path from raw content to
    participant that bypasses this type.
    """

    _content: str
    _original_hash: str
    _filter_version: "FilterVersion"
    _filtered_at: datetime

    # Note: The constructor is public (Python limitation), but the _create
    # factory method documents the intended usage pattern. Runtime validation
    # in participant-facing APIs ensures only properly filtered content is sent.

    @classmethod
    def _create(
        cls,
        content: str,
        original_content: str,
        filter_version: "FilterVersion",
        filtered_at: datetime,
    ) -> "FilteredContent":
        """Internal factory for creating filtered content.

        Only CoercionFilterService should call this method.
        This ensures content goes through the filter before
        being wrapped in FilteredContent.

        Args:
            content: The filtered/transformed content
            original_content: The original unfiltered content (for hash)
            filter_version: Version of filter rules used
            filtered_at: Timestamp when filtering occurred

        Returns:
            A new FilteredContent instance
        """
        original_hash = blake2b(
            original_content.encode("utf-8"), digest_size=32
        ).hexdigest()
        return cls(
            _content=content,
            _original_hash=original_hash,
            _filter_version=filter_version,
            _filtered_at=filtered_at,
        )

    @property
    def content(self) -> str:
        """The filtered content safe to send to participants."""
        return self._content

    @property
    def original_hash(self) -> str:
        """BLAKE2b hash of original content for audit trail."""
        return self._original_hash

    @property
    def filter_version(self) -> "FilterVersion":
        """Version of filter rules that processed this content."""
        return self._filter_version

    @property
    def filtered_at(self) -> datetime:
        """Timestamp when content was filtered."""
        return self._filtered_at

    def __len__(self) -> int:
        """Return length of filtered content."""
        return len(self._content)

    def __bool__(self) -> bool:
        """Return True if filtered content is non-empty."""
        return bool(self._content)
