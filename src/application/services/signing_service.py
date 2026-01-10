"""Centralized signing service (FP-5 Pattern).

This service orchestrates event signing using the HSM protocol.
All event signing MUST go through this service to ensure:
1. Key ID is always included
2. RT-1 pattern: mode watermark inside signed content
3. Chain binding: prev_hash included in signable content (MA-2)

Constitutional Constraints:
- FR74: Invalid agent signatures must be rejected
- MA-2: Signature must cover prev_hash (chain binding)

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Agent attribution creates verifiable authorship
"""

from __future__ import annotations

from src.application.ports.hsm import HSMProtocol, SignatureResult
from src.application.ports.key_registry import KeyRegistryProtocol
from src.domain.events.signing import (
    SIG_ALG_VERSION,
    compute_signable_content,
    signature_from_base64,
    signature_to_base64,
)
from src.domain.models.signable import SignableContent


class SigningService:
    """Centralized signing service (FP-5 Pattern).

    All event signing MUST go through this service to ensure:
    1. Key ID is always included
    2. RT-1 pattern: mode watermark inside signed content
    3. Chain binding: prev_hash included in signable content

    Attributes:
        _hsm: HSM protocol for cryptographic operations.
        _key_registry: Key registry for key lookup.
    """

    def __init__(
        self,
        hsm: HSMProtocol,
        key_registry: KeyRegistryProtocol,
    ) -> None:
        """Initialize the signing service.

        Args:
            hsm: HSM protocol implementation for signing.
            key_registry: Key registry for key management.
        """
        self._hsm = hsm
        self._key_registry = key_registry

    async def sign_event(
        self,
        content_hash: str,
        prev_hash: str,
        agent_id: str,
    ) -> tuple[str, str, int]:
        """Sign an event and return signature data.

        Creates a cryptographic signature covering the content_hash,
        prev_hash, and agent_id. The prev_hash inclusion ensures chain
        binding (MA-2 pattern) - the signature is invalid if the event
        is moved to a different position in the chain.

        Args:
            content_hash: SHA-256 hash of event content.
            prev_hash: Hash of previous event (chain binding).
            agent_id: ID of agent creating the event.
                Format: "agent-{uuid}" or "SYSTEM:{service_name}".

        Returns:
            Tuple of (signature_base64, signing_key_id, sig_alg_version).
            - signature_base64: Base64-encoded Ed25519 signature.
            - signing_key_id: HSM key ID used for signing.
            - sig_alg_version: Algorithm version (1 = Ed25519).
        """
        # Compute signable content (includes chain binding)
        signable_bytes = compute_signable_content(
            content_hash=content_hash,
            prev_hash=prev_hash,
            agent_id=agent_id,
        )

        # Sign with HSM (includes mode watermark via RT-1 pattern)
        result: SignatureResult = await self._hsm.sign(signable_bytes)

        return (
            signature_to_base64(result.signature),
            result.key_id,
            SIG_ALG_VERSION,
        )

    async def verify_event_signature(
        self,
        content_hash: str,
        prev_hash: str,
        agent_id: str,
        signature_b64: str,
        signing_key_id: str,
    ) -> bool:
        """Verify an event's signature.

        Reconstructs the signable content and verifies the signature
        using the specified key.

        Args:
            content_hash: SHA-256 hash of event content.
            prev_hash: Hash of previous event.
            agent_id: ID of agent that created the event.
            signature_b64: Base64-encoded signature.
            signing_key_id: Key ID used for signing.

        Returns:
            True if signature is valid, False otherwise.
        """
        from src.application.ports.hsm import HSMMode

        # Reconstruct signable content
        signable_bytes = compute_signable_content(
            content_hash=content_hash,
            prev_hash=prev_hash,
            agent_id=agent_id,
        )

        # Determine if we're in dev mode based on HSM mode
        mode = await self._hsm.get_mode()
        is_dev_mode = mode == HSMMode.DEVELOPMENT

        # Reconstruct with the same mode that was used during signing
        signable = SignableContent(raw_content=signable_bytes)
        content_with_mode = signable.to_bytes_with_mode(dev_mode=is_dev_mode)

        # Decode signature
        signature = signature_from_base64(signature_b64)

        # Verify with the specific key
        return await self._hsm.verify_with_key(
            content_with_mode,
            signature,
            signing_key_id,
        )
