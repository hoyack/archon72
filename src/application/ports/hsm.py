"""HSM (Hardware Security Module) protocol definition.

Defines the abstract interface for HSM operations including signing,
verification, and key management. Infrastructure adapters must implement
this protocol.

ADR-4: Key Custody, Signing, and Rotation (HSM Strategy)
- Production: Cloud HSM (AWS CloudHSM or equivalent)
- Development: Software HSM stub with [DEV MODE] watermark
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class HSMMode(Enum):
    """HSM operation mode.

    Determines whether the HSM is operating in development or production mode.
    The mode MUST be included in signed content (RT-1 pattern).
    """

    DEVELOPMENT = "development"
    PRODUCTION = "production"


@dataclass(frozen=True)
class SignatureResult:
    """Result of a signing operation.

    Attributes:
        content: The original content that was signed.
        signature: The cryptographic signature bytes.
        mode: The HSM mode used for signing (DEVELOPMENT or PRODUCTION).
        key_id: The identifier of the key used for signing.
    """

    content: bytes
    signature: bytes
    mode: HSMMode
    key_id: str


class HSMProtocol(ABC):
    """Abstract protocol for HSM operations.

    All HSM implementations (dev stub, cloud HSM) must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific HSM implementations.

    Security Requirements (RT-1 Pattern):
    - Mode watermark MUST be inside signed content, not metadata
    - Production mode MUST fail without real HSM configured
    - Dev mode signatures MUST include [DEV MODE] prefix in signable content
    """

    @abstractmethod
    async def sign(self, content: bytes) -> SignatureResult:
        """Sign content and return signature with metadata.

        The signed content includes mode prefix INSIDE the signature (RT-1 pattern):
        - Dev mode: b"[DEV MODE]" + content
        - Prod mode: b"[PROD]" + content

        Args:
            content: The raw bytes to sign.

        Returns:
            SignatureResult containing signature and metadata.

        Raises:
            HSMNotConfiguredError: If production mode without HSM configured.
            HSMError: For other HSM-related failures.
        """
        ...

    @abstractmethod
    async def verify(self, content: bytes, signature: bytes) -> bool:
        """Verify a signature against content.

        Content must include the same mode prefix used during signing.

        Args:
            content: The original content (with mode prefix).
            signature: The signature to verify.

        Returns:
            True if signature is valid, False otherwise.

        Raises:
            HSMError: For HSM-related failures during verification.
        """
        ...

    @abstractmethod
    async def generate_key_pair(self) -> str:
        """Generate a new signing key pair.

        In development mode, keys are stored locally (NOT secure).
        In production mode, keys are generated in the Cloud HSM.

        Returns:
            The key_id of the newly generated key pair.

        Raises:
            HSMNotConfiguredError: If production mode without HSM configured.
            HSMError: For key generation failures.
        """
        ...

    @abstractmethod
    async def get_mode(self) -> HSMMode:
        """Return the current HSM operating mode.

        Returns:
            HSMMode.DEVELOPMENT for software stub.
            HSMMode.PRODUCTION for cloud HSM.
        """
        ...

    @abstractmethod
    async def get_current_key_id(self) -> str:
        """Return the current signing key ID.

        Returns:
            The identifier of the currently active signing key.

        Raises:
            HSMError: If no key has been generated yet.
        """
        ...

    @abstractmethod
    async def verify_with_key(
        self,
        content: bytes,
        signature: bytes,
        key_id: str,
    ) -> bool:
        """Verify a signature against content using a specific key.

        Used when verifying signatures created by other parties (witnesses,
        other agents) where we need to specify which key to use.

        Args:
            content: The original content (with mode prefix).
            signature: The signature to verify.
            key_id: The identifier of the key to use for verification.

        Returns:
            True if signature is valid, False otherwise.

        Raises:
            HSMError: For HSM-related failures during verification.
            KeyNotFoundError: If the specified key_id is not found.
        """
        ...

    @abstractmethod
    async def get_public_key_bytes(self, key_id: str | None = None) -> bytes:
        """Get the public key bytes for a key.

        Used for exporting public key material for registration,
        verification by external parties, or key ceremonies.

        Args:
            key_id: The key ID to get public key for. Defaults to current key.

        Returns:
            Raw public key bytes (32 bytes for Ed25519).

        Raises:
            HSMKeyNotFoundError: If the specified key_id is not found.
        """
        ...
