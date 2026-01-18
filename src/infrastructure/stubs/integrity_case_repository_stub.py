"""Integrity Case Artifact repository stub implementation (Story 7.10, FR144).

This module provides an in-memory stub implementation of IntegrityCaseRepositoryProtocol
for testing and development purposes. The stub is pre-populated with all
constitutional guarantees from INTEGRITY_GUARANTEE_REGISTRY.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- CT-13: Read access must survive cessation (read-only mode)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.application.ports.integrity_case_repository import (
    IntegrityCaseRepositoryProtocol,
)
from src.domain.models.integrity_case import (
    REQUIRED_CT_REFERENCES,
    IntegrityCaseArtifact,
    IntegrityGuarantee,
)
from src.domain.primitives.integrity_guarantees import INTEGRITY_GUARANTEE_REGISTRY


@dataclass
class VersionEntry:
    """A single version in the artifact history."""

    artifact: IntegrityCaseArtifact
    saved_at: datetime


class IntegrityCaseRepositoryStub(IntegrityCaseRepositoryProtocol):
    """In-memory stub for Integrity Case Artifact storage (testing only).

    This stub provides an in-memory implementation of IntegrityCaseRepositoryProtocol
    suitable for unit and integration tests.

    The stub is pre-populated with all guarantees from INTEGRITY_GUARANTEE_REGISTRY.
    Version history is maintained for all updates.

    Attributes:
        _current: The current version of the artifact.
        _versions: Dictionary mapping version strings to VersionEntry.
        _is_ceased: Flag indicating if system has ceased (read-only mode).
    """

    def __init__(self, pre_populate: bool = True) -> None:
        """Initialize the stub with optional pre-population.

        Args:
            pre_populate: If True, initialize with all guarantees from registry.
        """
        self._versions: dict[str, VersionEntry] = {}
        self._is_ceased: bool = False

        if pre_populate:
            self._current = INTEGRITY_GUARANTEE_REGISTRY
            self._versions[self._current.version] = VersionEntry(
                artifact=self._current,
                saved_at=self._current.created_at,
            )
        else:
            # Empty artifact for testing edge cases
            self._current = IntegrityCaseArtifact(
                guarantees=(),
                version="0.0.0",
            )

    def clear(self) -> None:
        """Clear all stored versions except current (for test cleanup)."""
        current_version = self._current.version
        current_entry = self._versions.get(current_version)
        self._versions.clear()
        if current_entry:
            self._versions[current_version] = current_entry

    def set_ceased(self, ceased: bool = True) -> None:
        """Set the ceased flag (for testing read-only mode)."""
        self._is_ceased = ceased

    async def get_current(self) -> IntegrityCaseArtifact:
        """Retrieve the current version of the Integrity Case Artifact.

        Returns:
            The current IntegrityCaseArtifact.
        """
        return self._current

    async def get_version(self, version: str) -> IntegrityCaseArtifact | None:
        """Retrieve a specific historical version of the artifact.

        Args:
            version: The semantic version string (e.g., "1.0.0").

        Returns:
            The IntegrityCaseArtifact at that version, None if not found.
        """
        entry = self._versions.get(version)
        return entry.artifact if entry else None

    async def update_with_amendment(
        self,
        artifact: IntegrityCaseArtifact,
        amendment_event_id: str,
    ) -> None:
        """Update the artifact as part of an amendment.

        Args:
            artifact: The updated IntegrityCaseArtifact.
            amendment_event_id: ID of the amendment event triggering the update.

        Raises:
            SystemCeasedError: If system has ceased (read-only mode).
        """
        if self._is_ceased:
            from src.domain.errors.ceased import SystemCeasedError

            raise SystemCeasedError("Cannot update integrity case after cessation")

        # Store the new version
        self._versions[artifact.version] = VersionEntry(
            artifact=artifact,
            saved_at=datetime.now(timezone.utc),
        )
        self._current = artifact

    async def get_version_history(self) -> list[tuple[str, datetime]]:
        """Retrieve the version history of the artifact.

        Returns:
            List of (version, last_updated) tuples, ordered by saved_at.
        """
        entries = sorted(
            self._versions.items(),
            key=lambda x: x[1].saved_at,
        )
        return [(version, entry.saved_at) for version, entry in entries]

    async def validate_completeness(self) -> list[str]:
        """Validate that all required constitutional constraints are covered.

        Returns:
            List of missing CT references. Empty if complete.
        """
        return self._current.validate_completeness(REQUIRED_CT_REFERENCES)

    # Test helper methods (not part of protocol)

    def get_version_count(self) -> int:
        """Get total number of stored versions."""
        return len(self._versions)

    def get_guarantee_count(self) -> int:
        """Get number of guarantees in current artifact."""
        return len(self._current.guarantees)

    def get_guarantee(self, guarantee_id: str) -> IntegrityGuarantee | None:
        """Get a specific guarantee from current artifact (for testing)."""
        return self._current.get_guarantee(guarantee_id)

    def is_ceased(self) -> bool:
        """Check if repository is in ceased (read-only) mode."""
        return self._is_ceased

    def add_guarantee(self, guarantee: IntegrityGuarantee) -> None:
        """Add a guarantee to current artifact (for testing updates).

        Creates a new version with the guarantee added.
        """
        # Parse current version and increment patch
        parts = self._current.version.split(".")
        new_version = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

        # Create new artifact with added guarantee
        new_artifact = IntegrityCaseArtifact(
            guarantees=self._current.guarantees + (guarantee,),
            version=new_version,
            schema_version=self._current.schema_version,
            constitution_version=self._current.constitution_version,
            created_at=self._current.created_at,
            last_updated=datetime.now(timezone.utc),
        )

        self._versions[new_version] = VersionEntry(
            artifact=new_artifact,
            saved_at=new_artifact.last_updated,
        )
        self._current = new_artifact
