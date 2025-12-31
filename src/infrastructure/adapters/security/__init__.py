"""Security adapters for HSM operations.

Provides implementations of HSMProtocol:
- DevHSM: Software HSM stub for development (NOT SECURE)
- CloudHSM: Production HSM adapter (placeholder)

ADR-4: Key Custody, Signing, and Rotation
"""

from src.infrastructure.adapters.security.hsm_cloud import CloudHSM
from src.infrastructure.adapters.security.hsm_dev import DevHSM
from src.infrastructure.adapters.security.hsm_factory import get_hsm

__all__: list[str] = ["DevHSM", "CloudHSM", "get_hsm"]
