"""Application ports - Abstract interfaces for infrastructure adapters.

This module defines the contracts that infrastructure adapters must implement.
Ports enable dependency inversion and make the application layer testable.

Available ports:
- HSMProtocol: Hardware Security Module operations (signing, verification)
"""

from src.application.ports.hsm import HSMMode, HSMProtocol, SignatureResult

__all__: list[str] = ["HSMProtocol", "HSMMode", "SignatureResult"]
