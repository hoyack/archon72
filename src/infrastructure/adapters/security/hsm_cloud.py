"""Production Cloud HSM adapter placeholder.

This is a placeholder implementation that raises HSMNotConfiguredError
for all operations. It will be replaced with actual Cloud HSM integration
(AWS CloudHSM, Azure Key Vault, etc.) in a future story.

AC3: Production mode MUST fail without real HSM configured.
ADR-4: Production uses Cloud HSM (AWS CloudHSM or equivalent).
"""

from src.application.ports.hsm import HSMMode, HSMProtocol, SignatureResult
from src.domain.errors.hsm import HSMNotConfiguredError


class CloudHSM(HSMProtocol):
    """Production Cloud HSM adapter (placeholder).

    This placeholder implementation enforces the security requirement that
    production mode cannot operate without a properly configured HSM.

    All methods raise HSMNotConfiguredError with a clear message.
    """

    def __init__(self) -> None:
        """Initialize the Cloud HSM placeholder.

        In production, this would configure connection to Cloud HSM service.
        """
        pass

    async def sign(self, content: bytes) -> SignatureResult:
        """Sign content - NOT IMPLEMENTED.

        Raises:
            HSMNotConfiguredError: Always, as production HSM is not configured.
        """
        raise HSMNotConfiguredError("Production HSM not configured")

    async def verify(self, content: bytes, signature: bytes) -> bool:
        """Verify signature - NOT IMPLEMENTED.

        Raises:
            HSMNotConfiguredError: Always, as production HSM is not configured.
        """
        raise HSMNotConfiguredError("Production HSM not configured")

    async def generate_key_pair(self) -> str:
        """Generate key pair - NOT IMPLEMENTED.

        Raises:
            HSMNotConfiguredError: Always, as production HSM is not configured.
        """
        raise HSMNotConfiguredError("Production HSM not configured")

    async def get_mode(self) -> HSMMode:
        """Return production mode.

        Returns:
            HSMMode.PRODUCTION always for this implementation.
        """
        return HSMMode.PRODUCTION

    async def get_current_key_id(self) -> str:
        """Get current key ID - NOT IMPLEMENTED.

        Raises:
            HSMNotConfiguredError: Always, as production HSM is not configured.
        """
        raise HSMNotConfiguredError("Production HSM not configured")
