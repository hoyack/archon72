"""SignableContent domain model for cryptographic signing.

RT-1 Pattern: The mode watermark MUST be INSIDE the signature, not metadata.
This ensures that:
1. The watermark cannot be stripped without invalidating the signature
2. Dev signatures can never be confused with production signatures
3. Mode is cryptographically bound to the content
"""

import os
from dataclasses import dataclass


def is_dev_mode() -> bool:
    """Check if running in development mode.

    Returns:
        True if DEV_MODE environment variable is set to 'true'.
    """
    return os.getenv("DEV_MODE", "false").lower() == "true"


@dataclass(frozen=True)
class SignableContent:
    """Content prepared for cryptographic signing with mode watermark.

    The mode watermark ([DEV MODE] or [PROD]) is included INSIDE the
    bytes that get signed, ensuring the mode cannot be stripped without
    invalidating the signature.

    Attributes:
        raw_content: The original content before mode prefix is added.

    Example:
        >>> content = SignableContent(raw_content=b"vote:yes")
        >>> # In dev mode (DEV_MODE=true):
        >>> content.to_bytes()  # Returns: b"[DEV MODE]vote:yes"
        >>> # In prod mode (DEV_MODE=false):
        >>> content.to_bytes()  # Returns: b"[PROD]vote:yes"
    """

    raw_content: bytes

    # Mode prefixes - these are part of what gets signed
    DEV_MODE_PREFIX: bytes = b"[DEV MODE]"
    PROD_MODE_PREFIX: bytes = b"[PROD]"

    def to_bytes(self) -> bytes:
        """Convert to bytes with mode prefix for signing.

        The mode prefix is determined by the DEV_MODE environment variable
        at the time this method is called. The prefix becomes part of the
        signed content, making it impossible to strip without invalidating
        the signature.

        Returns:
            Bytes with mode prefix: b"[DEV MODE]..." or b"[PROD]..."
        """
        mode_prefix = self.DEV_MODE_PREFIX if is_dev_mode() else self.PROD_MODE_PREFIX
        return mode_prefix + self.raw_content

    def to_bytes_with_mode(self, dev_mode: bool) -> bytes:
        """Convert to bytes with explicit mode prefix.

        This method allows specifying the mode explicitly, useful for
        verification where we need to reconstruct the original signed bytes.

        Args:
            dev_mode: True to use DEV_MODE_PREFIX, False for PROD_MODE_PREFIX.

        Returns:
            Bytes with specified mode prefix.
        """
        mode_prefix = self.DEV_MODE_PREFIX if dev_mode else self.PROD_MODE_PREFIX
        return mode_prefix + self.raw_content

    @classmethod
    def from_signed_bytes(cls, signed_bytes: bytes) -> tuple["SignableContent", bool]:
        """Reconstruct SignableContent from signed bytes.

        Parses the mode prefix from signed bytes and returns the original
        content along with the detected mode.

        Args:
            signed_bytes: Bytes that include mode prefix.

        Returns:
            Tuple of (SignableContent, is_dev_mode).

        Raises:
            ValueError: If no valid mode prefix is found.
        """
        if signed_bytes.startswith(cls.DEV_MODE_PREFIX):
            raw_content = signed_bytes[len(cls.DEV_MODE_PREFIX) :]
            return cls(raw_content=raw_content), True
        elif signed_bytes.startswith(cls.PROD_MODE_PREFIX):
            raw_content = signed_bytes[len(cls.PROD_MODE_PREFIX) :]
            return cls(raw_content=raw_content), False
        else:
            raise ValueError(
                "Invalid signed bytes: missing mode prefix. "
                f"Expected '{cls.DEV_MODE_PREFIX.decode()}' or "
                f"'{cls.PROD_MODE_PREFIX.decode()}' prefix."
            )

    def __len__(self) -> int:
        """Return length of raw content (without mode prefix)."""
        return len(self.raw_content)
