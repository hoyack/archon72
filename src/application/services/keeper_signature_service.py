"""Keeper Signature Service (FR68-FR70).

This service handles cryptographic signing and verification of Keeper overrides.
All override signature operations MUST go through this service to ensure:
1. Keeper identity is verified via registered keys
2. Signatures are cryptographically valid
3. Full authorization chain is recorded (FR70)

Constitutional Constraints:
- FR68: Override commands require cryptographic signature from registered Keeper key
- FR69: Keeper keys must be generated through witnessed ceremony (Story 5.7)
- FR70: Every override must record full authorization chain

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Invalid signatures MUST raise errors
- CT-12: Witnessing creates accountability -> Keeper signatures create verifiable attribution
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from structlog import get_logger

from src.application.ports.hsm import HSMMode, HSMProtocol
from src.application.ports.keeper_key_registry import KeeperKeyRegistryProtocol
from src.domain.errors.keeper_signature import (
    InvalidKeeperSignatureError,
    KeeperKeyNotFoundError,
)
from src.domain.events.override_event import OverrideEventPayload
from src.domain.models.signable import SignableContent

logger = get_logger()


@dataclass(frozen=True)
class KeeperSignedOverride:
    """Signed override request wrapper.

    Contains the override payload along with its cryptographic signature.
    This enables verification of Keeper identity before processing.

    Attributes:
        override_payload: The override action details.
        signature: Base64-encoded Ed25519 signature.
        signing_key_id: HSM key ID used for signing.
        signed_at: Timestamp when signature was created.
    """

    override_payload: OverrideEventPayload
    signature: str  # Base64-encoded Ed25519 signature
    signing_key_id: str
    signed_at: datetime


class KeeperSignatureService:
    """Service for Keeper override signature operations (FR68-FR70).

    This service provides:
    1. sign_override(): Sign an override with Keeper's active key
    2. verify_override_signature(): Verify a signed override

    All Keeper override operations that require signing MUST use this service.

    Constitutional Constraints:
    - FR68: Overrides require cryptographic signature from registered Keeper key
    - FR70: Record full authorization chain from Keeper identity through execution

    Attributes:
        _hsm: HSM protocol for cryptographic operations.
        _key_registry: Keeper key registry for key lookup.
    """

    def __init__(
        self,
        hsm: HSMProtocol,
        key_registry: KeeperKeyRegistryProtocol,
    ) -> None:
        """Initialize the Keeper Signature Service.

        Args:
            hsm: HSM protocol implementation for signing.
            key_registry: Keeper key registry for key management.
        """
        self._hsm = hsm
        self._key_registry = key_registry

    async def sign_override(
        self,
        override_payload: OverrideEventPayload,
        keeper_id: str,
    ) -> KeeperSignedOverride:
        """Sign an override with Keeper's active key.

        Creates a cryptographic signature for the override payload using
        the Keeper's currently active key from the registry.

        Args:
            override_payload: The override action details to sign.
            keeper_id: ID of the Keeper signing the override.

        Returns:
            KeeperSignedOverride with signature and key information.

        Raises:
            KeeperKeyNotFoundError: If no active key for Keeper.
        """
        log = logger.bind(
            operation="sign_override",
            keeper_id=keeper_id,
            scope=override_payload.scope,
        )

        # Get active key for keeper
        key = await self._key_registry.get_active_key_for_keeper(keeper_id)
        if key is None:
            log.warning(
                "keeper_key_not_found",
                message="No active key found for Keeper",
            )
            raise KeeperKeyNotFoundError(
                f"FR68: No active key found for Keeper {keeper_id}"
            )

        # Create signable content from payload
        signable_content = self._create_signable_content(override_payload)

        # Sign with HSM
        result = await self._hsm.sign(signable_content)

        log.info(
            "override_signed",
            key_id=result.key_id,
            message="Override successfully signed",
        )

        return KeeperSignedOverride(
            override_payload=override_payload,
            signature=base64.b64encode(result.signature).decode("utf-8"),
            signing_key_id=result.key_id,
            signed_at=datetime.now(timezone.utc),
        )

    async def verify_override_signature(
        self,
        signed_override: KeeperSignedOverride,
    ) -> bool:
        """Verify a Keeper override signature (FR68).

        Reconstructs the signable content and verifies the signature
        using the specified key from the registry.

        Args:
            signed_override: The signed override to verify.

        Returns:
            True if signature is valid, False otherwise.

        Raises:
            InvalidKeeperSignatureError: If signing key not found in registry.
        """
        log = logger.bind(
            operation="verify_override_signature",
            keeper_id=signed_override.override_payload.keeper_id,
            key_id=signed_override.signing_key_id,
        )

        # Get key from registry
        key = await self._key_registry.get_key_by_id(signed_override.signing_key_id)
        if key is None:
            log.warning(
                "signing_key_not_found",
                message="FR68: Signing key not found in registry",
            )
            raise InvalidKeeperSignatureError(
                f"FR68: Invalid Keeper signature - signing key not found: {signed_override.signing_key_id}"
            )

        # Verify key was active at signing time
        if not key.is_active_at(signed_override.signed_at):
            log.warning(
                "key_not_active_at_signing_time",
                signed_at=signed_override.signed_at.isoformat(),
                active_from=key.active_from.isoformat(),
                active_until=key.active_until.isoformat() if key.active_until else None,
            )
            raise InvalidKeeperSignatureError(
                "FR68: Invalid Keeper signature - key was not active at signing time"
            )

        # Reconstruct signable content
        raw_signable_content = self._create_signable_content(
            signed_override.override_payload
        )

        # Decode signature
        try:
            signature = base64.b64decode(signed_override.signature)
        except Exception as e:
            log.warning(
                "signature_decode_failed",
                error=str(e),
            )
            raise InvalidKeeperSignatureError(
                f"FR68: Invalid Keeper signature - failed to decode signature: {e}"
            ) from e

        # Get HSM mode to determine content prefix
        hsm_mode = await self._hsm.get_mode()
        is_dev_mode = hsm_mode == HSMMode.DEVELOPMENT

        # Wrap content with SignableContent to add mode prefix (RT-1)
        signable = SignableContent(raw_content=raw_signable_content)
        content_with_prefix = signable.to_bytes_with_mode(dev_mode=is_dev_mode)

        # Verify with the specific key
        is_valid = await self._hsm.verify_with_key(
            content_with_prefix,
            signature,
            signed_override.signing_key_id,
        )

        if is_valid:
            log.info(
                "signature_verified",
                message="Keeper signature is valid",
            )
        else:
            log.warning(
                "signature_invalid",
                message="FR68: Invalid Keeper signature",
            )

        return is_valid

    def _create_signable_content(
        self,
        payload: OverrideEventPayload,
    ) -> bytes:
        """Create canonical signable content from override payload.

        Creates a deterministic byte representation of the payload
        for signing/verification. Uses sorted JSON keys for reproducibility.

        Args:
            payload: The override event payload.

        Returns:
            Canonical bytes to sign.
        """
        return json.dumps(
            {
                "keeper_id": payload.keeper_id,
                "scope": payload.scope,
                "duration": payload.duration,
                "reason": payload.reason,
                "action_type": payload.action_type.value,
                "initiated_at": payload.initiated_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),  # Compact JSON
        ).encode("utf-8")
