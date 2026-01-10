"""Integrity Case Artifact repository port (Story 7.10, FR144).

This module defines the repository interface for storing and querying
the Integrity Case Artifact and its version history.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- FR42: Public read access without authentication
- FR50: Versioned schema documentation
- CT-11: Silent failure destroys legitimacy -> Query failures must not be silent
- CT-12: Witnessing creates accountability -> Updates create witnessed events
- CT-13: Integrity outranks availability -> Must survive cessation (read-only)

Developer Golden Rules:
1. IMMUTABLE HISTORY - Version history preserved, never overwritten
2. POST-CESSATION - MUST be accessible after system ceases (read-only)
3. WITNESSED UPDATES - Amendment synchronization creates witnessed event
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol

from src.domain.models.integrity_case import IntegrityCaseArtifact


class IntegrityCaseRepositoryProtocol(Protocol):
    """Protocol for Integrity Case Artifact storage and retrieval (FR144).

    This protocol defines the interface for storing the Integrity Case Artifact
    and maintaining its version history. The artifact is pre-populated with
    all constitutional guarantees at system initialization.

    All implementations must support:
    - Getting the current artifact version
    - Getting a specific historical version
    - Updating the artifact (atomic with amendment events)
    - Retrieving version history

    Constitutional Constraints:
    - FR144: Artifact must be maintained and updated with amendments
    - CT-13: Read access must survive cessation indefinitely
    """

    async def get_current(self) -> IntegrityCaseArtifact:
        """Retrieve the current version of the Integrity Case Artifact.

        Constitutional Constraint (FR144):
        The artifact MUST always return a valid document with all
        constitutional guarantees documented.

        Returns:
            The current IntegrityCaseArtifact.

        Raises:
            IntegrityCaseError: If retrieval fails.
        """
        ...

    async def get_version(self, version: str) -> Optional[IntegrityCaseArtifact]:
        """Retrieve a specific historical version of the artifact.

        Constitutional Constraint (FR144):
        Version history must be preserved for audit and accountability.

        Args:
            version: The semantic version string (e.g., "1.0.0").

        Returns:
            The IntegrityCaseArtifact at that version, None if not found.

        Raises:
            IntegrityCaseError: If query fails.
        """
        ...

    async def update_with_amendment(
        self,
        artifact: IntegrityCaseArtifact,
        amendment_event_id: str,
    ) -> None:
        """Update the artifact as part of an amendment.

        Constitutional Constraint (FR144, CT-12):
        Updates to the artifact MUST be synchronized with amendment events.
        The amendment_event_id links the artifact update to the witnessed
        amendment that caused it.

        This should be called in the same transaction as the amendment
        event write to ensure atomicity.

        Args:
            artifact: The updated IntegrityCaseArtifact.
            amendment_event_id: ID of the amendment event triggering the update.

        Raises:
            IntegrityCaseError: If update fails.
            SystemCeasedError: If system has ceased (read-only mode, FR42).
        """
        ...

    async def get_version_history(self) -> list[tuple[str, datetime]]:
        """Retrieve the version history of the artifact.

        Constitutional Constraint (FR144):
        Version history must be accessible for audit purposes.

        Returns:
            List of (version, last_updated) tuples, ordered by last_updated.

        Raises:
            IntegrityCaseError: If query fails.
        """
        ...

    async def validate_completeness(self) -> list[str]:
        """Validate that all required constitutional constraints are covered.

        Constitutional Constraint (FR144):
        The artifact must document ALL constitutional constraints (CT-1 to CT-15).

        Returns:
            List of missing CT references. Empty if complete.

        Raises:
            IntegrityCaseError: If validation fails.
        """
        ...
