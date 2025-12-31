"""HSM factory for selecting appropriate HSM implementation.

The factory checks DEV_MODE environment variable to determine
which HSM implementation to use:
- DEV_MODE=true: DevHSM (software stub with watermark)
- DEV_MODE=false: CloudHSM (production - will fail without config)

AC1, AC3: Factory returns correct HSM based on environment.
ADR-4: Development uses software stub, production uses Cloud HSM.
"""

import os

import structlog

from src.application.ports.hsm import HSMProtocol
from src.infrastructure.adapters.security.hsm_cloud import CloudHSM
from src.infrastructure.adapters.security.hsm_dev import DevHSM

log = structlog.get_logger()


def is_dev_mode() -> bool:
    """Check if running in development mode.

    Returns:
        True if DEV_MODE environment variable is 'true' (case-insensitive).
    """
    return os.getenv("DEV_MODE", "false").lower() == "true"


def get_hsm(dev_hsm_instance: DevHSM | None = None) -> HSMProtocol:
    """Get the appropriate HSM implementation based on environment.

    Args:
        dev_hsm_instance: Optional pre-configured DevHSM instance.
            Useful for testing with specific key storage paths.

    Returns:
        DevHSM if DEV_MODE=true, CloudHSM otherwise.

    Example:
        >>> hsm = get_hsm()
        >>> result = await hsm.sign(b"data")
    """
    if is_dev_mode():
        log.info("hsm_factory_dev_mode", mode="development")
        return dev_hsm_instance or DevHSM()
    else:
        log.info("hsm_factory_prod_mode", mode="production")
        return CloudHSM()


def get_dev_hsm() -> DevHSM:
    """Get DevHSM instance directly.

    Useful when you need the concrete DevHSM type for dev-specific operations.

    Returns:
        DevHSM instance.
    """
    return DevHSM()


def get_cloud_hsm() -> CloudHSM:
    """Get CloudHSM instance directly.

    Useful when you need the concrete CloudHSM type for prod-specific operations.

    Returns:
        CloudHSM instance.
    """
    return CloudHSM()
