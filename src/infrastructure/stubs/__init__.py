"""Infrastructure stubs for development and testing.

This module provides stub implementations of infrastructure ports
for use in development and testing environments.

Available stubs:
- HaltCheckerStub: Configurable halt states (3 modes: always-ok, always-halted, injectable)
- WriterLockStub: Configurable lock behavior (5 modes: default, acquire-fails, ttl-expires,
  heartbeat-fails, contention) - use factory methods for common test scenarios
- EventReplicatorStub: Always returns success (Story 1.10, no replicas configured)
- AgentOrchestratorStub: Simulates agent invocation (Story 2.2, FR10)
- ForkMonitorStub: Returns no forks by default, supports injection (FR16, Story 3.1)
- DualChannelHaltTransportStub: Simulates dual-channel halt (Story 3.3, ADR-3)
- HaltGuardStub: Simulates HaltGuard for testing (Story 3.5, FR20)
- UnwitnessedHaltRepositoryStub: In-memory unwitnessed halt storage (Story 3.9, RT-2)
- WitnessedHaltWriterStub: Simulates witnessed halt event writing (Story 3.9, RT-2)
- TerminalEventDetectorStub: Simulates system termination detection (Story 7.3, NFR40)

WARNING: These stubs are NOT for production use.
Production implementations are in src/infrastructure/adapters/.
"""

from src.infrastructure.stubs.agent_orchestrator_stub import AgentOrchestratorStub
from src.infrastructure.stubs.amendment_repository_stub import AmendmentRepositoryStub
from src.infrastructure.stubs.amendment_visibility_validator_stub import (
    AmendmentVisibilityValidatorStub,
)
from src.infrastructure.stubs.anomaly_detector_stub import (
    DEFAULT_BASELINE_DAILY_RATE,
    DEFAULT_OVERRIDE_COUNT,
    AnomalyDetectorStub,
)
from src.infrastructure.stubs.anti_success_alert_repository_stub import (
    AntiSuccessAlertRepositoryStub,
)
from src.infrastructure.stubs.archon_assignment_stub import (
    ArchonAssignmentOperation,
    ArchonAssignmentServiceStub,
    AssignmentRecord,
)
from src.infrastructure.stubs.archon_pool_stub import (
    ArchonPoolOperation,
    ArchonPoolStub,
    create_test_archon,
)
from src.infrastructure.stubs.audit_repository_stub import (
    AuditRepositoryStub,
    ConfigurableAuditRepositoryStub,
)
from src.infrastructure.stubs.breach_repository_stub import BreachRepositoryStub
from src.infrastructure.stubs.cessation_agenda_repository_stub import (
    CessationAgendaRepositoryStub,
)
from src.infrastructure.stubs.cessation_flag_repository_stub import (
    CessationFlagRepositoryStub,
    FailureMode,
)
from src.infrastructure.stubs.cessation_repository_stub import CessationRepositoryStub
from src.infrastructure.stubs.checkpoint_repository_stub import CheckpointRepositoryStub
from src.infrastructure.stubs.collusion_investigator_stub import (
    CollusionInvestigatorStub,
)
from src.infrastructure.stubs.complexity_budget_repository_stub import (
    ComplexityBudgetRepositoryStub,
)
from src.infrastructure.stubs.complexity_calculator_stub import (
    DEFAULT_ADR_COUNT,
    DEFAULT_CEREMONY_TYPES,
    DEFAULT_CROSS_COMPONENT_DEPS,
    ComplexityCalculatorStub,
)
from src.infrastructure.stubs.compliance_repository_stub import (
    ComplianceRepositoryStub,
)
from src.infrastructure.stubs.configuration_floor_validator_stub import (
    ConfigurationFloorValidatorStub,
)
from src.infrastructure.stubs.consensus_resolver_stub import (
    ConsensusResolverOperation,
    ConsensusResolverStub,
    ResolverCall,
)
from src.infrastructure.stubs.constitution_validator_stub import (
    ConstitutionValidatorStub,
)
from src.infrastructure.stubs.constitutional_health_stub import (
    ConstitutionalHealthStub,
)
from src.infrastructure.stubs.content_hash_service_stub import (
    ContentHashServiceStub,
    HashOperation,
)
from src.infrastructure.stubs.context_package_builder_stub import (
    ContextPackageBuilderStub,
)
from src.infrastructure.stubs.deliberation_orchestrator_stub import (
    DeliberationOrchestratorStub,
    PhaseExecutorStub,
)
from src.infrastructure.stubs.deliberation_timeout_stub import (
    DeliberationTimeoutStub,
)
from src.infrastructure.stubs.disposition_emission_stub import (
    DispositionEmissionStub,
)
from src.infrastructure.stubs.dissent_recorder_stub import (
    DissentRecorderOperation,
    DissentRecorderStub,
)
from src.infrastructure.stubs.dual_channel_halt_stub import DualChannelHaltTransportStub
from src.infrastructure.stubs.emergence_violation_breach_service_stub import (
    EmergenceViolationBreachServiceStub,
)
from src.infrastructure.stubs.entropy_source_stub import (
    DEV_MODE_WARNING,
    EntropySourceStub,
    SecureEntropySourceStub,
)
from src.infrastructure.stubs.escalation_repository_stub import EscalationRepositoryStub
from src.infrastructure.stubs.event_query_stub import (
    EventQueryStub,
)
from src.infrastructure.stubs.event_replicator_stub import EventReplicatorStub
from src.infrastructure.stubs.event_store_stub import EventStoreStub
from src.infrastructure.stubs.external_health_stub import ExternalHealthStub
from src.infrastructure.stubs.failure_mode_registry_stub import (
    FailureModeRegistryStub,
)
from src.infrastructure.stubs.fork_monitor_stub import ForkMonitorStub
from src.infrastructure.stubs.fork_signal_rate_limiter_stub import (
    ForkSignalRateLimiterStub,
)
from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.halt_guard_stub import HaltGuardStub
from src.infrastructure.stubs.halt_state import HaltState
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub
from src.infrastructure.stubs.hash_verifier_stub import HashVerifierStub
from src.infrastructure.stubs.incident_report_repository_stub import (
    IncidentReportRepositoryStub,
)
from src.infrastructure.stubs.independence_attestation_stub import (
    IndependenceAttestationStub,
)
from src.infrastructure.stubs.integrity_case_repository_stub import (
    IntegrityCaseRepositoryStub,
)
from src.infrastructure.stubs.integrity_failure_repository_stub import (
    IntegrityFailureRepositoryStub,
)
from src.infrastructure.stubs.job_scheduler_stub import (
    JobSchedulerStub,
)
from src.infrastructure.stubs.keeper_availability_stub import KeeperAvailabilityStub
from src.infrastructure.stubs.keeper_key_registry_stub import KeeperKeyRegistryStub
from src.infrastructure.stubs.key_generation_ceremony_stub import (
    KeyGenerationCeremonyStub,
)
from src.infrastructure.stubs.material_repository_stub import (
    ConfigurableMaterialRepositoryStub,
    MaterialRepositoryStub,
)
from src.infrastructure.stubs.override_abuse_validator_stub import (
    EVIDENCE_DESTRUCTION_PATTERNS,
    GENERAL_FORBIDDEN_SCOPES,
    HISTORY_EDIT_PATTERNS,
    OverrideAbuseValidatorStub,
)
from src.infrastructure.stubs.override_executor_stub import (
    ExecutedOverride,
    OverrideExecutorStub,
)
from src.infrastructure.stubs.override_registry_stub import OverrideRegistryStub
from src.infrastructure.stubs.override_trend_repository_stub import (
    OverrideTrendRepositoryStub,
)
from src.infrastructure.stubs.petition_event_emitter_stub import (
    EmittedEvent,
    EmittedFateEvent,
    PetitionEventEmitterStub,
)
from src.infrastructure.stubs.petition_repository_stub import PetitionRepositoryStub
from src.infrastructure.stubs.petition_submission_repository_stub import (
    PetitionSubmissionRepositoryStub,
)
from src.infrastructure.stubs.phase_witness_batching_stub import (
    PhaseWitnessBatchingStub,
)
from src.infrastructure.stubs.prohibited_language_scanner_stub import (
    ConfigurableScannerStub,
    ProhibitedLanguageScannerStub,
)
from src.infrastructure.stubs.publication_scanner_stub import (
    ConfigurablePublicationScannerStub,
    PublicationScannerStub,
)
from src.infrastructure.stubs.queue_capacity_stub import (
    QueueCapacityStub,
)
from src.infrastructure.stubs.rate_limiter_stub import (
    RateLimiterStub,
)
from src.infrastructure.stubs.realm_registry_stub import (
    RealmOperation,
    RealmRegistryStub,
)
from src.infrastructure.stubs.recovery_waiting_period_stub import (
    RecoveryWaitingPeriodStub,
)
from src.infrastructure.stubs.seed_validator_stub import SeedValidatorStub
from src.infrastructure.stubs.semantic_scanner_stub import (
    CONFIDENCE_PER_PATTERN,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_SUSPICIOUS_PATTERNS,
    ConfigurableSemanticScannerStub,
    SemanticScannerStub,
)
from src.infrastructure.stubs.separation_validator_stub import SeparationValidatorStub
from src.infrastructure.stubs.sequence_gap_detector_stub import SequenceGapDetectorStub
from src.infrastructure.stubs.signature_verifier_stub import SignatureVerifierStub
from src.infrastructure.stubs.terminal_event_detector_stub import (
    TerminalEventDetectorStub,
)
from src.infrastructure.stubs.threshold_repository_stub import ThresholdRepositoryStub
from src.infrastructure.stubs.topic_daily_limiter_stub import (
    DailySubmissionRecord,
    TopicDailyLimiterStub,
)
from src.infrastructure.stubs.topic_manipulation_detector_stub import (
    TopicManipulationDetectorStub,
)
from src.infrastructure.stubs.topic_priority_stub import (
    QueuedTopic,
    TopicPriorityStub,
)
from src.infrastructure.stubs.unwitnessed_halt_repository_stub import (
    UnwitnessedHaltRepositoryStub,
)
from src.infrastructure.stubs.user_content_repository_stub import (
    UserContentRepositoryStub,
)
from src.infrastructure.stubs.waiver_repository_stub import (
    WaiverRepositoryStub,
)
from src.infrastructure.stubs.witness_anomaly_detector_stub import (
    WitnessAnomalyDetectorStub,
)
from src.infrastructure.stubs.witness_pair_history_stub import (
    InMemoryWitnessPairHistory,
)
from src.infrastructure.stubs.witness_pool_monitor_stub import WitnessPoolMonitorStub
from src.infrastructure.stubs.witnessed_halt_writer_stub import WitnessedHaltWriterStub
from src.infrastructure.stubs.writer_lock_stub import (
    WriterLockConfig,
    WriterLockMode,
    WriterLockStub,
)

__all__: list[str] = [
    "AgentOrchestratorStub",
    "CheckpointRepositoryStub",
    "DualChannelHaltTransportStub",
    "EventReplicatorStub",
    "EventStoreStub",
    "ForkMonitorStub",
    "ForkSignalRateLimiterStub",
    "HaltCheckerStub",
    "HaltGuardStub",
    "HaltState",
    "HaltTriggerStub",
    "RecoveryWaitingPeriodStub",
    "SequenceGapDetectorStub",
    "UnwitnessedHaltRepositoryStub",
    "WitnessedHaltWriterStub",
    "WriterLockConfig",
    "WriterLockMode",
    "WriterLockStub",
    "ExecutedOverride",
    "OverrideExecutorStub",
    "OverrideRegistryStub",
    "ConstitutionValidatorStub",
    "OverrideTrendRepositoryStub",
    "KeeperKeyRegistryStub",
    "KeyGenerationCeremonyStub",
    "KeeperAvailabilityStub",
    "OverrideAbuseValidatorStub",
    "HISTORY_EDIT_PATTERNS",
    "EVIDENCE_DESTRUCTION_PATTERNS",
    "GENERAL_FORBIDDEN_SCOPES",
    "AnomalyDetectorStub",
    "DEFAULT_BASELINE_DAILY_RATE",
    "DEFAULT_OVERRIDE_COUNT",
    "IndependenceAttestationStub",
    "BreachRepositoryStub",
    "EscalationRepositoryStub",
    "CessationRepositoryStub",
    "ThresholdRepositoryStub",
    "DEV_MODE_WARNING",
    "EntropySourceStub",
    "SecureEntropySourceStub",
    "InMemoryWitnessPairHistory",
    "WitnessAnomalyDetectorStub",
    "WitnessPoolMonitorStub",
    "AmendmentRepositoryStub",
    "AmendmentVisibilityValidatorStub",
    # Breach collusion defense (Story 6.8, FR124)
    "CollusionInvestigatorStub",
    # Hash verification (Story 6.8, FR125)
    "HashVerifierStub",
    # Topic manipulation defense (Story 6.9, FR118-FR119)
    "TopicManipulationDetectorStub",
    "SeedValidatorStub",
    "DailySubmissionRecord",
    "TopicDailyLimiterStub",
    "QueuedTopic",
    "TopicPriorityStub",
    # Configuration floor enforcement (Story 6.10, NFR39)
    "ConfigurationFloorValidatorStub",
    # Automatic agenda placement (Story 7.1, FR37-FR38, RT-4)
    "IntegrityFailureRepositoryStub",
    "AntiSuccessAlertRepositoryStub",
    "CessationAgendaRepositoryStub",
    # Petition (Story 7.2, FR39)
    "PetitionRepositoryStub",
    # Petition submission (Story 0.3, AC3)
    "PetitionSubmissionRepositoryStub",
    # Petition event emitter (Story 1.2, FR-1.7; Story 1.7, FR-2.5)
    "EmittedEvent",
    "EmittedFateEvent",
    "PetitionEventEmitterStub",
    # Job Scheduler (Story 0.4, AC3)
    "JobSchedulerStub",
    # Content Hash Service (Story 0.5, AC3)
    "ContentHashServiceStub",
    "HashOperation",
    # Realm Registry (Story 0.6, HP-3, HP-4)
    "RealmOperation",
    "RealmRegistryStub",
    # Archon Pool (Story 0.7, HP-11, FR-11.1)
    "ArchonPoolOperation",
    "ArchonPoolStub",
    "create_test_archon",
    # Archon Assignment Service (Story 2A.2, FR-11.1, FR-11.2)
    "ArchonAssignmentOperation",
    "ArchonAssignmentServiceStub",
    "AssignmentRecord",
    # Context Package Builder (Story 2A.3, FR-11.3)
    "ContextPackageBuilderStub",
    # Deliberation Orchestrator (Story 2A.4, FR-11.4)
    "DeliberationOrchestratorStub",
    "PhaseExecutorStub",
    # Deliberation Timeout (Story 2B.2, FR-11.9, HC-7)
    "DeliberationTimeoutStub",
    # Consensus Resolver (Story 2A.6, FR-11.5, FR-11.6)
    "ConsensusResolverOperation",
    "ConsensusResolverStub",
    "ResolverCall",
    # Phase Witness Batching (Story 2A.7, FR-11.7)
    "PhaseWitnessBatchingStub",
    # Disposition Emission (Story 2A.8, FR-11.11)
    "DispositionEmissionStub",
    # Dissent Recorder (Story 2B.1, FR-11.8)
    "DissentRecorderOperation",
    "DissentRecorderStub",
    # Queue Capacity (Story 1.3, FR-1.4)
    "QueueCapacityStub",
    # Rate Limiter (Story 1.4, FR-1.5, HC-4)
    "RateLimiterStub",
    "SignatureVerifierStub",
    # Schema irreversibility (Story 7.3, FR40, NFR40)
    "TerminalEventDetectorStub",
    # Freeze mechanics (Story 7.4, FR41)
    "FreezeCheckerStub",
    "CessationFlagRepositoryStub",
    "FailureMode",
    # Integrity Case Artifact (Story 7.10, FR144)
    "IntegrityCaseRepositoryStub",
    # Separation Validator (Story 8.2, FR52)
    "SeparationValidatorStub",
    # External Health (Story 8.3, FR54)
    "ExternalHealthStub",
    # Incident Report Repository (Story 8.4, FR54, FR145, FR147)
    "IncidentReportRepositoryStub",
    # Complexity Budget (Story 8.6, CT-14, RT-6, SC-3)
    "ComplexityBudgetRepositoryStub",
    "ComplexityCalculatorStub",
    "DEFAULT_ADR_COUNT",
    "DEFAULT_CEREMONY_TYPES",
    "DEFAULT_CROSS_COMPONENT_DEPS",
    # Failure Mode Registry (Story 8.8, FR106-FR107)
    "FailureModeRegistryStub",
    # Constitutional Health (Story 8.10, ADR-10)
    "ConstitutionalHealthStub",
    # Prohibited Language Scanner (Story 9.1, FR55)
    "ProhibitedLanguageScannerStub",
    "ConfigurableScannerStub",
    # Publication Scanner (Story 9.2, FR56)
    "PublicationScannerStub",
    "ConfigurablePublicationScannerStub",
    # Audit Repository (Story 9.3, FR57)
    "AuditRepositoryStub",
    "ConfigurableAuditRepositoryStub",
    # Material Repository (Story 9.3, FR57)
    "MaterialRepositoryStub",
    "ConfigurableMaterialRepositoryStub",
    # User Content Repository (Story 9.4, FR58)
    "UserContentRepositoryStub",
    # Event Query (Story 9.5, FR108)
    "EventQueryStub",
    # Emergence Violation Breach Service (Story 9.6, FR109)
    "EmergenceViolationBreachServiceStub",
    # Semantic Scanner (Story 9.7, FR110)
    "SemanticScannerStub",
    "ConfigurableSemanticScannerStub",
    "DEFAULT_SUSPICIOUS_PATTERNS",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "CONFIDENCE_PER_PATTERN",
    # Waiver Repository (Story 9.8, SC-4, SR-10)
    "WaiverRepositoryStub",
    # Compliance Repository (Story 9.9, NFR31-34)
    "ComplianceRepositoryStub",
]
