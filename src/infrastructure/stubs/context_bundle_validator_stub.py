"""Context Bundle Validator stub implementation (Story 2.9, ADR-2).

In-memory stub for ContextBundleValidatorPort for development and testing.
Follows DEV_MODE_WATERMARK pattern per RT-1/ADR-4.

ADR-2 Requirements:
- Signature MUST be verified BEFORE parsing/using content
- Invalid signature = "ADR-2: Invalid context bundle signature"
- as_of_event_seq must exist in canonical chain

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Clear validation errors
- CT-13: Integrity outranks availability -> Validation before use
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern for dev stubs
"""

from __future__ import annotations

import hashlib
import json

import structlog

from src.application.ports.context_bundle_validator import (
    BundleValidationResult,
    ContextBundleValidatorPort,
    FreshnessCheckResult,
)
from src.domain.models.context_bundle import (
    CONTENT_REF_LENGTH,
    CONTENT_REF_PREFIX,
    CONTEXT_BUNDLE_SCHEMA_VERSION,
    MAX_PRECEDENT_REFS,
    ContextBundlePayload,
)

logger = structlog.get_logger()


# DEV_MODE_WATERMARK per RT-1/ADR-4
DEV_MODE_WATERMARK: str = "DEV_STUB:ContextBundleValidatorStub:v1"


class ContextBundleValidatorStub(ContextBundleValidatorPort):
    """In-memory stub for ContextBundleValidatorPort (ADR-2).

    Development and testing implementation that validates bundles
    according to ADR-2 requirements.

    WARNING: This is a development stub. Not for production use.
    Production implementations should use HSM for signature verification.

    Example:
        >>> stub = ContextBundleValidatorStub()
        >>> result = await stub.validate_signature(bundle)
        >>> result.valid  # True if signature matches
    """

    def __init__(
        self,
        signing_key_id: str | None = None,
    ) -> None:
        """Initialize validator stub.

        Args:
            signing_key_id: Expected signing key ID for validation.
        """
        self._signing_key_id = (
            signing_key_id or "BUNDLE:DEV_STUB:ContextBundleCreatorStub:v1"
        )
        logger.debug(
            "context_bundle_validator_stub_initialized",
            watermark=DEV_MODE_WATERMARK,
            expected_key_id=self._signing_key_id,
        )

    async def validate_signature(
        self,
        bundle: ContextBundlePayload,
    ) -> BundleValidationResult:
        """Validate bundle signature.

        ADR-2 Critical: This MUST be called BEFORE using bundle content.

        Args:
            bundle: The bundle to validate.

        Returns:
            BundleValidationResult indicating if signature is valid.
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
                return BundleValidationResult(
                    valid=False,
                    bundle_id=bundle.bundle_id,
                    error_code="HASH_MISMATCH",
                    error_message="ADR-2: Invalid context bundle signature (hash mismatch)",
                )

            # Verify DEV MODE signature
            expected_signature = await self._create_dev_signature(
                bundle.bundle_hash,
                bundle.signing_key_id,
            )
            if bundle.signature != expected_signature:
                logger.warning(
                    "bundle_signature_mismatch",
                    bundle_id=bundle.bundle_id,
                )
                return BundleValidationResult(
                    valid=False,
                    bundle_id=bundle.bundle_id,
                    error_code="INVALID_SIGNATURE",
                    error_message="ADR-2: Invalid context bundle signature",
                )

            logger.debug(
                "signature_validation_passed",
                bundle_id=bundle.bundle_id,
            )

            return BundleValidationResult(
                valid=True,
                bundle_id=bundle.bundle_id,
            )

        except Exception as e:
            logger.error(
                "signature_validation_error",
                bundle_id=bundle.bundle_id if bundle else "unknown",
                error=str(e),
            )
            return BundleValidationResult(
                valid=False,
                bundle_id=bundle.bundle_id if bundle else None,
                error_code="VALIDATION_ERROR",
                error_message=f"Signature validation failed: {e}",
            )

    async def validate_schema(
        self,
        bundle: ContextBundlePayload,
    ) -> BundleValidationResult:
        """Validate bundle against JSON Schema requirements.

        Validates:
        - schema_version is "1.0"
        - Required fields present
        - ContentRef format correct
        - precedent_refs count <= MAX_PRECEDENT_REFS

        Args:
            bundle: The bundle to validate.

        Returns:
            BundleValidationResult indicating if schema is valid.
        """
        errors: list[str] = []

        # Check schema version
        if bundle.schema_version != CONTEXT_BUNDLE_SCHEMA_VERSION:
            errors.append(
                f"schema_version must be '{CONTEXT_BUNDLE_SCHEMA_VERSION}', "
                f"got '{bundle.schema_version}'"
            )

        # Check ContentRef formats
        if not self._is_valid_content_ref(bundle.identity_prompt_ref):
            errors.append("identity_prompt_ref is not valid ContentRef format")

        if not self._is_valid_content_ref(bundle.meeting_state_ref):
            errors.append("meeting_state_ref is not valid ContentRef format")

        # Check precedent_refs
        if len(bundle.precedent_refs) > MAX_PRECEDENT_REFS:
            errors.append(
                f"precedent_refs exceeds max of {MAX_PRECEDENT_REFS}, "
                f"has {len(bundle.precedent_refs)}"
            )

        for i, ref in enumerate(bundle.precedent_refs):
            if not self._is_valid_content_ref(ref):
                errors.append(f"precedent_refs[{i}] is not valid ContentRef format")

        # Check bundle_hash format (64 hex chars)
        if len(bundle.bundle_hash) != 64:
            errors.append("bundle_hash must be 64 character hex string")

        # Check as_of_event_seq
        if bundle.as_of_event_seq < 1:
            errors.append("as_of_event_seq must be >= 1")

        if errors:
            logger.warning(
                "schema_validation_failed",
                bundle_id=bundle.bundle_id,
                error_count=len(errors),
            )
            return BundleValidationResult(
                valid=False,
                bundle_id=bundle.bundle_id,
                error_code="SCHEMA_INVALID",
                error_message=f"Schema validation failed: {'; '.join(errors[:3])}",
            )

        logger.debug(
            "schema_validation_passed",
            bundle_id=bundle.bundle_id,
        )

        return BundleValidationResult(
            valid=True,
            bundle_id=bundle.bundle_id,
        )

    async def validate_freshness(
        self,
        bundle: ContextBundlePayload,
        current_head_seq: int,
    ) -> FreshnessCheckResult:
        """Validate bundle is not stale.

        ADR-2: Bundle's as_of_event_seq must exist in canonical chain.
        - Cannot be 0 (invalid)
        - Cannot be > current_head_seq (future/invalid)

        Args:
            bundle: The bundle to validate.
            current_head_seq: The current head sequence in the event chain.

        Returns:
            FreshnessCheckResult indicating if bundle is fresh.
        """
        as_of = bundle.as_of_event_seq

        # Check for future sequence (invalid)
        if as_of > current_head_seq:
            logger.warning(
                "bundle_references_future_sequence",
                bundle_id=bundle.bundle_id,
                as_of_event_seq=as_of,
                current_head_seq=current_head_seq,
            )
            return FreshnessCheckResult(
                fresh=False,
                as_of_event_seq=as_of,
                current_head_seq=current_head_seq,
                error_message=(
                    f"Bundle references future sequence {as_of} "
                    f"(current head: {current_head_seq})"
                ),
            )

        # Valid: sequence exists in chain (1 <= as_of <= current_head)
        logger.debug(
            "freshness_validation_passed",
            bundle_id=bundle.bundle_id,
            as_of_event_seq=as_of,
            current_head_seq=current_head_seq,
        )

        return FreshnessCheckResult(
            fresh=True,
            as_of_event_seq=as_of,
            current_head_seq=current_head_seq,
        )

    async def validate_all(
        self,
        bundle: ContextBundlePayload,
        current_head_seq: int,
    ) -> BundleValidationResult:
        """Perform all validations on a bundle.

        Order per ADR-2:
        1. Signature validation (MUST be first)
        2. Schema validation
        3. Freshness validation

        Args:
            bundle: The bundle to validate.
            current_head_seq: The current head sequence in the event chain.

        Returns:
            BundleValidationResult with combined validation status.
        """
        # 1. Signature validation FIRST (ADR-2 requirement)
        sig_result = await self.validate_signature(bundle)
        if not sig_result.valid:
            return sig_result

        # 2. Schema validation
        schema_result = await self.validate_schema(bundle)
        if not schema_result.valid:
            return schema_result

        # 3. Freshness validation
        freshness_result = await self.validate_freshness(bundle, current_head_seq)
        if not freshness_result.fresh:
            return BundleValidationResult(
                valid=False,
                bundle_id=bundle.bundle_id,
                error_code="STALE_BUNDLE",
                error_message=freshness_result.error_message,
            )

        logger.info(
            "bundle_fully_validated",
            bundle_id=bundle.bundle_id,
            as_of_event_seq=bundle.as_of_event_seq,
        )

        return BundleValidationResult(
            valid=True,
            bundle_id=bundle.bundle_id,
        )

    def _is_valid_content_ref(self, ref: str) -> bool:
        """Check if string is valid ContentRef format.

        Args:
            ref: String to check.

        Returns:
            True if valid ContentRef format.
        """
        if not ref.startswith(CONTENT_REF_PREFIX):
            return False
        if len(ref) != CONTENT_REF_LENGTH:
            return False
        # Check hex characters after prefix
        hash_part = ref[len(CONTENT_REF_PREFIX) :]
        try:
            int(hash_part, 16)
            return hash_part == hash_part.lower()
        except ValueError:
            return False

    async def _compute_hash(self, data: dict[str, object]) -> str:
        """Compute SHA-256 hash of canonical JSON."""
        canonical = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def _create_dev_signature(self, bundle_hash: str, key_id: str) -> str:
        """Create expected DEV MODE signature for verification."""
        signable = f"[DEV MODE]{bundle_hash}{key_id}"
        return hashlib.sha256(signable.encode("utf-8")).hexdigest()
