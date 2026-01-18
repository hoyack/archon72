"""Cessation domain models for system lifecycle management.

Story: consent-gov-8.1: System Cessation Trigger
Story: consent-gov-8.2: Cessation Record Creation
Story: consent-gov-8.3: Reconstitution Validation

This module provides domain models for system cessation - the permanent,
irreversible shutdown of the governance system.

Cessation is NOT:
- A crash (unexpected failure)
- A restart (temporary pause)
- Maintenance mode (partial operation)
- Halt (temporary safety stop)

Cessation IS:
- Permanent (forward-only state machine)
- Documented (Cessation Record created)
- Honorable (all records preserved)
- Final (no recovery to same instance)

Why Irreversible?
- Legitimacy cannot be inherited
- Continuity claims are false
- Clean break is honest
- New instance requires new identity

Constitutional Context:
- FR47: Human Operator can trigger cessation
- FR48: System can create immutable Cessation Record on cessation
- FR49: System can block new Motion Seeds on cessation
- FR50: System can halt execution on cessation
- FR51: System can preserve all records on cessation
- FR52: System can label in-progress work as `interrupted_by_cessation`
- FR53: System can validate Reconstitution Artifact before new instance
- FR54: System can reject reconstitution that claims continuity
- FR55: System can reject reconstitution that inherits legitimacy band
"""

from src.domain.governance.cessation.cessation_record import (
    CessationRecord,
    InterruptedWork,
    SystemSnapshot,
)
from src.domain.governance.cessation.cessation_state import CessationState
from src.domain.governance.cessation.cessation_status import CessationStatus
from src.domain.governance.cessation.cessation_trigger import CessationTrigger
from src.domain.governance.cessation.errors import (
    CessationAlreadyTriggeredError,
    CessationError,
    CessationRecordAlreadyExistsError,
    CessationRecordCreationError,
    MotionBlockedByCessationError,
)
from src.domain.governance.cessation.reconstitution_artifact import (
    ReconstitutionArtifact,
    RejectionReason,
    ValidationResult,
    ValidationStatus,
)

__all__ = [
    # Domain models
    "CessationRecord",
    "CessationState",
    "CessationStatus",
    "CessationTrigger",
    "InterruptedWork",
    "ReconstitutionArtifact",
    "RejectionReason",
    "SystemSnapshot",
    "ValidationResult",
    "ValidationStatus",
    # Errors
    "CessationAlreadyTriggeredError",
    "CessationError",
    "CessationRecordAlreadyExistsError",
    "CessationRecordCreationError",
    "MotionBlockedByCessationError",
]
