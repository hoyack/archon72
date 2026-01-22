"""
Ports (interfaces) for Archon 72.

Ports define abstract interfaces that infrastructure adapters implement.
This allows the domain to remain pure and testable without depending
on concrete implementations.

Future port types will include:
- EventStore (Protocol)
- HSMPort (Protocol)
- WitnessPort (Protocol)
- etc.
"""

from src.domain.ports.time_authority import TimeAuthorityProtocol

__all__: list[str] = ["TimeAuthorityProtocol"]
