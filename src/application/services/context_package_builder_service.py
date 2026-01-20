"""Context package builder service implementation (Story 2A.3, FR-11.3).

This module implements the ContextPackageBuilderProtocol for building
deliberation context packages for the Three Fates petition deliberation.

Constitutional Constraints:
- CT-1: LLMs are stateless -> Package provides deterministic state
- CT-12: Witnessing creates accountability -> Package hash enables audit
- FR-11.3: System SHALL provide deliberation context package to each Fate Archon
- Ruling-3: Similar petitions deferred to M2
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.errors.deliberation import PetitionSessionMismatchError
from src.domain.models.deliberation_context_package import (
    CONTEXT_PACKAGE_SCHEMA_VERSION,
    DeliberationContextPackage,
    compute_content_hash,
)
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.petition_submission import PetitionSubmission


class ContextPackageBuilderService:
    """Service for building deliberation context packages (Story 2A.3, FR-11.3).

    Creates immutable, content-hashed packages that provide Fate Archons
    with all information needed to deliberate on a petition.

    Key Guarantees:
    - Deterministic: Same inputs always produce same package
    - Immutable: Packages are frozen dataclasses
    - Verifiable: SHA-256 content hash for integrity
    - Ruling-3 compliant: Similar petitions explicitly empty

    Example:
        >>> builder = ContextPackageBuilderService()
        >>> package = builder.build_package(petition, session)
        >>> assert package.verify_hash()
    """

    def build_package(
        self,
        petition: PetitionSubmission,
        session: DeliberationSession,
    ) -> DeliberationContextPackage:
        """Build a context package for deliberation.

        Creates an immutable, content-hashed package containing all
        information needed by Fate Archons to deliberate the petition.

        Args:
            petition: The petition being deliberated.
            session: The deliberation session with assigned archons.

        Returns:
            DeliberationContextPackage with computed content_hash.

        Raises:
            PetitionSessionMismatchError: If session.petition_id != petition.id.
        """
        # Validate petition-session relationship
        if session.petition_id != petition.id:
            raise PetitionSessionMismatchError(
                petition_id=petition.id,
                session_petition_id=session.petition_id,
            )

        # Capture build time for determinism
        built_at = datetime.now(timezone.utc)

        # Build hashable content first (without content_hash)
        hashable_dict = {
            "petition_id": str(petition.id),
            "petition_text": petition.text,
            "petition_type": petition.type.value,
            "co_signer_count": petition.co_signer_count,
            "submitter_id": str(petition.submitter_id) if petition.submitter_id else None,
            "realm": petition.realm,
            "submitted_at": petition.created_at.isoformat(),
            "session_id": str(session.session_id),
            "assigned_archons": [str(a) for a in session.assigned_archons],
            "similar_petitions": [],  # Ruling-3: deferred to M2
            "ruling_3_deferred": True,
            "schema_version": CONTEXT_PACKAGE_SCHEMA_VERSION,
            "built_at": built_at.isoformat(),
        }

        # Compute content hash
        content_hash = compute_content_hash(hashable_dict)

        # Create immutable package with hash
        return DeliberationContextPackage(
            petition_id=petition.id,
            petition_text=petition.text,
            petition_type=petition.type.value,
            co_signer_count=petition.co_signer_count,
            submitter_id=petition.submitter_id,
            realm=petition.realm,
            submitted_at=petition.created_at,
            session_id=session.session_id,
            assigned_archons=session.assigned_archons,
            similar_petitions=tuple(),
            ruling_3_deferred=True,
            schema_version=CONTEXT_PACKAGE_SCHEMA_VERSION,
            built_at=built_at,
            content_hash=content_hash,
        )
