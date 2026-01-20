"""Domain models for Archon 72.

Contains value objects and domain models that represent
core business concepts. These models are immutable and
contain no infrastructure dependencies.
"""

from src.domain.models.acknowledgment_reason import (
    AcknowledgmentReasonCode,
    InvalidReasonCodeError,
    RationaleRequiredError,
    ReferenceRequiredError,
    validate_acknowledgment_requirements,
)
from src.domain.models.agent_pool import MAX_CONCURRENT_AGENTS, AgentPool
from src.domain.models.agent_status import AgentStatus
from src.domain.models.archon_metrics import (
    ArchonDeliberationMetrics,
)
from src.domain.models.archon_status import ArchonFailureReason, ArchonStatus
from src.domain.models.audit_event import (
    AUDIT_COMPLETED_EVENT_TYPE,
    AUDIT_EVENT_TYPE_PREFIX,
    AUDIT_STARTED_EVENT_TYPE,
    AUDIT_VIOLATION_FLAGGED_EVENT_TYPE,
    AuditCompletionStatus,
    AuditEvent,
    AuditEventType,
    AuditTrend,
    QuarterStats,
)
from src.domain.models.audit_timeline import (
    AUDIT_TIMELINE_SCHEMA_VERSION,
    BLAKE3_HASH_SIZE,
    AuditTimeline,
    TerminationReason,
    TimelineEvent,
    WitnessChainVerification,
)
from src.domain.models.breach_count_status import (
    CESSATION_THRESHOLD,
    CESSATION_WINDOW_DAYS,
    WARNING_THRESHOLD,
    BreachCountStatus,
    BreachTrajectory,
)
from src.domain.models.ceased_status_header import (
    SYSTEM_STATUS_CEASED,
    CeasedStatusHeader,
    CessationDetails,
)
from src.domain.models.ceremony_evidence import (
    HALT_CLEAR_CEREMONY_TYPE,
    MIN_APPROVERS_TIER_1,
    ApproverSignature,
    CeremonyEvidence,
)
from src.domain.models.ceremony_witness import (
    CeremonyWitness,
    WitnessType,
)
from src.domain.models.cessation_trigger_condition import (
    CESSATION_TRIGGER_JSON_LD_CONTEXT,
    CessationTriggerCondition,
    CessationTriggerConditionSet,
)
from src.domain.models.chaos_test_config import (
    CHAOS_CONFIG_SCHEMA_VERSION,
    MAX_INJECTION_DURATION_SECONDS,
    MIN_INJECTION_DURATION_SECONDS,
    ChaosScenario,
    ChaosTestConfig,
)
from src.domain.models.chaos_test_report import (
    ARCHON_SUBSTITUTION_SLA_MS,
    CHAOS_REPORT_SCHEMA_VERSION,
    ChaosTestOutcome,
    ChaosTestReport,
)
from src.domain.models.checkpoint import Checkpoint
from src.domain.models.co_sign import CoSign
from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    CEREMONY_TYPE_LIMIT,
    CROSS_COMPONENT_DEP_LIMIT,
    WARNING_THRESHOLD_PERCENT,
    ComplexityBudget,
    ComplexityBudgetStatus,
    ComplexityDimension,
    ComplexitySnapshot,
)
from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
    FrameworkMapping,
    generate_assessment_id,
)
from src.domain.models.conclave import (
    RANK_ORDER,
    AgendaItem,
    ConclavePhase,
    ConclaveSession,
    DebateEntry,
    Motion,
    MotionStatus,
    MotionType,
    TranscriptEntry,
    Vote,
    VoteChoice,
    get_rank_priority,
)
from src.domain.models.consensus_result import (
    CONSENSUS_ALGORITHM_VERSION,
    REQUIRED_VOTE_COUNT,
    SUPERMAJORITY_THRESHOLD,
    ConsensusResult,
    ConsensusStatus,
    VoteValidationResult,
    VoteValidationStatus,
)
from src.domain.models.constitutional_health import (
    BREACH_CRITICAL_THRESHOLD,
    BREACH_WARNING_THRESHOLD,
    DISSENT_CRITICAL_THRESHOLD,
    DISSENT_WARNING_THRESHOLD,
    OVERRIDE_CRITICAL_THRESHOLD,
    OVERRIDE_INCIDENT_THRESHOLD,
    WITNESS_CRITICAL_THRESHOLD,
    WITNESS_DEGRADED_THRESHOLD,
    ConstitutionalHealthMetric,
    ConstitutionalHealthSnapshot,
    ConstitutionalHealthStatus,
    MetricName,
)
from src.domain.models.constitutional_threshold import (
    ConstitutionalThreshold,
    ConstitutionalThresholdRegistry,
)
from src.domain.models.context_bundle import (
    BUNDLE_ID_PREFIX,
    CONTENT_REF_LENGTH,
    CONTENT_REF_PATTERN,
    CONTENT_REF_PREFIX,
    CONTEXT_BUNDLE_SCHEMA_VERSION,
    MAX_PRECEDENT_REFS,
    ContentRef,
    ContextBundlePayload,
    UnsignedContextBundle,
    create_content_ref,
    validate_content_ref,
)
from src.domain.models.decision_package import (
    DecisionPackage,
)
from src.domain.models.deliberation_context_package import (
    CONTEXT_PACKAGE_SCHEMA_VERSION as DELIBERATION_CONTEXT_SCHEMA_VERSION,
)
from src.domain.models.deliberation_context_package import (
    DeliberationContextPackage,
    compute_content_hash,
)
from src.domain.models.deliberation_result import (
    DeliberationResult,
    PhaseResult,
)
from src.domain.models.deliberation_session import (
    CONSENSUS_THRESHOLD,
    REQUIRED_ARCHON_COUNT,
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.domain.models.deliberation_session import (
    PHASE_TRANSITION_MATRIX as DELIBERATION_PHASE_TRANSITION_MATRIX,
)
from src.domain.models.disposition_result import (
    DispositionResult,
    PendingDisposition,
)
from src.domain.models.dissent_record import (
    BLAKE3_HASH_LENGTH,
    DissentRecord,
)
from src.domain.models.event_type_registry import EventTypeRegistry
from src.domain.models.failure_mode import (
    DEFAULT_FAILURE_MODES,
    EarlyWarning,
    FailureMode,
    FailureModeId,
    FailureModeSeverity,
    FailureModeStatus,
    FailureModeThreshold,
)
from src.domain.models.fate_archon import (
    DELIBERATION_PROMPT_HEADER,
    FATE_ARCHON_AMON,
    FATE_ARCHON_BY_ID,
    FATE_ARCHON_BY_NAME,
    FATE_ARCHON_FORNEUS,
    FATE_ARCHON_IDS,
    FATE_ARCHON_LERAJE,
    FATE_ARCHON_MARCHOSIAS,
    FATE_ARCHON_NABERIUS,
    FATE_ARCHON_ORIAS,
    FATE_ARCHON_RONOVE,
    THREE_FATES_POOL,
    DeliberationStyle,
    FateArchon,
    get_fate_archon_by_id,
    get_fate_archon_by_name,
    is_valid_fate_archon_id,
    list_fate_archons,
)
from src.domain.models.halt_status_header import (
    SYSTEM_STATUS_HALTED,
    SYSTEM_STATUS_OPERATIONAL,
    HaltStatusHeader,
)
from src.domain.models.heartbeat import Heartbeat
from src.domain.models.incident_report import (
    DAILY_OVERRIDE_THRESHOLD,
    PUBLICATION_DELAY_DAYS,
    IncidentReport,
    IncidentStatus,
    IncidentType,
    TimelineEntry,
)
from src.domain.models.independence_attestation import (
    ATTESTATION_DEADLINE_DAYS,
    DEADLINE_GRACE_PERIOD_DAYS,
    ConflictDeclaration,
    DeclarationType,
    IndependenceAttestation,
    calculate_deadline,
    get_current_attestation_year,
)
from src.domain.models.integrity_case import (
    INTEGRITY_CASE_JSON_LD_CONTEXT,
    REQUIRED_CT_REFERENCES,
    GuaranteeCategory,
    IntegrityCaseArtifact,
    IntegrityGuarantee,
)
from src.domain.models.keeper_attestation import (
    ATTESTATION_PERIOD_DAYS,
    MINIMUM_KEEPER_QUORUM,
    MISSED_ATTESTATIONS_THRESHOLD,
    KeeperAttestation,
    get_current_period,
)
from src.domain.models.keeper_key import (
    KEEPER_ID_PREFIX,
    KeeperKey,
)
from src.domain.models.key_generation_ceremony import (
    CEREMONY_TIMEOUT_SECONDS,
    REQUIRED_WITNESSES,
    TRANSITION_PERIOD_DAYS,
    VALID_TRANSITIONS,
    CeremonyState,
    CeremonyType,
    KeyGenerationCeremony,
)
from src.domain.models.load_test_config import LoadTestConfig
from src.domain.models.load_test_metrics import LoadTestMetrics
from src.domain.models.load_test_report import (
    NFR_10_1_THRESHOLD_MS,
    LoadTestReport,
)
from src.domain.models.material_audit import (
    AUDIT_ID_PREFIX,
    REMEDIATION_DEADLINE_DAYS,
    AuditQuarter,
    AuditStatus,
    MaterialAudit,
    MaterialViolation,
    RemediationStatus,
    generate_audit_id,
)
from src.domain.models.override_reason import (
    FORBIDDEN_OVERRIDE_SCOPE_PATTERNS,
    FORBIDDEN_OVERRIDE_SCOPES,
    OverrideReason,
    is_witness_suppression_scope,
)
from src.domain.models.pending_escalation import (
    ESCALATION_THRESHOLD_DAYS,
    PendingEscalation,
)
from src.domain.models.petition import (
    CoSigner,
    Petition,
)
from src.domain.models.petition_submission import (
    STATE_TRANSITION_MATRIX,
    TERMINAL_STATES,
    PetitionState,
    PetitionSubmission,
    PetitionType,
)
from src.domain.models.prohibited_language import (
    DEFAULT_PROHIBITED_TERMS,
    ProhibitedTermsList,
    normalize_for_scanning,
)
from src.domain.models.publication import (
    PUBLICATION_ID_PREFIX,
    Publication,
    PublicationScanRequest,
    PublicationStatus,
)
from src.domain.models.realm import (
    CANONICAL_REALM_IDS,
    REALM_DISPLAY_NAMES,
    Realm,
    RealmStatus,
    is_canonical_realm,
)
from src.domain.models.recovery_waiting_period import (
    WAITING_PERIOD_HOURS,
    RecoveryWaitingPeriod,
)
from src.domain.models.referral import (
    REFERRAL_DEFAULT_CYCLE_DURATION,
    REFERRAL_DEFAULT_DEADLINE_CYCLES,
    REFERRAL_MAX_EXTENSIONS,
    Referral,
    ReferralRecommendation,
    ReferralStatus,
)
from src.domain.models.scheduled_job import (
    DeadLetterJob,
    JobStatus,
    ScheduledJob,
)
from src.domain.models.signable import ParsedSignedContent, SignableContent
from src.domain.models.signed_fork_signal import SignedForkSignal
from src.domain.models.topic_diversity import TopicDiversityStats
from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)
from src.domain.models.transcript_reference import (
    TranscriptReference,
)
from src.domain.models.unwitnessed_halt import UnwitnessedHaltRecord
from src.domain.models.user_content import (
    USER_CONTENT_ID_PREFIX,
    USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
    FeaturedStatus,
    FeatureRequest,
    UserContent,
    UserContentProhibitionFlag,
    UserContentStatus,
)
from src.domain.models.verification_result import (
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)
from src.domain.models.witness import WITNESS_PREFIX, Witness
from src.domain.models.witness_pair import (
    ROTATION_WINDOW_HOURS,
    WitnessPair,
    WitnessPairHistory,
)
from src.domain.models.witness_selection import (
    SELECTION_ALGORITHM_VERSION,
    WitnessSelectionRecord,
    WitnessSelectionSeed,
    deterministic_select,
)

__all__: list[str] = [
    "AgentPool",
    "AgentStatus",
    "ArchonDeliberationMetrics",
    "BUNDLE_ID_PREFIX",
    "CONTENT_REF_LENGTH",
    "CONTENT_REF_PATTERN",
    "CONTENT_REF_PREFIX",
    "CONTEXT_BUNDLE_SCHEMA_VERSION",
    "ContentRef",
    "ContextBundlePayload",
    "Heartbeat",
    "MAX_CONCURRENT_AGENTS",
    "MAX_PRECEDENT_REFS",
    "ParsedSignedContent",
    "SignableContent",
    "TopicDiversityStats",
    "TopicOrigin",
    "TopicOriginMetadata",
    "TopicOriginType",
    "UnsignedContextBundle",
    "Witness",
    "WITNESS_PREFIX",
    "create_content_ref",
    "validate_content_ref",
    "ApproverSignature",
    "CeremonyEvidence",
    "HALT_CLEAR_CEREMONY_TYPE",
    "MIN_APPROVERS_TIER_1",
    "HaltStatusHeader",
    "SYSTEM_STATUS_HALTED",
    "SYSTEM_STATUS_OPERATIONAL",
    "RecoveryWaitingPeriod",
    "SignedForkSignal",
    "UnwitnessedHaltRecord",
    "WAITING_PERIOD_HOURS",
    "Checkpoint",
    "FORBIDDEN_OVERRIDE_SCOPE_PATTERNS",
    "FORBIDDEN_OVERRIDE_SCOPES",
    "OverrideReason",
    "is_witness_suppression_scope",
    "KEEPER_ID_PREFIX",
    "KeeperKey",
    "CEREMONY_TIMEOUT_SECONDS",
    "REQUIRED_WITNESSES",
    "TRANSITION_PERIOD_DAYS",
    "VALID_TRANSITIONS",
    "CeremonyState",
    "CeremonyType",
    "KeyGenerationCeremony",
    "CeremonyWitness",
    "WitnessType",
    "ATTESTATION_PERIOD_DAYS",
    "MINIMUM_KEEPER_QUORUM",
    "MISSED_ATTESTATIONS_THRESHOLD",
    "KeeperAttestation",
    "get_current_period",
    "ATTESTATION_DEADLINE_DAYS",
    "DEADLINE_GRACE_PERIOD_DAYS",
    "ConflictDeclaration",
    "DeclarationType",
    "IndependenceAttestation",
    "calculate_deadline",
    "get_current_attestation_year",
    "ESCALATION_THRESHOLD_DAYS",
    "PendingEscalation",
    "CESSATION_THRESHOLD",
    "CESSATION_WINDOW_DAYS",
    "WARNING_THRESHOLD",
    "BreachCountStatus",
    "BreachTrajectory",
    "ConstitutionalThreshold",
    "ConstitutionalThresholdRegistry",
    "SELECTION_ALGORITHM_VERSION",
    "WitnessSelectionRecord",
    "WitnessSelectionSeed",
    "deterministic_select",
    "ROTATION_WINDOW_HOURS",
    "WitnessPair",
    "WitnessPairHistory",
    # Petition models (Story 7.2, FR39)
    "CoSigner",
    "Petition",
    # Petition submission models (Story 0.2, FR-2.2, Story 1.5)
    "PetitionState",
    "PetitionSubmission",
    "PetitionType",
    "STATE_TRANSITION_MATRIX",
    "TERMINAL_STATES",
    # Realm models (Story 0.6, HP-3, HP-4)
    "CANONICAL_REALM_IDS",
    "REALM_DISPLAY_NAMES",
    "Realm",
    "RealmStatus",
    "is_canonical_realm",
    # Scheduled job models (Story 0.4, HP-1, HC-6, NFR-7.5)
    "DeadLetterJob",
    "JobStatus",
    "ScheduledJob",
    # Cessation models (Story 7.4, FR41)
    "SYSTEM_STATUS_CEASED",
    "CeasedStatusHeader",
    "CessationDetails",
    # Cessation trigger condition models (Story 7.7, FR134)
    "CESSATION_TRIGGER_JSON_LD_CONTEXT",
    "CessationTriggerCondition",
    "CessationTriggerConditionSet",
    # Integrity Case Artifact models (Story 7.10, FR144)
    "INTEGRITY_CASE_JSON_LD_CONTEXT",
    "REQUIRED_CT_REFERENCES",
    "GuaranteeCategory",
    "IntegrityCaseArtifact",
    "IntegrityGuarantee",
    # Event Type Registry (Story 8.2, FR52)
    "EventTypeRegistry",
    # Incident Report models (Story 8.4, FR54, FR145, FR147)
    "DAILY_OVERRIDE_THRESHOLD",
    "PUBLICATION_DELAY_DAYS",
    "IncidentReport",
    "IncidentStatus",
    "IncidentType",
    "TimelineEntry",
    # Pre-operational verification models (Story 8.5, FR146, NFR35)
    "VerificationCheck",
    "VerificationResult",
    "VerificationStatus",
    # Complexity budget models (Story 8.6, SC-3, RT-6)
    "ADR_LIMIT",
    "CEREMONY_TYPE_LIMIT",
    "CROSS_COMPONENT_DEP_LIMIT",
    "WARNING_THRESHOLD_PERCENT",
    "ComplexityBudget",
    "ComplexityBudgetStatus",
    "ComplexityDimension",
    "ComplexitySnapshot",
    # Failure mode models (Story 8.8, FR106-FR107)
    "DEFAULT_FAILURE_MODES",
    "EarlyWarning",
    "FailureMode",
    "FailureModeId",
    "FailureModeSeverity",
    "FailureModeStatus",
    "FailureModeThreshold",
    # Constitutional health models (Story 8.10, ADR-10)
    "BREACH_CRITICAL_THRESHOLD",
    "BREACH_WARNING_THRESHOLD",
    "DISSENT_CRITICAL_THRESHOLD",
    "DISSENT_WARNING_THRESHOLD",
    "OVERRIDE_CRITICAL_THRESHOLD",
    "OVERRIDE_INCIDENT_THRESHOLD",
    "WITNESS_CRITICAL_THRESHOLD",
    "WITNESS_DEGRADED_THRESHOLD",
    "ConstitutionalHealthMetric",
    "ConstitutionalHealthSnapshot",
    "ConstitutionalHealthStatus",
    "MetricName",
    # Prohibited language models (Story 9.1, FR55)
    "DEFAULT_PROHIBITED_TERMS",
    "ProhibitedTermsList",
    "normalize_for_scanning",
    # Publication models (Story 9.2, FR56)
    "PUBLICATION_ID_PREFIX",
    "Publication",
    "PublicationScanRequest",
    "PublicationStatus",
    # Material audit models (Story 9.3, FR57)
    "AUDIT_ID_PREFIX",
    "REMEDIATION_DEADLINE_DAYS",
    "AuditQuarter",
    "AuditStatus",
    "MaterialAudit",
    "MaterialViolation",
    "RemediationStatus",
    "generate_audit_id",
    # User content models (Story 9.4, FR58)
    "USER_CONTENT_ID_PREFIX",
    "USER_CONTENT_SCANNER_SYSTEM_AGENT_ID",
    "FeatureRequest",
    "FeaturedStatus",
    "UserContent",
    "UserContentProhibitionFlag",
    "UserContentStatus",
    # Audit event query models (Story 9.5, FR108)
    "AUDIT_COMPLETED_EVENT_TYPE",
    "AUDIT_EVENT_TYPE_PREFIX",
    "AUDIT_STARTED_EVENT_TYPE",
    "AUDIT_VIOLATION_FLAGGED_EVENT_TYPE",
    "AuditCompletionStatus",
    "AuditEvent",
    "AuditEventType",
    "AuditTrend",
    "QuarterStats",
    # Compliance models (Story 9.9, NFR31-34)
    "ComplianceAssessment",
    "ComplianceFramework",
    "ComplianceRequirement",
    "ComplianceStatus",
    "FrameworkMapping",
    "generate_assessment_id",
    # Conclave models (Epic 11 - CrewAI Conclave)
    "AgendaItem",
    "ConclavePhase",
    "ConclaveSession",
    "DebateEntry",
    "Motion",
    "MotionStatus",
    "MotionType",
    "RANK_ORDER",
    "TranscriptEntry",
    "Vote",
    "VoteChoice",
    "get_rank_priority",
    # FateArchon models (Story 0.7, HP-11)
    "DELIBERATION_PROMPT_HEADER",
    "DeliberationStyle",
    "FATE_ARCHON_AMON",
    "FATE_ARCHON_BY_ID",
    "FATE_ARCHON_BY_NAME",
    "FATE_ARCHON_FORNEUS",
    "FATE_ARCHON_IDS",
    "FATE_ARCHON_LERAJE",
    "FATE_ARCHON_MARCHOSIAS",
    "FATE_ARCHON_NABERIUS",
    "FATE_ARCHON_ORIAS",
    "FATE_ARCHON_RONOVE",
    "FateArchon",
    "THREE_FATES_POOL",
    "get_fate_archon_by_id",
    "get_fate_archon_by_name",
    "is_valid_fate_archon_id",
    "list_fate_archons",
    # Deliberation session models (Story 2A.1, FR-11.1, FR-11.4)
    "CONSENSUS_THRESHOLD",
    "DELIBERATION_PHASE_TRANSITION_MATRIX",
    "REQUIRED_ARCHON_COUNT",
    "DeliberationOutcome",
    "DeliberationPhase",
    "DeliberationSession",
    # Deliberation context package models (Story 2A.3, FR-11.3)
    "DELIBERATION_CONTEXT_SCHEMA_VERSION",
    "DeliberationContextPackage",
    "compute_content_hash",
    # Deliberation result models (Story 2A.4, FR-11.4)
    "DeliberationResult",
    "PhaseResult",
    # Consensus result models (Story 2A.6, FR-11.5, FR-11.6)
    "CONSENSUS_ALGORITHM_VERSION",
    "REQUIRED_VOTE_COUNT",
    "SUPERMAJORITY_THRESHOLD",
    "ConsensusResult",
    "ConsensusStatus",
    "VoteValidationResult",
    "VoteValidationStatus",
    # Disposition result models (Story 2A.8, FR-11.11)
    "DispositionResult",
    "PendingDisposition",
    # Dissent record models (Story 2B.1, FR-11.8)
    "BLAKE3_HASH_LENGTH",
    "DissentRecord",
    # Archon status models (Story 2B.4, NFR-10.6)
    "ArchonFailureReason",
    "ArchonStatus",
    # Transcript reference models (Story 2B.5, FR-11.7)
    "TranscriptReference",
    # Audit timeline models (Story 2B.6, FR-11.12, NFR-6.5)
    "AUDIT_TIMELINE_SCHEMA_VERSION",
    "BLAKE3_HASH_SIZE",
    "AuditTimeline",
    "TerminationReason",
    "TimelineEvent",
    "WitnessChainVerification",
    # Load test models (Story 2B.7, NFR-10.5)
    "LoadTestConfig",
    "LoadTestMetrics",
    "LoadTestReport",
    "NFR_10_1_THRESHOLD_MS",
    # Chaos test models (Story 2B.8, NFR-9.5)
    "ARCHON_SUBSTITUTION_SLA_MS",
    "CHAOS_CONFIG_SCHEMA_VERSION",
    "CHAOS_REPORT_SCHEMA_VERSION",
    "ChaosScenario",
    "ChaosTestConfig",
    "ChaosTestOutcome",
    "ChaosTestReport",
    "MAX_INJECTION_DURATION_SECONDS",
    "MIN_INJECTION_DURATION_SECONDS",
    # Acknowledgment reason code models (Story 3.1, FR-3.2)
    "AcknowledgmentReasonCode",
    "InvalidReasonCodeError",
    "RationaleRequiredError",
    "ReferenceRequiredError",
    "validate_acknowledgment_requirements",
    # Referral models (Story 4.1, FR-4.1, FR-4.2)
    "REFERRAL_DEFAULT_CYCLE_DURATION",
    "REFERRAL_DEFAULT_DEADLINE_CYCLES",
    "REFERRAL_MAX_EXTENSIONS",
    "Referral",
    "ReferralRecommendation",
    "ReferralStatus",
    # Decision package models (Story 4.3, FR-4.3)
    "DecisionPackage",
    # Co-sign models (Story 5.1, FR-6.2, NFR-3.5)
    "CoSign",
]
