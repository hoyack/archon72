"""Signed fork detection signal domain model (FR84, Story 3.8).

This module defines the SignedForkSignal for cryptographically signed
fork detection signals. Signing enables external observers to verify
the authenticity of fork detection events.

Constitutional Constraints:
- FR84: Fork detection signals MUST be signed by the detecting service
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

Security Considerations:
- Signatures prevent fabricated fork detection attacks
- Key ID enables signature verification and key rotation
- Algorithm version supports future cryptographic updates
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.events.fork_detected import ForkDetectedPayload


@dataclass(frozen=True, eq=True)
class SignedForkSignal:
    """Signed fork detection signal (FR84).

    Contains a fork detection payload with cryptographic signature
    for observer verification. The signature is created by the
    detecting service using its private key.

    Constitutional Constraints:
    - FR84: Fork signals must be signed
    - CT-12: Witnessing creates accountability
    - CT-13: Integrity outranks availability

    Attributes:
        fork_payload: The fork detection details
        signature: Base64-encoded cryptographic signature
        signing_key_id: Key ID used for signing (enables verification)
        sig_alg_version: Signature algorithm version for future-proofing

    Security Notes:
        - signature covers fork_payload.signable_content()
        - Observers verify signature using signing_key_id
        - sig_alg_version enables cryptographic agility
    """

    # The fork detection payload containing all detection details
    fork_payload: ForkDetectedPayload

    # Base64-encoded signature over fork_payload.signable_content()
    signature: str

    # Key ID used for signing - enables key lookup for verification
    signing_key_id: str

    # Signature algorithm version - enables cryptographic evolution
    sig_alg_version: int

    def get_signable_content(self) -> bytes:
        """Get the content that was signed.

        Returns the canonical byte representation from the fork payload
        that the signature was computed over.

        Returns:
            bytes: The signable content from fork_payload
        """
        return self.fork_payload.signable_content()
