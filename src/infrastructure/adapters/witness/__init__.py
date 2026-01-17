"""Knight-Witness service adapters.

This module provides concrete implementations of the KnightWitnessProtocol
for the Furcas (Knight-Witness) role in the governance system.
"""

from src.infrastructure.adapters.witness.knight_witness_adapter import (
    KnightWitnessAdapter,
    create_knight_witness,
)

__all__ = [
    "KnightWitnessAdapter",
    "create_knight_witness",
]
