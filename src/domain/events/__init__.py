"""Domain events for Archon 72.

Constitutional event types that represent significant state changes
in the governance system. All events are immutable and timestamped.

NFR40 COMPLIANCE: Cessation Reversal Prohibited
================================================
By architectural design (NFR40), no event type exists that can
reverse, undo, revert, or cancel a cessation event.

This is intentional:
- Cessation is final by design (FR40)
- The schema itself prevents reversal (NFR40)
- Import-time validation ensures compliance
- Any attempt to add such a type will fail CI/CD

Prohibited event type patterns:
- cessation[._-]reversal, cessation[._-]undo, cessation[._-]revert
- cessation[._-]restore, cessation[._-]cancel, cessation[._-]rollback
- uncease, resurrect, revive_system, and CamelCase variants

See: _bmad-output/planning-artifacts/epics.md#Story-7.3

Available entities:
- Event: Constitutional event entity (append-only, immutable)

Hash utilities:
- GENESIS_HASH: The prev_hash for first event (64 zeros)
- HASH_ALG_VERSION: Current hash algorithm version (1 = SHA-256)
- HASH_ALG_NAME: Hash algorithm name ("SHA-256")
- canonical_json: Deterministic JSON serialization for hashing
- compute_content_hash: SHA-256 hash of event content
- get_prev_hash: Get prev_hash based on sequence

Signing utilities:
- SIG_ALG_VERSION: Current signature algorithm version (1 = Ed25519)
- SIG_ALG_NAME: Signature algorithm name ("Ed25519")
- compute_signable_content: Compute bytes to sign (content_hash + prev_hash + agent_id)
- signature_to_base64: Convert signature bytes to base64 string
- signature_from_base64: Convert base64 string to signature bytes

Future event types will include:
- VoteCast
- MeetingConvened
- HaltTriggered
- BreachDeclared
- etc.
"""

from src.domain.events.agent_unresponsive import (
    AGENT_UNRESPONSIVE_EVENT_TYPE,
    AgentUnresponsivePayload,
)
from src.domain.events.amendment import (
    AMENDMENT_PROPOSED_EVENT_TYPE,
    AMENDMENT_REJECTED_EVENT_TYPE,
    AMENDMENT_VOTE_BLOCKED_EVENT_TYPE,
    VISIBILITY_PERIOD_DAYS,
    AmendmentImpactAnalysis,
    AmendmentProposedEventPayload,
    AmendmentRejectedEventPayload,
    AmendmentStatus,
    AmendmentType,
    AmendmentVoteBlockedEventPayload,
)
from src.domain.events.anti_success_alert import (
    ANTI_SUCCESS_ALERT_EVENT_TYPE,
    AntiSuccessAlertPayload,
)
from src.domain.events.anti_success_alert import (
    AlertType as AntiSuccessAlertType,
)
from src.domain.events.archon_substitution import (
    ARCHON_SUBSTITUTED_EVENT_TYPE,
    ARCHON_SUBSTITUTION_SCHEMA_VERSION,
    DELIBERATION_ABORTED_EVENT_TYPE,
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
)
from src.domain.events.audit import (
    AUDIT_COMPLETED_EVENT_TYPE,
    AUDIT_STARTED_EVENT_TYPE,
    AUDIT_SYSTEM_AGENT_ID,
    MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE,
    AuditCompletedEventPayload,
    AuditResultStatus,
    AuditStartedEventPayload,
    ViolationFlaggedEventPayload,
)
from src.domain.events.breach import (
    BREACH_DECLARED_EVENT_TYPE,
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)
from src.domain.events.certified_result import (
    CERTIFIED_RESULT_EVENT_TYPE,
    CertifiedResultPayload,
)
from src.domain.events.cessation import (
    CESSATION_CONSIDERATION_EVENT_TYPE,
    CESSATION_DECISION_EVENT_TYPE,
    CessationConsiderationEventPayload,
    CessationDecision,
    CessationDecisionEventPayload,
)
from src.domain.events.cessation_agenda import (
    CESSATION_AGENDA_PLACEMENT_EVENT_TYPE,
    AgendaTriggerType,
    CessationAgendaPlacementEventPayload,
)
from src.domain.events.cessation_executed import (
    CESSATION_EXECUTED_EVENT_TYPE,
    CessationExecutedEventPayload,
)
from src.domain.events.co_sign import (
    CO_SIGN_EVENT_SCHEMA_VERSION,
    CO_SIGN_RECORDED_EVENT_TYPE,
    CO_SIGN_SYSTEM_AGENT_ID,
    CoSignRecordedEvent,
)
from src.domain.events.collective_output import (
    COLLECTIVE_OUTPUT_EVENT_TYPE,
    AuthorType,
    CollectiveOutputPayload,
    VoteCounts,
)
from src.domain.events.collusion import (
    COLLUSION_INVESTIGATION_TRIGGERED_EVENT_TYPE,
    INVESTIGATION_RESOLVED_EVENT_TYPE,
    WITNESS_PAIR_SUSPENDED_EVENT_TYPE,
    CollusionInvestigationTriggeredEventPayload,
    InvestigationResolution,
    InvestigationResolvedEventPayload,
    WitnessPairSuspendedEventPayload,
)
from src.domain.events.complexity_budget import (
    COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE,
    COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE,
    COMPLEXITY_SYSTEM_AGENT_ID,
    ComplexityBudgetBreachedPayload,
    ComplexityBudgetEscalatedPayload,
)
from src.domain.events.compliance import (
    COMPLIANCE_DOCUMENTED_EVENT_TYPE,
    COMPLIANCE_SYSTEM_AGENT_ID,
    ComplianceDocumentedEventPayload,
)
from src.domain.events.compliance import (
    ComplianceFramework as EventComplianceFramework,
)
from src.domain.events.compliance import (
    ComplianceStatus as EventComplianceStatus,
)
from src.domain.events.configuration_floor import (
    CONFIGURATION_FLOOR_VIOLATION_EVENT_TYPE,
    ConfigurationFloorViolationEventPayload,
    ConfigurationSource,
)
from src.domain.events.constitutional_crisis import (
    CONSTITUTIONAL_CRISIS_EVENT_TYPE,
    ConstitutionalCrisisPayload,
    CrisisType,
)
from src.domain.events.constitutional_health import (
    CONSTITUTIONAL_HEALTH_ALERT_EVENT_TYPE,
    ConstitutionalAlertSeverity,
    ConstitutionalAlertType,
    ConstitutionalHealthAlertPayload,
    create_breach_critical_alert,
    create_breach_warning_alert,
    create_ceremonies_blocked_alert,
)
from src.domain.events.context_bundle_created import (
    CONTEXT_BUNDLE_CREATED_EVENT_TYPE,
    ContextBundleCreatedPayload,
)
from src.domain.events.deadlock import (
    CROSS_EXAMINE_ROUND_TRIGGERED_EVENT_TYPE,
    DEADLOCK_DETECTED_EVENT_TYPE,
    DEADLOCK_EVENT_SCHEMA_VERSION,
    CrossExamineRoundTriggeredEvent,
    DeadlockDetectedEvent,
)
from src.domain.events.deliberation_cancelled import (
    DELIBERATION_CANCELLED_EVENT_TYPE,
    DELIBERATION_CANCELLED_SCHEMA_VERSION,
    CancelReason,
    DeliberationCancelledEvent,
)
from src.domain.events.deliberation_timeout import (
    DELIBERATION_TIMEOUT_EVENT_TYPE,
    DELIBERATION_TIMEOUT_SCHEMA_VERSION,
    DeliberationTimeoutEvent,
)
from src.domain.events.disposition import (
    DISPOSITION_EVENT_SCHEMA_VERSION,
    DeliberationCompleteEvent,
    DispositionOutcome,
    PipelineRoutingEvent,
    PipelineType,
)
from src.domain.events.dissent import (
    DISSENT_RECORDED_EVENT_TYPE,
    DISSENT_RECORDED_SCHEMA_VERSION,
    DissentRecordedEvent,
)
from src.domain.events.escalation import (
    BREACH_ACKNOWLEDGED_EVENT_TYPE,
    ESCALATION_EVENT_TYPE,
    BreachAcknowledgedEventPayload,
    EscalationEventPayload,
    ResponseChoice,
)
from src.domain.events.event import Event
from src.domain.events.fork_detected import (
    FORK_DETECTED_EVENT_TYPE,
    ForkDetectedPayload,
)
from src.domain.events.fork_signal_rate_limit import (
    FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE,
    ForkSignalRateLimitPayload,
)
from src.domain.events.governance_review_required import (
    GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE,
    RT3_THRESHOLD,
    RT3_WINDOW_DAYS,
    GovernanceReviewRequiredPayload,
)
from src.domain.events.halt_cleared import (
    HALT_CLEARED_EVENT_TYPE,
    HaltClearedPayload,
)
from src.domain.events.hash_utils import (
    GENESIS_HASH,
    HASH_ALG_NAME,
    HASH_ALG_VERSION,
    canonical_json,
    compute_content_hash,
    get_prev_hash,
)
from src.domain.events.hash_verification import (
    HASH_VERIFICATION_BREACH_EVENT_TYPE,
    HASH_VERIFICATION_COMPLETED_EVENT_TYPE,
    HashVerificationBreachEventPayload,
    HashVerificationCompletedEventPayload,
    HashVerificationResult,
)
from src.domain.events.incident_report import (
    INCIDENT_REPORT_CREATED_EVENT_TYPE,
    INCIDENT_REPORT_PUBLISHED_EVENT_TYPE,
    INCIDENT_SYSTEM_AGENT_ID,
    IncidentReportCreatedPayload,
    IncidentReportPublishedPayload,
)
from src.domain.events.independence_attestation import (
    DECLARATION_CHANGE_DETECTED_EVENT_TYPE,
    INDEPENDENCE_ATTESTATION_EVENT_TYPE,
    KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE,
    DeclarationChangeDetectedPayload,
    IndependenceAttestationPayload,
    KeeperIndependenceSuspendedPayload,
)
from src.domain.events.integrity_case import (
    INTEGRITY_CASE_UPDATED_EVENT_TYPE,
    IntegrityCaseUpdatedEventPayload,
)
from src.domain.events.keeper_availability import (
    KEEPER_ATTESTATION_EVENT_TYPE,
    KEEPER_MISSED_ATTESTATION_EVENT_TYPE,
    KEEPER_QUORUM_WARNING_EVENT_TYPE,
    KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE,
    AlertSeverity,
    KeeperAttestationPayload,
    KeeperMissedAttestationPayload,
    KeeperQuorumWarningPayload,
    KeeperReplacementInitiatedPayload,
)
from src.domain.events.key_generation_ceremony import (
    KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE,
    KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE,
    KeyGenerationCeremonyCompletedPayload,
    KeyGenerationCeremonyFailedPayload,
    KeyGenerationCeremonyStartedPayload,
    KeyGenerationCeremonyWitnessedPayload,
)
from src.domain.events.override_abuse import (
    ANOMALY_DETECTED_EVENT_TYPE,
    OVERRIDE_ABUSE_REJECTED_EVENT_TYPE,
    AnomalyDetectedPayload,
    AnomalyType,
    OverrideAbuseRejectedPayload,
    ViolationType,
)
from src.domain.events.override_event import (
    MAX_DURATION_SECONDS,
    OVERRIDE_EVENT_TYPE,
    OVERRIDE_EXPIRED_EVENT_TYPE,
    ActionType,
    OverrideEventPayload,
    OverrideExpiredEventPayload,
)
from src.domain.events.petition import (
    ADOPTION_EVENT_SCHEMA_VERSION,
    PETITION_ADOPTED_EVENT_TYPE,
    PETITION_COSIGNED_EVENT_TYPE,
    PETITION_CREATED_EVENT_TYPE,
    PETITION_SYSTEM_AGENT_ID,
    PETITION_THRESHOLD_COSIGNERS,
    PETITION_THRESHOLD_MET_EVENT_TYPE,
    PetitionAdoptedEventPayload,
    PetitionCoSignedEventPayload,
    PetitionCreatedEventPayload,
    PetitionStatus,
    PetitionThresholdMetEventPayload,
)
from src.domain.events.petition_escalation import (
    PETITION_ESCALATION_SCHEMA_VERSION,
    PETITION_ESCALATION_TRIGGERED_EVENT_TYPE,
    PetitionEscalationTriggeredEvent,
)
from src.domain.events.phase_witness import (
    BLAKE3_HASH_SIZE,
    PHASE_WITNESS_EVENT_TYPE,
    PhaseWitnessEvent,
)
from src.domain.events.pre_operational_verification import (
    POST_HALT_VERIFICATION_STARTED_EVENT_TYPE,
    VERIFICATION_BYPASSED_EVENT_TYPE,
    VERIFICATION_FAILED_EVENT_TYPE,
    VERIFICATION_PASSED_EVENT_TYPE,
    VERIFICATION_SYSTEM_AGENT_ID,
    PostHaltVerificationStartedPayload,
    VerificationBypassedPayload,
    VerificationCompletedPayload,
)
from src.domain.events.procedural_record import (
    PROCEDURAL_RECORD_EVENT_TYPE,
    ProceduralRecordPayload,
)
from src.domain.events.prohibited_language_blocked import (
    MAX_CONTENT_PREVIEW_LENGTH,
    PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE,
    PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID,
    ProhibitedLanguageBlockedEventPayload,
)
from src.domain.events.publication_scan import (
    PUBLICATION_BLOCKED_EVENT_TYPE,
    PUBLICATION_SCANNED_EVENT_TYPE,
    PUBLICATION_SCANNER_SYSTEM_AGENT_ID,
    PublicationScannedEventPayload,
    ScanResultStatus,
)
from src.domain.events.recovery_completed import (
    RECOVERY_COMPLETED_EVENT_TYPE,
    RecoveryCompletedPayload,
)
from src.domain.events.recovery_waiting_period_started import (
    RECOVERY_WAITING_PERIOD_STARTED_EVENT_TYPE,
    RecoveryWaitingPeriodStartedPayload,
)
from src.domain.events.referral import (
    PETITION_REFERRED_EVENT_TYPE,
    REFERRAL_ASSIGNED_EVENT_TYPE,
    REFERRAL_COMPLETED_EVENT_TYPE,
    REFERRAL_DEFERRED_EVENT_TYPE,
    REFERRAL_EVENT_SCHEMA_VERSION,
    REFERRAL_EXPIRED_EVENT_TYPE,
    REFERRAL_EXTENDED_EVENT_TYPE,
    PetitionReferredEvent,
    ReferralAssignedEvent,
    ReferralCompletedEvent,
    ReferralDeferredEvent,
    ReferralExpiredEvent,
    ReferralExtendedEvent,
)
from src.domain.events.rollback_completed import (
    ROLLBACK_COMPLETED_EVENT_TYPE,
    RollbackCompletedPayload,
)
from src.domain.events.rollback_target_selected import (
    ROLLBACK_TARGET_SELECTED_EVENT_TYPE,
    RollbackTargetSelectedPayload,
)
from src.domain.events.seed_validation import (
    SEED_REJECTED_EVENT_TYPE,
    SEED_VALIDATION_EVENT_TYPE,
    SeedRejectedEventPayload,
    SeedValidationEventPayload,
    SeedValidationResult,
)
from src.domain.events.semantic_violation import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    SEMANTIC_SCANNER_SYSTEM_AGENT_ID,
    SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE,
    SemanticViolationSuspectedEventPayload,
)
from src.domain.events.sequence_gap_detected import (
    SEQUENCE_GAP_DETECTED_EVENT_TYPE,
    SequenceGapDetectedPayload,
)
from src.domain.events.signing import (
    SIG_ALG_NAME,
    SIG_ALG_VERSION,
    compute_signable_content,
    signature_from_base64,
    signature_to_base64,
)
from src.domain.events.threshold import (
    THRESHOLD_UPDATED_EVENT_TYPE,
    ThresholdUpdatedEventPayload,
)
from src.domain.events.topic_diversity_alert import (
    TOPIC_DIVERSITY_ALERT_EVENT_TYPE,
    TopicDiversityAlertPayload,
)
from src.domain.events.topic_manipulation import (
    COORDINATED_SUBMISSION_SUSPECTED_EVENT_TYPE,
    TOPIC_MANIPULATION_SUSPECTED_EVENT_TYPE,
    TOPIC_RATE_LIMIT_DAILY_EVENT_TYPE,
    CoordinatedSubmissionSuspectedEventPayload,
    ManipulationPatternType,
    TopicManipulationSuspectedEventPayload,
    TopicRateLimitDailyEventPayload,
)
from src.domain.events.topic_rate_limit import (
    TOPIC_RATE_LIMIT_EVENT_TYPE,
    TopicRateLimitPayload,
)
from src.domain.events.trigger_condition_changed import (
    TRIGGER_CONDITION_CHANGED_EVENT_TYPE,
    TriggerConditionChangedEventPayload,
)
from src.domain.events.unanimous_vote import (
    UNANIMOUS_VOTE_EVENT_TYPE,
    UnanimousVotePayload,
    VoteOutcome,
)
from src.domain.events.user_content_prohibition import (
    USER_CONTENT_CLEARED_EVENT_TYPE,
    USER_CONTENT_PROHIBITED_EVENT_TYPE,
    USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
    UserContentClearedEventPayload,
    UserContentProhibitionEventPayload,
)
from src.domain.events.waiver import (
    WAIVER_DOCUMENTED_EVENT_TYPE,
    WAIVER_SYSTEM_AGENT_ID,
    WaiverDocumentedEventPayload,
    WaiverStatus,
)
from src.domain.events.witness_anomaly import (
    WITNESS_ANOMALY_EVENT_TYPE,
    WITNESS_POOL_DEGRADED_EVENT_TYPE,
    ReviewStatus,
    WitnessAnomalyEventPayload,
    WitnessAnomalyType,
    WitnessPoolDegradedEventPayload,
)
from src.domain.events.witness_selection import (
    WITNESS_PAIR_ROTATION_EVENT_TYPE,
    WITNESS_SELECTION_EVENT_TYPE,
    WitnessPairRotationEventPayload,
    WitnessSelectionEventPayload,
)

__all__: list[str] = [
    "Event",
    "GENESIS_HASH",
    "HASH_ALG_VERSION",
    "HASH_ALG_NAME",
    "canonical_json",
    "compute_content_hash",
    "get_prev_hash",
    "SIG_ALG_VERSION",
    "SIG_ALG_NAME",
    "compute_signable_content",
    "signature_to_base64",
    "signature_from_base64",
    "COLLECTIVE_OUTPUT_EVENT_TYPE",
    "AuthorType",
    "CollectiveOutputPayload",
    "VoteCounts",
    "UNANIMOUS_VOTE_EVENT_TYPE",
    "UnanimousVotePayload",
    "VoteOutcome",
    "AGENT_UNRESPONSIVE_EVENT_TYPE",
    "AgentUnresponsivePayload",
    "TOPIC_DIVERSITY_ALERT_EVENT_TYPE",
    "TopicDiversityAlertPayload",
    "TOPIC_RATE_LIMIT_EVENT_TYPE",
    "TopicRateLimitPayload",
    "CERTIFIED_RESULT_EVENT_TYPE",
    "CertifiedResultPayload",
    "PROCEDURAL_RECORD_EVENT_TYPE",
    "ProceduralRecordPayload",
    "CONTEXT_BUNDLE_CREATED_EVENT_TYPE",
    "ContextBundleCreatedPayload",
    "FORK_DETECTED_EVENT_TYPE",
    "ForkDetectedPayload",
    "CONSTITUTIONAL_CRISIS_EVENT_TYPE",
    "ConstitutionalCrisisPayload",
    "CrisisType",
    "HALT_CLEARED_EVENT_TYPE",
    "HaltClearedPayload",
    "RECOVERY_COMPLETED_EVENT_TYPE",
    "RecoveryCompletedPayload",
    "RECOVERY_WAITING_PERIOD_STARTED_EVENT_TYPE",
    "RecoveryWaitingPeriodStartedPayload",
    "SEQUENCE_GAP_DETECTED_EVENT_TYPE",
    "SequenceGapDetectedPayload",
    "FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE",
    "ForkSignalRateLimitPayload",
    "ROLLBACK_COMPLETED_EVENT_TYPE",
    "RollbackCompletedPayload",
    "ROLLBACK_TARGET_SELECTED_EVENT_TYPE",
    "RollbackTargetSelectedPayload",
    "OVERRIDE_EVENT_TYPE",
    "OVERRIDE_EXPIRED_EVENT_TYPE",
    "MAX_DURATION_SECONDS",
    "ActionType",
    "OverrideEventPayload",
    "OverrideExpiredEventPayload",
    "ANTI_SUCCESS_ALERT_EVENT_TYPE",
    "AntiSuccessAlertType",
    "AntiSuccessAlertPayload",
    "GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE",
    "GovernanceReviewRequiredPayload",
    "RT3_THRESHOLD",
    "RT3_WINDOW_DAYS",
    "KEY_GENERATION_CEREMONY_STARTED_EVENT_TYPE",
    "KEY_GENERATION_CEREMONY_WITNESSED_EVENT_TYPE",
    "KEY_GENERATION_CEREMONY_COMPLETED_EVENT_TYPE",
    "KEY_GENERATION_CEREMONY_FAILED_EVENT_TYPE",
    "KeyGenerationCeremonyStartedPayload",
    "KeyGenerationCeremonyWitnessedPayload",
    "KeyGenerationCeremonyCompletedPayload",
    "KeyGenerationCeremonyFailedPayload",
    "KEEPER_ATTESTATION_EVENT_TYPE",
    "KEEPER_MISSED_ATTESTATION_EVENT_TYPE",
    "KEEPER_QUORUM_WARNING_EVENT_TYPE",
    "KEEPER_REPLACEMENT_INITIATED_EVENT_TYPE",
    "AlertSeverity",
    "KeeperAttestationPayload",
    "KeeperMissedAttestationPayload",
    "KeeperQuorumWarningPayload",
    "KeeperReplacementInitiatedPayload",
    "OVERRIDE_ABUSE_REJECTED_EVENT_TYPE",
    "ANOMALY_DETECTED_EVENT_TYPE",
    "OverrideAbuseRejectedPayload",
    "AnomalyDetectedPayload",
    "ViolationType",
    "AnomalyType",
    "INDEPENDENCE_ATTESTATION_EVENT_TYPE",
    "KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE",
    "DECLARATION_CHANGE_DETECTED_EVENT_TYPE",
    "IndependenceAttestationPayload",
    "KeeperIndependenceSuspendedPayload",
    "DeclarationChangeDetectedPayload",
    "BREACH_DECLARED_EVENT_TYPE",
    "BreachEventPayload",
    "BreachSeverity",
    "BreachType",
    "BREACH_ACKNOWLEDGED_EVENT_TYPE",
    "ESCALATION_EVENT_TYPE",
    "BreachAcknowledgedEventPayload",
    "EscalationEventPayload",
    "ResponseChoice",
    "CESSATION_CONSIDERATION_EVENT_TYPE",
    "CESSATION_DECISION_EVENT_TYPE",
    "CessationConsiderationEventPayload",
    "CessationDecision",
    "CessationDecisionEventPayload",
    "THRESHOLD_UPDATED_EVENT_TYPE",
    "ThresholdUpdatedEventPayload",
    "WITNESS_SELECTION_EVENT_TYPE",
    "WITNESS_PAIR_ROTATION_EVENT_TYPE",
    "WitnessSelectionEventPayload",
    "WitnessPairRotationEventPayload",
    "WITNESS_ANOMALY_EVENT_TYPE",
    "WITNESS_POOL_DEGRADED_EVENT_TYPE",
    "ReviewStatus",
    "WitnessAnomalyEventPayload",
    "WitnessAnomalyType",
    "WitnessPoolDegradedEventPayload",
    "AMENDMENT_PROPOSED_EVENT_TYPE",
    "AMENDMENT_REJECTED_EVENT_TYPE",
    "AMENDMENT_VOTE_BLOCKED_EVENT_TYPE",
    "VISIBILITY_PERIOD_DAYS",
    "AmendmentImpactAnalysis",
    "AmendmentProposedEventPayload",
    "AmendmentRejectedEventPayload",
    "AmendmentStatus",
    "AmendmentType",
    "AmendmentVoteBlockedEventPayload",
    # Collusion events (Story 6.8, FR124)
    "COLLUSION_INVESTIGATION_TRIGGERED_EVENT_TYPE",
    "INVESTIGATION_RESOLVED_EVENT_TYPE",
    "WITNESS_PAIR_SUSPENDED_EVENT_TYPE",
    "CollusionInvestigationTriggeredEventPayload",
    "InvestigationResolution",
    "InvestigationResolvedEventPayload",
    "WitnessPairSuspendedEventPayload",
    # Hash verification events (Story 6.8, FR125)
    "HASH_VERIFICATION_BREACH_EVENT_TYPE",
    "HASH_VERIFICATION_COMPLETED_EVENT_TYPE",
    "HashVerificationBreachEventPayload",
    "HashVerificationCompletedEventPayload",
    "HashVerificationResult",
    # Topic manipulation events (Story 6.9, FR118-FR119)
    "COORDINATED_SUBMISSION_SUSPECTED_EVENT_TYPE",
    "TOPIC_MANIPULATION_SUSPECTED_EVENT_TYPE",
    "TOPIC_RATE_LIMIT_DAILY_EVENT_TYPE",
    "CoordinatedSubmissionSuspectedEventPayload",
    "ManipulationPatternType",
    "TopicManipulationSuspectedEventPayload",
    "TopicRateLimitDailyEventPayload",
    # Seed validation events (Story 6.9, FR124)
    "SEED_REJECTED_EVENT_TYPE",
    "SEED_VALIDATION_EVENT_TYPE",
    "SeedRejectedEventPayload",
    "SeedValidationEventPayload",
    "SeedValidationResult",
    # Configuration floor events (Story 6.10, NFR39)
    "CONFIGURATION_FLOOR_VIOLATION_EVENT_TYPE",
    "ConfigurationFloorViolationEventPayload",
    "ConfigurationSource",
    # Cessation agenda placement events (Story 7.1, FR37-FR38, RT-4)
    "CESSATION_AGENDA_PLACEMENT_EVENT_TYPE",
    "AgendaTriggerType",
    "CessationAgendaPlacementEventPayload",
    # Petition events (Story 7.2, FR39, Story 6.3)
    "ADOPTION_EVENT_SCHEMA_VERSION",
    "PETITION_ADOPTED_EVENT_TYPE",
    "PETITION_CREATED_EVENT_TYPE",
    "PETITION_COSIGNED_EVENT_TYPE",
    "PETITION_THRESHOLD_MET_EVENT_TYPE",
    "PETITION_SYSTEM_AGENT_ID",
    "PETITION_THRESHOLD_COSIGNERS",
    "PetitionAdoptedEventPayload",
    "PetitionCreatedEventPayload",
    "PetitionCoSignedEventPayload",
    "PetitionThresholdMetEventPayload",
    "PetitionStatus",
    "ADOPTION_EVENT_SCHEMA_VERSION",
    "PETITION_ADOPTED_EVENT_TYPE",
    "PetitionAdoptedEventPayload",
    # Phase witness events (Story 2A.7, FR-11.7)
    "BLAKE3_HASH_SIZE",
    "PHASE_WITNESS_EVENT_TYPE",
    "PhaseWitnessEvent",
    # Deliberation timeout events (Story 2B.2, FR-11.9, HC-7)
    "DELIBERATION_TIMEOUT_EVENT_TYPE",
    "DELIBERATION_TIMEOUT_SCHEMA_VERSION",
    "DeliberationTimeoutEvent",
    # Deadlock detection events (Story 2B.3, FR-11.10)
    "CROSS_EXAMINE_ROUND_TRIGGERED_EVENT_TYPE",
    "DEADLOCK_DETECTED_EVENT_TYPE",
    "DEADLOCK_EVENT_SCHEMA_VERSION",
    "CrossExamineRoundTriggeredEvent",
    "DeadlockDetectedEvent",
    # Dissent recorded events (Story 2B.1, FR-11.8)
    "DISSENT_RECORDED_EVENT_TYPE",
    "DISSENT_RECORDED_SCHEMA_VERSION",
    "DissentRecordedEvent",
    # Disposition events (Story 2A.8, FR-11.11)
    "DISPOSITION_EVENT_SCHEMA_VERSION",
    "DeliberationCompleteEvent",
    "DispositionOutcome",
    "PipelineRoutingEvent",
    "PipelineType",
    # Cessation executed event (Story 7.3, FR40, NFR40)
    "CESSATION_EXECUTED_EVENT_TYPE",
    "CessationExecutedEventPayload",
    # Trigger condition changed event (Story 7.7, FR134)
    "TRIGGER_CONDITION_CHANGED_EVENT_TYPE",
    "TriggerConditionChangedEventPayload",
    # Integrity Case update event (Story 7.10, FR144)
    "INTEGRITY_CASE_UPDATED_EVENT_TYPE",
    "IntegrityCaseUpdatedEventPayload",
    # Incident Report events (Story 8.4, FR54, FR145, FR147)
    "INCIDENT_REPORT_CREATED_EVENT_TYPE",
    "INCIDENT_REPORT_PUBLISHED_EVENT_TYPE",
    "INCIDENT_SYSTEM_AGENT_ID",
    "IncidentReportCreatedPayload",
    "IncidentReportPublishedPayload",
    # Pre-Operational Verification events (Story 8.5, FR146, NFR35)
    "POST_HALT_VERIFICATION_STARTED_EVENT_TYPE",
    "VERIFICATION_BYPASSED_EVENT_TYPE",
    "VERIFICATION_FAILED_EVENT_TYPE",
    "VERIFICATION_PASSED_EVENT_TYPE",
    "VERIFICATION_SYSTEM_AGENT_ID",
    "PostHaltVerificationStartedPayload",
    "VerificationBypassedPayload",
    "VerificationCompletedPayload",
    # Complexity Budget events (Story 8.6, SC-3, RT-6)
    "COMPLEXITY_BUDGET_BREACHED_EVENT_TYPE",
    "COMPLEXITY_BUDGET_ESCALATED_EVENT_TYPE",
    "COMPLEXITY_SYSTEM_AGENT_ID",
    "ComplexityBudgetBreachedPayload",
    "ComplexityBudgetEscalatedPayload",
    # Constitutional Health Alert events (Story 8.10, ADR-10)
    "CONSTITUTIONAL_HEALTH_ALERT_EVENT_TYPE",
    "ConstitutionalAlertSeverity",
    "ConstitutionalAlertType",
    "ConstitutionalHealthAlertPayload",
    "create_breach_critical_alert",
    "create_breach_warning_alert",
    "create_ceremonies_blocked_alert",
    # Prohibited Language Blocking events (Story 9.1, FR55)
    "MAX_CONTENT_PREVIEW_LENGTH",
    "PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE",
    "PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID",
    "ProhibitedLanguageBlockedEventPayload",
    # Publication Scan events (Story 9.2, FR56)
    "PUBLICATION_BLOCKED_EVENT_TYPE",
    "PUBLICATION_SCANNED_EVENT_TYPE",
    "PUBLICATION_SCANNER_SYSTEM_AGENT_ID",
    "PublicationScannedEventPayload",
    "ScanResultStatus",
    # Audit events (Story 9.3, FR57)
    "AUDIT_COMPLETED_EVENT_TYPE",
    "AUDIT_STARTED_EVENT_TYPE",
    "AUDIT_SYSTEM_AGENT_ID",
    "MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE",
    "AuditCompletedEventPayload",
    "AuditResultStatus",
    "AuditStartedEventPayload",
    "ViolationFlaggedEventPayload",
    # User Content Prohibition events (Story 9.4, FR58)
    "USER_CONTENT_CLEARED_EVENT_TYPE",
    "USER_CONTENT_PROHIBITED_EVENT_TYPE",
    "USER_CONTENT_SCANNER_SYSTEM_AGENT_ID",
    "UserContentClearedEventPayload",
    "UserContentProhibitionEventPayload",
    # Semantic Violation events (Story 9.7, FR110)
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "SEMANTIC_SCANNER_SYSTEM_AGENT_ID",
    "SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE",
    "SemanticViolationSuspectedEventPayload",
    # Waiver Documentation events (Story 9.8, SC-4, SR-10)
    "WAIVER_DOCUMENTED_EVENT_TYPE",
    "WAIVER_SYSTEM_AGENT_ID",
    "WaiverDocumentedEventPayload",
    "WaiverStatus",
    # Compliance Documentation events (Story 9.9, NFR31-34)
    "COMPLIANCE_DOCUMENTED_EVENT_TYPE",
    "COMPLIANCE_SYSTEM_AGENT_ID",
    "ComplianceDocumentedEventPayload",
    "EventComplianceFramework",
    "EventComplianceStatus",
    # Archon substitution events (Story 2B.4, NFR-10.6)
    "ARCHON_SUBSTITUTED_EVENT_TYPE",
    "ARCHON_SUBSTITUTION_SCHEMA_VERSION",
    "DELIBERATION_ABORTED_EVENT_TYPE",
    "ArchonSubstitutedEvent",
    "DeliberationAbortedEvent",
    # Referral events (Story 4.2, FR-4.1, FR-4.2)
    "PETITION_REFERRED_EVENT_TYPE",
    "REFERRAL_COMPLETED_EVENT_TYPE",
    "REFERRAL_EVENT_SCHEMA_VERSION",
    "REFERRAL_EXPIRED_EVENT_TYPE",
    "REFERRAL_EXTENDED_EVENT_TYPE",
    "PetitionReferredEvent",
    "ReferralCompletedEvent",
    "ReferralExpiredEvent",
    "ReferralExtendedEvent",
    # Referral assignment events (Story 4.7, FR-4.7, NFR-7.3)
    "REFERRAL_ASSIGNED_EVENT_TYPE",
    "REFERRAL_DEFERRED_EVENT_TYPE",
    "ReferralAssignedEvent",
    "ReferralDeferredEvent",
    # Co-sign events (Story 5.2, FR-6.1, FR-6.4, CT-12)
    "CO_SIGN_EVENT_SCHEMA_VERSION",
    "CO_SIGN_RECORDED_EVENT_TYPE",
    "CO_SIGN_SYSTEM_AGENT_ID",
    "CoSignRecordedEvent",
    # Petition escalation events (Story 5.6, FR-5.1, FR-5.3, CT-12, CT-14)
    "PETITION_ESCALATION_SCHEMA_VERSION",
    "PETITION_ESCALATION_TRIGGERED_EVENT_TYPE",
    "PetitionEscalationTriggeredEvent",
    # Deliberation cancelled events (Story 5.6, AC4)
    "DELIBERATION_CANCELLED_EVENT_TYPE",
    "DELIBERATION_CANCELLED_SCHEMA_VERSION",
    "CancelReason",
    "DeliberationCancelledEvent",
]


# =============================================================================
# NFR40 COMPLIANCE: Import-Time Validation
# =============================================================================
# This validation runs when the module is imported to ensure no prohibited
# event types (cessation reversal, undo, etc.) exist in the schema.
#
# Developer Note:
# If you add a new event type constant that ends with "_EVENT_TYPE",
# this validation will check it against prohibited patterns.
# If it matches, an EventTypeProhibitedError will be raised at import time.
# =============================================================================


def _validate_no_prohibited_event_types() -> None:
    """Import-time validation: NFR40 compliance check.

    Scans all exported event type constants to ensure none match
    prohibited patterns (cessation reversal, undo, etc.)

    Constitutional Constraint (NFR40):
    Cessation reversal is architecturally prohibited. This function
    validates at import time that no such event types exist.

    This runs automatically when the module is imported, ensuring:
    1. CI/CD fails fast if a prohibited type is added
    2. Application startup fails if prohibited types exist
    3. The constraint is self-documenting in code

    Raises:
        EventTypeProhibitedError: If any event type matches a prohibited pattern.
    """
    from src.domain.services.event_type_validator import validate_event_type

    # Get all exported names from __all__
    for name in __all__:
        if name.endswith("_EVENT_TYPE"):
            # Get the actual value of the event type constant
            event_type_value = globals().get(name)
            if event_type_value is not None and isinstance(event_type_value, str):
                # Validate - will raise EventTypeProhibitedError if prohibited
                validate_event_type(event_type_value)


# Run validation on import (NFR40)
_validate_no_prohibited_event_types()
