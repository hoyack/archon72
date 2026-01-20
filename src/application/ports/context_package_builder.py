"""Context package builder protocol (Story 2A.3, FR-11.3).

This module defines the protocol for building deliberation context packages
for the Three Fates petition deliberation system.

Constitutional Constraints:
- CT-1: LLMs are stateless -> Package provides deterministic state
- CT-12: Witnessing creates accountability -> Package hash enables audit
- FR-11.3: System SHALL provide deliberation context package to each Fate Archon
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.domain.models.deliberation_context_package import (
        DeliberationContextPackage,
    )
    from src.domain.models.deliberation_session import DeliberationSession
    from src.domain.models.petition_submission import PetitionSubmission


class ContextPackageBuilderProtocol(Protocol):
    """Protocol for building deliberation context packages (Story 2A.3, FR-11.3).

    Implementations of this protocol create immutable, content-hashed context
    packages that provide Fate Archons with all information needed to
    deliberate on a petition.

    Key Guarantees:
    - Deterministic: Same inputs always produce same package (idempotent)
    - Immutable: Packages are frozen dataclasses
    - Verifiable: Content hash enables integrity verification
    - Ruling-3 compliant: Similar petitions deferred to M2
    """

    def build_package(
        self,
        petition: PetitionSubmission,
        session: DeliberationSession,
    ) -> DeliberationContextPackage:
        """Build a context package for deliberation.

        Creates an immutable, content-hashed package containing all
        information needed by Fate Archons to deliberate the petition.

        The package includes:
        - Full petition text and metadata
        - Petition type and realm
        - Co-signer count
        - Deliberation session info
        - Assigned archon IDs
        - Content hash for integrity

        Per Ruling-3, similar_petitions is explicitly empty in M1.

        Args:
            petition: The petition being deliberated.
            session: The deliberation session with assigned archons.

        Returns:
            DeliberationContextPackage with computed content_hash.

        Raises:
            ValueError: If petition or session is invalid.
            PetitionSessionMismatchError: If session.petition_id != petition.id.

        Example:
            >>> builder = ContextPackageBuilderService()
            >>> package = builder.build_package(petition, session)
            >>> assert package.content_hash  # Hash is computed
            >>> assert package.verify_hash()  # Hash is valid
        """
        ...
