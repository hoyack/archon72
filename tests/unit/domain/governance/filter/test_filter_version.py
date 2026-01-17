"""Unit tests for FilterVersion value object.

Tests AC4: Filter version tracked for auditability.
Tests AC8: Immutable value objects.
"""

import pytest
from dataclasses import FrozenInstanceError

from src.domain.governance.filter.filter_version import FilterVersion


class TestFilterVersion:
    """Unit tests for FilterVersion value object."""

    def test_create_filter_version(self) -> None:
        """FilterVersion can be created with valid values."""
        version = FilterVersion(
            major=1,
            minor=2,
            patch=3,
            rules_hash="abc123def456",
        )

        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.rules_hash == "abc123def456"

    def test_filter_version_str(self) -> None:
        """FilterVersion string representation is semantic version."""
        version = FilterVersion(
            major=1,
            minor=2,
            patch=3,
            rules_hash="abc123",
        )

        assert str(version) == "1.2.3"

    def test_filter_version_immutable(self) -> None:
        """FilterVersion is immutable (AC8)."""
        version = FilterVersion(
            major=1,
            minor=0,
            patch=0,
            rules_hash="abc123",
        )

        with pytest.raises(FrozenInstanceError):
            version.major = 2  # type: ignore

    def test_filter_version_negative_major_raises(self) -> None:
        """Negative major version raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            FilterVersion(
                major=-1,
                minor=0,
                patch=0,
                rules_hash="abc123",
            )

    def test_filter_version_negative_minor_raises(self) -> None:
        """Negative minor version raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            FilterVersion(
                major=1,
                minor=-1,
                patch=0,
                rules_hash="abc123",
            )

    def test_filter_version_negative_patch_raises(self) -> None:
        """Negative patch version raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            FilterVersion(
                major=1,
                minor=0,
                patch=-1,
                rules_hash="abc123",
            )

    def test_filter_version_empty_hash_raises(self) -> None:
        """Empty rules hash raises ValueError."""
        with pytest.raises(ValueError, match="Rules hash is required"):
            FilterVersion(
                major=1,
                minor=0,
                patch=0,
                rules_hash="",
            )

    def test_filter_version_equality(self) -> None:
        """FilterVersions with same values are equal."""
        v1 = FilterVersion(major=1, minor=0, patch=0, rules_hash="abc")
        v2 = FilterVersion(major=1, minor=0, patch=0, rules_hash="abc")

        assert v1 == v2

    def test_filter_version_inequality_major(self) -> None:
        """FilterVersions with different major are not equal."""
        v1 = FilterVersion(major=1, minor=0, patch=0, rules_hash="abc")
        v2 = FilterVersion(major=2, minor=0, patch=0, rules_hash="abc")

        assert v1 != v2

    def test_filter_version_inequality_hash(self) -> None:
        """FilterVersions with different hash are not equal."""
        v1 = FilterVersion(major=1, minor=0, patch=0, rules_hash="abc")
        v2 = FilterVersion(major=1, minor=0, patch=0, rules_hash="def")

        assert v1 != v2

    def test_filter_version_zero_versions_allowed(self) -> None:
        """Zero values are valid for version components."""
        version = FilterVersion(
            major=0,
            minor=0,
            patch=0,
            rules_hash="initial",
        )

        assert str(version) == "0.0.0"
