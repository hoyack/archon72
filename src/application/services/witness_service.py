"""Witness service for event attestation (FR4, FR5).

This service coordinates witness selection and attestation signing.
All witness attestations MUST go through this service to ensure:
1. Witnesses are selected from an available pool
2. RT-1 pattern: mode watermark inside signed content
3. Consistent signable content format (WITNESS_ATTESTATION prefix)

Constitutional Constraints:
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Witness attestation creates verifiable audit trail
"""

from __future__ import annotations

from src.application.ports.hsm import HSMMode, HSMProtocol, SignatureResult
from src.application.ports.witness_pool import WitnessPoolProtocol
from src.domain.errors.witness import WitnessNotFoundError
from src.domain.events.signing import signature_from_base64, signature_to_base64
from src.domain.models.signable import SignableContent
from src.domain.models.witness import Witness

# Witness attestation prefix - included in signed content
WITNESS_ATTESTATION_PREFIX: str = "WITNESS_ATTESTATION:"


class WitnessService:
    """Service for witness operations (FR4, FR5).

    Witnesses attest to event creation by signing the event content hash.
    This is separate from agent signing - witnesses verify, they don't create.

    The service coordinates:
    1. Witness selection from the pool
    2. Attestation signing with HSM
    3. Attestation verification

    Attributes:
        _hsm: HSM protocol for cryptographic operations.
        _witness_pool: Witness pool protocol for witness management.
    """

    def __init__(
        self,
        hsm: HSMProtocol,
        witness_pool: WitnessPoolProtocol,
    ) -> None:
        """Initialize the witness service.

        Args:
            hsm: HSM protocol implementation for signing.
            witness_pool: Witness pool protocol for witness selection.
        """
        self._hsm = hsm
        self._witness_pool = witness_pool

    async def attest_event(
        self,
        event_content_hash: str,
    ) -> tuple[str, str]:
        """Select witness and create attestation signature.

        This method:
        1. Selects an available witness from the pool
        2. Creates signable content with WITNESS_ATTESTATION prefix
        3. Signs with HSM (includes RT-1 mode watermark)
        4. Returns witness ID and base64 signature

        Args:
            event_content_hash: The content hash of the event to attest.
                This hash identifies the specific event being witnessed.

        Returns:
            Tuple of (witness_id, witness_signature_base64).
            - witness_id: ID of the witness (format: "WITNESS:{uuid}")
            - witness_signature_base64: Base64-encoded Ed25519 signature

        Raises:
            NoWitnessAvailableError: If no witnesses are available (RT-1).
                This MUST cause the event write to be rejected.
        """
        # Select available witness (raises NoWitnessAvailableError if none available)
        witness: Witness = await self._witness_pool.get_available_witness()

        # Compute witness signable content
        # Witnesses sign: WITNESS_ATTESTATION:{content_hash}
        # This attests to the specific event identified by the hash
        signable_raw = f"{WITNESS_ATTESTATION_PREFIX}{event_content_hash}".encode()

        # Wrap in SignableContent to include RT-1 mode watermark
        signable = SignableContent(raw_content=signable_raw)

        # Sign with HSM (mode watermark is added by SignableContent.to_bytes())
        result: SignatureResult = await self._hsm.sign(signable.to_bytes())

        return (
            witness.witness_id,
            signature_to_base64(result.signature),
        )

    async def verify_attestation(
        self,
        event_content_hash: str,
        witness_id: str,
        witness_signature_b64: str,
    ) -> bool:
        """Verify a witness attestation signature.

        Reconstructs the signable content and verifies the signature
        using the witness's public key.

        Args:
            event_content_hash: The content hash of the event that was attested.
            witness_id: ID of the witness that attested the event.
            witness_signature_b64: Base64-encoded witness signature.

        Returns:
            True if attestation is valid, False otherwise.

        Raises:
            WitnessNotFoundError: If witness cannot be found by ID.
        """
        # Lookup witness for public key
        witness: Witness | None = await self._witness_pool.get_witness_by_id(witness_id)
        if witness is None:
            raise WitnessNotFoundError(witness_id)

        # Reconstruct signable content
        signable_raw = f"{WITNESS_ATTESTATION_PREFIX}{event_content_hash}".encode()
        signable = SignableContent(raw_content=signable_raw)

        # Determine mode for verification (use current HSM mode)
        mode = await self._hsm.get_mode()
        is_dev_mode = mode == HSMMode.DEVELOPMENT

        # Reconstruct with the same mode that was used during signing
        content_with_mode = signable.to_bytes_with_mode(dev_mode=is_dev_mode)

        # Decode signature
        signature = signature_from_base64(witness_signature_b64)

        # Verify with HSM using witness's key
        # Note: We use the witness_id as the key_id for lookup
        return await self._hsm.verify_with_key(
            content_with_mode,
            signature,
            witness_id,
        )
