"""Result certifier stub implementation (Story 2.8, FR99-FR101).

In-memory stub for ResultCertifierPort for development and testing.
Follows DEV_MODE_WATERMARK pattern per RT-1/ADR-4.

Constitutional Constraints:
- FR99: Deliberation results SHALL have certified result events
- FR100: Certification SHALL include result_hash, participant_count, certification_timestamp
- FR101: Certification signature SHALL be verifiable
- RT-1/ADR-4: DEV_MODE_WATERMARK pattern for dev stubs
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.result_certifier import (
    CertificationResult,
)

logger = structlog.get_logger()


# DEV_MODE_WATERMARK per RT-1/ADR-4
# This constant indicates this is a development stub, not production code
DEV_MODE_WATERMARK: str = "DEV_STUB:ResultCertifierStub:v1"


class ResultCertifierStub:
    """In-memory stub for ResultCertifierPort (FR99-FR101).

    Development and testing implementation that stores certifications
    in memory. Follows DEV_MODE_WATERMARK pattern.

    WARNING: This is a development stub. Not for production use.
    Production implementations should use HSM for signing.

    Attributes:
        _certifications: In-memory dict mapping result_id to CertificationResult.
        _result_hashes: In-memory dict mapping result_id to result_hash.
        _deliberation_to_result: In-memory dict mapping deliberation_id to result_id.
        _halt_checker: Optional halt checker for HALT FIRST enforcement.

    Example:
        >>> stub = ResultCertifierStub()
        >>> result = await stub.certify_result(uuid4(), {"decision": "approved"})
        >>> is_valid = await stub.verify_certification(result.result_id, result.certification_signature)
        >>> is_valid  # True
    """

    def __init__(
        self,
        halt_checker: HaltChecker | None = None,
    ) -> None:
        """Initialize empty certification store.

        Args:
            halt_checker: Optional halt checker for HALT FIRST enforcement.
        """
        self._certifications: dict[UUID, CertificationResult] = {}
        self._result_hashes: dict[UUID, str] = {}
        self._deliberation_to_result: dict[UUID, UUID] = {}
        self._halt_checker = halt_checker
        logger.debug(
            "result_certifier_stub_initialized",
            watermark=DEV_MODE_WATERMARK,
        )

    async def certify_result(
        self,
        deliberation_id: UUID,
        result_content: dict[str, Any],
    ) -> CertificationResult:
        """Certify a deliberation result with cryptographic signature.

        Creates a certified result event with hash and signature that
        can be verified by external observers.

        Args:
            deliberation_id: The UUID of the deliberation to certify.
            result_content: The result content to certify (will be hashed).

        Returns:
            CertificationResult with certification details.
        """
        result_id = uuid4()
        result_hash = await self.compute_result_hash(result_content)
        certification_timestamp = datetime.now(timezone.utc)

        # DEV MODE signature - in production this would use HSM
        # The signature includes the DEV MODE watermark inside per RT-1
        signable_content = f"[DEV MODE]{result_hash}{str(deliberation_id)}"
        certification_signature = hashlib.sha256(
            signable_content.encode("utf-8")
        ).hexdigest()

        certification_key_id = f"CERT:dev-key-{DEV_MODE_WATERMARK}"

        cert = CertificationResult(
            certified=True,
            result_id=result_id,
            certification_signature=certification_signature,
            certification_key_id=certification_key_id,
            certification_timestamp=certification_timestamp,
        )

        self._certifications[result_id] = cert
        self._result_hashes[result_id] = result_hash
        self._deliberation_to_result[deliberation_id] = result_id

        logger.info(
            "result_certified",
            result_id=str(result_id),
            deliberation_id=str(deliberation_id),
            result_hash_prefix=result_hash[:8],
            certification_key_id=certification_key_id,
        )

        return cert

    async def verify_certification(
        self,
        result_id: UUID,
        signature: str,
    ) -> bool:
        """Verify a certification signature (FR101).

        Verifies that the signature matches the stored certification
        for the given result.

        Args:
            result_id: The UUID of the result to verify.
            signature: The signature to verify.

        Returns:
            True if signature is valid, False otherwise.
        """
        cert = self._certifications.get(result_id)

        if cert is None:
            logger.debug(
                "certification_not_found_for_verification",
                result_id=str(result_id),
            )
            return False

        is_valid = cert.certification_signature == signature

        if is_valid:
            logger.debug(
                "certification_verification_passed",
                result_id=str(result_id),
            )
        else:
            logger.warning(
                "certification_verification_failed",
                result_id=str(result_id),
                expected_sig_prefix=cert.certification_signature[:8] + "...",
                provided_sig_prefix=signature[:8] + "..." if len(signature) >= 8 else signature,
            )

        return is_valid

    async def get_certification(
        self,
        result_id: UUID,
    ) -> CertificationResult | None:
        """Get a stored certification result.

        Args:
            result_id: The UUID of the result.

        Returns:
            The CertificationResult if found, None otherwise.
        """
        cert = self._certifications.get(result_id)

        logger.debug(
            "certification_lookup",
            result_id=str(result_id),
            found=cert is not None,
        )

        return cert

    async def get_certification_by_deliberation(
        self,
        deliberation_id: UUID,
    ) -> CertificationResult | None:
        """Get a stored certification result by deliberation ID.

        Enables lookup of the certification for a specific deliberation.

        Args:
            deliberation_id: The UUID of the deliberation.

        Returns:
            The CertificationResult if found, None otherwise.
        """
        result_id = self._deliberation_to_result.get(deliberation_id)

        if result_id is None:
            logger.debug(
                "certification_not_found_by_deliberation",
                deliberation_id=str(deliberation_id),
            )
            return None

        cert = self._certifications.get(result_id)

        logger.debug(
            "certification_lookup_by_deliberation",
            deliberation_id=str(deliberation_id),
            result_id=str(result_id),
            found=cert is not None,
        )

        return cert

    async def compute_result_hash(
        self,
        result_content: dict[str, Any],
    ) -> str:
        """Compute SHA-256 hash of result content.

        Uses canonical JSON serialization for deterministic hashing.

        Args:
            result_content: The result content to hash.

        Returns:
            64-character hexadecimal SHA-256 hash string.
        """
        # Canonical JSON: sorted keys, no whitespace
        canonical = json.dumps(
            result_content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
