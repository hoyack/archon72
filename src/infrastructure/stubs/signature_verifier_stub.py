"""Signature verifier stub implementation (Story 7.2, FR39, AC4).

This module provides a stub implementation of SignatureVerifierProtocol
for development and testing purposes.

Constitutional Constraints:
- AC4: Ed25519 signature algorithm for all petition signatures
- CT-12: Witnessing creates accountability → Signatures must be verifiable

In development mode, this stub can be configured to accept all signatures
or to validate signatures using actual Ed25519 cryptography.
"""

from __future__ import annotations

from src.application.ports.signature_verifier import SignatureVerifierProtocol


class SignatureVerifierStub(SignatureVerifierProtocol):
    """Stub implementation of SignatureVerifierProtocol.

    This stub provides configurable signature verification behavior:
    - accept_all=True: Accept all signatures (for testing)
    - accept_all=False: Reject all signatures (for testing error paths)

    For actual Ed25519 verification, use a real implementation.

    Attributes:
        accept_all: Whether to accept all signatures.
    """

    def __init__(self, accept_all: bool = True) -> None:
        """Initialize the stub.

        Args:
            accept_all: If True, all signatures are accepted.
                       If False, all signatures are rejected.
        """
        self._accept_all = accept_all

    async def verify_signature(
        self,
        public_key: str,
        signature: str,
        content: bytes,
    ) -> bool:
        """Verify an Ed25519 signature (stub).

        In this stub implementation, the result is determined by
        the accept_all configuration.

        Args:
            public_key: Hex-encoded Ed25519 public key.
            signature: Hex-encoded Ed25519 signature.
            content: The bytes that were signed.

        Returns:
            True if accept_all is True, False otherwise.
        """
        return self._accept_all

    def get_algorithm(self) -> str:
        """Get the signature algorithm name.

        Returns:
            Algorithm name, always "Ed25519" for this port.
        """
        return "Ed25519"

    def set_accept_all(self, accept_all: bool) -> None:
        """Configure whether to accept all signatures.

        Args:
            accept_all: If True, all signatures are accepted.
        """
        self._accept_all = accept_all
