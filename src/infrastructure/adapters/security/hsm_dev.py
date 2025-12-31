"""Development HSM stub implementation.

WARNING: This is a SOFTWARE HSM for LOCAL DEVELOPMENT ONLY.
Keys are stored in plain text files and are NOT SECURE.

RT-1 Pattern: All signatures include [DEV MODE] prefix inside
the signed content to prevent confusion with production signatures.

ADR-4: Development mode uses software HSM stub with watermark.
"""

import base64
import json
import uuid
from pathlib import Path

import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from src.application.ports.hsm import HSMMode, HSMProtocol, SignatureResult
from src.domain.errors.hsm import HSMKeyNotFoundError
from src.domain.models.signable import SignableContent

log = structlog.get_logger()


class DevHSM(HSMProtocol):
    """Software HSM stub for development.

    WARNING: NOT FOR PRODUCTION USE.

    This implementation:
    - Uses Ed25519 for signing (fast, secure algorithm)
    - Stores keys in ~/.archon72/dev_keys.json (NOT SECURE)
    - Includes [DEV MODE] watermark in all signatures
    - Logs warnings about insecure key storage

    AC1: Creates signatures with [DEV MODE] prefix inside content
    AC2: Signature metadata contains mode: "development"
    AC4: Logs warning on initialization
    """

    # Default key storage location
    DEFAULT_KEY_DIR = Path.home() / ".archon72"
    DEFAULT_KEY_FILE = "dev_keys.json"

    def __init__(
        self,
        key_dir: Path | None = None,
        key_file: str | None = None,
    ) -> None:
        """Initialize the development HSM.

        Args:
            key_dir: Directory for key storage. Defaults to ~/.archon72/
            key_file: Filename for keys. Defaults to dev_keys.json
        """
        self._key_dir = key_dir or self.DEFAULT_KEY_DIR
        self._key_file = key_file or self.DEFAULT_KEY_FILE
        self._key_path = self._key_dir / self._key_file

        # In-memory key cache
        self._keys: dict[str, tuple[Ed25519PrivateKey, Ed25519PublicKey]] = {}
        self._current_key_id: str | None = None

        # Log security warning
        log.warning(
            "hsm_dev_mode_active",
            message="Using software HSM - NOT FOR PRODUCTION",
            key_storage=str(self._key_path),
        )

        # Load existing keys if available
        self._load_keys()

    def _ensure_key_dir(self) -> None:
        """Create key directory if it doesn't exist."""
        self._key_dir.mkdir(parents=True, exist_ok=True)

    def _load_keys(self) -> None:
        """Load keys from disk if they exist."""
        if not self._key_path.exists():
            return

        try:
            with open(self._key_path) as f:
                data = json.load(f)

            for key_id, key_data in data.get("keys", {}).items():
                private_bytes = base64.b64decode(key_data["private"])
                private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
                public_key = private_key.public_key()
                self._keys[key_id] = (private_key, public_key)

            self._current_key_id = data.get("current_key_id")

            log.debug(
                "hsm_keys_loaded",
                key_count=len(self._keys),
                current_key_id=self._current_key_id,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            log.warning("hsm_key_load_failed", error=str(e))

    def _save_keys(self) -> None:
        """Save keys to disk."""
        self._ensure_key_dir()

        data: dict[str, object] = {
            "keys": {},
            "current_key_id": self._current_key_id,
        }

        keys_dict: dict[str, dict[str, str]] = {}
        for key_id, (private_key, _) in self._keys.items():
            private_bytes = private_key.private_bytes(
                encoding=Encoding.Raw,
                format=PrivateFormat.Raw,
                encryption_algorithm=NoEncryption(),
            )
            keys_dict[key_id] = {
                "private": base64.b64encode(private_bytes).decode(),
            }
        data["keys"] = keys_dict

        with open(self._key_path, "w") as f:
            json.dump(data, f, indent=2)

        log.debug("hsm_keys_saved", key_path=str(self._key_path))

    async def sign(self, content: bytes) -> SignatureResult:
        """Sign content with [DEV MODE] watermark.

        The content is wrapped in SignableContent to add the mode prefix,
        then signed with Ed25519.

        Args:
            content: Raw bytes to sign.

        Returns:
            SignatureResult with signature and development mode metadata.

        Raises:
            HSMKeyNotFoundError: If no key has been generated.
        """
        if not self._current_key_id or self._current_key_id not in self._keys:
            # Auto-generate a key if none exists
            await self.generate_key_pair()

        if self._current_key_id is None:
            raise HSMKeyNotFoundError()

        private_key, _ = self._keys[self._current_key_id]

        # Create signable content with dev mode prefix
        signable = SignableContent(raw_content=content)
        content_with_prefix = signable.to_bytes_with_mode(dev_mode=True)

        # Sign the content (including mode prefix)
        signature = private_key.sign(content_with_prefix)

        log.debug(
            "hsm_sign_complete",
            mode="development",
            key_id=self._current_key_id,
            content_length=len(content),
        )

        return SignatureResult(
            content=content_with_prefix,
            signature=signature,
            mode=HSMMode.DEVELOPMENT,
            key_id=self._current_key_id,
        )

    async def verify(self, content: bytes, signature: bytes) -> bool:
        """Verify a signature against content.

        Args:
            content: Content with mode prefix (as returned by sign).
            signature: The signature to verify.

        Returns:
            True if signature is valid.
        """
        if not self._current_key_id or self._current_key_id not in self._keys:
            log.warning("hsm_verify_no_key")
            return False

        _, public_key = self._keys[self._current_key_id]

        try:
            public_key.verify(signature, content)
            log.debug("hsm_verify_success")
            return True
        except InvalidSignature:
            log.warning("hsm_verify_failed", reason="invalid_signature")
            return False

    async def verify_with_key(
        self, content: bytes, signature: bytes, key_id: str
    ) -> bool:
        """Verify a signature with a specific key.

        Args:
            content: Content with mode prefix.
            signature: The signature to verify.
            key_id: The key ID to use for verification.

        Returns:
            True if signature is valid.
        """
        if key_id not in self._keys:
            log.warning("hsm_verify_key_not_found", key_id=key_id)
            return False

        _, public_key = self._keys[key_id]

        try:
            public_key.verify(signature, content)
            return True
        except InvalidSignature:
            return False

    async def generate_key_pair(self) -> str:
        """Generate a new Ed25519 key pair.

        Returns:
            The key_id of the new key pair.
        """
        # Generate new key
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # Create key ID
        key_id = f"dev-{uuid.uuid4().hex[:8]}"

        # Store key
        self._keys[key_id] = (private_key, public_key)
        self._current_key_id = key_id

        # Persist to disk
        self._save_keys()

        log.info(
            "hsm_key_generated",
            key_id=key_id,
            mode="development",
            warning="Keys stored in plain text - NOT FOR PRODUCTION",
        )

        return key_id

    async def get_mode(self) -> HSMMode:
        """Return development mode.

        Returns:
            HSMMode.DEVELOPMENT always for this implementation.
        """
        return HSMMode.DEVELOPMENT

    async def get_current_key_id(self) -> str:
        """Return the current signing key ID.

        Returns:
            The current key ID.

        Raises:
            HSMKeyNotFoundError: If no key has been generated.
        """
        if not self._current_key_id:
            raise HSMKeyNotFoundError()
        return self._current_key_id

    async def get_public_key_bytes(self, key_id: str | None = None) -> bytes:
        """Get the public key bytes for verification.

        Args:
            key_id: Key ID to get. Defaults to current key.

        Returns:
            Raw public key bytes.

        Raises:
            HSMKeyNotFoundError: If key not found.
        """
        target_key_id = key_id or self._current_key_id
        if not target_key_id or target_key_id not in self._keys:
            raise HSMKeyNotFoundError(target_key_id or "")

        _, public_key = self._keys[target_key_id]
        return public_key.public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
