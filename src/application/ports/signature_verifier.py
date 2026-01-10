"""Signature verifier port (Story 7.2, FR39, AC4).

This module defines the abstract interface for Ed25519 signature verification.
External observers self-verify petition signatures using this port.

Constitutional Constraints:
- CT-12: Witnessing creates accountability → Signatures must be verifiable
- AC4: Ed25519 signature algorithm for all petition signatures

Developer Golden Rules:
1. FAIL LOUD - Never accept invalid signatures
2. Ed25519 ONLY - This port is specifically for Ed25519 verification
"""

from __future__ import annotations

from typing import Protocol


class SignatureVerifierProtocol(Protocol):
    """Protocol for Ed25519 signature verification (FR39, AC4).

    Defines the contract for verifying external observer signatures.
    This enables observers to self-verify petition authenticity.

    Constitutional Constraints:
    - AC4: Ed25519 signature algorithm
    - AC4: Signature over canonical petition content bytes
    - AC4: Public key recovery from signature supported
    """

    async def verify_signature(
        self,
        public_key: str,
        signature: str,
        content: bytes,
    ) -> bool:
        """Verify an Ed25519 signature.

        Verifies that the signature was created by the holder of the
        private key corresponding to the given public key.

        Args:
            public_key: Hex-encoded Ed25519 public key.
            signature: Hex-encoded Ed25519 signature.
            content: The bytes that were signed.

        Returns:
            True if signature is valid, False otherwise.

        Note:
            This method does NOT raise on invalid signatures.
            It returns False to allow the caller to decide on error handling.
        """
        ...

    def get_algorithm(self) -> str:
        """Get the signature algorithm name.

        Returns:
            Algorithm name, always "Ed25519" for this port.
        """
        ...
