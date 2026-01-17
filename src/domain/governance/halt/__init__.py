"""Halt domain module for emergency safety circuit.

This module contains domain models for the three-channel halt circuit
as specified in consent-gov-4.1 (Emergency Safety Circuit).

Constitutional Context:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-13: Integrity outranks availability → Halt preserves integrity
- NFR-PERF-01: Halt completes in ≤100ms
- NFR-REL-01: Primary halt works without external dependencies

Three-Channel Design:
1. Primary (In-Memory): Process-local atomic flag - ALWAYS works
2. Secondary (Redis): Propagates to other instances - best-effort
3. Tertiary (Ledger): Permanent audit record - best-effort

Priority: Correctness > Observability > Durability
"""

from src.domain.governance.halt.halt_status import (
    HaltedException,
    HaltReason,
    HaltStatus,
)

__all__ = [
    "HaltReason",
    "HaltStatus",
    "HaltedException",
]
