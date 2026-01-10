"""Result Certifier Port interface (Story 2.8, FR99-FR101).

This module defines the application port for result certification,
enabling deliberation results to be certified with cryptographic
signatures and hash verification.

Constitutional Constraints:
- FR99: Deliberation results SHALL have certified result events
- FR100: Certification SHALL include result_hash, participant_count, certification_timestamp
- FR101: Certification signature SHALL be verifiable
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, eq=True)
class CertificationResult:
    """Result of a certification operation (FR99-FR101).

    This dataclass captures the result of certifying a deliberation result,
    including the certification signature and key information needed for
    later verification.

    Attributes:
        certified: True if certification succeeded, False otherwise.
        result_id: Unique identifier for this certified result (UUID).
        certification_signature: The cryptographic signature (base64).
        certification_key_id: ID of key used for signing.
        certification_timestamp: When certification was created.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> result = CertificationResult(
        ...     certified=True,
        ...     result_id=uuid4(),
        ...     certification_signature="sig123",
        ...     certification_key_id="CERT:key-001",
        ...     certification_timestamp=datetime.now(timezone.utc),
        ... )
        >>> result.certified
        True
    """

    certified: bool
    result_id: UUID
    certification_signature: str
    certification_key_id: str
    certification_timestamp: datetime


class ResultCertifierPort(Protocol):
    """Port interface for result certification (FR99-FR101).

    This protocol defines the contract for result certification adapters.
    Implementations must provide certification, verification, and hash
    computation capabilities.

    Constitutional Constraints:
        - FR99: Certification creates official record
        - FR100: Required metadata captured
        - FR101: Signature verifiable

    Example implementation:
        class ResultCertifierAdapter:
            async def certify_result(
                self, deliberation_id: UUID, result_content: dict
            ) -> CertificationResult:
                hash_val = await self.compute_result_hash(result_content)
                signature = await self.hsm.sign(hash_val.encode())
                return CertificationResult(
                    certified=True,
                    result_id=uuid4(),
                    certification_signature=signature,
                    certification_key_id=self.hsm.get_current_key_id(),
                    certification_timestamp=datetime.now(timezone.utc),
                )
    """

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

        Raises:
            CertificationError: If certification fails.
        """
        ...

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
        ...

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
        ...

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
        ...
