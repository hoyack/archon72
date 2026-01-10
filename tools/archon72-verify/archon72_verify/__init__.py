"""Archon 72 Verification Toolkit.

Open-source tools for verifying Archon 72 event chain integrity.

FR47: Verification toolkit downloadable from public repository
FR49: Chain verification, signature verification, gap detection
FR122: Local database gap detection for observers
FR123: Gap range reporting (start, end sequences)

Example usage:

    import asyncio
    from archon72_verify import ObserverClient, ChainVerifier

    async def main():
        client = ObserverClient()
        events = await client.get_events(1, 1000)
        await client.close()

        verifier = ChainVerifier()
        result = verifier.verify_chain(events)
        print(f"Valid: {result.is_valid}")

    asyncio.run(main())
"""

__version__ = "0.1.0"

from archon72_verify.client import ObserverClient
from archon72_verify.database import ObserverDatabase
from archon72_verify.verifier import (
    GENESIS_HASH,
    ChainVerifier,
    ProofVerificationResult,
    VerificationResult,
)

__all__ = [
    "ObserverClient",
    "ObserverDatabase",
    "ChainVerifier",
    "VerificationResult",
    "ProofVerificationResult",
    "GENESIS_HASH",
    "__version__",
]
