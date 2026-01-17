"""Government adapters for branch services.

This package contains adapters for the government branch services:
- King Service (Legislative Branch)
- President Service (Executive Branch)
- Prince Service (Judicial Branch)
- Duke/Earl Services (Administrative Branch)
- Marquis Service (Advisory Branch)
- Governance State Machine (Flow Enforcement)
"""

from src.infrastructure.adapters.government.king_service_adapter import (
    KingServiceAdapter,
    create_king_service,
)
from src.infrastructure.adapters.government.president_service_adapter import (
    PresidentServiceAdapter,
    create_president_service,
)
from src.infrastructure.adapters.government.prince_service_adapter import (
    PrinceServiceAdapter,
    create_prince_service,
)
from src.infrastructure.adapters.government.duke_service_adapter import (
    DukeServiceAdapter,
)
from src.infrastructure.adapters.government.earl_service_adapter import (
    EarlServiceAdapter,
)
from src.infrastructure.adapters.government.marquis_service_adapter import (
    MarquisServiceAdapter,
)
from src.infrastructure.adapters.government.governance_state_machine_adapter import (
    GovernanceStateMachineAdapter,
)

__all__ = [
    # Legislative Branch
    "KingServiceAdapter",
    "create_king_service",
    # Executive Branch
    "PresidentServiceAdapter",
    "create_president_service",
    # Judicial Branch
    "PrinceServiceAdapter",
    "create_prince_service",
    # Administrative Branch
    "DukeServiceAdapter",
    "EarlServiceAdapter",
    # Advisory Branch
    "MarquisServiceAdapter",
    # Governance Flow
    "GovernanceStateMachineAdapter",
]
