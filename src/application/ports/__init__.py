"""Application ports - Abstract interfaces for infrastructure adapters.

This module defines the contracts that infrastructure adapters must implement.
Ports enable dependency inversion and make the application layer testable.

Available ports:
- HSMProtocol: Hardware Security Module operations (signing, verification)
- EventStorePort: Event store operations (append-only)
- KeyRegistryProtocol: Agent key registry operations (FR75, FR76)
- WitnessPoolProtocol: Witness pool operations (FR4, FR5)
- HaltChecker: Halt state checking interface (Story 1.6, Epic 3 stub)
- WriterLockProtocol: Single-writer lock interface (Story 1.6, ADR-1)
- EventReplicatorPort: Replica propagation and verification (Story 1.10, FR94-FR95)
- AgentOrchestratorProtocol: Agent orchestration interface (Story 2.2, FR10)

Helper functions:
- validate_sequence_continuity: Validate sequence gaps (FR7, Story 1.5)
"""

# Time Authority Protocol (HARDENING-1, AC4)
from src.application.ports.agent_orchestrator import (
    AgentOrchestratorProtocol,
    AgentOutput,
    AgentRequest,
    AgentStatus,
    AgentStatusInfo,
    ContextBundle,
)
from src.application.ports.amendment_repository import (
    AmendmentProposal,
    AmendmentRepositoryProtocol,
)
from src.application.ports.amendment_visibility_validator import (
    AmendmentVisibilityValidatorProtocol,
    HistoryProtectionResult,
    ImpactValidationResult,
    VisibilityValidationResult,
)
from src.application.ports.anomaly_detector import (
    AnomalyDetectorProtocol,
    AnomalyResult,
    FrequencyData,
)
from src.application.ports.anti_success_alert_repository import (
    AntiSuccessAlertRepositoryProtocol,
    SustainedAlertInfo,
)
from src.application.ports.archon_profile_repository import (
    ArchonProfileRepository,
)
from src.application.ports.archon_selector import (
    DEFAULT_MAX_ARCHONS,
    DEFAULT_MIN_ARCHONS,
    DEFAULT_RELEVANCE_THRESHOLD,
    ArchonSelection,
    ArchonSelectionMetadata,
    ArchonSelectorProtocol,
    SelectionMode,
    TopicContext,
)
from src.application.ports.audit_repository import (
    AuditRepositoryProtocol,
)
from src.application.ports.breach_declaration import BreachDeclarationProtocol
from src.application.ports.breach_repository import BreachRepositoryProtocol
from src.application.ports.cessation import CessationConsiderationProtocol
from src.application.ports.cessation_agenda_repository import (
    CessationAgendaRepositoryProtocol,
)
from src.application.ports.cessation_flag_repository import (
    CessationFlagRepositoryProtocol,
)
from src.application.ports.cessation_repository import CessationRepositoryProtocol
from src.application.ports.checkpoint_repository import CheckpointRepository
from src.application.ports.collective_output import (
    CollectiveOutputPort,
    StoredCollectiveOutput,
)
from src.application.ports.collusion_investigator import (
    CollusionInvestigatorProtocol,
    Investigation,
    InvestigationStatus,
)
from src.application.ports.complexity_budget_repository import (
    ComplexityBudgetRepositoryPort,
)
from src.application.ports.complexity_calculator import (
    ComplexityCalculatorPort,
)
from src.application.ports.compliance_repository import (
    ComplianceRepositoryProtocol,
)
from src.application.ports.configuration_floor_validator import (
    ConfigurationChangeResult,
    ConfigurationFloorValidatorProtocol,
    ConfigurationHealthStatus,
    ConfigurationValidationResult,
    ThresholdStatus,
    ThresholdViolation,
)
from src.application.ports.content_hash_service import (
    ContentHashServiceProtocol,
)
from src.application.ports.realm_registry import (
    RealmRegistryProtocol,
)
from src.application.ports.archon_pool import (
    ArchonPoolProtocol,
)
from src.application.ports.constitution_validator import ConstitutionValidatorProtocol
from src.application.ports.constitutional_health import (
    ConstitutionalHealthPort,
)
from src.application.ports.content_verification import (
    ContentVerificationPort,
    ContentVerificationResult,
)
from src.application.ports.context_bundle_creator import (
    BundleCreationResult,
    BundleVerificationResult,
    ContextBundleCreatorPort,
)
from src.application.ports.context_bundle_validator import (
    BundleValidationResult,
    ContextBundleValidatorPort,
    FreshnessCheckResult,
)
from src.application.ports.dissent_metrics import (
    DissentMetricsPort,
    DissentRecord,
)
from src.application.ports.dual_channel_halt import (
    CONFIRMATION_TIMEOUT_SECONDS,
    DualChannelHaltTransport,
    HaltFlagState,
)

# Government PRD Phase 3 - Duke Service (Epic 4, FR-GOV-11, FR-GOV-13)
from src.application.ports.duke_service import (
    DomainOwnershipRequest,
    DomainOwnershipResult,
    DomainStatus,
    DukeServiceProtocol,
    ExecutionDomain,
    ProgressReport,
    ProgressTrackingResult,
    ResourceAllocation,
    ResourceAllocationRequest,
    ResourceAllocationResult,
    ResourceType,
    StatusReport,
    StatusReportResult,
    TaskProgressStatus,
)

# Government PRD Phase 3 - Earl Service (Epic 4, FR-GOV-12, FR-GOV-13)
from src.application.ports.earl_service import (
    AgentAssignment,
    AgentCoordination,
    AgentCoordinationRequest,
    AgentCoordinationResult,
    AgentRole,
    EarlServiceProtocol,
    ExecutionResult,
    ExecutionStatus,
    OptimizationAction,
    OptimizationReport,
    OptimizationRequest,
    OptimizationResult,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from src.application.ports.entropy_source import EntropySourceProtocol
from src.application.ports.escalation import EscalationProtocol
from src.application.ports.escalation_repository import EscalationRepositoryProtocol
from src.application.ports.event_query import (
    EventQueryProtocol,
)
from src.application.ports.event_replicator import (
    EventReplicatorPort,
    ReplicationReceipt,
    ReplicationStatus,
    VerificationResult,
)
from src.application.ports.event_store import (
    EventStorePort,
    validate_sequence_continuity,
)
from src.application.ports.external_health import (
    ExternalHealthPort,
    ExternalHealthStatus,
)
from src.application.ports.failure_mode_registry import (
    FailureModeRegistryPort,
    HealthSummary,
)

# Government PRD Phase 3 - Flow Orchestrator (Epic 8, Story 8.2, FR-GOV-23)
from src.application.ports.flow_orchestrator import (
    ERROR_TYPE_MAP,
    STATE_BRANCH_MAP,
    STATE_SERVICE_MAP,
    BranchResult,
    ErrorEscalationStrategy,
    EscalationRecord,
    FlowOrchestratorProtocol,
    GovernanceBranch,
    HandleCompletionRequest,
    HandleCompletionResult,
    MotionBlockReason,
    MotionPipelineState,
    PipelineStatus,
    ProcessMotionRequest,
    ProcessMotionResult,
    RouteMotionRequest,
    RouteMotionResult,
    RoutingDecision,
    get_branch_for_state,
    get_escalation_strategy,
    get_service_for_state,
    is_blocking_error,
    is_retryable_error,
)
from src.application.ports.fork_monitor import ForkMonitor
from src.application.ports.fork_signal_rate_limiter import ForkSignalRateLimiterPort
from src.application.ports.freeze_checker import (
    FreezeCheckerProtocol,
)

# Government PRD Phase 3 - Governance State Machine (Epic 8, FR-GOV-23)
from src.application.ports.governance_state_machine import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    GovernanceState,
    GovernanceStateMachineProtocol,
    InvalidTransitionError,
    MotionStateRecord,
    StateTransition,
    TerminalStateError,
    TransitionRejection,
    TransitionRequest,
    TransitionResult,
    get_valid_next_states,
    is_terminal_state,
    is_valid_transition,
)
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.halt_trigger import HaltTrigger
from src.application.ports.hash_verifier import (
    HashScanResult,
    HashScanStatus,
    HashVerifierProtocol,
)
from src.application.ports.heartbeat_emitter import (
    HEARTBEAT_INTERVAL_SECONDS,
    MISSED_HEARTBEAT_THRESHOLD,
    UNRESPONSIVE_TIMEOUT_SECONDS,
    HeartbeatEmitterPort,
)
from src.application.ports.heartbeat_monitor import HeartbeatMonitorPort
from src.application.ports.hsm import HSMMode, HSMProtocol, SignatureResult
from src.application.ports.incident_report_repository import (
    IncidentReportRepositoryPort,
)
from src.application.ports.independence_attestation import (
    IndependenceAttestationProtocol,
)
from src.application.ports.integrity_case_repository import (
    IntegrityCaseRepositoryProtocol,
)
from src.application.ports.integrity_failure_repository import (
    IntegrityFailure,
    IntegrityFailureRepositoryProtocol,
)
from src.application.ports.keeper_availability import KeeperAvailabilityProtocol
from src.application.ports.keeper_key_registry import KeeperKeyRegistryProtocol
from src.application.ports.key_generation_ceremony import KeyGenerationCeremonyProtocol
from src.application.ports.key_registry import KeyRegistryProtocol

# Government PRD Phase 3 - Marquis Service (Epic 6, FR-GOV-17, FR-GOV-18)
from src.application.ports.marquis_service import (
    MARQUIS_DOMAIN_MAPPING,
    Advisory,
    AdvisoryRequest,
    AdvisoryResult,
    ExpertiseDomain,
    MarquisServiceProtocol,
    RiskAnalysis,
    RiskAnalysisRequest,
    RiskAnalysisResult,
    RiskFactor,
    RiskLevel,
    Testimony,
    TestimonyRequest,
    TestimonyResult,
    get_expertise_domain,
    get_marquis_for_domain,
)
from src.application.ports.material_repository import (
    MATERIAL_TYPE_ANNOUNCEMENT,
    MATERIAL_TYPE_DOCUMENT,
    MATERIAL_TYPE_PUBLICATION,
    Material,
    MaterialRepositoryProtocol,
)
from src.application.ports.override_abuse_validator import (
    OverrideAbuseValidatorProtocol,
    ValidationResult,
)
from src.application.ports.override_executor import (
    OverrideExecutorPort,
    OverrideResult,
)
from src.application.ports.override_registry import (
    ExpiredOverrideInfo,
    OverrideRegistryPort,
)
from src.application.ports.override_trend_repository import (
    OverrideTrendData,
    OverrideTrendRepositoryProtocol,
)
from src.application.ports.petition_repository import (
    PetitionRepositoryProtocol,
)
from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.application.ports.petition_event_emitter import (
    PetitionEventEmitterPort,
)
from src.application.ports.job_scheduler import (
    JobSchedulerProtocol,
)
from src.application.ports.queue_capacity import (
    QueueCapacityPort,
)
from src.application.ports.rate_limiter import (
    RateLimitResult,
    RateLimiterPort,
)
from src.application.ports.rate_limit_store import (
    RateLimitStorePort,
)
from src.application.ports.procedural_record_generator import (
    ProceduralRecordData,
    ProceduralRecordGeneratorPort,
)
from src.application.ports.prohibited_language_scanner import (
    ProhibitedLanguageScannerProtocol,
    ScanResult,
)
from src.application.ports.publication_scanner import (
    PublicationScannerProtocol,
    PublicationScanResult,
    PublicationScanResultStatus,
)
from src.application.ports.recovery_waiting_period import RecoveryWaitingPeriodPort
from src.application.ports.result_certifier import (
    CertificationResult,
    ResultCertifierPort,
)
from src.application.ports.rollback_coordinator import RollbackCoordinator
from src.application.ports.seed_validator import (
    PredictabilityCheck,
    SeedSourceValidation,
    SeedUsageRecord,
    SeedValidatorProtocol,
)
from src.application.ports.semantic_scanner import (
    DEFAULT_ANALYSIS_METHOD,
    SemanticScannerProtocol,
    SemanticScanResult,
)
from src.application.ports.separation_validator import (
    DataClassification,
    SeparationValidatorPort,
)
from src.application.ports.sequence_gap_detector import (
    DETECTION_INTERVAL_SECONDS,
    SequenceGapDetectorPort,
)
from src.application.ports.signature_verifier import (
    SignatureVerifierProtocol,
)
from src.application.ports.terminal_event_detector import (
    TerminalEventDetectorProtocol,
)
from src.application.ports.threshold_configuration import (
    ThresholdConfigurationProtocol,
    ThresholdRepositoryProtocol,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.application.ports.tool_registry import (
    ToolRegistryProtocol,
)
from src.application.ports.topic_daily_limiter import (
    DAILY_TOPIC_LIMIT,
    TopicDailyLimiterProtocol,
)
from src.application.ports.topic_manipulation_detector import (
    FlaggedTopic,
    ManipulationAnalysisResult,
    TimingPatternResult,
    TopicManipulationDetectorProtocol,
)
from src.application.ports.topic_origin_tracker import (
    DIVERSITY_THRESHOLD,
    DIVERSITY_WINDOW_DAYS,
    TopicOriginTrackerPort,
)
from src.application.ports.topic_priority import (
    TopicPriorityLevel,
    TopicPriorityProtocol,
)
from src.application.ports.topic_rate_limiter import (
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_WINDOW_SECONDS,
    TopicRateLimiterPort,
)
from src.application.ports.unanimous_vote import (
    StoredUnanimousVote,
    UnanimousVotePort,
)
from src.application.ports.unwitnessed_halt_repository import UnwitnessedHaltRepository
from src.application.ports.user_content_repository import (
    UserContentRepositoryProtocol,
)
from src.application.ports.waiver_repository import (
    WaiverRecord,
    WaiverRepositoryProtocol,
)
from src.application.ports.witness_anomaly_detector import (
    PairExclusion,
    WitnessAnomalyDetectorProtocol,
    WitnessAnomalyResult,
)
from src.application.ports.witness_pair_history import WitnessPairHistoryProtocol
from src.application.ports.witness_pool import WitnessPoolProtocol
from src.application.ports.witness_pool_monitor import (
    MINIMUM_WITNESSES_HIGH_STAKES,
    MINIMUM_WITNESSES_STANDARD,
    WitnessPoolMonitorProtocol,
    WitnessPoolStatus,
)
from src.application.ports.witnessed_halt_writer import WitnessedHaltWriter
from src.application.ports.writer_lock import WriterLockProtocol

__all__: list[str] = [
    # Time Authority Protocol (HARDENING-1, AC4)
    "TimeAuthorityProtocol",
    "AgentOrchestratorProtocol",
    "AgentOutput",
    "AgentRequest",
    "AgentStatus",
    "AgentStatusInfo",
    "ContextBundle",
    "HSMProtocol",
    "HSMMode",
    "SignatureResult",
    "EventStorePort",
    "EventReplicatorPort",
    "ReplicationReceipt",
    "ReplicationStatus",
    "VerificationResult",
    "KeyRegistryProtocol",
    "WitnessPoolProtocol",
    "HaltChecker",
    "HaltTrigger",
    "WriterLockProtocol",
    "validate_sequence_continuity",
    "CollectiveOutputPort",
    "StoredCollectiveOutput",
    "DissentMetricsPort",
    "DissentRecord",
    "StoredUnanimousVote",
    "UnanimousVotePort",
    "ContentVerificationPort",
    "ContentVerificationResult",
    "HeartbeatEmitterPort",
    "HeartbeatMonitorPort",
    "HEARTBEAT_INTERVAL_SECONDS",
    "MISSED_HEARTBEAT_THRESHOLD",
    "UNRESPONSIVE_TIMEOUT_SECONDS",
    "TopicOriginTrackerPort",
    "DIVERSITY_WINDOW_DAYS",
    "DIVERSITY_THRESHOLD",
    "TopicRateLimiterPort",
    "RATE_LIMIT_PER_HOUR",
    "RATE_LIMIT_WINDOW_SECONDS",
    "ResultCertifierPort",
    "CertificationResult",
    "ProceduralRecordGeneratorPort",
    "ProceduralRecordData",
    "BundleCreationResult",
    "BundleVerificationResult",
    "ContextBundleCreatorPort",
    "BundleValidationResult",
    "ContextBundleValidatorPort",
    "FreshnessCheckResult",
    "ForkMonitor",
    "HaltTrigger",
    "DualChannelHaltTransport",
    "HaltFlagState",
    "CONFIRMATION_TIMEOUT_SECONDS",
    "DETECTION_INTERVAL_SECONDS",
    "RecoveryWaitingPeriodPort",
    "SequenceGapDetectorPort",
    "ForkSignalRateLimiterPort",
    "UnwitnessedHaltRepository",
    "WitnessedHaltWriter",
    "CheckpointRepository",
    "RollbackCoordinator",
    "OverrideExecutorPort",
    "OverrideResult",
    "OverrideRegistryPort",
    "ExpiredOverrideInfo",
    "ConstitutionValidatorProtocol",
    "OverrideTrendData",
    "OverrideTrendRepositoryProtocol",
    "KeeperKeyRegistryProtocol",
    "KeyGenerationCeremonyProtocol",
    "KeeperAvailabilityProtocol",
    "OverrideAbuseValidatorProtocol",
    "ValidationResult",
    "AnomalyDetectorProtocol",
    "AnomalyResult",
    "FrequencyData",
    "IndependenceAttestationProtocol",
    "BreachDeclarationProtocol",
    "BreachRepositoryProtocol",
    "EscalationProtocol",
    "EscalationRepositoryProtocol",
    "CessationConsiderationProtocol",
    "CessationRepositoryProtocol",
    "ThresholdConfigurationProtocol",
    "ThresholdRepositoryProtocol",
    "EntropySourceProtocol",
    "WitnessPairHistoryProtocol",
    "WitnessAnomalyDetectorProtocol",
    "WitnessAnomalyResult",
    "PairExclusion",
    "WitnessPoolMonitorProtocol",
    "WitnessPoolStatus",
    "MINIMUM_WITNESSES_STANDARD",
    "MINIMUM_WITNESSES_HIGH_STAKES",
    "AmendmentProposal",
    "AmendmentRepositoryProtocol",
    "AmendmentVisibilityValidatorProtocol",
    "HistoryProtectionResult",
    "ImpactValidationResult",
    "VisibilityValidationResult",
    # Collusion investigation (Story 6.8, FR124)
    "CollusionInvestigatorProtocol",
    "Investigation",
    "InvestigationStatus",
    # Hash verification (Story 6.8, FR125)
    "HashScanResult",
    "HashScanStatus",
    "HashVerifierProtocol",
    # Topic manipulation detection (Story 6.9, FR118)
    "FlaggedTopic",
    "ManipulationAnalysisResult",
    "TimingPatternResult",
    "TopicManipulationDetectorProtocol",
    # Seed validation (Story 6.9, FR124)
    "PredictabilityCheck",
    "SeedSourceValidation",
    "SeedUsageRecord",
    "SeedValidatorProtocol",
    # Daily rate limiting (Story 6.9, FR118)
    "DAILY_TOPIC_LIMIT",
    "TopicDailyLimiterProtocol",
    # Topic priority (Story 6.9, FR119)
    "TopicPriorityLevel",
    "TopicPriorityProtocol",
    # Configuration floor validation (Story 6.10, NFR39)
    "ConfigurationChangeResult",
    "ConfigurationFloorValidatorProtocol",
    "ConfigurationHealthStatus",
    "ConfigurationValidationResult",
    "ThresholdStatus",
    "ThresholdViolation",
    # Integrity failure tracking (Story 7.1, FR37, RT-4)
    "IntegrityFailure",
    "IntegrityFailureRepositoryProtocol",
    # Anti-success alert tracking (Story 7.1, FR38)
    "AntiSuccessAlertRepositoryProtocol",
    "SustainedAlertInfo",
    # Cessation agenda placement (Story 7.1, FR37-FR38, RT-4)
    "CessationAgendaRepositoryProtocol",
    # Petition repository (Story 7.2, FR39)
    "PetitionRepositoryProtocol",
    # Petition submission repository (Story 0.3, FR-9.1)
    "PetitionSubmissionRepositoryProtocol",
    # Petition event emitter (Story 1.2, FR-1.7)
    "PetitionEventEmitterPort",
    # Job Scheduler (Story 0.4, HP-1, HC-6, NFR-7.5)
    "JobSchedulerProtocol",
    # Queue Capacity (Story 1.3, FR-1.4, NFR-3.1, CT-11)
    "QueueCapacityPort",
    # Rate Limiter (Story 1.4, FR-1.5, HC-4, D4)
    "RateLimitResult",
    "RateLimiterPort",
    "RateLimitStorePort",
    # Content Hash Service (Story 0.5, HP-2, HC-5)
    "ContentHashServiceProtocol",
    # Realm Registry (Story 0.6, HP-3, HP-4)
    "RealmRegistryProtocol",
    # Archon Pool (Story 0.7, HP-11, FR-11.1)
    "ArchonPoolProtocol",
    # Signature verifier (Story 7.2, FR39, AC4)
    "SignatureVerifierProtocol",
    # Terminal event detection (Story 7.3, FR40, NFR40)
    "TerminalEventDetectorProtocol",
    # Freeze mechanics (Story 7.4, FR41)
    "FreezeCheckerProtocol",
    "CessationFlagRepositoryProtocol",
    # Integrity Case Artifact (Story 7.10, FR144)
    "IntegrityCaseRepositoryProtocol",
    # Separation Validator (Story 8.2, FR52)
    "DataClassification",
    "SeparationValidatorPort",
    # External Health (Story 8.3, FR54)
    "ExternalHealthPort",
    "ExternalHealthStatus",
    # Incident Report Repository (Story 8.4, FR54, FR145, FR147)
    "IncidentReportRepositoryPort",
    # Complexity Budget (Story 8.6, CT-14, RT-6, SC-3)
    "ComplexityCalculatorPort",
    "ComplexityBudgetRepositoryPort",
    # Failure Mode Registry (Story 8.8, FR106-FR107)
    "FailureModeRegistryPort",
    "HealthSummary",
    # Constitutional Health Port (Story 8.10, ADR-10)
    "ConstitutionalHealthPort",
    # Prohibited Language Scanner (Story 9.1, FR55)
    "ProhibitedLanguageScannerProtocol",
    "ScanResult",
    # Publication Scanner (Story 9.2, FR56)
    "PublicationScannerProtocol",
    "PublicationScanResult",
    "PublicationScanResultStatus",
    # Material Repository (Story 9.3, FR57)
    "Material",
    "MaterialRepositoryProtocol",
    "MATERIAL_TYPE_ANNOUNCEMENT",
    "MATERIAL_TYPE_DOCUMENT",
    "MATERIAL_TYPE_PUBLICATION",
    # Audit Repository (Story 9.3, FR57)
    "AuditRepositoryProtocol",
    # User Content Repository (Story 9.4, FR58)
    "UserContentRepositoryProtocol",
    # Event Query (Story 9.5, FR108)
    "EventQueryProtocol",
    # Semantic Scanner (Story 9.7, FR110)
    "DEFAULT_ANALYSIS_METHOD",
    "SemanticScannerProtocol",
    "SemanticScanResult",
    # Waiver Repository (Story 9.8, SC-4, SR-10)
    "WaiverRecord",
    "WaiverRepositoryProtocol",
    # Compliance Repository (Story 9.9, NFR31-34)
    "ComplianceRepositoryProtocol",
    # Tool Registry (Story 10.3, FR10, NFR5)
    "ToolRegistryProtocol",
    # Archon Profile Repository (Story 10.1)
    "ArchonProfileRepository",
    # Archon Selector (Story 10.4, FR10, NFR5)
    "ArchonSelection",
    "ArchonSelectionMetadata",
    "ArchonSelectorProtocol",
    "DEFAULT_MAX_ARCHONS",
    "DEFAULT_MIN_ARCHONS",
    "DEFAULT_RELEVANCE_THRESHOLD",
    "SelectionMode",
    "TopicContext",
    # Duke Service (Epic 4, FR-GOV-11, FR-GOV-13)
    "DomainOwnershipRequest",
    "DomainOwnershipResult",
    "DomainStatus",
    "DukeServiceProtocol",
    "ExecutionDomain",
    "ProgressReport",
    "ProgressTrackingResult",
    "ResourceAllocation",
    "ResourceAllocationRequest",
    "ResourceAllocationResult",
    "ResourceType",
    "StatusReport",
    "StatusReportResult",
    "TaskProgressStatus",
    # Earl Service (Epic 4, FR-GOV-12, FR-GOV-13)
    "AgentAssignment",
    "AgentCoordination",
    "AgentCoordinationRequest",
    "AgentCoordinationResult",
    "AgentRole",
    "EarlServiceProtocol",
    "ExecutionResult",
    "ExecutionStatus",
    "OptimizationAction",
    "OptimizationReport",
    "OptimizationRequest",
    "OptimizationResult",
    "TaskExecutionRequest",
    "TaskExecutionResult",
    # Marquis Service (Epic 6, FR-GOV-17, FR-GOV-18)
    "Advisory",
    "AdvisoryRequest",
    "AdvisoryResult",
    "ExpertiseDomain",
    "MARQUIS_DOMAIN_MAPPING",
    "MarquisServiceProtocol",
    "RiskAnalysis",
    "RiskAnalysisRequest",
    "RiskAnalysisResult",
    "RiskFactor",
    "RiskLevel",
    "Testimony",
    "TestimonyRequest",
    "TestimonyResult",
    "get_expertise_domain",
    "get_marquis_for_domain",
    # Governance State Machine (Epic 8, FR-GOV-23)
    "GovernanceState",
    "GovernanceStateMachineProtocol",
    "InvalidTransitionError",
    "MotionStateRecord",
    "StateTransition",
    "TERMINAL_STATES",
    "TerminalStateError",
    "TransitionRejection",
    "TransitionRequest",
    "TransitionResult",
    "VALID_TRANSITIONS",
    "get_valid_next_states",
    "is_terminal_state",
    "is_valid_transition",
    # Flow Orchestrator (Epic 8, Story 8.2, FR-GOV-23)
    "BranchResult",
    "ERROR_TYPE_MAP",
    "ErrorEscalationStrategy",
    "EscalationRecord",
    "FlowOrchestratorProtocol",
    "GovernanceBranch",
    "HandleCompletionRequest",
    "HandleCompletionResult",
    "MotionBlockReason",
    "MotionPipelineState",
    "PipelineStatus",
    "ProcessMotionRequest",
    "ProcessMotionResult",
    "RouteMotionRequest",
    "RouteMotionResult",
    "RoutingDecision",
    "STATE_BRANCH_MAP",
    "STATE_SERVICE_MAP",
    "get_branch_for_state",
    "get_escalation_strategy",
    "get_service_for_state",
    "is_blocking_error",
    "is_retryable_error",
]
