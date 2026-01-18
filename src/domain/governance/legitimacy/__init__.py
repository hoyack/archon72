"""Legitimacy band domain module for consent-based governance system.

This module implements the legitimacy visibility subsystem as specified in
governance-prd.md (FR28-FR32) and governance-architecture.md.

Legitimacy Bands
================
The system tracks legitimacy through five bands representing system health:

| Band        | Severity | Description                                    |
|-------------|----------|------------------------------------------------|
| STABLE      | 0        | Normal operation, no active issues             |
| STRAINED    | 1        | Minor issues detected, monitoring required     |
| ERODING     | 2        | Significant issues, intervention recommended   |
| COMPROMISED | 3        | Critical issues, limited operation             |
| FAILED      | 4        | System integrity compromised, halt recommended |

Transition Rules
================
- **Downward (automatic)**: Any band can transition to any lower band
  automatically when violations occur. Bands can be skipped based on
  severity of violation.

- **Upward (requires acknowledgment)**: Restoration must be explicit and
  acknowledged by a human operator. Only one step at a time is allowed
  (e.g., ERODING → STRAINED, not ERODING → STABLE).

- **FAILED is terminal**: Once the system reaches FAILED, it cannot recover
  through normal transitions. Reconstitution is required.

Why Asymmetric?
===============
- Decay is automatic because violations are objective events and delayed
  decay would hide problems. The system should transparently show health.

- Restoration requires acknowledgment because a human must verify the issue
  is resolved. This prevents premature restoration and creates accountability
  for decisions (NFR-CONST-04).

Constitutional Compliance
========================
- FR28: System can track current legitimacy band
- NFR-CONST-04: All transitions logged with timestamp and actor
- NFR-AUDIT-04: State transitions are auditable
"""

from src.domain.governance.legitimacy.band_transition_rules import (
    BandTransitionRules,
)
from src.domain.governance.legitimacy.errors import (
    AcknowledgmentRequiredError,
    InvalidTransitionError,
    TerminalBandError,
)
from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)
from src.domain.governance.legitimacy.restoration_acknowledgment import (
    RestorationAcknowledgment,
    RestorationRequest,
    RestorationResult,
)
from src.domain.governance.legitimacy.transition_type import TransitionType
from src.domain.governance.legitimacy.transition_validation import (
    TransitionValidation,
)
from src.domain.governance.legitimacy.violation_severity import (
    VIOLATION_SEVERITY_MAP,
    ViolationSeverity,
    calculate_target_band,
    get_severity_for_violation,
)

__all__ = [
    # Core enum
    "LegitimacyBand",
    # State models
    "LegitimacyState",
    "LegitimacyTransition",
    "TransitionType",
    # Validation
    "TransitionValidation",
    "BandTransitionRules",
    # Errors
    "InvalidTransitionError",
    "TerminalBandError",
    "AcknowledgmentRequiredError",
    # Violation severity (for auto-decay)
    "ViolationSeverity",
    "VIOLATION_SEVERITY_MAP",
    "get_severity_for_violation",
    "calculate_target_band",
    # Restoration acknowledgment (for explicit restoration)
    "RestorationAcknowledgment",
    "RestorationRequest",
    "RestorationResult",
]
