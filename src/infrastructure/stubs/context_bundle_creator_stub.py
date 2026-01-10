"""Context Bundle Creator stub implementation (Story 2.9, ADR-2).

In-memory stub for ContextBundleCreatorPort for development and testing.
Follows DEV_MODE_WATERMARK pattern per RT-1/ADR-4.

ADR-2 Requirements:
- Bundle is signed at creation time
- bundle_hash is computed over canonical JSON
- Signature verification before use

Constitutional Constraints:
- CT-1: LLMs are stateless -> Context bundles provide deterministic state
- CT-12: Witnessing creates accountability -> All bundles hash-chained
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern for dev stubs
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

import structlog

from src.application.ports.context_bundle_creator import (
    BundleCreationResult,
    BundleVerificationResult,
    ContextBundleCreatorPort,
)
from src.domain.models.context_bundle import (
    CONTEXT_BUNDLE_SCHEMA_VERSION,
    ContentRef,
    ContextBundlePayload,
)

logger = structlog.get_logger()


# DEV_MODE_WATERMARK per RT-1/ADR-4
# This constant indicates this is a development stub, not production code
DEV_MODE_WATERMARK: str = "DEV_STUB:ContextBundleCreatorStub:v1"


class ContextBundleCreatorStub(ContextBundleCreatorPort):
    """In-memory stub for ContextBundleCreatorPort (ADR-2).

    Development and testing implementation that creates bundles
    in memory with DEV_MODE watermarked signatures.

    WARNING: This is a development stub. Not for production use.
    Production implementations should use HSM for signing.

    Attributes:
        _bundles: In-memory dict mapping bundle_id to ContextBundlePayload.
        _signing_key_id: The key ID used for signing bundles.

    Example:
        >>> stub = ContextBundleCreatorStub()
        >>> result = await stub.create_bundle(
        ...     meeting_id=uuid4(),
        ...     as_of_event_seq=42,
        ...     identity_prompt_ref="ref:" + "a" * 64,
        ...     meeting_state_ref="ref:" + "b" * 64,
        ...     precedent_refs=tuple(),
        ... )
        >>> result.success  # True
    """

    def __init__(
        self,
        signing_key_id: str | None = None,
    ) -> None:
        """Initialize bundle creator stub.

        Args:
            signing_key_id: Optional key ID for signing. Defaults to dev key.
        """
        self._bundles: dict[str, ContextBundlePayload] = {}
        self._signing_key_id = signing_key_id or f"BUNDLE:{DEV_MODE_WATERMARK}"
        logger.debug(
            "context_bundle_creator_stub_initialized",
            watermark=DEV_MODE_WATERMARK,
            signing_key_id=self._signing_key_id,
        )

    async def create_bundle(
        self,
        meeting_id: UUID,
        as_of_event_seq: int,
        identity_prompt_ref: ContentRef,
        meeting_state_ref: ContentRef,
        precedent_refs: tuple[ContentRef, ...],
    ) -> BundleCreationResult:
        """Create a signed context bundle.

        Creates a new context bundle with DEV MODE signature watermark.

        Args:
            meeting_id: UUID of the meeting for this bundle.
            as_of_event_seq: Sequence number anchor for determinism.
            identity_prompt_ref: ContentRef to agent identity prompt.
            meeting_state_ref: ContentRef to meeting state snapshot.
            precedent_refs: Tuple of ContentRefs to relevant precedents.

        Returns:
            BundleCreationResult with the created bundle.
        """
        try:
            created_at = datetime.now(timezone.utc)

            # Build signable content (without signature/hash)
            signable_dict = {
                "schema_version": CONTEXT_BUNDLE_SCHEMA_VERSION,
                "meeting_id": str(meeting_id),
                "as_of_event_seq": as_of_event_seq,
                "identity_prompt_ref": identity_prompt_ref,
                "meeting_state_ref": meeting_state_ref,
                "precedent_refs": list(precedent_refs),
                "created_at": created_at.isoformat(),
            }

            # Compute bundle hash from canonical JSON
            bundle_hash = await self._compute_hash(signable_dict)

            # Create DEV MODE signature
            # Per RT-1: mode is inside signature, not metadata
            signature = await self._create_dev_signature(bundle_hash)

            # Create the bundle payload
            bundle = ContextBundlePayload(
                schema_version=CONTEXT_BUNDLE_SCHEMA_VERSION,
                meeting_id=meeting_id,
                as_of_event_seq=as_of_event_seq,
                identity_prompt_ref=identity_prompt_ref,
                meeting_state_ref=meeting_state_ref,
                precedent_refs=precedent_refs,
                created_at=created_at,
                bundle_hash=bundle_hash,
                signature=signature,
                signing_key_id=self._signing_key_id,
            )

            # Store for later verification
            self._bundles[bundle.bundle_id] = bundle

            logger.info(
                "context_bundle_created",
                bundle_id=bundle.bundle_id,
                meeting_id=str(meeting_id),
                as_of_event_seq=as_of_event_seq,
                bundle_hash_prefix=bundle_hash[:8],
                signing_key_id=self._signing_key_id,
                precedent_count=len(precedent_refs),
            )

            return BundleCreationResult(
                success=True,
                bundle=bundle,
                bundle_hash=bundle_hash,
            )

        except Exception as e:
            logger.error(
                "context_bundle_creation_failed",
                meeting_id=str(meeting_id),
                error=str(e),
            )
            return BundleCreationResult(
                success=False,
                bundle=None,
                bundle_hash=None,
                error_message=f"Bundle creation failed: {e}",
            )

    async def verify_bundle(
        self,
        bundle: ContextBundlePayload,
    ) -> BundleVerificationResult:
        """Verify a bundle's signature.

        Recomputes the hash and verifies the DEV MODE signature.

        Args:
            bundle: The bundle to verify.

        Returns:
            BundleVerificationResult indicating if signature is valid.
        """
        try:
            # Recompute hash from signable content
            signable_dict = bundle.to_signable_dict()
            expected_hash = await self._compute_hash(signable_dict)

            # Check bundle_hash matches
            if bundle.bundle_hash != expected_hash:
                logger.warning(
                    "bundle_hash_mismatch",
                    bundle_id=bundle.bundle_id,
                    stored_hash_prefix=bundle.bundle_hash[:8],
                    computed_hash_prefix=expected_hash[:8],
                )
                return BundleVerificationResult(
                    valid=False,
                    bundle_id=bundle.bundle_id,
                    signing_key_id=bundle.signing_key_id,
                    error_message="ADR-2: Invalid context bundle signature (hash mismatch)",
                )

            # Verify DEV MODE signature
            expected_signature = await self._create_dev_signature(bundle.bundle_hash)
            if bundle.signature != expected_signature:
                logger.warning(
                    "bundle_signature_mismatch",
                    bundle_id=bundle.bundle_id,
                )
                return BundleVerificationResult(
                    valid=False,
                    bundle_id=bundle.bundle_id,
                    signing_key_id=bundle.signing_key_id,
                    error_message="ADR-2: Invalid context bundle signature",
                )

            logger.debug(
                "bundle_verification_passed",
                bundle_id=bundle.bundle_id,
                signing_key_id=bundle.signing_key_id,
            )

            return BundleVerificationResult(
                valid=True,
                bundle_id=bundle.bundle_id,
                signing_key_id=bundle.signing_key_id,
            )

        except Exception as e:
            logger.error(
                "bundle_verification_error",
                bundle_id=bundle.bundle_id if bundle else "unknown",
                error=str(e),
            )
            return BundleVerificationResult(
                valid=False,
                bundle_id=bundle.bundle_id if bundle else None,
                signing_key_id=None,
                error_message=f"Verification failed: {e}",
            )

    async def get_signing_key_id(self) -> str:
        """Get the current signing key ID.

        Returns:
            String identifier of the current signing key.
        """
        return self._signing_key_id

    async def get_bundle(self, bundle_id: str) -> ContextBundlePayload | None:
        """Get a stored bundle by ID.

        Args:
            bundle_id: The bundle ID to lookup.

        Returns:
            The ContextBundlePayload if found, None otherwise.
        """
        bundle = self._bundles.get(bundle_id)
        logger.debug(
            "bundle_lookup",
            bundle_id=bundle_id,
            found=bundle is not None,
        )
        return bundle

    async def _compute_hash(self, data: dict[str, object]) -> str:
        """Compute SHA-256 hash of canonical JSON.

        Args:
            data: Dictionary to hash.

        Returns:
            64-character lowercase hex hash string.
        """
        canonical = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def _create_dev_signature(self, bundle_hash: str) -> str:
        """Create DEV MODE signature.

        Per RT-1: mode is inside signature, not metadata.

        Args:
            bundle_hash: The hash to sign.

        Returns:
            DEV MODE signature string.
        """
        signable = f"[DEV MODE]{bundle_hash}{self._signing_key_id}"
        return hashlib.sha256(signable.encode("utf-8")).hexdigest()
