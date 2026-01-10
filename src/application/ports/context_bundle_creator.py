"""Context Bundle Creator port definition (Story 2.9, ADR-2).

Defines the abstract interface for context bundle creation.
This port enables deterministic, verifiable context bundles for
agent deliberation.

ADR-2 Decision: Use signed JSON context bundles with JSON Schema validation.

Constitutional Constraints:
- CT-1: LLMs are stateless -> Context bundles provide deterministic state
- CT-12: Witnessing creates accountability -> Bundle hash creates audit trail
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from src.domain.models.context_bundle import (
    ContentRef,
    ContextBundlePayload,
)


@dataclass(frozen=True, eq=True)
class BundleCreationResult:
    """Result of bundle creation operation.

    Attributes:
        success: Whether bundle was created successfully.
        bundle: The created bundle (if success=True).
        bundle_hash: SHA-256 hash of bundle content.
        error_message: Error description (if success=False).
    """

    success: bool
    bundle: ContextBundlePayload | None
    bundle_hash: str | None
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate result state."""
        if self.success and self.bundle is None:
            raise ValueError("bundle required when success=True")
        if self.success and self.bundle_hash is None:
            raise ValueError("bundle_hash required when success=True")
        if not self.success and self.error_message is None:
            raise ValueError("error_message required when success=False")


@dataclass(frozen=True, eq=True)
class BundleVerificationResult:
    """Result of bundle verification operation.

    Attributes:
        valid: Whether bundle signature is valid.
        bundle_id: ID of the verified bundle.
        signing_key_id: Key ID used for signing.
        error_message: Error description (if valid=False).
    """

    valid: bool
    bundle_id: str | None
    signing_key_id: str | None
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate result state."""
        if self.valid and self.bundle_id is None:
            raise ValueError("bundle_id required when valid=True")
        if not self.valid and self.error_message is None:
            raise ValueError("error_message required when valid=False")


class ContextBundleCreatorPort(ABC):
    """Abstract interface for context bundle creation.

    All context bundle creator implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific bundle creation implementations.

    ADR-2 Requirements:
    - Bundle is signed at creation time
    - bundle_hash is computed over canonical JSON
    - Bundle includes all required fields (schema_version, bundle_id,
      meeting_id, as_of_event_seq, identity_prompt_ref, meeting_state_ref,
      precedent_refs[], created_at)

    Note:
        This port defines the abstract interface. Infrastructure adapters
        (e.g., ContextBundleCreatorStub, HSMBundleCreator) implement this
        protocol with specific creation logic.
    """

    @abstractmethod
    async def create_bundle(
        self,
        meeting_id: UUID,
        as_of_event_seq: int,
        identity_prompt_ref: ContentRef,
        meeting_state_ref: ContentRef,
        precedent_refs: tuple[ContentRef, ...],
    ) -> BundleCreationResult:
        """Create a signed context bundle.

        Creates a new context bundle with all required fields,
        computes the bundle_hash over canonical JSON, and signs it.

        Args:
            meeting_id: UUID of the meeting for this bundle.
            as_of_event_seq: Sequence number anchor for determinism.
            identity_prompt_ref: ContentRef to agent identity prompt.
            meeting_state_ref: ContentRef to meeting state snapshot.
            precedent_refs: Tuple of ContentRefs to relevant precedents.

        Returns:
            BundleCreationResult with the created bundle or error.

        Raises:
            SystemHaltedError: If system is halted (caller should check).
            BundleCreationError: If bundle creation fails.
        """
        ...

    @abstractmethod
    async def verify_bundle(
        self,
        bundle: ContextBundlePayload,
    ) -> BundleVerificationResult:
        """Verify a bundle's signature.

        ADR-2 Requirement: Receivers verify signature BEFORE parsing/using bundle.

        Args:
            bundle: The bundle to verify.

        Returns:
            BundleVerificationResult indicating if signature is valid.
        """
        ...

    @abstractmethod
    async def get_signing_key_id(self) -> str:
        """Get the current signing key ID.

        Returns:
            String identifier of the current signing key.
        """
        ...

    @abstractmethod
    async def get_bundle(self, bundle_id: str) -> ContextBundlePayload | None:
        """Get a stored bundle by ID.

        Args:
            bundle_id: The bundle ID to lookup.

        Returns:
            The ContextBundlePayload if found, None otherwise.
        """
        ...
