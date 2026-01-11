"""Domain models for Archon 72.

Contains value objects and domain models that represent
core business concepts. These models are immutable and
contain no infrastructure dependencies.
"""

from src.domain.models.agent_pool import MAX_CONCURRENT_AGENTS, AgentPool
from src.domain.models.agent_status import AgentStatus
from src.domain.models.ceremony_evidence import (
    HALT_CLEAR_CEREMONY_TYPE,
    MIN_APPROVERS_TIER_1,
    ApproverSignature,
    CeremonyEvidence,
)
from src.domain.models.halt_status_header import (
    SYSTEM_STATUS_HALTED,
    SYSTEM_STATUS_OPERATIONAL,
    HaltStatusHeader,
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
from src.domain.models.heartbeat import Heartbeat
from src.domain.models.signable import ParsedSignedContent, SignableContent
from src.domain.models.topic_diversity import TopicDiversityStats
from src.domain.models.topic_origin import (
    TopicOrigin,
    TopicOriginMetadata,
    TopicOriginType,
)
from src.domain.models.recovery_waiting_period import (
    WAITING_PERIOD_HOURS,
    RecoveryWaitingPeriod,
)
from src.domain.models.signed_fork_signal import SignedForkSignal
from src.domain.models.unwitnessed_halt import UnwitnessedHaltRecord
from src.domain.models.witness import WITNESS_PREFIX, Witness
from src.domain.models.checkpoint import Checkpoint
from src.domain.models.override_reason import (
    FORBIDDEN_OVERRIDE_SCOPE_PATTERNS,
    FORBIDDEN_OVERRIDE_SCOPES,
    OverrideReason,
    is_witness_suppression_scope,
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
from src.domain.models.ceremony_witness import (
    CeremonyWitness,
    WitnessType,
)
from src.domain.models.keeper_attestation import (
    ATTESTATION_PERIOD_DAYS,
    MINIMUM_KEEPER_QUORUM,
    MISSED_ATTESTATIONS_THRESHOLD,
    KeeperAttestation,
    get_current_period,
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
from src.domain.models.pending_escalation import (
    ESCALATION_THRESHOLD_DAYS,
    PendingEscalation,
)
from src.domain.models.breach_count_status import (
    CESSATION_THRESHOLD,
    CESSATION_WINDOW_DAYS,
    WARNING_THRESHOLD,
    BreachCountStatus,
    BreachTrajectory,
)
from src.domain.models.constitutional_threshold import (
    ConstitutionalThreshold,
    ConstitutionalThresholdRegistry,
)
from src.domain.models.witness_selection import (
    SELECTION_ALGORITHM_VERSION,
    WitnessSelectionRecord,
    WitnessSelectionSeed,
    deterministic_select,
)
from src.domain.models.witness_pair import (
    ROTATION_WINDOW_HOURS,
    WitnessPair,
    WitnessPairHistory,
)
from src.domain.models.petition import (
    CoSigner,
    Petition,
)
from src.domain.models.ceased_status_header import (
    SYSTEM_STATUS_CEASED,
    CeasedStatusHeader,
    CessationDetails,
)
from src.domain.models.cessation_trigger_condition import (
    CESSATION_TRIGGER_JSON_LD_CONTEXT,
    CessationTriggerCondition,
    CessationTriggerConditionSet,
)
from src.domain.models.integrity_case import (
    INTEGRITY_CASE_JSON_LD_CONTEXT,
    REQUIRED_CT_REFERENCES,
    GuaranteeCategory,
    IntegrityCaseArtifact,
    IntegrityGuarantee,
)
from src.domain.models.event_type_registry import EventTypeRegistry
from src.domain.models.incident_report import (
    DAILY_OVERRIDE_THRESHOLD,
    PUBLICATION_DELAY_DAYS,
    IncidentReport,
    IncidentStatus,
    IncidentType,
    TimelineEntry,
)
from src.domain.models.verification_result import (
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
)
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
from src.domain.models.failure_mode import (
    DEFAULT_FAILURE_MODES,
    EarlyWarning,
    FailureMode,
    FailureModeId,
    FailureModeSeverity,
    FailureModeStatus,
    FailureModeThreshold,
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
from src.domain.models.user_content import (
    USER_CONTENT_ID_PREFIX,
    USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
    FeatureRequest,
    FeaturedStatus,
    UserContent,
    UserContentProhibitionFlag,
    UserContentStatus,
)
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
from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
    FrameworkMapping,
    generate_assessment_id,
)
from src.domain.models.conclave import (
    AgendaItem,
    ConclavePhase,
    ConclaveSession,
    DebateEntry,
    Motion,
    MotionStatus,
    MotionType,
    RANK_ORDER,
    TranscriptEntry,
    Vote,
    VoteChoice,
    get_rank_priority,
)

__all__: list[str] = [
    "AgentPool",
    "AgentStatus",
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
]
