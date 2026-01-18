"""Governance application services.

This package contains application services for the consent-based
governance system, including:
- Write-time validation (Story 1-4)
- Projection rebuild (Story 1-5)
- Task timeout processing (Story 2-5)
- Task reminder processing (Story 2-6)
- Knight Observer (Story 6-2)
"""

from src.application.services.governance.cessation_record_service import (
    CessationRecordService,
)
from src.application.services.governance.cessation_trigger_service import (
    DEFAULT_GRACE_PERIOD_SECONDS,
    CessationTriggerService,
)
from src.application.services.governance.contact_prevention_service import (
    ContactPreventionService,
)
from src.application.services.governance.contribution_preservation_service import (
    CONTRIBUTIONS_PRESERVED_EVENT,
    ContributionPreservationService,
)
from src.application.services.governance.exit_service import (
    EXIT_COMPLETED_EVENT,
    EXIT_INITIATED_EVENT,
    ExitService,
)
from src.application.services.governance.filter_logging_service import (
    FILTER_DECISION_LOGGED_EVENT,
    FilterLoggingService,
)
from src.application.services.governance.halt_task_transition_service import (
    HaltTaskTransitionService,
    TaskStateQueryPort,
)
from src.application.services.governance.knight_observer_service import (
    GapDetection,
    KnightObserverService,
    ObservationMetrics,
)
from src.application.services.governance.ledger_export_service import (
    LEDGER_EXPORTED_EVENT,
    LedgerExportService,
)
from src.application.services.governance.ledger_proof_service import (
    PROOF_GENERATED_EVENT,
    PROOF_VERIFIED_EVENT,
    LedgerProofService,
)
from src.application.services.governance.ledger_validation_service import (
    LedgerValidationService,
)
from src.application.services.governance.legitimacy_decay_service import (
    BAND_DECREASED_EVENT,
    LegitimacyDecayService,
)
from src.application.services.governance.obligation_release_service import (
    OBLIGATIONS_RELEASED_EVENT,
    PENDING_REQUESTS_CANCELLED_EVENT,
    RELEASE_CATEGORIES,
    TASK_NULLIFIED_ON_EXIT_EVENT,
    TASK_RELEASED_ON_EXIT_EVENT,
    ObligationReleaseService,
)
from src.application.services.governance.panel_finding_service import (
    DISSENT_RECORDED_EVENT,
    FINDING_ISSUED_EVENT,
    PanelFindingService,
    compute_finding_hash,
)
from src.application.services.governance.projection_rebuild_service import (
    ProjectionRebuildService,
    RebuildResult,
    VerificationResult,
)
from src.application.services.governance.reconstitution_validation_service import (
    BASELINE_LEGITIMACY_BAND,
    REJECTION_MESSAGES,
    ReconstitutionValidationService,
)
from src.application.services.governance.task_constraint_service import (
    TaskConstraintService,
)
from src.application.services.governance.task_reminder_service import (
    TaskReminderScheduler,
    TaskReminderService,
)
from src.application.services.governance.task_timeout_service import (
    TaskTimeoutScheduler,
    TaskTimeoutService,
)
from src.application.services.governance.transition_logging_service import (
    TRANSITION_LOGGED_EVENT,
    TransitionLoggingService,
)
from src.application.services.governance.violation_event_subscriber import (
    VIOLATION_EVENT_PATTERN,
    ViolationEventSubscriber,
)
from src.application.services.governance.witness_routing_service import (
    HIGH_PRIORITY_KEYWORDS,
    ROUTING_RULES,
    WitnessRoutingService,
    determine_priority,
)

# Event type constants for Contact Prevention (Story 7-4)
CONTACT_BLOCKED_EVENT = "custodial.contact.blocked"
CONTACT_ATTEMPT_VIOLATION_EVENT = "constitutional.violation.contact_attempt"

__all__ = [
    "LedgerValidationService",
    "ProjectionRebuildService",
    "RebuildResult",
    "VerificationResult",
    "TaskTimeoutService",
    "TaskTimeoutScheduler",
    "TaskReminderService",
    "TaskReminderScheduler",
    "TaskConstraintService",
    "HaltTaskTransitionService",
    "TaskStateQueryPort",
    "FilterLoggingService",
    "FILTER_DECISION_LOGGED_EVENT",
    "KnightObserverService",
    "ObservationMetrics",
    "GapDetection",
    "WitnessRoutingService",
    "determine_priority",
    "ROUTING_RULES",
    "HIGH_PRIORITY_KEYWORDS",
    "PanelFindingService",
    "compute_finding_hash",
    "FINDING_ISSUED_EVENT",
    "DISSENT_RECORDED_EVENT",
    "LegitimacyDecayService",
    "BAND_DECREASED_EVENT",
    "ViolationEventSubscriber",
    "VIOLATION_EVENT_PATTERN",
    # Exit service (Story 7-1)
    "ExitService",
    "EXIT_INITIATED_EVENT",
    "EXIT_COMPLETED_EVENT",
    # Obligation release service (Story 7-2)
    "ObligationReleaseService",
    "OBLIGATIONS_RELEASED_EVENT",
    "TASK_NULLIFIED_ON_EXIT_EVENT",
    "TASK_RELEASED_ON_EXIT_EVENT",
    "PENDING_REQUESTS_CANCELLED_EVENT",
    "RELEASE_CATEGORIES",
    # Contribution preservation service (Story 7-3)
    "ContributionPreservationService",
    "CONTRIBUTIONS_PRESERVED_EVENT",
    # Contact prevention service (Story 7-4)
    "ContactPreventionService",
    "CONTACT_BLOCKED_EVENT",
    "CONTACT_ATTEMPT_VIOLATION_EVENT",
    # Cessation trigger service (Story 8-1)
    "CessationTriggerService",
    "DEFAULT_GRACE_PERIOD_SECONDS",
    # Cessation record service (Story 8-2)
    "CessationRecordService",
    # Reconstitution validation service (Story 8-3)
    "ReconstitutionValidationService",
    "BASELINE_LEGITIMACY_BAND",
    "REJECTION_MESSAGES",
    # Ledger export service (Story 9-1)
    "LedgerExportService",
    "LEDGER_EXPORTED_EVENT",
    # Ledger proof service (Story 9-2)
    "LedgerProofService",
    "PROOF_GENERATED_EVENT",
    "PROOF_VERIFIED_EVENT",
    # Transition logging service (Story 9-4)
    "TransitionLoggingService",
    "TRANSITION_LOGGED_EVENT",
]
