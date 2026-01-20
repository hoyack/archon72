"""Context package builder stub for testing (Story 2A.3, FR-11.3).

This module provides an in-memory stub implementation of the
ContextPackageBuilderProtocol for testing purposes.

The stub:
- Builds packages identically to the real service
- Tracks all built packages for test assertions
- Provides test helpers for verification

Usage:
    >>> stub = ContextPackageBuilderStub()
    >>> package = stub.build_package(petition, session)
    >>> assert stub.get_built_packages() == [package]
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


class ContextPackageBuilderStub:
    """In-memory stub for testing context package building (Story 2A.3).

    Provides the same functionality as ContextPackageBuilderService but
    also tracks built packages for test assertions.

    Attributes:
        _built_packages: List of packages built during test.
        _fixed_build_time: Optional fixed timestamp for deterministic tests.

    Example:
        >>> stub = ContextPackageBuilderStub()
        >>> package = stub.build_package(petition, session)
        >>> assert len(stub.get_built_packages()) == 1
        >>> assert package.verify_hash()
    """

    def __init__(self, fixed_build_time: datetime | None = None) -> None:
        """Initialize the stub.

        Args:
            fixed_build_time: Optional fixed timestamp for deterministic tests.
                If None, uses current UTC time.
        """
        self._built_packages: list[DeliberationContextPackage] = []
        self._fixed_build_time = fixed_build_time

    def build_package(
        self,
        petition: PetitionSubmission,
        session: DeliberationSession,
    ) -> DeliberationContextPackage:
        """Build a context package for deliberation.

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

        # Use fixed time or current time
        built_at = self._fixed_build_time or datetime.now(timezone.utc)

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
        package = DeliberationContextPackage(
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

        # Track for test assertions
        self._built_packages.append(package)

        return package

    def get_built_packages(self) -> list[DeliberationContextPackage]:
        """Get all packages built during test.

        Returns:
            List of built packages in order.
        """
        return list(self._built_packages)

    def get_package_count(self) -> int:
        """Get count of packages built.

        Returns:
            Number of packages built.
        """
        return len(self._built_packages)

    def clear(self) -> None:
        """Clear all tracked packages.

        Use between tests to reset state.
        """
        self._built_packages.clear()

    def set_fixed_build_time(self, build_time: datetime | None) -> None:
        """Set fixed build time for deterministic tests.

        Args:
            build_time: Fixed timestamp or None for real time.
        """
        self._fixed_build_time = build_time
