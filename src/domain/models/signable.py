"""SignableContent domain model for cryptographic signing.

RT-1 Pattern: The mode watermark MUST be INSIDE the signature, not metadata.
This ensures that:
1. The watermark cannot be stripped without invalidating the signature
2. Dev signatures can never be confused with production signatures
3. Mode is cryptographically bound to the content

H1 Security Enhancement:
- Secondary validation prevents accidental DEV_MODE in production
- ENVIRONMENT variable must match DEV_MODE setting
- Startup verification detects environment inconsistency
"""

import os
from dataclasses import dataclass

import structlog

log = structlog.get_logger()


class DevModeEnvironmentMismatchError(Exception):
    """Raised when DEV_MODE and ENVIRONMENT variables are inconsistent (H1 fix).

    This prevents accidental use of DevHSM (plaintext keys) in production.
    """

    pass


@dataclass(frozen=True)
class ParsedSignedContent:
    """Result of parsing signed bytes back into SignableContent.

    This dataclass provides clearer semantics than a bare tuple for the
    result of SignableContent.from_signed_bytes().

    Attributes:
        content: The parsed SignableContent with raw_content extracted.
        is_dev_mode: True if the signed bytes had [DEV MODE] prefix, False for [PROD].
    """

    content: "SignableContent"
    is_dev_mode: bool


# Valid environment names for production detection
PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod", "staging", "stage"})


def _detect_environment() -> str:
    """Detect the current environment from ENVIRONMENT variable.

    Returns:
        Environment name (lowercase), defaults to 'development'.
    """
    return os.getenv("ENVIRONMENT", "development").lower()


def _is_production_environment() -> bool:
    """Check if running in a production-like environment.

    Returns:
        True if ENVIRONMENT indicates production/staging.
    """
    return _detect_environment() in PRODUCTION_ENVIRONMENTS


def is_dev_mode() -> bool:
    """Check if running in development mode.

    Returns:
        True if DEV_MODE environment variable is set to 'true'.
    """
    return os.getenv("DEV_MODE", "false").lower() == "true"


def validate_dev_mode_consistency() -> None:
    """Validate DEV_MODE is consistent with ENVIRONMENT (H1 fix).

    This secondary validation prevents a critical security misconfiguration
    where DEV_MODE=true in a production environment. An attacker who can
    modify environment variables could force development mode in production.

    H1 Security Finding:
    - Single environment variable determines HSM selection
    - This validation adds a secondary check

    Raises:
        DevModeEnvironmentMismatchError: If DEV_MODE=true in production environment.
    """
    dev_mode = is_dev_mode()
    environment = _detect_environment()
    is_prod = _is_production_environment()

    if dev_mode and is_prod:
        log.critical(
            "dev_mode_environment_mismatch",
            dev_mode=dev_mode,
            environment=environment,
            message="H1: DEV_MODE=true in production environment - SECURITY VIOLATION",
        )
        raise DevModeEnvironmentMismatchError(
            f"H1 Security Violation: DEV_MODE=true is not allowed in "
            f"'{environment}' environment. Set DEV_MODE=false or change "
            f"ENVIRONMENT to 'development'."
        )

    if not dev_mode and not is_prod and environment == "development":
        # Informational: Production HSM in development is allowed but unusual
        log.info(
            "dev_mode_production_hsm_in_dev",
            dev_mode=dev_mode,
            environment=environment,
            message="Using production HSM configuration in development environment",
        )

    log.debug(
        "dev_mode_consistency_validated",
        dev_mode=dev_mode,
        environment=environment,
        is_production=is_prod,
    )


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
            Tuple of (SignableContent, is_dev_mode). For clearer semantics,
            use parse_signed_bytes() which returns ParsedSignedContent.

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

    @classmethod
    def parse_signed_bytes(cls, signed_bytes: bytes) -> ParsedSignedContent:
        """Reconstruct SignableContent from signed bytes with named result.

        This is the preferred method over from_signed_bytes() as it returns
        a named dataclass instead of a bare tuple.

        Args:
            signed_bytes: Bytes that include mode prefix.

        Returns:
            ParsedSignedContent with content and is_dev_mode fields.

        Raises:
            ValueError: If no valid mode prefix is found.
        """
        content, is_dev = cls.from_signed_bytes(signed_bytes)
        return ParsedSignedContent(content=content, is_dev_mode=is_dev)

    def __len__(self) -> int:
        """Return length of raw content (without mode prefix)."""
        return len(self.raw_content)
