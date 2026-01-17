"""Governance domain module for consent-based governance system.

This module contains domain models, events, and value objects for the
consent-based governance system as specified in governance-prd.md and
governance-architecture.md.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
- CT-12: Witnessing creates accountability → Unwitnessed actions are invalid
- CT-13: Integrity outranks availability → Availability may be sacrificed
"""

from src.domain.governance.events import (
    EventMetadata,
    GovernanceEvent,
)

__all__ = [
    "EventMetadata",
    "GovernanceEvent",
]
