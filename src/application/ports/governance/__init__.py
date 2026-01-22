"""Governance ports - Abstract interfaces for consent-based governance system.

This module defines the contracts for the consent-based governance system
as specified in governance-architecture.md (Phase 3 Government PRD).

Available ports:
- GovernanceLedgerPort: Append-only ledger for governance events (Story 1-2)
- ProjectionPort: Derived state projections from ledger (Story 1-5)
- HaltPort: Three-channel halt circuit for emergency safety (Story 4-1)
- TaskActivationPort: Task activation and routing (Story 2-2)
- CoercionFilterPort: Content filtering (Story 2-2, 3-2)
- ParticipantMessagePort: Participant messaging (Story 2-2)

Constitutional Constraints:
- NFR-CONST-01: Append-only enforcement - NO delete methods on ledger
- AD-1: Event sourcing as canonical model
- AD-8: Same DB, schema isolation (ledger.*, projections.*)
- AD-9: CQRS-Lite query pattern
- AD-11: Global monotonic sequence
- NFR-PERF-01: Halt completes in ≤100ms
- NFR-REL-01: Primary halt works without external dependencies
- FR21: All content through Coercion Filter
- NFR-INT-01: Async protocol for Earl→Cluster
"""

from src.application.ports.governance.cessation_port import (
    CessationPort,
    ExecutionHalterPort,
    MotionBlockerPort,
)
from src.application.ports.governance.cessation_record_port import (
    CessationRecordPort,
)
from src.application.ports.governance.coercion_filter_port import (
    CoercionFilterPort,
    FilterResult,
)
from src.application.ports.governance.contact_block_port import (
    ContactBlockPort,
)
from src.application.ports.governance.contribution_port import (
    ContributionPort,
)
from src.application.ports.governance.exit_port import (
    ExitPort,
)
from src.application.ports.governance.filter_decision_log_port import (
    FilterDecisionLogPort,
)
from src.application.ports.governance.halt_port import (
    HaltChecker,
    HaltPort,
)
from src.application.ports.governance.halt_task_transition_port import (
    ConcurrentModificationError,
    HaltTaskTransitionPort,
    HaltTransitionResult,
    HaltTransitionType,
    TaskStateCategory,
    TaskTransitionRecord,
)
from src.application.ports.governance.halt_trigger_port import (
    HaltExecutionResult,
    HaltMessageRequiredError,
    HaltTriggerPort,
    UnauthorizedHaltError,
)
from src.application.ports.governance.ledger_export_port import (
    LedgerExportPort,
    PIICheckerPort,
)
from src.application.ports.governance.ledger_port import (
    GovernanceLedgerPort,
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.application.ports.governance.legitimacy_decay_port import (
    DecayResult,
    LegitimacyDecayPort,
)
from src.application.ports.governance.legitimacy_port import (
    LegitimacyPort,
    LegitimacyQueryPort,
)
from src.application.ports.governance.legitimacy_restoration_port import (
    LegitimacyRestorationPort,
    RestorationAcknowledgment,
    RestorationRequest,
    RestorationResult,
)
from src.application.ports.governance.panel_finding_port import (
    PanelFindingPort,
)
from src.application.ports.governance.panel_port import (
    PanelPort,
)
from src.application.ports.governance.panel_queue_port import (
    PanelQueuePort,
)
from src.application.ports.governance.participant_message_port import (
    MessageDeliveryError,
    ParticipantMessagePort,
)
from src.application.ports.governance.pattern_library_port import (
    PatternLibraryPort,
)
from src.application.ports.governance.projection_port import (
    ActorRegistryProjectionPort,
    LegitimacyStateProjectionPort,
    ProjectionApplyRecord,
    ProjectionCheckpoint,
    ProjectionPort,
    TaskStateProjectionPort,
)
from src.application.ports.governance.proof_port import (
    HashChainPort,
    ProofPort,
)
from src.application.ports.governance.reconstitution_port import (
    ReconstitutionPort,
)
from src.application.ports.governance.task_activation_port import (
    TaskActivationPort,
    TaskNotFoundError,
    TaskStatePort,
    UnauthorizedAccessError,
)
from src.application.ports.governance.task_consent_port import (
    InvalidTaskStateError,
    PendingTaskView,
    TaskConsentPort,
    TaskConsentResult,
    UnauthorizedConsentError,
)
from src.application.ports.governance.task_constraint_port import (
    ConstraintViolation,
    ConstraintViolationError,
    TaskConstraintPort,
)
from src.application.ports.governance.task_reminder_port import (
    ReminderProcessingResult,
    ReminderRecord,
    ReminderSendResult,
    ReminderTrackingPort,
    TaskReminderPort,
)
from src.domain.governance.task.reminder_milestone import ReminderMilestone
from src.domain.governance.task.task_constraint import (
    ROLE_ALLOWED_OPERATIONS,
    ROLE_PROHIBITED_OPERATIONS,
    TaskOperation,
)
from src.application.ports.governance.task_result_port import (
    InvalidResultStateError,
    ProblemCategory,
    ProblemReportValue,
    ResultSubmissionResult,
    TaskResultPort,
    TaskResultValue,
    UnauthorizedResultError,
)
from src.application.ports.governance.task_timeout_port import (
    TaskTimeoutConfig,
    TaskTimeoutPort,
    TimeoutProcessingResult,
    TimeoutSchedulerPort,
)
from src.application.ports.governance.transition_log_port import (
    TransitionLogPort,
)
from src.application.ports.governance.verification_port import (
    StateReplayerPort,
    VerificationPort,
)
from src.application.ports.governance.witness_port import (
    WitnessPort,
)

__all__ = [
    # Halt ports (Story 4-1, 4-2)
    "HaltPort",
    "HaltChecker",
    "HaltTriggerPort",
    "HaltExecutionResult",
    "UnauthorizedHaltError",
    "HaltMessageRequiredError",
    # Ledger ports (Story 1-2)
    "GovernanceLedgerPort",
    "LedgerReadOptions",
    "PersistedGovernanceEvent",
    # Projection ports (Story 1-5)
    "ProjectionPort",
    "ProjectionCheckpoint",
    "ProjectionApplyRecord",
    "TaskStateProjectionPort",
    "LegitimacyStateProjectionPort",
    "ActorRegistryProjectionPort",
    # Task activation ports (Story 2-2)
    "TaskActivationPort",
    "TaskStatePort",
    "UnauthorizedAccessError",
    "TaskNotFoundError",
    # Task consent ports (Story 2-3)
    "TaskConsentPort",
    "PendingTaskView",
    "TaskConsentResult",
    "UnauthorizedConsentError",
    "InvalidTaskStateError",
    # Task result ports (Story 2-4)
    "TaskResultPort",
    "TaskResultValue",
    "ProblemReportValue",
    "ProblemCategory",
    "ResultSubmissionResult",
    "UnauthorizedResultError",
    "InvalidResultStateError",
    # Coercion filter ports (Story 2-2, 3-2)
    "CoercionFilterPort",
    "FilterResult",
    # Participant message ports (Story 2-2)
    "ParticipantMessagePort",
    "MessageDeliveryError",
    # Task timeout ports (Story 2-5)
    "TaskTimeoutPort",
    "TaskTimeoutConfig",
    "TimeoutProcessingResult",
    "TimeoutSchedulerPort",
    # Task reminder ports (Story 2-6)
    "TaskReminderPort",
    "ReminderTrackingPort",
    "ReminderMilestone",
    "ReminderRecord",
    "ReminderSendResult",
    "ReminderProcessingResult",
    # Task constraint ports (Story 2-7)
    "TaskConstraintPort",
    "TaskOperation",
    "ConstraintViolation",
    "ConstraintViolationError",
    "ROLE_ALLOWED_OPERATIONS",
    "ROLE_PROHIBITED_OPERATIONS",
    # Halt task transition ports (Story 4-3)
    "HaltTaskTransitionPort",
    "HaltTransitionResult",
    "HaltTransitionType",
    "TaskStateCategory",
    "TaskTransitionRecord",
    "ConcurrentModificationError",
    # Filter decision logging ports (Story 3-3)
    "FilterDecisionLogPort",
    # Pattern library ports (Story 3-4)
    "PatternLibraryPort",
    # Witness ports (Story 6-1)
    "WitnessPort",
    # Panel queue ports (Story 6-3)
    "PanelQueuePort",
    # Panel ports (Story 6-4)
    "PanelPort",
    # Panel finding ports (Story 6-5)
    "PanelFindingPort",
    # Legitimacy ports (Story 5-1)
    "LegitimacyPort",
    "LegitimacyQueryPort",
    # Legitimacy decay ports (Story 5-2)
    "LegitimacyDecayPort",
    "DecayResult",
    # Legitimacy restoration ports (Story 5-3)
    "LegitimacyRestorationPort",
    "RestorationAcknowledgment",
    "RestorationRequest",
    "RestorationResult",
    # Exit ports (Story 7-1)
    "ExitPort",
    # Contribution ports (Story 7-3)
    "ContributionPort",
    # Contact block ports (Story 7-4)
    "ContactBlockPort",
    # Cessation ports (Story 8-1)
    "CessationPort",
    "ExecutionHalterPort",
    "MotionBlockerPort",
    # Cessation record ports (Story 8-2)
    "CessationRecordPort",
    # Reconstitution ports (Story 8-3)
    "ReconstitutionPort",
    # Ledger export ports (Story 9-1)
    "LedgerExportPort",
    "PIICheckerPort",
    # Proof ports (Story 9-2)
    "ProofPort",
    "HashChainPort",
    # Verification ports (Story 9-3)
    "VerificationPort",
    "StateReplayerPort",
    # Transition log ports (Story 9-4)
    "TransitionLogPort",
]
