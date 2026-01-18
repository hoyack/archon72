"""Integrity Case Artifact service (Story 7.10, FR144).

This service provides access to the Integrity Case Artifact, which documents
all constitutional guarantees, their enforcement mechanisms, and invalidation
conditions.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- FR42: Public read access without authentication
- FR50: Versioned schema documentation
- CT-11: Silent failure destroys legitimacy -> Service must be reliable
- CT-12: Witnessing creates accountability -> Updates must be witnessed
- CT-13: Integrity outranks availability -> Must survive cessation

Developer Golden Rules:
1. COMPLETE COVERAGE - Every CT and FR with a guarantee MUST be in the artifact
2. MACHINE-READABLE - JSON with JSON-LD context for semantic interoperability
3. IMMUTABLE HISTORY - Version history preserved, never overwritten
4. POST-CESSATION - MUST be accessible after system ceases (read-only)
5. WITNESSED UPDATES - Amendment synchronization creates witnessed event

Usage:
    from src.application.services.integrity_case_service import IntegrityCaseService
    from src.infrastructure.stubs.integrity_case_repository_stub import (
        IntegrityCaseRepositoryStub,
    )

    # Create service (typically via dependency injection)
    repository = IntegrityCaseRepositoryStub()
    service = IntegrityCaseService(repository)

    # Get the artifact
    artifact = await service.get_artifact()

    # Get JSON-LD format
    json_ld = await service.get_artifact_jsonld()

    # Get single guarantee
    guarantee = await service.get_guarantee("ct-1-audit-trail")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from src.application.ports.integrity_case_repository import (
    IntegrityCaseRepositoryProtocol,
)
from src.domain.events.integrity_case import (
    IntegrityCaseUpdatedEventPayload,
)
from src.domain.models.integrity_case import (
    INTEGRITY_CASE_JSON_LD_CONTEXT,
    REQUIRED_CT_REFERENCES,
    GuaranteeCategory,
    IntegrityCaseArtifact,
    IntegrityGuarantee,
)

logger = structlog.get_logger(__name__)


class IntegrityCaseService:
    """Service for accessing the Integrity Case Artifact (FR144).

    This service provides read-only access to the Integrity Case Artifact.
    The artifact documents all constitutional guarantees the system makes.

    The service supports:
    - Getting the current artifact
    - Getting the artifact in JSON-LD format
    - Looking up individual guarantees
    - Checking version history
    - Validating completeness (all CTs covered)
    - Updating for amendments (creates witnessed event)

    Constitutional Constraint (FR144):
    The system SHALL maintain a published Integrity Case Artifact that
    documents guarantees claimed, mechanisms enforcing them, and conditions
    that would invalidate them.

    Attributes:
        _repository: Repository for artifact storage and retrieval.
        _log: Structured logger for the service.

    Example:
        >>> repository = IntegrityCaseRepositoryStub()
        >>> service = IntegrityCaseService(repository)
        >>> artifact = await service.get_artifact()
        >>> len(artifact.guarantees)
        20
    """

    def __init__(
        self,
        repository: IntegrityCaseRepositoryProtocol,
    ) -> None:
        """Initialize the Integrity Case service.

        Args:
            repository: Repository for artifact storage.
        """
        self._repository = repository
        self._log = logger.bind(service="integrity_case_service")

    async def get_artifact(self) -> IntegrityCaseArtifact:
        """Get the current Integrity Case Artifact (FR144).

        Returns the complete artifact with all guarantees and version metadata.

        Constitutional Constraint (FR144):
        The artifact MUST always return a valid document with all
        constitutional guarantees documented.

        Returns:
            The current IntegrityCaseArtifact.

        Example:
            >>> artifact = await service.get_artifact()
            >>> artifact.version
            '1.0.0'
        """
        artifact = await self._repository.get_current()

        self._log.debug(
            "integrity_case_artifact_accessed",
            version=artifact.version,
            guarantee_count=len(artifact.guarantees),
        )

        return artifact

    async def get_artifact_jsonld(self) -> dict[str, Any]:
        """Get the artifact in JSON-LD format (FR144, FR50).

        Returns the artifact with JSON-LD context for semantic interoperability.
        This format is machine-readable and includes schema versioning.

        Constitutional Constraint (FR50):
        Versioned schema documentation SHALL be publicly accessible.

        Returns:
            Dict with JSON-LD context and artifact data.

        Example:
            >>> json_ld = await service.get_artifact_jsonld()
            >>> json_ld["@type"]
            'integrity:IntegrityCaseArtifact'
        """
        artifact = await self._repository.get_current()
        json_ld = artifact.to_json_ld()

        self._log.debug(
            "integrity_case_artifact_jsonld_accessed",
            version=artifact.version,
            guarantee_count=len(artifact.guarantees),
        )

        return json_ld

    async def get_guarantee(self, guarantee_id: str) -> IntegrityGuarantee | None:
        """Get a specific guarantee by ID (FR144).

        Looks up a single guarantee by its guarantee_id.

        Args:
            guarantee_id: The guarantee_id to look up (e.g., "ct-1-audit-trail").

        Returns:
            The IntegrityGuarantee if found, None otherwise.

        Example:
            >>> guarantee = await service.get_guarantee("ct-1-audit-trail")
            >>> guarantee.name
            'Append-Only Audit Trail'
        """
        artifact = await self._repository.get_current()
        result = artifact.get_guarantee(guarantee_id)

        if result is None:
            self._log.debug(
                "integrity_guarantee_not_found",
                guarantee_id=guarantee_id,
            )
        else:
            self._log.debug(
                "integrity_guarantee_accessed",
                guarantee_id=guarantee_id,
                name=result.name,
                category=result.category.value,
            )

        return result

    async def get_guarantees_by_category(
        self, category: GuaranteeCategory
    ) -> tuple[IntegrityGuarantee, ...]:
        """Get all guarantees of a specific category.

        Args:
            category: The category to filter by.

        Returns:
            Tuple of guarantees matching the category.

        Example:
            >>> constitutional = await service.get_guarantees_by_category(
            ...     GuaranteeCategory.CONSTITUTIONAL
            ... )
            >>> len(constitutional)
            15
        """
        artifact = await self._repository.get_current()
        return artifact.get_by_category(category)

    async def get_version_history(self) -> list[tuple[str, datetime]]:
        """Get the version history of the artifact (FR144).

        Constitutional Constraint (FR144):
        Version history must be accessible for audit purposes.

        Returns:
            List of (version, last_updated) tuples, ordered by date.

        Example:
            >>> history = await service.get_version_history()
            >>> history[0][0]  # First version
            '1.0.0'
        """
        history = await self._repository.get_version_history()

        self._log.debug(
            "integrity_case_history_accessed",
            version_count=len(history),
        )

        return history

    async def get_artifact_version(self, version: str) -> IntegrityCaseArtifact | None:
        """Get a specific historical version of the artifact.

        Args:
            version: The semantic version string (e.g., "1.0.0").

        Returns:
            The IntegrityCaseArtifact at that version, None if not found.

        Example:
            >>> artifact = await service.get_artifact_version("1.0.0")
            >>> artifact.version
            '1.0.0'
        """
        result = await self._repository.get_version(version)

        if result is None:
            self._log.debug(
                "integrity_case_version_not_found",
                version=version,
            )
        else:
            self._log.debug(
                "integrity_case_version_accessed",
                version=version,
                guarantee_count=len(result.guarantees),
            )

        return result

    async def validate_completeness(self) -> list[str]:
        """Validate that all required CTs are covered (FR144).

        Constitutional Constraint (FR144):
        The artifact must document ALL constitutional constraints (CT-1 to CT-15).

        Returns:
            List of missing CT references. Empty if complete.

        Example:
            >>> missing = await service.validate_completeness()
            >>> len(missing)
            0
        """
        missing = await self._repository.validate_completeness()

        if missing:
            self._log.warning(
                "integrity_case_incomplete",
                missing_cts=missing,
            )
        else:
            self._log.debug(
                "integrity_case_complete",
                covered_cts=list(REQUIRED_CT_REFERENCES),
            )

        return missing

    async def update_for_amendment(
        self,
        amendment_event_id: str,
        guarantees_added: tuple[IntegrityGuarantee, ...] = (),
        guarantees_modified: tuple[IntegrityGuarantee, ...] = (),
        guarantees_removed: tuple[str, ...] = (),
        reason: str = "",
    ) -> IntegrityCaseUpdatedEventPayload:
        """Update the artifact for a constitutional amendment (FR144, CT-12).

        Creates a new version of the artifact and returns an update event
        payload for witnessing.

        Constitutional Constraint (FR144):
        Artifact SHALL be updated with each constitutional amendment.

        Constitutional Constraint (CT-12):
        Updates must be witnessed. Returns event payload for witnessing.

        Args:
            amendment_event_id: ID of the triggering amendment event.
            guarantees_added: New guarantees to add.
            guarantees_modified: Guarantees with updated content.
            guarantees_removed: IDs of guarantees to remove.
            reason: Reason for the update.

        Returns:
            IntegrityCaseUpdatedEventPayload for witnessing.

        Raises:
            SystemCeasedError: If system has ceased (read-only mode).
            ValueError: If no changes specified.

        Example:
            >>> payload = await service.update_for_amendment(
            ...     amendment_event_id="amend-123",
            ...     guarantees_added=(new_guarantee,),
            ...     reason="Added FR200 guarantee",
            ... )
        """
        if not (guarantees_added or guarantees_modified or guarantees_removed):
            raise ValueError("At least one change must be specified")

        # Get current artifact
        current = await self._repository.get_current()

        # Build new guarantees list
        current_guarantees = {g.guarantee_id: g for g in current.guarantees}

        # Remove
        for guarantee_id in guarantees_removed:
            current_guarantees.pop(guarantee_id, None)

        # Modify (replace)
        for guarantee in guarantees_modified:
            current_guarantees[guarantee.guarantee_id] = guarantee

        # Add
        for guarantee in guarantees_added:
            current_guarantees[guarantee.guarantee_id] = guarantee

        # Compute new version (increment patch)
        parts = current.version.split(".")
        new_version = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

        # Create new artifact
        now = datetime.now(timezone.utc)
        new_artifact = IntegrityCaseArtifact(
            guarantees=tuple(current_guarantees.values()),
            version=new_version,
            schema_version=current.schema_version,
            constitution_version=current.constitution_version,
            created_at=current.created_at,
            last_updated=now,
            amendment_event_id=amendment_event_id,
        )

        # Save to repository
        await self._repository.update_with_amendment(new_artifact, amendment_event_id)

        # Create event payload for witnessing
        payload = IntegrityCaseUpdatedEventPayload(
            artifact_version=new_version,
            previous_version=current.version,
            amendment_event_id=amendment_event_id,
            guarantees_added=tuple(g.guarantee_id for g in guarantees_added),
            guarantees_modified=tuple(g.guarantee_id for g in guarantees_modified),
            guarantees_removed=guarantees_removed,
            updated_at=now,
            reason=reason,
        )

        self._log.info(
            "integrity_case_updated",
            previous_version=current.version,
            new_version=new_version,
            amendment_event_id=amendment_event_id,
            added=len(guarantees_added),
            modified=len(guarantees_modified),
            removed=len(guarantees_removed),
        )

        return payload

    def get_json_ld_context(self) -> dict[str, Any]:
        """Get the JSON-LD context for the integrity case schema.

        Returns the JSON-LD context used for semantic interoperability.

        Returns:
            Dict with JSON-LD context definitions.

        Example:
            >>> context = service.get_json_ld_context()
            >>> "integrity" in context["@context"]
            True
        """
        return INTEGRITY_CASE_JSON_LD_CONTEXT
